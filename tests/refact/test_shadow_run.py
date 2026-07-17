from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from datetime import datetime

import pytest
import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

import dw_refactor_agent.refactor.shadow_run as shadow_run_module
from dw_refactor_agent.lineage.job_dag import JobDAG
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.execution_provenance import _lock_path
from dw_refactor_agent.refactor.plan_artifact import (
    analysis_input_fingerprints,
    write_verification_plan,
)
from dw_refactor_agent.refactor.qa_pool import QaSlotOwnership
from dw_refactor_agent.refactor.session import write_manifest
from dw_refactor_agent.refactor.shadow_rewrite import (
    RewriteContext,
    rewrite_shadow_sql,
)
from dw_refactor_agent.refactor.shadow_run import (
    ShadowRunSqlError,
    _wait_for_table_alter_jobs,
    main,
    run_shadow_plan,
)
from dw_refactor_agent.refactor.shadow_run import (
    execute_shadow_plan as _execute_shadow_plan,
)
from dw_refactor_agent.refactor.workspace_snapshot import workspace_fingerprint

TIMING_KEYS = {"started_at", "finished_at", "duration_ms"}


def test_shadow_scheduler_rejects_missing_dependency_snapshot(tmp_path):
    project = "stale_scheduler"
    _write_shadow_job_dag(
        tmp_path,
        project,
        ("Prepare_Sales", "Build_Report"),
    )
    plan = {
        "project": project,
        "jobs_to_run": [
            {"job": "Prepare_Sales"},
            {"job": "Build_Report"},
        ],
    }

    with pytest.raises(
        ArtifactFormatError, match="execution_graph.*run analyze again"
    ):
        shadow_run_module._job_dependencies_from_plan(plan, tmp_path)


def test_run_execution_lock_matches_across_worktrees_but_differs_by_run(
    tmp_path,
):
    prefix = "warehouses/shop/artifacts/refactor_runs"
    first = _lock_path(
        tmp_path / "worktree-one" / prefix / "run-a/verification/plan.json"
    )
    second = _lock_path(
        tmp_path / "worktree-two" / prefix / "run-a/verification/plan.json"
    )
    other = _lock_path(
        tmp_path / "worktree-two" / prefix / "run-b/verification/plan.json"
    )

    assert first == second
    assert first != other
    assert first.name == "shop.run-a.shadow_execution.lock"


def _without_timing(result: dict) -> dict:
    return {
        key: value for key, value in result.items() if key not in TIMING_KEYS
    }


def _assert_timing(result: dict) -> None:
    assert set(result) >= TIMING_KEYS
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0
    started_at = datetime.fromisoformat(result["started_at"])
    finished_at = datetime.fromisoformat(result["finished_at"])
    assert finished_at >= started_at


