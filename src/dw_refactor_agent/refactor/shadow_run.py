#!/usr/bin/env python3
"""Execute refactor shadow-run plans against the QA database."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel
from sqlglot.tokens import Tokenizer, TokenType

from dw_refactor_agent.config import PROJECT_ROOT, TEXT_ENCODING, get_mysql_cmd
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.execution.sql_executor import ShadowSqlExecutor
from dw_refactor_agent.sql.doris import extract_create_table_name

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


class ShadowRunSqlError(RuntimeError):
    """Raised when a SQL command fails during shadow-run execution."""


def _project_root() -> Path:
    return PROJECT_ROOT


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    )


def _start_timing() -> dict:
    return {
        "started_at": _now_iso(),
        "monotonic_start": time.monotonic(),
    }


def _finish_timing(result: dict, timing: dict) -> dict:
    result["started_at"] = timing["started_at"]
    result["finished_at"] = _now_iso()
    elapsed_ms = int(
        round((time.monotonic() - timing["monotonic_start"]) * 1000)
    )
    result["duration_ms"] = max(0, elapsed_ms)
    return result


def _sql_error_message(result: subprocess.CompletedProcess) -> str:
    return (
        result.stderr.strip()
        or result.stdout.strip()
        or f"mysql exited with status {result.returncode}"
    )


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
        raise ShadowRunSqlError(_sql_error_message(result))
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
        raise ShadowRunSqlError(_sql_error_message(result))
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


def _get_statement_target_table(stmt):
    """Return the statement target table name without database prefix."""
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
        if isinstance(stmt.this, exp.Table):
            return stmt.this.name
        if isinstance(stmt.this, exp.Schema) and isinstance(
            stmt.this.this, exp.Table
        ):
            return stmt.this.this.name
    elif isinstance(stmt, (exp.Drop, exp.Alter)):
        if isinstance(stmt.this, exp.Table):
            return stmt.this.name
    elif isinstance(stmt, exp.Command) and str(stmt.this).upper() == "CREATE":
        table_name = extract_create_table_name(stmt.sql(dialect="doris"))
        return table_name.split(".")[-1] if table_name else None
    return None


def _get_dml_target(stmt):
    """Backward-compatible alias for statement target detection."""
    return _get_statement_target_table(stmt)


def _statement_ranges(sql_text: str) -> list[tuple[int, int]]:
    """Return raw SQL statement ranges, including statement terminators."""
    tokens = Tokenizer(dialect="doris").tokenize(sql_text)
    ranges = []
    start = 0
    for token in tokens:
        if token.token_type == TokenType.SEMICOLON:
            end = token.end + 1
            ranges.append((start, end))
            start = end
    if sql_text[start:].strip():
        ranges.append((start, len(sql_text)))
    return ranges


def _parse_first_statement(sql_text: str):
    statements = sqlglot.parse(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    return next((stmt for stmt in statements if stmt is not None), None)


def _is_backtick(token) -> bool:
    return token.token_type == TokenType.UNKNOWN and token.text == "`"


def _next_non_backtick(tokens: list, index: int) -> int:
    while index < len(tokens) and _is_backtick(tokens[index]):
        index += 1
    return index


def _previous_non_backtick(tokens: list, index: int) -> int:
    index -= 1
    while index >= 0 and _is_backtick(tokens[index]):
        index -= 1
    return index


def _identifier_matches(token, value: str) -> bool:
    if token.token_type not in {TokenType.IDENTIFIER, TokenType.VAR}:
        return False
    return token.text.casefold() == value.casefold()


def _identifier_replacement(sql_text: str, token, value: str) -> str:
    original = sql_text[token.start : token.end + 1]
    if (
        len(original) >= 2
        and original[0] == original[-1]
        and original[0] in {'"', "`"}
    ):
        return f"{original[0]}{value}{original[-1]}"
    return value


def _identifier_start(tokens: list, index: int) -> int:
    previous_index = index - 1
    if previous_index >= 0 and _is_backtick(tokens[previous_index]):
        return tokens[previous_index].start
    return tokens[index].start


def _is_unqualified_identifier(tokens: list, index: int) -> bool:
    previous_index = _previous_non_backtick(tokens, index)
    next_index = _next_non_backtick(tokens, index + 1)
    if (
        previous_index >= 0
        and tokens[previous_index].token_type == TokenType.DOT
    ):
        return False
    return not (
        next_index < len(tokens)
        and tokens[next_index].token_type == TokenType.DOT
    )


def _comma_continues_table_context(tokens: list, comma_index: int) -> bool:
    boundary_tokens = {
        TokenType.SELECT,
        TokenType.WHERE,
        TokenType.ON,
        TokenType.GROUP_BY,
        TokenType.ORDER_BY,
        TokenType.HAVING,
        TokenType.LIMIT,
        TokenType.WITH,
        TokenType.SEMICOLON,
    }
    index = comma_index - 1
    while index >= 0:
        token_type = tokens[index].token_type
        if token_type in {TokenType.FROM, TokenType.JOIN}:
            return True
        if token_type in boundary_tokens:
            return False
        index -= 1
    return False


def _is_table_reference_context(tokens: list, index: int) -> bool:
    previous_index = _previous_non_backtick(tokens, index)
    if previous_index < 0:
        return False
    previous_type = tokens[previous_index].token_type
    if previous_type in {
        TokenType.FROM,
        TokenType.JOIN,
        TokenType.UPDATE,
        TokenType.INTO,
        TokenType.TABLE,
    }:
        return True
    if previous_type == TokenType.COMMA:
        return _comma_continues_table_context(tokens, previous_index)
    return False


def _cte_names(stmt) -> set[str]:
    return {
        cte.alias_or_name.casefold()
        for cte in stmt.find_all(exp.CTE)
        if cte.alias_or_name
    }


def _unqualified_table_dbs(
    stmt,
    prod_db: str,
    qa_db: str,
    recalculated: set,
    statement_target: str | None,
) -> dict[str, str]:
    cte_names = _cte_names(stmt)
    recalculated_names = {name.casefold() for name in recalculated}
    target_name = statement_target.casefold() if statement_target else ""
    table_dbs = {}

    for table in stmt.find_all(exp.Table):
        if table.db:
            continue
        table_name = table.name
        if not table_name:
            continue
        canonical_name = table_name.casefold()
        if canonical_name in cte_names and canonical_name != target_name:
            continue
        if (
            canonical_name == target_name
            or canonical_name in recalculated_names
        ):
            table_dbs[canonical_name] = qa_db
        else:
            table_dbs[canonical_name] = prod_db

    return table_dbs


def _rewrite_qualified_table_dbs(
    sql_text: str,
    prod_db: str,
    qa_db: str,
    table_names: set[str],
) -> str:
    if not table_names:
        return sql_text

    wanted_tables = {name.casefold() for name in table_names}
    tokens = Tokenizer(dialect="doris").tokenize(sql_text)
    replacements = []

    for index, token in enumerate(tokens):
        if not _identifier_matches(token, prod_db):
            continue

        dot_index = _next_non_backtick(tokens, index + 1)
        if (
            dot_index >= len(tokens)
            or tokens[dot_index].token_type != TokenType.DOT
        ):
            continue

        table_index = _next_non_backtick(tokens, dot_index + 1)
        if table_index >= len(tokens):
            continue

        table_token = tokens[table_index]
        if table_token.token_type not in {TokenType.IDENTIFIER, TokenType.VAR}:
            continue
        if table_token.text.casefold() not in wanted_tables:
            continue

        after_table = _next_non_backtick(tokens, table_index + 1)
        if (
            after_table < len(tokens)
            and tokens[after_table].token_type == TokenType.DOT
        ):
            continue

        replacements.append(
            (
                token.start,
                token.end + 1,
                _identifier_replacement(sql_text, token, qa_db),
            )
        )

    if not replacements:
        return sql_text

    rewritten = sql_text
    for start, end, value in reversed(replacements):
        rewritten = f"{rewritten[:start]}{value}{rewritten[end:]}"
    return rewritten


def _rewrite_unqualified_table_dbs(
    sql_text: str,
    table_dbs: dict[str, str],
) -> str:
    if not table_dbs:
        return sql_text

    tokens = Tokenizer(dialect="doris").tokenize(sql_text)
    replacements = []

    for index, token in enumerate(tokens):
        if token.token_type not in {TokenType.IDENTIFIER, TokenType.VAR}:
            continue
        target_db = table_dbs.get(token.text.casefold())
        if not target_db:
            continue
        if not _is_unqualified_identifier(tokens, index):
            continue
        if not _is_table_reference_context(tokens, index):
            continue
        replacements.append(
            (
                _identifier_start(tokens, index),
                _identifier_start(tokens, index),
                f"{target_db}.",
            )
        )

    if not replacements:
        return sql_text

    rewritten = sql_text
    for start, end, value in reversed(replacements):
        rewritten = f"{rewritten[:start]}{value}{rewritten[end:]}"
    return rewritten


def _rewrite_statement_sql(
    sql_text: str, prod_db: str, qa_db: str, recalculated: set
) -> str:
    stmt = _parse_first_statement(sql_text)
    if stmt is None:
        return sql_text

    table_names = set(recalculated)
    statement_target = _get_statement_target_table(stmt)
    if statement_target:
        table_names.add(statement_target)

    rewritten = _rewrite_qualified_table_dbs(
        sql_text, prod_db, qa_db, table_names
    )
    table_dbs = _unqualified_table_dbs(
        stmt, prod_db, qa_db, recalculated, statement_target
    )
    return _rewrite_unqualified_table_dbs(rewritten, table_dbs)


def rewrite_sql(
    sql_text: str, prod_db: str, qa_db: str, recalculated: set
) -> str:
    """
    Rewrite table references for shadow execution.

    DML targets write to QA. Already recalculated intermediate sources read from
    QA. ODS and untouched intermediate sources keep reading from production.
    """
    if not sql_text.strip():
        return ""

    ranges = _statement_ranges(sql_text)
    if not ranges:
        return sql_text

    parts = []
    cursor = 0
    for start, end in ranges:
        parts.append(sql_text[cursor:start])
        parts.append(
            _rewrite_statement_sql(
                sql_text[start:end], prod_db, qa_db, recalculated
            )
        )
        cursor = end
    parts.append(sql_text[cursor:])
    return "".join(parts)


def _check_with_compare_anchor(check: dict, verification: dict) -> dict:
    if check.get("partition_col") or check.get("partition_value") is not None:
        return dict(check)
    anchor = (verification.get("compare_anchors") or {}).get(
        check.get("table")
    ) or {}
    time_column = anchor.get("time_column")
    anchor_value = anchor.get("anchor_time_value")
    if not time_column or anchor_value is None:
        return dict(check)
    resolved = dict(check)
    resolved["partition_col"] = time_column
    resolved["partition_value"] = anchor_value
    return resolved


def _plan_scope(plan: dict) -> dict:
    return plan.get("scope") or plan.get("affected_scope") or {}


def _plan_anchor_tables(plan: dict) -> list:
    anchors = plan.get("anchors")
    if anchors is not None:
        return list(anchors)
    return list((_plan_scope(plan).get("anchor_tables") or []))


def _rewrite_db_prefix(value: str, prod_db: str, qa_db: str) -> str:
    return value.replace(f"{prod_db}.", f"{qa_db}.")


def _qa_ddl_change(change: dict, prod_db: str, qa_db: str) -> dict:
    result = dict(change)
    if "sql" in result:
        original_sql = result.get("original_sql", result.get("sql", ""))
        result["sql"] = _rewrite_db_prefix(
            result.get("sql", ""),
            prod_db,
            qa_db,
        )
        result["original_sql"] = original_sql

    for key in ("table_name", "old_name", "new_name"):
        if key in result and isinstance(result[key], str):
            result[key] = _rewrite_db_prefix(result[key], prod_db, qa_db)

    return result


def _ddl_change_result(
    change: dict,
    status: str,
    error: str | None = None,
    *,
    statement_results: list[dict] | None = None,
) -> dict:
    result = {
        "change_type": change.get("change_type"),
        "sql": change.get("sql", ""),
        "status": status,
        "error": error,
    }
    if "original_sql" in change:
        result["original_sql"] = change.get("original_sql")
    for key in ("table_name", "old_name", "new_name"):
        if key in change:
            result[key] = change.get(key)
    for key in ("renames", "case_only_renames"):
        if key in change:
            result[key] = change.get(key)
    if statement_results is not None:
        result["statements"] = statement_results
    return result


def _ddl_statement_result(
    sql: str,
    status: str,
    error: str | None = None,
) -> dict:
    return {"sql": sql, "status": status, "error": error}


def _job_result(
    job: dict,
    status: str,
    error: str | None = None,
    *,
    actual_execution_values: list[str] | None = None,
    invocation_count: int | None = None,
    invocations: list[dict] | None = None,
) -> dict:
    job_name = job.get("job")
    result = {
        "job": job_name,
        "file": job.get("file"),
        "layer": job.get("layer", "?"),
        "target": job.get("target") or job_name,
        "status": status,
        "error": error,
    }
    for key in ("execution_values",):
        if key in job:
            result[key] = job.get(key)
    if actual_execution_values is not None:
        result["actual_execution_values"] = list(actual_execution_values)
    if invocation_count is not None:
        result["invocation_count"] = invocation_count
    if invocations is not None:
        result["invocations"] = invocations
    if "needs_etl_date" in job:
        result["needs_etl_date"] = bool(job.get("needs_etl_date", False))
    return result


def _invocation_result(
    driver_value: str | None,
    status: str,
    error: str | None = None,
) -> dict:
    return {
        "execution_value": driver_value,
        "status": status,
        "error": error,
    }


def _execution_value_strings(values) -> list[str]:
    result = []
    seen = set()
    for value in values or []:
        item = str(value)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return sorted(result)


def _job_driver_values(job: dict, spec) -> list[str | None]:
    if spec.materialized == "full" or not spec.slice_param:
        return [None]
    values = _execution_value_strings(job.get("execution_values"))
    if values:
        return values
    job_name = job.get("job") or spec.job_name
    raise ExecutionConfigError(
        f"[{job_name}] shadow-run requires execution_values "
        "for sliced incremental jobs"
    )


def _append_actual_execution_value(
    actual_execution_values: list[str],
    driver_value: str | None,
) -> None:
    if driver_value is None or driver_value in actual_execution_values:
        return
    actual_execution_values.append(driver_value)


def _job_for_driver_value(job: dict, driver_value: str | None) -> dict:
    if driver_value is None:
        return dict(job)
    planned = dict(job)
    planned["execution_values"] = [driver_value]
    return planned


def _result_summary(plan: dict, phases: list[dict]) -> dict:
    phase_by_name = {phase.get("name"): phase for phase in phases}
    ddl_changes = phase_by_name.get("apply_ddl_changes", {}).get(
        "ddl_changes", []
    )
    jobs = phase_by_name.get("run_jobs", {}).get("jobs", [])
    return {
        "baseline_table_count": len(plan.get("baseline_ddl", {})),
        "ddl_change_count": len(plan.get("ddl_changes", [])),
        "job_count": len(plan.get("jobs_to_run", [])),
        "failed_job_count": sum(
            1 for job in jobs if job.get("status") == "failed"
        ),
        "failed_ddl_change_count": sum(
            1
            for ddl_change in ddl_changes
            if ddl_change.get("status") == "failed"
        ),
    }


def _shadow_result(
    plan: dict, *, mode: str, status: str, phases: list
) -> dict:
    return {
        "status": status,
        "mode": mode,
        "project": plan.get("project"),
        "project_db": plan.get("project_db"),
        "qa_db": plan["qa_db"],
        "job_count": len(plan.get("jobs_to_run", [])),
        "summary": _result_summary(plan, phases),
        "phases": phases,
    }


def _failed_shadow_result(plan: dict, phases: list[dict]) -> dict:
    return _shadow_result(
        plan,
        mode="execute",
        status="failed",
        phases=phases,
    )


def _dry_run_phases(plan: dict, *, timing_detail: bool = False) -> list[dict]:
    root = _project_root()
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    planner = ExecutionPlanner(plan["project"], project_root=root)
    qa_ddl_changes = [
        _qa_ddl_change(change, prod_db, qa_db) for change in ddl_changes
    ]

    reset_timer = _start_timing()
    reset_phase = _finish_timing(
        {
            "name": "reset_qa_db",
            "status": "dry_run",
            "actions": [
                f"DROP DATABASE IF EXISTS {qa_db}",
                f"CREATE DATABASE {qa_db}",
            ],
        },
        reset_timer,
    )
    create_timer = _start_timing()
    create_phase = _finish_timing(
        {
            "name": "create_baseline_tables",
            "status": "dry_run",
            "tables": [
                {"table": table_name, "status": "dry_run"}
                for table_name in sorted(baseline_ddl)
            ],
        },
        create_timer,
    )
    ddl_timer = _start_timing()
    ddl_phase = _finish_timing(
        {
            "name": "apply_ddl_changes",
            "status": "dry_run",
            "ddl_changes": [
                _ddl_change_result(change, "dry_run")
                for change in qa_ddl_changes
            ],
        },
        ddl_timer,
    )

    job_phase_timer = _start_timing()
    jobs = []
    for job in jobs_to_run:
        job_timer = _start_timing()
        file_path = root / job["file"]
        actual_values = []
        invocation_count = 0
        invocation_results = [] if timing_detail else None
        if not file_path.exists():
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "skipped",
                        "文件不存在",
                        actual_execution_values=actual_values,
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                    ),
                    job_timer,
                )
            )
            continue
        try:
            spec = planner.task_spec(job["job"], file_path)
            driver_values = _job_driver_values(job, spec)
            for driver_value in driver_values:
                planned_job = _job_for_driver_value(job, driver_value)
                planned_invocations = planner.plan_shadow_job(
                    planned_job,
                    project_root=root,
                )
                if planned_invocations:
                    _append_actual_execution_value(actual_values, driver_value)
                    invocation_count += len(planned_invocations)
                    if invocation_results is not None:
                        for _ in planned_invocations:
                            invocation_timer = _start_timing()
                            invocation_results.append(
                                _finish_timing(
                                    _invocation_result(
                                        driver_value,
                                        "dry_run",
                                    ),
                                    invocation_timer,
                                )
                            )
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "dry_run",
                        actual_execution_values=actual_values,
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                    ),
                    job_timer,
                )
            )
        except ExecutionConfigError as exc:
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "failed",
                        str(exc),
                        actual_execution_values=actual_values,
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                    ),
                    job_timer,
                )
            )
    job_phase_status = (
        "failed"
        if any(job.get("status") == "failed" for job in jobs)
        else "dry_run"
    )

    job_phase = _finish_timing(
        {
            "name": "run_jobs",
            "status": job_phase_status,
            "jobs": jobs,
        },
        job_phase_timer,
    )

    return [reset_phase, create_phase, ddl_phase, job_phase]


def execute_shadow_plan(
    plan: dict, *, dry_run: bool = False, timing_detail: bool = False
) -> dict:
    """Execute or preview a shadow-run validation plan."""
    result_timer = _start_timing()

    def finish_result(result: dict) -> dict:
        return _finish_timing(result, result_timer)

    if dry_run:
        _dry_run(plan)
        phases = _dry_run_phases(plan, timing_detail=timing_detail)
        summary = _result_summary(plan, phases)
        status = "failed" if summary["failed_job_count"] else "dry_run"
        return finish_result(
            _shadow_result(plan, mode="dry_run", status=status, phases=phases)
        )

    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    phases = []

    checks = plan.get("verification", {}).get("checks", [])
    if not _plan_anchor_tables(plan) and not checks:
        print("  警告: 无锚点表且无校验配置")
        print("    作业会正常执行，但后续 compare 命令没有表可对比校验")
        print("    如果只是想确认作业不报错，可继续执行\n")

    print("=" * 60)
    print(f"Phase 0: 重置验证数据库 {qa_db}")
    reset_timer = _start_timing()
    reset_phase = {
        "name": "reset_qa_db",
        "status": "success",
        "actions": [
            f"DROP DATABASE IF EXISTS {qa_db}",
            f"CREATE DATABASE {qa_db}",
        ],
    }
    try:
        run_sql(
            f"DROP DATABASE IF EXISTS {qa_db}",
            "information_schema",
            qa=True,
        )
        run_sql(f"CREATE DATABASE {qa_db}", "information_schema", qa=True)
    except Exception as exc:
        print(f"  [FAIL] 重置验证数据库失败: {exc}")
        reset_phase["status"] = "failed"
        reset_phase["error"] = str(exc)
        _finish_timing(reset_phase, reset_timer)
        phases.append(reset_phase)
        return finish_result(_failed_shadow_result(plan, phases))
    print(f"  {qa_db} 已重建")
    _finish_timing(reset_phase, reset_timer)
    phases.append(reset_phase)

    print(f"\n{'=' * 60}")
    print(f"Phase 1: 基线建表 ({len(baseline_ddl)} 张)")
    create_timer = _start_timing()
    table_results = []
    create_phase = {
        "name": "create_baseline_tables",
        "status": "success",
        "tables": table_results,
    }
    for table_name in sorted(baseline_ddl):
        ddl_raw = baseline_ddl[table_name]
        if not ddl_raw.strip():
            table_results.append({"table": table_name, "status": "skipped"})
            continue
        ddl_qa = ddl_raw.replace(f"{prod_db}.", f"{qa_db}.")
        try:
            run_sql(ddl_qa, qa_db, qa=True)
            print(f"  [CREATE] {qa_db}.{table_name}")
            table_results.append({"table": table_name, "status": "success"})
        except Exception as exc:
            print(f"  [FAIL] {qa_db}.{table_name}: {exc}")
            table_results.append(
                {"table": table_name, "status": "failed", "error": str(exc)}
            )
            create_phase["status"] = "failed"
            _finish_timing(create_phase, create_timer)
            phases.append(create_phase)
            return finish_result(_failed_shadow_result(plan, phases))
    _finish_timing(create_phase, create_timer)
    phases.append(create_phase)

    ddl_change_results = []
    ddl_timer = _start_timing()
    ddl_phase = {
        "name": "apply_ddl_changes",
        "status": "success",
        "ddl_changes": ddl_change_results,
    }
    if ddl_changes:
        print(f"\n{'-' * 60}")
        print(f"Phase 2: 应用 DDL 变更 ({len(ddl_changes)} 条)")
        for change in ddl_changes:
            qa_change = _qa_ddl_change(change, prod_db, qa_db)
            sql = qa_change.get("sql", "")
            if not sql.strip():
                ddl_change_results.append(
                    _ddl_change_result(qa_change, "skipped")
                )
                continue
            statements = _ddl_change_statements(sql)
            statement_results = []
            try:
                for statement in statements:
                    try:
                        _execute_ddl_statement(statement, qa_db)
                    except Exception as exc:
                        statement_results.append(
                            _ddl_statement_result(
                                statement,
                                "failed",
                                str(exc),
                            )
                        )
                        raise
                    statement_results.append(
                        _ddl_statement_result(statement, "success")
                    )
                print(
                    f"  [{qa_change.get('change_type')}] "
                    f"{qa_change.get('table_name', '?')}"
                )
                ddl_change_results.append(
                    _ddl_change_result(
                        qa_change,
                        "success",
                        statement_results=(
                            statement_results
                            if len(statement_results) > 1
                            else None
                        ),
                    )
                )
            except Exception as exc:
                print(f"  [FAIL] {qa_change.get('change_type')}: {exc}")
                ddl_change_results.append(
                    _ddl_change_result(
                        qa_change,
                        "failed",
                        str(exc),
                        statement_results=(
                            statement_results
                            if len(statements) > 1
                            or len(statement_results) > 1
                            else None
                        ),
                    )
                )
                ddl_phase["status"] = "failed"
                _finish_timing(ddl_phase, ddl_timer)
                phases.append(ddl_phase)
                return finish_result(_failed_shadow_result(plan, phases))
    _finish_timing(ddl_phase, ddl_timer)
    phases.append(ddl_phase)

    print(f"\n{'=' * 60}")
    print(f"Phase 3: 执行作业 ({len(jobs_to_run)} 个)")
    job_phase_timer = _start_timing()
    recalculated = set()
    root = _project_root()
    planner = ExecutionPlanner(plan["project"], project_root=root)
    job_results = []
    job_phase = {
        "name": "run_jobs",
        "status": "success",
        "jobs": job_results,
    }

    executor = ShadowSqlExecutor(
        prod_db=prod_db,
        qa_db=qa_db,
        recalculated=recalculated,
        rewrite_sql=rewrite_sql,
        run_sql_text=run_sql_text,
    )
    for idx, job in enumerate(jobs_to_run, 1):
        job_name = job["job"]
        job_file = job["file"]
        layer = job.get("layer", "?")
        actual_values = []
        invocation_count = 0
        invocation_results = [] if timing_detail else None
        job_timer = _start_timing()

        print(f"\n  --- {idx}/{len(jobs_to_run)}: [{layer}] {job_name} ---")
        file_path = root / job_file
        if not file_path.exists():
            error = f"文件不存在: {file_path}"
            print(f"  [FAIL] {error}")
            job_results.append(
                _finish_timing(
                    _job_result(
                        job,
                        "failed",
                        error,
                        actual_execution_values=actual_values,
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                    ),
                    job_timer,
                )
            )
            job_phase["status"] = "failed"
            _finish_timing(job_phase, job_phase_timer)
            phases.append(job_phase)
            return finish_result(_failed_shadow_result(plan, phases))

        try:
            spec = planner.task_spec(job_name, file_path)
            driver_values = _job_driver_values(job, spec)
        except ExecutionConfigError as exc:
            print(f"  [FAIL] {job_name}: {exc}")
            job_results.append(
                _finish_timing(
                    _job_result(
                        job,
                        "failed",
                        str(exc),
                        actual_execution_values=actual_values,
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                    ),
                    job_timer,
                )
            )
            job_phase["status"] = "failed"
            _finish_timing(job_phase, job_phase_timer)
            phases.append(job_phase)
            return finish_result(_failed_shadow_result(plan, phases))

        for driver_idx, driver_value in enumerate(driver_values, 1):
            if driver_value is not None:
                print(
                    f"\n  === replay slice "
                    f"{driver_idx}/{len(driver_values)}: "
                    f"{driver_value} ==="
                )
            planned_job = _job_for_driver_value(job, driver_value)

            try:
                invocations = planner.plan_shadow_job(
                    planned_job,
                    project_root=root,
                )
            except ExecutionConfigError as exc:
                print(f"  [FAIL] {job_name}: {exc}")
                job_results.append(
                    _finish_timing(
                        _job_result(
                            job,
                            "failed",
                            str(exc),
                            actual_execution_values=actual_values,
                            invocation_count=invocation_count,
                            invocations=invocation_results,
                        ),
                        job_timer,
                    )
                )
                job_phase["status"] = "failed"
                _finish_timing(job_phase, job_phase_timer)
                phases.append(job_phase)
                return finish_result(_failed_shadow_result(plan, phases))

            try:
                for invocation in invocations:
                    _append_actual_execution_value(actual_values, driver_value)
                    invocation_count += 1
                    invocation_timer = _start_timing()
                    try:
                        executor.execute(invocation)
                    except Exception as exc:
                        if invocation_results is not None:
                            invocation_results.append(
                                _finish_timing(
                                    _invocation_result(
                                        driver_value,
                                        "failed",
                                        str(exc),
                                    ),
                                    invocation_timer,
                                )
                            )
                        raise
                    if invocation_results is not None:
                        invocation_results.append(
                            _finish_timing(
                                _invocation_result(driver_value, "success"),
                                invocation_timer,
                            )
                        )
                print(f"  + {qa_db}.{job_name}")
            except Exception as exc:
                print(f"  [FAIL] {job_name}: {exc}")
                job_results.append(
                    _finish_timing(
                        _job_result(
                            job,
                            "failed",
                            str(exc),
                            actual_execution_values=actual_values,
                            invocation_count=invocation_count,
                            invocations=invocation_results,
                        ),
                        job_timer,
                    )
                )
                job_phase["status"] = "failed"
                _finish_timing(job_phase, job_phase_timer)
                phases.append(job_phase)
                return finish_result(_failed_shadow_result(plan, phases))

            recalculated.add(job_name)

        job_results.append(
            _finish_timing(
                _job_result(
                    job,
                    "success",
                    actual_execution_values=actual_values,
                    invocation_count=invocation_count,
                    invocations=invocation_results,
                ),
                job_timer,
            )
        )
    _finish_timing(job_phase, job_phase_timer)
    phases.append(job_phase)

    print(f"\n{'=' * 60}")
    print(
        f"Shadow run 完成! 共执行 {len(jobs_to_run)} 个作业, 目标库: {qa_db}"
    )
    return finish_result(
        _shadow_result(
            plan,
            mode="execute",
            status="completed",
            phases=phases,
        )
    )


def run_shadow_plan(
    plan_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
    timing_detail: bool = False,
) -> dict:
    """Run or dry-run a validation plan and write the execution result."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    result = execute_shadow_plan(
        plan, dry_run=dry_run, timing_detail=timing_detail
    )
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
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    root = _project_root()
    planner = ExecutionPlanner(plan["project"], project_root=root)

    print(f"{'=' * 60}")
    print("=== SHADOW RUN DRY RUN ===")
    print(f"  项目: {plan['project']}")
    git_info = plan.get("git") or {}
    if git_info:
        print(f"  分支: {git_info.get('branch', '')}")
        merge_base = str(git_info.get("merge_base") or "")
        print(f"  基线: {merge_base[:12]}...")
    print(f"  生产库: {prod_db} -> 验证库: {qa_db}")
    print(f"  锚点: {_plan_anchor_tables(plan)}")
    verification = plan.get("verification", {})
    compare_anchors = verification.get("compare_anchors") or {}
    if compare_anchors:
        for table in sorted(compare_anchors):
            anchor = compare_anchors[table] or {}
            time_column = anchor.get("time_column")
            anchor_value = anchor.get("anchor_time_value")
            time_period = anchor.get("time_period")
            if time_column and anchor_value:
                print(
                    f"  对比范围: {table} "
                    f"WHERE {time_column} = '{anchor_value}' ({time_period})"
                )
            else:
                print(f"  对比范围: {table} 全表")
    else:
        partition_info = plan.get("partition_info", {})
        print(f"  分区: {partition_info.get('partition', 'N/A')}")
    checks = plan.get("verification", {}).get("checks", [])
    if not _plan_anchor_tables(plan) and not checks:
        print()
        print(
            "  警告: 无锚点表且无校验配置，后续 compare 命令没有表可对比校验"
        )

    print("\n--- Phase 0: 重置验证库 ---")
    print(f"  DROP DATABASE IF EXISTS {qa_db}")
    print(f"  CREATE DATABASE {qa_db}")

    print(f"\n--- Phase 1: 基线建表 ({len(baseline_ddl)} 张) ---")
    for table_name in sorted(baseline_ddl):
        print(f"  [CREATE] {qa_db}.{table_name}")

    print(f"\n--- Phase 2: DDL 变更 ({len(ddl_changes)} 条) ---")
    for change in ddl_changes:
        qa_change = _qa_ddl_change(change, prod_db, qa_db)
        name = qa_change.get("table_name", qa_change.get("old_name", "?"))
        print(f"  [{qa_change['change_type']}] {name}")
        for statement in _ddl_change_statements(qa_change.get("sql", "")):
            print(f"    {statement}")

    print(f"\n--- Phase 3: 作业 ({len(jobs_to_run)} 个) ---")
    recalculated = set()
    executor = ShadowSqlExecutor(
        prod_db=prod_db,
        qa_db=qa_db,
        recalculated=recalculated,
        rewrite_sql=rewrite_sql,
        run_sql_text=run_sql_text,
    )
    for idx, job in enumerate(jobs_to_run, 1):
        job_name = job["job"]
        layer = job.get("layer", "?")
        job_file = job["file"]
        file_path = root / job_file

        print(f"\n  {idx}/{len(jobs_to_run)}: [{layer}] {job_name}")
        if not file_path.exists():
            print("    [SKIP] 文件不存在")
            continue

        try:
            spec = planner.task_spec(job_name, file_path)
            driver_values = _job_driver_values(job, spec)
        except ExecutionConfigError as exc:
            print(f"    [FAIL] {exc}")
            continue

        for driver_idx, driver_value in enumerate(driver_values, 1):
            if driver_value is not None:
                print(
                    f"\n    === replay slice "
                    f"{driver_idx}/{len(driver_values)}: "
                    f"{driver_value} ==="
                )
            planned_job = _job_for_driver_value(job, driver_value)

            try:
                invocations = planner.plan_shadow_job(
                    planned_job,
                    project_root=root,
                )
            except ExecutionConfigError as exc:
                print(f"    [FAIL] {exc}")
                continue

            for invocation in invocations:
                print(
                    f"    strategy={invocation.strategy}, "
                    f"full_refresh={int(invocation.full_refresh)}, "
                    f"sql={invocation.sql_path}"
                )
                rendered = executor.render(invocation)
                for line in rendered.splitlines()[:8]:
                    print(f"    {line}")
                total = len(rendered.splitlines())
                if total > 8:
                    print(f"    ... ({total} 行)")

            recalculated.add(job_name)

    if checks:
        print(f"\n--- 校验检查 ({len(checks)} 项) ---")
        verification = plan.get("verification", {})
        for raw_check in checks:
            check = _check_with_compare_anchor(raw_check, verification)
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
    parser.add_argument(
        "--timing-detail",
        "--profile",
        action="store_true",
        dest="timing_detail",
        help="记录每次 job invocation/slice 的耗时明细",
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
    result = run_shadow_plan(
        plan_path,
        output_path,
        dry_run=args.dry_run,
        timing_detail=args.timing_detail,
    )
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
