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
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
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
    iter_project_asset_files,
    iter_project_task_files,
    job_dag_path,
    lineage_data_path,
    load_model_metadata,
    python_module_env,
)
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.execution.sql_executor import DirectSqlExecutor
from dw_refactor_agent.execution.thread_pool import shutdown_executor
from dw_refactor_agent.lineage.job_dag import (
    JobDAG,
    asset_job_dag_from_lineage,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_UNIT_RE = re.compile(
    r'"dynamic_partition\.time_unit"\s*=\s*"(\w+)"', re.IGNORECASE
)
_TABLE_PARTITION_UNITS: dict[str, str] | None = None
_TABLE_PARTITIONED_CACHE: dict[tuple[str, str], bool] = {}
_TABLE_DYNAMIC_PARTITION_CACHE: dict[tuple[str, str], bool] = {}
_SLICE_PERIOD_TO_PARTITION_UNIT = {
    "D": "DAY",
    "M": "MONTH",
    "W": "WEEK",
    "H": "HOUR",
}


def _load_partition_units(project: str) -> dict[str, str]:
    """读取每张表的分区时间单位，优先使用显式执行切片配置."""
    units: dict[str, str] = {}
    for f in iter_project_asset_files(project, "ddl", "*.sql"):
        m = _TIME_UNIT_RE.search(f.read_text(encoding=TEXT_ENCODING))
        if m:
            units[f.stem] = m.group(1).upper()

    project_execution = (PROJECT_CONFIG.get(project) or {}).get("execution")
    if not isinstance(project_execution, dict):
        project_execution = {}
    default_unit = _partition_unit_from_slice(
        project_execution.get("default_slice")
    )
    if default_unit:
        for job_name in _get_task_files(project):
            units[job_name] = default_unit

    for job_name, metadata in load_model_metadata(project).items():
        raw_execution = metadata.get("execution") or {}
        if not isinstance(raw_execution, dict):
            continue
        unit = _partition_unit_from_slice(raw_execution.get("slice"))
        if unit:
            units[job_name] = unit
    return units


def _partition_unit_from_slice(value) -> str | None:
    if not isinstance(value, dict):
        return None
    return _SLICE_PERIOD_TO_PARTITION_UNIT.get(
        str(value.get("period") or "").strip().upper()
    )


def _build_job_dag(project: str) -> JobDAG:
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
    return asset_job_dag_from_lineage(data)


def _resolve_lineage_data_file(project: str) -> Path:
    return lineage_data_path(project)


def _resolve_job_dag_file(project: str) -> Path:
    return job_dag_path(project)


def _dag_needs_refresh_for_tasks(dag: JobDAG, task_names: set[str]) -> bool:
    """Return True when a loaded DAG looks unrelated to current task names."""
    if not task_names:
        return False

    target_tables = set(dag._rev)
    if not target_tables:
        for edge in dag._edges:
            target = JobDAG._edge_table(edge.get("target"))
            if target:
                target_tables.add(target)

    if not target_tables:
        return False

    matched_targets = target_tables & task_names
    return len(matched_targets) / len(target_tables) < 0.5


def _get_task_files(project: str) -> dict[str, Path]:
    files = {}
    for f in iter_project_task_files(project, include_full_refresh=False):
        if f.stem.endswith("_full_refresh"):
            continue
        files[f.stem] = f
    return files


def _is_partitioned_table(
    db_name: str, table_name: str, mysql_cmd: list[str]
) -> bool:
    """检查目标表是否为分区表，结果按库表缓存。"""
    cache_key = (db_name, table_name)
    if cache_key in _TABLE_PARTITIONED_CACHE:
        return _TABLE_PARTITIONED_CACHE[cache_key]

    full_name = f"{db_name}.{table_name}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=f"SHOW CREATE TABLE {full_name};",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"[{table_name}] [SHOW CREATE FAIL]\n  {r.stderr.strip()}"
        )

    is_partitioned = "PARTITION BY" in r.stdout.upper()
    _TABLE_PARTITIONED_CACHE[cache_key] = is_partitioned
    _TABLE_DYNAMIC_PARTITION_CACHE[cache_key] = (
        "DYNAMIC_PARTITION.ENABLE" in r.stdout.upper()
    )
    return is_partitioned


def _is_dynamic_partition_table(
    db_name: str, table_name: str, mysql_cmd: list[str]
) -> bool:
    """检查目标表是否配置了 Doris 动态分区。"""
    cache_key = (db_name, table_name)
    if cache_key in _TABLE_DYNAMIC_PARTITION_CACHE:
        return _TABLE_DYNAMIC_PARTITION_CACHE[cache_key]

    full_name = f"{db_name}.{table_name}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=f"SHOW CREATE TABLE {full_name};",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"[{table_name}] [SHOW CREATE FAIL]\n  {r.stderr.strip()}"
        )

    upper_ddl = r.stdout.upper()
    _TABLE_PARTITIONED_CACHE[cache_key] = "PARTITION BY" in upper_ddl
    _TABLE_DYNAMIC_PARTITION_CACHE[cache_key] = (
        "DYNAMIC_PARTITION.ENABLE" in upper_ddl
    )
    return _TABLE_DYNAMIC_PARTITION_CACHE[cache_key]


