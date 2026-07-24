#!/usr/bin/env python3
"""
按照依赖顺序执行 ETL 作业.

用法:
    python -m dw_refactor_agent.execution.task_run --project shop --etl-dates 2025-01-01
    python -m dw_refactor_agent.execution.task_run --project shop --full-refresh
    python -m dw_refactor_agent.execution.task_run --project finance_analytics --etl-dates 2025-01-15 --db-env prod
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.config import (
    DB_ENV_CONFIG,
    PROJECT_CONFIG,
    PROJECT_ROOT,
    TEXT_ENCODING,
    get_model_names_by_layer,
    get_mysql_cmd,
    iter_project_task_files,
    lineage_data_path,
    python_module_env,
)
from dw_refactor_agent.execution.dag_executor import execute_dag
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner, TaskSpec
from dw_refactor_agent.execution.run_lock import (
    ExecutionRunLockError,
    execution_target_run_lock,
)
from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
)
from dw_refactor_agent.execution.sql_executor import DirectSqlExecutor
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    short_table_name,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.job_dag import (
    JobDAG,
    job_dag_from_lineage,
)
from dw_refactor_agent.lineage.schedule_inference import (
    validate_schedule_against_lineage,
)


def _refresh_lineage_and_load_schedule(
    project: str,
    runnable_jobs: set[str],
    *,
    no_cache: bool,
) -> tuple[dict, ScheduleGraph, JobDAG, list[dict]]:
    """Refresh lineage, load the trusted DAG, and validate their agreement."""
    lineage_path = _resolve_lineage_data_file(project)
    command = [
        sys.executable,
        "-m",
        "dw_refactor_agent.lineage.lineage_extractor",
        "--project",
        project,
        "--output",
        str(lineage_path),
    ]
    if no_cache:
        command.append("--no-cache")
    print(
        "刷新 lineage 并校验可信 Schedule DAG"
        + (" (禁用 task cache)" if no_cache else " (使用 task cache)")
        + f": {project}"
    )
    try:
        subprocess.run(
            command,
            check=True,
            cwd=PROJECT_ROOT,
            env=python_module_env(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExecutionConfigError(
            f"lineage extraction failed for project {project!r}: {exc}"
        ) from exc

    data = json.loads(lineage_path.read_text(encoding=TEXT_ENCODING))
    if data.get("format_version") != 2:
        raise ExecutionConfigError(
            "lineage extractor did not produce a version 2 payload"
        )
    lineage_dag = job_dag_from_lineage(data, runnable_jobs=runnable_jobs)
    schedule = ScheduleGraph.load_for_project(project)
    _validate_schedule_job_universe(schedule, runnable_jobs)
    diagnostics = validate_schedule_against_lineage(schedule, data)
    return data, schedule, lineage_dag, diagnostics


def _validate_schedule_job_universe(
    schedule: ScheduleGraph, runnable_jobs: set[str]
) -> None:
    runnable_by_key = {identifier_match_key(job): job for job in runnable_jobs}
    schedule_by_key = {identifier_match_key(job): job for job in schedule.jobs}
    missing_sql = sorted(
        schedule_by_key[key]
        for key in set(schedule_by_key) - set(runnable_by_key)
    )
    unscheduled = sorted(
        runnable_by_key[key]
        for key in set(runnable_by_key) - set(schedule_by_key)
    )
    if missing_sql or unscheduled:
        details = []
        if missing_sql:
            details.append(f"schedule Jobs without task SQL: {missing_sql!r}")
        if unscheduled:
            details.append(f"task Jobs absent from schedule: {unscheduled!r}")
        raise ExecutionConfigError("; ".join(details))


def _resolve_lineage_data_file(project: str) -> Path:
    return lineage_data_path(project)


def _resolve_requested_jobs(
    requested_jobs: list[str], task_files: dict[str, Path]
) -> tuple[set[str], list[str]]:
    task_name_by_key = {
        identifier_match_key(job_name): job_name for job_name in task_files
    }
    resolved = set()
    missing = []
    for requested_job in requested_jobs:
        job_name = task_name_by_key.get(identifier_match_key(requested_job))
        if job_name is None:
            missing.append(requested_job)
        else:
            resolved.add(job_name)
    return resolved, sorted(set(missing), key=identifier_match_key)


def _validate_process_plan_safety(
    job_set: set[str],
    dag: JobDAG,
    lineage_data: dict,
) -> None:
    """Fail closed for incomplete process or cross-Job temporary inputs."""
    if dag.format_version != 2:
        return
    if lineage_data.get("format_version") != 2:
        raise ExecutionConfigError(
            "cannot validate process-table execution safety without "
            "lineage v2 table metadata; regenerate lineage"
        )

    selected_job_keys = {identifier_match_key(job) for job in job_set}
    restricted_tables_by_key = {
        table_identity_match_key(table["full_name"]): (
            table["full_name"],
            table.get("dataset_type"),
        )
        for table in lineage_data.get("tables") or []
        if table.get("full_name")
        and table.get("dataset_type") in {"process", "temporary"}
    }

    missing_resolved_producers = []
    for dependency in dag.data_dependencies:
        upstream_job = dependency["upstream_job"]
        downstream_job = dependency["downstream_job"]
        if (
            identifier_match_key(downstream_job) not in selected_job_keys
            or identifier_match_key(upstream_job) in selected_job_keys
        ):
            continue
        for dataset in dependency["datasets"]:
            restricted_dataset = restricted_tables_by_key.get(
                table_identity_match_key(dataset)
            )
            if restricted_dataset:
                missing_resolved_producers.append(
                    (
                        upstream_job,
                        downstream_job,
                        restricted_dataset[0],
                        restricted_dataset[1],
                    )
                )

    unresolved_producers = []
    for diagnostic in lineage_data.get("diagnostics") or []:
        if diagnostic.get("code") != "UNRESOLVED_DATASET_PRODUCER":
            continue
        restricted_dataset = restricted_tables_by_key.get(
            table_identity_match_key(diagnostic.get("dataset"))
        )
        if not restricted_dataset:
            continue
        selected_consumers = [
            consumer
            for consumer in diagnostic.get("consumer_jobs") or []
            if identifier_match_key(consumer) in selected_job_keys
        ]
        if not selected_consumers:
            continue
        unresolved_producers.append(
            (
                restricted_dataset[0],
                restricted_dataset[1],
                diagnostic.get("reason"),
                selected_consumers,
                list(diagnostic.get("candidate_producer_jobs") or []),
            )
        )

    if not missing_resolved_producers and not unresolved_producers:
        return
    missing_resolved_producers.sort(
        key=lambda item: (
            identifier_match_key(item[1]),
            identifier_match_key(item[0]),
            table_identity_match_key(item[2]),
            item[3] or "",
        )
    )
    unresolved_producers.sort(
        key=lambda item: (
            table_identity_match_key(item[0]),
            item[1] or "",
            item[2] or "",
            tuple(identifier_match_key(job) for job in item[3]),
            tuple(identifier_match_key(job) for job in item[4]),
        )
    )
    details = [
        "producer={!r}, consumer={!r}, dataset={!r}, type={!r}".format(*item)
        for item in missing_resolved_producers
    ]
    details.extend(
        "unresolved dataset={!r}, type={!r}, reason={!r}, "
        "consumer jobs={!r}, candidate producer jobs={!r}".format(*item)
        for item in unresolved_producers
    )
    raise ExecutionConfigError(
        "unsafe process/temporary execution plan: {}".format(
            "; ".join(details)
        )
    )


def _job_model_names_from_lineage(lineage_data: dict) -> dict[str, str]:
    if lineage_data.get("format_version") != 2:
        return {}
    managed_table_keys = {
        table_identity_match_key(table.get("full_name"))
        for table in lineage_data.get("tables") or []
        if table.get("full_name") and table.get("dataset_type") == "managed"
    }
    model_names = {}
    for job in lineage_data.get("jobs") or []:
        managed_outputs = [
            output
            for output in job.get("outputs") or []
            if table_identity_match_key(output) in managed_table_keys
        ]
        if len(managed_outputs) > 1:
            raise ExecutionConfigError(
                f"[{job.get('name')}] has multiple managed outputs; "
                "execution model target is ambiguous: "
                f"{sorted(managed_outputs)!r}"
            )
        if managed_outputs:
            model_names[identifier_match_key(job.get("name"))] = (
                short_table_name(managed_outputs[0])
            )
    return model_names


def _task_spec(
    planner: ExecutionPlanner,
    job_name: str,
    sql_file: Path,
    model_names_by_job: dict[str, str] | None,
) -> TaskSpec:
    model_name = (model_names_by_job or {}).get(identifier_match_key(job_name))
    return planner.task_spec(
        job_name,
        sql_file,
        model_name=model_name,
    )


def _get_task_files(project: str) -> dict[str, Path]:
    files = {}
    for f in iter_project_task_files(project, include_full_refresh=False):
        files[f.stem] = f
    return files


def _run_job(
    etl_date: str,
    job_name: str,
    sql_file: Path,
    mysql_cmd: list[str],
    db_name: str,
    planner: ExecutionPlanner,
    skip_unsupported_history: bool = False,
    model_names_by_job: dict[str, str] | None = None,
) -> None:
    spec = _task_spec(
        planner,
        job_name,
        sql_file,
        model_names_by_job,
    )
    invocations = _plan_regular_invocations(
        planner,
        spec,
        etl_date,
        skip_unsupported_history=skip_unsupported_history,
    )
    if not invocations:
        print(f"  [{job_name}] 跳过 — 不支持非当天历史回放")
        return
    for invocation in invocations:
        _execute_invocation(
            invocation,
            mysql_cmd,
            db_name,
        )


def _run_job_full_refresh(
    job_name: str,
    sql_file: Path,
    mysql_cmd: list[str],
    db_name: str,
    planner: ExecutionPlanner,
    all_dates: list[str],
    model_names_by_job: dict[str, str] | None = None,
) -> None:
    """全量刷新模式下的作业执行."""
    spec = _task_spec(
        planner,
        job_name,
        sql_file,
        model_names_by_job,
    )
    invocations = planner.plan_full_refresh(spec, all_dates)
    if not invocations:
        print(f"  [{job_name}] 跳过 — 无可执行切片")
        return

    for invocation in invocations:
        _execute_invocation(
            invocation,
            mysql_cmd,
            db_name,
        )


def _plan_regular_invocations(
    planner: ExecutionPlanner,
    spec: TaskSpec,
    etl_date: str,
    *,
    skip_unsupported_history: bool,
) -> list[TaskInvocation]:
    if (
        skip_unsupported_history
        and not spec.historical_replay_supported
        and etl_date != date.today().isoformat()
    ):
        return []
    return planner.plan_regular_run(spec, [etl_date])


def _validate_execution_plan(
    exec_order: list[str],
    task_files: dict[str, Path],
    planner: ExecutionPlanner,
    etl_dates: list[str],
    *,
    full_refresh: bool,
    skip_unsupported_history: bool = False,
    model_names_by_job: dict[str, str] | None = None,
) -> int:
    """Validate every job/date combination before the first database write."""
    invocation_count = 0
    for job_name in exec_order:
        spec = _task_spec(
            planner,
            job_name,
            task_files[job_name],
            model_names_by_job,
        )
        if full_refresh:
            invocation_count += len(planner.plan_full_refresh(spec, etl_dates))
            continue
        for etl_date in etl_dates:
            invocation_count += len(
                _plan_regular_invocations(
                    planner,
                    spec,
                    etl_date,
                    skip_unsupported_history=skip_unsupported_history,
                )
            )
    return invocation_count


def _execute_invocation(
    invocation: TaskInvocation,
    mysql_cmd: list[str],
    db_name: str,
) -> None:
    executor = DirectSqlExecutor(mysql_cmd, db_name)
    executor.execute(invocation)
    value_text = ""
    if invocation.public_session_params:
        value_text = " " + ", ".join(
            f"{key}={value}"
            for key, value in invocation.public_session_params.items()
        )
    print(
        f"  [{invocation.job_name}] [OK] "
        f"({invocation.strategy}, full_refresh={int(invocation.full_refresh)}"
        f"{value_text})"
    )


def _discover_ods_dates(
    project: str, db_name: str, mysql_cmd: list[str]
) -> list[str]:
    """从 ODS 表发现所有日期."""
    ods_model_tables = set(get_model_names_by_layer(project, "ODS"))
    r = subprocess.run(
        mysql_cmd + [db_name],
        input="SHOW TABLES",
        capture_output=True,
        text=True,
        timeout=60,
    )
    tables = [
        line.strip()
        for line in r.stdout.strip().split("\n")[1:]
        if line.strip()
    ]
    ods_tables = [t for t in tables if t in ods_model_tables]
    all_dates: set[str] = set()
    for tbl in ods_tables:
        r = subprocess.run(
            mysql_cmd + [db_name],
            input=f"SELECT DISTINCT DATE(load_time) AS d FROM {db_name}.{tbl} ORDER BY d",
            capture_output=True,
            text=True,
            timeout=120,
        )
        dates = [
            line.strip()
            for line in r.stdout.strip().split("\n")[1:]
            if line.strip()
        ]
        all_dates.update(dates)
    return sorted(all_dates)


def _resolve_full_refresh_dates(
    project: str,
    db_name: str,
    mysql_cmd: list[str],
    etl_dates: list[str] | None,
) -> list[str]:
    """Resolve slice values used by full-refresh planning."""
    if etl_dates:
        print("使用指定日期切片...")
        return list(dict.fromkeys(etl_dates))
    execution = (PROJECT_CONFIG.get(project) or {}).get("execution") or {}
    if execution.get("require_explicit_etl_dates") is True:
        raise ExecutionConfigError(
            f"[{project}] full refresh requires explicit --etl-dates; "
            "ODS load_time is an ingestion timestamp, not a business date"
        )
    print("发现 ODS 日期分区...")
    return _discover_ods_dates(project, db_name, mysql_cmd)


def _run_scheduled_jobs(
    job_set: set[str],
    dependencies: dict[str, list[str]],
    exec_order: list[str],
    run_job,
    *,
    parallel: int,
) -> bool:
    results = execute_dag(
        job_set,
        dependencies,
        run_job,
        parallel=parallel,
        order=exec_order,
    )
    success = True
    for job_name in exec_order:
        result = results[job_name]
        if result.status == "failed":
            success = False
            print(f"  [{job_name}] [FAIL] {result.error}")
        elif result.status == "blocked":
            success = False
            print(
                f"  [{job_name}] [BLOCKED] upstream failed: "
                f"{list(result.blocked_by)!r}"
            )
    return success


def main():
    parser = argparse.ArgumentParser(description="按依赖顺序执行 ETL 作业")
    parser.add_argument(
        "--project", required=True, choices=list(PROJECT_CONFIG.keys())
    )
    parser.add_argument(
        "--etl-dates", nargs="*", default=None, help="ETL 日期 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--etl-lookback-months",
        type=int,
        default=None,
        help="展开截至 --etl-end-date 向前 N 个日历月的闭区间",
    )
    parser.add_argument(
        "--etl-end-date",
        default=None,
        help="日期窗口结束日 (YYYY-MM-DD), 默认当天",
    )
    parser.add_argument(
        "--full-refresh", action="store_true", help="全量刷新模式"
    )
    parser.add_argument(
        "--job-list",
        nargs="*",
        default=None,
        help=(
            "作业清单, 默认全部; process consumer 必须包含已解析 producer, "
            "未解析 producer 会阻止执行"
        ),
    )
    parser.add_argument(
        "--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys())
    )
    parser.add_argument(
        "--refresh-lineage",
        "--refresh-dag",
        dest="refresh_dag",
        action="store_true",
        help="强制禁用 task cache 刷新当前 SQL lineage",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="并行度, 默认 1 (串行)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="仅构建并校验完整执行计划，不执行 SQL",
    )
    parser.add_argument(
        "--skip-unsupported-history",
        action="store_true",
        help="历史补跑时跳过不支持非当天回放的 current-state 作业",
    )
    args = parser.parse_args()

    project = args.project
    env = args.db_env
    cfg = PROJECT_CONFIG[project]
    db_name = cfg["db"]
    parallel = args.parallel
    if parallel < 1:
        print("错误: --parallel 必须 >= 1")
        sys.exit(1)

    try:
        etl_dates = resolve_etl_dates(
            args.etl_dates,
            lookback_months=args.etl_lookback_months,
            end_date=args.etl_end_date,
        )
    except ValueError as e:
        parser.error(str(e))

    if not args.full_refresh and not etl_dates and not args.validate_only:
        parser.error("请指定 --etl-dates 或使用 --full-refresh")
    if args.full_refresh and args.skip_unsupported_history:
        parser.error("--skip-unsupported-history 仅用于非全量历史补跑")

    task_files = _get_task_files(project)
    task_names = set(task_files.keys())

    try:
        (
            lineage_data,
            schedule,
            lineage_dag,
            schedule_diagnostics,
        ) = _refresh_lineage_and_load_schedule(
            project,
            task_names,
            no_cache=args.refresh_dag,
        )
    except (ExecutionConfigError, ScheduleContractError, ValueError) as e:
        print(f"错误: {e}")
        return 1

    for diagnostic in schedule_diagnostics:
        if diagnostic.get("severity") != "WARNING":
            continue
        print(
            "警告: {code}: {message}".format(
                code=diagnostic.get("code"),
                message=diagnostic.get("message"),
            )
        )

    task_file_by_key = {
        identifier_match_key(job): path for job, path in task_files.items()
    }
    task_files = {
        job: task_file_by_key[identifier_match_key(job)]
        for job in schedule.jobs
    }

    try:
        model_names_by_job = _job_model_names_from_lineage(lineage_data)
    except ExecutionConfigError as e:
        print(f"错误: {e}")
        sys.exit(1)

    if args.job_list is not None:
        job_set, missing = _resolve_requested_jobs(args.job_list, task_files)
        if missing:
            print(f"错误: 以下作业不存在: {sorted(missing)}")
            sys.exit(1)
    else:
        job_set = set(task_files.keys())

    try:
        _validate_process_plan_safety(job_set, lineage_dag, lineage_data)
    except ExecutionConfigError as e:
        print(f"错误: {e}")
        return 1

    if not job_set:
        print("没有作业需要执行")
        return 0

    try:
        exec_order = schedule.topological_sort(job_set)
    except (ScheduleContractError, ValueError) as e:
        print(f"错误: {e}")
        sys.exit(1)

    omitted_upstreams = schedule.omitted_upstreams(job_set)
    for job_name, upstreams in omitted_upstreams.items():
        print(
            f"提示: --job-list 精确子图省略 {job_name} 的调度上游: "
            f"{upstreams!r}"
        )

    print(f"作业执行顺序 ({len(exec_order)} 个):")
    for i, j in enumerate(exec_order, 1):
        print(f"  {i}. {j}")

    job_dependencies = schedule.selected_dependencies(job_set)

    mysql_cmd = get_mysql_cmd(env)
    execution_target = (
        DB_ENV_CONFIG[env]["host"],
        DB_ENV_CONFIG[env]["port"],
        db_name,
    )
    planner = ExecutionPlanner(project, db_env=env)

    if args.full_refresh:
        print(f"\n{'=' * 60}")
        print("全量刷新模式 (按 DAG 拓扑执行)")
        print(f"{'=' * 60}")
        if args.validate_only and etl_dates is None:
            all_dates = []
        else:
            try:
                all_dates = _resolve_full_refresh_dates(
                    project,
                    db_name,
                    mysql_cmd,
                    etl_dates,
                )
            except ExecutionConfigError as e:
                print(f"  {e}")
                sys.exit(1)
        print(f"  {len(all_dates)} 个日期")
        try:
            _validate_execution_plan(
                exec_order,
                task_files,
                planner,
                all_dates,
                full_refresh=True,
                model_names_by_job=model_names_by_job,
            )
        except ExecutionConfigError as e:
            print(f"  {e}")
            sys.exit(1)
        if args.validate_only:
            print("执行计划校验通过，未执行 SQL")
            return 0
        try:
            with execution_target_run_lock(*execution_target):
                completed = _run_scheduled_jobs(
                    job_set,
                    job_dependencies,
                    exec_order,
                    lambda job_name: _run_job_full_refresh(
                        job_name,
                        task_files[job_name],
                        mysql_cmd,
                        db_name,
                        planner,
                        all_dates,
                        model_names_by_job,
                    ),
                    parallel=parallel,
                )
                if not completed:
                    return 1
        except ExecutionRunLockError as e:
            print(f"错误: {e}")
            return 1
        print(f"\n{'=' * 60}")
        print(f"全部完成! 共执行 {len(exec_order)} 个作业 (全量刷新)")
        return 0

    regular_dates = etl_dates or []
    try:
        planned_invocation_count = _validate_execution_plan(
            exec_order,
            task_files,
            planner,
            regular_dates,
            full_refresh=False,
            skip_unsupported_history=args.skip_unsupported_history,
            model_names_by_job=model_names_by_job,
        )
    except ExecutionConfigError as e:
        print(f"  {e}")
        sys.exit(1)
    if args.validate_only:
        print("执行计划校验通过，未执行 SQL")
        return 0

    try:
        with execution_target_run_lock(*execution_target):
            for etl_date in regular_dates:
                print(f"\n{'=' * 60}")
                print(f"执行日期: {etl_date}  (并行度: {parallel})")
                print(f"{'=' * 60}")
                completed = _run_scheduled_jobs(
                    job_set,
                    job_dependencies,
                    exec_order,
                    lambda job_name, etl_date=etl_date: _run_job(
                        etl_date,
                        job_name,
                        task_files[job_name],
                        mysql_cmd,
                        db_name,
                        planner,
                        args.skip_unsupported_history,
                        model_names_by_job,
                    ),
                    parallel=parallel,
                )
                if not completed:
                    return 1
    except ExecutionRunLockError as e:
        print(f"错误: {e}")
        return 1

    total_jobs = planned_invocation_count
    print(f"\n{'=' * 60}")
    print(f"全部完成! 共执行 {total_jobs} 个作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
