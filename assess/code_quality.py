"""SQL task code quality checks for assess."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    finalize_dimension,
    make_check,
    rule_meta,
)

RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP = "TEMP_TABLE_NAME_HAS_TEMP_OR_TMP"
RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK = "TEMP_TABLE_DROPPED_IN_SAME_TASK"
RULE_NO_SELECT_STAR_IN_WRITE = "NO_SELECT_STAR_IN_WRITE"

CODE_RULE_TEMP_TABLE_NAME = "CODE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP"
CODE_RULE_TEMP_TABLE_DROPPED = "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK"
CODE_RULE_NO_SELECT_STAR = "CODE_NO_SELECT_STAR_IN_WRITE"

CODE_QUALITY_RULES = {
    CODE_RULE_TEMP_TABLE_NAME: rule_meta(
        name="临时表名包含temp/tmp",
        severity=SEVERITY_LOW,
        title="临时表命名不清晰",
        remediation_summary="将临时表名调整为包含temp或tmp的名称",
        strategy="rename_temp_table",
        edit_scope=["tasks"],
    ),
    CODE_RULE_TEMP_TABLE_DROPPED: rule_meta(
        name="临时表在同一作业清理",
        severity=SEVERITY_MEDIUM,
        title="临时表未在同一作业清理",
        remediation_summary="在创建临时表后的同一作业中补充DROP TABLE清理语句",
        strategy="drop_temp_table_after_use",
        edit_scope=["tasks"],
    ),
    CODE_RULE_NO_SELECT_STAR: rule_meta(
        name="写入型语句不使用SELECT *",
        severity=SEVERITY_HIGH,
        title="写入型SQL使用SELECT *",
        remediation_summary="将写入型SQL中的SELECT *改为显式字段列表",
        strategy="expand_select_star",
        edit_scope=["tasks"],
    ),
}


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
        checks=[],
    )


def _record_check(
    result: dict,
    rule: str,
    file_name: str,
    table_name: str,
    ok: bool,
    message: str,
) -> None:
    if rule == RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP:
        rule_id = CODE_RULE_TEMP_TABLE_NAME
        expected = "临时表名包含temp或tmp"
        actual = (
            f"临时表名 {table_name} 符合要求"
            if ok
            else f"临时表名 {table_name} 未包含temp/tmp"
        )
        target_type = "table"
        target = table_name
    elif rule == RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK:
        rule_id = CODE_RULE_TEMP_TABLE_DROPPED
        expected = "临时表在同一作业后续DROP清理"
        actual = "已清理" if ok else "未在同一作业后续DROP清理"
        target_type = "table"
        target = table_name
    else:
        rule_id = CODE_RULE_NO_SELECT_STAR
        expected = "写入型语句显式列出字段"
        actual = (
            f"写入 {table_name} 时显式列出字段"
            if ok
            else f"写入 {table_name} 时使用 SELECT *"
        )
        target_type = "task"
        target = file_name

    result["checks"].append(
        make_check(
            rule_id=rule_id,
            target_type=target_type,
            target=target,
            passed=ok,
            expected=expected,
            actual=actual,
            evidence={"file": file_name, "table": table_name},
            message=message if not ok else "",
        )
    )


def _finalize_result(result: dict) -> dict:
    checks = result["checks"]
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="code_quality",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=CODE_QUALITY_RULES,
    )


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
