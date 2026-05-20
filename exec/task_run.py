#!/usr/bin/env python3
"""
按照依赖顺序执行 ETL 作业.

用法:
    python exec/task_run.py --project shop --etl-dates 2025-01-01
    python exec/task_run.py --project shop --etl-dates 2025-01-01 2025-01-02 --job-list dwd_customer dws_store_sales_daily
    python exec/task_run.py --project olist --etl-dates 2025-01-01 --db-env prod
    python exec/task_run.py --project shop --etl-dates 2025-01-01 --refresh-dag
"""

import json, argparse, subprocess, sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lineage.job_dag import JobDAG
from lineage.lineage_extractor import PROJECT_CONFIG

DB_ENV_CONFIG = {
    "prod": {"host": "172.16.0.90", "port": "9030", "user": "root"},
    "test": {"host": "172.16.0.90", "port": "9034", "user": "root"},
    "qa":   {"host": "172.16.0.90", "port": "9030", "user": "qa"},
}


def _get_db_name(project: str, env: str) -> str:
    base = PROJECT_CONFIG[project]["db"]
    return base + "_qa" if env == "qa" else base


def _get_mysql_cmd(env: str) -> list[str]:
    cfg = DB_ENV_CONFIG[env]
    return ["mysql", f"-h{cfg['host']}", f"-P{cfg['port']}", f"-u{cfg['user']}"]


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


def main():
    parser = argparse.ArgumentParser(description="按依赖顺序执行 ETL 作业")
    parser.add_argument("--project", required=True, choices=list(PROJECT_CONFIG.keys()))
    parser.add_argument("--etl-dates", required=True, nargs="+", help="ETL 日期 (YYYY-MM-DD)")
    parser.add_argument("--job-list", nargs="*", default=None, help="作业清单, 默认全部")
    parser.add_argument("--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys()))
    parser.add_argument("--refresh-dag", action="store_true", help="重新生成 DAG 文件")
    args = parser.parse_args()

    project = args.project
    env = args.db_env
    db_name = _get_db_name(project, env)

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

    mysql_cmd = _get_mysql_cmd(env)
    for etl_date in args.etl_dates:
        print(f"\n{'=' * 60}")
        print(f"执行日期: {etl_date}")
        print(f"{'=' * 60}")
        for job_name in exec_order:
            sql_file = task_files[job_name]
            sql_text = sql_file.read_text(encoding="utf-8")
            print(f"\n  [{job_name}] ", end="", flush=True)
            full_sql = f"SET @etl_date = '{etl_date}';\n{sql_text}"
            try:
                r = subprocess.run(
                    mysql_cmd + [db_name],
                    input=full_sql, capture_output=True, text=True, timeout=600,
                )
                if r.returncode != 0:
                    print(f"[FAIL]\n  {r.stderr.strip()}")
                    sys.exit(1)
                print(f"[OK]")
            except subprocess.TimeoutExpired:
                print("[TIMEOUT]")
                sys.exit(1)
            except Exception as e:
                print(f"[FAIL] {e}")
                sys.exit(1)

    total_jobs = len(exec_order) * len(args.etl_dates)
    print(f"\n{'=' * 60}")
    print(f"全部完成! 共执行 {total_jobs} 个作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
