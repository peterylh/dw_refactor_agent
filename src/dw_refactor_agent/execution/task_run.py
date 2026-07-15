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
import threading
from concurrent.futures import ThreadPoolExecutor
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
    job_dag_path,
    lineage_data_path,
    python_module_env,
)
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner, TaskSpec
from dw_refactor_agent.execution.run_lock import (
    ProjectRunLockError,
    project_run_lock,
)
from dw_refactor_agent.execution.sql_executor import DirectSqlExecutor
from dw_refactor_agent.execution.thread_pool import shutdown_executor
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    short_table_name,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.job_dag import (
    JobDAG,
    job_dag_from_lineage,
)


def _build_job_dag(
    project: str,
    runnable_jobs: set[str] | None = None,
) -> JobDAG:
    lineage_path = _resolve_lineage_data_file(project)
    if not lineage_path.exists():
        print("  lineage 数据不存在, 运行 lineage_extractor 生成...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "dw_refactor_agent.lineage.lineage_extractor",
                "--project",
                project,
            ],
            check=True,
            cwd=PROJECT_ROOT,
            env=python_module_env(),
        )
        lineage_path = _resolve_lineage_data_file(project)
    data = json.loads(lineage_path.read_text(encoding=TEXT_ENCODING))
    return job_dag_from_lineage(data, runnable_jobs=runnable_jobs)


def _resolve_lineage_data_file(project: str) -> Path:
    return lineage_data_path(project)


def _resolve_job_dag_file(project: str) -> Path:
    return job_dag_path(project)


def _dag_needs_refresh_for_tasks(dag: JobDAG, task_names: set[str]) -> bool:
    """Return True when a loaded DAG looks unrelated to current task names."""
    if not task_names:
        return False

    task_keys = {identifier_match_key(name) for name in task_names}
    if dag.format_version == 2:
        dag_job_keys = {identifier_match_key(name) for name in dag.jobs}
        return dag_job_keys != task_keys

    target_tables = set(dag._rev)
    if not target_tables:
        for edge in dag._edges:
            target = JobDAG._edge_table(edge.get("target"))
            if target:
                target_tables.add(target)

    if not target_tables:
        return False

    target_keys = {identifier_match_key(name) for name in target_tables}
    matched_targets = target_keys & task_keys
    return len(matched_targets) / len(target_keys) < 0.5


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