def _ensure_partition(
    db_name: str, table_name: str, etl_date: str, mysql_cmd: list[str]
) -> None:
    if not _is_partitioned_table(db_name, table_name, mysql_cmd):
        return
    is_dynamic_partition = _is_dynamic_partition_table(
        db_name, table_name, mysql_cmd
    )

    raw_dt = datetime.strptime(etl_date[:10], "%Y-%m-%d")
    dt = raw_dt.date()
    full_name = f"{db_name}.{table_name}"

    time_unit = (
        _TABLE_PARTITION_UNITS.get(table_name, "DAY")
        if _TABLE_PARTITION_UNITS
        else "DAY"
    )
    if time_unit == "MONTH":
        p_name = f"p{dt.strftime('%Y%m')}"
        month_start = dt.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(
            day=1
        )
        next_val = next_month.strftime("%Y-%m-%d")
    elif time_unit == "WEEK":
        week_start = dt - timedelta(days=dt.weekday())
        p_name = f"p{week_start.strftime('%Y%m%d')}"
        next_val = (week_start + timedelta(days=7)).strftime("%Y-%m-%d")
    elif time_unit == "HOUR":
        hour_dt = raw_dt
        p_name = f"p{hour_dt.strftime('%Y%m%d%H')}"
        next_val = (hour_dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        p_name = f"p{dt.strftime('%Y%m%d')}"
        next_val = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    def run(sql):
        return subprocess.run(
            mysql_cmd + [db_name],
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
        )

    if is_dynamic_partition:
        run(
            f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'false');"
        )
    run(f"ALTER TABLE {full_name} DROP PARTITION IF EXISTS {p_name};")
    r = run(
        f'ALTER TABLE {full_name} ADD PARTITION {p_name} VALUES LESS THAN ("{next_val}");'
    )
    if is_dynamic_partition:
        run(
            f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'true');"
        )
    if r.returncode != 0:
        stderr = r.stderr.strip()
        if "already exists" not in stderr.lower():
            print(f"  [{table_name}] [PARTITION WARN] {stderr}")


def _run_job(
    etl_date: str,
    job_name: str,
    sql_file: Path,
    mysql_cmd: list[str],
    db_name: str,
    planner: ExecutionPlanner,
) -> None:
    spec = planner.task_spec(job_name, sql_file)
    for invocation in planner.plan_regular_run(spec, [etl_date]):
        _execute_invocation(
            invocation,
            mysql_cmd,
            db_name,
            full_refresh_dates=[etl_date],
        )


def _ensure_full_refresh_partitions(
    db_name: str, table_name: str, all_dates: list[str], mysql_cmd: list[str]
) -> None:
    """为全量刷新模式重建分区: 清除所有旧分区, 建单个覆盖全 ODS 范围的分区."""
    if not _is_partitioned_table(db_name, table_name, mysql_cmd):
        return
    is_dynamic_partition = _is_dynamic_partition_table(
        db_name, table_name, mysql_cmd
    )

    full_name = f"{db_name}.{table_name}"

    # 动态表重建静态验证分区前先停用调度；静态表不写动态属性。
    def run(sql):
        return subprocess.run(
            mysql_cmd + [db_name],
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
        )

    if is_dynamic_partition:
        run(
            f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'false');"
        )

    # 查询当前分区列表, 全部 DROP
    r = run("SHOW PARTITIONS FROM " + full_name)
    pnames = []
    for line in r.stdout.strip().split("\n")[1:]:
        parts = line.split("\t")
        if len(parts) >= 2:
            pnames.append(parts[1].strip())
    for p in pnames:
        run(f"ALTER TABLE {full_name} DROP PARTITION IF EXISTS {p};")

    # 3) 添加单个覆盖全日期范围的分区 (ODS max + 1, 兼顾 CURDATE 场景)
    if not all_dates:
        print(f"  [{table_name}] 跳过分区 — ODS 无数据")
        return
    last_dt = max(
        datetime.strptime(all_dates[-1], "%Y-%m-%d"),
        datetime.now(),
    ) + timedelta(days=1)
    r = run(
        f'ALTER TABLE {full_name} ADD PARTITION p_full VALUES LESS THAN ("{last_dt.strftime("%Y-%m-%d")}");'
    )
    if r.returncode != 0 and "Unknown table" not in r.stderr:
        print(f"  [{table_name}] [PARTITION WARN] {r.stderr.strip()}")


