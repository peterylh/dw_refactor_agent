#!/usr/bin/env python3
"""
通用字段级 SQL 血缘采集器
使用 sqlglot.lineage() 替代手写 AST 遍历
支持: INSERT, UPDATE, CTAS, CREATE VIEW, SELECT INTO, MERGE
"""

import argparse
import json
import logging
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import sqlglot
from sqlglot import exp
from sqlglot.lineage import build_scope as build_lineage_scope
from sqlglot.lineage import lineage
from sqlglot.lineage import qualify as lineage_qualify
from sqlglot.schema import MappingSchema, Schema

from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    iter_project_task_files,
    lineage_data_path,
    lineage_task_cache_path,
    ods_source_catalog_ddl_dialect,
    project_asset_dirs,
    project_ods_asset_dirs,
    task_source_file,
)
from dw_refactor_agent.config import determine_layer as determine_config_layer
from dw_refactor_agent.config import (
    project_dir as configured_project_dir,
)
from dw_refactor_agent.lineage.identifiers import (
    canonical_identifier,
    canonical_qualified_identifier,
    display_table_name,
    identifier_match_key,
    qualified_table_name,
    schema_table_match_key,
    table_identity,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.sql_task_facts import (
    extract_task_table_facts,
    extract_task_table_facts_from_statements,
)
from dw_refactor_agent.sql.doris import normalize_create_table_for_sqlglot

AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)
DROP_TABLE_FORCE_PATTERN = re.compile(
    r"(\bDROP\s+TABLE\b[^;]*?)\s+FORCE(\s*(?:;|$))",
    flags=re.IGNORECASE,
)


# ============================================================
# 0. 项目配置
# ============================================================

CURRENT_PROJECT = "shop"
CURRENT_CATALOG = "internal"
CURRENT_DB = "shop_dm"
LINEAGE_DIALECT = "doris, normalization_strategy=lowercase"
DDL_DIALECTS_WITH_PARTITIONED_BY = {"hive", "spark"}
LOGGER = logging.getLogger(__name__)


def configure_project(project_name):
    global CURRENT_PROJECT, CURRENT_CATALOG, CURRENT_DB
    cfg = PROJECT_CONFIG.get(project_name)
    if not cfg:
        raise ValueError(
            f"未知项目: {project_name}, 可选: {list(PROJECT_CONFIG.keys())}"
        )
    CURRENT_PROJECT = project_name
    CURRENT_CATALOG = cfg.get("catalog", "internal")
    CURRENT_DB = cfg["db"]


def _sqlglot_task_sql(sql_text):
    """Remove Doris task syntax that sqlglot cannot parse."""
    return DROP_TABLE_FORCE_PATTERN.sub(r"\1\2", str(sql_text or ""))


def _canonical_identifier(name):
    """Return the logical identifier name without SQL quote wrappers."""
    return canonical_identifier(name)


def _identifier_match_key(name):
    return identifier_match_key(name)


def _canonical_qualified_identifier(name):
    return canonical_qualified_identifier(name)


def _default_catalog():
    return _canonical_identifier(CURRENT_CATALOG) or "internal"


def _default_db():
    return _canonical_identifier(CURRENT_DB)


def _table_identity(name, default_catalog=None, default_db=None):
    """Return (catalog, database, table), filling project defaults as needed."""
    return table_identity(
        name,
        default_catalog=default_catalog or _default_catalog(),
        default_db=default_db or _default_db(),
    )


def _schema_table_match_key(catalog, database, table):
    return schema_table_match_key(catalog, database, table)


def _table_identity_match_key(name, default_catalog=None, default_db=None):
    return table_identity_match_key(
        name,
        default_catalog=default_catalog or _default_catalog(),
        default_db=default_db or _default_db(),
    )


def _qualified_table_name(catalog, database, table):
    return qualified_table_name(catalog, database, table)


def _display_table_name(name, strip_current_db=False):
    """Format a table name for output, hiding the default internal catalog."""
    return display_table_name(
        name,
        default_catalog=_default_catalog(),
        default_db=_default_db(),
        strip_current_db=strip_current_db,
    )


def _strip_db(name):
    return _display_table_name(name, strip_current_db=True)


def _canonical_column(name):
    return _canonical_identifier(name)


class _SchemaLookup:
    """Precomputed schema indexes for hot-path lineage normalization."""

    def __init__(self, schema):
        self.table_by_match_key = {}
        self.columns_by_match_key = {}
        self.schema_columns_by_table = {}
        self.schema_type_by_table_col = {}

        for catalog, database, table, columns in _iter_schema_tables(schema):
            match_key = _schema_table_match_key(catalog, database, table)
            full_table_name = _qualified_table_name(catalog, database, table)
            display_table = _display_table_name(
                full_table_name,
                strip_current_db=True,
            )
            if not display_table:
                continue

            self.table_by_match_key.setdefault(match_key, display_table)
            column_lookup = self.columns_by_match_key.setdefault(
                match_key,
                {},
            )
            table_columns = self.schema_columns_by_table.setdefault(
                display_table,
                [],
            )
            for raw_column, col_type in (columns or {}).items():
                column = _canonical_column(raw_column)
                if not column:
                    continue
                column_lookup.setdefault(
                    _identifier_match_key(column),
                    column,
                )

                type_key = (display_table, column)
                if type_key in self.schema_type_by_table_col:
                    continue
                self.schema_type_by_table_col[type_key] = col_type
                table_columns.append((column, col_type))

    def table_name(self, table_name):
        requested_key = _table_identity_match_key(table_name)
        if not requested_key[2]:
            return _strip_db(table_name)
        return self.table_by_match_key.get(
            requested_key,
            _strip_db(table_name),
        )

    def column_name(self, table_name, column_name):
        clean_column = _canonical_column(column_name)
        column_key = _identifier_match_key(clean_column)
        if not column_key:
            return ""
        requested_key = _table_identity_match_key(table_name)
        return self.columns_by_match_key.get(requested_key, {}).get(
            column_key,
            clean_column,
        )


def _schema_lookup(schema):
    if isinstance(schema, _SchemaLookup):
        return schema
    return _SchemaLookup(schema)


def _iter_matching_schema_tables(schema, table_name):
    requested_key = _table_identity_match_key(table_name)
    if not requested_key[2]:
        return
    for catalog, database, table, columns in _iter_schema_tables(schema):
        if _schema_table_match_key(catalog, database, table) == requested_key:
            yield catalog, database, table, columns


def _schema_table_name(schema, table_name):
    if isinstance(schema, _SchemaLookup):
        return schema.table_name(table_name)
    for catalog, database, table, _columns in _iter_matching_schema_tables(
        schema, table_name
    ):
        return _display_table_name(
            _qualified_table_name(catalog, database, table),
            strip_current_db=True,
        )
    return _strip_db(table_name)


def _schema_column_name(schema, table_name, column_name):
    if isinstance(schema, _SchemaLookup):
        return schema.column_name(table_name, column_name)
    clean_column = _canonical_column(column_name)
    column_key = _identifier_match_key(clean_column)
    if not column_key:
        return ""
    for _catalog, _database, _table, columns in _iter_matching_schema_tables(
        schema, table_name
    ):
        for raw_column in columns or {}:
            if _identifier_match_key(raw_column) == column_key:
                return _canonical_column(raw_column)
    return clean_column


def _canonical_lineage_entry(entry, schema=None):
    cleaned = dict(entry)
    for key in ("source_table", "target_table"):
        if key in cleaned:
            if schema is not None:
                cleaned[key] = _schema_table_name(schema, cleaned[key])
            else:
                cleaned[key] = _strip_db(cleaned[key])
    if "source_column" in cleaned:
        if schema is not None:
            cleaned["source_column"] = _schema_column_name(
                schema,
                cleaned.get("source_table", ""),
                cleaned["source_column"],
            )
        else:
            cleaned["source_column"] = _canonical_column(
                cleaned["source_column"]
            )
    if "target_column" in cleaned:
        if schema is not None:
            cleaned["target_column"] = _schema_column_name(
                schema,
                cleaned.get("target_table", ""),
                cleaned["target_column"],
            )
        else:
            cleaned["target_column"] = _canonical_column(
                cleaned["target_column"]
            )
    return cleaned


def _node_id(table_name, column_name):
    table_name = _canonical_qualified_identifier(table_name)
    return f"{table_name}.{_canonical_column(column_name)}"


def _column_source(table_name, column_name):
    return {"type": "column", "id": _node_id(table_name, column_name)}


def _column_target(table_name, column_name):
    return {"type": "column", "id": _node_id(table_name, column_name)}


def _table_target(table_name):
    return {
        "type": "table",
        "id": _canonical_qualified_identifier(table_name),
    }


def _literal_source(value):
    return {"type": "literal", "value": value}


def _expression_source(expression):
    return {"type": "expression", "expression": expression}


def _expression_sql(expression):
    return (
        expression.sql(dialect="doris")
        if hasattr(expression, "sql")
        else str(expression)
    )


def _source_sort_key(source):
    if not isinstance(source, dict):
        return str(source or "")
    return "|".join(
        str(source.get(key) or "")
        for key in ("type", "id", "value", "expression")
    )


def _target_sort_key(target):
    if not isinstance(target, dict):
        return str(target or "")
    return "|".join(str(target.get(key) or "") for key in ("type", "id"))


def _relation_type_for_condition(condition_type):
    normalized = str(condition_type or "").strip().lower()
    return {
        "join_on": "join",
        "where": "filter",
        "having": "having",
        "group_by": "group_by",
    }.get(normalized, normalized or "indirect")


def _transformation_type_for_expression(expression):
    if AGGREGATE_PATTERN.search(str(expression or "")):
        return "aggregation"
    return "passthrough"


def _is_literal_expression(expression):
    node = expression.this if isinstance(expression, exp.Alias) else expression
    return isinstance(node, (exp.Literal, exp.Boolean, exp.Null))


def _literal_value(expression):
    node = expression.this if isinstance(expression, exp.Alias) else expression
    if isinstance(node, exp.Boolean):
        return bool(node.this)
    if isinstance(node, exp.Null):
        return None
    if isinstance(node, exp.Literal):
        if node.is_int:
            return int(node.this)
        if node.is_number:
            return float(node.this)
        return str(node.this)
    return ""


def _constant_lineage_entry(
    target_table,
    target_column,
    expression,
    file_path,
):
    expression_sql = (
        expression.sql(dialect="doris")
        if hasattr(expression, "sql")
        else str(expression)
    )
    if _is_literal_expression(expression):
        return {
            "lineage_type": "direct",
            "source_type": "literal",
            "source_value": _literal_value(expression),
            "target_table": _strip_db(target_table),
            "target_column": _canonical_column(target_column),
            "expression": expression_sql,
            "transformation_type": "constant",
            "source_file": file_path,
        }
    return {
        "lineage_type": "direct",
        "source_type": "expression",
        "source_expression": expression_sql,
        "target_table": _strip_db(target_table),
        "target_column": _canonical_column(target_column),
        "expression": expression_sql,
        "transformation_type": "constant",
        "source_file": file_path,
    }


def _target_table_sql(target_expr):
    """返回写入目标表名,不包含 INSERT/CREATE 目标列清单。"""
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if isinstance(target_expr, exp.Table):
        return _table_name(target_expr)
    return _canonical_qualified_identifier(target_expr.sql(dialect="doris"))


def _target_columns(target_expr):
    """返回 INSERT/CTAS 显式声明的目标列,用于按 SELECT 位置对齐。"""
    if not isinstance(target_expr, exp.Schema):
        return None
    columns = []
    for col in target_expr.expressions:
        if isinstance(col, exp.ColumnDef):
            columns.append(_canonical_column(col.this.name))
        elif hasattr(col, "name"):
            columns.append(_canonical_column(col.name))
    return columns or None


def _schema_columns_for_table(schema, table_name):
    """返回目标表 DDL 字段顺序,用于 INSERT 未声明目标列时按位置对齐。"""
    for _catalog, _database, _table, columns in _iter_matching_schema_tables(
        schema, table_name
    ):
        if columns:
            return [_canonical_column(col_name) for col_name in columns]
    return None


def _schema_column_map_for_table(schema, table_name):
    for _catalog, _database, _table, columns in _iter_matching_schema_tables(
        schema, table_name
    ):
        if columns:
            return {
                _canonical_column(col_name): col_type
                for col_name, col_type in columns.items()
                if _canonical_column(col_name)
            }
    return None


