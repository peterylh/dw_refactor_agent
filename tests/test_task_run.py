import json
import subprocess
from contextlib import contextmanager
from datetime import date

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner, TaskSpec
from dw_refactor_agent.lineage.contract import validate_lineage_v2


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["mysql"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


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


def _unresolved_process_lineage_payload(
    *,
    reason="not_found",
    dataset_type="process",
    candidate_producer_jobs=(),
    include_unrelated_job=False,
):
    process_dataset = "Internal.Demo_DB.Sales_Stage"
    tables = [
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
    ]
    jobs = [
        {
            "name": "Build_Report",
            "source_file": "mid/tasks/Build_Report.sql",
            "inputs": [process_dataset],
            "outputs": ["internal.demo_db.sales_report"],
        }
    ]
    jobs.extend(
        {
            "name": job_name,
            "source_file": "mid/tasks/{}.sql".format(job_name),
            "inputs": [],
            "outputs": [process_dataset],
        }
        for job_name in candidate_producer_jobs
    )
    if include_unrelated_job:
        tables.append(
            {
                "name": "Unrelated_Output",
                "full_name": "internal.demo_db.unrelated_output",
                "dataset_type": "managed",
                "columns": [],
            }
        )
        jobs.append(
            {
                "name": "Unrelated_Job",
                "source_file": "mid/tasks/Unrelated_Job.sql",
                "inputs": [],
                "outputs": ["internal.demo_db.unrelated_output"],
            }
        )
    lineage_data = {
        "format_version": 2,
        "tables": tables,
        "jobs": jobs,
        "edges": [],
        "diagnostics": [
            {
                "code": "UNRESOLVED_DATASET_PRODUCER",
                "dataset": process_dataset,
                "reason": reason,
                "consumer_jobs": ["Build_Report"],
                "candidate_producer_jobs": list(candidate_producer_jobs),
            }
        ],
    }
    validate_lineage_v2(lineage_data)
    return lineage_data


def _configure_process_plan_project(
    monkeypatch,
    tmp_path,
    *,
    dataset_type="process",
    extracted_dataset_type=None,
    extracted_lineage=None,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    lineage_dir = project_dir / "artifacts" / "lineage"
    task_dir.mkdir(parents=True)
    lineage_dir.mkdir(parents=True)
    fresh_lineage = extracted_lineage or _process_lineage_payload(
        extracted_dataset_type or dataset_type
    )
    task_names = {job["name"] for job in fresh_lineage["jobs"]}
    for job_name in task_names:
        (task_dir / "{}.sql".format(job_name)).write_text(
            "SELECT 1;", encoding="utf-8"
        )

    stale_lineage = (
        fresh_lineage
        if extracted_lineage is not None
        else _process_lineage_payload(dataset_type)
    )
    lineage_path = lineage_dir / "lineage_data.json"
    lineage_path.write_text(json.dumps(stale_lineage), encoding="utf-8")
    stale_dag = task_run.job_dag_from_lineage(
        stale_lineage,
        runnable_jobs=task_names,
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


def test_unresolved_process_diagnostic_does_not_block_unrelated_subset(
    monkeypatch,
    tmp_path,
):
    lineage_data = _unresolved_process_lineage_payload(
        include_unrelated_job=True
    )
    _configure_process_plan_project(
        monkeypatch,
        tmp_path,
        extracted_lineage=lineage_data,
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
            "Unrelated_Job",
        ],
    )

    assert task_run.main() == 0
    assert executed == ["Unrelated_Job"]


def test_managed_dataset_diagnostic_does_not_block_selected_consumer():
    lineage_data = _unresolved_process_lineage_payload(dataset_type="managed")
    dag = task_run.JobDAG.from_jobs(["Build_Report"], [])

    task_run._validate_process_plan_safety(
        {"Build_Report"},
        dag,
        lineage_data,
    )


def test_default_plan_rejects_unresolved_process_consumer_before_sql(
    monkeypatch,
    tmp_path,
    capsys,
):
    lineage_data = _unresolved_process_lineage_payload()
    _configure_process_plan_project(
        monkeypatch,
        tmp_path,
        extracted_lineage=lineage_data,
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
        ],
    )

    assert task_run.main() == 1
    assert executed == []
    output = capsys.readouterr().out
    assert "Internal.Demo_DB.Sales_Stage" in output
    assert "not_found" in output
    assert "Build_Report" in output


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
    def recording_lock(host, port, database):
        lock_entries.append((host, port, database))
        yield

    monkeypatch.setattr(
        task_run,
        "execution_target_run_lock",
        recording_lock,
        raising=False,
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

    assert lock_entries == [
        (
            task_run.DB_ENV_CONFIG["prod"]["host"],
            task_run.DB_ENV_CONFIG["prod"]["port"],
            "demo_db",
        )
    ]
    assert executed == ["Prepare_Sales", "Build_Report"]


def test_task_run_rejects_busy_execution_target_lock_before_sql(
    monkeypatch,
    tmp_path,
    capsys,
):
    _configure_process_plan_project(monkeypatch, tmp_path)
    executed = []

    class BusyLockError(RuntimeError):
        pass

    @contextmanager
    def busy_lock(_host, _port, _database):
        raise BusyLockError("target demo_db is already executing SQL")
        yield

    monkeypatch.setattr(
        task_run, "ExecutionRunLockError", BusyLockError, raising=False
    )
    monkeypatch.setattr(
        task_run,
        "execution_target_run_lock",
        busy_lock,
        raising=False,
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
            "--job-list",
            "Prepare_Sales",
            "Build_Report",
        ],
    )

    assert task_run.main() == 1
    assert executed == []
    assert "target demo_db is already executing SQL" in capsys.readouterr().out


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
