import json
import os
import subprocess
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner, TaskSpec


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


def test_execution_preflight_uses_output_model_and_job_sql_identity(tmp_path):
    sql_path = tmp_path / "prepare_sales.sql"
    sql_path.write_text("SELECT 1;", encoding="utf-8")
    calls = []

    class RecordingPlanner:
        def task_spec(self, job_name, path, *, model_name=None):
            calls.append((job_name, path, model_name))
            return TaskSpec(
                job_name=job_name,
                sql_path=path,
                materialized="full",
                full_refresh_strategy="replace_all",
                slice_param=None,
                slice_column=None,
                slice_period=None,
                companion_path=None,
                historical_replay_supported=True,
            )

        @staticmethod
        def plan_full_refresh(spec, values):
            return []

    task_run._validate_execution_plan(
        ["prepare_sales"],
        {"prepare_sales": sql_path},
        RecordingPlanner(),
        [],
        full_refresh=True,
        model_names_by_job={"prepare_sales": "dwd_order"},
    )

    assert calls == [("prepare_sales", sql_path, "dwd_order")]


def test_job_model_names_require_one_managed_output():
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "full_name": "internal.demo_db.stage",
                "dataset_type": "process",
            },
            {
                "full_name": "internal.demo_db.dwd_order",
                "dataset_type": "managed",
            },
        ],
        "jobs": [
            {
                "name": "prepare_sales",
                "outputs": [
                    "internal.demo_db.stage",
                    "internal.demo_db.dwd_order",
                ],
            }
        ],
    }

    assert task_run._job_model_names_from_lineage(lineage_data) == {
        "prepare_sales": "dwd_order"
    }


def _process_lineage_payload(dataset_type):
    process_dataset = "Internal.Demo_DB.Sales_Stage"
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "Sales_Report",
                "full_name": "internal.demo_db.sales_report",
                "dataset_type": "managed",
                "columns": [],
            },
            {
                "name": "Sales_Stage",
                "full_name": process_dataset,
                "dataset_type": dataset_type,
                "columns": [],
            },
        ],
        "jobs": [
            {
                "name": "Build_Report",
                "source_file": "mid/tasks/Build_Report.sql",
                "inputs": [process_dataset],
                "outputs": ["internal.demo_db.sales_report"],
            },
            {
                "name": "Prepare_Sales",
                "source_file": "mid/tasks/Prepare_Sales.sql",
                "inputs": [],
                "outputs": [process_dataset],
            },
        ],
        "edges": [],
        "diagnostics": [],
    }


def _configure_process_plan_project(
    monkeypatch,
    tmp_path,
    *,
    dataset_type="process",
    extracted_dataset_type=None,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    lineage_dir = project_dir / "artifacts" / "lineage"
    task_dir.mkdir(parents=True)
    lineage_dir.mkdir(parents=True)
    for job_name in ("Prepare_Sales", "Build_Report"):
        (task_dir / "{}.sql".format(job_name)).write_text(
            "SELECT 1;", encoding="utf-8"
        )

    stale_lineage = _process_lineage_payload(dataset_type)
    fresh_lineage = _process_lineage_payload(
        extracted_dataset_type or dataset_type
    )
    lineage_path = lineage_dir / "lineage_data.json"
    lineage_path.write_text(json.dumps(stale_lineage), encoding="utf-8")
    stale_dag = task_run.JobDAG.from_jobs(
        ["Build_Report", "Prepare_Sales"],
        [
            {
                "upstream_job": "Prepare_Sales",
                "downstream_job": "Build_Report",
                "datasets": ["internal.demo_db.sales_stage"],
            }
        ],
    )
    dag_path = lineage_dir / "job_dag.json"
    stale_dag.save(dag_path)

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "db": "demo_db",
            "qa_db": "demo_db_qa",
        },
    )
    monkeypatch.setattr(task_run, "get_mysql_cmd", lambda _: ["mysql"])
    monkeypatch.setattr(task_run, "ExecutionPlanner", lambda _: object())
    monkeypatch.setattr(
        task_run, "_validate_execution_plan", lambda *args, **kwargs: 0
    )
    extractor_calls = []

    def fake_extractor(cmd, **kwargs):
        extractor_calls.append((cmd, kwargs))
        lineage_path.write_text(json.dumps(fresh_lineage), encoding="utf-8")
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_extractor)
    return {
        "project_dir": project_dir,
        "lineage_path": lineage_path,
        "dag_path": dag_path,
        "stale_lineage": stale_lineage,
        "fresh_lineage": fresh_lineage,
        "extractor_calls": extractor_calls,
    }


