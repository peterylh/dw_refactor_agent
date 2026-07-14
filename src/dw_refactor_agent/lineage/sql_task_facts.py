"""Task-level SQL facts used by lineage and asset assessment."""

from __future__ import annotations

import re
from collections import defaultdict

import sqlglot
from sqlglot import exp

from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    qualified_table_name,
    short_table_name,
    table_identity_match_key,
)


def _short_table_name(table_name: str) -> str:
    return short_table_name(table_name)


def _table_match_key(
    table_name: str,
    default_catalog: str = "internal",
    default_db: str = "",
) -> tuple:
    return table_identity_match_key(
        table_name,
        default_catalog=default_catalog,
        default_db=default_db,
    )


def _target_table_name(target_expr) -> str:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if target_expr is None:
        return ""
    if isinstance(target_expr, exp.Table):
        return qualified_table_name(
            target_expr.catalog,
            target_expr.db,
            target_expr.name,
        )
    return canonical_qualified_identifier(target_expr.sql(dialect="doris"))


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


def _temp_name_is_valid(table_name: str) -> bool:
    table_key = identifier_match_key(_short_table_name(table_name))
    return "temp" in table_key or "tmp" in table_key


def _lifecycle_table_facts(
    creates_by_table: dict[str, list[dict]],
    drops_by_table: dict[str, list[dict]],
    source_file: str,
    *,
    include_legacy_pre_drop: bool = False,
) -> list[dict]:
    transient_tables = []
    for table_key, creates in creates_by_table.items():
        drops = drops_by_table.get(table_key, [])
        previous_create_index = -1
        for create in creates:
            pre_drops = [
                drop["index"]
                for drop in drops
                if previous_create_index < drop["index"] < create["index"]
                and drop.get("if_exists")
            ]
            later_drops = [
                drop["index"]
                for drop in drops
                if drop["index"] > create["index"]
            ]
            is_temporary = bool(create.get("is_temporary"))
            has_legacy_pre_drop = (
                include_legacy_pre_drop
                and bool(pre_drops)
                and _temp_name_is_valid(create.get("table", ""))
            )
            if (
                not later_drops
                and not is_temporary
                and not has_legacy_pre_drop
            ):
                previous_create_index = create["index"]
                continue
            if later_drops:
                reason = "created_then_dropped_in_same_task"
            elif is_temporary:
                reason = "temporary_create_without_post_drop"
            else:
                reason = "pre_drop_create_without_post_drop"
            fact = {
                "name": create["table"],
                "source_file": source_file,
                "created_statement_index": create["index"],
                "dropped_statement_index": min(later_drops)
                if later_drops
                else None,
                "is_ctas": create["is_ctas"],
                "is_transient": True,
                "dropped_in_same_task": bool(later_drops),
                "pre_drop_statement_indexes": pre_drops,
                "reason": reason,
            }
            if is_temporary:
                fact["is_temporary"] = True
            transient_tables.append(fact)
            previous_create_index = create["index"]
    return sorted(
        transient_tables,
        key=lambda item: (
            item["source_file"],
            item["created_statement_index"],
            item["name"],
        ),
    )


