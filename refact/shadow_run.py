#!/usr/bin/env python3
"""Execute refactor shadow-run plans against the QA database."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from config import TEXT_ENCODING, get_mysql_cmd
from doris_sql import extract_create_table_name


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sql(sql: str, db: str = "", qa: bool = False) -> str:
    """Execute one SQL statement and return stdout."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    cmd.extend(["-e", sql])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout


def run_sql_text(sql_text: str, db: str = "", qa: bool = False) -> str:
    """Execute multi-statement SQL text through stdin."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    result = subprocess.run(
        cmd,
        input=sql_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout


def _get_dml_target(stmt):
    """Return the DML target table name without database prefix."""
    if isinstance(stmt, exp.Insert):
        target = stmt.this
        if isinstance(target, exp.Table):
            return target.name
        if isinstance(target, exp.Schema) and isinstance(
            target.this, exp.Table
        ):
            return target.this.name
    elif isinstance(stmt, (exp.Update, exp.Delete)):
        if isinstance(stmt.this, exp.Table):
            return stmt.this.name
    elif isinstance(stmt, exp.TruncateTable):
        if stmt.expressions:
            table = stmt.expressions[0]
            if isinstance(table, exp.Table):
                return table.name
    elif isinstance(stmt, exp.Create):
        if isinstance(stmt.this, exp.Schema) and isinstance(
            stmt.this.this, exp.Table
        ):
            return stmt.this.this.name
    elif isinstance(stmt, exp.Command) and str(stmt.this).upper() == "CREATE":
        table_name = extract_create_table_name(stmt.sql(dialect="doris"))
        return table_name.split(".")[-1] if table_name else None
    return None


def rewrite_sql(
    sql_text: str, prod_db: str, qa_db: str, recalculated: set
) -> str:
    """
    Rewrite table references for shadow execution.

    DML targets write to QA. Already recalculated intermediate sources read from
    QA. ODS and untouched intermediate sources keep reading from production.
    """
    statements = sqlglot.parse(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    rewritten = []
    for stmt in statements:
        if stmt is None:
            continue

        dml_target = _get_dml_target(stmt)
        todo = []
        for table in stmt.find_all(exp.Table):
            db_node = table.args.get("db")
            if db_node is None:
                continue
            table_name = table.name
            if table_name == dml_target or table_name in recalculated:
                todo.append((table, qa_db))

        for table, target_db in todo:
            table.args["db"] = exp.to_identifier(target_db)

        rewritten.append(stmt.sql(dialect="doris"))

    if not rewritten:
        return ""
    return ";\n".join(rewritten) + ";"


def execute_shadow_plan(plan: dict, *, dry_run: bool = False) -> dict:
    """Execute or preview a shadow-run validation plan."""
    if dry_run:
        _dry_run(plan)
        return {
            "status": "dry_run",
            "qa_db": plan["qa_db"],
            "job_count": len(plan.get("jobs_to_run", [])),
        }

    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    etl_date = plan.get("partition_info", {}).get("etl_date")
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])

    checks = plan.get("verification", {}).get("checks", [])
    if not plan.get("anchors") and not checks:
        print("  警告: 无锚点表且无校验配置")
        print("    作业会正常执行，但 compare 阶段没有表可对比校验")
        print("    如果只是想确认作业不报错，可继续执行\n")

    print("=" * 60)
    print(f"Phase 0: 重置验证数据库 {qa_db}")
    run_sql(f"DROP DATABASE IF EXISTS {qa_db}", "information_schema", qa=True)
    run_sql(f"CREATE DATABASE {qa_db}", "information_schema", qa=True)
    print(f"  {qa_db} 已重建")

    print(f"\n{'=' * 60}")
    print(f"Phase 1: 基线建表 ({len(baseline_ddl)} 张)")
    for table_name in sorted(baseline_ddl):
        ddl_raw = baseline_ddl[table_name]
        if not ddl_raw.strip():
            continue
        ddl_qa = ddl_raw.replace(f"{prod_db}.", f"{qa_db}.")
        try:
            run_sql(ddl_qa, qa_db, qa=True)
            print(f"  [CREATE] {qa_db}.{table_name}")
        except Exception as exc:
            print(f"  [FAIL] {qa_db}.{table_name}: {exc}")
            sys.exit(1)

    if ddl_changes:
        print(f"\n{'-' * 60}")
        print(f"Phase 2: 应用 DDL 变更 ({len(ddl_changes)} 条)")
        for change in ddl_changes:
            sql = change.get("sql", "")
            if not sql.strip():
                continue
            sql_qa = sql.replace(f"{prod_db}.", f"{qa_db}.")
            try:
                run_sql(sql_qa, qa_db, qa=True)
                print(
                    f"  [{change.get('change_type')}] "
                    f"{change.get('table_name', '?')}"
                )
            except Exception as exc:
                print(f"  [SKIP] {change.get('change_type')}: {exc}")

    print(f"\n{'=' * 60}")
    print(f"Phase 3: 执行作业 ({len(jobs_to_run)} 个)")
    recalculated = set()
    root = _project_root()

    for idx, job in enumerate(jobs_to_run, 1):
        job_name = job["job"]
        job_file = job["file"]
        layer = job.get("layer", "?")
        needs_etl_date = job.get("needs_etl_date", False)

        print(f"\n  --- {idx}/{len(jobs_to_run)}: [{layer}] {job_name} ---")
        file_path = root / job_file
        if not file_path.exists():
            print(f"  [SKIP] 文件不存在: {file_path}")
            continue

        sql_text = file_path.read_text(encoding=TEXT_ENCODING)
        rewritten = rewrite_sql(sql_text, prod_db, qa_db, recalculated)

        if needs_etl_date and etl_date:
            rewritten = f"SET @etl_date = '{etl_date}';\n" + rewritten

        try:
            run_sql_text(rewritten, qa_db, qa=True)
            print(f"  + {qa_db}.{job_name}")
        except Exception as exc:
            print(f"  [FAIL] {job_name}: {exc}")
            sys.exit(1)

        recalculated.add(job_name)

    print(f"\n{'=' * 60}")
    print(
        f"Shadow run 完成! 共执行 {len(jobs_to_run)} 个作业, 目标库: {qa_db}"
    )
    return {
        "status": "completed",
        "qa_db": qa_db,
        "job_count": len(jobs_to_run),
    }


def run_shadow_plan(
    plan_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Run or dry-run a validation plan and write the execution result."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    result = execute_shadow_plan(plan, dry_run=dry_run)
    result.update(
        {
            "plan": str(plan_path),
            "project": plan.get("project"),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    return result


def _dry_run(plan: dict) -> None:
    qa_db = plan["qa_db"]
    prod_db = plan["project_db"]
    etl_date = plan.get("partition_info", {}).get("etl_date")
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    root = _project_root()

    print(f"{'=' * 60}")
    print("=== SHADOW RUN DRY RUN ===")
    print(f"  项目: {plan['project']}")
    git_info = plan.get("git") or {}
    if git_info:
        print(f"  分支: {git_info.get('branch', '')}")
        merge_base = str(git_info.get("merge_base") or "")
        print(f"  基线: {merge_base[:12]}...")
    print(f"  生产库: {prod_db} -> 验证库: {qa_db}")
    print(f"  锚点: {plan.get('anchors', [])}")
    partition_info = plan.get("partition_info", {})
    print(f"  分区: {partition_info.get('partition', 'N/A')}")
    checks = plan.get("verification", {}).get("checks", [])
    if not plan.get("anchors") and not checks:
        print()
        print("  警告: 无锚点表且无校验配置，compare 阶段没有表可对比校验")

    print("\n--- Phase 0: 重置验证库 ---")
    print(f"  DROP DATABASE IF EXISTS {qa_db}")
    print(f"  CREATE DATABASE {qa_db}")

    print(f"\n--- Phase 1: 基线建表 ({len(baseline_ddl)} 张) ---")
    for table_name in sorted(baseline_ddl):
        print(f"  [CREATE] {qa_db}.{table_name}")

    print(f"\n--- Phase 2: DDL 变更 ({len(ddl_changes)} 条) ---")
    for change in ddl_changes:
        name = change.get("table_name", change.get("old_name", "?"))
        print(f"  [{change['change_type']}] {name}")

    print(f"\n--- Phase 3: 作业 ({len(jobs_to_run)} 个) ---")
    recalculated = set()
    for idx, job in enumerate(jobs_to_run, 1):
        job_name = job["job"]
        layer = job.get("layer", "?")
        job_file = job["file"]
        file_path = root / job_file

        print(f"\n  {idx}/{len(jobs_to_run)}: [{layer}] {job_name}")
        if not file_path.exists():
            print("    [SKIP] 文件不存在")
            continue

        sql_text = file_path.read_text(encoding=TEXT_ENCODING)
        rewritten = rewrite_sql(sql_text, prod_db, qa_db, recalculated)
        needs_etl_date = job.get("needs_etl_date", False)

        if needs_etl_date and etl_date:
            print(f"    SET @etl_date = '{etl_date}';")

        for line in rewritten.splitlines()[:8]:
            print(f"    {line}")
        total = len(rewritten.splitlines())
        if total > 8:
            print(f"    ... ({total} 行)")

        recalculated.add(job_name)

    if checks:
        print(f"\n--- 校验检查 ({len(checks)} 项) ---")
        for check in checks:
            line = f"  [{check['method']}] {qa_db}.{check['table']}"
            partition_col = check.get("partition_col")
            partition_value = check.get("partition_value")
            if partition_col and partition_value is not None:
                line = f"{line} WHERE {partition_col} = '{partition_value}'"
            print(line)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="执行 refactor shadow-run 计划"
    )
    parser.add_argument("--plan", required=True, help="验证计划 JSON 路径")
    parser.add_argument(
        "--output",
        default=None,
        help="结果 JSON 路径，默认写入 plan 同目录 shadow_run_result.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只输出执行计划，不连接数据库"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plan_path = Path(args.plan)
    output_path = (
        Path(args.output)
        if args.output
        else plan_path.parent / "shadow_run_result.json"
    )
    run_shadow_plan(plan_path, output_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
