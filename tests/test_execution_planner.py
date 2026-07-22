from __future__ import annotations

import subprocess
from datetime import date

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.planner import (
    ExecutionConfigError,
    ExecutionPlanner,
)
from dw_refactor_agent.execution.sql_executor import DirectSqlExecutor


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


def _write_template_task(
    monkeypatch,
    tmp_path,
    *,
    slice_parameter="etl_date",
    startup_prop="etl_date",
    startup_sensitive=False,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    sql_path.write_text(
        "INSERT INTO ${cdm_schema}.${run_table}\n"
        f"SELECT ${{{startup_prop}}}, ${{previous_day}}, ${{next_day}}, "
        "${previous_year_end};\n",
        encoding="utf-8",
    )
    contract = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": startup_prop,
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": True,
                "sensitive": startup_sensitive,
            }
        ],
        "project_params": [
            {
                "prop": "cdm_schema",
                "type": "IDENTIFIER",
                "source": "project.cdm_schema",
                "required": True,
            }
        ],
        "local_params": [
            {
                "prop": "previous_day",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": startup_prop,
                        "operation": "add_days",
                        "amount": -1,
                    }
                },
            },
            {
                "prop": "next_day",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": startup_prop,
                        "operation": "add_days",
                        "amount": 1,
                    }
                },
            },
            {
                "prop": "previous_year_end",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": startup_prop,
                        "operation": "previous_year_end",
                    }
                },
            },
            {
                "prop": "run_table",
                "direct": "IN",
                "type": "IDENTIFIER",
                "value": {
                    "derive": {
                        "from": startup_prop,
                        "operation": "format_date",
                        "format": "yyyyMMdd",
                        "prefix": "tmp_orders_",
                    }
                },
            },
        ],
        "usage": {
            "slices": [{"prop": startup_prop, "parameter": slice_parameter}],
            "dynamic_relations": [
                {"prop": "run_table", "lifecycle": "invocation"}
            ],
        },
    }
    sql_path.with_suffix(".yaml").write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    config.core.PROJECT_CONFIG["demo"]["task_templates"] = {
        "version": 1,
        "analysis": {
            "startup": {"etl_date": "2000-02-29"},
            "project": {"cdm_schema": "analysis_dm"},
        },
        "bindings": {
            "prod": {"project": {"cdm_schema": "prod_dm"}},
            "test": {"project": {"cdm_schema": "test_dm"}},
        },
    }
    return sql_path


def _write_companion_template(companion_path, *, declare_slice=False):
    companion_path.write_text(
        "SELECT ${etl_start_date}, ${etl_end_date};\n",
        encoding="utf-8",
    )
    contract = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": prop,
                "type": "DATE",
                "source": f"invocation.{prop}",
                "required": True,
            }
            for prop in ("etl_start_date", "etl_end_date")
        ],
        "usage": {
            "partitions": [
                {"prop": prop, "parameter": prop}
                for prop in ("etl_start_date", "etl_end_date")
            ]
        },
    }
    if declare_slice:
        contract["usage"]["slices"] = [
            {"prop": "etl_start_date", "parameter": "etl_start_date"}
        ]
    companion_path.with_suffix(".yaml").write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )


def test_template_invocations_render_typed_dates_and_dynamic_names(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo", db_env="prod")
    spec = planner.task_spec("dwd_orders", sql_path)

    invocations = planner.plan_regular_run(
        spec,
        ["2025-03-01", "2025-03-02"],
    )

    assert [item.session_params for item in invocations] == [
        {"etl_date": "2025-03-01"},
        {"etl_date": "2025-03-02"},
    ]
    assert "`prod_dm`.`tmp_orders_20250301`" in invocations[0].resolved_sql
    assert "'2025-02-28'" in invocations[0].resolved_sql
    assert "'2025-03-02'" in invocations[0].resolved_sql
    assert "'2024-12-31'" in invocations[0].resolved_sql
    assert "`tmp_orders_20250302`" in invocations[1].resolved_sql
    assert invocations[0].render_inputs["etl_date"] == date(2025, 3, 1)
    assert invocations[0].render_inputs["previous_day"] == date(2025, 2, 28)
    assert invocations[0].render_inputs["run_table"] == "tmp_orders_20250301"


def test_direct_executor_injects_legacy_session_params_after_template_render(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo")
    invocation = planner.plan_regular_run(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01"],
    )[0]
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs["input"])
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(
        "dw_refactor_agent.execution.sql_executor.subprocess.run",
        fake_run,
    )
    DirectSqlExecutor(["mysql"], "demo_dm").execute(invocation)

    assert calls[0].startswith(
        "SET @etl_date = '2025-03-01';\nSET @full_refresh = 0;\n"
    )
    assert "${" not in calls[0]
    assert "`prod_dm`.`tmp_orders_20250301`" in calls[0]


def test_legacy_invocation_sql_bytes_remain_unchanged(
    monkeypatch,
    tmp_path,
):
    sql_path, _ = _write_demo_project(
        monkeypatch,
        tmp_path,
        model_config="execution:\n  materialized: incremental\n",
    )
    legacy_sql = sql_path.read_text(encoding="utf-8")
    planner = ExecutionPlanner("demo")
    invocation = planner.plan_regular_run(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01"],
    )[0]
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs["input"])
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(
        "dw_refactor_agent.execution.sql_executor.subprocess.run",
        fake_run,
    )
    DirectSqlExecutor(["mysql"], "demo_dm").execute(invocation)

    assert invocation.resolved_sql is None
    assert invocation.render_inputs == {}
    assert calls == [
        f"SET @etl_date = '2025-03-01';\nSET @full_refresh = 0;\n{legacy_sql}"
    ]


