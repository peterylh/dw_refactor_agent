import threading

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.model_metadata_publication import (
    MetadataPublicationConflict,
    MetadataPublicationError,
    MetadataPublicationOutcome,
    MetadataPublicationRecoveryRequired,
    capture_metadata_publication_snapshot,
    metadata_publication_journal_path,
    recover_metadata_publication,
    transactional_metadata_publication,
)
from tests.assess.model_metadata_writer_test_support import (
    _configure_project_root,
)


@pytest.fixture
def publication_project(tmp_path, monkeypatch):
    project = "transactional_publication"
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": f"warehouses/{project}"},
    )
    _configure_project_root(monkeypatch, tmp_path)
    directory = tmp_path / "warehouses" / project
    (directory / "mid" / "models").mkdir(parents=True)
    return project, directory


def _assert_no_transaction_artifacts(directory):
    assert not list(directory.rglob("*.staged"))
    assert not list(directory.rglob("*.backup"))


def test_transaction_publishes_create_replace_delete_and_fsyncs_journal(
    publication_project,
):
    project, directory = publication_project
    replaced = directory / "mid" / "models" / "replaced.yaml"
    deleted = directory / "mid" / "models" / "deleted.yaml"
    created = directory / "business_processes.yaml"
    replaced.write_text("old: replaced\n", encoding="utf-8")
    deleted.write_text("old: deleted\n", encoding="utf-8")
    snapshot = capture_metadata_publication_snapshot(project)

    outcome = transactional_metadata_publication(
        project,
        {replaced: "new: replaced\n", created: "new: created\n"},
        delete_paths=(deleted,),
        expected_snapshot=snapshot,
    )

    assert outcome.formal_files_state == "published"
    assert outcome.recovery_required is False
    assert replaced.read_text(encoding="utf-8") == "new: replaced\n"
    assert created.read_text(encoding="utf-8") == "new: created\n"
    assert not deleted.exists()
    assert not metadata_publication_journal_path(project).exists()
    _assert_no_transaction_artifacts(directory)


@pytest.mark.parametrize("change_after_staging", [False, True])
def test_publication_cas_rejects_manual_change(
    publication_project, change_after_staging
):
    project, directory = publication_project
    model = directory / "mid" / "models" / "fact.yaml"
    model.write_text("value: old\n", encoding="utf-8")
    snapshot = capture_metadata_publication_snapshot(project)

    def edit_after_staging(stage):
        if stage == "stage":
            model.write_text("value: manual\n", encoding="utf-8")

    failure_injector = edit_after_staging if change_after_staging else None
    if not change_after_staging:
        model.write_text("value: manual\n", encoding="utf-8")

    with pytest.raises(MetadataPublicationConflict) as raised:
        transactional_metadata_publication(
            project,
            {model: "value: stale-writer\n"},
            expected_snapshot=snapshot,
            failure_injector=failure_injector,
        )

    assert raised.value.outcome.formal_files_state == "unchanged"
    assert model.read_text(encoding="utf-8") == "value: manual\n"
    assert not metadata_publication_journal_path(project).exists()


@pytest.mark.parametrize(
    "failed_stage", ["stage", "backup", "install", "verify"]
)
def test_ordinary_stage_failures_roll_back_complete_file_set(
    publication_project, failed_stage
):
    project, directory = publication_project
    first = directory / "mid" / "models" / "first.yaml"
    second = directory / "mid" / "models" / "second.yaml"
    deleted = directory / "mid" / "models" / "deleted.yaml"
    first.write_text("value: old-first\n", encoding="utf-8")
    second.write_text("value: old-second\n", encoding="utf-8")
    deleted.write_text("value: old-deleted\n", encoding="utf-8")

    def fail(stage):
        if stage == failed_stage:
            raise OSError(f"failed at {stage}")

    with pytest.raises(MetadataPublicationError) as raised:
        transactional_metadata_publication(
            project,
            {first: "value: new-first\n", second: "value: new-second\n"},
            delete_paths=(deleted,),
            failure_injector=fail,
        )

    assert raised.value.outcome.formal_files_state == "unchanged"
    assert first.read_text(encoding="utf-8") == "value: old-first\n"
    assert second.read_text(encoding="utf-8") == "value: old-second\n"
    assert deleted.read_text(encoding="utf-8") == "value: old-deleted\n"
    assert not metadata_publication_journal_path(project).exists()
    _assert_no_transaction_artifacts(directory)


