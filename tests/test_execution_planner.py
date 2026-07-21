from __future__ import annotations

from datetime import date

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


def _rename_execution_model(
    tmp_path,
    *,
    job_name: str,
    model_name: str,
) -> None:
    project_dir = tmp_path / "warehouses" / "demo" / "mid"
    old_model = project_dir / "models" / f"{job_name}.yaml"
    model_text = old_model.read_text(encoding="utf-8").replace(
        f"name: {job_name}",
        f"name: {model_name}",
    )
    old_model.unlink()
    (project_dir / "models" / f"{model_name}.yaml").write_text(
        model_text,
        encoding="utf-8",
    )
    old_ddl = project_dir / "ddl" / f"{job_name}.sql"
    ddl_text = old_ddl.read_text(encoding="utf-8")
    old_ddl.unlink()
    (project_dir / "ddl" / f"{model_name}.sql").write_text(
        ddl_text,
        encoding="utf-8",
    )


def _write_quarantined_v3_model(tmp_path, execution_yaml=""):
    model_path = tmp_path / "warehouses/demo/mid/models/dwd_orders.yaml"
    model_path.write_text(
        "version: 3\n"
        "name: dwd_orders\n"
        "operational_layer: DWD\n"
        f"{execution_yaml}"
        "governance:\n"
        "  status: quarantined\n"
        "  schema_version: 1\n"
        "  withheld_sections: [classification, business_semantics, entities, grain, metrics]\n"
        "  reasons:\n"
        "    classification: [structure_bundle_incomplete]\n"
        "    business_semantics: [business_process_missing]\n"
        "    entities: [structure_bundle_incomplete]\n"
        "    grain: [structure_bundle_incomplete]\n"
        "    metrics: [dependent_structure_unavailable]\n",
        encoding="utf-8",
    )


def test_task_spec_validates_slice_against_model_name_ddl(
    monkeypatch, tmp_path
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        job_name="prepare_sales",
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  slice:\n"
            "    param: etl_date\n"
            "    column: stat_date\n"
            "    period: D\n"
        ),
        warehouse_execution="",
        ddl_column="other_date",
    )
    _rename_execution_model(
        tmp_path,
        job_name="prepare_sales",
        model_name="dwd_order",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError, match="dwd_order.sql"):
        planner.task_spec(
            "prepare_sales",
            sql_path,
            model_name="dwd_order",
        )


@pytest.mark.parametrize("mode", ["taskless", " TaSkLeSs "])
def test_task_spec_rejects_task_bound_to_taskless_model(
    monkeypatch,
    tmp_path,
    mode,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=f"execution:\n  mode: {mode!r}\n",
        warehouse_execution="",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(
        ExecutionConfigError,
        match="task SQL cannot bind to execution.mode=taskless",
    ):
        planner.task_spec("dwd_orders", sql_path)


def test_task_spec_matches_execution_model_name_case_insensitively(
    monkeypatch, tmp_path
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        job_name="prepare_sales",
        model_config="execution:\n  materialized: full\n",
        warehouse_execution="",
    )
    _rename_execution_model(
        tmp_path,
        job_name="prepare_sales",
        model_name="dwd_order",
    )
    planner = ExecutionPlanner("demo")

    spec = planner.task_spec(
        "Prepare_Sales",
        sql_path,
        model_name="DWD_Order",
    )

    assert spec.job_name == "Prepare_Sales"
    assert spec.materialized == "full"


def test_quarantined_v3_model_preserves_deterministic_task_spec(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: full\n",
        warehouse_execution="",
    )
    active_spec = ExecutionPlanner("demo").task_spec("dwd_orders", sql_path)
    _write_quarantined_v3_model(
        tmp_path,
        "execution:\n"
        "  materialized: full\n"
        "  full_refresh_strategy: replace_all\n",
    )

    quarantined_spec = ExecutionPlanner("demo").task_spec(
        "dwd_orders",
        sql_path,
    )

    assert quarantined_spec == active_spec


def test_quarantined_v3_model_still_requires_execution_contract(
    monkeypatch,
    tmp_path,
):
    _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: full\n",
    )
    _write_quarantined_v3_model(tmp_path)

    with pytest.raises(
        ExecutionConfigError,
        match="execution must be a mapping",
    ):
        ExecutionPlanner("demo")


