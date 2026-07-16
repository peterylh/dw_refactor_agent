"""Schema, identifier normalization, and DDL parsing helpers."""

from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.schema import MappingSchema, Schema

from dw_refactor_agent.lineage.runtime_binding import RuntimeBindings

_BINDINGS = RuntimeBindings(
    __name__,
    "dw_refactor_agent.lineage.lineage_extractor",
)

_canonical_column = _BINDINGS.delegate("_canonical_column")
_canonical_identifier = _BINDINGS.delegate("_canonical_identifier")
_canonical_qualified_identifier = _BINDINGS.delegate(
    "_canonical_qualified_identifier"
)
_default_catalog = _BINDINGS.delegate("_default_catalog")
_default_db = _BINDINGS.delegate("_default_db")
_display_table_name = _BINDINGS.delegate("_display_table_name")
_expand_query_star_projections = _BINDINGS.delegate(
    "_expand_query_star_projections"
)
_identifier_match_key = _BINDINGS.delegate("_identifier_match_key")
_projection_output_names = _BINDINGS.delegate("_projection_output_names")
_qualified_table_name = _BINDINGS.delegate("_qualified_table_name")
_schema_has_column = _BINDINGS.delegate("_schema_has_column")
_schema_table_match_key = _BINDINGS.delegate("_schema_table_match_key")
_strip_db = _BINDINGS.delegate("_strip_db")
_table_identity = _BINDINGS.delegate("_table_identity")
_table_identity_match_key = _BINDINGS.delegate("_table_identity_match_key")
_table_name = _BINDINGS.delegate("_table_name")
_unwrap_query_expression = _BINDINGS.delegate("_unwrap_query_expression")


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
    if _is_schema_lookup(schema):
        return schema
    return _BINDINGS.runtime()._SchemaLookup(schema)


def _is_schema_lookup(schema):
    return isinstance(schema, _SchemaLookup) or (
        callable(getattr(schema, "table_name", None))
        and callable(getattr(schema, "column_name", None))
    )


def _iter_matching_schema_tables(schema, table_name):
    requested_key = _table_identity_match_key(table_name)
    if not requested_key[2]:
        return
    for catalog, database, table, columns in _iter_schema_tables(schema):
        if _schema_table_match_key(catalog, database, table) == requested_key:
            yield catalog, database, table, columns


def _schema_table_name(schema, table_name):
    if _is_schema_lookup(schema):
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
    if _is_schema_lookup(schema):
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
    if _BINDINGS.runtime().AGGREGATE_PATTERN.search(str(expression or "")):
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
        dialect=_BINDINGS.runtime().LINEAGE_DIALECT,
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
    runtime = _BINDINGS.runtime()
    qualified = runtime.lineage_qualify.qualify(
        select_expr.copy(),
        dialect=runtime.LINEAGE_DIALECT,
        schema=_lineage_schema(schema),
        validate_qualify_columns=False,
        identify=False,
    )
    return runtime.build_lineage_scope(qualified)


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


def _parse_schema_create_statements(sql_text, dialect="doris"):
    text = (
        _BINDINGS.runtime().normalize_create_table_for_sqlglot(sql_text)
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
            if dialect in _BINDINGS.runtime().DDL_DIALECTS_WITH_PARTITIONED_BY:
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
            f.read_text(encoding=_BINDINGS.runtime().TEXT_ENCODING)
            for f in sorted(directory.glob("*.sql"))
        )
    return build_schema_from_texts(
        texts,
        dialect=dialect,
        default_catalog=default_catalog,
        default_db=default_db,
    )


def build_schema_from_project_ddl(project):
    runtime = _BINDINGS.runtime()
    cfg = runtime.PROJECT_CONFIG[project]
    schema = {}
    ods_dirs = set(runtime.project_ods_asset_dirs(project, "ddl"))
    asset_dirs = runtime.project_asset_dirs(project, "ddl")
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
                dialect=runtime.ods_source_catalog_ddl_dialect(
                    project,
                    catalog,
                ),
                default_catalog=catalog,
                default_db=database,
            ),
        )
    return schema


_EXPORTED_FUNCTIONS = (
    "_schema_lookup",
    "_iter_matching_schema_tables",
    "_schema_table_name",
    "_schema_column_name",
    "_canonical_lineage_entry",
    "_node_id",
    "_column_source",
    "_column_target",
    "_table_target",
    "_literal_source",
    "_expression_source",
    "_expression_sql",
    "_source_sort_key",
    "_target_sort_key",
    "_relation_type_for_condition",
    "_transformation_type_for_expression",
    "_is_literal_expression",
    "_literal_value",
    "_constant_lineage_entry",
    "_target_table_sql",
    "_target_columns",
    "_schema_columns_for_table",
    "_schema_column_map_for_table",
    "_is_column_map",
    "_is_table_map",
    "_iter_schema_tables",
    "_copy_schema",
    "schema_table_count",
    "_schema_has_table",
    "_statement_target_table",
    "_statement_table_references",
    "collect_statement_table_names",
    "collect_statement_cte_names",
    "_is_table_create_statement",
    "_is_table_drop_statement",
    "_target_table_expr",
    "_statement_table_target_exprs",
    "_statement_source_table_names",
    "_statement_existing_target_table_names",
    "_normalized_skip_table_names",
    "slice_schema",
    "_task_schema_for_statements",
    "_task_schema_for_table_names",
    "_lineage_schema_mapping",
    "_lineage_schema",
    "_identifier_arg_name",
    "_set_identifier_arg",
    "_normalize_table_alias",
    "_normalize_lineage_table_identifier",
    "_normalize_lineage_column_identifier",
    "_normalize_lineage_identifier_case",
    "_lineage_output_column_name",
    "_lineage_scope",
    "_register_task_table_schema",
    "_drop_task_table_schema",
    "_apply_alter_table_to_task_schema",
    "_create_like_source_table",
    "_created_table_columns_from_schema",
    "_infer_table_for_column",
    "_fallback_direct_edges_from_expression",
    "_parse_schema_create_statements",
    "_column_def_type",
    "_add_column_def",
    "_partition_column_defs",
    "build_schema_from_texts",
    "_merge_schema",
    "build_schema_from_ddl",
    "build_schema_from_project_ddl",
)
_BINDINGS.install(globals(), _EXPORTED_FUNCTIONS)


def install_facade(namespace):
    """Install compatibility exports on the extractor facade."""
    _BINDINGS.install_facade(namespace, _EXPORTED_FUNCTIONS)
