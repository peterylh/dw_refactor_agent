"""SQL task code quality checks for assess."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP = "TEMP_TABLE_NAME_HAS_TEMP_OR_TMP"
RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK = "TEMP_TABLE_DROPPED_IN_SAME_TASK"
RULE_NO_SELECT_STAR_IN_WRITE = "NO_SELECT_STAR_IN_WRITE"


def _short_table_name(table_name: str) -> str:
    name = str(table_name or "").strip().rstrip(";")
    if not name:
        return ""
    name = name.replace("`", "").replace('"', "")
    return name.split(".")[-1].strip()


def _target_table_name(target_expr) -> str:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if target_expr is None:
        return ""
    return _short_table_name(target_expr.sql(dialect="doris"))


def _display_file_path(project_dir: Path | None, file_path: Path) -> str:
    if not project_dir:
        return str(file_path)
    try:
        return file_path.relative_to(project_dir.parent).as_posix()
    except ValueError:
        return file_path.as_posix()


def _parse_statements(sql: str) -> list:
    try:
        return sqlglot.parse(sql, dialect="doris")
    except Exception:
        return []


def _is_table_create(stmt) -> bool:
    return (
        isinstance(stmt, exp.Create)
        and str(stmt.args.get("kind") or "").upper() == "TABLE"
    )


def _is_table_drop(stmt) -> bool:
    return (
        isinstance(stmt, exp.Drop)
        and str(stmt.args.get("kind") or "").upper() == "TABLE"
    )


def _select_has_star_projection(select_expr) -> bool:
    if not isinstance(select_expr, exp.Select):
        return False

    for projection in select_expr.expressions:
        current = (
            projection.this
            if isinstance(projection, exp.Alias)
            else projection
        )
        if isinstance(current, exp.Star):
            return True
        if (
            isinstance(current, exp.Column)
            and isinstance(current.this, exp.Star)
        ):
            return True
    return False


def _write_expression_has_select_star(expression) -> bool:
    if expression is None:
        return False
    if isinstance(expression, exp.Select):
        return _select_has_star_projection(expression)
    return any(
        _select_has_star_projection(select_expr)
        for select_expr in expression.find_all(exp.Select)
    )


def _write_statement_target_and_expression(stmt) -> tuple[str, object] | None:
    if isinstance(stmt, exp.Insert):
        return _target_table_name(stmt.this), stmt.expression
    if _is_table_create(stmt) and stmt.args.get("expression") is not None:
        return _target_table_name(stmt.this), stmt.args.get("expression")
    return None


def _temp_name_is_valid(table_name: str) -> bool:
    lowered = table_name.lower()
    return "temp" in lowered or "tmp" in lowered


def _empty_result() -> dict:
    return dict(
        score=100.0,
        passed=0,
        total=0,
        rule_summary={},
        details=[],
    )


def _record_check(
    result: dict,
    rule: str,
    file_name: str,
    table_name: str,
    ok: bool,
    message: str,
) -> None:
    result["total"] += 1
    summary = result["rule_summary"].setdefault(
        rule,
        {"pass_count": 0, "total": 0},
    )
    summary["total"] += 1

    if ok:
        result["passed"] += 1
        summary["pass_count"] += 1
        return

    result["details"].append(
        dict(
            file=file_name,
            table=table_name,
            rule=rule,
            message=message,
        )
    )


def _finalize_result(result: dict) -> dict:
    result["score"] = (
        round(result["passed"] / result["total"] * 100, 1)
        if result["total"] else 100.0
    )
    for summary in result["rule_summary"].values():
        total = summary["total"]
        summary["pct"] = (
            round(summary["pass_count"] / total * 100, 1)
            if total else 0
        )
    return result


def _fallback_scan(sql: str) -> tuple[list[dict], list[dict], list[dict]]:
    creates = []
    drops = []
    write_statements = []
    statements = [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]
    for index, statement in enumerate(statements):
        create_match = re.search(
            r"\bCREATE\s+(?:TEMPORARY\s+)?TABLE\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?(?:`?\w+`?\.)?`?(\w+)`?",
            statement,
            flags=re.IGNORECASE,
        )
        if create_match:
            table = _short_table_name(create_match.group(1))
            creates.append({"table": table, "index": index})
            is_ctas = bool(
                re.search(
                    r"\bAS\s+SELECT\b",
                    statement,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            )
            if is_ctas:
                has_star = bool(
                    re.search(
                        r"\bAS\s+SELECT\s+(?:`?\w+`?\.)?\*",
                        statement,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                )
                write_statements.append(
                    {"table": table, "has_select_star": has_star}
                )

        drop_match = re.search(
            r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?"
            r"(?:`?\w+`?\.)?`?(\w+)`?",
            statement,
            flags=re.IGNORECASE,
        )
        if drop_match:
            drops.append({
                "table": _short_table_name(drop_match.group(1)),
                "index": index,
            })

        insert_match = re.search(
            r"\bINSERT\s+(?:OVERWRITE\s+TABLE|INTO)\s+"
            r"(?:`?\w+`?\.)?`?(\w+)`?",
            statement,
            flags=re.IGNORECASE,
        )
        if insert_match:
            has_star = bool(
                re.search(
                    r"\bSELECT\s+(?:`?\w+`?\.)?\*",
                    statement,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            )
            write_statements.append(
                {
                    "table": _short_table_name(insert_match.group(1)),
                    "has_select_star": has_star,
                }
            )
    return creates, drops, write_statements


def _scan_task_sql(sql: str) -> tuple[list[dict], list[dict], list[dict]]:
    statements = _parse_statements(sql)
    if not statements:
        return _fallback_scan(sql)

    creates = []
    drops = []
    write_statements = []
    for index, stmt in enumerate(statements):
        if _is_table_create(stmt):
            creates.append({
                "table": _target_table_name(stmt.this),
                "index": index,
            })
        elif _is_table_drop(stmt):
            drops.append({
                "table": _target_table_name(stmt.this),
                "index": index,
            })

        write_target = _write_statement_target_and_expression(stmt)
        if write_target:
            target, expression = write_target
            write_statements.append(
                {
                    "table": target,
                    "has_select_star": _write_expression_has_select_star(
                        expression
                    ),
                }
            )

    return creates, drops, write_statements


def score_code_quality(asset_catalog: dict) -> dict:
    """Score task SQL code quality checks."""
    result = _empty_result()
    project_dir = asset_catalog.get("project_dir")

    for task in asset_catalog.get("tasks") or []:
        task_path = Path(task["path"])
        file_name = _display_file_path(project_dir, task_path)
        sql = task_path.read_text(encoding="utf-8")
        creates, drops, write_statements = _scan_task_sql(sql)
        expected_table = _short_table_name(task.get("expected_table") or "")

        drop_indexes_by_table = defaultdict(list)
        for drop in drops:
            table = _short_table_name(drop.get("table") or "")
            if table:
                drop_indexes_by_table[table.lower()].append(drop["index"])

        for create in creates:
            table = _short_table_name(create.get("table") or "")
            if not table or table.lower() == expected_table.lower():
                continue

            _record_check(
                result,
                RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP,
                file_name,
                table,
                _temp_name_is_valid(table),
                "临时表名未包含temp/tmp",
            )
            dropped_after_create = any(
                drop_index > create["index"]
                for drop_index in drop_indexes_by_table.get(table.lower(), [])
            )
            _record_check(
                result,
                RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK,
                file_name,
                table,
                dropped_after_create,
                "临时表未在同一作业后续DROP清理",
            )

        for write_statement in write_statements:
            table = _short_table_name(write_statement.get("table") or "")
            _record_check(
                result,
                RULE_NO_SELECT_STAR_IN_WRITE,
                file_name,
                table,
                not write_statement["has_select_star"],
                "写入型语句使用SELECT *，请显式列出字段",
            )

    return _finalize_result(result)