def _is_column_map(value):
    return isinstance(value, dict) and all(
        not isinstance(col_type, dict) for col_type in value.values()
    )


def _is_table_map(value):
    return isinstance(value, dict) and all(
        isinstance(columns, dict) and _is_column_map(columns)
        for columns in value.values()
    )


def _iter_schema_tables(schema):
    """Yield normalized (catalog, database, table, columns) entries."""
    for first_name, first_value in (schema or {}).items():
        if not isinstance(first_value, dict):
            continue
        first_name = _canonical_identifier(first_name)

        # Legacy malformed one-level shape: {table: {column: type}}.
        if _is_column_map(first_value):
            yield _default_catalog(), _default_db(), first_name, first_value
            continue

        # Legacy two-level shape: {database: {table: {column: type}}}.
        if _is_table_map(first_value):
            database = first_name
            for table_name, columns in first_value.items():
                yield (
                    _default_catalog(),
                    database,
                    _canonical_identifier(table_name),
                    columns,
                )
            continue

        # Catalog-aware shape: {catalog: {database: {table: {column: type}}}}.
        catalog = first_name
        for db_name, db_tables in first_value.items():
            if not isinstance(db_tables, dict):
                continue
            database = _canonical_identifier(db_name)
            for table_name, columns in db_tables.items():
                if isinstance(columns, dict):
                    yield (
                        catalog,
                        database,
                        _canonical_identifier(table_name),
                        columns,
                    )


def _copy_schema(schema):
    copied = {}
    for catalog, database, table, columns in _iter_schema_tables(schema):
        copied.setdefault(catalog, {}).setdefault(database, {})[table] = dict(
            columns or {}
        )
    return copied


def schema_table_count(schema):
    return sum(1 for _ in _iter_schema_tables(schema))


def _schema_has_table(schema, table_name):
    return any(
        True for _table in _iter_matching_schema_tables(schema, table_name)
    )


def _statement_target_table(stmt):
    if not (
        isinstance(stmt, (exp.Create, exp.Drop))
        and str(stmt.args.get("kind") or "").upper() == "TABLE"
    ):
        return None
    target_expr = stmt.this
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    if isinstance(target_expr, exp.Table):
        return target_expr
    return None


def _statement_table_references(statements):
    """Collect referenced table names with their statement index."""
    references = []
    for statement_index, stmt in enumerate(statements or []):
        if stmt is None:
            continue
        target_table = _statement_target_table(stmt)
        target_table_ids = (
            {id(target_table)} if target_table is not None else set()
        )
        for table_expr in stmt.find_all(exp.Table):
            if id(table_expr) in target_table_ids:
                continue
            table_name = _canonical_qualified_identifier(
                _table_name(table_expr)
            )
            if table_name:
                references.append(
                    {
                        "statement_index": statement_index,
                        "table_name": table_name,
                    }
                )
    return references


def collect_statement_table_names(statements):
    """Collect table names referenced by a parsed task."""
    return {
        reference["table_name"]
        for reference in _statement_table_references(statements)
    }


def collect_statement_cte_names(statements):
    """Collect CTE names so they are not treated as physical tables."""
    cte_names = set()
    for stmt in statements or []:
        if stmt is None:
            continue
        for cte in stmt.find_all(exp.CTE):
            cte_name = _canonical_identifier(cte.alias_or_name)
            if cte_name:
                cte_names.add(cte_name)
    return cte_names


def _is_table_create_statement(stmt):
    return (
        isinstance(stmt, exp.Create)
        and str(stmt.args.get("kind") or "").upper() == "TABLE"
    )


def _is_table_drop_statement(stmt):
    return (
        isinstance(stmt, exp.Drop)
        and str(stmt.args.get("kind") or "").upper() == "TABLE"
    )


def _target_table_expr(target_expr):
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    return target_expr if isinstance(target_expr, exp.Table) else None


def _statement_table_target_exprs(stmt):
    if stmt is None:
        return []
    if _is_table_create_statement(stmt) or _is_table_drop_statement(stmt):
        target_expr = _target_table_expr(stmt.this)
        return [target_expr] if target_expr is not None else []
    if isinstance(stmt, (exp.Insert, exp.Update, exp.Delete, exp.Merge)):
        target_expr = _target_table_expr(stmt.this)
        return [target_expr] if target_expr is not None else []
    if isinstance(stmt, exp.TruncateTable):
        return [
            target_expr
            for target_expr in (
                _target_table_expr(expr) for expr in stmt.expressions
            )
            if target_expr is not None
        ]
    if isinstance(stmt, exp.Alter):
        target_expr = _target_table_expr(stmt.this)
        return [target_expr] if target_expr is not None else []
    return []


def _statement_source_table_names(stmt):
    if stmt is None:
        return set()
    target_table_ids = {
        id(expr) for expr in _statement_table_target_exprs(stmt)
    }
    cte_table_names = _normalized_skip_table_names(
        collect_statement_cte_names([stmt])
    )

    table_names = set()
    for table_expr in stmt.find_all(exp.Table):
        if id(table_expr) in target_table_ids:
            continue
        table_name = _canonical_qualified_identifier(_table_name(table_expr))
        if not table_name:
            continue
        is_qualified = bool(
            table_expr.args.get("db") or table_expr.args.get("catalog")
        )
        if (
            not is_qualified
            and _identifier_match_key(_strip_db(table_name)) in cte_table_names
        ):
            continue
        table_names.add(table_name)
    return table_names


def _statement_existing_target_table_names(stmt):
    if not isinstance(
        stmt,
        (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Merge,
            exp.TruncateTable,
            exp.Alter,
        ),
    ):
        return set()
    table_names = set()
    for target_expr in _statement_table_target_exprs(stmt):
        table_name = _canonical_qualified_identifier(_table_name(target_expr))
        if table_name:
            table_names.add(table_name)
    return table_names


def _normalized_skip_table_names(table_names):
    return {
        _identifier_match_key(_strip_db(table_name))
        for table_name in table_names
        if table_name
    }


def slice_schema(schema, table_names):
    """Return a schema containing only tables referenced by a task."""
    requested_identities = set()
    for table_name in table_names or []:
        catalog, database, table = _table_identity(table_name)
        if not table:
            continue
        requested_identities.add(
            _schema_table_match_key(catalog, database, table)
        )

    sliced = {}
    for catalog, database, table, columns in _iter_schema_tables(schema):
        full_name_key = _schema_table_match_key(catalog, database, table)
        if full_name_key in requested_identities:
            sliced.setdefault(catalog, {}).setdefault(database, {})[table] = (
                dict(columns or {})
            )
    return sliced


def _task_schema_for_statements(schema, statements):
    try:
        table_names = collect_statement_table_names(statements)
    except Exception:
        return _copy_schema(schema)
    return _task_schema_for_table_names(schema, table_names)


def _task_schema_for_table_names(schema, table_names):
    if not table_names:
        return _copy_schema(schema)

    task_schema = slice_schema(schema, table_names)
    if schema_table_count(task_schema) == 0:
        return _copy_schema(schema)
    return task_schema


def _lineage_schema_mapping(schema):
    mapping = {}
    for catalog, database, table, columns in _iter_schema_tables(schema):
        column_mapping = {}
        for column_name, column_type in (columns or {}).items():
            canonical = _canonical_column(column_name)
            if not canonical:
                continue
            column_mapping[canonical] = column_type
            column_mapping.setdefault(
                _identifier_match_key(canonical),
                column_type,
            )
        if column_mapping:
            mapping.setdefault(_identifier_match_key(catalog), {}).setdefault(
                _identifier_match_key(database),
                {},
            )[_identifier_match_key(table)] = column_mapping
    return mapping


def _lineage_schema(schema):
    if isinstance(schema, Schema):
        return schema
    return MappingSchema(
        _lineage_schema_mapping(schema),
        dialect=LINEAGE_DIALECT,
        normalize=False,
    )


def _identifier_arg_name(expression, arg_name):
    identifier = expression.args.get(arg_name)
    if identifier is None:
        return ""
    return _canonical_identifier(getattr(identifier, "name", identifier))


def _set_identifier_arg(expression, arg_name, name):
    normalized = _identifier_match_key(name)
    if not normalized:
        return
    current = expression.args.get(arg_name)
    quoted = isinstance(current, exp.Identifier) and current.args.get("quoted")
    expression.set(
        arg_name,
        exp.to_identifier(normalized, quoted=bool(quoted)),
    )


def _normalize_table_alias(alias):
    if not alias:
        return
    _set_identifier_arg(alias, "this", _identifier_arg_name(alias, "this"))
    normalized_columns = []
    for column in alias.args.get("columns") or []:
        column_name = _canonical_identifier(getattr(column, "name", column))
        column_key = _identifier_match_key(column_name)
        if not column_key:
            continue
        quoted = isinstance(column, exp.Identifier) and column.args.get(
            "quoted"
        )
        normalized_columns.append(
            exp.to_identifier(column_key, quoted=bool(quoted))
        )
    if normalized_columns:
        alias.set("columns", normalized_columns)


def _normalize_lineage_table_identifier(table):
    for arg_name in ("catalog", "db"):
        _set_identifier_arg(
            table,
            arg_name,
            _identifier_arg_name(table, arg_name),
        )
    _set_identifier_arg(table, "this", table.name)


def _normalize_lineage_column_identifier(column):
    if isinstance(column.this, exp.Star):
        return
    for arg_name in ("catalog", "db", "table"):
        _set_identifier_arg(
            column,
            arg_name,
            _identifier_arg_name(column, arg_name),
        )
    _set_identifier_arg(column, "this", column.name)


def _normalize_lineage_identifier_case(query_expr):
    """Return a parser-only AST where table and column names are casefolded."""
    normalized = query_expr.copy()
    for table_alias in list(normalized.find_all(exp.TableAlias)):
        _normalize_table_alias(table_alias)
    for table in list(normalized.find_all(exp.Table)):
        _normalize_lineage_table_identifier(table)
    for column in list(normalized.find_all(exp.Column)):
        _normalize_lineage_column_identifier(column)
    return normalized


def _lineage_output_column_name(display_expr, lineage_expr, column_name):
    requested_key = _identifier_match_key(column_name)
    display_names = _projection_output_names(display_expr)
    lineage_names = _projection_output_names(lineage_expr)
    if requested_key:
        for idx, display_name in enumerate(display_names):
            if _identifier_match_key(display_name) == requested_key:
                if idx < len(lineage_names) and lineage_names[idx]:
                    return lineage_names[idx]
                break
        for lineage_name in lineage_names:
            if _identifier_match_key(lineage_name) == requested_key:
                return lineage_name
    return _identifier_match_key(column_name) or column_name


def _lineage_scope(select_expr, schema):
    qualified = lineage_qualify.qualify(
        select_expr.copy(),
        dialect=LINEAGE_DIALECT,
        schema=_lineage_schema(schema),
        validate_qualify_columns=False,
        identify=False,
    )
    return build_lineage_scope(qualified)


def _register_task_table_schema(schema, table_name, columns):
    catalog, database, table_short = _table_identity(table_name)
    if isinstance(columns, dict):
        clean_column_map = {
            _canonical_column(column_name): column_type
            for column_name, column_type in columns.items()
            if _canonical_column(column_name)
        }
    else:
        clean_column_map = {
            _canonical_column(column_name): "UNKNOWN"
            for column_name in (columns or [])
            if _canonical_column(column_name)
        }
    if not table_short or not clean_column_map:
        return
    schema.setdefault(catalog, {}).setdefault(database, {})[table_short] = (
        clean_column_map
    )


def _drop_task_table_schema(schema, table_name):
    target_key = _table_identity_match_key(table_name)
    if not target_key[2]:
        return
    for catalog_key, databases in list((schema or {}).items()):
        if not isinstance(databases, dict):
            continue
        for database_key, tables in list(databases.items()):
            if not isinstance(tables, dict):
                continue
            for table_key in list(tables):
                if (
                    _schema_table_match_key(
                        catalog_key,
                        database_key,
                        table_key,
                    )
                    == target_key
                ):
                    tables.pop(table_key, None)
            if not tables:
                databases.pop(database_key, None)
        if not databases:
            schema.pop(catalog_key, None)


