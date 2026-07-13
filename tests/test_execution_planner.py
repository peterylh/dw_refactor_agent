from __future__ import annotations

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.planner import (
    ExecutionConfigError,
    ExecutionPlanner,
)


def _write_demo_project(
    monkeypatch,
    tmp_path,
    *,
    model_config: str,
    warehouse_execution: str = (
        "execution:\n"
        "  default_slice:\n"
        "    param: etl_date\n"
        "    column: stat_date\n"
        "    period: D\n"
    ),
    job_name: str = "dwd_orders",
    ddl_column: str = "stat_date",
    companion: bool = False,
):
    project_dir = tmp_path / "warehouses" / "demo"
    task_dir = project_dir / "mid" / "tasks"
    model_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    ddl_dir.mkdir(parents=True)

    warehouse_yaml = project_dir / "warehouse.yaml"
    warehouse_yaml.write_text(
        "name: demo\n"
        "catalog: internal\n"
        "database: demo_dm\n"
        "qa_database: demo_dm_qa\n"
        f"{warehouse_execution}",
        encoding="utf-8",
    )
    sql_path = task_dir / f"{job_name}.sql"
    sql_path.write_text(
        "INSERT INTO demo_dm.dwd_orders SELECT 1;", encoding="utf-8"
    )
    (model_dir / f"{job_name}.yaml").write_text(
        f"version: 2\nname: {job_name}\nlayer: DWD\n{model_config}",
        encoding="utf-8",
    )
    (ddl_dir / f"{job_name}.sql").write_text(
        "CREATE TABLE demo_dm.dwd_orders (\n"
        "    id BIGINT,\n"
        f"    {ddl_column} DATE\n"
        ") ENGINE=OLAP\n"
        "DUPLICATE KEY(id)\n"
        "DISTRIBUTED BY HASH(id) BUCKETS 1;",
        encoding="utf-8",
    )
    companion_path = None
    if companion:
        companion_dir = task_dir / "full_refresh"
        companion_dir.mkdir()
        companion_path = companion_dir / f"{job_name}_full_refresh.sql"
        companion_path.write_text(
            "INSERT INTO demo_dm.dwd_orders SELECT 2;",
            encoding="utf-8",
        )

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        config.core,
        "PROJECT_CONFIG",
        {
            "demo": config.core.load_warehouse_config(
                warehouse_yaml,
                project_root=tmp_path,
            )
        },
    )
    config.clear_model_metadata_cache()
    return sql_path, companion_path


def test_snapshot_materialized_is_rejected(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: snapshot\n",
    )

    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError) as exc:
        planner.task_spec("dwd_orders", sql_path)

    message = str(exc.value)
    assert "materialized: snapshot" in message
    assert "materialized: incremental" in message
    assert "execution:" in message
    assert "slice:" in message
    assert "snapshot_date" in message


def test_config_materialized_is_rejected(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="config:\n  materialized: full\n",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError) as exc:
        planner.task_spec("dwd_orders", sql_path)

    assert "config.materialized is no longer supported" in str(exc.value)
    assert "execution.materialized" in str(exc.value)


def test_explicit_project_root_ignores_other_workspace_global_config(
    monkeypatch, tmp_path
):
    _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    monkeypatch.setattr(
        config.core,
        "PROJECT_CONFIG",
        {
            "demo": {
                "dir": "warehouses/wrong-workspace",
                "execution": {"default_slice": {"period": "M"}},
            }
        },
    )

    planner = ExecutionPlanner("demo", project_root=tmp_path)

    assert planner.project_dir == tmp_path / "warehouses" / "demo"
    assert planner.warehouse_execution["default_slice"]["period"] == "D"


