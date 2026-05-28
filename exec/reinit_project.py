#!/usr/bin/env python3
"""
数据重新初始化.

流程:
  1. 重建所有表 (执行 ddl/*.sql, DROP + CREATE)
  2. 初始化 ODS 层数据
  3. 从 ODS 表自动发现分区日期, 确定 etl_dates
  4. 调用 task_run.py 按 DAG 拓扑重算上层表

用法:
    python exec/reinit_project.py --project shop
"""

import argparse, subprocess, sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from config import PROJECT_CONFIG, DB_ENV_CONFIG, get_mysql_cmd


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
    from config import get_naming_config
    _nc = get_naming_config()
    _ods_prefix = _nc.layers["ODS"].prefix
    ods_tables = [t for t in tables if t.startswith(_ods_prefix)]
    all_dates = set()
    for tbl in ods_tables:
        result = run_sql(
            f"SELECT DISTINCT DATE(create_time) AS d FROM {db}.{tbl} ORDER BY d",
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
    args = parser.parse_args()

    project = args.project
    env_cmd = get_mysql_cmd(args.db_env)
    cfg = PROJECT_CONFIG[project]
    db_name = cfg["db"]
    data_dir = _root / cfg["dir"] / "data"

    ddl_dir = _root / cfg["dir"] / "ddl"

    print(f"项目: {project}")
    print(f"数据库: {db_name}")
    print(f"环境: {args.db_env}")

    # ── Step 1: 重建所有表 ──
    print(f"\n{'=' * 60}")
    print("Step 1: 重建所有表 (执行 ddl/*.sql)")

    if not ddl_dir.exists():
        print(f"  [FAIL] DDL 目录不存在: {ddl_dir}")
        sys.exit(1)

    ddl_files = sorted(ddl_dir.glob("*.sql"))
    if not ddl_files:
        print("  DDL 目录中无 SQL 文件")
        sys.exit(1)

    for f in ddl_files:
        print(f"  [DDL] {f.name}")
        try:
            run_sql(f.read_text(encoding="utf-8"), db_name, env_cmd)
        except Exception as e:
            print(f"  [FAIL] {f.name}: {e}")
            sys.exit(1)

    # ── Step 2: 初始化 ODS ──
    print(f"\n{'=' * 60}")
    print("Step 2: 初始化 ODS 层")

    if data_dir.exists():
        for f in sorted(data_dir.glob("*.sql")):
            print(f"  [ODS INIT] {f.name}")
            sql = f.read_text(encoding="utf-8")
            try:
                run_sql(sql, db_name, env_cmd)
            except Exception as e:
                print(f"  [FAIL] {f.name}: {e}")
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