def _table_refs(sql: str) -> list[tuple[str, str]]:
    statements = sqlglot.parse(
        sql, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    refs = []
    for stmt in statements:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            refs.append((table.name, table.db))
    return refs


def _rewrite_with_context(
    sql_text: str,
    prod_db: str,
    qa_db: str,
    qa_ready_tables: set[str],
    selected_tables: set[str] | None = None,
) -> str:
    qa_ready = set(qa_ready_tables)
    return rewrite_shadow_sql(
        sql_text,
        RewriteContext(
            prod_db=prod_db,
            qa_db=qa_db,
            selected_tables=set(selected_tables or set()) | qa_ready,
            qa_ready_tables=qa_ready,
        ),
    )


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _provenance(plan_path):
    persisted_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return {
        "workspace_fingerprint": persisted_plan["analysis_snapshot"][
            "workspace_fingerprint"
        ],
        "plan_fingerprint": persisted_plan["plan_fingerprint"],
    }


def _analysis_snapshot():
    return {
        "partition": None,
        "workspace_fingerprint": "sha256:workspace",
    }


def _claimed_ownership(plan, database=None):
    return QaSlotOwnership(
        2,
        plan.get("project", "shop"),
        plan.get("run_id", "test-run"),
        "execution-1",
        database or plan["qa_db"],
        plan.get("plan_fingerprint", "sha256:" + "a" * 64),
        (plan.get("analysis_snapshot") or {}).get(
            "workspace_fingerprint", "sha256:" + "b" * 64
        ),
        "2026-07-14 12:00:00",
        1784001600,
    )


def execute_shadow_plan(plan, *, root, dry_run=False, **kwargs):
    """Exercise the production core with an explicit synthetic claim."""
    dependencies = plan.pop("job_dependencies", None) or {}
    plan.setdefault(
        "execution_graph",
        {
            "format_version": 1,
            "project": plan["project"],
            "jobs": [job["job"] for job in plan.get("jobs_to_run") or []],
            "dependencies": dependencies,
        },
    )
    return _execute_shadow_plan(
        plan,
        root=root,
        dry_run=dry_run,
        claimed_ownership=(None if dry_run else _claimed_ownership(plan)),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _stub_qa_pool_boundary(monkeypatch):
    monkeypatch.setattr(
        shadow_run_module,
        "require_slot_ownership",
        lambda **kwargs: None,
        raising=False,
    )

    def fake_claim(**kwargs):
        return QaSlotOwnership(
            2,
            kwargs["project"],
            kwargs["run_id"],
            kwargs["execution_id"],
            kwargs["pool"][0],
            kwargs["plan_fingerprint"],
            kwargs["workspace_fingerprint"],
            "2026-07-14 12:00:00",
            1784001600,
        )

    monkeypatch.setattr(
        shadow_run_module,
        "claim_qa_slot",
        fake_claim,
        raising=False,
    )


def _write_shadow_cli_plan(plan_path):
    return _write_fresh_plan_bundle(
        plan_path,
        {
            "project": "shop",
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "qa_database_pool": ["shop_dm_qa", "shop_dm_qa_02"],
            "baseline_ddl": {},
            "ddl_changes": [],
            "jobs_to_run": [],
            "verification": {"checks": []},
            "analysis_snapshot": _analysis_snapshot(),
        },
    )


def _write_shadow_project(
    tmp_path, project: str, *, with_default_slice: bool = False
) -> None:
    project_dir = tmp_path / "warehouses" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    execution = ""
    if with_default_slice:
        execution = """execution:
  default_slice:
    param: etl_date
    column: stat_date
    period: D
"""
    (project_dir / "warehouse.yaml").write_text(
        f"""name: {project}
catalog: internal
database: shadow_dm
qa_database: shadow_dm_qa
{execution}
""",
        encoding="utf-8",
    )


def _write_fresh_plan_bundle(plan_path, plan):
    root = plan_path.parent.parent
    warehouse_path = root / "warehouses" / plan["project"] / "warehouse.yaml"
    if not warehouse_path.is_file():
        _write_shadow_project(root, plan["project"], with_default_slice=True)

    manifest = {
        "format_version": 1,
        "run_id": "test-run",
        "project": plan["project"],
        "root": str(root),
        "artifacts": {
            "baseline_lineage": "baseline/lineage.json",
            "current_lineage": "current/lineage.json",
            "change_analysis": "analysis/change.json",
            "verification_plan": "verification/plan.json",
        },
        "verification_intent": {"semantic_modes": {}},
    }
    write_manifest(root / "manifest.json", manifest)
    inputs = {
        "baseline_lineage": {"tables": [], "edges": []},
        "current_lineage": {"tables": [], "edges": []},
        "change_analysis": {"changed_files": []},
    }
    for artifact_name, value in inputs.items():
        _write_json(root / manifest["artifacts"][artifact_name], value)

    prepared = deepcopy(plan)
    dependencies = prepared.pop("job_dependencies", None) or {}
    prepared.setdefault(
        "execution_graph",
        {
            "format_version": 1,
            "project": prepared["project"],
            "jobs": [job["job"] for job in prepared.get("jobs_to_run") or []],
            "dependencies": dependencies,
        },
    )
    prepared.setdefault("run_id", manifest["run_id"])
    prepared.setdefault("qa_database_pool", [prepared["qa_db"]])
    snapshot = deepcopy(prepared.get("analysis_snapshot") or {})
    snapshot["workspace_fingerprint"] = workspace_fingerprint(
        root, plan["project"]
    )
    snapshot["analysis_inputs"] = analysis_input_fingerprints(
        manifest=manifest,
        baseline_lineage=inputs["baseline_lineage"],
        current_lineage=inputs["current_lineage"],
        change_analysis=inputs["change_analysis"],
    )
    prepared["analysis_snapshot"] = snapshot
    return write_verification_plan(plan_path, prepared)


def _write_shadow_job(
    tmp_path,
    project: str,
    asset_dir: str,
    job_name: str,
    *,
    model_yaml: str,
    task_sql: str,
) -> None:
    project_dir = tmp_path / "warehouses" / project
    model_dir = project_dir / asset_dir / "models"
    task_dir = project_dir / asset_dir / "tasks"
    model_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / f"{job_name}.yaml").write_text(
        model_yaml,
        encoding="utf-8",
    )
    (task_dir / f"{job_name}.sql").write_text(
        task_sql,
        encoding="utf-8",
    )


def _write_shadow_job_dag(tmp_path, project: str, *edges) -> None:
    dag_path = (
        tmp_path
        / "warehouses"
        / project
        / "artifacts"
        / "lineage"
        / "job_dag.json"
    )
    dag_path.parent.mkdir(parents=True, exist_ok=True)
    JobDAG(
        [{"source": source, "target": target} for source, target in edges]
    ).save(dag_path)


def test_rewrite_sql_table_mapping_scenarios():
    _assert_rewrite_sql_maps_targets_to_qa_and_keeps_ods_sources_in_prod()
    _assert_rewrite_sql_maps_qa_ready_sources_to_qa()
    _assert_rewrite_sql_rewrites_qa_ready_sources_inside_ctes()
    _assert_rewrite_sql_handles_multiple_dml_statements_in_one_file()


def _assert_rewrite_sql_maps_targets_to_qa_and_keeps_ods_sources_in_prod():
    sql = """
    INSERT INTO shop_dm.dwd_order_detail
    SELECT o.order_id
    FROM shop_dm.ods_order o
    JOIN shop_dm.ods_order_item i ON o.order_id = i.order_id
    """

    refs = _table_refs(
        _rewrite_with_context(sql, "shop_dm", "shop_dm_qa", set())
    )

    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("ods_order", "shop_dm") in refs
    assert ("ods_order_item", "shop_dm") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def _assert_rewrite_sql_maps_qa_ready_sources_to_qa():
    sql = """
    INSERT INTO shop_dm.ads_store_performance
    SELECT ssd.store_id, s.store_name
    FROM shop_dm.dws_store_sales_daily ssd
    LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id
    """

    refs = _table_refs(
        _rewrite_with_context(
            sql,
            "shop_dm",
            "shop_dm_qa",
            {"dws_store_sales_daily"},
        )
    )

    assert ("ads_store_performance", "shop_dm_qa") in refs
    assert ("dws_store_sales_daily", "shop_dm_qa") in refs
    assert ("dwd_store", "shop_dm") in refs
    assert ("dws_store_sales_daily", "shop_dm") not in refs


def _assert_rewrite_sql_rewrites_qa_ready_sources_inside_ctes():
    sql = """
    INSERT INTO shop_dm.ads_sales_dashboard
    WITH daily_base AS (
        SELECT order_date, COUNT(*) AS cnt
        FROM shop_dm.dwd_order_detail
        GROUP BY order_date
    )
    SELECT order_date, cnt FROM daily_base
    """

    refs = _table_refs(
        _rewrite_with_context(
            sql,
            "shop_dm",
            "shop_dm_qa",
            {"dwd_order_detail"},
        )
    )

    assert ("ads_sales_dashboard", "shop_dm_qa") in refs
    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def _assert_rewrite_sql_handles_multiple_dml_statements_in_one_file():
    sql = """
    TRUNCATE TABLE shop_dm.dwd_order_detail;
    INSERT INTO shop_dm.dwd_order_detail
    SELECT * FROM shop_dm.ods_order;
    UPDATE shop_dm.dwd_order_detail
    SET cost_price = 0.00 WHERE cost_price IS NULL;
    """

    refs = _table_refs(
        _rewrite_with_context(sql, "shop_dm", "shop_dm_qa", set())
    )

    assert refs.count(("dwd_order_detail", "shop_dm_qa")) == 3
    assert ("ods_order", "shop_dm") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def test_rewrite_sql_maps_project_ddl_targets_to_qa():
    sql = """
    DROP TABLE IF EXISTS shop_dm.tmp_store_sales_daily;
    CREATE TABLE IF NOT EXISTS shop_dm.tmp_store_sales_daily
    LIKE shop_dm.dws_store_sales_daily;
    CREATE TEMPORARY TABLE shop_dm.tmp_session_sales
    LIKE shop_dm.dws_store_sales_daily;
    TRUNCATE TABLE shop_dm.tmp_store_sales_daily;
    ALTER TABLE shop_dm.tmp_store_sales_daily ADD COLUMN c1 INT;
    """

    rewritten = _rewrite_with_context(sql, "shop_dm", "shop_dm_qa", set())

    assert "DROP TABLE IF EXISTS shop_dm_qa.tmp_store_sales_daily" in rewritten
    assert (
        "CREATE TABLE IF NOT EXISTS shop_dm_qa.tmp_store_sales_daily"
        in rewritten
    )
    assert "CREATE TEMPORARY TABLE shop_dm_qa.tmp_session_sales" in rewritten
    assert "TRUNCATE TABLE shop_dm_qa.tmp_store_sales_daily" in rewritten
    assert (
        "ALTER TABLE shop_dm_qa.tmp_store_sales_daily ADD COLUMN c1 INT"
        in rewritten
    )
    assert "shop_dm.tmp_store_sales_daily" not in rewritten
    assert "shop_dm.tmp_session_sales" not in rewritten


def test_rewrite_sql_text_empty():
    assert _rewrite_with_context("", "shop_dm", "shop_dm_qa", set()) == ""


def test_execute_shadow_plan_runs_case_only_rename_steps_in_order(
    tmp_path, monkeypatch
):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [
            {
                "change_type": "ALTER",
                "table_name": "shop_dm.dws_store_sales_daily",
                "sql": (
                    "ALTER TABLE shop_dm.dws_store_sales_daily "
                    "RENAME COLUMN store_id __tmp_STORE_ID; "
                    "ALTER TABLE shop_dm.dws_store_sales_daily "
                    "RENAME COLUMN __tmp_STORE_ID STORE_ID;"
                ),
                "renames": [{"old": "store_id", "new": "STORE_ID"}],
                "case_only_renames": [
                    {
                        "old": "store_id",
                        "new": "STORE_ID",
                        "temporary": "__tmp_STORE_ID",
                        "steps": [
                            {"old": "store_id", "new": "__tmp_STORE_ID"},
                            {"old": "__tmp_STORE_ID", "new": "STORE_ID"},
                        ],
                    }
                ],
            }
        ],
        "partition_info": {},
        "jobs_to_run": [],
        "verification": {"checks": []},
    }
    calls = []

    def fake_run_sql(sql, db="", qa=False):
        calls.append((sql, db, qa))
        return ""

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql", fake_run_sql
    )

    result = execute_shadow_plan(plan, root=tmp_path)

    alter_calls = [sql for sql, _, _ in calls if sql.startswith("ALTER TABLE")]
    show_calls = [
        sql for sql, _, _ in calls if sql.startswith("SHOW ALTER TABLE COLUMN")
    ]
    assert alter_calls == [
        (
            "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
            "RENAME COLUMN store_id __tmp_STORE_ID;"
        ),
        (
            "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
            "RENAME COLUMN __tmp_STORE_ID STORE_ID;"
        ),
    ]
    assert len(show_calls) == 4
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    ddl_result = phase_by_name["apply_ddl_changes"]["ddl_changes"][0]
    assert ddl_result["status"] == "success"
    assert ddl_result["sql"] == (
        "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
        "RENAME COLUMN store_id __tmp_STORE_ID; "
        "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
        "RENAME COLUMN __tmp_STORE_ID STORE_ID;"
    )
    assert ddl_result["renames"] == [{"old": "store_id", "new": "STORE_ID"}]
    assert ddl_result["case_only_renames"] == [
        {
            "old": "store_id",
            "new": "STORE_ID",
            "temporary": "__tmp_STORE_ID",
            "steps": [
                {"old": "store_id", "new": "__tmp_STORE_ID"},
                {"old": "__tmp_STORE_ID", "new": "STORE_ID"},
            ],
        }
    ]
    assert ddl_result["statements"] == [
        {
            "sql": (
                "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
                "RENAME COLUMN store_id __tmp_STORE_ID;"
            ),
            "status": "success",
            "error": None,
        },
        {
            "sql": (
                "ALTER TABLE shop_dm_qa.dws_store_sales_daily "
                "RENAME COLUMN __tmp_STORE_ID STORE_ID;"
            ),
            "status": "success",
            "error": None,
        },
    ]


