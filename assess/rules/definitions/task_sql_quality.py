"""SQL task code quality rule definitions."""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
from sqlglot import exp

from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    make_check,
    rule_meta,
)
from assess.rules.engine.base import AssessRule

RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP = "TEMP_TABLE_NAME_HAS_TEMP_OR_TMP"
RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK = "TEMP_TABLE_DROPPED_IN_SAME_TASK"
RULE_NO_SELECT_STAR_IN_WRITE = "NO_SELECT_STAR_IN_WRITE"

CODE_RULE_TEMP_TABLE_NAME = "CODE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP"
CODE_RULE_TEMP_TABLE_DROPPED = "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK"
CODE_RULE_NO_SELECT_STAR = "CODE_NO_SELECT_STAR_IN_WRITE"
CODE_RULE_CARTESIAN_JOIN_RISK = "CODE_CARTESIAN_JOIN_RISK"
CODE_RULE_DWS_JOIN_BEFORE_AGGREGATION = "CODE_DWS_JOIN_BEFORE_AGGREGATION"
CODE_RULE_FILTER_COLUMN_WRAPPED = "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION"
CODE_RULE_TEMP_TABLE_PRE_DROP_NOT_CLEANED = (
    "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED"
)
CODE_RULE_TEMP_TABLE_USED_ACROSS_TASKS = "CODE_TEMP_TABLE_USED_ACROSS_TASKS"

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
    CODE_RULE_TEMP_TABLE_PRE_DROP_NOT_CLEANED: rule_meta(
        name="DROP后CREATE临时/过程表需后续清理",
        severity=SEVERITY_MEDIUM,
        title="伪临时表生命周期未闭合",
        remediation_summary=(
            "在CREATE后的同一作业补充DROP TABLE，或改为正式中间层资产"
        ),
        strategy="close_pseudo_temp_table_lifecycle",
        edit_scope=["tasks", "models", "ddl"],
    ),
    CODE_RULE_TEMP_TABLE_USED_ACROSS_TASKS: rule_meta(
        name="临时/过程表不跨task复用",
        severity=SEVERITY_HIGH,
        title="临时/过程表形成跨task依赖",
        remediation_summary=(
            "将跨task复用的临时/过程表治理为正式中间层资产，或收敛到同一task内"
        ),
        strategy="promote_pseudo_temp_table_to_governed_asset",
        edit_scope=["tasks", "models", "ddl"],
    ),
}


class CodeTempTableNameHasTempOrTmpRule(AssessRule):
    rule_id = CODE_RULE_TEMP_TABLE_NAME
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        checks = []
        governed_tables = rule_context.get("governed_tables") or set()
        for create in target["creates"]:
            table_name = _short_table_name(create.get("table") or "")
            if (
                not table_name
                or table_name.lower() == target["expected_table"].lower()
                or table_name.lower() in governed_tables
            ):
                continue
            checks.append(self._check(target["file_name"], table_name))
        return checks

    def _check(self, file_name: str, table_name: str) -> dict:
        ok = _temp_name_is_valid(table_name)
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=ok,
            expected="临时表名包含temp或tmp",
            actual=(
                f"临时表名 {table_name} 符合要求"
                if ok
                else f"临时表名 {table_name} 未包含temp/tmp"
            ),
            evidence={"file": file_name, "table": table_name},
            message="临时表名未包含temp/tmp" if not ok else "",
        )


class CodeTempTableDroppedInSameTaskRule(AssessRule):
    rule_id = CODE_RULE_TEMP_TABLE_DROPPED
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        checks = []
        governed_tables = rule_context.get("governed_tables") or set()
        for create in target["creates"]:
            table_name = _short_table_name(create.get("table") or "")
            if (
                not table_name
                or table_name.lower() == target["expected_table"].lower()
                or table_name.lower() in governed_tables
            ):
                continue
            checks.append(
                self._check(
                    target["file_name"],
                    create,
                    target["drop_indexes_by_table"],
                )
            )
        return checks

    def _check(
        self,
        file_name: str,
        create: dict,
        drop_indexes_by_table: dict,
    ) -> dict:
        table_name = _short_table_name(create.get("table") or "")
        ok = any(
            drop_index > create["index"]
            for drop_index in drop_indexes_by_table.get(
                table_name.lower(),
                [],
            )
        )
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=ok,
            expected="临时表在同一作业后续DROP清理",
            actual="已清理" if ok else "未在同一作业后续DROP清理",
            evidence={"file": file_name, "table": table_name},
            message="临时表未在同一作业后续DROP清理" if not ok else "",
        )