def test_execution_plan_validation_dry_renders_without_database_calls(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo")
    database_calls = []

    monkeypatch.setattr(
        "dw_refactor_agent.execution.sql_executor.subprocess.run",
        lambda *args, **kwargs: database_calls.append((args, kwargs)),
    )

    count = task_run._validate_execution_plan(
        ["dwd_orders"],
        {"dwd_orders": sql_path},
        planner,
        ["2025-03-01", "2025-03-02"],
        full_refresh=False,
    )

    assert count == 2
    assert database_calls == []


def test_template_execution_uses_selected_database_environment(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo", db_env="test")

    invocation = planner.plan_regular_run(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01"],
    )[0]

    assert "`test_dm`.`tmp_orders_20250301`" in invocation.resolved_sql
    assert "prod_dm" not in invocation.resolved_sql


def test_template_execution_requires_selected_environment_binding(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo", db_env="qa")
    spec = planner.task_spec("dwd_orders", sql_path)

    with pytest.raises(ExecutionConfigError, match="missing execution"):
        planner.plan_regular_run(spec, ["2025-03-01"])


def test_scheduler_etl_date_binds_yaml_internal_startup_name(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(
        monkeypatch,
        tmp_path,
        startup_prop="business_date",
    )
    planner = ExecutionPlanner("demo")

    invocation = planner.plan_regular_run(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01"],
    )[0]

    assert invocation.session_params == {"etl_date": "2025-03-01"}
    assert invocation.render_inputs["business_date"] == date(2025, 3, 1)
    assert "'2025-03-01'" in invocation.resolved_sql


def test_sensitive_template_inputs_are_redacted_from_public_invocation(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(
        monkeypatch,
        tmp_path,
        startup_sensitive=True,
    )
    planner = ExecutionPlanner("demo")

    invocation = planner.plan_regular_run(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01"],
    )[0]

    assert invocation.public_session_params == {"etl_date": "<redacted>"}
    assert "2025-03-01" not in repr(invocation)
    assert invocation.public_summary["public_bindings"]["etl_date"] == (
        "<redacted>"
    )


def test_execution_override_cannot_replace_scheduler_slice_dependency(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    contract_path = sql_path.with_suffix(".yaml")
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    contract["startup_params"][0]["overrideable"] = True
    contract_path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    config.core.PROJECT_CONFIG["demo"]["task_templates"]["bindings"]["prod"][
        "overrides"
    ] = {"etl_date": "1999-01-01"}
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)

    with pytest.raises(ExecutionConfigError, match="protected_override"):
        planner.plan_regular_run(spec, ["2025-03-01"])


def test_companion_template_uses_only_full_refresh_window_parameters(
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
    _write_companion_template(companion_path)
    planner = ExecutionPlanner("demo")

    invocation = planner.plan_full_refresh(
        planner.task_spec("dwd_orders", sql_path),
        ["2025-03-01", "2025-03-02"],
    )[0]

    assert invocation.session_params == {
        "etl_start_date": "2025-03-01",
        "etl_end_date": "2025-03-02",
    }
    assert "'2025-03-01', '2025-03-02'" in invocation.resolved_sql


def test_companion_template_rejects_per_slice_usage(
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
    _write_companion_template(companion_path, declare_slice=True)
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError, match="usage.slices"):
        planner.task_spec("dwd_orders", sql_path)


@pytest.mark.parametrize(
    ("etl_date", "schema", "message"),
    [
        ("2025-02-30", "prod_dm", "does not match"),
        ("2025-03-01", "unsafe-name", "safe identifier"),
    ],
)
def test_template_execution_fails_closed_on_invalid_inputs(
    monkeypatch,
    tmp_path,
    etl_date,
    schema,
    message,
):
    sql_path = _write_template_task(monkeypatch, tmp_path)
    config.core.PROJECT_CONFIG["demo"]["task_templates"]["bindings"]["prod"][
        "project"
    ]["cdm_schema"] = schema
    planner = ExecutionPlanner("demo")
    spec = planner.task_spec("dwd_orders", sql_path)

    with pytest.raises(ExecutionConfigError, match=message):
        planner.plan_regular_run(spec, [etl_date])


def test_template_slice_usage_must_match_model_execution_contract(
    monkeypatch,
    tmp_path,
):
    sql_path = _write_template_task(
        monkeypatch,
        tmp_path,
        slice_parameter="other_date",
    )
    planner = ExecutionPlanner("demo")

    with pytest.raises(ExecutionConfigError, match="must match"):
        planner.task_spec("dwd_orders", sql_path)


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