def test_wait_for_table_alter_jobs_polls_until_finished(monkeypatch):
    outputs = [
        (
            "JobId\tTableName\tCreateTime\tFinishedTime\tState\tMsg\n"
            "1\tdwd_order_detail\t2026-06-30 12:00:00\tN/A\tRUNNING\t\n"
        ),
        (
            "JobId\tTableName\tCreateTime\tFinishedTime\tState\tMsg\n"
            "1\tdwd_order_detail\t2026-06-30 12:00:00\t"
            "2026-06-30 12:00:03\tFINISHED\t\n"
        ),
    ]
    calls = []

    def fake_run_sql(sql, db="", qa=False):
        calls.append((sql, db, qa))
        return outputs.pop(0)

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql", fake_run_sql
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.time.sleep", lambda _: None
    )

    _wait_for_table_alter_jobs(
        "shop_dm_qa",
        "dwd_order_detail",
        qa=True,
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert len(calls) == 2
    assert calls[0][0] == (
        "SHOW ALTER TABLE COLUMN FROM `shop_dm_qa` "
        'WHERE TableName = "dwd_order_detail" '
        "ORDER BY CreateTime DESC LIMIT 10"
    )


def test_run_shadow_plan_persists_failed_job_result(tmp_path, monkeypatch):
    job_file = (
        tmp_path
        / "warehouses"
        / "shop"
        / "mid"
        / "tasks"
        / "dwd_order_detail.sql"
    )
    job_file.parent.mkdir(parents=True)
    job_file.write_text(
        "INSERT INTO shop_dm.dwd_order_detail SELECT * FROM shop_dm.ods_order",
        encoding="utf-8",
    )
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_fresh_plan_bundle(
        plan_path,
        {
            "project": "shop",
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {},
            "ddl_changes": [],
            "partition_info": {},
            "jobs_to_run": [
                {
                    "job": "dwd_order_detail",
                    "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
                    "layer": "DWD",
                    "execution_values": ["2025-01-15"],
                }
            ],
            "verification": {
                "checks": [
                    {
                        "table": "ads_sales_dashboard",
                        "scope": {"mode": "full_table"},
                        "methods": [{"method": "count"}],
                    }
                ]
            },
            "analysis_snapshot": _analysis_snapshot(),
        },
    )

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: (_ for _ in ()).throw(
            ShadowRunSqlError("insert failed")
        ),
    )

    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
    )

    assert result["status"] == "failed"
    assert result["mode"] == "execute"
    assert result["summary"]["failed_job_count"] == 1
    _assert_timing(result)
    phase_names = [phase["name"] for phase in result["phases"]]
    assert "compare" not in phase_names
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    for phase in phase_by_name.values():
        _assert_timing(phase)
    assert phase_by_name["run_jobs"]["status"] == "failed"
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    _assert_timing(job_result)
    assert _without_timing(job_result) == {
        "job": "dwd_order_detail",
        "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
        "layer": "DWD",
        "target": "dwd_order_detail",
        "status": "failed",
        "error": "insert failed",
        "execution_values": ["2025-01-15"],
        "invocation_count": 1,
    }
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_run_shadow_plan_timing_detail_records_invocation_timings(
    tmp_path, monkeypatch
):
    job_file = (
        tmp_path / "warehouses" / "shop" / "mid" / "tasks" / "dws_order.sql"
    )
    job_file.parent.mkdir(parents=True)
    job_file.write_text(
        "INSERT INTO shop_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_fresh_plan_bundle(
        plan_path,
        {
            "project": "shop",
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {},
            "ddl_changes": [],
            "partition_info": {},
            "jobs_to_run": [
                {
                    "job": "dws_order",
                    "file": "warehouses/shop/mid/tasks/dws_order.sql",
                    "layer": "DWS",
                    "execution_values": ["2024-06-01", "2024-06-02"],
                }
            ],
            "verification": {"checks": []},
            "analysis_snapshot": _analysis_snapshot(),
        },
    )

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: "",
    )

    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
        timing_detail=True,
    )

    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    invocations = job_result["invocations"]
    assert [item["execution_value"] for item in invocations] == [
        "2024-06-01",
        "2024-06-02",
    ]
    assert [item["status"] for item in invocations] == [
        "success",
        "success",
    ]
    for invocation in invocations:
        _assert_timing(invocation)
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_execute_shadow_plan_fails_when_job_file_is_missing(
    tmp_path, monkeypatch
):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "partition_info": {},
        "jobs_to_run": [
            {
                "job": "dwd_order_detail",
                "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
                "layer": "DWD",
            }
        ],
        "verification": {"checks": []},
    }

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )

    result = execute_shadow_plan(plan, root=tmp_path)

    assert result["status"] == "failed"
    assert result["summary"]["failed_job_count"] == 1
    phase_names = [phase["name"] for phase in result["phases"]]
    assert "compare" not in phase_names
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["run_jobs"]["status"] == "failed"
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    assert job_result["status"] == "failed"
    assert "文件不存在" in job_result["error"]


