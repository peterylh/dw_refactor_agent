"""Task-level SQL facts used by lineage and asset assessment."""

from __future__ import annotations

import re
from collections import defaultdict

import sqlglot
from sqlglot import exp


def _short_table_name(table_name: str) -> str:
    name = str(table_name or "").strip().rstrip(";")
    if not name:
        return ""
    name = name.replace("`", "").replace('"', "")
    return name.split(".")[-1].strip()


def _target_table_sql(target_expr) -> str:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if target_expr is None:
        return ""
    return target_expr.sql(dialect="doris")


def _target_short_name(target_expr) -> str:
    return _short_table_name(_target_table_sql(target_expr))


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


def _transient_table_facts(
    creates_by_table: dict[str, list[dict]],
    drops_by_table: dict[str, list[int]],
    source_file: str,
) -> list[dict]:
    transient_tables = []
    for table_key, creates in creates_by_table.items():
        drop_indexes = drops_by_table.get(table_key, [])
        for create in creates:
            later_drops = [
                drop_index
                for drop_index in drop_indexes
                if drop_index > create["index"]
            ]
            is_temporary = bool(create.get("is_temporary"))
            if not later_drops and not is_temporary:
                continue
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
            }
            if is_temporary:
                fact["is_temporary"] = True
            transient_tables.append(fact)
            break
    return sorted(
        transient_tables,
        key=lambda item: (
            item["source_file"],
            item["created_statement_index"],
            item["name"],
        ),
    )


def _finalize_task_facts(
    outputs: set[str],
    creates_by_table: dict[str, list[dict]],
    drops_by_table: dict[str, list[int]],
    source_file: str,
) -> dict:
    transient_tables = _transient_table_facts(
        creates_by_table,
        drops_by_table,
        source_file,
    )
    transient_names = {table["name"] for table in transient_tables}
    return {
        "source_file": source_file,
        "output_tables": {
            output
            for output in outputs
            if output and output not in transient_names
        },
        "transient_tables": transient_tables,
    }


def _parse_with_sqlglot(sql_text: str, source_file: str) -> dict | None:
    outputs = set()
    creates_by_table = defaultdict(list)
    drops_by_table = defaultdict(list)
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
    except Exception:
        return None
    if not statements:
        return None

    for index, stmt in enumerate(statements):
        if stmt is None:
            continue
        if _is_table_create(stmt):
            target = _target_short_name(stmt.this)
            if target:
                is_ctas = stmt.args.get("expression") is not None
                creates_by_table[target.lower()].append(
                    {
                        "table": target,
                        "index": index,
                        "is_ctas": is_ctas,
                        "is_temporary": _is_temporary_create(stmt),
                    }
                )
                if is_ctas:
                    outputs.add(target)
        elif _is_table_drop(stmt):
            target = _target_short_name(stmt.this)
            if target:
                drops_by_table[target.lower()].append(index)

        if isinstance(stmt, (exp.Insert, exp.Update, exp.Delete, exp.Merge)):
            outputs.add(_target_short_name(stmt.this))
        elif isinstance(stmt, exp.TruncateTable):
            for table in stmt.expressions:
                outputs.add(_target_short_name(table))

    return _finalize_task_facts(
        outputs,
        creates_by_table,
        drops_by_table,
        source_file,
    )


def _parse_with_regex(sql_text: str, source_file: str) -> dict:
    outputs = set()
    creates_by_table = defaultdict(list)
    drops_by_table = defaultdict(list)
    statements = [
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip()
    ]

    for index, statement in enumerate(statements):
        create_match = re.search(
            r"\bCREATE\s+(TEMPORARY\s+)?TABLE\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?(?:`?\w+`?\.)?`?(\w+)`?",
            statement,
            flags=re.IGNORECASE,
        )
        if create_match:
            target = _short_table_name(create_match.group(2))
            if target:
                is_ctas = bool(
                    re.search(
                        r"\bAS\s+SELECT\b",
                        statement,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                )
                creates_by_table[target.lower()].append(
                    {
                        "table": target,
                        "index": index,
                        "is_ctas": is_ctas,
                        "is_temporary": bool(create_match.group(1)),
                    }
                )
                if is_ctas:
                    outputs.add(target)

        drop_match = re.search(
            r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?"
            r"(?:`?\w+`?\.)?`?(\w+)`?",
            statement,
            flags=re.IGNORECASE,
        )
        if drop_match:
            target = _short_table_name(drop_match.group(1))
            if target:
                drops_by_table[target.lower()].append(index)

    write_patterns = [
        r"\bINSERT\s+(?:OVERWRITE\s+TABLE|INTO)\s+"
        r"(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bUPDATE\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bDELETE\s+FROM\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bTRUNCATE\s+(?:TABLE\s+)?(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bMERGE\s+INTO\s+(?:`?\w+`?\.)?`?(\w+)`?",
    ]
    for pattern in write_patterns:
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
            target = _short_table_name(match.group(1))
            if target:
                outputs.add(target)

    return _finalize_task_facts(
        outputs,
        creates_by_table,
        drops_by_table,
        source_file,
    )


def extract_task_table_facts(
    sql_text: str,
    source_file: str = "",
) -> dict:
    """Return persistent task outputs and created-then-dropped tables."""
    parsed = _parse_with_sqlglot(sql_text, source_file)
    if parsed is not None:
        return parsed
    return _parse_with_regex(sql_text, source_file)
