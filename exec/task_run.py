#!/usr/bin/env python3
"""
按照依赖顺序执行 ETL 作业.

用法:
    python exec/task_run.py --project shop --etl-dates 2025-01-01
    python exec/task_run.py --project shop --etl-dates 2025-01-01 2025-01-02 --job-list dwd_customer dws_store_sales_daily
    python exec/task_run.py --project olist --etl-dates 2025-01-01 --db-env prod
    python exec/task_run.py --project shop --etl-dates 2025-01-01 --refresh-dag
"""

import argparse
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lineage.job_dag import JobDAG
from config import PROJECT_CONFIG, DB_ENV_CONFIG, get_mysql_cmd

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_UNIT_RE = re.compile(r'"dynamic_partition\.time_unit"\s*=\s*"(\w+)"', re.IGNORECASE)
_TABLE_PARTITION_UNITS: dict[str, str] | None = None


def _load_partition_units(project: str) -> dict[str, str]:
    """从 DDL 文件中读取每张表的 dynamic_partition.time_unit."""
    ddl_dir = _root / PROJECT_CONFIG[project]["dir"] / "ddl"
    units: dict[str, str] = {}
    for f in sorted(ddl_dir.glob("*.sql")):
        m = _TIME_UNIT_RE.search(f.read_text(encoding="utf-8"))
        if m:
            units[f.stem] = m.group(1).upper()
    return units


def _build_job_dag(project: str) -> JobDAG:
    lineage_path = _root / "lineage" / f"lineage_data_{project}.json"
    if not lineage_path.exists():
        print(f"  lineage 数据不存在, 运行 lineage_extractor 生成...")
        subprocess.run(
            [sys.executable, str(_root / "lineage" / "lineage_extractor.py"),
             "--project", project],
            check=True, cwd=_root,
        )
    data = json.loads(lineage_path.read_text(encoding="utf-8"))
    table_edges = []
    seen = set()
    for e in data.get("edges", []):
        src = e["source"].rsplit(".", 1)[0]
        tgt = e["target"].rsplit(".", 1)[0]
        if src == tgt:
            continue
        key = (src, tgt)
        if key not in seen:
            seen.add(key)
            table_edges.append({"source": src, "target": tgt})
    return JobDAG(table_edges)


def _get_task_files(project: str) -> dict[str, Path]:
    tasks_dir = _root / PROJECT_CONFIG[project]["dir"] / "tasks"
    return {f.stem: f for f in sorted(tasks_dir.glob("*.sql"))}


def _ensure_partition(db_name: str, table_name: str, etl_date: str,
                      mysql_cmd: list[str]) -> None:
    dt = datetime.strptime(etl_date, "%Y-%m-%d").date()
    full_name = f"{db_name}.{table_name}"

    time_unit = _TABLE_PARTITION_UNITS.get(table_name, "DAY") if _TABLE_PARTITION_UNITS else "DAY"
    if time_unit == "MONTH":
        p_name = f"p{dt.strftime('%Y%m')}"
        month_start = dt.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        next_val = next_month.strftime("%Y-%m-%d")
    else:
        p_name = f"p{dt.strftime('%Y%m%d')}"
        next_val = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    drop_sql = f"ALTER TABLE {full_name} DROP PARTITION IF EXISTS {p_name};\n"
    add_sql = f"ALTER TABLE {full_name} ADD PARTITION {p_name} VALUES LESS THAN (\"{next_val}\");"

    r = subprocess.run(
        mysql_cmd + [db_name],
        input=drop_sql + add_sql,
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        stderr = r.stderr.strip()
        if "already exists" not in stderr.lower():
            print(f"  [{table_name}] [PARTITION WARN] {stderr}")


def _run_job(etl_date: str, job_name: str, sql_file: Path,
             mysql_cmd: list[str], db_name: str) -> None:
    _ensure_partition(db_name, job_name, etl_date, mysql_cmd)
    sql_text = sql_file.read_text(encoding="utf-8")
    full_sql = f"SET @etl_date = '{etl_date}';\n{sql_text}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=full_sql, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"[{job_name}] [FAIL]\n  {r.stderr.strip()}")
    print(f"  [{job_name}] [OK]")


def _run_parallel(etl_date: str, job_set: set, task_files: dict[str, Path],
                  in_degree: dict[str, int], adj: dict[str, list[str]],
                  mysql_cmd: list[str], db_name: str, parallel: int) -> None:
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
            _run_job, etl_date, job_name, task_files[job_name], mysql_cmd, db_name
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
        executor.shutdown(wait=False, cancel_futures=True)
    if failed.is_set():
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="按依赖顺序执行 ETL 作业")
    parser.add_argument("--project", required=True, choices=list(PROJECT_CONFIG.keys()))
    parser.add_argument("--etl-dates", required=True, nargs="+", help="ETL 日期 (YYYY-MM-DD)")
    parser.add_argument("--job-list", nargs="*", default=None, help="作业清单, 默认全部")
    parser.add_argument("--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys()))
    parser.add_argument("--refresh-dag", action="store_true", help="重新生成 DAG 文件")
    parser.add_argument("--parallel", type=int, default=1,
                        help="并行度, 默认 1 (串行)")
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

    for d in args.etl_dates:
        if not _DATE_RE.match(d):
            print(f"错误: 日期格式无效 '{d}', 需要 YYYY-MM-DD")
            sys.exit(1)

    dag_path = _root / "lineage" / f"job_dag_{project}.json"
    if args.refresh_dag or not dag_path.exists():
        print(f"生成 DAG: {dag_path}")
        dag = _build_job_dag(project)
        dag.save(dag_path)
        print(f"  DAG 已保存: {len(dag._edges)} 条边")
    else:
        print(f"加载 DAG: {dag_path}")
        dag = JobDAG.load(dag_path)

    task_files = _get_task_files(project)
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
    for etl_date in args.etl_dates:
        print(f"\n{'=' * 60}")
        print(f"执行日期: {etl_date}  (并行度: {parallel})")
        print(f"{'=' * 60}")
        if parallel == 1:
            for job_name in exec_order:
                try:
                    _run_job(etl_date, job_name, task_files[job_name], mysql_cmd, db_name)
                except (subprocess.TimeoutExpired, RuntimeError) as e:
                    print(f"  {e}")
                    sys.exit(1)
        else:
            _run_parallel(etl_date, job_set, task_files, in_degree, adj,
                          mysql_cmd, db_name, parallel)

    total_jobs = len(exec_order) * len(args.etl_dates)
    print(f"\n{'=' * 60}")
    print(f"全部完成! 共执行 {total_jobs} 个作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
