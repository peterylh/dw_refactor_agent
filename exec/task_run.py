#!/usr/bin/env python3
"""
按照依赖顺序执行 ETL 作业.

用法:
    python exec/task_run.py --project shop --etl-dates 2025-01-01
    python exec/task_run.py --project shop --etl-dates 2025-01-01 2025-01-02 --job-list dwd_customer dws_store_sales_daily
    python exec/task_run.py --project shop --full-refresh
    python exec/task_run.py --project finance_analytics --etl-dates 2025-01-15 --db-env prod
    python exec/task_run.py --project shop --etl-dates 2025-01-01 --refresh-dag
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

import yaml

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lineage.job_dag import JobDAG
from config import (
    PROJECT_CONFIG,
    DB_ENV_CONFIG,
    get_model_names_by_layer,
    get_mysql_cmd,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_UNIT_RE = re.compile(r'"dynamic_partition\.time_unit"\s*=\s*"(\w+)"', re.IGNORECASE)
_TABLE_PARTITION_UNITS: dict[str, str] | None = None
_TABLE_PARTITIONED_CACHE: dict[tuple[str, str], bool] = {}
_SCHEMA_CONFIG_CACHE: dict[str, dict[str, str]] = {}


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
        src = JobDAG._edge_table(e.get("source"))
        tgt = JobDAG._edge_table(e.get("target"))
        if not src or not tgt or src == tgt:
            continue
        key = (src, tgt)
        if key not in seen:
            seen.add(key)
            table_edges.append({"source": src, "target": tgt})
    return JobDAG(table_edges)


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
    tasks_dir = _root / PROJECT_CONFIG[project]["dir"] / "tasks"
    files = {}
    for f in sorted(tasks_dir.glob("*.sql")):
        if f.stem.endswith("_full_refresh"):
            continue
        files[f.stem] = f
    return files


def _get_full_refresh_path(task_dir: Path, job_name: str) -> Path | None:
    full_dir = task_dir / "full_refresh"
    if not full_dir.exists():
        return None
    companion = full_dir / f"{job_name}_full_refresh.sql"
    return companion if companion.exists() else None


def _is_partitioned_table(db_name: str, table_name: str, mysql_cmd: list[str]) -> bool:
    """检查目标表是否为分区表，结果按库表缓存。"""
    cache_key = (db_name, table_name)
    if cache_key in _TABLE_PARTITIONED_CACHE:
        return _TABLE_PARTITIONED_CACHE[cache_key]

    full_name = f"{db_name}.{table_name}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=f"SHOW CREATE TABLE {full_name};",
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"[{table_name}] [SHOW CREATE FAIL]\n  {r.stderr.strip()}")

    is_partitioned = "PARTITION BY" in r.stdout.upper()
    _TABLE_PARTITIONED_CACHE[cache_key] = is_partitioned
    return is_partitioned


def _ensure_partition(db_name: str, table_name: str, etl_date: str,
                      mysql_cmd: list[str]) -> None:
    if not _is_partitioned_table(db_name, table_name, mysql_cmd):
        return

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

    run = lambda sql: subprocess.run(
        mysql_cmd + [db_name], input=sql,
        capture_output=True, text=True, timeout=30,
    )
    run(f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'false');")
    run(f"ALTER TABLE {full_name} DROP PARTITION IF EXISTS {p_name};")
    r = run(f"ALTER TABLE {full_name} ADD PARTITION {p_name} VALUES LESS THAN (\"{next_val}\");")
    run(f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'true');")
    if r.returncode != 0:
        stderr = r.stderr.strip()
        if "already exists" not in stderr.lower():
            print(f"  [{table_name}] [PARTITION WARN] {stderr}")


def _run_job(etl_date: str, job_name: str, sql_file: Path,
             mysql_cmd: list[str], db_name: str) -> None:
    _ensure_partition(db_name, job_name, etl_date, mysql_cmd)
    sql_text = sql_file.read_text(encoding="utf-8")
    full_sql = f"SET @etl_date = '{etl_date}';\nSET @full_refresh = 0;\n{sql_text}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=full_sql, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"[{job_name}] [FAIL]\n  {r.stderr.strip()}")
    print(f"  [{job_name}] [OK]")


def _load_schema(project: str) -> dict:
    """加载表级模型配置, 兼容旧 schema.yaml."""
    global _SCHEMA_CONFIG_CACHE
    if project in _SCHEMA_CONFIG_CACHE:
        return _SCHEMA_CONFIG_CACHE[project]

    project_dir = _root / PROJECT_CONFIG[project]["dir"]
    models_dir = project_dir / "models"
    if models_dir.exists():
        config = {}
        for model_path in sorted(models_dir.glob("*.yaml")):
            raw = yaml.safe_load(model_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                continue
            name = raw.get("name") or model_path.stem
            mat = raw.get("config", {}).get("materialized", "incremental")
            config[name] = mat
        _SCHEMA_CONFIG_CACHE[project] = config
        print(f"  加载 models/: {len(config)} 个模型")
        return config

    schema_path = project_dir / "schema.yaml"
    if not schema_path.exists():
        print(f"  未找到 models/ 或 schema.yaml, 使用默认配置 (incremental)")
        _SCHEMA_CONFIG_CACHE[project] = {}
        return {}
    with open(schema_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    config = {}
    for model in raw.get("models", []):
        name = model["name"]
        mat = model.get("config", {}).get("materialized", "incremental")
        config[name] = mat
    _SCHEMA_CONFIG_CACHE[project] = config
    print(f"  加载 schema.yaml: {len(config)} 个模型")
    return config


def _get_materialized(schema: dict, job_name: str) -> str:
    return schema.get(job_name, "incremental")


def _ensure_full_refresh_partitions(db_name: str, table_name: str,
                                    all_dates: list[str],
                                    mysql_cmd: list[str]) -> None:
    """为全量刷新模式重建分区: 清除所有旧分区, 建单个覆盖全 ODS 范围的分区."""
    if not _is_partitioned_table(db_name, table_name, mysql_cmd):
        return

    full_name = f"{db_name}.{table_name}"

    # 1) 禁用动态分区
    run = lambda sql: subprocess.run(
        mysql_cmd + [db_name], input=sql,
        capture_output=True, text=True, timeout=30,
    )
    run(f"ALTER TABLE {full_name} SET ('dynamic_partition.enable' = 'false');")

    # 2) 查询当前分区列表, 全部 DROP
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
        f"ALTER TABLE {full_name} ADD PARTITION p_full VALUES LESS THAN (\"{last_dt.strftime('%Y-%m-%d')}\");"
    )
    if r.returncode != 0 and "Unknown table" not in r.stderr:
        print(f"  [{table_name}] [PARTITION WARN] {r.stderr.strip()}")


def _run_job_full_refresh(job_name: str, sql_file: Path,
                          mysql_cmd: list[str], db_name: str,
                          schema: dict, all_dates: list[str]) -> None:
    """全量刷新模式下的作业执行."""
    materialized = _get_materialized(schema, job_name)
    task_dir = sql_file.parent

    if materialized == 'snapshot':
        companion = _get_full_refresh_path(task_dir, job_name)
        if companion:
            _ensure_full_refresh_partitions(db_name, job_name, all_dates, mysql_cmd)
            sql_text = companion.read_text(encoding="utf-8")
            full_sql = f"SET @full_refresh = 1;\n{sql_text}"
            r = subprocess.run(
                mysql_cmd + [db_name],
                input=full_sql, capture_output=True, text=True, timeout=600,
            )
            if r.returncode != 0:
                raise RuntimeError(f"[{job_name}] [FAIL]\n  {r.stderr.strip()}")
            print(f"  [{job_name}] [OK] (full-refresh companion)")
            return
        else:
            print(f"  [{job_name}] 未找到伴生文件, 按逐日模式执行 ({len(all_dates)} 个日期)")
            if _is_partitioned_table(db_name, job_name, mysql_cmd):
                # 清理可能存在的宽分区 (来自 previous full-refresh run)
                run = lambda sql: subprocess.run(
                    mysql_cmd + [db_name], input=sql,
                    capture_output=True, text=True, timeout=30,
                )
                run(f"ALTER TABLE {db_name}.{job_name} DROP PARTITION IF EXISTS p_full;")
                run(f"ALTER TABLE {db_name}.{job_name} SET ('dynamic_partition.enable' = 'true');")
            for etl_date in all_dates:
                _ensure_partition(db_name, job_name, etl_date, mysql_cmd)
                sql_text = sql_file.read_text(encoding="utf-8")
                full_sql = f"SET @etl_date = '{etl_date}';\nSET @full_refresh = 0;\n{sql_text}"
                r = subprocess.run(
                    mysql_cmd + [db_name],
                    input=full_sql, capture_output=True, text=True, timeout=600,
                )
                if r.returncode != 0:
                    raise RuntimeError(f"[{job_name}] [FAIL] (date={etl_date})\n  {r.stderr.strip()}")
                print(f"  [{job_name}] [OK] (date={etl_date})")
            return

    _ensure_full_refresh_partitions(db_name, job_name, all_dates, mysql_cmd)

    if materialized == 'full':
        sql_text = sql_file.read_text(encoding="utf-8")
        full_sql = f"SET @full_refresh = 1;\n{sql_text}"
        r = subprocess.run(
            mysql_cmd + [db_name],
            input=full_sql, capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            raise RuntimeError(f"[{job_name}] [FAIL]\n  {r.stderr.strip()}")
        print(f"  [{job_name}] [OK] (full-refresh)")
        return

    # incremental: run with @full_refresh=1
    sql_text = sql_file.read_text(encoding="utf-8")
    full_sql = f"SET @full_refresh = 1; SET @etl_date = CURDATE();\n{sql_text}"
    r = subprocess.run(
        mysql_cmd + [db_name],
        input=full_sql, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"[{job_name}] [FAIL]\n  {r.stderr.strip()}")
    print(f"  [{job_name}] [OK] (full-refresh)")


def _discover_ods_dates(project: str, db_name: str,
                        mysql_cmd: list[str]) -> list[str]:
    """从 ODS 表发现所有日期."""
    ods_model_tables = set(get_model_names_by_layer(project, "ODS"))
    r = subprocess.run(
        mysql_cmd + [db_name],
        input="SHOW TABLES", capture_output=True, text=True, timeout=60,
    )
    tables = [line.strip() for line in r.stdout.strip().split("\n")[1:] if line.strip()]
    ods_tables = [t for t in tables if t in ods_model_tables]
    all_dates: set[str] = set()
    for tbl in ods_tables:
        r = subprocess.run(
            mysql_cmd + [db_name],
            input=f"SELECT DISTINCT DATE(load_time) AS d FROM {db_name}.{tbl} ORDER BY d",
            capture_output=True, text=True, timeout=120,
        )
        dates = [line.strip() for line in r.stdout.strip().split("\n")[1:] if line.strip()]
        all_dates.update(dates)
    return sorted(all_dates)


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
    parser.add_argument("--etl-dates", nargs="*", default=None, help="ETL 日期 (YYYY-MM-DD)")
    parser.add_argument("--full-refresh", action="store_true", help="全量刷新模式")
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

    if not args.full_refresh:
        if not args.etl_dates:
            parser.error("请指定 --etl-dates 或使用 --full-refresh")
        for d in args.etl_dates:
            if not _DATE_RE.match(d):
                print(f"错误: 日期格式无效 '{d}', 需要 YYYY-MM-DD")
                sys.exit(1)
    else:
        if args.etl_dates:
            print("提示: --full-refresh 模式下忽略 --etl-dates")

    task_files = _get_task_files(project)
    task_names = set(task_files.keys())

    dag_path = _root / "lineage" / f"job_dag_{project}.json"
    if args.refresh_dag or not dag_path.exists():
        print(f"生成 DAG: {dag_path}")
        dag = _build_job_dag(project)
        dag.save(dag_path)
        print(f"  DAG 已保存: {len(dag._edges)} 条边")
    else:
        print(f"加载 DAG: {dag_path}")
        dag = JobDAG.load(dag_path)
        if _dag_needs_refresh_for_tasks(dag, task_names):
            print("  DAG 与当前作业不匹配, 重新生成...")
            dag = _build_job_dag(project)
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

    if args.full_refresh:
        print(f"\n{'=' * 60}")
        print(f"全量刷新模式 (按 DAG 拓扑执行)")
        print(f"{'=' * 60}")
        schema = _load_schema(project)
        print(f"发现 ODS 日期分区...")
        all_dates = _discover_ods_dates(project, db_name, mysql_cmd)
        print(f"  {len(all_dates)} 个日期")
        for job_name in exec_order:
            try:
                _run_job_full_refresh(
                    job_name, task_files[job_name], mysql_cmd, db_name,
                    schema, all_dates,
                )
            except (subprocess.TimeoutExpired, RuntimeError) as e:
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