def test_shadow_run_cli_passes_timing_detail_flag(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    persisted_plan = _write_shadow_cli_plan(plan_path)
    calls = []
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.require_fresh_plan",
        lambda *args, **kwargs: persisted_plan,
    )

    def fake_run_shadow_plan(
        plan,
        output,
        provenance,
        dry_run=False,
        timing_detail=False,
        parallel=1,
        batch_size=1,
    ):
        calls.append(
            (
                plan,
                output,
                provenance,
                dry_run,
                timing_detail,
                parallel,
                batch_size,
            )
        )
        return {"status": "completed"}

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_shadow_plan",
        fake_run_shadow_plan,
    )

    assert (
        main(
            [
                "--plan",
                str(plan_path),
                "--output",
                str(output_path),
                "--timing-detail",
            ]
        )
        == 0
    )

    assert calls == [
        (
            plan_path,
            output_path,
            {
                "workspace_fingerprint": persisted_plan["analysis_snapshot"][
                    "workspace_fingerprint"
                ],
                "plan_fingerprint": persisted_plan["plan_fingerprint"],
            },
            False,
            True,
            1,
            1,
        )
    ]


def test_run_shadow_plan_rejects_provenance_not_from_plan(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_shadow_cli_plan(plan_path)
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.execute_shadow_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("mismatched provenance must block execution")
        ),
    )

    with pytest.raises(ArtifactFormatError, match="does not match"):
        run_shadow_plan(
            plan_path,
            output_path,
            provenance={
                "workspace_fingerprint": "sha256:other-workspace",
                "plan_fingerprint": "sha256:other-plan",
            },
        )