def _finalize_task_facts(
    inputs: set[str],
    outputs: set[str],
    creates_by_table: dict[str, list[dict]],
    drops_by_table: dict[str, list[dict]],
    source_file: str,
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict:
    local_lifecycle_tables = _lifecycle_table_facts(
        creates_by_table,
        drops_by_table,
        source_file,
    )
    legacy_transient_tables = _lifecycle_table_facts(
        creates_by_table,
        drops_by_table,
        source_file,
        include_legacy_pre_drop=True,
    )
    created_tables = {
        create["table"]
        for creates in creates_by_table.values()
        for create in creates
        if create.get("table")
    }
    temporary_tables = {
        create["table"]
        for creates in creates_by_table.values()
        for create in creates
        if create.get("table") and create.get("is_temporary")
    }
    non_persistent_created_keys = set()
    for table_key, creates in creates_by_table.items():
        last_create = max(creates, key=lambda create: create["index"])
        later_drops = [
            drop
            for drop in drops_by_table.get(table_key, [])
            if drop["index"] > last_create["index"]
        ]
        if last_create.get("is_temporary") or later_drops:
            non_persistent_created_keys.add(table_key)
    return {
        "source_file": source_file,
        "input_tables": {table for table in inputs if table},
        "output_tables": {
            output
            for output in outputs
            if output
            and _table_match_key(
                output,
                default_catalog=default_catalog,
                default_db=default_db,
            )
            not in non_persistent_created_keys
        },
        "created_tables": created_tables,
        "temporary_tables": temporary_tables,
        "local_lifecycle_tables": local_lifecycle_tables,
        # Assessment compatibility: legacy quality checks still use pre-drop
        # evidence. Producer eligibility uses local_lifecycle_tables instead.
        "transient_tables": legacy_transient_tables,
    }


def _table_expr(target_expr):
    if isinstance(target_expr, exp.Schema):
        return target_expr.this
    if isinstance(target_expr, exp.Table):
        return target_expr
    return None


def _statement_target_table_exprs(stmt) -> list:
    if isinstance(
        stmt,
        (
            exp.Create,
            exp.Drop,
            exp.Alter,
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Merge,
        ),
    ):
        target = _table_expr(stmt.this)
        return [target] if target is not None else []
    if isinstance(stmt, exp.TruncateTable):
        candidates = list(stmt.expressions or [])
        if stmt.this is not None:
            candidates.append(stmt.this)
        return [
            target
            for target in (_table_expr(candidate) for candidate in candidates)
            if target is not None
        ]
    if isinstance(stmt, exp.Select) and stmt.args.get("into"):
        target = _table_expr(stmt.args["into"].this)
        return [target] if target is not None else []
    return []


def _statement_input_tables(stmt) -> set[str]:
    target_ids = {
        id(table_expr) for table_expr in _statement_target_table_exprs(stmt)
    }
    cte_names = {
        identifier_match_key(cte.alias_or_name)
        for cte in stmt.find_all(exp.CTE)
        if cte.alias_or_name
    }
    inputs = set()
    for table_expr in stmt.find_all(exp.Table):
        if id(table_expr) in target_ids:
            continue
        table_name = _target_table_name(table_expr)
        short_name = _short_table_name(table_name)
        if not short_name:
            continue
        is_qualified = bool(
            table_expr.args.get("db") or table_expr.args.get("catalog")
        )
        if not is_qualified and identifier_match_key(short_name) in cte_names:
            continue
        inputs.add(table_name)
    return inputs


def extract_task_table_facts_from_statements(
    statements,
    source_file: str = "",
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict:
    """Return task facts from already parsed SQLGlot statements."""
    inputs = set()
    outputs = set()
    creates_by_table = defaultdict(list)
    drops_by_table = defaultdict(list)

    for index, stmt in enumerate(statements):
        if stmt is None:
            continue
        inputs.update(_statement_input_tables(stmt))
        if _is_table_create(stmt):
            target = _target_table_name(stmt.this)
            if target:
                is_ctas = stmt.args.get("expression") is not None
                creates_by_table[
                    _table_match_key(target, default_catalog, default_db)
                ].append(
                    {
                        "table": target,
                        "index": index,
                        "is_ctas": is_ctas,
                        "is_temporary": _is_temporary_create(stmt),
                    }
                )
                outputs.add(target)
        elif _is_table_drop(stmt):
            target = _target_table_name(stmt.this)
            if target:
                drops_by_table[
                    _table_match_key(target, default_catalog, default_db)
                ].append(
                    {
                        "index": index,
                        "if_exists": bool(stmt.args.get("exists")),
                    }
                )
        elif isinstance(stmt, exp.Select) and stmt.args.get("into"):
            target = _target_table_name(stmt.args["into"].this)
            if target:
                creates_by_table[
                    _table_match_key(target, default_catalog, default_db)
                ].append(
                    {
                        "table": target,
                        "index": index,
                        "is_ctas": True,
                        "is_temporary": False,
                    }
                )
                outputs.add(target)

        if isinstance(stmt, (exp.Insert, exp.Update, exp.Delete, exp.Merge)):
            outputs.add(_target_table_name(stmt.this))
        elif isinstance(stmt, exp.TruncateTable):
            for table in stmt.expressions:
                outputs.add(_target_table_name(table))

    return _finalize_task_facts(
        inputs,
        outputs,
        creates_by_table,
        drops_by_table,
        source_file,
        default_catalog,
        default_db,
    )


def _parse_with_sqlglot(
    sql_text: str,
    source_file: str,
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict | None:
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
    except Exception:
        return None
    if not statements:
        return None
    return extract_task_table_facts_from_statements(
        statements,
        source_file,
        default_catalog,
        default_db,
    )


def _parse_with_regex(
    sql_text: str,
    source_file: str,
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict:
    inputs = set()
    outputs = set()
    creates_by_table = defaultdict(list)
    drops_by_table = defaultdict(list)
    statements = [
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip()
    ]

    for index, statement in enumerate(statements):
        target_spans = set()
        create_match = re.search(
            r"\bCREATE\s+(TEMPORARY\s+)?TABLE\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?((?:`?\w+`?\.)*`?\w+`?)",
            statement,
            flags=re.IGNORECASE,
        )
        if create_match:
            target_spans.add(create_match.span(2))
            target = canonical_qualified_identifier(create_match.group(2))
            if target:
                is_ctas = bool(
                    re.search(
                        r"\bAS\s+SELECT\b",
                        statement,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                )
                creates_by_table[
                    _table_match_key(target, default_catalog, default_db)
                ].append(
                    {
                        "table": target,
                        "index": index,
                        "is_ctas": is_ctas,
                        "is_temporary": bool(create_match.group(1)),
                    }
                )
                outputs.add(target)

        drop_match = re.search(
            r"\bDROP\s+TABLE\s+(IF\s+EXISTS\s+)?"
            r"((?:`?\w+`?\.)*`?\w+`?)",
            statement,
            flags=re.IGNORECASE,
        )
        if drop_match:
            target = canonical_qualified_identifier(drop_match.group(2))
            if target:
                drops_by_table[
                    _table_match_key(target, default_catalog, default_db)
                ].append(
                    {
                        "index": index,
                        "if_exists": bool(drop_match.group(1)),
                    }
                )

        write_patterns = [
            r"\bINSERT\s+(?:OVERWRITE\s+TABLE|INTO)\s+"
            r"((?:`?\w+`?\.)*`?\w+`?)",
            r"\bUPDATE\s+((?:`?\w+`?\.)*`?\w+`?)",
            r"\bDELETE\s+FROM\s+((?:`?\w+`?\.)*`?\w+`?)",
            r"\bTRUNCATE\s+(?:TABLE\s+)?((?:`?\w+`?\.)*`?\w+`?)",
            r"\bMERGE\s+INTO\s+((?:`?\w+`?\.)*`?\w+`?)",
        ]
        for pattern in write_patterns:
            match = re.search(pattern, statement, flags=re.IGNORECASE)
            if not match:
                continue
            target_spans.add(match.span(1))
            target = canonical_qualified_identifier(match.group(1))
            if target:
                outputs.add(target)

        cte_names = {
            identifier_match_key(match.group(1))
            for match in re.finditer(
                r"(?:\bWITH\b|,)\s*`?(\w+)`?\s+AS\s*\(",
                statement,
                flags=re.IGNORECASE,
            )
        }
        for match in re.finditer(
            r"\b(?:FROM|JOIN|USING)\s+"
            r"((?:`?\w+`?\.)*`?\w+`?)",
            statement,
            flags=re.IGNORECASE,
        ):
            if match.span(1) in target_spans:
                continue
            table_name = match.group(1)
            canonical_name = canonical_qualified_identifier(table_name)
            short_name = _short_table_name(canonical_name)
            is_qualified = "." in table_name
            if (
                not is_qualified
                and identifier_match_key(short_name) in cte_names
            ):
                continue
            if short_name:
                inputs.add(canonical_name)

    return _finalize_task_facts(
        inputs,
        outputs,
        creates_by_table,
        drops_by_table,
        source_file,
        default_catalog,
        default_db,
    )


def extract_task_table_facts(
    sql_text: str,
    source_file: str = "",
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict:
    """Return task reads, writes, creates, and local lifecycle facts."""
    parsed = _parse_with_sqlglot(
        sql_text,
        source_file,
        default_catalog,
        default_db,
    )
    if parsed is not None:
        return parsed
    return _parse_with_regex(
        sql_text,
        source_file,
        default_catalog,
        default_db,
    )
