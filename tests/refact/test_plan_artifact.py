import hashlib
import json

import pytest

import dw_refactor_agent.refactor.plan_artifact as plan_artifact_module
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.plan_artifact import (
    StalePlanError,
    analysis_input_fingerprints,
    calculate_plan_fingerprint,
    load_persisted_verification_plan,
    load_verification_plan,
    require_fresh_plan,
    write_verification_plan,
)
from dw_refactor_agent.refactor.session import write_manifest

_WORKSPACE_DIGEST = "sha256:" + "a" * 64


def _plan(ddl_by_table):
    return {
        "project": "demo",
        "project_db": "demo_dm",
        "qa_db": "demo_dm_qa",
        "baseline_ddl": ddl_by_table,
        "ddl_changes": [],
        "jobs_to_run": [],
        "verification": {"checks": []},
        "analysis_snapshot": {
            "partition": None,
            "workspace_fingerprint": _WORKSPACE_DIGEST,
        },
    }


def _write_persisted_plan(path, payload):
    base = _plan({})
    base.pop("baseline_ddl")
    persisted = {"format_version": 1, **base, **payload}
    persisted["plan_fingerprint"] = calculate_plan_fingerprint(persisted)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(persisted), encoding="utf-8")
    return persisted


def _write_fresh_run_bundle(tmp_path, *, workspace=_WORKSPACE_DIGEST):
    run_root = tmp_path / "run"
    manifest_path = run_root / "manifest.json"
    manifest = {
        "format_version": 1,
        "run_id": "run",
        "project": "demo",
        "root": str(tmp_path),
        "base_git": {"head": "base"},
        "artifacts": {
            "baseline_lineage": "baseline/lineage.json",
            "current_lineage": "current/lineage.json",
            "change_analysis": "analysis/change.json",
            "verification_plan": "verification/plan.json",
        },
        "verification_intent": {"semantic_modes": {}},
    }
    write_manifest(manifest_path, manifest)
    values = {
        "baseline_lineage": {"tables": ["baseline"]},
        "current_lineage": {"tables": ["current"]},
        "change_analysis": {"changed_files": ["one.sql"]},
    }
    for key, value in values.items():
        path = run_root / manifest["artifacts"][key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    plan_path = run_root / manifest["artifacts"]["verification_plan"]
    write_verification_plan(
        plan_path,
        {
            **_plan({}),
            "analysis_snapshot": {
                "partition": "2024-12-31",
                "workspace_fingerprint": workspace,
                "analysis_inputs": analysis_input_fingerprints(
                    manifest=manifest,
                    baseline_lineage=values["baseline_lineage"],
                    current_lineage=values["current_lineage"],
                    change_analysis=values["change_analysis"],
                ),
            },
        },
    )
    return manifest_path, manifest, plan_path


def test_write_verification_plan_externalizes_exact_ddl_and_hashes_bytes(
    tmp_path,
):
    plan_path = tmp_path / "verification" / "plan.json"
    ddl = (
        "CREATE TABLE demo_dm.dwd_order (id BIGINT, amount DECIMAL(10, 2)) "
        "ENGINE=OLAP DISTRIBUTED BY HASH(id) BUCKETS 1;"
    )

    persisted = write_verification_plan(plan_path, _plan({"dwd_order": ddl}))

    ddl_path = next(
        (plan_path.parent / "baseline_ddl").glob("dwd_order.*.sql")
    )
    ddl_bytes = ddl_path.read_bytes()
    ddl_text = ddl_bytes.decode("utf-8")
    on_disk_plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert persisted == on_disk_plan
    assert persisted["format_version"] == 1
    assert persisted["plan_fingerprint"] == calculate_plan_fingerprint(
        persisted
    )
    assert "baseline_ddl" not in persisted
    assert persisted["baseline_ddl_refs"] == {
        "dwd_order": {
            "path": f"baseline_ddl/{ddl_path.name}",
            "sha256": hashlib.sha256(ddl_bytes).hexdigest(),
        }
    }
    assert ddl_text == ddl


def test_load_persisted_plan_detects_plan_body_edit(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    persisted = write_verification_plan(plan_path, _plan({}))
    persisted["qa_db"] = "tampered"
    plan_path.write_text(json.dumps(persisted), encoding="utf-8")

    with pytest.raises(ArtifactFormatError, match="plan_fingerprint"):
        load_persisted_verification_plan(plan_path)


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("project", None, "project.*non-empty string"),
        ("jobs_to_run", {}, "jobs_to_run.*list"),
        ("ddl_changes", {}, "ddl_changes.*list"),
        ("verification", [], "verification.*mapping"),
    ],
)
def test_load_persisted_plan_rejects_malformed_core_schema(
    tmp_path, field, value, expected
):
    plan_path = tmp_path / "verification" / "plan.json"
    persisted = write_verification_plan(plan_path, _plan({}))
    persisted[field] = value
    persisted["plan_fingerprint"] = calculate_plan_fingerprint(persisted)
    plan_path.write_text(json.dumps(persisted), encoding="utf-8")

    with pytest.raises(ArtifactFormatError, match=expected):
        load_persisted_verification_plan(plan_path)