def test_shadow_run_rejects_claim_outside_configured_pool(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    persisted = _write_shadow_cli_plan(plan_path)
    owner = QaSlotOwnership(
        2,
        "shop",
        "test-run",
        "execution-1",
        "shop_dm",
        persisted["plan_fingerprint"],
        persisted["analysis_snapshot"]["workspace_fingerprint"],
        "2026-07-14 12:00:00",
        1784001600,
    )
    monkeypatch.setattr(
        shadow_run_module, "claim_qa_slot", lambda **kwargs: owner
    )
    monkeypatch.setattr(
        shadow_run_module,
        "execute_shadow_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pool-external database must not execute")
        ),
    )

    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
    )

    assert result["status"] == "failed"
    assert "configured QA database pool" in result["error"]


def test_execute_shadow_plan_validates_ownership_before_database_writes(
    tmp_path, monkeypatch
):
    plan = {
        "project": "shop",
        "run_id": "test-run",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {
            "dwd_order": "CREATE TABLE shop_dm.dwd_order (id BIGINT)"
        },
        "ddl_changes": [],
        "jobs_to_run": [],
        "verification": {"checks": []},
    }
    monkeypatch.setattr(
        shadow_run_module,
        "require_slot_ownership",
        lambda **kwargs: (_ for _ in ()).throw(
            ArtifactFormatError("ownership mismatch")
        ),
    )
    monkeypatch.setattr(
        shadow_run_module,
        "run_sql",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ownership failure must precede database writes")
        ),
    )

    result = _execute_shadow_plan(
        plan,
        root=tmp_path,
        claimed_ownership=_claimed_ownership(plan),
    )

    assert result["status"] == "failed"
    assert result["phases"][-1]["name"] == "validate_qa_slot_ownership"


def test_shadow_run_standalone_cli_rejects_stale_plan(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    _write_shadow_cli_plan(plan_path)
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.require_fresh_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ArtifactFormatError(
                "stale_plan: workspace changed after analyze; run analyze again"
            )
        ),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_shadow_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("stale plan must block shadow execution")
        ),
    )

    with pytest.raises(SystemExit, match="stale_plan.*analyze"):
        main(["--plan", str(plan_path)])


def test_run_shadow_plan_dry_run_persists_phase_summary(
    tmp_path, monkeypatch, capsys
):
    job_file = (
        tmp_path
        / "warehouses"
        / "shop"
        / "mid"
        / "tasks"
        / "M_SHOP_05_INV_DF.sql"
    )
    job_file.parent.mkdir(parents=True)
    job_file.write_text(
        (
            "SET @etl_date = COALESCE(@etl_date, CURDATE());\n"
            "INSERT INTO shop_dm.M_SHOP_05_INV_DF "
            "SELECT * FROM shop_dm.ods_inventory"
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "qa_database_pool": ["shop_dm_qa", "shop_dm_qa_02"],
        "baseline_ddl": {
            "dwd_inventory": "CREATE TABLE shop_dm.dwd_inventory (id INT)"
        },
        "ddl_changes": [
            {
                "change_type": "RENAME",
                "sql": (
                    "ALTER TABLE shop_dm.dwd_inventory "
                    "RENAME M_SHOP_05_INV_DF;"
                ),
                "old_name": "shop_dm.dwd_inventory",
                "new_name": "shop_dm.M_SHOP_05_INV_DF",
            }
        ],
        "partition_info": {"etl_date": "2025-01-15"},
        "jobs_to_run": [
            {
                "job": "M_SHOP_05_INV_DF",
                "file": "warehouses/shop/mid/tasks/M_SHOP_05_INV_DF.sql",
                "layer": "DWD",
                "target": "M_SHOP_05_INV_DF",
                "needs_etl_date": True,
                "execution_values": ["2025-01-15"],
            }
        ],
        "verification": {
            "checks": [
                {
                    "table": "dws_inventory_daily",
                    "scope": {"mode": "full_table"},
                    "methods": [
                        {"method": "count"},
                        {"method": "row_compare"},
                    ],
                }
            ]
        },
        "analysis_snapshot": _analysis_snapshot(),
    }
    _write_fresh_plan_bundle(plan_path, plan)

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )

    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
        dry_run=True,
    )
    assert result["format_version"] == 1
    assert (
        result["workspace_fingerprint"]
        == _provenance(plan_path)["workspace_fingerprint"]
    )
    assert (
        result["plan_fingerprint"]
        == _provenance(plan_path)["plan_fingerprint"]
    )

    assert result["status"] == "dry_run"
    assert result["mode"] == "dry_run"
    assert result["summary"] == {
        "baseline_table_count": 1,
        "ddl_change_count": 1,
        "job_count": 1,
        "failed_job_count": 0,
        "failed_ddl_change_count": 0,
    }
    phase_names = [phase["name"] for phase in result["phases"]]
    assert phase_names == [
        "compile_shadow_manifest",
        "select_qa_slot",
        "create_baseline_tables",
        "prefill_baseline_data",
        "apply_ddl_changes",
        "run_jobs",
    ]
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["select_qa_slot"]["qa_database_pool"] == [
        "shop_dm_qa",
        "shop_dm_qa_02",
    ]
    assert phase_by_name["create_baseline_tables"]["tables"] == [
        {"table": "dwd_inventory", "status": "dry_run"}
    ]
    assert phase_by_name["apply_ddl_changes"]["ddl_changes"] == [
        {
            "change_type": "RENAME",
            "sql": (
                "ALTER TABLE shop_dm_qa.dwd_inventory RENAME M_SHOP_05_INV_DF;"
            ),
            "original_sql": (
                "ALTER TABLE shop_dm.dwd_inventory RENAME M_SHOP_05_INV_DF;"
            ),
            "old_name": "shop_dm_qa.dwd_inventory",
            "new_name": "shop_dm_qa.M_SHOP_05_INV_DF",
            "status": "dry_run",
            "error": None,
        }
    ]
    assert phase_by_name["run_jobs"]["jobs"][0]["job"] == "M_SHOP_05_INV_DF"
    assert phase_by_name["run_jobs"]["jobs"][0]["status"] == "dry_run"
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    output = capsys.readouterr().out
    assert "分区:" not in output
    assert (
        "[RENAME] shop_dm_qa.dwd_inventory -> shop_dm_qa.M_SHOP_05_INV_DF"
    ) in output
    assert "[RENAME] ?" not in output