@pytest.mark.parametrize(
    ("dataset_type", "expected_status"),
    (("process", 1), ("managed", 0)),
)
def test_job_list_requires_process_producer_but_not_managed_producer(
    monkeypatch,
    tmp_path,
    capsys,
    dataset_type,
    expected_status,
):
    _configure_process_plan_project(
        monkeypatch,
        tmp_path,
        dataset_type=dataset_type,
    )
    executed = []
    monkeypatch.setattr(
        task_run,
        "_run_job",
        lambda _date, job_name, *args, **kwargs: executed.append(job_name),
    )

    @contextmanager
    def available_lock(_project):
        yield

    monkeypatch.setattr(
        task_run, "project_run_lock", available_lock, raising=False
    )
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--job-list",
            "build_report",
        ],
    )

    assert task_run.main() == expected_status
    captured = capsys.readouterr()
    if dataset_type == "process":
        assert executed == []
        assert "Prepare_Sales" in captured.out
        assert "Build_Report" in captured.out
        assert "Internal.Demo_DB.Sales_Stage" in captured.out
    else:
        assert executed == ["Build_Report"]


@pytest.mark.parametrize("full_refresh", (False, True))
def test_task_run_locks_actual_execution_but_not_validation(
    monkeypatch,
    tmp_path,
    full_refresh,
):
    _configure_process_plan_project(monkeypatch, tmp_path)
    lock_entries = []
    executed = []

    @contextmanager
    def recording_lock(project):
        lock_entries.append(project)
        yield

    monkeypatch.setattr(
        task_run, "project_run_lock", recording_lock, raising=False
    )
    monkeypatch.setattr(
        task_run,
        "_run_job",
        lambda _date, job_name, *args, **kwargs: executed.append(job_name),
    )
    monkeypatch.setattr(
        task_run,
        "_run_job_full_refresh",
        lambda job_name, *args, **kwargs: executed.append(job_name),
    )
    base_argv = [
        "task_run",
        "--project",
        "demo",
        "--etl-dates",
        "2025-01-15",
        "--job-list",
        "Prepare_Sales",
        "Build_Report",
    ]
    if full_refresh:
        base_argv.append("--full-refresh")

    monkeypatch.setattr(task_run.sys, "argv", base_argv)
    assert task_run.main() == 0
    monkeypatch.setattr(task_run.sys, "argv", base_argv + ["--validate-only"])
    assert task_run.main() == 0

    assert lock_entries == ["demo"]
    assert executed == ["Prepare_Sales", "Build_Report"]


def test_task_run_rejects_busy_project_lock_before_sql(
    monkeypatch,
    tmp_path,
    capsys,
):
    _configure_process_plan_project(monkeypatch, tmp_path)
    executed = []

    class BusyLockError(RuntimeError):
        pass

    @contextmanager
    def busy_lock(_project):
        raise BusyLockError("project demo is already executing SQL")
        yield

    monkeypatch.setattr(
        task_run, "ProjectRunLockError", BusyLockError, raising=False
    )
    monkeypatch.setattr(task_run, "project_run_lock", busy_lock, raising=False)
    monkeypatch.setattr(
        task_run,
        "_run_job",
        lambda _date, job_name, *args, **kwargs: executed.append(job_name),
    )
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--job-list",
            "Prepare_Sales",
            "Build_Report",
        ],
    )

    assert task_run.main() == 1
    assert executed == []
    assert "project demo is already executing SQL" in capsys.readouterr().out


def test_task_run_refreshes_stale_managed_dependency_before_process_closure(
    monkeypatch,
    tmp_path,
    capsys,
):
    state = _configure_process_plan_project(
        monkeypatch,
        tmp_path,
        dataset_type="managed",
        extracted_dataset_type="process",
    )
    executed = []
    monkeypatch.setattr(
        task_run,
        "_run_job",
        lambda _date, job_name, *args, **kwargs: executed.append(job_name),
    )
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--job-list",
            "Build_Report",
        ],
    )

    assert task_run.main() == 1
    assert len(state["extractor_calls"]) == 1
    assert executed == []
    output = capsys.readouterr().out
    assert "Prepare_Sales" in output
    assert "Build_Report" in output
    assert "Internal.Demo_DB.Sales_Stage" in output