@pytest.mark.parametrize(
    ("interrupt_stage", "recovered_action", "expected_value"),
    [
        ("install", "rollback", "value: old\n"),
        ("finalize", "commit", "value: new\n"),
    ],
)
def test_interrupted_publication_is_recovered_on_next_entry(
    publication_project,
    interrupt_stage,
    recovered_action,
    expected_value,
):
    project, directory = publication_project
    model = directory / "mid" / "models" / "fact.yaml"
    model.write_text("value: old\n", encoding="utf-8")

    def interrupt(stage):
        if stage == interrupt_stage:
            raise KeyboardInterrupt(stage)

    with pytest.raises(KeyboardInterrupt):
        transactional_metadata_publication(
            project,
            {model: "value: new\n"},
            failure_injector=interrupt,
        )
    assert metadata_publication_journal_path(project).exists()

    outcome = recover_metadata_publication(project)

    assert outcome.formal_files_state == "recovered"
    assert outcome.recovered_action == recovered_action
    assert model.read_text(encoding="utf-8") == expected_value
    assert not metadata_publication_journal_path(project).exists()
    _assert_no_transaction_artifacts(directory)


def test_finalization_failure_does_not_misreport_published_files(
    publication_project,
):
    project, directory = publication_project
    model = directory / "mid" / "models" / "fact.yaml"

    def fail_finalization(stage):
        if stage == "finalize":
            raise OSError("journal cleanup unavailable")

    with pytest.raises(MetadataPublicationRecoveryRequired) as raised:
        transactional_metadata_publication(
            project,
            {model: "value: published\n"},
            failure_injector=fail_finalization,
        )

    assert raised.value.outcome == MetadataPublicationOutcome(
        formal_files_state="published",
        finalization_status="failed",
        recovery_required=True,
        transaction_id=raised.value.outcome.transaction_id,
        error="OSError: journal cleanup unavailable",
    )
    assert model.read_text(encoding="utf-8") == "value: published\n"
    assert metadata_publication_journal_path(project).exists()
    assert recover_metadata_publication(project).recovered_action == "commit"


def test_same_project_writers_serialize_and_stale_writer_loses_cas(
    publication_project,
):
    project, directory = publication_project
    first_writer, second_writer = "generate", "refresh"
    model = directory / "mid" / "models" / "fact.yaml"
    model.write_text("writer: base\n", encoding="utf-8")
    base = capture_metadata_publication_snapshot(project)
    first_holds_lock = threading.Event()
    release_first = threading.Event()
    outcomes = {}

    def first_failure_hook(stage):
        if stage == "stage":
            first_holds_lock.set()
            assert release_first.wait(timeout=5)

    def publish_first():
        outcomes[first_writer] = transactional_metadata_publication(
            project,
            {model: f"writer: {first_writer}\n"},
            expected_snapshot=base,
            failure_injector=first_failure_hook,
        )

    def publish_second():
        assert first_holds_lock.wait(timeout=5)
        try:
            transactional_metadata_publication(
                project,
                {model: f"writer: {second_writer}\n"},
                expected_snapshot=base,
            )
        except MetadataPublicationConflict as exc:
            outcomes[second_writer] = exc

    first_thread = threading.Thread(target=publish_first)
    second_thread = threading.Thread(target=publish_second)
    first_thread.start()
    second_thread.start()
    assert first_holds_lock.wait(timeout=5)
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert outcomes[first_writer].formal_files_state == "published"
    assert isinstance(outcomes[second_writer], MetadataPublicationConflict)
    assert model.read_text(encoding="utf-8") == f"writer: {first_writer}\n"


def test_different_projects_do_not_share_publication_lock(
    publication_project, tmp_path, monkeypatch
):
    first_project, first_directory = publication_project
    second_project = "transactional_publication_other"
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        second_project,
        {"dir": f"warehouses/{second_project}"},
    )
    second_directory = tmp_path / "warehouses" / second_project
    (second_directory / "mid" / "models").mkdir(parents=True)
    first = first_directory / "mid" / "models" / "fact.yaml"
    second = second_directory / "mid" / "models" / "fact.yaml"
    first_started = threading.Event()
    release_first = threading.Event()
    second_finished = threading.Event()

    def hold_first(stage):
        if stage == "stage":
            first_started.set()
            assert release_first.wait(timeout=5)

    def publish_first():
        transactional_metadata_publication(
            first_project,
            {first: "writer: first\n"},
            failure_injector=hold_first,
        )

    def publish_second():
        assert first_started.wait(timeout=5)
        transactional_metadata_publication(
            second_project,
            {second: "writer: second\n"},
        )
        second_finished.set()

    first_thread = threading.Thread(target=publish_first)
    second_thread = threading.Thread(target=publish_second)
    first_thread.start()
    second_thread.start()
    assert second_finished.wait(timeout=5)
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert first.read_text(encoding="utf-8") == "writer: first\n"
    assert second.read_text(encoding="utf-8") == "writer: second\n"
