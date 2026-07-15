from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.refactor.shadow_manifest import (
    PrefillMode,
    compile_shadow_manifest,
    manifest_summary,
)
from dw_refactor_agent.refactor.shadow_rewrite import rewrite_shadow_sql


class FakePlanner:
    def __init__(self, specs):
        self.specs = specs
        self.task_spec_calls = []

    def task_spec(self, job_name, sql_path, *, model_name=None):
        self.task_spec_calls.append((job_name, model_name))
        raw = self.specs.get(model_name or job_name, {})
        return SimpleNamespace(
            materialized=raw.get("materialized", "full"),
            slice_param=raw.get("slice_param"),
            slice_column=raw.get("slice_column"),
            slice_period=raw.get("slice_period", "D"),
        )

    def plan_shadow_job(self, job, *, project_root=None, full_refresh=False):
        root = Path(project_root)
        spec = self.task_spec(
            job["job"],
            root / job["file"],
            model_name=job.get("target"),
        )
        values = job.get("execution_values") or [None]
        return [
            TaskInvocation(
                job_name=job["job"],
                sql_path=root / job["file"],
                params={spec.slice_param: value}
                if spec.slice_param and value is not None
                else {},
                full_refresh=spec.materialized == "full",
                strategy="replace_all"
                if spec.materialized == "full"
                else "replay_slices",
            )
            for value in values
        ]


def _write_task(tmp_path, name: str, sql: str) -> str:
    path = tmp_path / "tasks" / f"{name}.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")
    return path.relative_to(tmp_path).as_posix()


def _ddl(table: str, body: str = "id BIGINT") -> str:
    return f"CREATE TABLE dm.{table} ({body}) ENGINE=OLAP;"


def _plan(tmp_path, *, baseline_ddl, ddl_changes, jobs):
    return {
        "project": "demo",
        "project_db": "dm",
        "qa_db": "dm_qa",
        "baseline_ddl": baseline_ddl,
        "ddl_changes": ddl_changes,
        "jobs_to_run": jobs,
    }


def test_shadow_manifest_uses_target_model_without_renaming_job(tmp_path):
    task = _write_task(
        tmp_path,
        "prepare_sales",
        "INSERT INTO dm.dwd_order SELECT 1;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"dwd_order": _ddl("dwd_order")},
        ddl_changes=[],
        jobs=[
            {
                "job": "prepare_sales",
                "target": "dwd_order",
                "file": task,
            }
        ],
    )
    planner = FakePlanner({"dwd_order": {"materialized": "full"}})

    manifest = compile_shadow_manifest(plan, tmp_path, planner)

    assert planner.task_spec_calls == [
        ("prepare_sales", "dwd_order"),
        ("prepare_sales", "dwd_order"),
    ]
    assert "prepare_sales" in manifest["jobs"]


def test_reserved_execution_marker_reference_is_blocked(tmp_path):
    task = _write_task(
        tmp_path,
        "daily_report",
        "INSERT INTO dm.daily_report "
        "SELECT * FROM dm.dw_refactor_execution_marker;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"daily_report": _ddl("daily_report")},
        ddl_changes=[],
        jobs=[
            {
                "job": "daily_report",
                "target": "daily_report",
                "file": task,
            }
        ],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))

    assert any(
        "reserved" in blocker and "dw_refactor_execution_marker" in blocker
        for blocker in manifest["blockers"]
    )