def test_execute_shadow_plan_runs_same_job_slice_batches_in_parallel(
    tmp_path, monkeypatch
):
    _write_shadow_project(tmp_path, "shop", with_default_slice=True)
    task_path = tmp_path / "shop" / "mid" / "tasks" / "dws_order.sql"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        "INSERT INTO shop_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dws_order",
                "file": "shop/mid/tasks/dws_order.sql",
                "layer": "DWS",
                "target": "dws_order",
                "execution_values": [
                    "2024-06-01",
                    "2024-06-02",
                    "2024-06-03",
                ],
            }
        ],
        "verification": {"checks": []},
    }
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_run_sql_text(sql_text, db="", qa=False):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return ""

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        fake_run_sql_text,
    )

    result = execute_shadow_plan(plan, root=tmp_path, parallel=2)

    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    assert result["status"] == "completed"
    assert max_active == 2
    assert job_result["invocation_count"] == 3
    assert job_result["batch_count"] == 3
    assert job_result["parallelism"] == 2
    assert job_result["batch_size"] == 1


def test_execute_shadow_plan_serializes_slices_with_created_stage_table(
    tmp_path, monkeypatch
):
    _write_shadow_project(tmp_path, "shop", with_default_slice=True)
    task_path = tmp_path / "shop" / "mid" / "tasks" / "dws_order.sql"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        """\
DROP TABLE IF EXISTS shop_dm.stage_order;
CREATE TABLE shop_dm.stage_order AS SELECT @etl_date AS stat_date;
INSERT INTO shop_dm.dws_order SELECT * FROM shop_dm.stage_order;
""",
        encoding="utf-8",
    )
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dws_order",
                "file": "shop/mid/tasks/dws_order.sql",
                "layer": "DWS",
                "target": "dws_order",
                "execution_values": [
                    "2024-06-01",
                    "2024-06-02",
                    "2024-06-03",
                ],
            }
        ],
        "verification": {"checks": []},
    }
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_run_sql_text(sql_text, db="", qa=False):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return ""

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        fake_run_sql_text,
    )

    result = execute_shadow_plan(plan, root=tmp_path, parallel=2)

    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    assert result["status"] == "completed"
    assert max_active == 1
    assert job_result["invocation_count"] == 3
    assert "parallelism" not in job_result
    assert (
        result["shadow_manifest"]["jobs"]["dws_order"][
            "requires_serial_slices"
        ]
        is True
    )


def test_execute_shadow_plan_skips_downstream_after_upstream_failure(
    tmp_path, monkeypatch
):
    project = "shadow_dag_failure"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "dws_order",
        model_yaml="""version: 2
name: dws_order
layer: DWS
execution:
  materialized: full
""",
        task_sql="INSERT INTO shadow_dm.dws_order SELECT 1;",
    )
    _write_shadow_job(
        tmp_path,
        project,
        "ads",
        "ads_order",
        model_yaml="""version: 2
name: ads_order
layer: ADS
execution:
  materialized: full
""",
        task_sql="INSERT INTO shadow_dm.ads_order SELECT * FROM shadow_dm.dws_order;",
    )
    _write_shadow_job_dag(tmp_path, project, ("dws_order", "ads_order"))
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "ads_order",
                "file": (
                    "warehouses/shadow_dag_failure/ads/tasks/ads_order.sql"
                ),
                "layer": "ADS",
                "target": "ads_order",
            },
            {
                "job": "dws_order",
                "file": (
                    "warehouses/shadow_dag_failure/mid/tasks/dws_order.sql"
                ),
                "layer": "DWS",
                "target": "dws_order",
            },
        ],
        "execution_graph": {
            "format_version": 1,
            "project": project,
            "jobs": ["dws_order", "ads_order"],
            "dependencies": {"ads_order": ["dws_order"]},
        },
        "verification": {"checks": []},
    }
    executed_jobs = []

    def fake_run_sql_text(sql_text, db="", qa=False):
        if "ads_order" in sql_text:
            executed_jobs.append("ads_order")
            return ""
        executed_jobs.append("dws_order")
        raise ShadowRunSqlError("boom")

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        fake_run_sql_text,
    )

    result = execute_shadow_plan(plan, root=tmp_path, parallel=2)

    assert result["status"] == "failed"
    assert executed_jobs == ["dws_order"]
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    jobs = {job["job"]: job for job in phase_by_name["run_jobs"]["jobs"]}
    assert jobs["dws_order"]["status"] == "failed"
    assert jobs["ads_order"]["status"] == "skipped"
    assert "actual_execution_values" not in jobs["ads_order"]


