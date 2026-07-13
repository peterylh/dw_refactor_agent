#!/usr/bin/env python3
"""
数据重新初始化.

流程:
   1. 重建所有表 (执行 ODS/MID/ADS DDL, DROP + CREATE)
   2. 初始化 ODS 层数据
   3. 从 ODS 表自动发现分区日期, 确定 etl_dates
   4. 调用 task_run.py 按 DAG 拓扑重算上层表

用法:
    python -m dw_refactor_agent.execution.reinit_project --project shop
    python -m dw_refactor_agent.execution.reinit_project --project shop --full-refresh
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    python_module_env,
)
from dw_refactor_agent.execution.thread_pool import shutdown_executor


def run_sql(sql_text: str, db: str, env_cmd: list[str]) -> str:
    r = subprocess.run(
        env_cmd + [db],
        input=sql_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def get_etl_date_partitions(
    project: str, db: str, env_cmd: list[str]
) -> list[str]:
    result = run_sql("SHOW TABLES", db, env_cmd)
    tables = [
        line.strip() for line in result.strip().split("\n")[1:] if line.strip()
    ]
    ods_model_tables = set(get_model_names_by_layer(project, "ODS"))
    ods_tables = [t for t in tables if t in ods_model_tables]
    all_dates = set()
    for tbl in ods_tables:
        result = run_sql(
            f"SELECT DISTINCT DATE(load_time) AS d FROM {db}.{tbl} ORDER BY d",
            db,
            env_cmd,
        )
        dates = [
            line.strip()
            for line in result.strip().split("\n")[1:]
            if line.strip()
        ]
        all_dates.update(dates)
    return sorted(all_dates)


def _project_sql_files(project: str, asset_kind: str) -> list[Path]:
    return iter_project_asset_files(project, asset_kind, "*.sql")


def _task_run_command(project: str, db_env: str, parallel: int) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "dw_refactor_agent.execution.task_run",
        "--project",
        project,
        "--db-env",
        db_env,
        "--refresh-dag",
        "--parallel",
        str(parallel),
    ]


def _validate_etl_dates_requirement(
    project: str, etl_dates: list[str] | None
) -> None:
    """Reject unsafe implicit business-date discovery before rebuilding tables."""
    execution = (PROJECT_CONFIG.get(project) or {}).get("execution") or {}
    if execution.get("require_explicit_etl_dates") is True and not etl_dates:
        raise ValueError(
            f"[{project}] requires explicit --etl-dates; ODS load_time is an "
            "ingestion timestamp, not a business date"
        )


def main():
    parser = argparse.ArgumentParser(description="数据重新初始化")
    parser.add_argument(
        "--project", required=True, choices=list(PROJECT_CONFIG.keys())
    )
    parser.add_argument(
        "--db-env", default="prod", choices=list(DB_ENV_CONFIG.keys())
    )
    parser.add_argument(
        "--etl-dates",
        nargs="*",
        default=None,
        help="ETL 日期列表 (YYYY-MM-DD), 不传则自动从 ODS 发现",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="全量刷新模式 (启用 batch SQL 加速)",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="并行度, 默认 1 (串行)"
    )
    args = parser.parse_args()

    project = args.project
    try:
        _validate_etl_dates_requirement(project, args.etl_dates)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)
    env_cmd = get_mysql_cmd(args.db_env)
    cfg = PROJECT_CONFIG[project]
    db_name = cfg["db"]
    parallel = args.parallel
    if parallel < 1:
        print("错误: --parallel 必须 >= 1")
        sys.exit(1)

    print(f"项目: {project}")
    print(f"数据库: {db_name}")
    print(f"环境: {args.db_env}")
    print(f"并行度: {parallel}")

    # ── Step 1: 重建所有表 ──
    print(f"\n{'=' * 60}")
    print("Step 1: 重建所有表 (执行 ODS/MID/ADS DDL)")

    ddl_files = _project_sql_files(project, "ddl")
    if not ddl_files:
        print("  DDL 目录中无 SQL 文件")
        sys.exit(1)

    for f in ddl_files:
        print(f"  [DDL] {f.name}")
        try:
            run_sql(f.read_text(encoding=TEXT_ENCODING), db_name, env_cmd)
        except Exception as e:
            print(f"  [FAIL] {f.name}: {e}")
            sys.exit(1)

    # ── Step 2: 初始化 ODS (并行) ──
    print(f"\n{'=' * 60}")
    print(f"Step 2: 初始化 ODS 层  (并行度: {parallel})")

    ods_files = _project_sql_files(project, "data")
    if ods_files:
        if parallel == 1:
            for f in ods_files:
                print(f"  [ODS INIT] {f.name}")
                try:
                    run_sql(
                        f.read_text(encoding=TEXT_ENCODING), db_name, env_cmd
                    )
                except Exception as e:
                    print(f"  [FAIL] {f.name}: {e}")
                    sys.exit(1)
        else:

            def load_ods(f: Path) -> Path:
                run_sql(f.read_text(encoding=TEXT_ENCODING), db_name, env_cmd)
                return f

            ods_error: str | None = None
            executor = ThreadPoolExecutor(max_workers=parallel)
            try:
                fut_to_file = {
                    executor.submit(load_ods, f): f for f in ods_files
                }
                for future in as_completed(fut_to_file):
                    f = fut_to_file[future]
                    exc = future.exception()
                    if exc is not None:
                        ods_error = f"[FAIL] {f.name}: {exc}"
                        break
                    print(f"  [ODS INIT] {f.name}")
            finally:
                shutdown_executor(executor)
            if ods_error:
                print(f"  {ods_error}")
                sys.exit(1)
    else:
        print(f"  {project} 项目无 ODS 初始化 SQL, 请手动导入 ODS 数据")

    # ── Step 3: 确定 ETL 日期 ──
    cmd = _task_run_command(project, args.db_env, parallel)

    if args.full_refresh:
        print(f"\n{'=' * 60}")
        print("Step 3: 全量刷新模式 (启用 batch SQL 加速)")
        cmd += ["--full-refresh"]
        if args.etl_dates:
            cmd += ["--etl-dates", *args.etl_dates]
        print("  跳过逐日迭代, 按 batch SQL 执行")
    else:
        print(f"\n{'=' * 60}")
        if args.etl_dates:
            etl_dates = args.etl_dates
            print(f"Step 3: 使用指定的 ETL 日期 ({len(etl_dates)} 个)")
        else:
            print("Step 3: 自动发现 ODS 分区日期")
            etl_dates = get_etl_date_partitions(project, db_name, env_cmd)
            if not etl_dates:
                print("  ODS 表中无数据, 无法确定 etl_date")
                sys.exit(1)
        print(f"  ETL 日期: {', '.join(etl_dates)}")
        cmd += ["--etl-dates", *etl_dates]

    # ── Step 4: 调用 task_run.py ──
    print(f"\n{'=' * 60}")
    print("Step 4: 按 DAG 拓扑重算上层表")
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=python_module_env())
    if result.returncode != 0:
        print("\n[FAIL] 初始化失败")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("初始化完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
