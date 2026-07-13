import json
import os
import subprocess
from datetime import date, timedelta

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["mysql"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_resolve_etl_dates_expands_two_calendar_month_window():
    values = resolve_etl_dates(
        None,
        lookback_months=2,
        end_date="2026-07-13",
    )

    assert values[0] == "2026-05-13"
    assert values[-1] == "2026-07-13"
    assert len(values) == 62


def test_resolve_etl_dates_clamps_month_end_and_validates_inputs():
    values = resolve_etl_dates(
        None,
        lookback_months=1,
        end_date="2025-03-31",
    )

    assert values[0] == "2025-02-28"
    assert values[-1] == "2025-03-31"
    with pytest.raises(ValueError, match="不能与"):
        resolve_etl_dates(
            ["2025-03-31"],
            lookback_months=1,
        )
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        resolve_etl_dates(["2025-02-30"])
    with pytest.raises(ValueError, match="只能与"):
        resolve_etl_dates(None, end_date="2025-03-31")


def test_resolve_etl_dates_defaults_window_end_to_today():
    values = resolve_etl_dates(
        None,
        lookback_months=1,
        today=date(2025, 1, 15),
    )

    assert values[0] == "2024-12-15"
    assert values[-1] == "2025-01-15"


def _write_execution_project(
    monkeypatch,
    tmp_path,
    *,
    job_name="dwd_customer",
    model_config="execution:\n  materialized: incremental\n",
    companion=False,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    model_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    ddl_dir.mkdir(parents=True)
    sql_file = task_dir / f"{job_name}.sql"
    sql_file.write_text("SELECT @etl_date, @full_refresh;", encoding="utf-8")
    (model_dir / f"{job_name}.yaml").write_text(
        f"version: 2\nname: {job_name}\nlayer: DWD\n{model_config}",
        encoding="utf-8",
    )
    (ddl_dir / f"{job_name}.sql").write_text(
        "CREATE TABLE demo_db.dwd_customer (\n"
        "  id BIGINT,\n"
        "  stat_date DATE\n"
        ") ENGINE=OLAP DISTRIBUTED BY HASH(id) BUCKETS 1;",
        encoding="utf-8",
    )
    if companion:
        companion_dir = task_dir / "full_refresh"
        companion_dir.mkdir()
        (companion_dir / f"{job_name}_full_refresh.sql").write_text(
            "SELECT @full_refresh;",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "execution": {
                "default_slice": {
                    "param": "etl_date",
                    "column": "stat_date",
                    "period": "D",
                }
            },
        },
    )
    return sql_file


def test_incremental_full_refresh_replays_slices_without_partition_management(
    monkeypatch,
    tmp_path,
):
    calls = []
    sql_file = _write_execution_project(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo")

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("input", "").strip())
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)

    task_run._run_job_full_refresh(
        "dwd_customer",
        sql_file,
        ["mysql"],
        "demo_db",
        planner,
        ["2025-01-01", "2025-01-02"],
    )

    assert len(calls) == 2
    assert calls[0].startswith(
        "SET @etl_date = '2025-01-01';\nSET @full_refresh = 0;"
    )
    assert calls[1].startswith(
        "SET @etl_date = '2025-01-02';\nSET @full_refresh = 0;"
    )


def test_companion_full_refresh_runs_companion_with_full_refresh_one(
    monkeypatch,
    tmp_path,
):
    calls = []
    sql_file = _write_execution_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  full_refresh_strategy: companion\n"
        ),
        companion=True,
    )
    planner = ExecutionPlanner("demo")

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("input", "").strip())
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)

    task_run._run_job_full_refresh(
        "dwd_customer",
        sql_file,
        ["mysql"],
        "demo_db",
        planner,
        ["2025-01-01", "2025-01-02"],
    )

    assert len(calls) == 1
    assert calls[0].startswith("SET @full_refresh = 1;\n")
    assert "SELECT @full_refresh;" in calls[0]
    assert "PARTITION" not in calls[0]


def test_execution_plan_preflight_rejects_history_before_running_sql(
    monkeypatch,
    tmp_path,
):
    sql_file = _write_execution_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  historical_replay_supported: false\n"
        ),
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(
        ExecutionConfigError, match="does not support historical replay"
    ):
        task_run._validate_execution_plan(
            ["dwd_customer"],
            {"dwd_customer": sql_file},
            planner,
            ["2000-01-01"],
            full_refresh=False,
        )