def _run_job_full_refresh(
    job_name: str,
    sql_file: Path,
    mysql_cmd: list[str],
    db_name: str,
    planner: ExecutionPlanner,
    all_dates: list[str],
) -> None:
    """全量刷新模式下的作业执行."""
    spec = planner.task_spec(job_name, sql_file)
    invocations = planner.plan_full_refresh(spec, all_dates)
    if not invocations:
        print(f"  [{job_name}] 跳过 — 无可执行切片")
        return

    for invocation in invocations:
        _execute_invocation(
            invocation,
            mysql_cmd,
            db_name,
            full_refresh_dates=all_dates,
        )


def _partition_date(value: str) -> str | None:
    match = re.match(r"^\d{4}-\d{2}-\d{2}", str(value or ""))
    return match.group(0) if match else None


def _prepare_invocation_partitions(
    invocation: TaskInvocation,
    db_name: str,
    mysql_cmd: list[str],
    full_refresh_dates: list[str],
) -> None:
    if invocation.full_refresh:
        _ensure_full_refresh_partitions(
            db_name,
            invocation.job_name,
            full_refresh_dates,
            mysql_cmd,
        )
        return

    for value in invocation.params.values():
        partition_date = _partition_date(value)
        if partition_date:
            _ensure_partition(
                db_name,
                invocation.job_name,
                partition_date,
                mysql_cmd,
            )


def _execute_invocation(
    invocation: TaskInvocation,
    mysql_cmd: list[str],
    db_name: str,
    *,
    full_refresh_dates: list[str],
) -> None:
    executor = DirectSqlExecutor(
        mysql_cmd,
        db_name,
        before_execute=lambda item: _prepare_invocation_partitions(
            item,
            db_name,
            mysql_cmd,
            full_refresh_dates,
        ),
    )
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
    args = parser.parse_args()

    project = args.project
    env = args.db_env
    cfg = PROJECT_CONFIG[project]
    db_name = cfg["db"]
    parallel = args.parallel
    if parallel < 1:
        print("错误: --parallel 必须 >= 1")
        sys.exit(1)

    global _TABLE_PARTITION_UNITS
    _TABLE_PARTITION_UNITS = _load_partition_units(project)

    if not args.full_refresh:
        if not args.etl_dates:
            parser.error("请指定 --etl-dates 或使用 --full-refresh")
        for d in args.etl_dates:
            if not _DATE_RE.match(d):
                print(f"错误: 日期格式无效 '{d}', 需要 YYYY-MM-DD")
                sys.exit(1)
    else:
        for d in args.etl_dates or []:
            if not _DATE_RE.match(d):
                print(f"错误: 日期格式无效 '{d}', 需要 YYYY-MM-DD")
                sys.exit(1)

    task_files = _get_task_files(project)
    task_names = set(task_files.keys())

    dag_path = job_dag_path(project)
    existing_dag_path = _resolve_job_dag_file(project)
    if args.refresh_dag or not existing_dag_path.exists():
        print(f"生成 DAG: {dag_path}")
        dag = _build_job_dag(project)
        dag_path.parent.mkdir(parents=True, exist_ok=True)
        dag.save(dag_path)
        print(f"  DAG 已保存: {len(dag._edges)} 条边")
    else:
        print(f"加载 DAG: {existing_dag_path}")
        dag = JobDAG.load(existing_dag_path)
        if _dag_needs_refresh_for_tasks(dag, task_names):
            print("  DAG 与当前作业不匹配, 重新生成...")
            dag = _build_job_dag(project)
            dag_path.parent.mkdir(parents=True, exist_ok=True)
            dag.save(dag_path)
            print(f"  DAG 已保存: {len(dag._edges)} 条边")

    if args.job_list is not None:
        job_set = set(args.job_list)
        missing = job_set - set(task_files.keys())
        if missing:
            print(f"错误: 以下作业不存在: {sorted(missing)}")
            sys.exit(1)
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
        all_dates = _resolve_full_refresh_dates(
            project,
            db_name,
            mysql_cmd,
            args.etl_dates,
        )
        print(f"  {len(all_dates)} 个日期")
        for job_name in exec_order:
            try:
                _run_job_full_refresh(
                    job_name,
                    task_files[job_name],
                    mysql_cmd,
                    db_name,
                    planner,
                    all_dates,
                )
            except (
                subprocess.TimeoutExpired,
                RuntimeError,
                ExecutionConfigError,
            ) as e:
                print(f"  {e}")
                sys.exit(1)
        print(f"\n{'=' * 60}")
        print(f"全部完成! 共执行 {len(exec_order)} 个作业 (全量刷新)")
        return 0

    for etl_date in args.etl_dates:
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
            )

    total_jobs = len(exec_order) * len(args.etl_dates)
    print(f"\n{'=' * 60}")
    print(f"全部完成! 共执行 {total_jobs} 个作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