class CodeNoSelectStarInWriteRule(AssessRule):
    rule_id = CODE_RULE_NO_SELECT_STAR
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        return [
            self._check(target["file_name"], write_statement)
            for write_statement in target["write_statements"]
        ]

    def _check(self, file_name: str, write_statement: dict) -> dict:
        table_name = _short_table_name(write_statement.get("table") or "")
        ok = not write_statement["has_select_star"]
        return make_check(
            rule_id=self.rule_id,
            target_type="task",
            target=file_name,
            passed=ok,
            expected="写入型语句显式列出字段",
            actual=(
                f"写入 {table_name} 时显式列出字段"
                if ok
                else f"写入 {table_name} 时使用 SELECT *"
            ),
            evidence={"file": file_name, "table": table_name},
            message="写入型语句使用SELECT *，请显式列出字段" if not ok else "",
        )


class _CodeIssueRule(AssessRule):
    def _issue_check(
        self,
        file_name: str,
        table_name: str,
        expected: str,
        actual: str,
        message: str,
        evidence: dict,
    ) -> dict:
        full_evidence = {"file": file_name, "table": table_name}
        full_evidence.update(evidence)
        return make_check(
            rule_id=self.rule_id,
            target_type="task",
            target=file_name,
            passed=False,
            expected=expected,
            actual=actual,
            evidence=full_evidence,
            message=message,
        )


class CodeCartesianJoinRiskRule(_CodeIssueRule):
    rule_id = CODE_RULE_CARTESIAN_JOIN_RISK
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        return [
            self._issue_check(
                target["file_name"],
                target["expected_table"],
                "JOIN具备明确ON/USING条件且不使用隐式笛卡尔积",
                f"存在{issue['reason']}",
                "JOIN存在笛卡尔积风险，请补充明确关联条件",
                issue,
            )
            for issue in _scan_cartesian_join_risks(target["sql"])
        ]


class CodeDwsJoinBeforeAggregationRule(_CodeIssueRule):
    rule_id = CODE_RULE_DWS_JOIN_BEFORE_AGGREGATION
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        task = target["task"]
        asset_catalog = rule_context["asset_catalog"]
        if not _is_dws_task(task, asset_catalog):
            return []
        return [
            self._issue_check(
                target["file_name"],
                target["expected_table"],
                "DWS聚合前JOIN已确认一对一或先预聚合",
                "DWS作业存在JOIN后直接聚合",
                "DWS聚合前JOIN可能放大明细行，需确认粒度或先预聚合",
                issue,
            )
            for issue in _scan_join_before_aggregation(
                target["sql"],
                asset_catalog,
            )
        ]


class CodeFilterColumnWrappedInFunctionRule(_CodeIssueRule):
    rule_id = CODE_RULE_FILTER_COLUMN_WRAPPED
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        return [
            self._issue_check(
                target["file_name"],
                target["expected_table"],
                "WHERE中的分区/过滤列保持裸列比较",
                f"过滤列被{issue['function']}包裹: {issue['detail']}",
                "过滤列被函数或CAST包裹，可能导致分区/索引裁剪失效",
                issue,
            )
            for issue in _scan_wrapped_filter_columns(target["sql"])
        ]