def test_schema_only_read_of_renamed_table_uses_qa_without_prefill(tmp_path):
    task = _write_task(
        tmp_path,
        "tmp_x",
        "CREATE TABLE dm.tmp_x LIKE dm.I_SHOP_STORE_SALES_DS;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={
            "dws_store_sales_daily": _ddl("dws_store_sales_daily"),
            "tmp_x": _ddl("tmp_x"),
        },
        ddl_changes=[
            {
                "change_type": "RENAME",
                "old_name": "dm.dws_store_sales_daily",
                "new_name": "dm.I_SHOP_STORE_SALES_DS",
                "sql": (
                    "ALTER TABLE dm.dws_store_sales_daily "
                    "RENAME I_SHOP_STORE_SALES_DS;"
                ),
            }
        ],
        jobs=[{"job": "tmp_x", "target": "tmp_x", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    context = manifest["jobs"]["tmp_x"]["context"]

    assert (
        manifest["relations"]["i_shop_store_sales_ds"]["baseline_table"]
        == "dws_store_sales_daily"
    )
    assert manifest["phase2_qa_only_tables"] == {"i_shop_store_sales_ds"}
    assert context.schema_routes["i_shop_store_sales_ds"].database == "dm_qa"
    assert manifest["prefill_actions"] == []
    assert manifest["blockers"] == []

    summary = manifest_summary(manifest)
    assert summary["jobs"]["tmp_x"]["routes"] == {
        "write": {
            "tmp_x": {"database": "dm_qa", "table": "tmp_x"},
        },
        "schema_read": {
            "i_shop_store_sales_ds": {
                "database": "dm_qa",
                "table": "I_SHOP_STORE_SALES_DS",
            },
        },
        "data_read": {},
    }


def test_manifest_persists_explicit_prod_route_for_unselected_upstream(
    tmp_path,
):
    task = _write_task(
        tmp_path,
        "result",
        "INSERT INTO dm.result SELECT * FROM dm.ods_sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"result": _ddl("result")},
        ddl_changes=[],
        jobs=[{"job": "result", "target": "result", "file": task}],
    )

    summary = manifest_summary(
        compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    )

    assert summary["jobs"]["result"]["routes"]["data_read"] == {
        "ods_sales": {"database": "dm", "table": "ods_sales"},
    }


def test_data_read_of_ddl_only_rename_prefills_baseline_data(tmp_path):
    task = _write_task(
        tmp_path,
        "daily_report",
        "INSERT INTO dm.daily_report SELECT * FROM dm.renamed_sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={
            "sales": _ddl("sales"),
            "daily_report": _ddl("daily_report"),
        },
        ddl_changes=[
            {
                "change_type": "RENAME",
                "old_name": "dm.sales",
                "new_name": "dm.renamed_sales",
                "sql": "ALTER TABLE dm.sales RENAME renamed_sales;",
            }
        ],
        jobs=[
            {
                "job": "daily_report",
                "target": "daily_report",
                "file": task,
            }
        ],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    action = manifest["prefill_actions"][0]
    context = manifest["jobs"]["daily_report"]["context"]

    assert action.current_table == "renamed_sales"
    assert action.baseline_table == "sales"
    assert action.mode is PrefillMode.FULL
    assert context.data_routes["renamed_sales"].database == "dm_qa"
    assert manifest["prefilled_tables"] == {"renamed_sales"}
    assert manifest["blockers"] == []


def test_self_read_previous_day_prefills_only_matching_partition(tmp_path):
    task = _write_task(
        tmp_path,
        "sales",
        "INSERT INTO dm.sales "
        "SELECT * FROM dm.sales "
        "WHERE stat_date = DATE_SUB(@etl_date, INTERVAL 1 DAY);",
    )
    sales_ddl = """CREATE TABLE dm.sales (
  stat_date DATE,
  amount DECIMAL(10, 2)
) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p_before VALUES LESS THAN ("2025-01-14"),
  PARTITION p20250114 VALUES LESS THAN ("2025-01-15"),
  PARTITION p20250115 VALUES LESS THAN ("2025-01-16"),
  PARTITION p_after VALUES LESS THAN (MAXVALUE)
);"""
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": sales_ddl},
        ddl_changes=[],
        jobs=[
            {
                "job": "sales",
                "target": "sales",
                "file": task,
                "execution_values": ["2025-01-15"],
            }
        ],
    )
    planner = FakePlanner(
        {
            "sales": {
                "materialized": "incremental",
                "slice_param": "etl_date",
                "slice_column": "stat_date",
            }
        }
    )

    manifest = compile_shadow_manifest(plan, tmp_path, planner)
    action = manifest["prefill_actions"][0]

    assert action.mode is PrefillMode.PARTITIONS
    assert action.partitions == ("p20250114",)
    assert (
        manifest["jobs"]["sales"]["context"].data_routes["sales"].database
        == "dm_qa"
    )


def test_selected_dependency_uses_runtime_readiness_not_array_order(tmp_path):
    ads_task = _write_task(
        tmp_path,
        "ads_sales",
        "INSERT INTO dm.ads_sales SELECT * FROM dm.sales;",
    )
    sales_task = _write_task(
        tmp_path,
        "sales",
        "INSERT INTO dm.sales SELECT * FROM dm.ods_sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={
            "sales": _ddl("sales"),
            "ads_sales": _ddl("ads_sales"),
        },
        ddl_changes=[],
        jobs=[
            {"job": "ads_sales", "target": "ads_sales", "file": ads_task},
            {"job": "sales", "target": "sales", "file": sales_task},
        ],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))

    assert manifest["blockers"] == []
    assert manifest["jobs"]["ads_sales"]["required_qa_tables"] == {"sales"}