def _apply_alter_table_to_task_schema(schema, stmt, dialect="doris"):
    if not isinstance(stmt, exp.Alter):
        return
    table_expr = stmt.this
    if not isinstance(table_expr, exp.Table):
        return
    table_name = _table_name(table_expr)
    catalog, database, table_short = _table_identity(table_name)
    if not table_short:
        return

    new_columns = []
    for action in stmt.args.get("actions") or []:
        if not isinstance(action, exp.ColumnDef):
            continue
        col_name = _canonical_column(action.this.name)
        if col_name:
            new_columns.append((col_name, _column_def_type(action, dialect)))
    if not new_columns:
        return

    table_columns = (
        schema.setdefault(catalog, {})
        .setdefault(
            database,
            {},
        )
        .setdefault(table_short, {})
    )
    for col_name, col_type in new_columns:
        if not col_name or col_name in table_columns:
            continue
        table_columns[col_name] = col_type


def _create_like_source_table(stmt):
    properties = stmt.args.get("properties")
    for prop in getattr(properties, "expressions", None) or []:
        if isinstance(prop, exp.LikeProperty) and isinstance(
            prop.this,
            exp.Table,
        ):
            return _table_name(prop.this)
    return ""


def _created_table_columns_from_schema(
    stmt,
    schema,
    file_path="",
    diagnostics=None,
):
    target_columns = _target_columns(stmt.this)
    if target_columns:
        return target_columns
    inner = _unwrap_query_expression(stmt.args.get("expression"))
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        (
            _expanded_inner,
            output_columns,
            has_unresolved_output,
        ) = _expand_query_star_projections(
            inner,
            schema,
            file_path=file_path,
            target_table=_target_table_sql(stmt.this),
            diagnostics=diagnostics,
        )
        if has_unresolved_output and not output_columns:
            return []
        return output_columns
    like_source_table = _create_like_source_table(stmt)
    if like_source_table:
        return _schema_column_map_for_table(schema, like_source_table) or {}
    return []


def _infer_table_for_column(schema, preferred_table, column_name):
    column_key = _identifier_match_key(column_name)
    preferred = _strip_db(preferred_table)
    if preferred and _schema_has_column(schema, preferred, column_name):
        return _schema_table_name(schema, preferred)

    matches = []
    for catalog, database, table_name, columns in _iter_schema_tables(schema):
        if any(
            _identifier_match_key(raw_column) == column_key
            for raw_column in (columns or {})
        ):
            matches.append(
                _display_table_name(
                    _qualified_table_name(catalog, database, table_name),
                    strip_current_db=True,
                )
            )
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else ""


def _fallback_direct_edges_from_expression(
    expression, target_table, target_col, schema
):
    edges = []
    seen = set()
    for col in expression.find_all(exp.Column):
        source_table = _strip_db(_canonical_identifier(col.table))
        if not source_table:
            source_table = _infer_table_for_column(
                schema, target_table, col.name
            )
        if not source_table:
            continue
        source_col = _canonical_column(col.name)
        key = (source_table, source_col)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "source_table": source_table,
                "source_column": source_col,
                "target_table": _strip_db(target_table),
                "target_column": _canonical_column(target_col),
            }
        )
    return edges


# ============================================================
# 1. Schema 构建: 从 DDL 解析
# ============================================================


def _parse_schema_create_statements(sql_text, dialect="doris"):
    text = (
        normalize_create_table_for_sqlglot(sql_text)
        if dialect == "doris"
        else sql_text
    )
    try:
        statements = sqlglot.parse(text, dialect=dialect)
    except Exception:
        return
    for stmt in statements:
        if isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Schema):
            yield stmt


def _column_def_type(col, dialect):
    kind = col.args.get("kind")
    return kind.sql(dialect=dialect) if kind else "UNKNOWN"


def _add_column_def(col_map, col, dialect):
    if not isinstance(col, exp.ColumnDef):
        return
    col_name = _canonical_column(col.this.name)
    if not col_name:
        return
    if col_name not in col_map:
        col_map[col_name] = _column_def_type(col, dialect)


def _partition_column_defs(stmt):
    properties = stmt.args.get("properties")
    for prop in getattr(properties, "expressions", None) or []:
        if prop.__class__.__name__ != "PartitionedByProperty":
            continue
        partition_schema = prop.args.get("this")
        if partition_schema is None:
            continue
        yield from partition_schema.find_all(exp.ColumnDef)


def build_schema_from_texts(
    sql_texts,
    dialect="doris",
    default_catalog=None,
    default_db=None,
):
    schema = {}
    for text in sql_texts:
        ddl_tables = {}
        for stmt in _parse_schema_create_statements(text, dialect=dialect):
            full_name = _canonical_qualified_identifier(
                stmt.this.this.sql(dialect=dialect)
            )
            if not full_name:
                continue
            col_map = ddl_tables.setdefault(full_name, {})
            for col in stmt.this.expressions:
                _add_column_def(col_map, col, dialect)
            if dialect in DDL_DIALECTS_WITH_PARTITIONED_BY:
                for col in _partition_column_defs(stmt):
                    _add_column_def(col_map, col, dialect)

        for full_name, col_map in ddl_tables.items():
            if col_map:
                catalog, database, table = _table_identity(
                    full_name,
                    default_catalog=default_catalog,
                    default_db=default_db,
                )
                schema.setdefault(catalog, {}).setdefault(database, {})[
                    table
                ] = col_map
    return schema


from dw_refactor_agent.lineage import lineage_projection as _lineage_projection

_LINEAGE_RUNTIME = sys.modules[__name__]


def _call_projection(name, *args, **kwargs):
    return _lineage_projection.call(
        name,
        _LINEAGE_RUNTIME,
        *args,
        **kwargs,
    )


def _unwrap_paren_projection(*args, **kwargs):
    return _call_projection("_unwrap_paren_projection", *args, **kwargs)


def _projection_output_name(*args, **kwargs):
    return _call_projection("_projection_output_name", *args, **kwargs)


def _projection_output_identifier(*args, **kwargs):
    return _call_projection("_projection_output_identifier", *args, **kwargs)


def _lineage_column_arg(*args, **kwargs):
    return _call_projection("_lineage_column_arg", *args, **kwargs)


def _projection_output_names(*args, **kwargs):
    return _call_projection("_projection_output_names", *args, **kwargs)


def _projection_items(*args, **kwargs):
    return _call_projection("_projection_items", *args, **kwargs)


def _unwrap_query_expression(*args, **kwargs):
    return _call_projection("_unwrap_query_expression", *args, **kwargs)


def _identifier_needs_quotes(*args, **kwargs):
    return _call_projection("_identifier_needs_quotes", *args, **kwargs)


def _projection_can_inline_through_star(*args, **kwargs):
    return _call_projection(
        "_projection_can_inline_through_star",
        *args,
        **kwargs,
    )


def _inline_star_projection(*args, **kwargs):
    return _call_projection("_inline_star_projection", *args, **kwargs)


def _is_star_projection(*args, **kwargs):
    return _call_projection("_is_star_projection", *args, **kwargs)


def _star_projection_table(*args, **kwargs):
    return _call_projection("_star_projection_table", *args, **kwargs)


def _star_has_modifiers(*args, **kwargs):
    return _call_projection("_star_has_modifiers", *args, **kwargs)


def _relation_alias(*args, **kwargs):
    return _call_projection("_relation_alias", *args, **kwargs)


def _explicit_relation_alias(*args, **kwargs):
    return _call_projection("_explicit_relation_alias", *args, **kwargs)


def _relation_match_keys(*args, **kwargs):
    return _call_projection("_relation_match_keys", *args, **kwargs)


def _column_projection(*args, **kwargs):
    return _call_projection("_column_projection", *args, **kwargs)


def _alias_column_names(*args, **kwargs):
    return _call_projection("_alias_column_names", *args, **kwargs)


def _exposed_columns(*args, **kwargs):
    return _call_projection("_exposed_columns", *args, **kwargs)


def _has_unexpanded_star_projection(*args, **kwargs):
    return _call_projection(
        "_has_unexpanded_star_projection",
        *args,
        **kwargs,
    )


def _mark_unresolved_star_source(*args, **kwargs):
    return _call_projection("_mark_unresolved_star_source", *args, **kwargs)


def _unresolved_star_source_keys(*args, **kwargs):
    return _call_projection("_unresolved_star_source_keys", *args, **kwargs)


def _projection_references_unresolved_source(*args, **kwargs):
    return _call_projection(
        "_projection_references_unresolved_source",
        *args,
        **kwargs,
    )


def _relation_source_match_keys(*args, **kwargs):
    return _call_projection("_relation_source_match_keys", *args, **kwargs)


def _expand_query_star_projections(*args, **kwargs):
    return _call_projection("_expand_query_star_projections", *args, **kwargs)


def _expand_select_star_projections(*args, **kwargs):
    return _call_projection("_expand_select_star_projections", *args, **kwargs)


def _expand_explicit_derived_sources(*args, **kwargs):
    return _call_projection(
        "_expand_explicit_derived_sources",
        *args,
        **kwargs,
    )


def _build_star_relation_sources(*args, **kwargs):
    return _call_projection("_build_star_relation_sources", *args, **kwargs)


def _star_relation_source(*args, **kwargs):
    return _call_projection("_star_relation_source", *args, **kwargs)


def _expand_star_projection_from_sources(*args, **kwargs):
    return _call_projection(
        "_expand_star_projection_from_sources",
        *args,
        **kwargs,
    )


def _derived_output_column_lookup(*args, **kwargs):
    return _call_projection("_derived_output_column_lookup", *args, **kwargs)


def _derived_output_lookups_for_select(*args, **kwargs):
    return _call_projection(
        "_derived_output_lookups_for_select",
        *args,
        **kwargs,
    )


def _enclosing_select(*args, **kwargs):
    return _call_projection("_enclosing_select", *args, **kwargs)


def _normalize_derived_column_reference_case(*args, **kwargs):
    return _call_projection(
        "_normalize_derived_column_reference_case",
        *args,
        **kwargs,
    )


def _named_struct_field_expressions(*args, **kwargs):
    return _call_projection(
        "_named_struct_field_expressions",
        *args,
        **kwargs,
    )


def _lateral_named_struct_field_lookups(*args, **kwargs):
    return _call_projection(
        "_lateral_named_struct_field_lookups",
        *args,
        **kwargs,
    )


def _lineage_expression_for_lateral_field(*args, **kwargs):
    return _call_projection(
        "_lineage_expression_for_lateral_field",
        *args,
        **kwargs,
    )


def _rewrite_lateral_named_struct_fields(*args, **kwargs):
    return _call_projection(
        "_rewrite_lateral_named_struct_fields",
        *args,
        **kwargs,
    )


_lineage_projection.preserve_facade_metadata(globals())


def _diagnostic_error(error):
    return f"{type(error).__name__}: {error}"


_DIAGNOSTIC_SEVERITY_BY_STAGE = {
    "lineage_scope": "warning",
    "lineage_star_expand": "warning",
    "lineage_target": "warning",
    "derived_lineage_column": "warning",
    "parse": "error",
    "lineage_column": "error",
    "worker": "error",
}


def _diagnostic_severity(stage):
    return _DIAGNOSTIC_SEVERITY_BY_STAGE.get(str(stage or ""), "error")


def _record_diagnostic(
    diagnostics,
    source_file,
    stage,
    error,
    severity=None,
    **context,
):
    if diagnostics is None:
        return
    diagnostics.append(
        {
            "source_file": source_file,
            "stage": stage,
            "severity": severity or _diagnostic_severity(stage),
            "error": _diagnostic_error(error),
            **{
                key: value
                for key, value in context.items()
                if value is not None and value != ""
            },
        }
    )


def _fatal_diagnostics(diagnostics):
    return [
        diagnostic
        for diagnostic in (diagnostics or [])
        if (
            diagnostic.get("severity")
            or _diagnostic_severity(diagnostic.get("stage"))
        )
        == "error"
    ]