class CodeTempTableCreatedWithPreDropNotCleanedRule(AssessRule):
    rule_id = CODE_RULE_TEMP_TABLE_PRE_DROP_NOT_CLEANED
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        return [
            self._check(target["file_name"], issue)
            for issue in _unclosed_transient_table_issues(
                target,
                rule_context.get("governed_tables") or set(),
                allowed_reasons={"pre_drop_create_without_post_drop"},
            )
        ]

    def _check(self, file_name: str, issue: dict) -> dict:
        table_name = issue["table"]
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=False,
            expected="DROP IF EXISTS只能清理历史残留，CREATE后需在同一作业后续DROP",
            actual="CREATE之后未找到后续DROP清理",
            evidence={
                "file": file_name,
                "table": table_name,
                "reason": issue["reason"],
                "created_statement_index": issue["created_statement_index"],
                "pre_drop_statement_indexes": issue[
                    "pre_drop_statement_indexes"
                ],
                "post_create_drop_statement_indexes": issue[
                    "post_create_drop_statement_indexes"
                ],
            },
            message="DROP IF EXISTS发生在CREATE之前，不能证明本次临时表生命周期闭合",
        )


class CodeTempTableUsedAcrossTasksRule(AssessRule):
    rule_id = CODE_RULE_TEMP_TABLE_USED_ACROSS_TASKS
    dimension = "code_quality"
    domain = "task"
    target = "sql"

    def evaluate(
        self,
        target: dict,
        rule_context: dict,
    ) -> list[dict]:
        reader_tasks_by_table = rule_context.get("reader_tasks_by_table") or {}
        checks = []
        for issue in _unclosed_transient_table_issues(
            target,
            rule_context.get("governed_tables") or set(),
        ):
            table_name = issue["table"]
            reader_tasks = [
                task
                for task in reader_tasks_by_table.get(table_name.lower(), [])
                if task != target["file_name"]
            ]
            if not reader_tasks:
                continue
            checks.append(
                self._check(
                    target["file_name"],
                    issue,
                    sorted(reader_tasks),
                )
            )
        return checks

    def _check(
        self,
        file_name: str,
        issue: dict,
        reader_tasks: list[str],
    ) -> dict:
        table_name = issue["table"]
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=False,
            expected="临时/过程表只在同一task内创建、使用并清理",
            actual="临时/过程表被其他task读取",
            evidence={
                "file": file_name,
                "table": table_name,
                "reason": issue["reason"],
                "creator_task": file_name,
                "reader_tasks": reader_tasks,
                "created_statement_index": issue["created_statement_index"],
                "pre_drop_statement_indexes": issue[
                    "pre_drop_statement_indexes"
                ],
                "post_create_drop_statement_indexes": issue[
                    "post_create_drop_statement_indexes"
                ],
            },
            message="临时/过程表被其他task读取，形成跨task隐式依赖",
        )


CODE_QUALITY_RULE_CLASSES = [
    CodeTempTableNameHasTempOrTmpRule,
    CodeTempTableDroppedInSameTaskRule,
    CodeNoSelectStarInWriteRule,
    CodeCartesianJoinRiskRule,
    CodeDwsJoinBeforeAggregationRule,
    CodeFilterColumnWrappedInFunctionRule,
    CodeTempTableCreatedWithPreDropNotCleanedRule,
    CodeTempTableUsedAcrossTasksRule,
]

