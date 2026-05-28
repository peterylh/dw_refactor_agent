#!/usr/bin/env python3
"""
数据重新初始化.

流程:
  1. 清空所有表数据
  2. 初始化 ODS 层数据
  3. 从 ODS 表自动发现分区日期, 确定 etl_dates
  4. 调用 task_run.py 按 DAG 拓扑重算上层表

用法:
    python exec/reinit_project.py --project shop
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from config import PROJECT_CONFIG, DB_ENV_CONFIG, get_mysql_cmd, get_naming_config


def run_sql(sql_text: str, db: str, env_cmd: list[str]) -> str:
    r = subprocess.run(
        env_cmd + [db], input=sql_text, capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def get_etl_date_partitions(db: str, env_cmd: list[str]) -> list[str]:
    result = run_sql("SHOW TABLES", db, env_cmd)
    tables = [line.strip() for line in result.strip().split("\n")[1:] if line.strip()]
    nc = get_naming_config()
    ods_prefix = nc.layers["ODS"].prefix
    ods_tables = [t for t in tables if t.startswith(ods_prefix)]
    all_dates = set()
    for tbl in ods_tables:
        result = run_sql(
            f"SELECT DISTINCT DATE(load_time) AS d FROM {db}.{tbl} ORDER BY d",
            db, env_cmd,
        )
        dates = [line.strip() for line in result.strip().split("\n")[1:] if line.strip()]
        all_dates.update(dates)
    return sorted(all_dates)


def main():
    parser = argparse.ArgumentParser(description="数据重新初始化")
    parser.add_argument("--project", required=True, choices=list(PROJECT_CONFIG.keys()))
    parser.add_argument("--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys()))
    parser.add_argument("--etl-dates", nargs="*", default=None,
                        help="ETL 日期列表 (YYYY-MM-DD), 不传则自动从 ODS 发现")
    parser.add_argument("--parallel", type=int, default=1,
                        help="并行度, 默认 1 (串行)")
    args = parser.parse_args()

    project = args.project
    env_cmd = get_mysql_cmd(args.db_env)
    cfg = PROJECT_CONFIG[project]
    db_name = cfg["db"]
    data_dir = _root / cfg["dir"] / "data"
    parallel = args.parallel
    if parallel < 1:
        print("错误: --parallel 必须 >= 1")
        sys.exit(1)

    print(f"项目: {project}")
    print(f"数据库: {db_name}")
    print(f"环境: {args.db_env}")
    print(f"并行度: {parallel}")

    # ── Step 1: 清空所有表 ──
    print(f"\n{'=' * 60}")
    print("Step 1: 清空所有表数据")

    result = run_sql("SHOW TABLES", db_name, env_cmd)
    tables = [line.strip() for line in result.strip().split("\n")[1:] if line.strip()]

    if not tables:
        print("  数据库中无表, 跳过清空步骤")
    else:
        nc = get_naming_config()

        def sort_key(t):
            for layer_name in reversed(nc.layer_order):
                if t.startswith(nc.layers[layer_name].prefix):
                    return nc.layers[layer_name].rank
            return 4

        for t in sorted(tables, key=sort_key, reverse=True):
            try:
                run_sql(f"TRUNCATE TABLE {db_name}.{t}", db_name, env_cmd)
                print(f"  [TRUNCATE] {t}")
            except Exception as e:
                print(f"  [SKIP] {t}: {e}")

    # ── Step 2: 初始化 ODS (并行) ──
    print(f"\n{'=' * 60}")
    print(f"Step 2: 初始化 ODS 层  (并行度: {parallel})")

    if data_dir.exists():
        ods_files = sorted(data_dir.glob("*.sql"))
        if parallel == 1:
            for f in ods_files:
                print(f"  [ODS INIT] {f.name}")
                try:
                    run_sql(f.read_text(encoding="utf-8"), db_name, env_cmd)
                except Exception as e:
                    print(f"  [FAIL] {f.name}: {e}")
                    sys.exit(1)
        else:
            def load_ods(f: Path) -> Path:
                run_sql(f.read_text(encoding="utf-8"), db_name, env_cmd)
                return f

            ods_error: str | None = None
            executor = ThreadPoolExecutor(max_workers=parallel)
            try:
                fut_to_file = {executor.submit(load_ods, f): f for f in ods_files}
                for future in as_completed(fut_to_file):
                    f = fut_to_file[future]
                    exc = future.exception()
                    if exc is not None:
                        ods_error = f"[FAIL] {f.name}: {exc}"
                        break
                    print(f"  [ODS INIT] {f.name}")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            if ods_error:
                print(f"  {ods_error}")
                sys.exit(1)
    else:
        print(f"  {project} 项目无 data/ 目录, 请手动导入 ODS 数据")
        if project == "olist":
            print(f"  参考: python {PROJECT_CONFIG[project]['dir']}/import_data.py")

    # ── Step 3: 确定 ETL 日期 ──
    print(f"\n{'=' * 60}")
    if args.etl_dates:
        etl_dates = args.etl_dates
        print(f"Step 3: 使用指定的 ETL 日期 ({len(etl_dates)} 个)")
    else:
        print("Step 3: 自动发现 ODS 分区日期")
        etl_dates = get_etl_date_partitions(db_name, env_cmd)
        if not etl_dates:
            print("  ODS 表中无数据, 无法确定 etl_date")
            sys.exit(1)
    print(f"  ETL 日期: {', '.join(etl_dates)}")

    # ── Step 4: 调用 task_run.py ──
    print(f"\n{'=' * 60}")
    print("Step 4: 按 DAG 拓扑重算上层表")

    task_run = _root / "exec" / "task_run.py"
    cmd = [
        sys.executable, str(task_run),
        "--project", project,
        "--etl-dates", *etl_dates,
        "--db-env", args.db_env,
        "--refresh-dag",
        "--parallel", str(parallel),
    ]
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=_root)
    if result.returncode != 0:
        print(f"\n[FAIL] 初始化失败")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"初始化完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