def _lineage_node_items_for_select(
    select_expr,
    schema,
    file_path="",
    target_table="",
    diagnostics=None,
):
    node_items = []
    display_expr = _rewrite_lateral_named_struct_fields(
        _normalize_derived_column_reference_case(select_expr)
    )
    lineage_expr = _normalize_lineage_identifier_case(display_expr)
    projections = _projection_items(display_expr)
    lineage_projections = _projection_items(lineage_expr)
    display_column_names = _projection_output_names(display_expr)
    lineage_column_names = _projection_output_names(lineage_expr)
    if len(lineage_column_names) < len(display_column_names):
        lineage_column_names = list(display_column_names)
    unresolved_source_keys = _unresolved_star_source_keys(display_expr)
    sqlglot_schema = _lineage_schema(schema)
    try:
        scope = _lineage_scope(lineage_expr, sqlglot_schema)
    except Exception as exc:
        _record_diagnostic(
            diagnostics,
            file_path,
            "lineage_scope",
            exc,
            target_table=_strip_db(target_table),
        )
        scope = None
    for idx, col_name in enumerate(display_column_names):
        projection = projections[idx] if idx < len(projections) else None
        lineage_projection = (
            lineage_projections[idx]
            if idx < len(lineage_projections)
            else None
        )
        lineage_col_name = (
            lineage_column_names[idx]
            if idx < len(lineage_column_names)
            else col_name
        )
        if not col_name:
            node_items.append((col_name, projection, None))
            continue
        if projection is not None and not list(
            projection.find_all(exp.Column)
        ):
            node_items.append((col_name, projection, None))
            continue
        if _projection_references_unresolved_source(
            projection,
            unresolved_source_keys,
        ):
            node_items.append((col_name, projection, None))
            continue
        try:
            column_arg = col_name
            if lineage_projection is not None:
                column_arg = _lineage_column_arg(
                    lineage_projection,
                    lineage_col_name,
                )
            else:
                column_arg = lineage_col_name
            node_items.append(
                (
                    col_name,
                    projection,
                    lineage(
                        column=column_arg,
                        sql=lineage_expr,
                        schema=sqlglot_schema,
                        dialect=LINEAGE_DIALECT,
                        scope=scope,
                        trim_selects=False,
                    ),
                )
            )
        except Exception as exc:
            expression = ""
            if projection is not None and hasattr(projection, "sql"):
                expression = projection.sql(dialect="doris")
            _record_diagnostic(
                diagnostics,
                file_path,
                "lineage_column",
                exc,
                target_table=_strip_db(target_table),
                target_column=col_name,
                expression=expression,
            )
            node_items.append((col_name, projection, None))
            continue
    return node_items


def _lineage_nodes_for_select(
    select_expr,
    schema,
    file_path="",
    target_table="",
    diagnostics=None,
):
    nodes = {}
    for col_name, _projection, node in _lineage_node_items_for_select(
        select_expr,
        schema,
        file_path=file_path,
        target_table=target_table,
        diagnostics=diagnostics,
    ):
        if col_name and node is not None:
            nodes[col_name] = node
    return nodes


def _target_column_for_projection(
    idx,
    col_name,
    target_columns=None,
    output_columns=None,
):
    if target_columns is not None and idx < len(target_columns):
        return target_columns[idx]
    if output_columns is not None and idx < len(output_columns):
        return output_columns[idx]
    return col_name


def _align_projection_names_to_targets(query_expr, target_columns):
    """Alias projections by target position before lineage qualify."""
    if not target_columns:
        return query_expr
    if isinstance(query_expr, exp.Select):
        aligned = query_expr.copy()
        expressions = []
        for idx, projection in enumerate(aligned.expressions):
            if (
                idx < len(target_columns)
                and target_columns[idx]
                and not _is_star_projection(projection)
                and _projection_output_name(projection)
                != _canonical_column(target_columns[idx])
            ):
                expressions.append(
                    exp.alias_(
                        projection.copy(),
                        target_columns[idx],
                        quoted=_identifier_needs_quotes(target_columns[idx]),
                    )
                )
                continue
            expressions.append(projection)
        aligned.set("expressions", expressions)
        return aligned
    if isinstance(query_expr, exp.SetOperation):
        aligned = query_expr.copy()
        left = aligned.args.get("this")
        if left is not None:
            aligned.set(
                "this",
                _align_projection_names_to_targets(left, target_columns),
            )
        return aligned
    return query_expr


def _leftmost_set_operand(query_expr):
    current = _unwrap_query_expression(query_expr)
    while isinstance(current, exp.SetOperation):
        current = _unwrap_query_expression(current.args.get("this"))
    return current


def _merge_schema(target, source):
    for catalog, database, table, columns in _iter_schema_tables(source):
        target.setdefault(catalog, {}).setdefault(database, {})[table] = dict(
            columns
        )
    return target


def build_schema_from_ddl(
    ddl_dir,
    dialect="doris",
    default_catalog=None,
    default_db=None,
):
    if isinstance(ddl_dir, (str, Path)):
        ddl_dirs = [Path(ddl_dir)]
    else:
        ddl_dirs = [Path(path) for path in ddl_dir]
    texts = []
    for directory in ddl_dirs:
        if not directory.exists():
            continue
        texts.extend(
            f.read_text(encoding=TEXT_ENCODING)
            for f in sorted(directory.glob("*.sql"))
        )
    return build_schema_from_texts(
        texts,
        dialect=dialect,
        default_catalog=default_catalog,
        default_db=default_db,
    )


def build_schema_from_project_ddl(project):
    cfg = PROJECT_CONFIG[project]
    schema = {}
    ods_dirs = set(project_ods_asset_dirs(project, "ddl"))
    asset_dirs = project_asset_dirs(project, "ddl")
    if not asset_dirs:
        return schema

    for ddl_dir in asset_dirs:
        if ddl_dir in ods_dirs:
            continue
        _merge_schema(
            schema,
            build_schema_from_ddl(
                ddl_dir,
                dialect="doris",
                default_catalog=cfg.get("catalog", "internal"),
                default_db=cfg.get("db"),
            ),
        )

    for ods_dir in ods_dirs:
        catalog = ods_dir.parent.name
        database = ods_dir.name
        _merge_schema(
            schema,
            build_schema_from_ddl(
                ods_dir,
                dialect=ods_source_catalog_ddl_dialect(project, catalog),
                default_catalog=catalog,
                default_db=database,
            ),
        )
    return schema


# ============================================================
# 2. Layer 推断
# ============================================================


def determine_layer(table_name):
    short = _strip_db(table_name)
    return determine_config_layer(short, CURRENT_PROJECT)


# ============================================================
# 3. UPDATE → SELECT 转换
# ============================================================


def update_to_select(update_stmt):
    select_items = []
    for item in update_stmt.expressions:
        select_items.append(exp.alias_(item.expression.copy(), item.this.name))
    select = exp.Select(expressions=select_items)
    target = update_stmt.this
    joins = list(target.args.get("joins") or [])
    if isinstance(target, exp.Table):
        tbl = target.copy()
        tbl.args["joins"] = None
        select.set("from_", exp.From(this=tbl))
        if joins:
            select.set("joins", joins)
    where = update_stmt.args.get("where")
    if where:
        select.set("where", where.copy())
    return select


# ============================================================
# 4. Node DAG → 血缘条目
# ============================================================


def _table_name(tbl_expr):
    parts = []
    if tbl_expr.args.get("catalog"):
        parts.append(_canonical_identifier(tbl_expr.args["catalog"].name))
    if tbl_expr.args.get("db"):
        parts.append(_canonical_identifier(tbl_expr.args["db"].name))
    parts.append(_canonical_identifier(tbl_expr.name))
    return ".".join(parts)


def _extract_leaf_edges(node, target_table, target_col):
    edges = []
    for child in node.downstream:
        _walk_leaf(child, target_table, target_col, edges)
    return edges


def _walk_leaf(node, target_table, target_col, edges):
    if not node.downstream:
        expr = node.expression
        if isinstance(expr, exp.Table):
            edges.append(
                {
                    "source_table": _strip_db(_table_name(expr)),
                    "source_column": _canonical_column(
                        node.name.split(".")[-1]
                    ),
                    "target_table": _strip_db(target_table),
                    "target_column": _canonical_column(target_col),
                }
            )
        elif isinstance(expr, exp.Column):
            edges.append(
                {
                    "source_table": _strip_db(expr.table or "UNKNOWN"),
                    "source_column": _canonical_column(expr.name),
                    "target_table": _strip_db(target_table),
                    "target_column": _canonical_column(target_col),
                }
            )
        return
    for child in node.downstream:
        _walk_leaf(child, target_table, target_col, edges)


# ============================================================
# 4b. 间接血缘提取: WHERE / JOIN ON / GROUP BY / HAVING
# ============================================================


def _iter_relation_sources(select_expr):
    from_ = select_expr.args.get("from_") or select_expr.args.get("from")
    if from_:
        if from_.this:
            yield from_.this
        for relation in from_.expressions or []:
            yield relation
    for join in select_expr.args.get("joins") or []:
        if join.this:
            yield join.this


def _collect_ctes(select_expr):
    ctes = {}
    with_ = select_expr.args.get("with_") or select_expr.args.get("with")
    if not with_:
        return ctes
    for cte in with_.expressions:
        if isinstance(cte.this, (exp.Select, exp.SetOperation)):
            ctes[_canonical_identifier(cte.alias_or_name)] = cte.this
    return ctes


def _schema_has_column(schema, table_name, column_name):
    column_key = _identifier_match_key(column_name)
    if not column_key:
        return False
    for _catalog, _database, _table, columns in _iter_matching_schema_tables(
        schema, table_name
    ):
        if any(
            _identifier_match_key(raw_column) == column_key
            for raw_column in (columns or {})
        ):
            return True
    return False


def _derived_leaf_sources(
    select_expr,
    column_name,
    schema,
    file_path="",
    diagnostics=None,
):
    """将派生表/CTE 输出列追溯到物理源表列。"""
    display_expr = _rewrite_lateral_named_struct_fields(
        _normalize_derived_column_reference_case(select_expr)
    )
    lineage_expr = _normalize_lineage_identifier_case(display_expr)
    lineage_column_name = _lineage_output_column_name(
        display_expr,
        lineage_expr,
        column_name,
    )
    try:
        node = lineage(
            column=lineage_column_name,
            sql=lineage_expr,
            schema=_lineage_schema(schema),
            dialect=LINEAGE_DIALECT,
            trim_selects=False,
        )
    except Exception as exc:
        _record_diagnostic(
            diagnostics,
            file_path,
            "derived_lineage_column",
            exc,
            target_column=column_name,
        )
        return []

    sources = []
    seen = set()
    for edge in _extract_leaf_edges(node, "__derived__", column_name):
        src_table = edge["source_table"]
        src_col = edge["source_column"]
        if src_table == "UNKNOWN":
            continue
        key = (src_table, src_col)
        if key not in seen:
            seen.add(key)
            sources.append(key)
    return sources