def test_write_verification_plan_preserves_multiline_ddl_exactly(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    ddl = """-- @table_id: abc
CREATE TABLE demo_dm.dwd_order (
    -- @column_id: def
    id BIGINT
) ENGINE=OLAP;
"""

    write_verification_plan(plan_path, _plan({"dwd_order": ddl}))

    ddl_path = next(
        (plan_path.parent / "baseline_ddl").glob("dwd_order.*.sql")
    )
    assert ddl_path.read_text(encoding="utf-8") == ddl


def test_write_verification_plan_removes_stale_sql_files(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    ddl_dir = plan_path.parent / "baseline_ddl"
    ddl_dir.mkdir(parents=True)
    stale_path = ddl_dir / "stale.sql"
    stale_path.write_text("CREATE TABLE stale (id INT);\n", encoding="utf-8")
    keep_path = ddl_dir / "notes.txt"
    keep_path.write_text("operator notes", encoding="utf-8")

    write_verification_plan(
        plan_path,
        _plan({"current": "CREATE TABLE current (id INT);"}),
    )

    assert not stale_path.exists()
    assert keep_path.exists()
    assert list(ddl_dir.glob("current.*.sql"))


def test_write_verification_plan_invalidates_downstream_results(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = plan_path.parent / "shadow_run_result.json"
    compare_path = plan_path.parent / "compare_result.json"
    shadow_path.parent.mkdir(parents=True)
    shadow_path.write_text('{"status":"completed"}', encoding="utf-8")
    compare_path.write_text(
        '{"verification_status":"passed"}', encoding="utf-8"
    )

    write_verification_plan(plan_path, _plan({}))

    assert not shadow_path.exists()
    assert not compare_path.exists()


def test_write_verification_plan_keeps_stale_files_when_plan_write_fails(
    tmp_path,
):
    plan_path = tmp_path / "verification" / "plan.json"
    plan_path.mkdir(parents=True)
    ddl_dir = plan_path.parent / "baseline_ddl"
    ddl_dir.mkdir()
    stale_path = ddl_dir / "stale.sql"
    stale_path.write_text("CREATE TABLE stale (id INT);\n", encoding="utf-8")

    with pytest.raises(IsADirectoryError):
        write_verification_plan(
            plan_path,
            _plan({"current": "CREATE TABLE current (id INT);"}),
        )

    assert stale_path.exists()


@pytest.mark.parametrize(
    "table_name",
    ["../escape", "nested/table", "nested\\table", "", ".", ".."],
)
def test_write_verification_plan_rejects_unsafe_table_filenames(
    tmp_path, table_name
):
    plan_path = tmp_path / "verification" / "plan.json"

    with pytest.raises(ValueError, match="baseline DDL table name"):
        write_verification_plan(
            plan_path,
            _plan({table_name: "CREATE TABLE invalid (id INT);"}),
        )

    assert not plan_path.exists()


def test_load_verification_plan_materializes_referenced_ddl(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    write_verification_plan(
        plan_path,
        _plan({"dwd_order": "CREATE TABLE dwd_order (id INT);"}),
    )

    loaded = load_verification_plan(plan_path)

    assert loaded["baseline_ddl"] == {
        "dwd_order": "CREATE TABLE dwd_order (id INT);"
    }
    assert "baseline_ddl_refs" in loaded


def test_load_verification_plan_accepts_empty_reference_map(tmp_path):
    plan_path = tmp_path / "plan.json"
    _write_persisted_plan(plan_path, {"baseline_ddl_refs": {}})

    assert load_verification_plan(plan_path)["baseline_ddl"] == {}


def test_load_verification_plan_rejects_legacy_embedded_ddl(tmp_path):
    plan_path = tmp_path / "plan.json"
    _write_persisted_plan(
        plan_path,
        {"baseline_ddl": {}, "baseline_ddl_refs": {}},
    )

    with pytest.raises(ValueError, match="legacy.*baseline_ddl.*analyze"):
        load_verification_plan(plan_path)


@pytest.mark.parametrize(
    "refs, expected_message",
    [
        (None, "baseline_ddl_refs must be a mapping"),
        ({"dwd_order": "baseline_ddl/dwd_order.sql"}, "reference.*mapping"),
        (
            {"dwd_order": {"sha256": "a" * 64}},
            "reference path must be a non-empty string",
        ),
        (
            {
                "dwd_order": {
                    "path": "baseline_ddl/dwd_order.sql",
                    "sha256": "invalid",
                }
            },
            "sha256 must be 64 lowercase hex characters",
        ),
    ],
)
def test_load_verification_plan_rejects_malformed_references(
    tmp_path, refs, expected_message
):
    plan_path = tmp_path / "plan.json"
    _write_persisted_plan(plan_path, {"baseline_ddl_refs": refs})

    with pytest.raises(ValueError, match=expected_message):
        load_verification_plan(plan_path)


@pytest.mark.parametrize(
    "reference_path",
    ["../outside.sql", "/tmp/outside.sql"],
)
def test_load_verification_plan_rejects_unsafe_reference_paths(
    tmp_path, reference_path
):
    plan_path = tmp_path / "verification" / "plan.json"
    _write_persisted_plan(
        plan_path,
        {
            "baseline_ddl_refs": {
                "dwd_order": {
                    "path": reference_path,
                    "sha256": "a" * 64,
                }
            }
        },
    )

    with pytest.raises(ValueError, match="unsafe baseline DDL path"):
        load_verification_plan(plan_path)


def test_load_verification_plan_rejects_missing_file(tmp_path):
    plan_path = tmp_path / "plan.json"
    _write_persisted_plan(
        plan_path,
        {
            "baseline_ddl_refs": {
                "dwd_order": {
                    "path": "baseline_ddl/dwd_order.sql",
                    "sha256": "a" * 64,
                }
            }
        },
    )

    with pytest.raises(ValueError, match="dwd_order.*does not exist"):
        load_verification_plan(plan_path)


def test_load_verification_plan_rejects_digest_mismatch(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    persisted = write_verification_plan(
        plan_path,
        _plan({"dwd_order": "CREATE TABLE dwd_order (id INT);"}),
    )
    persisted["baseline_ddl_refs"]["dwd_order"]["sha256"] = "0" * 64
    persisted["plan_fingerprint"] = calculate_plan_fingerprint(persisted)
    plan_path.write_text(json.dumps(persisted), encoding="utf-8")

    with pytest.raises(ValueError, match="dwd_order.*SHA-256 mismatch"):
        load_verification_plan(plan_path)


def test_require_fresh_plan_matches_analysis_workspace_snapshot(
    tmp_path, monkeypatch
):
    _manifest_path, _manifest, plan_path = _write_fresh_run_bundle(tmp_path)
    monkeypatch.setattr(
        plan_artifact_module,
        "workspace_fingerprint",
        lambda root, project: _WORKSPACE_DIGEST,
    )

    persisted = require_fresh_plan(plan_path, root=tmp_path, project="demo")

    assert persisted["analysis_snapshot"]["partition"] == "2024-12-31"


def test_require_fresh_plan_rejects_workspace_drift(tmp_path, monkeypatch):
    _manifest_path, _manifest, plan_path = _write_fresh_run_bundle(
        tmp_path, workspace=_WORKSPACE_DIGEST
    )
    monkeypatch.setattr(
        plan_artifact_module,
        "workspace_fingerprint",
        lambda root, project: "sha256:" + "b" * 64,
    )

    with pytest.raises(StalePlanError, match="stale_plan.*analyze"):
        require_fresh_plan(plan_path, root=tmp_path, project="demo")


def test_require_fresh_plan_rejects_persisted_analysis_input_drift(
    tmp_path, monkeypatch
):
    _manifest_path, manifest, plan_path = _write_fresh_run_bundle(tmp_path)
    monkeypatch.setattr(
        plan_artifact_module,
        "workspace_fingerprint",
        lambda root, project: _WORKSPACE_DIGEST,
    )
    change_path = (
        plan_path.parent.parent / manifest["artifacts"]["change_analysis"]
    )
    change_path.write_text(
        json.dumps({"changed_files": ["substituted.sql"]}),
        encoding="utf-8",
    )

    with pytest.raises(
        StalePlanError, match="analysis input.*change_analysis"
    ):
        require_fresh_plan(plan_path, root=tmp_path, project="demo")


def test_require_fresh_plan_rejects_semantic_intent_drift(
    tmp_path, monkeypatch
):
    manifest_path, manifest, plan_path = _write_fresh_run_bundle(tmp_path)
    monkeypatch.setattr(
        plan_artifact_module,
        "workspace_fingerprint",
        lambda root, project: _WORKSPACE_DIGEST,
    )
    manifest["verification_intent"]["semantic_modes"]["dws_sales"] = {
        "mode": "changed"
    }
    write_manifest(manifest_path, manifest)

    with pytest.raises(StalePlanError, match="semantic intent"):
        require_fresh_plan(plan_path, root=tmp_path, project="demo")