@pytest.mark.parametrize(
    ("lineage_version", "dag_version"),
    ((1, 1), (1, 2), (2, 1)),
    ids=("v1", "v1-lineage-v2-dag", "v2-lineage-v1-dag"),
)
def test_task_run_replaces_v1_or_mixed_artifacts_from_one_fresh_v2_payload(
    monkeypatch,
    tmp_path,
    lineage_version,
    dag_version,
):
    state = _configure_process_plan_project(monkeypatch, tmp_path)
    if lineage_version == 1:
        state["lineage_path"].write_text(
            json.dumps({"tables": [], "edges": []}), encoding="utf-8"
        )
    if dag_version == 1:
        task_run.JobDAG(
            [{"source": "Prepare_Sales", "target": "Build_Report"}]
        ).save(state["dag_path"])
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--validate-only",
            "--job-list",
            "Prepare_Sales",
            "Build_Report",
        ],
    )

    assert task_run.main() == 0
    assert len(state["extractor_calls"]) == 1
    assert (
        json.loads(state["lineage_path"].read_text(encoding="utf-8"))
        == (state["fresh_lineage"])
    )
    expected_dag = task_run.job_dag_from_lineage(
        state["fresh_lineage"],
        runnable_jobs={"Prepare_Sales", "Build_Report"},
    ).to_dict()
    assert json.loads(state["dag_path"].read_text(encoding="utf-8")) == (
        expected_dag
    )


def test_refresh_dag_forces_no_cache_lineage_extraction(monkeypatch, tmp_path):
    state = _configure_process_plan_project(monkeypatch, tmp_path)
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--validate-only",
            "--refresh-dag",
        ],
    )

    assert task_run.main() == 0
    assert len(state["extractor_calls"]) == 1
    command = state["extractor_calls"][0][0]
    assert "--no-cache" in command


def test_normal_planning_uses_cached_extraction_output_for_saved_dag(
    monkeypatch,
    tmp_path,
):
    state = _configure_process_plan_project(
        monkeypatch,
        tmp_path,
        dataset_type="managed",
        extracted_dataset_type="process",
    )
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
            "--validate-only",
            "--job-list",
            "Prepare_Sales",
            "Build_Report",
        ],
    )

    assert task_run.main() == 0
    assert len(state["extractor_calls"]) == 1
    command, kwargs = state["extractor_calls"][0]
    assert command[:3] == [
        os.sys.executable,
        "-m",
        "dw_refactor_agent.lineage.lineage_extractor",
    ]
    assert "--no-cache" not in command
    assert command[command.index("--output") + 1] == str(state["lineage_path"])
    assert kwargs["check"] is True
    assert kwargs["cwd"] == task_run.PROJECT_ROOT
    assert str(config.SRC_ROOT) in kwargs["env"]["PYTHONPATH"].split(
        os.pathsep
    )
    saved_dag = json.loads(state["dag_path"].read_text(encoding="utf-8"))
    assert (
        saved_dag
        == task_run.job_dag_from_lineage(
            state["fresh_lineage"],
            runnable_jobs={"Prepare_Sales", "Build_Report"},
        ).to_dict()
    )


def test_lineage_extractor_failure_aborts_before_database_execution(
    monkeypatch,
    tmp_path,
    capsys,
):
    _configure_process_plan_project(monkeypatch, tmp_path)
    database_setup = []
    executed = []

    def fail_extractor(cmd, **_kwargs):
        raise subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(task_run.subprocess, "run", fail_extractor)
    monkeypatch.setattr(
        task_run,
        "get_mysql_cmd",
        lambda env: database_setup.append(env) or ["mysql"],
    )
    monkeypatch.setattr(
        task_run,
        "_run_job",
        lambda _date, job_name, *args, **kwargs: executed.append(job_name),
    )
    monkeypatch.setattr(
        task_run.sys,
        "argv",
        [
            "task_run",
            "--project",
            "demo",
            "--etl-dates",
            "2025-01-15",
        ],
    )

    assert task_run.main() == 1
    assert database_setup == []
    assert executed == []
    assert "lineage extraction failed" in capsys.readouterr().out