CODE_QUALITY_RULE_CLASSES_BY_ID = {
    rule_class.rule_id: rule_class for rule_class in CODE_QUALITY_RULE_CLASSES
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


def _is_temporary_create(stmt) -> bool:
    properties = stmt.args.get("properties")
    if not properties:
        return False
    return any(
        isinstance(prop, exp.TemporaryProperty)
        for prop in properties.expressions or []
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


def _unclosed_transient_table_issues(
    target: dict,
    governed_tables: set[str],
    allowed_reasons: set[str] | None = None,
) -> list[dict]:
    issues = []
    for table in target.get("transient_tables") or []:
        table_name = _short_table_name(
            table.get("name") or table.get("table") or ""
        )
        table_key = table_name.lower()
        if not table_name or table_key in governed_tables:
            continue
        if table.get("dropped_in_same_task") or (
            table.get("dropped_statement_index") is not None
        ):
            continue
        reason = str(
            table.get("reason") or "transient_table_without_post_drop"
        )
        if allowed_reasons is not None and reason not in allowed_reasons:
            continue

        issues.append(
            {
                "table": table_name,
                "reason": reason,
                "created_statement_index": table.get(
                    "created_statement_index"
                ),
                "pre_drop_statement_indexes": list(
                    table.get("pre_drop_statement_indexes") or []
                ),
                "post_create_drop_statement_indexes": [],
            }
        )
    return issues


def _target_table_nodes(target_expr) -> set[int]:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if isinstance(target_expr, exp.Table):
        return {id(target_expr)}
    return set()


def _statement_target_table_nodes(stmt) -> set[int]:
    if isinstance(stmt, exp.Insert):
        return _target_table_nodes(stmt.this)
    if _is_table_create(stmt) or _is_table_drop(stmt):
        return _target_table_nodes(stmt.this)
    if isinstance(stmt, (exp.Update, exp.Delete, exp.Merge)):
        return _target_table_nodes(stmt.this)
    if isinstance(stmt, exp.TruncateTable):
        nodes = set()
        for table in stmt.expressions:
            nodes.update(_target_table_nodes(table))
        return nodes
    return set()


def _cte_names(statement) -> set[str]:
    names = set()
    for cte in statement.find_all(exp.CTE):
        name = _short_table_name(cte.alias_or_name)
        if name:
            names.add(name.lower())
    return names


def _fallback_scan_source_tables(sql: str) -> set[str]:
    source_tables = set()
    sql = _strip_string_literals(_strip_line_comments(sql))
    pattern = (
        r"\b(?:FROM|JOIN)\s+"
        r"((?:`?\w+`?\.)*`?\w+`?)"
    )
    for match in re.finditer(pattern, sql, flags=re.IGNORECASE):
        table_name = _short_table_name(match.group(1))
        if table_name:
            source_tables.add(table_name)
    return source_tables


def _scan_task_source_tables(sql: str) -> set[str]:
    statements = _parse_statements(sql)
    if not statements:
        return _fallback_scan_source_tables(sql)

    source_tables = set()
    for statement in statements:
        target_node_ids = _statement_target_table_nodes(statement)
        cte_names = _cte_names(statement)
        for table in statement.find_all(exp.Table):
            table_name = _short_table_name(table.name)
            if not table_name:
                continue
            if id(table) in target_node_ids:
                continue
            if table_name.lower() in cte_names:
                continue
            source_tables.add(table_name)
    return source_tables


def _fallback_scan(sql: str) -> tuple[list[dict], list[dict], list[dict]]:
    creates = []
    drops = []
    write_statements = []
    statements = [
        statement.strip() for statement in sql.split(";") if statement.strip()
    ]
    for index, statement in enumerate(statements):
        create_match = re.search(
            r"\bCREATE\s+(TEMPORARY\s+)?TABLE\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?((?:`?\w+`?\.)*`?\w+`?)",
            statement,
            flags=re.IGNORECASE,
        )
        if create_match:
            table = _short_table_name(create_match.group(2))
            creates.append(
                {
                    "table": table,
                    "index": index,
                    "is_temporary": bool(create_match.group(1)),
                }
            )
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
            r"\bDROP\s+TABLE\s+(IF\s+EXISTS\s+)?"
            r"((?:`?\w+`?\.)*`?\w+`?)",
            statement,
            flags=re.IGNORECASE,
        )
        if drop_match:
            drops.append(
                {
                    "table": _short_table_name(drop_match.group(2)),
                    "index": index,
                    "if_exists": bool(drop_match.group(1)),
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
                    "is_temporary": _is_temporary_create(stmt),
                }
            )
        elif _is_table_drop(stmt):
            drops.append(
                {
                    "table": _target_table_name(stmt.this),
                    "index": index,
                    "if_exists": bool(stmt.args.get("exists")),
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
