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
CODE_RULE_CARTESIAN_JOIN_RISK = "CODE_CARTESIAN_JOIN_RISK"
CODE_RULE_DWS_JOIN_BEFORE_AGGREGATION = "CODE_DWS_JOIN_BEFORE_AGGREGATION"
CODE_RULE_FILTER_COLUMN_WRAPPED = "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION"

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
    CODE_RULE_CARTESIAN_JOIN_RISK: rule_meta(
        name="JOIN条件避免笛卡尔积风险",
        severity=SEVERITY_HIGH,
        title="JOIN存在笛卡尔积风险",
        remediation_summary="补充明确JOIN条件，避免缺失ON/USING、逗号JOIN或ON常量条件",
        strategy="fix_cartesian_join_condition",
        edit_scope=["tasks"],
    ),
    CODE_RULE_DWS_JOIN_BEFORE_AGGREGATION: rule_meta(
        name="DWS聚合前JOIN需确认粒度",
        severity=SEVERITY_HIGH,
        title="DWS聚合前JOIN存在fanout风险",
        remediation_summary="先将明细侧预聚合到目标粒度，或确认JOIN键保持一对一",
        strategy="pre_aggregate_before_join",
        edit_scope=["tasks", "models"],
    ),
    CODE_RULE_FILTER_COLUMN_WRAPPED: rule_meta(
        name="过滤列不被函数或CAST包裹",
        severity=SEVERITY_HIGH,
        title="过滤列被函数或CAST包裹",
        remediation_summary="将函数转换为边界值，保持WHERE中的分区/过滤列裸列比较",
        strategy="rewrite_sargable_filter",
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


def _split_statements(sql: str) -> list[str]:
    return [
        statement.strip()
        for statement in str(sql or "").split(";")
        if statement.strip()
    ]


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", " ", str(sql or "")).replace("\r", "\n")


def _strip_line_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", " ", _strip_sql_comments(sql))


def _strip_string_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", str(sql or ""))


def _from_clause_has_top_level_comma(statement: str) -> bool:
    sql = _strip_string_literals(_strip_line_comments(statement))
    for match in re.finditer(r"\bFROM\b", sql, flags=re.IGNORECASE):
        depth = 0
        for index in range(match.end(), len(sql)):
            char = sql[index]
            if char == "(":
                depth += 1
                continue
            if char == ")":
                if depth == 0:
                    break
                depth -= 1
                continue
            if depth != 0:
                continue
            if char == ",":
                return True
            rest = sql[index:]
            if re.match(
                r"\s+(WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|QUALIFY|"
                r"UNION|EXCEPT|INTERSECT)\b",
                rest,
                flags=re.IGNORECASE,
            ):
                break
    return False


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
        if isinstance(current, exp.Column) and isinstance(
            current.this, exp.Star
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


def _join_has_condition(join: exp.Join) -> bool:
    return bool(join.args.get("on") or join.args.get("using"))


def _is_explicit_cross_join(join: exp.Join) -> bool:
    return str(join.args.get("kind") or "").upper() == "CROSS"


def _is_constant_join_condition(condition) -> bool:
    if condition is None:
        return False
    if isinstance(condition, exp.Boolean):
        return condition.this is True
    if isinstance(condition, exp.EQ):
        left = condition.this
        right = condition.expression
        if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
            return left.this == right.this
    return False


def _join_display_name(join: exp.Join) -> str:
    return _short_table_name(join.this.sql(dialect="doris"))


def _scan_cartesian_join_risks(sql: str) -> list[dict]:
    issues = []
    for statement_index, raw_statement in enumerate(_split_statements(sql)):
        has_comma_join = _from_clause_has_top_level_comma(raw_statement)
        if has_comma_join:
            issues.append(
                {
                    "reason": "comma_join",
                    "statement_index": statement_index,
                    "detail": "FROM子句存在顶层逗号JOIN",
                }
            )

        parsed = _parse_statements(raw_statement)
        if not parsed:
            continue
        for statement in parsed:
            for select_expr in statement.find_all(exp.Select):
                for join in select_expr.args.get("joins") or []:
                    if _is_explicit_cross_join(join):
                        continue
                    condition = join.args.get("on")
                    if _is_constant_join_condition(condition):
                        issues.append(
                            {
                                "reason": "constant_join_condition",
                                "statement_index": statement_index,
                                "join_table": _join_display_name(join),
                                "detail": condition.sql(dialect="doris"),
                            }
                        )
                    elif not _join_has_condition(join) and not has_comma_join:
                        issues.append(
                            {
                                "reason": "missing_join_condition",
                                "statement_index": statement_index,
                                "join_table": _join_display_name(join),
                                "detail": "JOIN缺少ON/USING条件",
                            }
                        )
    return issues


def _nearest_select(expression: exp.Expression) -> exp.Select | None:
    parent = expression.parent
    while parent is not None:
        if isinstance(parent, exp.Select):
            return parent
        parent = parent.parent
    return None


def _same_select_aggregate_count(select_expr: exp.Select) -> int:
    return sum(
        1
        for aggregate in select_expr.find_all(exp.AggFunc)
        if _nearest_select(aggregate) is select_expr
    )


def _select_has_join_and_aggregation(select_expr: exp.Select) -> bool:
    return bool(select_expr.args.get("joins")) and bool(
        _same_select_aggregate_count(select_expr)
    )


def _join_right_table_name(join: exp.Join) -> str:
    target = join.this
    if isinstance(target, exp.Table):
        return _short_table_name(target.name)
    return ""


def _join_right_alias(join: exp.Join) -> str:
    target = join.this
    alias_or_name = getattr(target, "alias_or_name", "")
    return _short_table_name(alias_or_name)


def _column_belongs_to_alias(column: exp.Column, alias: str) -> bool:
    if not alias:
        return False
    return _short_table_name(column.table).lower() == alias.lower()


def _right_join_condition_columns(join: exp.Join) -> set[str]:
    alias = _join_right_alias(join)
    columns = set()

    for using_column in join.args.get("using") or []:
        columns.add(_short_table_name(using_column.name).lower())

    condition = join.args.get("on")
    if not condition:
        return columns

    for equality in condition.find_all(exp.EQ):
        for side in (equality.this, equality.expression):
            if isinstance(side, exp.Column) and _column_belongs_to_alias(
                side,
                alias,
            ):
                columns.add(_short_table_name(side.name).lower())
    return columns


def _unique_key_columns_for_table(
    asset_catalog: dict | None,
    table_name: str,
) -> set[str]:
    table_asset = ((asset_catalog or {}).get("tables") or {}).get(
        _short_table_name(table_name)
    ) or {}
    ddl = table_asset.get("ddl") or {}
    key_type = str(ddl.get("key_type") or "").upper()
    if key_type not in {"PRIMARY", "UNIQUE"}:
        return set()
    return {
        _short_table_name(column).lower()
        for column in ddl.get("key_columns") or []
        if _short_table_name(column)
    }


def _join_is_proven_many_to_one(
    join: exp.Join,
    asset_catalog: dict | None,
) -> bool:
    right_table = _join_right_table_name(join)
    unique_key_columns = _unique_key_columns_for_table(
        asset_catalog,
        right_table,
    )
    if not unique_key_columns:
        return False
    return unique_key_columns.issubset(_right_join_condition_columns(join))


def _unproven_join_count(
    select_expr: exp.Select,
    asset_catalog: dict | None,
) -> int:
    return sum(
        1
        for join in select_expr.args.get("joins") or []
        if not _join_is_proven_many_to_one(join, asset_catalog)
    )


def _scan_join_before_aggregation(
    sql: str,
    asset_catalog: dict | None = None,
) -> list[dict]:
    issues = []
    for statement_index, statement in enumerate(_parse_statements(sql)):
        for select_expr in statement.find_all(exp.Select):
            if not _select_has_join_and_aggregation(select_expr):
                continue
            unproven_join_count = _unproven_join_count(
                select_expr,
                asset_catalog,
            )
            if not unproven_join_count:
                continue
            total_join_count = len(select_expr.args.get("joins") or [])
            issues.append(
                {
                    "reason": "join_before_aggregation",
                    "statement_index": statement_index,
                    "join_count": unproven_join_count,
                    "total_join_count": total_join_count,
                    "proven_unique_join_count": (
                        total_join_count - unproven_join_count
                    ),
                    "aggregate_count": _same_select_aggregate_count(
                        select_expr
                    ),
                }
            )
    return issues


def _function_name(expression: exp.Expression) -> str:
    sql_name = getattr(expression, "sql_name", None)
    if callable(sql_name):
        return str(sql_name()).upper()
    return expression.key.upper()


def _is_filter_column_wrapper(expression: exp.Expression) -> bool:
    if not isinstance(expression, exp.Func):
        return False
    if isinstance(expression, (exp.Connector, exp.Predicate)):
        return False
    if isinstance(expression, (exp.DateAdd, exp.DateSub)):
        return isinstance(expression.args.get("this"), exp.Column)
    return any(
        isinstance(child, exp.Column)
        for child in expression.iter_expressions()
    )


def _column_names(expression: exp.Expression) -> list[str]:
    return sorted(
        {
            _short_table_name(column.sql(dialect="doris"))
            for column in expression.find_all(exp.Column)
        }
    )


def _scan_wrapped_filter_columns(sql: str) -> list[dict]:
    issues = []
    for statement_index, statement in enumerate(_parse_statements(sql)):
        for select_expr in statement.find_all(exp.Select):
            where = select_expr.args.get("where")
            if not where:
                continue
            for function in where.find_all(exp.Func):
                if not _is_filter_column_wrapper(function):
                    continue
                columns = _column_names(function)
                if not columns:
                    continue
                issues.append(
                    {
                        "reason": "function_wrapped_filter_column",
                        "statement_index": statement_index,
                        "function": _function_name(function),
                        "columns": columns,
                        "detail": function.sql(dialect="doris"),
                    }
                )
    return issues


def _temp_name_is_valid(table_name: str) -> bool:
    lowered = table_name.lower()
    return "temp" in lowered or "tmp" in lowered


def _is_dws_task(task: dict, asset_catalog: dict) -> bool:
    expected_table = _short_table_name(task.get("expected_table") or "")
    if expected_table.lower().startswith("dws_"):
        return True
    table_asset = (asset_catalog.get("tables") or {}).get(expected_table) or {}
    return str(table_asset.get("layer") or "").upper() == "DWS"


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


def _record_issue_check(
    result: dict,
    rule_id: str,
    file_name: str,
    table_name: str,
    expected: str,
    actual: str,
    message: str,
    evidence: dict,
) -> None:
    full_evidence = {"file": file_name, "table": table_name}
    full_evidence.update(evidence)
    result["checks"].append(
        make_check(
            rule_id=rule_id,
            target_type="task",
            target=file_name,
            passed=False,
            expected=expected,
            actual=actual,
            evidence=full_evidence,
            message=message,
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
        statement.strip() for statement in sql.split(";") if statement.strip()
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
            drops.append(
                {
                    "table": _short_table_name(drop_match.group(1)),
                    "index": index,
                }
            )

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
            creates.append(
                {
                    "table": _target_table_name(stmt.this),
                    "index": index,
                }
            )
        elif _is_table_drop(stmt):
            drops.append(
                {
                    "table": _target_table_name(stmt.this),
                    "index": index,
                }
            )

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

        for issue in _scan_cartesian_join_risks(sql):
            _record_issue_check(
                result,
                CODE_RULE_CARTESIAN_JOIN_RISK,
                file_name,
                expected_table,
                "JOIN具备明确ON/USING条件且不使用隐式笛卡尔积",
                f"存在{issue['reason']}",
                "JOIN存在笛卡尔积风险，请补充明确关联条件",
                issue,
            )

        if _is_dws_task(task, asset_catalog):
            for issue in _scan_join_before_aggregation(sql, asset_catalog):
                _record_issue_check(
                    result,
                    CODE_RULE_DWS_JOIN_BEFORE_AGGREGATION,
                    file_name,
                    expected_table,
                    "DWS聚合前JOIN已确认一对一或先预聚合",
                    "DWS作业存在JOIN后直接聚合",
                    "DWS聚合前JOIN可能放大明细行，需确认粒度或先预聚合",
                    issue,
                )

        for issue in _scan_wrapped_filter_columns(sql):
            _record_issue_check(
                result,
                CODE_RULE_FILTER_COLUMN_WRAPPED,
                file_name,
                expected_table,
                "WHERE中的分区/过滤列保持裸列比较",
                f"过滤列被{issue['function']}包裹: {issue['detail']}",
                "过滤列被函数或CAST包裹，可能导致分区/索引裁剪失效",
                issue,
            )

    return _finalize_result(result)