def test_task_spec_matches_execution_model_ddl_case_insensitively(
    monkeypatch, tmp_path
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        job_name="prepare_sales",
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  slice:\n"
            "    param: etl_date\n"
            "    column: missing_date\n"
            "    period: D\n"
        ),
        warehouse_execution="",
        ddl_column="stat_date",
    )
    _rename_execution_model(
        tmp_path,
        job_name="prepare_sales",
        model_name="dwd_order",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError, match="dwd_order.sql"):
        planner.task_spec(
            "Prepare_Sales",
            sql_path,
            model_name="DWD_Order",
        )


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
    _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="config:\n  materialized: full\n",
    )

    with pytest.raises(ExecutionConfigError) as exc:
        ExecutionPlanner("demo")

    assert "config.materialized is no longer supported" in str(exc.value)
    assert "execution.materialized" in str(exc.value)


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


def test_companion_receives_configured_full_refresh_window(
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
        warehouse_execution=(
            "execution:\n"
            "  default_slice:\n"
            "    param: etl_date\n"
            "    column: stat_date\n"
            "    period: D\n"
            "  full_refresh_window:\n"
            "    start_param: etl_start_date\n"
            "    end_param: etl_end_date\n"
        ),
        companion=True,
    )
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)

    assert planner.plan_full_refresh(
        spec,
        ["2025-03-02", "2025-02-28", "2025-03-01", "2025-03-02"],
    ) == [
        TaskInvocation(
            job_name="dwd_orders",
            sql_path=companion_path,
            params={
                "etl_start_date": "2025-02-28",
                "etl_end_date": "2025-03-02",
            },
            full_refresh=True,
            strategy="companion",
        )
    ]

    with pytest.raises(ExecutionConfigError, match="contiguous"):
        planner.plan_full_refresh(
            spec,
            ["2025-02-28", "2025-03-02"],
        )


def test_shop_process_jobs_use_one_window_companion_invocation_each():
    project_path = config.project_dir("shop")
    assert project_path is not None
    planner = ExecutionPlanner("shop")
    jobs = (
        (
            "dws_store_sales_daily",
            "mid/tasks/dws_store_sales_daily.sql",
            "mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql",
        ),
        (
            "dim_store_metric_snapshot",
            "mid/tasks/dim_store_metric_snapshot.sql",
            (
                "mid/tasks/full_refresh/"
                "dim_store_metric_snapshot_full_refresh.sql"
            ),
        ),
    )

    invocations = []
    for job_name, task_path, _companion_path in jobs:
        spec = planner.task_spec(job_name, project_path / task_path)
        invocations.extend(
            planner.plan_full_refresh(spec, ["2025-01-15", "2025-01-16"])
        )

    window = {
        "etl_start_date": "2025-01-15",
        "etl_end_date": "2025-01-16",
    }
    assert [
        (
            invocation.job_name,
            invocation.sql_path.relative_to(project_path).as_posix(),
            invocation.params,
            invocation.full_refresh,
            invocation.strategy,
        )
        for invocation in invocations
    ] == [
        (job_name, companion_path, window, True, "companion")
        for job_name, _task_path, companion_path in jobs
    ]


def test_full_model_rejects_explicit_slice(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: full\n"
            "  slice:\n"
            "    param: etl_date\n"
            "    column: stat_date\n"
            "    period: D\n"
        ),
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(
        ExecutionConfigError, match="full models cannot define execution.slice"
    ):
        planner.task_spec("dwd_orders", sql_path)


def test_current_state_capture_rejects_historical_slice(monkeypatch, tmp_path):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  full_refresh_strategy: legacy_full_refresh\n"
            "  historical_replay_supported: false\n"
        ),
    )
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)

    with pytest.raises(
        ExecutionConfigError, match="does not support historical replay"
    ):
        planner.plan_regular_run(spec, ["2000-01-01"])

    invocations = planner.plan_regular_run(spec, [date.today().isoformat()])
    assert invocations[0].params == {"etl_date": date.today().isoformat()}


def test_full_refresh_replay_rejects_unsupported_historical_slice(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  historical_replay_supported: false\n"
        ),
    )
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)

    with pytest.raises(
        ExecutionConfigError, match="does not support historical replay"
    ):
        planner.plan_full_refresh(spec, ["2000-01-01"])