def test_history_replay_can_skip_unsupported_current_state_dates(
    monkeypatch,
    tmp_path,
):
    sql_file = _write_execution_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  historical_replay_supported: false\n"
        ),
    )
    planner = ExecutionPlanner("demo")
    current_date = date.today().isoformat()
    historical_date = (date.today() - timedelta(days=1)).isoformat()

    invocation_count = task_run._validate_execution_plan(
        ["dwd_customer"],
        {"dwd_customer": sql_file},
        planner,
        [historical_date, current_date],
        full_refresh=False,
        skip_unsupported_history=True,
    )

    assert invocation_count == 1
    assert (
        task_run._plan_regular_invocations(
            planner,
            planner.task_spec("dwd_customer", sql_file),
            historical_date,
            skip_unsupported_history=True,
        )
        == []
    )


def test_build_job_dag_refreshes_lineage_with_src_pythonpath(
    monkeypatch, tmp_path
):
    lineage_path = tmp_path / "lineage_data.json"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        lineage_path.write_text(
            json.dumps({"tables": [], "edges": []}),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr(
        task_run, "_resolve_lineage_data_file", lambda _: lineage_path
    )
    monkeypatch.setattr(task_run.subprocess, "run", fake_run)

    dag = task_run._build_job_dag("shop")

    assert dag._edges == []
    cmd, kwargs = calls[0]
    assert cmd[:3] == [
        os.sys.executable,
        "-m",
        "dw_refactor_agent.lineage.lineage_extractor",
    ]
    assert str(config.SRC_ROOT) in kwargs["env"]["PYTHONPATH"].split(
        os.pathsep
    )


def test_get_task_files_reads_mid_and_ads_task_dirs(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "full_refresh").mkdir(parents=True)
    (project_dir / "ads" / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / "legacy_job.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dwd_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dwd_customer_full_refresh.sql"
    ).write_text("", encoding="utf-8")
    (project_dir / "ads" / "tasks" / "ads_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
        },
    )

    task_files = task_run._get_task_files("demo")

    assert sorted(task_files) == [
        "ads_customer",
        "dwd_customer",
    ]
    assert task_files["dwd_customer"] == (
        project_dir / "mid" / "tasks" / "dwd_customer.sql"
    )


def test_discover_ods_dates_uses_model_layer(monkeypatch, tmp_path):
    models_dir = tmp_path / "demo_project" / "mid" / "models"
    ods_models_dir = (
        tmp_path / "demo_project" / "ods" / "models" / "internal" / "demo_db"
    )
    models_dir.mkdir(parents=True)
    ods_models_dir.mkdir(parents=True)
    (ods_models_dir / "source_events.yaml").write_text(
        "version: 2\nname: source_events\nlayer: ODS\n",
        encoding="utf-8",
    )
    (models_dir / "ods_legacy.yaml").write_text(
        "version: 2\nname: ods_legacy\nlayer: DWD\n",
        encoding="utf-8",
    )

    calls = []

    def fake_run(*args, **kwargs):
        sql = kwargs.get("input", "")
        calls.append(sql)
        if sql == "SHOW TABLES":
            return _completed(
                stdout=("Tables_in_demo_db\nsource_events\nods_legacy\n")
            )
        return _completed(stdout="d\n2025-01-02\n2025-01-01\n")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG, "demo", {"dir": "demo_project"}
    )
    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    config.clear_model_metadata_cache()

    assert task_run._discover_ods_dates("demo", "demo_db", ["mysql"]) == [
        "2025-01-01",
        "2025-01-02",
    ]
    assert calls == [
        "SHOW TABLES",
        "SELECT DISTINCT DATE(load_time) AS d FROM demo_db.source_events ORDER BY d",
    ]
    config.clear_model_metadata_cache()


