from pathlib import Path

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.sql.task_template import ContractValidationError


def _configure_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "warehouses" / "demo"
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "warehouses/demo",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )
    return project_dir


def _write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _date_contract():
    return {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "etl_date",
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": True,
            }
        ],
    }


@pytest.mark.parametrize(
    ("project", "expected_count"),
    [("shop", 31), ("finance_analytics", 42)],
)
def test_existing_warehouses_remain_legacy_with_stable_task_order(
    project,
    expected_count,
):
    expected_paths = []
    for task_dir in config.project_task_dirs(project):
        expected_paths.extend(sorted(task_dir.glob("*.sql")))
        expected_paths.extend(
            sorted((task_dir / "full_refresh").glob("*.sql"))
        )

    tasks = config.discover_project_tasks(project)

    assert [item.sql_path for item in tasks] == expected_paths
    assert [item.sql_path for item in tasks] == config.iter_project_task_files(
        project
    )
    assert len(tasks) == expected_count
    assert all(not item.is_template for item in tasks)
    assert [item.source_file for item in tasks] == [
        config.task_source_file(project, path) for path in expected_paths
    ]


def test_mixed_legacy_template_and_full_refresh_tasks_are_loaded_explicitly(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    legacy_path = _write(tasks_dir / "a_legacy.sql", "SELECT 1;\n")
    template_path = _write(
        tasks_dir / "b_template.sql",
        "SELECT ${etl_date};\n",
    )
    template_yaml = _write(
        tasks_dir / "b_template.yaml",
        yaml.safe_dump(_date_contract(), sort_keys=False),
    )
    full_path = _write(
        tasks_dir / "full_refresh" / "c_full_refresh.sql",
        "SELECT ${etl_date};\n",
    )
    full_yaml = _write(
        tasks_dir / "full_refresh" / "c_full_refresh.yml",
        yaml.safe_dump(_date_contract(), sort_keys=False),
    )

    tasks = config.discover_project_tasks("demo")

    assert [item.sql_path for item in tasks] == [
        legacy_path,
        template_path,
        full_path,
    ]
    assert [item.is_template for item in tasks] == [False, True, True]
    assert [item.contract_path for item in tasks] == [
        None,
        template_yaml,
        full_yaml,
    ]
    assert [item.source_file for item in tasks] == [
        "a_legacy.sql",
        "b_template.sql",
        "full_refresh/c_full_refresh.sql",
    ]
    assert tasks[1].template_definition.placeholder_names == ("etl_date",)
    assert tasks[2].is_full_refresh is True
    assert (
        config.discover_project_tasks("demo", include_full_refresh=False)
        == tasks[:2]
    )
    assert (
        config.task_path_for_source_file(
            "demo", "full_refresh/c_full_refresh.sql"
        )
        == full_path
    )


def test_template_marker_without_contract_fails_during_discovery(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    sql_path = _write(
        project_dir / "mid" / "tasks" / "missing.sql",
        "SELECT ${etl_date};\n",
    )

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")

    assert raised.value.code == "template.asset.missing_contract"
    assert str(sql_path) in str(raised.value)


def test_orphan_and_duplicate_task_contracts_fail_closed(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    orphan = _write(tasks_dir / "orphan.yaml", "version: 1\n")

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")
    assert raised.value.code == "template.asset.orphan_contract"
    assert str(orphan) in str(raised.value)

    orphan.unlink()
    _write(tasks_dir / "job.sql", "SELECT 1;\n")
    _write(tasks_dir / "job.yaml", "version: 1\nstrict: true\n")
    duplicate = _write(tasks_dir / "job.yml", "version: 1\nstrict: true\n")

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")
    assert raised.value.code == "template.asset.duplicate_contract"
    assert str(duplicate) in str(raised.value)


def test_full_refresh_companion_does_not_inherit_main_task_contract(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    main_path = _write(tasks_dir / "job.sql", "SELECT ${etl_date};\n")
    _write(
        tasks_dir / "job.yaml",
        yaml.safe_dump(_date_contract(), sort_keys=False),
    )
    full_path = _write(
        tasks_dir / "full_refresh" / "job_full_refresh.sql",
        "SELECT ${etl_date};\n",
    )

    main_only = config.discover_project_tasks(
        "demo",
        include_full_refresh=False,
    )
    assert [item.sql_path for item in main_only] == [main_path]
    assert (
        config.task_path_for_job(
            "demo",
            "job",
            include_full_refresh=False,
        )
        == main_path
    )

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")

    assert raised.value.code == "template.asset.missing_contract"
    assert str(full_path) in str(raised.value)


@pytest.mark.parametrize(
    ("first_role", "first_name", "second_role", "second_name", "code"),
    [
        ("mid", "Job.sql", "mid", "job.sql", "duplicate_job"),
        (
            "mid",
            "Customer.sql",
            "ads",
            "customer.sql",
            "cross_role_job_collision",
        ),
    ],
)
def test_casefold_job_collisions_fail_before_consumers_run(
    monkeypatch,
    tmp_path,
    first_role,
    first_name,
    second_role,
    second_name,
    code,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    _write(project_dir / first_role / "tasks" / first_name, "SELECT 1;\n")
    second_dir = project_dir / second_role / "tasks"
    if first_role == second_role:
        second_dir = second_dir / "full_refresh"
    _write(second_dir / second_name, "SELECT 1;\n")

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")

    assert raised.value.code == f"template.asset.{code}"


def test_yaml_must_match_sql_directory_and_exact_stem(monkeypatch, tmp_path):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    _write(tasks_dir / "job.sql", "SELECT ${etl_date};\n")
    mismatch = _write(
        tasks_dir / "full_refresh" / "job.yaml",
        yaml.safe_dump(_date_contract(), sort_keys=False),
    )

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")

    assert raised.value.code == "template.asset.orphan_contract"
    assert str(mismatch) in str(raised.value)


def test_task_path_for_job_preserves_primary_then_full_refresh_lookup(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    primary = _write(tasks_dir / "customer.sql", "SELECT 1;\n")
    full = _write(
        tasks_dir / "full_refresh" / "inventory_full_refresh.sql",
        "SELECT 1;\n",
    )

    assert config.task_path_for_job("demo", "customer") == primary
    assert config.task_path_for_job("demo", "inventory") == full
    assert (
        config.task_path_for_job(
            "demo", "inventory", include_full_refresh=False
        )
        is None
    )
    assert isinstance(primary, Path)


def test_task_path_for_job_uses_casefold_identity_on_every_filesystem(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    mixed_case = _write(
        project_dir / "mid" / "tasks" / "CustomerJob.sql",
        "SELECT 1;\n",
    )

    assert (
        config.task_path_for_job(
            "demo",
            "customerjob",
            include_full_refresh=False,
        )
        == mixed_case
    )


def test_template_discovery_reads_sql_once_and_lookup_does_not_parse_yaml(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    sql_path = _write(tasks_dir / "template.sql", "SELECT ${etl_date};\n")
    _write(
        tasks_dir / "template.yaml",
        yaml.safe_dump(_date_contract(), sort_keys=False),
    )
    original_read_text = Path.read_text
    sql_reads = []

    def tracking_read_text(path, *args, **kwargs):
        if path == sql_path:
            sql_reads.append(path)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)

    tasks = config.discover_project_tasks("demo")
    assert tasks[0].template_definition.sql_text == "SELECT ${etl_date};\n"
    assert sql_reads == [sql_path]

    assert config.task_path_for_job("demo", "template") == sql_path
    assert config.task_path_for_source_file("demo", "template.sql") == sql_path
    assert sql_reads == [sql_path]


def test_lightweight_lookup_ignores_sql_named_directories_and_directory_links(
    monkeypatch,
    tmp_path,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    fake_directory = tasks_dir / "fake.sql"
    fake_directory.mkdir(parents=True)
    directory_link = tasks_dir / "linked.sql"
    directory_link.symlink_to(fake_directory, target_is_directory=True)

    assert config.discover_project_tasks("demo") == []
    assert config.task_path_for_job("demo", "fake") is None
    assert config.task_path_for_job("demo", "linked") is None


@pytest.mark.parametrize("template", [False, True])
def test_discovery_wraps_invalid_sql_encoding_in_structured_errors(
    monkeypatch,
    tmp_path,
    template,
):
    project_dir = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    sql_path = tasks_dir / "bad.sql"
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_bytes(b"SELECT '\xff';")
    if template:
        _write(
            tasks_dir / "bad.yaml",
            "version: 1\nstrict: true\n",
        )

    with pytest.raises(ContractValidationError) as raised:
        config.discover_project_tasks("demo")

    expected_code = (
        "template.sql.read_failed"
        if template
        else "template.asset.sql_read_failed"
    )
    assert raised.value.code == expected_code
    assert str(sql_path) in str(raised.value)