def test_execute_shadow_plan_uses_job_execution_values_and_records_counts(
    tmp_path, monkeypatch
):
    project = "shadow_driver_values"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "dws_store_sales_daily",
        model_yaml="""version: 2
name: dws_store_sales_daily
layer: DWS
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: D
""",
        task_sql=(
            "INSERT INTO shadow_dm.dws_store_sales_daily SELECT @etl_date;"
        ),
    )
    _write_shadow_job(
        tmp_path,
        project,
        "ads",
        "ads_store_performance",
        model_yaml="""version: 2
name: ads_store_performance
layer: ADS
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_month_date
    period: M
""",
        task_sql=(
            "INSERT INTO shadow_dm.ads_store_performance SELECT @etl_date;"
        ),
    )
    _write_shadow_job(
        tmp_path,
        project,
        "ads",
        "ads_sales_dashboard",
        model_yaml="""version: 2
name: ads_sales_dashboard
layer: ADS
execution:
  materialized: full
""",
        task_sql="INSERT INTO shadow_dm.ads_sales_dashboard SELECT 1;",
    )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dws_store_sales_daily",
                "file": (
                    "warehouses/shadow_driver_values/mid/tasks/"
                    "dws_store_sales_daily.sql"
                ),
                "layer": "DWS",
                "execution_values": ["2024-06-01", "2024-06-02"],
            },
            {
                "job": "ads_store_performance",
                "file": (
                    "warehouses/shadow_driver_values/ads/tasks/"
                    "ads_store_performance.sql"
                ),
                "layer": "ADS",
                "execution_values": ["2024-06-01"],
            },
            {
                "job": "ads_sales_dashboard",
                "file": (
                    "warehouses/shadow_driver_values/ads/tasks/"
                    "ads_sales_dashboard.sql"
                ),
                "layer": "ADS",
            },
        ],
        "verification": {"checks": []},
    }
    executed_texts = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql_text, db="", qa=False: (
            executed_texts.append(sql_text) or ""
        ),
    )

    result = execute_shadow_plan(plan, root=tmp_path)
    dry_run_result = execute_shadow_plan(plan, root=tmp_path, dry_run=True)

    assert result["status"] == "completed"
    assert len(executed_texts) == 4
    assert executed_texts[0].startswith("SET @etl_date = '2024-06-01';\n")
    assert (
        "INSERT INTO shadow_dm_qa.dws_store_sales_daily" in executed_texts[0]
    )
    assert executed_texts[1].startswith("SET @etl_date = '2024-06-02';\n")
    assert (
        "INSERT INTO shadow_dm_qa.dws_store_sales_daily" in executed_texts[1]
    )
    assert executed_texts[2].startswith("SET @etl_date = '2024-06-01';\n")
    assert (
        "INSERT INTO shadow_dm_qa.ads_store_performance" in executed_texts[2]
    )
    assert "2024-06-02" not in executed_texts[2]
    assert executed_texts[3].startswith("SET @full_refresh = 1;\n")
    assert "INSERT INTO shadow_dm_qa.ads_sales_dashboard" in executed_texts[3]

    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    jobs = {job["job"]: job for job in phase_by_name["run_jobs"]["jobs"]}
    assert "actual_execution_values" not in jobs["dws_store_sales_daily"]
    assert jobs["dws_store_sales_daily"]["invocation_count"] == 2
    assert "actual_execution_values" not in jobs["ads_store_performance"]
    assert jobs["ads_store_performance"]["invocation_count"] == 1
    assert "actual_execution_values" not in jobs["ads_sales_dashboard"]
    assert jobs["ads_sales_dashboard"]["invocation_count"] == 1

    assert dry_run_result["status"] == "dry_run"
    dry_run_phase_by_name = {
        phase["name"]: phase for phase in dry_run_result["phases"]
    }
    dry_run_jobs = {
        job["job"]: job for job in dry_run_phase_by_name["run_jobs"]["jobs"]
    }
    assert (
        "actual_execution_values" not in dry_run_jobs["dws_store_sales_daily"]
    )
    assert dry_run_jobs["dws_store_sales_daily"]["invocation_count"] == 2
    assert (
        "actual_execution_values" not in dry_run_jobs["ads_store_performance"]
    )
    assert dry_run_jobs["ads_store_performance"]["invocation_count"] == 1
    assert "actual_execution_values" not in dry_run_jobs["ads_sales_dashboard"]
    assert dry_run_jobs["ads_sales_dashboard"]["invocation_count"] == 1


def test_execute_shadow_plan_fails_sliced_job_without_execution_values(
    tmp_path, monkeypatch
):
    project = "shadow_missing_values"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "dws_order",
        model_yaml="""version: 2
name: dws_order
layer: DWS
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: D
""",
        task_sql="INSERT INTO shadow_dm.dws_order SELECT @etl_date;",
    )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dws_order",
                "file": (
                    "warehouses/shadow_missing_values/mid/tasks/dws_order.sql"
                ),
                "layer": "DWS",
            },
        ],
        "verification": {"checks": []},
    }
    executed_texts = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql_text, db="", qa=False: (
            executed_texts.append(sql_text) or ""
        ),
    )

    result = execute_shadow_plan(plan, root=tmp_path)
    dry_run_result = execute_shadow_plan(plan, root=tmp_path, dry_run=True)

    assert result["status"] == "failed"
    assert executed_texts == []
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    assert job_result["status"] == "failed"
    assert "requires execution_values" in job_result["error"]
    assert "actual_execution_values" not in job_result
    assert job_result["invocation_count"] == 0

    assert dry_run_result["status"] == "failed"
    assert dry_run_result["mode"] == "dry_run"
    dry_run_phase_by_name = {
        phase["name"]: phase for phase in dry_run_result["phases"]
    }
    dry_run_job_result = dry_run_phase_by_name["run_jobs"]["jobs"][0]
    assert dry_run_job_result["status"] == "failed"
    assert "requires execution_values" in dry_run_job_result["error"]
    assert "actual_execution_values" not in dry_run_job_result
    assert dry_run_job_result["invocation_count"] == 0


def test_execute_shadow_plan_prefills_after_baseline_before_rename(
    tmp_path, monkeypatch
):
    project = "shadow_prefill"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "daily_report",
        model_yaml="""version: 2
name: daily_report
layer: DWS
execution:
  materialized: full
""",
        task_sql=(
            "INSERT INTO shadow_dm.daily_report "
            "SELECT * FROM shadow_dm.renamed_sales;"
        ),
    )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {
            "sales": "CREATE TABLE shadow_dm.sales (id BIGINT) ENGINE=OLAP;",
            "daily_report": (
                "CREATE TABLE shadow_dm.daily_report (id BIGINT) ENGINE=OLAP;"
            ),
        },
        "ddl_changes": [
            {
                "change_type": "RENAME",
                "old_name": "shadow_dm.sales",
                "new_name": "shadow_dm.renamed_sales",
                "sql": "ALTER TABLE shadow_dm.sales RENAME renamed_sales;",
            }
        ],
        "jobs_to_run": [
            {
                "job": "daily_report",
                "target": "daily_report",
                "file": (f"warehouses/{project}/mid/tasks/daily_report.sql"),
                "layer": "DWS",
            }
        ],
        "verification": {"checks": []},
    }
    calls = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: calls.append(("sql", sql)) or "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: calls.append(("text", sql)),
    )

    result = execute_shadow_plan(plan, root=tmp_path)

    phase_names = [phase["name"] for phase in result["phases"]]
    assert phase_names == [
        "compile_shadow_manifest",
        "create_baseline_tables",
        "prefill_baseline_data",
        "apply_ddl_changes",
        "run_jobs",
    ]
    sql_texts = [sql for _kind, sql in calls]
    prefill_index = sql_texts.index(
        "INSERT INTO shadow_dm_qa.sales SELECT * FROM shadow_dm.sales;"
    )
    rename_index = sql_texts.index(
        "ALTER TABLE shadow_dm_qa.sales RENAME renamed_sales;"
    )
    assert prefill_index < rename_index
    assert result["shadow_manifest"]["prefill_actions"][0]["mode"] == "full"