def test_incremental_defaults_to_replay_slices_with_full_refresh_zero(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    planner = ExecutionPlanner("demo")

    spec = planner.task_spec("dwd_orders", sql_path)
    invocations = planner.plan_full_refresh(spec, ["2025-01-01"])

    assert spec.full_refresh_strategy == "replay_slices"
    assert invocations == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=sql_path,
            params={"etl_date": "2025-01-01"},
            full_refresh=False,
            strategy="replay_slices",
        )
    ]


def test_companion_uses_companion_sql_and_full_refresh_one(
    monkeypatch,
    tmp_path,
):
    sql_path, companion_path = _write_demo_project(
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

    spec = planner.task_spec("dwd_orders", sql_path)
    invocations = planner.plan_full_refresh(spec, ["2025-01-01"])

    assert spec.companion_path == companion_path
    assert invocations == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=companion_path,
            params={},
            full_refresh=True,
            strategy="companion",
        )
    ]


def test_legacy_full_refresh_runs_normal_sql_once_with_full_refresh_one(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  full_refresh_strategy: legacy_full_refresh\n"
        ),
    )
    planner = ExecutionPlanner("demo")

    spec = planner.task_spec("dwd_orders", sql_path)

    assert planner.plan_full_refresh(spec, ["2025-01-01", "2025-01-02"]) == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=sql_path,
            params={},
            full_refresh=True,
            strategy="legacy_full_refresh",
        )
    ]


def test_full_defaults_to_replace_all_with_full_refresh_one(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: full\n",
    )
    planner = ExecutionPlanner("demo")

    spec = planner.task_spec("dwd_orders", sql_path)

    assert spec.full_refresh_strategy == "replace_all"
    assert planner.plan_full_refresh(spec, ["2025-01-01"]) == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=sql_path,
            params={},
            full_refresh=True,
            strategy="replace_all",
        )
    ]


def test_model_slice_overrides_project_default_slice(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  slice:\n"
            "    param: etl_month\n"
            "    column: stat_month_date\n"
            "    period: M\n"
        ),
        ddl_column="stat_month_date",
    )
    planner = ExecutionPlanner("demo")

    spec = planner.task_spec("dwd_orders", sql_path)
    invocations = planner.plan_regular_run(spec, ["2025-01-15"])

    assert spec.slice_param == "etl_month"
    assert spec.slice_column == "stat_month_date"
    assert spec.slice_period == "M"
    assert invocations[0].params == {"etl_month": "2025-01-01"}


def test_incremental_replay_slices_requires_slice_config(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
        warehouse_execution="",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError, match="execution.slice"):
        planner.task_spec("dwd_orders", sql_path)


def test_task_and_shadow_planning_match_for_same_job(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)
    shadow_job = {
        "job": "dwd_orders",
        "file": "warehouses/demo/mid/tasks/dwd_orders.sql",
        "execution_values": ["2025-01-01"],
    }

    task_invocations = planner.plan_regular_run(spec, ["2025-01-01"])
    shadow_invocations = planner.plan_shadow_job(
        shadow_job,
        project_root=tmp_path,
    )

    assert shadow_invocations == task_invocations


def test_shadow_job_missing_values_does_not_infer_slice_value(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    planner = ExecutionPlanner("demo")
    shadow_job = {
        "job": "dwd_orders",
        "file": "warehouses/demo/mid/tasks/dwd_orders.sql",
    }

    assert planner.plan_shadow_job(
        shadow_job,
        project_root=tmp_path,
    ) == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=sql_path,
            params={},
            full_refresh=False,
            strategy="replay_slices",
        )
    ]


def test_shop_main_task_specs_are_valid_against_declared_slices():
    planner = ExecutionPlanner("shop")

    specs = [
        planner.task_spec(task_path.stem, task_path)
        for task_path in config.iter_project_task_files(
            "shop",
            include_full_refresh=False,
        )
        if not task_path.stem.endswith("_full_refresh")
    ]

    assert {spec.job_name for spec in specs} >= {
        "dwd_order_detail",
        "dws_category_sales_monthly",
        "ads_store_performance",
        "ads_inventory_alert",
    }