def test_resolve_full_refresh_dates_prefers_explicit_dates(monkeypatch):
    def fail_discover(*args, **kwargs):
        raise AssertionError("should not discover ODS dates")

    monkeypatch.setattr(task_run, "_discover_ods_dates", fail_discover)

    assert task_run._resolve_full_refresh_dates(
        "demo",
        "demo_db",
        ["mysql"],
        ["2025-01-02", "2025-01-01", "2025-01-02"],
    ) == ["2025-01-02", "2025-01-01"]


def test_resolve_full_refresh_dates_requires_explicit_business_dates(
    monkeypatch,
):
    def fail_discover(*args, **kwargs):
        raise AssertionError("should not discover ODS dates")

    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {"execution": {"require_explicit_etl_dates": True}},
    )
    monkeypatch.setattr(task_run, "_discover_ods_dates", fail_discover)

    with pytest.raises(ExecutionConfigError, match="explicit --etl-dates"):
        task_run._resolve_full_refresh_dates(
            "demo",
            "demo_db",
            ["mysql"],
            None,
        )


def test_build_job_dag_accepts_structured_lineage_edges(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    (lineage_dir / "lineage_data.json").write_text(
        """
        {
          "edges": [
            {
              "source": {"type": "column", "id": "ods_order.order_id"},
              "target": {"type": "column", "id": "dwd_order_detail.order_id"}
            },
            {
              "source": {"type": "column", "id": "dwd_order_detail.order_id"},
              "target": {"type": "table", "id": "dws_order_summary"},
              "relation_type": "filter"
            },
            {
              "source": {"type": "literal", "value": "1"},
              "target": {"type": "column", "id": "dwd_order_detail.flag"}
            },
            {
              "source": {"type": "column", "id": "dwd_order_detail.order_id"},
              "target": {"type": "column", "id": "dwd_order_detail.order_id"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    dag = task_run._build_job_dag("demo")

    assert dag._deps == {
        "ods_order": {"dwd_order_detail"},
        "dwd_order_detail": {"dws_order_summary"},
    }


def test_task_run_resolvers_ignore_old_lineage_artifact_paths(
    monkeypatch, tmp_path
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    old_lineage_dir = tmp_path / "lineage"
    old_lineage_dir.mkdir()
    (old_lineage_dir / "lineage_data_demo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (old_lineage_dir / "job_dag_demo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    assert task_run._resolve_lineage_data_file("demo") == (
        project_dir / "artifacts" / "lineage" / "lineage_data.json"
    )
    assert task_run._resolve_job_dag_file("demo") == (
        project_dir / "artifacts" / "lineage" / "job_dag.json"
    )


def test_build_job_dag_collapses_transient_tables(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    (lineage_dir / "lineage_data.json").write_text(
        """
        {
          "tables": [
            {"name": "dwd_orders", "layer": "DWD", "columns": []},
            {"name": "tmp_orders_stage", "layer": "OTHER", "columns": [], "is_transient": true},
            {"name": "dws_orders", "layer": "DWS", "columns": []}
          ],
          "edges": [
            {
              "source": {"type": "column", "id": "dwd_orders.order_id"},
              "target": {"type": "column", "id": "tmp_orders_stage.order_id"}
            },
            {
              "source": {"type": "column", "id": "tmp_orders_stage.order_id"},
              "target": {"type": "column", "id": "dws_orders.order_id"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    dag = task_run._build_job_dag("demo")

    assert dag._deps == {"dwd_orders": {"dws_orders"}}
    assert "tmp_orders_stage" not in dag._deps
    assert "tmp_orders_stage" not in dag._rev


def test_dag_needs_refresh_when_loaded_targets_do_not_match_tasks():
    dag = task_run.JobDAG(
        [
            {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_CATG_SALE_MS"},
            {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_STORE_SALE_DS"},
        ]
    )

    assert (
        task_run._dag_needs_refresh_for_tasks(
            dag,
            {"dwd_order_detail", "dws_store_sales_daily"},
        )
        is True
    )


def test_dag_needs_refresh_keeps_current_dag_with_matching_targets():
    dag = task_run.JobDAG(
        [
            {"source": "ods_order", "target": "dwd_order_detail"},
            {"source": "dwd_order_detail", "target": "dws_store_sales_daily"},
        ]
    )

    assert (
        task_run._dag_needs_refresh_for_tasks(
            dag,
            {"dwd_order_detail", "dws_store_sales_daily"},
        )
        is False
    )