def _validate_process_dependency_closure(
    job_set: set[str],
    dag: JobDAG,
    lineage_data: dict,
) -> None:
    """Require selected process consumers to include their resolved producer."""
    if dag.format_version != 2:
        return
    selected_job_keys = {identifier_match_key(job) for job in job_set}
    unclosed_dependencies = [
        dependency
        for dependency in dag.data_dependencies
        if identifier_match_key(dependency["downstream_job"])
        in selected_job_keys
        and identifier_match_key(dependency["upstream_job"])
        not in selected_job_keys
    ]
    if not unclosed_dependencies:
        return
    if lineage_data.get("format_version") != 2:
        raise ExecutionConfigError(
            "cannot validate --job-list process dependencies without "
            "lineage v2 table metadata; regenerate lineage"
        )

    process_tables_by_key = {
        table_identity_match_key(table["full_name"]): table["full_name"]
        for table in lineage_data.get("tables") or []
        if table.get("full_name") and table.get("dataset_type") == "process"
    }
    missing = []
    for dependency in unclosed_dependencies:
        upstream_job = dependency["upstream_job"]
        downstream_job = dependency["downstream_job"]
        for dataset in dependency["datasets"]:
            process_dataset = process_tables_by_key.get(
                table_identity_match_key(dataset)
            )
            if process_dataset:
                missing.append((upstream_job, downstream_job, process_dataset))

    if not missing:
        return
    missing.sort(
        key=lambda item: (
            identifier_match_key(item[1]),
            identifier_match_key(item[0]),
            table_identity_match_key(item[2]),
        )
    )
    details = "; ".join(
        "producer={!r}, consumer={!r}, process dataset={!r}".format(*item)
        for item in missing
    )
    raise ExecutionConfigError(
        "incomplete --job-list process-table dependency: {}".format(details)
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


def _load_lineage_data(project: str) -> dict:
    lineage_path = _resolve_lineage_data_file(project)
    if not lineage_path.exists():
        return {}
    return json.loads(lineage_path.read_text(encoding=TEXT_ENCODING))


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


def _save_job_dag(dag: JobDAG, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    dag.save(path)
    if dag.format_version == 2:
        return len(dag.data_dependencies)
    return len(dag._edges)


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
    if invocation.params:
        value_text = " " + ", ".join(
            f"{key}={value}" for key, value in invocation.params.items()
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


def _run_parallel(
    etl_date: str,
    job_set: set,
    task_files: dict[str, Path],
    in_degree: dict[str, int],
    adj: dict[str, list[str]],
    mysql_cmd: list[str],
    db_name: str,
    parallel: int,
    planner: ExecutionPlanner,
    skip_unsupported_history: bool,
    model_names_by_job: dict[str, str] | None = None,
) -> None:
    deg = dict(in_degree)
    lock = threading.Lock()
    all_done = threading.Event()
    failed = threading.Event()
    total = len(job_set)
    completed = 0

    def on_complete(job_name: str, future):
        nonlocal completed
        if failed.is_set():
            return
        exc = future.exception()
        if exc is not None:
            print(f"  [{job_name}] [FAIL] {exc}")
            failed.set()
            return
        to_submit = []
        with lock:
            completed += 1
            for dep in adj.get(job_name, []):
                deg[dep] -= 1
                if deg[dep] == 0:
                    to_submit.append(dep)
            if completed == total:
                all_done.set()
        for dep in to_submit:
            _submit_and_track(dep)

    def _submit_and_track(job_name: str):
        if failed.is_set():
            return
        fut = executor.submit(
            _run_job,
            etl_date,
            job_name,
            task_files[job_name],
            mysql_cmd,
            db_name,
            planner,
            skip_unsupported_history,
            model_names_by_job,
        )
        fut.add_done_callback(lambda f, j=job_name: on_complete(j, f))

    executor = ThreadPoolExecutor(max_workers=parallel)
    try:
        for job_name in job_set:
            if deg[job_name] == 0:
                _submit_and_track(job_name)
        while not all_done.is_set():
            if failed.wait(timeout=1.0):
                break
            all_done.wait(timeout=1.0)
    finally:
        shutdown_executor(executor)
    if failed.is_set():
        sys.exit(1)


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
        "--job-list", nargs="*", default=None, help="作业清单, 默认全部"
    )
    parser.add_argument(
        "--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys())
    )
    parser.add_argument(
        "--refresh-dag", action="store_true", help="重新生成 DAG 文件"
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

    dag_path = job_dag_path(project)
    existing_dag_path = _resolve_job_dag_file(project)
    try:
        if args.refresh_dag or not existing_dag_path.exists():
            print(f"生成 DAG: {dag_path}")
            dag = _build_job_dag(project, task_names)
            dependency_count = _save_job_dag(dag, dag_path)
            print(f"  DAG 已保存: {dependency_count} 条边")
        else:
            print(f"加载 DAG: {existing_dag_path}")
            dag = JobDAG.load(existing_dag_path)
            if _dag_needs_refresh_for_tasks(dag, task_names):
                print("  DAG 与当前作业不匹配, 重新生成...")
                dag = _build_job_dag(project, task_names)
                dependency_count = _save_job_dag(dag, dag_path)
                print(f"  DAG 已保存: {dependency_count} 条边")
    except (ExecutionConfigError, ValueError) as e:
        print(f"错误: {e}")
        return 1

    try:
        lineage_data = _load_lineage_data(project)
        model_names_by_job = _job_model_names_from_lineage(lineage_data)
    except ExecutionConfigError as e:
        print(f"错误: {e}")
        sys.exit(1)

    if args.job_list is not None:
        job_set, missing = _resolve_requested_jobs(args.job_list, task_files)
        if missing:
            print(f"错误: 以下作业不存在: {sorted(missing)}")
            sys.exit(1)
        try:
            _validate_process_dependency_closure(job_set, dag, lineage_data)
        except ExecutionConfigError as e:
            print(f"错误: {e}")
            return 1
    else:
        job_set = set(task_files.keys())

    if not job_set:
        print("没有作业需要执行")
        return 0

    try:
        exec_order = dag.topological_sort(job_set)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    print(f"作业执行顺序 ({len(exec_order)} 个):")
    for i, j in enumerate(exec_order, 1):
        print(f"  {i}. {j}")

    in_degree, adj = dag.compute_in_degree(job_set)

    mysql_cmd = get_mysql_cmd(env)
    planner = ExecutionPlanner(project)

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
            with project_run_lock(project):
                for job_name in exec_order:
                    try:
                        _run_job_full_refresh(
                            job_name,
                            task_files[job_name],
                            mysql_cmd,
                            db_name,
                            planner,
                            all_dates,
                            model_names_by_job,
                        )
                    except (
                        subprocess.TimeoutExpired,
                        RuntimeError,
                        ExecutionConfigError,
                    ) as e:
                        print(f"  {e}")
                        sys.exit(1)
        except ProjectRunLockError as e:
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
        with project_run_lock(project):
            for etl_date in regular_dates:
                print(f"\n{'=' * 60}")
                print(f"执行日期: {etl_date}  (并行度: {parallel})")
                print(f"{'=' * 60}")
                if parallel == 1:
                    for job_name in exec_order:
                        try:
                            _run_job(
                                etl_date,
                                job_name,
                                task_files[job_name],
                                mysql_cmd,
                                db_name,
                                planner,
                                args.skip_unsupported_history,
                                model_names_by_job,
                            )
                        except (
                            subprocess.TimeoutExpired,
                            RuntimeError,
                            ExecutionConfigError,
                        ) as e:
                            print(f"  {e}")
                            sys.exit(1)
                else:
                    _run_parallel(
                        etl_date,
                        job_set,
                        task_files,
                        in_degree,
                        adj,
                        mysql_cmd,
                        db_name,
                        parallel,
                        planner,
                        args.skip_unsupported_history,
                        model_names_by_job,
                    )
    except ProjectRunLockError as e:
        print(f"错误: {e}")
        return 1

    total_jobs = planned_invocation_count
    print(f"\n{'=' * 60}")
    print(f"全部完成! 共执行 {total_jobs} 个作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