def _indirect_entries_from_select(
    select_expr,
    target_table,
    file_path,
    schema,
    default_table=None,
    _visited=None,
    diagnostics=None,
):
    """从 SELECT 的 WHERE / JOIN ON / GROUP BY / HAVING 中提取间接血缘条目"""
    entries = []
    target_table_short = _strip_db(target_table)
    _visited = _visited or set()

    # 收集当前 SELECT 作用域中的物理表、派生表和 CTE 映射。
    from_tables = set()
    alias_map = {}
    derived_sources = {}
    derived_output_lookups = {}
    relation_aliases = []
    ctes = _collect_ctes(select_expr)
    ctes_by_key = {
        _identifier_match_key(cte_name): cte_query
        for cte_name, cte_query in ctes.items()
    }
    unresolved_source_keys = _unresolved_star_source_keys(select_expr)

    def _remember_alias(alias):
        alias_key = _identifier_match_key(alias)
        if alias_key and alias_key not in relation_aliases:
            relation_aliases.append(alias_key)

    for relation in _iter_relation_sources(select_expr):
        if isinstance(relation, exp.Subquery) and isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            alias = _canonical_identifier(relation.alias_or_name)
            alias_key = _identifier_match_key(alias)
            if alias_key:
                derived_sources[alias_key] = relation.this
                derived_output_lookups[alias_key] = (
                    _derived_output_column_lookup(relation.this)
                )
                _remember_alias(alias)
        elif isinstance(relation, exp.Table):
            tbl = _strip_db(_table_name(relation))
            alias = _canonical_identifier(
                relation.alias_or_name or relation.name
            )
            tbl_key = _identifier_match_key(tbl)
            alias_key = _identifier_match_key(alias)
            relation_name_key = _identifier_match_key(relation.name)
            if tbl_key in ctes_by_key:
                cte_query = ctes_by_key[tbl_key]
                if alias_key:
                    derived_sources[alias_key] = cte_query
                    derived_output_lookups[alias_key] = (
                        _derived_output_column_lookup(cte_query)
                    )
                derived_sources[tbl_key] = cte_query
                derived_output_lookups[tbl_key] = (
                    _derived_output_column_lookup(cte_query)
                )
                _remember_alias(alias)
            elif tbl and tbl != "UNKNOWN":
                from_tables.add(tbl)
                if alias_key:
                    alias_map[alias_key] = tbl
                if relation_name_key:
                    alias_map[relation_name_key] = tbl
                _remember_alias(alias)

    def _resolve_column_sources(col):
        tbl_or_alias = _canonical_identifier(col.table)
        col_name = _canonical_column(col.name)
        if tbl_or_alias:
            tbl_or_alias_key = _identifier_match_key(tbl_or_alias)
            if tbl_or_alias_key in unresolved_source_keys:
                return []
            if tbl_or_alias_key in derived_sources:
                return _derived_leaf_sources(
                    derived_sources[tbl_or_alias_key],
                    col_name,
                    schema,
                    file_path=file_path,
                    diagnostics=diagnostics,
                )
            return [
                (
                    _strip_db(alias_map.get(tbl_or_alias_key, tbl_or_alias)),
                    col_name,
                )
            ]

        if unresolved_source_keys:
            return []

        col_key = _identifier_match_key(col_name)
        derived_aliases = [
            a
            for a in relation_aliases
            if a in derived_sources
            and col_key in (derived_output_lookups.get(a) or {})
        ]
        if len(derived_aliases) == 1:
            sources = _derived_leaf_sources(
                derived_sources[derived_aliases[0]],
                col_name,
                schema,
                file_path=file_path,
                diagnostics=diagnostics,
            )
            if sources:
                return sources
        if len(from_tables) == 1:
            return [(next(iter(from_tables)), col_name)]
        if default_table:
            return [(_strip_db(default_table), col_name)]
        return []

    def _add_entries(condition_type, expression, columns):
        for col in columns:
            for tbl, src_col in _resolve_column_sources(col):
                if tbl == "UNKNOWN":
                    continue
                if not _schema_has_column(schema, tbl, src_col):
                    continue
                entries.append(
                    {
                        "lineage_type": "indirect",
                        "source_table": tbl,
                        "source_column": _canonical_column(src_col),
                        "target_table": target_table_short,
                        "target_column": "",
                        "condition_type": condition_type,
                        "condition_expression": expression.sql(dialect="doris")
                        if hasattr(expression, "sql")
                        else str(expression),
                        "source_file": file_path,
                    }
                )

    # 先递归提取派生表/CTE 内部的过滤、分组等间接依赖。
    unique_derived = []
    seen_derived = set()
    for derived_select in derived_sources.values():
        marker = id(derived_select)
        if marker in seen_derived:
            continue
        seen_derived.add(marker)
        unique_derived.append(derived_select)

    for derived_select in unique_derived:
        marker = id(derived_select)
        if marker in _visited:
            continue
        _visited.add(marker)
        entries.extend(
            _indirect_entries_from_select(
                derived_select,
                target_table,
                file_path,
                schema,
                default_table,
                _visited,
                diagnostics,
            )
        )

    # WHERE
    where = select_expr.args.get("where")
    if where:
        cols = list(where.this.find_all(exp.Column))
        _add_entries("WHERE", where.this, cols)

    # JOIN ON
    joins = select_expr.args.get("joins") or []
    for join in joins:
        on = join.args.get("on")
        if on:
            cols = list(on.find_all(exp.Column))
            _add_entries("JOIN_ON", on, cols)

    # GROUP BY
    group = select_expr.args.get("group")
    if group:
        for expr_ in group.expressions:
            cols = list(expr_.find_all(exp.Column))
            _add_entries("GROUP_BY", expr_, cols)

    # HAVING
    having = select_expr.args.get("having")
    if having:
        cols = list(having.this.find_all(exp.Column))
        _add_entries("HAVING", having.this, cols)

    return entries


def _extract_indirect(
    inner,
    target_table,
    file_path,
    schema,
    diagnostics=None,
):
    """从可能包含 CTE 的 SELECT 中提取间接血缘"""
    entries = []
    default_table = _strip_db(target_table)
    # 主查询
    if isinstance(inner, exp.With):
        inner = inner.this
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        entries.extend(
            _indirect_entries_from_select(
                inner,
                target_table,
                file_path,
                schema,
                default_table,
                diagnostics=diagnostics,
            )
        )
    return entries


def _extract_indirect_from_delete(delete_stmt, file_path):
    """DELETE 语句的 WHERE 条件产生自引用间接血缘"""
    target_table = _strip_db(_target_table_sql(delete_stmt.this))
    entries = []
    where = delete_stmt.args.get("where")
    if where:
        for col in where.this.find_all(exp.Column):
            tbl = _strip_db(_canonical_identifier(col.table) or target_table)
            entries.append(
                {
                    "lineage_type": "indirect",
                    "source_table": tbl,
                    "source_column": _canonical_column(col.name),
                    "target_table": target_table,
                    "target_column": "",
                    "condition_type": "WHERE",
                    "condition_expression": where.this.sql(dialect="doris"),
                    "source_file": file_path,
                }
            )
    return entries


def _handle_delete(stmt, file_path):
    """DELETE 语句: 提取 WHERE 条件中的自引用间接血缘"""
    return _extract_indirect_from_delete(stmt, file_path)


# ============================================================
# 5. 核心血缘提取
# ============================================================


STATS = {"parse_failures": 0, "lineage_failures": 0}
"""模块级统计,在 main() 结束后输出"""


def _reset_stats():
    STATS["parse_failures"] = 0
    STATS["lineage_failures"] = 0


def _add_stats(stats):
    for key in STATS:
        STATS[key] += int((stats or {}).get(key, 0))


@dataclass
class TaskWorkItem:
    index: int
    source_file: str
    sql_text: str
    sql_hash: str = ""
    cache_key: str = ""


@dataclass
class ParsedTaskContext:
    work_item: TaskWorkItem
    statements: List[Any]
    task_facts: Dict[str, Any]
    referenced_tables: Tuple[str, ...]
    cte_names: Tuple[str, ...]
    task_schema: Dict[str, Any]
    missing_ddl_tables: List[str]
    missing_source_ddl: List[str]
    missing_target_ddl: List[str]
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def index(self):
        return self.work_item.index

    @property
    def source_file(self):
        return self.work_item.source_file

    @property
    def sql_hash(self):
        return self.work_item.sql_hash


def _task_context_from_statements(
    work_item,
    statements,
    schema,
    diagnostics=None,
):
    diagnostics = diagnostics if diagnostics is not None else []
    referenced_tables = tuple(
        sorted(collect_statement_table_names(statements))
    )
    cte_names = tuple(sorted(collect_statement_cte_names(statements)))
    task_facts = extract_task_table_facts_from_statements(
        statements,
        work_item.source_file,
        default_catalog=_default_catalog(),
        default_db=_default_db(),
    )
    task_schema = _task_schema_for_table_names(schema, referenced_tables)
    if not work_item.sql_hash:
        work_item.sql_hash = _task_sql_hash(work_item)
    return ParsedTaskContext(
        work_item=work_item,
        statements=statements,
        task_facts=task_facts,
        referenced_tables=referenced_tables,
        cte_names=cte_names,
        task_schema=task_schema,
        missing_ddl_tables=[],
        missing_source_ddl=[],
        missing_target_ddl=[],
        diagnostics=diagnostics,
    )


def _parse_task_context(work_item, schema, diagnostics=None):
    statements = sqlglot.parse(
        _sqlglot_task_sql(work_item.sql_text), dialect="doris"
    )
    return _task_context_from_statements(
        work_item,
        statements,
        schema,
        diagnostics=diagnostics,
    )


def _task_fact_result_fields(task_facts):
    def sorted_tables(field):
        return sorted(
            task_facts.get(field) or [],
            key=_identifier_match_key,
        )

    return {
        "input_tables": sorted_tables("input_tables"),
        "output_tables": sorted_tables("output_tables"),
        "created_tables": sorted_tables("created_tables"),
        "temporary_tables": sorted_tables("temporary_tables"),
        "local_lifecycle_tables": task_facts.get("local_lifecycle_tables")
        or [],
    }


def _persistent_created_table_schemas(context):
    """Return schemas for CTAS/create outputs that survive this task."""
    output_keys = {
        _table_identity_match_key(table_name)
        for table_name in context.task_facts.get("output_tables") or []
    }
    records = {}
    for table_name in context.task_facts.get("created_tables") or []:
        table_key = _table_identity_match_key(table_name)
        if table_key not in output_keys:
            continue
        for catalog, database, table, columns in _iter_matching_schema_tables(
            context.task_schema,
            table_name,
        ):
            clean_columns = {
                _canonical_column(column_name): str(column_type or "UNKNOWN")
                for column_name, column_type in (columns or {}).items()
                if _canonical_column(column_name)
            }
            if not clean_columns:
                continue
            records[table_key] = {
                "name": _qualified_table_name(catalog, database, table),
                "columns": clean_columns,
            }
    return [records[key] for key in sorted(records)]


def _task_result_from_context(context, entries):
    result = {
        "index": context.index,
        "source_file": context.source_file,
        "entries": entries,
        "transient_tables": context.task_facts["transient_tables"],
        "missing_ddl_tables": context.missing_ddl_tables,
        "missing_source_ddl": context.missing_source_ddl,
        "missing_target_ddl": context.missing_target_ddl,
        "referenced_tables": list(context.referenced_tables),
        "sql_hash": context.sql_hash,
        "stats": dict(STATS),
        "errors": context.diagnostics,
        "process_table_schemas": _persistent_created_table_schemas(context),
    }
    result.update(_task_fact_result_fields(context.task_facts))
    return result


def extract_lineage_from_statements(
    statements,
    file_path,
    schema,
    diagnostics=None,
):
    work_item = TaskWorkItem(
        index=-1,
        source_file=file_path,
        sql_text="",
    )
    context = _task_context_from_statements(
        work_item,
        statements,
        schema,
        diagnostics=diagnostics,
    )
    return extract_lineage_from_context(context)


def _add_context_missing_ddl(context, category, table_name):
    display_name = _strip_db(table_name)
    if not display_name:
        return
    missing_tables = getattr(context, category)
    if display_name not in missing_tables:
        missing_tables.append(display_name)
        missing_tables.sort()
    context.missing_ddl_tables = sorted(
        set(context.missing_source_ddl) | set(context.missing_target_ddl)
    )


def _record_statement_missing_ddl(context, stmt):
    for table_name in _statement_source_table_names(stmt):
        if not _schema_has_table(context.task_schema, table_name):
            _add_context_missing_ddl(
                context,
                "missing_source_ddl",
                table_name,
            )
    for table_name in _statement_existing_target_table_names(stmt):
        if not _schema_has_table(context.task_schema, table_name):
            _add_context_missing_ddl(
                context,
                "missing_target_ddl",
                table_name,
            )