def test_execute_shadow_plan_manifest_blocker_runs_no_database_sql(
    tmp_path, monkeypatch
):
    project = "shadow_blocked"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "daily_report",
        model_yaml="""version: 2
name: daily_report
layer: DWS
execution:
  materialized: full
""",
        task_sql=(
            "INSERT INTO shadow_dm.daily_report "
            "SELECT * FROM shadow_dm.brand_new_sales;"
        ),
    )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {
            "daily_report": (
                "CREATE TABLE shadow_dm.daily_report (id BIGINT) ENGINE=OLAP;"
            )
        },
        "ddl_changes": [
            {
                "change_type": "CREATE",
                "table_name": "shadow_dm.brand_new_sales",
                "sql": (
                    "CREATE TABLE shadow_dm.brand_new_sales "
                    "(id BIGINT) ENGINE=OLAP;"
                ),
            }
        ],
        "jobs_to_run": [
            {
                "job": "daily_report",
                "target": "daily_report",
                "file": (f"warehouses/{project}/mid/tasks/daily_report.sql"),
                "layer": "DWS",
            }
        ],
        "verification": {"checks": []},
    }
    calls = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: calls.append(sql),
    )

    result = execute_shadow_plan(plan, root=tmp_path)

    assert result["status"] == "failed"
    assert calls == []
    assert [phase["name"] for phase in result["phases"]] == [
        "compile_shadow_manifest"
    ]
    assert result["phases"][0]["status"] == "failed"
    assert "brand_new_sales" in result["phases"][0]["blockers"][0]


def test_trusted_schedule_orders_jobs_without_manifest_dependency_inference(
    tmp_path, monkeypatch
):
    project = "shadow_manifest_order"
    _write_shadow_project(tmp_path, project)
    for name, task_sql in {
        "sales": "INSERT INTO shadow_dm.sales SELECT 1;",
        "report": (
            "INSERT INTO shadow_dm.report SELECT * FROM shadow_dm.sales;"
        ),
    }.items():
        _write_shadow_job(
            tmp_path,
            project,
            "mid",
            name,
            model_yaml=f"""version: 2
name: {name}
layer: DWS
execution:
  materialized: full
""",
            task_sql=task_sql,
        )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {
            name: f"CREATE TABLE shadow_dm.{name} (id BIGINT) ENGINE=OLAP;"
            for name in ("sales", "report")
        },
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": name,
                "target": name,
                "file": f"warehouses/{project}/mid/tasks/{name}.sql",
                "layer": "DWS",
            }
            for name in ("report", "sales")
        ],
        "execution_graph": {
            "format_version": 1,
            "project": project,
            "jobs": ["sales", "report"],
            "dependencies": {"report": ["sales"]},
        },
        "verification": {"checks": []},
    }
    executed = []

    def fake_run_sql_text(sql, db="", qa=False):
        executed.append("report" if "shadow_dm_qa.report" in sql else "sales")
        return ""

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        fake_run_sql_text,
    )

    result = execute_shadow_plan(plan, root=tmp_path, parallel=2)
    run_phase = {phase["name"]: phase for phase in result["phases"]}[
        "run_jobs"
    ]

    assert result["status"] == "completed"
    assert executed == ["sales", "report"]
    assert run_phase["scheduler"] == "trusted_schedule"


def test_self_reading_job_serializes_parallel_slice_invocations(
    tmp_path, monkeypatch
):
    project = "shadow_self_serial"
    _write_shadow_project(tmp_path, project)
    _write_shadow_job(
        tmp_path,
        project,
        "mid",
        "sales",
        model_yaml="""version: 2
name: sales
layer: DWS
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: D
""",
        task_sql=(
            "INSERT INTO shadow_dm.sales "
            "SELECT * FROM shadow_dm.sales "
            "WHERE stat_date = DATE_SUB(@etl_date, INTERVAL 1 DAY);"
        ),
    )
    plan = {
        "project": project,
        "project_db": "shadow_dm",
        "qa_db": "shadow_dm_qa",
        "baseline_ddl": {
            "sales": """CREATE TABLE shadow_dm.sales (
  stat_date DATE
) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p20250114 VALUES LESS THAN ("2025-01-15"),
  PARTITION p20250115 VALUES LESS THAN ("2025-01-16"),
  PARTITION p_after VALUES LESS THAN (MAXVALUE)
);"""
        },
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "sales",
                "target": "sales",
                "file": f"warehouses/{project}/mid/tasks/sales.sql",
                "layer": "DWS",
                "execution_values": ["2025-01-15", "2025-01-16"],
            }
        ],
        "verification": {"checks": []},
    }
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_run_sql_text(sql, db="", qa=False):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return ""

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        fake_run_sql_text,
    )

    result = execute_shadow_plan(plan, root=tmp_path, parallel=2)
    job_result = {phase["name"]: phase for phase in result["phases"]}[
        "run_jobs"
    ]["jobs"][0]

    assert result["status"] == "completed"
    assert max_active == 1
    assert "parallelism" not in job_result
    assert result["shadow_manifest"]["jobs"]["sales"]["self_read"] is True