def test_job_declares_multiple_non_helper_write_outputs(tmp_path):
    task = _write_task(
        tmp_path,
        "sales",
        "INSERT INTO dm.sales SELECT * FROM dm.ods_sales;\n"
        "INSERT INTO dm.sales_audit SELECT * FROM dm.ods_sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={
            "sales": _ddl("sales"),
            "sales_audit": _ddl("sales_audit"),
        },
        ddl_changes=[],
        jobs=[{"job": "sales", "target": "sales", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))

    assert manifest["jobs"]["sales"]["outputs"] == {
        "sales",
        "sales_audit",
    }


def test_created_helper_is_qa_local_but_not_published_as_business_output(
    tmp_path,
):
    sql = (
        "CREATE TABLE dm.stage_sales LIKE dm.sales;\n"
        "INSERT INTO dm.stage_sales SELECT * FROM dm.ods_sales;\n"
        "INSERT INTO dm.sales SELECT * FROM dm.stage_sales;"
    )
    task = _write_task(tmp_path, "sales", sql)
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": _ddl("sales")},
        ddl_changes=[],
        jobs=[{"job": "sales", "target": "sales", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    job = manifest["jobs"]["sales"]
    rewritten = rewrite_shadow_sql(sql, job["context"])

    assert job["outputs"] == {"sales"}
    assert "FROM dm_qa.stage_sales" in rewritten
    assert manifest["prefill_actions"] == []


def test_conditional_delete_prefills_rows_but_unconditional_delete_does_not(
    tmp_path,
):
    sales_ddl = """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
  PARTITION p_after VALUES LESS THAN (MAXVALUE)
);"""
    conditional_file = _write_task(
        tmp_path,
        "conditional_delete",
        "DELETE FROM dm.sales WHERE stat_date = DATE '2025-01-15';",
    )
    truncate_file = _write_task(
        tmp_path,
        "truncate_delete",
        "DELETE FROM dm.sales;",
    )
    conditional_plan = _plan(
        tmp_path,
        baseline_ddl={"sales": sales_ddl},
        ddl_changes=[],
        jobs=[
            {
                "job": "conditional_delete",
                "target": "sales",
                "file": conditional_file,
            }
        ],
    )
    truncate_plan = _plan(
        tmp_path,
        baseline_ddl={"sales": sales_ddl},
        ddl_changes=[],
        jobs=[
            {
                "job": "truncate_delete",
                "target": "sales",
                "file": truncate_file,
            }
        ],
    )

    conditional = compile_shadow_manifest(
        conditional_plan, tmp_path, FakePlanner({})
    )
    truncate = compile_shadow_manifest(
        truncate_plan, tmp_path, FakePlanner({})
    )

    assert conditional["prefill_actions"][0].mode is PrefillMode.PARTITIONS
    assert conditional["prefill_actions"][0].partitions == ("p202501",)
    assert truncate["prefill_actions"] == []


def test_unresolved_relation_role_is_a_compile_blocker(tmp_path):
    task = _write_task(
        tmp_path,
        "sales",
        "GRANT SELECT ON dm.sales TO bob;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": _ddl("sales")},
        ddl_changes=[],
        jobs=[{"job": "sales", "target": "sales", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))

    assert len(manifest["blockers"]) == 1
    assert "unresolved relation roles: sales" in manifest["blockers"][0]


def test_reading_a_phase2_dropped_table_is_blocked(tmp_path):
    task = _write_task(
        tmp_path,
        "report",
        "INSERT INTO dm.report SELECT * FROM dm.sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": _ddl("sales"), "report": _ddl("report")},
        ddl_changes=[
            {
                "change_type": "DROP",
                "table_name": "dm.sales",
                "sql": "DROP TABLE dm.sales;",
            }
        ],
        jobs=[{"job": "report", "target": "report", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))

    assert manifest["prefill_actions"] == []
    assert len(manifest["blockers"]) == 1
    assert "sales is dropped in Phase 2" in manifest["blockers"][0]


def test_external_same_name_source_is_not_selected_or_prefilled(tmp_path):
    task = _write_task(
        tmp_path,
        "report",
        "INSERT INTO dm.report SELECT * FROM reference_db.sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": _ddl("sales"), "report": _ddl("report")},
        ddl_changes=[],
        jobs=[{"job": "report", "target": "report", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    context = manifest["jobs"]["report"]["context"]

    assert manifest["prefill_actions"] == []
    assert rewrite_shadow_sql(
        "INSERT INTO dm.report SELECT * FROM reference_db.sales;", context
    ) == ("INSERT INTO dm_qa.report SELECT * FROM reference_db.sales;")


def test_other_alias_partition_predicate_cannot_narrow_selected_source(
    tmp_path,
):
    sales_ddl = """CREATE TABLE dm.sales (
  store_id BIGINT,
  stat_date DATE
) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
  PARTITION p202502 VALUES LESS THAN ("2025-03-01")
);"""
    task = _write_task(
        tmp_path,
        "report",
        "INSERT INTO dm.report "
        "SELECT s.store_id FROM dm.sales s "
        "JOIN reference_db.store_dim d ON s.store_id = d.store_id "
        "WHERE d.stat_date = DATE '2025-01-15';",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": sales_ddl, "report": _ddl("report")},
        ddl_changes=[],
        jobs=[{"job": "report", "target": "report", "file": task}],
    )

    manifest = compile_shadow_manifest(plan, tmp_path, FakePlanner({}))
    action = manifest["prefill_actions"][0]

    assert action.current_table == "sales"
    assert action.mode is PrefillMode.FULL


def test_prefill_does_not_satisfy_downstream_producer_readiness(tmp_path):
    sales_task = _write_task(
        tmp_path,
        "sales",
        "INSERT INTO dm.sales SELECT * FROM dm.ods_sales "
        "WHERE stat_date = @etl_date;",
    )
    report_task = _write_task(
        tmp_path,
        "report",
        "INSERT INTO dm.report SELECT * FROM dm.sales;",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": _ddl("sales"), "report": _ddl("report")},
        ddl_changes=[],
        jobs=[
            {"job": "report", "target": "report", "file": report_task},
            {
                "job": "sales",
                "target": "sales",
                "file": sales_task,
                "execution_values": ["2025-01-15"],
            },
        ],
    )
    planner = FakePlanner(
        {
            "sales": {
                "materialized": "incremental",
                "slice_param": "etl_date",
                "slice_column": "stat_date",
            }
        }
    )

    manifest = compile_shadow_manifest(plan, tmp_path, planner)

    assert manifest["prefilled_tables"] == {"sales"}
    assert manifest["jobs"]["report"]["required_qa_tables"] == {"sales"}
    assert manifest["producers"]["sales"] == "sales"


def test_invocation_full_refresh_flag_folds_real_incremental_if_predicate(
    tmp_path,
):
    sales_ddl = """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p20250115 VALUES LESS THAN ("2025-01-16"),
  PARTITION p_after VALUES LESS THAN (MAXVALUE)
);"""
    task = _write_task(
        tmp_path,
        "sales",
        "DELETE FROM dm.sales WHERE "
        "IF(@full_refresh = 1, 1 = 1, "
        "stat_date = CAST(@etl_date AS DATE));",
    )
    plan = _plan(
        tmp_path,
        baseline_ddl={"sales": sales_ddl},
        ddl_changes=[],
        jobs=[
            {
                "job": "sales",
                "target": "sales",
                "file": task,
                "execution_values": ["2025-01-15"],
            }
        ],
    )
    planner = FakePlanner(
        {
            "sales": {
                "materialized": "incremental",
                "slice_param": "etl_date",
                "slice_column": "stat_date",
            }
        }
    )

    manifest = compile_shadow_manifest(plan, tmp_path, planner)

    assert manifest["prefill_actions"][0].mode is PrefillMode.PARTITIONS
    assert manifest["prefill_actions"][0].partitions == ("p20250115",)