def extract_lineage_from_context(context):
    entries = []
    for stmt in context.statements:
        if stmt is None:
            continue
        _record_statement_missing_ddl(context, stmt)
        if isinstance(stmt, exp.Insert):
            entries.extend(
                _handle_insert(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Update):
            entries.extend(
                _handle_update(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Create):
            entries.extend(
                _handle_create(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
            _register_task_table_schema(
                context.task_schema,
                _target_table_sql(stmt.this),
                _created_table_columns_from_schema(
                    stmt,
                    context.task_schema,
                    file_path=context.source_file,
                    diagnostics=None,
                ),
            )
        elif isinstance(stmt, exp.Alter):
            _apply_alter_table_to_task_schema(context.task_schema, stmt)
        elif _is_table_drop_statement(stmt):
            _drop_task_table_schema(
                context.task_schema,
                _target_table_sql(stmt.this),
            )
        elif isinstance(stmt, exp.Merge):
            entries.extend(
                _handle_merge(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Delete):
            entries.extend(_handle_delete(stmt, context.source_file))
        elif isinstance(stmt, exp.Select) and stmt.args.get("into"):
            entries.extend(
                _handle_select_into(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
    task_schema_lookup = _schema_lookup(context.task_schema)
    return [
        _canonical_lineage_entry(entry, task_schema_lookup)
        for entry in entries
    ]


def extract_lineage_from_sql(sql_text, file_path, schema, diagnostics=None):
    try:
        statements = sqlglot.parse(
            _sqlglot_task_sql(sql_text), dialect="doris"
        )
    except Exception as e:
        print(f"  解析失败 {file_path}: {e}")
        _record_diagnostic(diagnostics, file_path, "parse", e)
        STATS["parse_failures"] += 1
        return []

    return extract_lineage_from_statements(
        statements,
        file_path,
        schema,
        diagnostics=diagnostics,
    )


def _extract_task_work_item(work_item, schema):
    previous_stats = dict(STATS)
    _reset_stats()
    try:
        diagnostics = []
        try:
            statements = sqlglot.parse(
                _sqlglot_task_sql(work_item.sql_text),
                dialect="doris",
            )
        except Exception as e:
            print(f"  解析失败 {work_item.source_file}: {e}")
            _record_diagnostic(diagnostics, work_item.source_file, "parse", e)
            STATS["parse_failures"] += 1
            if not work_item.sql_hash:
                work_item.sql_hash = _task_sql_hash(work_item)
            task_facts = extract_task_table_facts(
                work_item.sql_text,
                work_item.source_file,
                default_catalog=_default_catalog(),
                default_db=_default_db(),
            )
            result = {
                "index": work_item.index,
                "source_file": work_item.source_file,
                "entries": [],
                "transient_tables": task_facts["transient_tables"],
                "missing_ddl_tables": [],
                "missing_source_ddl": [],
                "missing_target_ddl": [],
                "referenced_tables": [],
                "sql_hash": work_item.sql_hash,
                "stats": dict(STATS),
                "errors": diagnostics,
                "process_table_schemas": [],
            }
            result.update(_task_fact_result_fields(task_facts))
            result["schema_slice_hash"] = _schema_slice_hash_for_tables(
                schema,
                result["referenced_tables"],
            )
            return result

        context = _task_context_from_statements(
            work_item,
            statements,
            schema,
            diagnostics=diagnostics,
        )
        entries = extract_lineage_from_context(context)
        result = _task_result_from_context(context, entries)
        result["schema_slice_hash"] = _schema_slice_hash_for_tables(
            schema,
            result["referenced_tables"],
        )
        return result
    finally:
        STATS.update(previous_stats)


_PARALLEL_SCHEMA = None


def _init_parallel_worker(project_name, schema):
    global _PARALLEL_SCHEMA
    configure_project(project_name)
    _PARALLEL_SCHEMA = schema


def _extract_task_work_item_parallel(work_item):
    if _PARALLEL_SCHEMA is None:
        raise RuntimeError("parallel lineage worker schema is not initialized")
    return _extract_task_work_item(work_item, _PARALLEL_SCHEMA)


def _task_failure_result(work_item, error, stage="worker"):
    return {
        "index": work_item.index,
        "source_file": work_item.source_file,
        "entries": [],
        "transient_tables": [],
        "input_tables": [],
        "output_tables": [],
        "created_tables": [],
        "temporary_tables": [],
        "local_lifecycle_tables": [],
        "missing_ddl_tables": [],
        "missing_source_ddl": [],
        "missing_target_ddl": [],
        "referenced_tables": [],
        "stats": {},
        "errors": [
            {
                "source_file": work_item.source_file,
                "stage": stage,
                "severity": _diagnostic_severity(stage),
                "error": _diagnostic_error(error),
            }
        ],
        "process_table_schemas": [],
    }


def _read_task_work_items(task_files, tasks_dir, source_file_for_path=None):
    work_items = []
    for index, task_file in enumerate(task_files):
        task_path = Path(task_file)
        if source_file_for_path:
            source_file = source_file_for_path(task_path)
        else:
            source_file = task_path.relative_to(tasks_dir).as_posix()
        work_items.append(
            TaskWorkItem(
                index=index,
                source_file=source_file,
                sql_text=task_path.read_text(encoding=TEXT_ENCODING),
            )
        )
    return work_items


def _task_result_from_cache(work_item, cached):
    result = {
        "index": work_item.index,
        "source_file": work_item.source_file,
        "entries": cached.get("entries") or [],
        "transient_tables": cached.get("transient_tables") or [],
        "input_tables": cached.get("input_tables") or [],
        "output_tables": cached.get("output_tables") or [],
        "created_tables": cached.get("created_tables") or [],
        "temporary_tables": cached.get("temporary_tables") or [],
        "local_lifecycle_tables": cached.get("local_lifecycle_tables") or [],
        "missing_ddl_tables": cached.get("missing_ddl_tables") or [],
        "missing_source_ddl": cached.get("missing_source_ddl") or [],
        "missing_target_ddl": cached.get("missing_target_ddl") or [],
        "referenced_tables": cached.get("referenced_tables") or [],
        "stats": cached.get("stats") or {},
        "errors": cached.get("errors") or [],
        "process_table_schemas": cached.get("process_table_schemas") or [],
        "cache_hit": True,
    }
    for key in (
        "sql_hash",
        "schema_slice_hash",
        "extractor_hash",
        "project_config",
    ):
        if key in cached:
            result[key] = cached[key]
    return result


def _project_config_for_cache(project):
    return PROJECT_CONFIG.get(
        project,
        {
            "catalog": CURRENT_CATALOG,
            "db": CURRENT_DB,
        },
    )


def _cache_project_config(project):
    from dw_refactor_agent.lineage.task_cache import cache_project_config

    return cache_project_config(_project_config_for_cache(project))


def _extractor_hash_for_cache():
    from dw_refactor_agent.lineage.task_cache import extractor_version_hash

    return extractor_version_hash(
        (
            __file__,
            Path(__file__).with_name("lineage_projection.py"),
            Path(__file__).with_name("runtime_binding.py"),
            Path(__file__).with_name("sql_task_facts.py"),
        )
    )


def _task_sql_hash(work_item):
    from dw_refactor_agent.lineage.task_cache import sha256_text

    return sha256_text(work_item.sql_text)


def _schema_slice_hash_for_tables(schema, referenced_tables):
    from dw_refactor_agent.lineage.task_cache import stable_json_hash

    if referenced_tables:
        return stable_json_hash(slice_schema(schema, referenced_tables))
    return stable_json_hash(_copy_schema(schema))


def _cache_can_seed_process_table_schemas(
    work_item,
    cached,
    project,
    extractor_hash,
):
    if not cached or "process_table_schemas" not in cached:
        return False
    sql_hash = work_item.sql_hash or _task_sql_hash(work_item)
    return (
        cached.get("sql_hash") == sql_hash
        and cached.get("extractor_hash") == extractor_hash
        and cached.get("project_config") == _cache_project_config(project)
    )


def _process_table_schema_catalog(task_results, schema=None):
    """Return schemas supplied by one unambiguous persistent creator."""
    formal_keys = {
        _schema_table_match_key(catalog, database, table)
        for catalog, database, table, _columns in _iter_schema_tables(schema)
    }
    consumers = {}
    for result in task_results or []:
        source_file = str(result.get("source_file") or "")
        for table_name in result.get("input_tables") or []:
            consumers.setdefault(
                _table_identity_match_key(table_name),
                set(),
            ).add(source_file)

    candidates = {}
    for result in task_results or []:
        source_file = str(result.get("source_file") or "")
        output_keys = {
            _table_identity_match_key(table_name)
            for table_name in result.get("output_tables") or []
        }
        for record in result.get("process_table_schemas") or []:
            table_name = record.get("name")
            columns = record.get("columns") or {}
            table_key = _table_identity_match_key(table_name)
            external_consumers = consumers.get(table_key, set()) - {
                source_file
            }
            if (
                not table_key[2]
                or table_key in formal_keys
                or table_key not in output_keys
                or not columns
                or not external_consumers
            ):
                continue
            candidates.setdefault(table_key, {})[source_file] = {
                "name": table_name,
                "columns": dict(columns),
            }

    catalog = []
    for table_key in sorted(candidates):
        by_source = candidates[table_key]
        if len(by_source) != 1:
            continue
        catalog.append(next(iter(by_source.values())))
    return catalog


def _schema_with_process_table_catalog(schema, catalog):
    if not catalog:
        return schema
    combined = _copy_schema(schema)
    formal_keys = {
        _schema_table_match_key(catalog_name, database, table)
        for catalog_name, database, table, _columns in _iter_schema_tables(
            schema
        )
    }
    for record in catalog or []:
        table_name = record.get("name")
        if _table_identity_match_key(table_name) in formal_keys:
            continue
        _register_task_table_schema(
            combined,
            table_name,
            record.get("columns") or {},
        )
    return combined


def _cache_key_from_cached_metadata(
    work_item,
    cached,
    schema,
    project,
    extractor_hash,
):
    required_keys = (
        "sql_hash",
        "referenced_tables",
        "schema_slice_hash",
        "extractor_hash",
        "project_config",
    )
    if not all(key in cached for key in required_keys):
        return None

    sql_hash = work_item.sql_hash or _task_sql_hash(work_item)
    if cached.get("sql_hash") != sql_hash:
        return None
    if cached.get("extractor_hash") != extractor_hash:
        return None
    if cached.get("project_config") != _cache_project_config(project):
        return None

    referenced_tables = cached.get("referenced_tables") or []
    schema_slice_hash = _schema_slice_hash_for_tables(
        schema,
        referenced_tables,
    )
    if cached.get("schema_slice_hash") != schema_slice_hash:
        return None

    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    metadata = TaskCacheMetadata(
        sql_hash=sql_hash,
        referenced_tables=tuple(referenced_tables),
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
    )
    return _task_cache_key_from_metadata(
        work_item,
        project,
        metadata,
    )


def _task_cache_metadata_from_context(
    context,
    schema,
    project,
    extractor_hash,
):
    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    schema_slice_hash = _schema_slice_hash_for_tables(
        schema,
        context.referenced_tables,
    )
    return TaskCacheMetadata(
        sql_hash=context.sql_hash,
        referenced_tables=context.referenced_tables,
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
    )


def _task_cache_metadata_from_result(
    result,
    work_item,
    schema,
    project,
    extractor_hash,
):
    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    referenced_tables = tuple(sorted(result.get("referenced_tables") or []))
    sql_hash = (
        result.get("sql_hash")
        or work_item.sql_hash
        or _task_sql_hash(work_item)
    )
    schema_slice_hash = result.get("schema_slice_hash")
    if not schema_slice_hash:
        schema_slice_hash = _schema_slice_hash_for_tables(
            schema,
            referenced_tables,
        )
    return TaskCacheMetadata(
        sql_hash=sql_hash,
        referenced_tables=referenced_tables,
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
    )


def _task_cache_key_from_metadata(work_item, project, metadata):
    from dw_refactor_agent.lineage.task_cache import task_cache_key

    return task_cache_key(
        project=project,
        source_file=work_item.source_file,
        metadata=metadata,
    )


def _result_with_cache_metadata(result, metadata):
    cached_result = dict(result)
    cached_result.update(
        {
            "sql_hash": metadata.sql_hash,
            "referenced_tables": list(metadata.referenced_tables),
            "schema_slice_hash": metadata.schema_slice_hash,
            "extractor_hash": metadata.extractor_hash,
            "project_config": metadata.project_config,
        }
    )
    return cached_result


def _cache_metadata_for_result(
    result, work_item, schema, project, extractor_hash
):
    metadata = _task_cache_metadata_from_result(
        result,
        work_item,
        schema,
        project,
        extractor_hash,
    )
    cache_key = _task_cache_key_from_metadata(
        work_item,
        project,
        metadata,
    )
    return cache_key, _result_with_cache_metadata(result, metadata)


def _load_previous_task_cache(path):
    from dw_refactor_agent.lineage.task_cache import load_task_cache

    return load_task_cache(path)


def _build_task_cache(project, schema, task_cache_entries):
    from dw_refactor_agent.lineage.task_cache import (
        TASK_CACHE_FORMAT_VERSION,
        stable_json_hash,
    )

    return {
        "format_version": TASK_CACHE_FORMAT_VERSION,
        "project": project,
        "schema_hash": stable_json_hash(schema),
        "tasks": sorted(
            task_cache_entries,
            key=lambda item: item.get("source_file", ""),
        ),
    }


def _cache_entry_from_result(result, cache_key):
    from dw_refactor_agent.lineage.task_cache import cache_entry_from_result

    return cache_entry_from_result(result, cache_key)


def _notify_progress(progress_callback, completed, total, result):
    if progress_callback is not None:
        progress_callback(completed, total, result)


def _extract_task_work_items_serial(work_items, schema, progress_callback):
    task_results = []
    total = len(work_items)
    for completed, work_item in enumerate(work_items, start=1):
        try:
            result = _extract_task_work_item(work_item, schema)
        except Exception as exc:
            result = _task_failure_result(work_item, exc)
        task_results.append(result)
        _notify_progress(progress_callback, completed, total, result)
    return task_results


def _extract_task_work_items_parallel(
    work_items,
    schema,
    parallel,
    progress_callback,
):
    max_workers = min(parallel, len(work_items))
    try:
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_parallel_worker,
            initargs=(CURRENT_PROJECT, schema),
        ) as executor:
            future_to_item = {
                executor.submit(_extract_task_work_item_parallel, work_item): (
                    work_item
                )
                for work_item in work_items
            }
            task_results = []
            total = len(work_items)
            for completed, future in enumerate(
                as_completed(future_to_item),
                start=1,
            ):
                work_item = future_to_item[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = _task_failure_result(work_item, exc)
                task_results.append(result)
                _notify_progress(
                    progress_callback,
                    completed,
                    total,
                    result,
                )
            return sorted(
                task_results,
                key=lambda result: result["index"],
            )
    except (NotImplementedError, OSError, PermissionError):
        return _extract_task_work_items_serial(
            work_items,
            schema,
            progress_callback,
        )


def _extract_task_work_items(
    work_items,
    schema,
    parallel,
    progress_callback=None,
):
    if len(work_items) <= 1 or parallel == 1:
        return _extract_task_work_items_serial(
            work_items,
            schema,
            progress_callback,
        )
    return _extract_task_work_items_parallel(
        work_items,
        schema,
        parallel,
        progress_callback,
    )


def _propagate_process_table_schemas(
    task_results,
    work_items_by_index,
    schema,
    parallel,
    initial_schema,
    initial_catalog,
):
    """Re-extract consumers until cross-Job process schemas reach a fixpoint."""
    results_by_index = {result["index"]: result for result in task_results}
    final_schema = schema
    max_rounds = len(work_items_by_index) + 1
    for _round in range(max_rounds):
        catalog = _process_table_schema_catalog(
            results_by_index.values(),
            schema=schema,
        )
        if _round == 0 and catalog == initial_catalog:
            return (
                [
                    results_by_index[index]
                    for index in sorted(results_by_index)
                ],
                initial_schema,
            )
        final_schema = _schema_with_process_table_catalog(schema, catalog)
        stale_items = []
        for index, result in sorted(results_by_index.items()):
            if "schema_slice_hash" not in result:
                continue
            expected_hash = _schema_slice_hash_for_tables(
                final_schema,
                result.get("referenced_tables") or [],
            )
            if result.get("schema_slice_hash") != expected_hash:
                stale_items.append(work_items_by_index[index])
        if not stale_items:
            return (
                [
                    results_by_index[index]
                    for index in sorted(results_by_index)
                ],
                final_schema,
            )

        refreshed = _extract_task_work_items(
            stale_items,
            final_schema,
            parallel,
        )
        for result in refreshed:
            results_by_index[result["index"]] = result

    raise RuntimeError(
        "cross-Job process table schema propagation did not converge"
    )


def extract_lineage_from_task_files(
    task_files,
    tasks_dir,
    schema,
    parallel=1,
    progress_callback=None,
    previous_cache_file=None,
    cache_project=None,
    source_file_for_path=None,
):
    work_items = _read_task_work_items(
        task_files,
        tasks_dir,
        source_file_for_path=source_file_for_path,
    )
    parallel = max(1, int(parallel or 1))
    cache_enabled = previous_cache_file is not None
    cache_project = cache_project or CURRENT_PROJECT
    previous_cache = (
        _load_previous_task_cache(previous_cache_file) if cache_enabled else {}
    )
    extractor_hash = _extractor_hash_for_cache() if cache_enabled else None
    work_items_by_index = {item.index: item for item in work_items}

    cached_schema_seeds = []
    if cache_enabled:
        for work_item in work_items:
            work_item.sql_hash = _task_sql_hash(work_item)
            cached = previous_cache.get(work_item.source_file)
            if _cache_can_seed_process_table_schemas(
                work_item,
                cached,
                cache_project,
                extractor_hash,
            ):
                cached_schema_seeds.append(cached)
    initial_catalog = _process_table_schema_catalog(
        cached_schema_seeds,
        schema=schema,
    )
    extraction_schema = _schema_with_process_table_catalog(
        schema,
        initial_catalog,
    )

    total = len(work_items)
    completed = 0
    cached_results = []
    uncached_work_items = []
    for work_item in work_items:
        if not cache_enabled:
            uncached_work_items.append(work_item)
            continue
        cached = previous_cache.get(work_item.source_file)
        if cached:
            cache_key = _cache_key_from_cached_metadata(
                work_item,
                cached,
                extraction_schema,
                cache_project,
                extractor_hash,
            )
            work_item.cache_key = cache_key or ""

        if cached and cached.get("cache_key") == work_item.cache_key:
            result = _task_result_from_cache(work_item, cached)
            cached_results.append(result)
            completed += 1
            _notify_progress(progress_callback, completed, total, result)
        else:
            uncached_work_items.append(work_item)

    def notify_uncached_progress(_completed, _total, result):
        nonlocal completed
        completed += 1
        _notify_progress(progress_callback, completed, total, result)

    computed_results = _extract_task_work_items(
        uncached_work_items,
        extraction_schema,
        parallel,
        notify_uncached_progress,
    )
    task_results = sorted(
        [*cached_results, *computed_results],
        key=lambda result: result["index"],
    )
    task_results, extraction_schema = _propagate_process_table_schemas(
        task_results,
        work_items_by_index,
        schema,
        parallel,
        extraction_schema,
        initial_catalog,
    )

    task_cache_entries = []
    if cache_enabled:
        for result in task_results:
            work_item = work_items_by_index[result["index"]]
            cache_key, cache_result = _cache_metadata_for_result(
                result,
                work_item,
                extraction_schema,
                cache_project,
                extractor_hash,
            )
            task_cache_entries.append(
                _cache_entry_from_result(cache_result, cache_key)
            )

    all_lineage = []
    transient_tables = []
    missing_ddl_tables = set()
    missing_source_ddl = set()
    missing_target_ddl = set()
    errors = []
    for result in task_results:
        all_lineage.extend(result["entries"])
        transient_tables.extend(result["transient_tables"])
        missing_ddl_tables.update(result.get("missing_ddl_tables") or [])
        missing_source_ddl.update(result.get("missing_source_ddl") or [])
        missing_target_ddl.update(result.get("missing_target_ddl") or [])
        _add_stats(result["stats"])
        errors.extend(result.get("errors") or [])

    return {
        "lineage": all_lineage,
        "transient_tables": transient_tables,
        "missing_ddl_tables": sorted(missing_ddl_tables),
        "missing_source_ddl": sorted(missing_source_ddl),
        "missing_target_ddl": sorted(missing_target_ddl),
        "task_results": task_results,
        "task_cache": (
            _build_task_cache(
                cache_project,
                extraction_schema,
                task_cache_entries,
            )
            if cache_enabled
            else None
        ),
        "errors": errors,
    }


def format_missing_ddl_warnings(task_results, missing_ddl_tables):
    lines = []
    for result in task_results or []:
        source_missing = sorted(result.get("missing_source_ddl") or [])
        target_missing = sorted(result.get("missing_target_ddl") or [])
        if source_missing or target_missing:
            if source_missing:
                lines.append(
                    "WARNING missing source DDL: "
                    f"{result.get('source_file', '')} reads "
                    f"{', '.join(source_missing)}, "
                    "but no schema DDL was found."
                )
            if target_missing:
                lines.append(
                    "WARNING missing target DDL: "
                    f"{result.get('source_file', '')} writes "
                    f"{', '.join(target_missing)}, "
                    "but no schema DDL was found."
                )
            continue
        missing_tables = sorted(result.get("missing_ddl_tables") or [])
        if not missing_tables:
            continue
        lines.append(
            "WARNING missing DDL: "
            f"{result.get('source_file', '')} references "
            f"{', '.join(missing_tables)}, "
            "but no schema DDL was found."
        )
    if missing_ddl_tables:
        lines.append(
            "DDL warning: "
            f"{len(missing_ddl_tables)} referenced tables are missing "
            "from schema DDL."
        )
    return lines


def _truncate_diagnostic_text(text, limit=300):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _format_diagnostic(diagnostic):
    severity = diagnostic.get("severity") or _diagnostic_severity(
        diagnostic.get("stage")
    )
    parts = [severity, str(diagnostic.get("stage") or "unknown")]
    target_table = diagnostic.get("target_table")
    target_column = diagnostic.get("target_column")
    if target_table or target_column:
        target = ".".join(
            part for part in (target_table, target_column) if part
        )
        parts.append(f"target={target}")
    expression = diagnostic.get("expression")
    if expression:
        parts.append(f"expr={_truncate_diagnostic_text(expression)}")
    parts.append(str(diagnostic.get("error") or ""))
    return " | ".join(part for part in parts if part)


def _diagnostics_by_source_file(diagnostics):
    grouped = {}
    for diagnostic in diagnostics or []:
        source_file = diagnostic.get("source_file") or "<unknown>"
        grouped.setdefault(source_file, []).append(diagnostic)
    return grouped


def _should_write_lineage_output(
    fatal_diagnostics,
    output_paths,
    force_overwrite_on_error=False,
):
    if not fatal_diagnostics or force_overwrite_on_error:
        return True
    return not any(Path(path).exists() for path in output_paths if path)


def _trace_lineage(
    target_table,
    select_expr,
    schema,
    file_path,
    target_columns=None,
    diagnostics=None,
):
    entries = []
    (
        expanded_select_expr,
        output_columns,
        has_unresolved_output,
    ) = _expand_query_star_projections(
        select_expr,
        schema,
        file_path=file_path,
        target_table=target_table,
        diagnostics=diagnostics,
    )
    expanded_select_expr = _align_projection_names_to_targets(
        expanded_select_expr,
        target_columns,
    )
    output_columns = [
        _target_column_for_projection(
            idx,
            col_name,
            target_columns=target_columns,
        )
        for idx, col_name in enumerate(
            _projection_output_names(expanded_select_expr)
        )
    ]
    lineage_select_expr = expanded_select_expr
    if has_unresolved_output and isinstance(
        expanded_select_expr, exp.SetOperation
    ):
        lineage_select_expr = _leftmost_set_operand(expanded_select_expr)
    node_items = _lineage_node_items_for_select(
        lineage_select_expr,
        schema,
        file_path=file_path,
        target_table=target_table,
        diagnostics=diagnostics,
    )
    has_direct_nodes = any(
        node is not None for _col_name, _projection, node in node_items
    )
    if not has_direct_nodes and not output_columns:
        output_columns = _projection_output_names(expanded_select_expr)
    if not has_direct_nodes and not output_columns:
        _record_diagnostic(
            diagnostics,
            file_path,
            "lineage_target",
            ValueError("No lineage nodes or output columns extracted"),
            target_table=_strip_db(target_table),
        )
        STATS["lineage_failures"] += 1
        return entries

    first_unresolved_star_idx = None
    if isinstance(lineage_select_expr, exp.Select):
        for idx, projection in enumerate(lineage_select_expr.expressions):
            if _is_star_projection(projection):
                first_unresolved_star_idx = idx
                break

    for idx, (col_name, projection, node) in enumerate(node_items):
        if (
            first_unresolved_star_idx is not None
            and idx > first_unresolved_star_idx
        ):
            continue
        if node is None or not col_name:
            continue
        target_col = _target_column_for_projection(
            idx,
            col_name,
            target_columns=target_columns,
            output_columns=output_columns,
        )
        target_col = _canonical_column(target_col)
        edges = _extract_leaf_edges(node, target_table, target_col)
        if not edges:
            edges = _fallback_direct_edges_from_expression(
                node.expression,
                target_table,
                target_col,
                schema,
            )
        seen = set()
        for edge in edges:
            key = (
                edge["source_table"],
                edge["source_column"],
                edge["target_table"],
                edge["target_column"],
            )
            if key not in seen:
                seen.add(key)
                if _identifier_match_key(edge["source_column"]) == "*":
                    continue
                entries.append(
                    {
                        **edge,
                        "lineage_type": "direct",
                        "expression": _expression_sql(
                            projection
                            if projection is not None
                            else node.expression
                        ),
                        "source_file": file_path,
                    }
                )

    for idx, projection in enumerate(_projection_items(expanded_select_expr)):
        if (
            first_unresolved_star_idx is not None
            and idx > first_unresolved_star_idx
        ):
            continue
        if list(projection.find_all(exp.Column)):
            continue
        if _is_star_projection(projection):
            continue
        target_col = _target_column_for_projection(
            idx,
            projection.alias_or_name,
            target_columns=target_columns,
            output_columns=output_columns,
        )
        target_col = _canonical_column(target_col)
        if not target_col:
            continue
        key = (
            "constant",
            _strip_db(target_table),
            target_col,
            projection.sql(dialect="doris"),
        )
        existing = {
            (
                entry.get("transformation_type"),
                entry.get("target_table"),
                entry.get("target_column"),
                entry.get("expression"),
            )
            for entry in entries
        }
        if key in existing:
            continue
        entries.append(
            _constant_lineage_entry(
                target_table,
                target_col,
                projection,
                file_path,
            )
        )

    # 间接血缘: WHERE / JOIN ON / GROUP BY / HAVING
    indirect_entries = _extract_indirect(
        expanded_select_expr,
        target_table,
        file_path,
        schema,
        diagnostics=diagnostics,
    )
    entries.extend(indirect_entries)

    return entries


def _handle_insert(stmt, file_path, schema, diagnostics=None):
    target_table = _target_table_sql(stmt.this)
    target_columns = _target_columns(stmt.this)
    if target_columns is None:
        target_columns = _schema_columns_for_table(schema, target_table)
    inner = stmt.expression
    if isinstance(inner, exp.Values):
        return _extract_values_lineage(target_table, inner, file_path)
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _trace_lineage(
            target_table,
            inner,
            schema,
            file_path,
            target_columns,
            diagnostics,
        )
    return []


def _handle_update(stmt, file_path, schema, diagnostics=None):
    target_table = _target_table_sql(stmt.this)
    select = update_to_select(stmt)
    return _trace_lineage(
        target_table,
        select,
        schema,
        file_path,
        diagnostics=diagnostics,
    )


def _handle_create(stmt, file_path, schema, diagnostics=None):
    target_table = _target_table_sql(stmt.this)
    target_columns = _target_columns(stmt.this)
    inner = _unwrap_query_expression(stmt.args.get("expression"))
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _trace_lineage(
            target_table,
            inner,
            schema,
            file_path,
            target_columns,
            diagnostics,
        )
    return []


def _handle_merge(stmt, file_path, schema, diagnostics=None):
    target_table = _target_table_sql(stmt.this)
    entries = []
    whens = stmt.args.get("whens")
    if not whens:
        return entries
    for when in whens.expressions:
        action = when.args.get("then")
        if isinstance(action, exp.Update):
            select = update_to_select(action)
            entries.extend(
                _trace_lineage(
                    target_table,
                    select,
                    schema,
                    file_path,
                    diagnostics=diagnostics,
                )
            )
        elif isinstance(action, exp.Insert):
            inner = action.expression
            if isinstance(inner, exp.Select):
                entries.extend(
                    _trace_lineage(
                        target_table,
                        inner,
                        schema,
                        file_path,
                        diagnostics=diagnostics,
                    )
                )
            elif isinstance(inner, exp.Tuple):
                entries.extend(
                    _extract_values_lineage(target_table, action, file_path)
                )
    return entries


def _handle_select_into(stmt, file_path, schema, diagnostics=None):
    into = stmt.args.get("into")
    if not into:
        return []
    target_table = _target_table_sql(into.this)
    return _trace_lineage(
        target_table,
        stmt,
        schema,
        file_path,
        diagnostics=diagnostics,
    )


def _extract_values_lineage(target_table, insert_or_values, file_path):
    entries = []
    if isinstance(insert_or_values, exp.Insert):
        cols = [
            _canonical_column(c.name if hasattr(c, "name") else c.sql())
            for c in (insert_or_values.args.get("this").expressions or [])
        ]
        vals = insert_or_values.args.get("expression")
        if not vals or not isinstance(vals, exp.Tuple):
            return entries
        val_list = vals.expressions
    elif isinstance(insert_or_values, exp.Values):
        return entries
    else:
        return entries

    for col_name, val in zip(cols, val_list):
        for col_ref in val.find_all(exp.Column):
            entries.append(
                {
                    "source_table": _strip_db(col_ref.table or "UNKNOWN"),
                    "source_column": _canonical_column(col_ref.name),
                    "target_table": _strip_db(target_table),
                    "target_column": col_name,
                    "expression": val.sql(dialect="doris")
                    if hasattr(val, "sql")
                    else str(val),
                    "source_file": file_path,
                }
            )
    return entries


from dw_refactor_agent.lineage import lineage_output as _lineage_output


def _call_output(name, *args, **kwargs):
    return _lineage_output.call(
        name,
        _LINEAGE_RUNTIME,
        *args,
        **kwargs,
    )


def _source_file_match_key(*args, **kwargs):
    return _call_output("_source_file_match_key", *args, **kwargs)


def _task_fact_table_names(*args, **kwargs):
    return _call_output("_task_fact_table_names", *args, **kwargs)


def _legacy_task_results(*args, **kwargs):
    return _call_output("_legacy_task_results", *args, **kwargs)


def _job_for_lineage_entry(*args, **kwargs):
    return _call_output("_job_for_lineage_entry", *args, **kwargs)


def _normalize_producer_diagnostics(*args, **kwargs):
    return _call_output("_normalize_producer_diagnostics", *args, **kwargs)


def build_lineage_output(*args, **kwargs):
    return _call_output("build_lineage_output", *args, **kwargs)


def format_lineage_output_statistics(*args, **kwargs):
    return _call_output(
        "format_lineage_output_statistics",
        *args,
        **kwargs,
    )


def warn_multiple_producer_datasets(*args, **kwargs):
    return _call_output(
        "warn_multiple_producer_datasets",
        *args,
        **kwargs,
    )


def warn_jobs_with_multiple_non_process_outputs(*args, **kwargs):
    return _call_output(
        "warn_jobs_with_multiple_non_process_outputs",
        *args,
        **kwargs,
    )


def format_layer_statistics(*args, **kwargs):
    return _call_output("format_layer_statistics", *args, **kwargs)


_lineage_output.preserve_facade_metadata(globals())


# ============================================================
# 6. 主流程
# ============================================================


def main():
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="SQL 血缘采集器")
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称, 对应 PROJECT_CONFIG 中的 key",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="task 文件级并行度, 默认 1",
    )
    parser.add_argument(
        "--force-overwrite-on-error",
        action="store_true",
        help="存在严重错误时仍覆盖写出 lineage_data 文件",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "血缘 JSON 输出文件; 默认使用 warehouses/{project}/artifacts/lineage/lineage_data.json"
        ),
    )
    parser.add_argument(
        "--cache-file",
        default=None,
        help=(
            "task 级血缘缓存文件; 默认使用 "
            "warehouses/{project}/artifacts/lineage/task_lineage_cache.json"
        ),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用 task 级血缘缓存",
    )
    args = parser.parse_args()
    configure_project(args.project)
    _reset_stats()
    project_dir = configured_project_dir(args.project)
    if project_dir is None:
        raise KeyError(f"未知项目: {args.project}")
    # 1. 构建 Schema
    schema = build_schema_from_project_ddl(args.project)
    table_count = schema_table_count(schema)
    print(f"Schema: {table_count} 个表")

    # 2. 提取血缘
    all_lineage = []
    task_files = iter_project_task_files(
        args.project,
        include_full_refresh=False,
    )

    parallel = max(1, int(args.parallel or 1))
    print(f"Tasks: {len(task_files)} 个文件, 并行度: {parallel}")

    def print_task_progress(completed, total, task_result):
        entries = task_result["entries"]
        diagnostics = task_result.get("errors") or []
        fatal_count = len(_fatal_diagnostics(diagnostics))
        warning_count = len(diagnostics) - fatal_count
        diagnostic_parts = []
        if task_result.get("cache_hit"):
            diagnostic_parts.append("cache hit")
        if fatal_count:
            diagnostic_parts.append(f"{fatal_count} 个错误")
        if warning_count:
            diagnostic_parts.append(f"{warning_count} 个警告")
        diagnostic_text = (
            f", {', '.join(diagnostic_parts)}" if diagnostic_parts else ""
        )
        print(
            f"  [{completed}/{total}] {task_result['source_file']}: "
            f"{len(entries)} 条血缘{diagnostic_text}"
        )

    cache_path = None
    if not args.no_cache:
        cache_path = (
            Path(args.cache_file)
            if args.cache_file
            else lineage_task_cache_path(CURRENT_PROJECT)
        )

    extraction_result = extract_lineage_from_task_files(
        task_files,
        project_dir,
        schema,
        parallel=parallel,
        progress_callback=print_task_progress,
        previous_cache_file=cache_path,
        cache_project=CURRENT_PROJECT,
        source_file_for_path=lambda path: task_source_file(
            CURRENT_PROJECT,
            path,
        ),
    )
    all_lineage = extraction_result["lineage"]
    warning_lines = format_missing_ddl_warnings(
        extraction_result["task_results"],
        extraction_result["missing_ddl_tables"],
    )
    if warning_lines:
        print()
        for line in warning_lines:
            print(line)

    output_path = (
        Path(args.output)
        if args.output
        else lineage_data_path(CURRENT_PROJECT)
    )
    output_paths = [output_path]

    diagnostics = extraction_result["errors"]
    fatal_diagnostics = _fatal_diagnostics(diagnostics)
    if diagnostics:
        print()
        print("诊断明细:")
        for source_file, source_diagnostics in sorted(
            _diagnostics_by_source_file(diagnostics).items()
        ):
            source_fatal_count = len(_fatal_diagnostics(source_diagnostics))
            source_warning_count = len(source_diagnostics) - source_fatal_count
            print(
                f"  {source_file}: "
                f"{source_fatal_count} 个错误, "
                f"{source_warning_count} 个警告"
            )
            for diagnostic in source_diagnostics[:5]:
                print(f"    - {_format_diagnostic(diagnostic)}")
            if len(source_diagnostics) > 5:
                print(f"    - ... 还有 {len(source_diagnostics) - 5} 个诊断")
    should_write_output = _should_write_lineage_output(
        fatal_diagnostics,
        output_paths,
        force_overwrite_on_error=args.force_overwrite_on_error,
    )
    if fatal_diagnostics and not should_write_output:
        print(
            "\n血缘提取失败: "
            f"存在 {len(fatal_diagnostics)} 个错误, "
            "未覆盖已有输出文件; 如需覆盖请使用 --force-overwrite-on-error"
        )
        sys.exit(1)

    output = build_lineage_output(
        all_lineage,
        schema,
        task_results=extraction_result["task_results"],
    )
    warn_multiple_producer_datasets(output["jobs"])
    warn_jobs_with_multiple_non_process_outputs(
        output["jobs"],
        output["tables"],
    )
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=TEXT_ENCODING) as fp:
            json.dump(output, fp, ensure_ascii=False, indent=2)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding=TEXT_ENCODING) as fp:
            json.dump(
                extraction_result["task_cache"],
                fp,
                ensure_ascii=False,
                indent=2,
            )

    if fatal_diagnostics:
        print("\n血缘提取完成, 但存在严重错误!")
    else:
        print("\n血缘提取完成!")
    for line in format_lineage_output_statistics(output):
        print(line)
    if STATS["parse_failures"]:
        print(f"  解析失败: {STATS['parse_failures']} 个文件")
    if STATS["lineage_failures"]:
        print(f"  lineage 未抽取: {STATS['lineage_failures']} 个目标表")
    print(f"  输出: {output_path}")
    if fatal_diagnostics and not args.force_overwrite_on_error:
        print("  存在严重错误, 已写出新输出文件但进程返回失败")
        sys.exit(1)
    if fatal_diagnostics and args.force_overwrite_on_error:
        print("  已按 --force-overwrite-on-error 覆盖写出")

    print()
    for line in format_layer_statistics(output["tables"]):
        print(line)

    return output


if __name__ == "__main__":
    main()
