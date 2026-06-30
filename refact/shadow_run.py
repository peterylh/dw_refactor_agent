#!/usr/bin/env python3
"""Execute refactor shadow-run plans against the QA database."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from config import TEXT_ENCODING, get_mysql_cmd
from doris_sql import extract_create_table_name

FINAL_ALTER_JOB_STATES = {"FINISHED", "CANCELLED"}
DEFAULT_ALTER_JOB_TIMEOUT_SECONDS = 300
DEFAULT_ALTER_JOB_POLL_INTERVAL_SECONDS = 2
ALTER_TABLE_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+"
    r"(?P<table>(?:`[^`]+`|[^\s]+)(?:\s*\.\s*(?:`[^`]+`|[^\s]+))?)"
    r"\s+(?P<body>.*?)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
TABLE_RENAME_RE = re.compile(
    r"^\s*RENAME\s+"
    r"(?!COLUMN\b|ROLLUP\b|PARTITION\b)"
    r"(?P<target>(?:`[^`]+`|[^\s;]+)"
    r"(?:\s*\.\s*(?:`[^`]+`|[^\s;]+))?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


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


def _with_semicolon(sql: str) -> str:
    sql = sql.strip()
    return sql if sql.endswith(";") else f"{sql};"


def _split_outside_quotes(text: str, delimiter: str) -> list[str]:
    parts = []
    current = []
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if quote:
            current.append(ch)
            if ch == "\\" and nxt:
                current.append(nxt)
                i += 2
                continue
            if ch == quote:
                if nxt == quote:
                    current.append(nxt)
                    i += 2
                    continue
                quote = ""
            i += 1
            continue

        if ch in {"'", '"', "`"}:
            quote = ch
            current.append(ch)
            i += 1
            continue

        if ch == "-" and nxt == "-":
            line_end = text.find("\n", i + 2)
            if line_end == -1:
                current.append(text[i:])
                break
            current.append(text[i : line_end + 1])
            i = line_end + 1
            continue

        if ch == "/" and nxt == "*":
            block_end = text.find("*/", i + 2)
            if block_end == -1:
                current.append(text[i:])
                break
            current.append(text[i : block_end + 2])
            i = block_end + 2
            continue

        if ch == delimiter:
            parts.append("".join(current))
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    parts.append("".join(current))
    return parts


def _split_sql_statements(sql_text: str) -> list[str]:
    return [
        _with_semicolon(part)
        for part in _split_outside_quotes(sql_text, ";")
        if part.strip()
    ]


def _ddl_change_statements(sql_text: str) -> list[str]:
    """Return the DDL statements provided by the plan without rewriting them."""
    return _split_sql_statements(sql_text)


def _split_identifier_path(identifier: str) -> list[str]:
    parts = []
    current = []
    in_backticks = False
    for ch in identifier.strip():
        if ch == "`":
            in_backticks = not in_backticks
            current.append(ch)
        elif ch == "." and not in_backticks:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _unquote_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith("`") and identifier.endswith("`"):
        return identifier[1:-1].replace("``", "`")
    return identifier


def _quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def _quote_string_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _resolve_table_ref(
    table_ref: str, default_db: str
) -> tuple[str, str] | None:
    parts = [
        _unquote_identifier(part) for part in _split_identifier_path(table_ref)
    ]
    if len(parts) == 1:
        return default_db, parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


def _dedupe_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    seen = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
    return result


def _alter_table_wait_refs(
    statement: str, default_db: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    match = ALTER_TABLE_RE.match(statement)
    if not match:
        return [], []

    current_ref = _resolve_table_ref(match.group("table"), default_db)
    if current_ref is None:
        return [], []

    before_refs = [current_ref]
    after_refs = [current_ref]
    rename_match = TABLE_RENAME_RE.match(match.group("body").strip())
    if rename_match:
        target_ref = _resolve_table_ref(
            rename_match.group("target"), current_ref[0] or default_db
        )
        if target_ref is not None:
            after_refs = [target_ref]

    return _dedupe_refs(before_refs), _dedupe_refs(after_refs)


def _parse_mysql_table(output: str) -> list[dict]:
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return []

    headers = [header.strip() for header in lines[0].split("\t")]
    if "State" not in headers:
        return []

    rows = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        rows.append(
            {headers[idx]: values[idx].strip() for idx in range(len(headers))}
        )
    return rows


def _show_table_alter_jobs(
    db_name: str, table_name: str, qa: bool
) -> list[dict]:
    sql = (
        f"SHOW ALTER TABLE COLUMN FROM {_quote_identifier(db_name)} "
        f'WHERE TableName = "{_quote_string_value(table_name)}" '
        "ORDER BY CreateTime DESC LIMIT 10"
    )
    return _parse_mysql_table(run_sql(sql, qa=qa))


def _job_ids(jobs: list[dict]) -> set[str]:
    return {job.get("JobId", "") for job in jobs if job.get("JobId")}


def _active_alter_jobs(jobs: list[dict]) -> list[dict]:
    return [
        job
        for job in jobs
        if job.get("State", "").strip().upper() not in FINAL_ALTER_JOB_STATES
    ]


def _new_cancelled_jobs(
    jobs: list[dict], known_job_ids: set[str] | None
) -> list[dict]:
    if known_job_ids is None:
        return []
    return [
        job
        for job in jobs
        if job.get("JobId")
        and job.get("JobId") not in known_job_ids
        and job.get("State", "").strip().upper() == "CANCELLED"
    ]


def _wait_for_table_alter_jobs(
    db_name: str,
    table_name: str,
    *,
    qa: bool,
    known_job_ids: set[str] | None = None,
    poll_interval_seconds: float = DEFAULT_ALTER_JOB_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_ALTER_JOB_TIMEOUT_SECONDS,
) -> list[dict]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        jobs = _show_table_alter_jobs(db_name, table_name, qa)
        cancelled = _new_cancelled_jobs(jobs, known_job_ids)
        if cancelled:
            msg = cancelled[0].get("Msg", "")
            raise RuntimeError(
                f"ALTER job cancelled for {db_name}.{table_name}: {msg}"
            )

        active_jobs = _active_alter_jobs(jobs)
        if not active_jobs:
            return jobs

        if time.monotonic() >= deadline:
            states = ", ".join(
                f"{job.get('JobId')}:{job.get('State')}" for job in active_jobs
            )
            raise TimeoutError(
                f"Timed out waiting for ALTER jobs on "
                f"{db_name}.{table_name}: {states}"
            )
        time.sleep(poll_interval_seconds)


def _execute_ddl_statement(statement: str, qa_db: str) -> None:
    before_refs, after_refs = _alter_table_wait_refs(statement, qa_db)
    known_job_ids_by_ref = {}

    for db_name, table_name in before_refs:
        jobs = _wait_for_table_alter_jobs(db_name, table_name, qa=True)
        known_job_ids_by_ref[(db_name, table_name)] = _job_ids(jobs)

    run_sql(statement, qa_db, qa=True)

    for db_name, table_name in after_refs:
        known_job_ids = known_job_ids_by_ref.get((db_name, table_name))
        jobs = _wait_for_table_alter_jobs(
            db_name,
            table_name,
            qa=True,
            known_job_ids=known_job_ids,
        )
        known_job_ids_by_ref[(db_name, table_name)] = _job_ids(jobs)


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
            statements = _ddl_change_statements(sql_qa)
            try:
                for statement in statements:
                    _execute_ddl_statement(statement, qa_db)
                print(
                    f"  [{change.get('change_type')}] "
                    f"{change.get('table_name', '?')}"
                )
            except Exception as exc:
                print(f"  [FAIL] {change.get('change_type')}: {exc}")
                sys.exit(1)

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
