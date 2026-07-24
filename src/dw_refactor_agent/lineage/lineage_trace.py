"""SQL lineage tracing, diagnostics, and statement handlers."""

from pathlib import Path

from sqlglot import exp

from dw_refactor_agent.lineage.runtime_binding import RuntimeBindings

_BINDINGS = RuntimeBindings(
    __name__,
    "dw_refactor_agent.lineage.lineage_extractor",
)

_canonical_column = _BINDINGS.delegate("_canonical_column")
_canonical_identifier = _BINDINGS.delegate("_canonical_identifier")
_constant_lineage_entry = _BINDINGS.delegate("_constant_lineage_entry")
_derived_output_column_lookup = _BINDINGS.delegate(
    "_derived_output_column_lookup"
)
_expand_query_star_projections = _BINDINGS.delegate(
    "_expand_query_star_projections"
)
_expression_sql = _BINDINGS.delegate("_expression_sql")
_fallback_direct_edges_from_expression = _BINDINGS.delegate(
    "_fallback_direct_edges_from_expression"
)
_identifier_match_key = _BINDINGS.delegate("_identifier_match_key")
_identifier_needs_quotes = _BINDINGS.delegate("_identifier_needs_quotes")
_is_star_projection = _BINDINGS.delegate("_is_star_projection")
_iter_matching_schema_tables = _BINDINGS.delegate(
    "_iter_matching_schema_tables"
)
_lineage_column_arg = _BINDINGS.delegate("_lineage_column_arg")
_lineage_output_column_name = _BINDINGS.delegate("_lineage_output_column_name")
_lineage_schema = _BINDINGS.delegate("_lineage_schema")
_lineage_scope = _BINDINGS.delegate("_lineage_scope")
lineage = _BINDINGS.delegate("lineage")
_normalize_derived_column_reference_case = _BINDINGS.delegate(
    "_normalize_derived_column_reference_case"
)
_normalize_lineage_identifier_case = _BINDINGS.delegate(
    "_normalize_lineage_identifier_case"
)
_projection_items = _BINDINGS.delegate("_projection_items")
_projection_output_name = _BINDINGS.delegate("_projection_output_name")
_projection_output_names = _BINDINGS.delegate("_projection_output_names")
_projection_references_unresolved_source = _BINDINGS.delegate(
    "_projection_references_unresolved_source"
)
_rewrite_lateral_named_struct_fields = _BINDINGS.delegate(
    "_rewrite_lateral_named_struct_fields"
)
_schema_columns_for_table = _BINDINGS.delegate("_schema_columns_for_table")
_strip_db = _BINDINGS.delegate("_strip_db")
_target_columns = _BINDINGS.delegate("_target_columns")
_target_table_sql = _BINDINGS.delegate("_target_table_sql")
_unresolved_star_source_keys = _BINDINGS.delegate(
    "_unresolved_star_source_keys"
)
_unwrap_query_expression = _BINDINGS.delegate("_unwrap_query_expression")


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
                        dialect=_BINDINGS.runtime().LINEAGE_DIALECT,
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


def determine_layer(table_name):
    short = _strip_db(table_name)
    runtime = _BINDINGS.runtime()
    return runtime.determine_config_layer(short, runtime.CURRENT_PROJECT)


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
            dialect=_BINDINGS.runtime().LINEAGE_DIALECT,
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


def _derived_queries_by_alias(select_expr):
    if not isinstance(select_expr, exp.Select):
        return {}

    ctes = _collect_ctes(select_expr)
    ctes_by_key = {
        _identifier_match_key(cte_name): cte_query
        for cte_name, cte_query in ctes.items()
    }
    derived_queries = {}
    for relation in _iter_relation_sources(select_expr):
        if isinstance(relation, exp.Subquery) and isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            alias_key = _identifier_match_key(relation.alias_or_name)
            if alias_key:
                derived_queries[alias_key] = relation.this
            continue
        if not isinstance(relation, exp.Table):
            continue
        if relation.args.get("db") or relation.args.get("catalog"):
            continue
        table_key = _identifier_match_key(_strip_db(_table_name(relation)))
        cte_query = ctes_by_key.get(table_key)
        if cte_query is None:
            continue
        for name in (relation.alias_or_name, relation.name):
            alias_key = _identifier_match_key(name)
            if alias_key:
                derived_queries[alias_key] = cte_query
    return derived_queries


def _physical_aliases_by_table_name(select_expr):
    if not isinstance(select_expr, exp.Select):
        return {}

    cte_keys = {
        _identifier_match_key(cte_name)
        for cte_name in _collect_ctes(select_expr)
    }
    aliases_by_table = {}
    for relation in _iter_relation_sources(select_expr):
        if not isinstance(relation, exp.Table):
            continue
        table_key = _identifier_match_key(_strip_db(_table_name(relation)))
        is_qualified = bool(
            relation.args.get("db") or relation.args.get("catalog")
        )
        if not is_qualified and table_key in cte_keys:
            continue
        alias_key = _identifier_match_key(
            relation.alias_or_name or relation.name
        )
        if table_key and alias_key:
            aliases_by_table.setdefault(table_key, set()).add(alias_key)
    return aliases_by_table


def _projection_table_keys(projection):
    if projection is None:
        return set()
    return {
        _identifier_match_key(column.table)
        for column in projection.find_all(exp.Column)
        if _identifier_match_key(column.table)
    }


def _set_operand_projection_lists(query_expr):
    query_expr = _unwrap_query_expression(query_expr)
    if isinstance(query_expr, exp.Select):
        return [list(query_expr.expressions)]
    if not isinstance(query_expr, exp.SetOperation):
        return []
    return _set_operand_projection_lists(
        query_expr.args.get("this")
    ) + _set_operand_projection_lists(query_expr.args.get("expression"))


def _derived_output_is_column_free(query_expr, column_name):
    column_key = _identifier_match_key(column_name)
    matching_indexes = [
        idx
        for idx, output_name in enumerate(_projection_output_names(query_expr))
        if _identifier_match_key(output_name) == column_key
    ]
    if len(matching_indexes) != 1:
        return False

    projection_index = matching_indexes[0]
    projection_lists = _set_operand_projection_lists(query_expr)
    if not projection_lists:
        return False
    for projections in projection_lists:
        if projection_index >= len(projections):
            return False
        if list(projections[projection_index].find_all(exp.Column)):
            return False
    return True


def _resolve_derived_alias_edges(
    edges,
    select_expr,
    projection,
    schema,
    file_path,
    diagnostics,
):
    derived_queries = _derived_queries_by_alias(select_expr)
    if not derived_queries:
        return edges, False

    projection_table_keys = _projection_table_keys(projection)
    physical_aliases = _physical_aliases_by_table_name(select_expr)
    resolved_edges = []
    has_non_column_source = False
    for edge in edges:
        alias_key = _identifier_match_key(edge.get("source_table"))
        derived_query = derived_queries.get(alias_key)
        if derived_query is None:
            resolved_edges.append(edge)
            continue
        if projection_table_keys and (
            alias_key not in projection_table_keys
            or projection_table_keys & physical_aliases.get(alias_key, set())
        ):
            resolved_edges.append(edge)
            continue
        source_column = edge.get("source_column")
        if _derived_output_is_column_free(derived_query, source_column):
            has_non_column_source = True
            continue
        leaf_sources = _derived_leaf_sources(
            derived_query,
            source_column,
            schema,
            file_path=file_path,
            diagnostics=diagnostics,
        )
        if not leaf_sources:
            resolved_edges.append(edge)
            continue
        for source_table, source_column in leaf_sources:
            resolved_edges.append(
                {
                    **edge,
                    "source_table": source_table,
                    "source_column": source_column,
                }
            )
    return resolved_edges, has_non_column_source


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
        _BINDINGS.runtime().STATS["lineage_failures"] += 1
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
        edges, has_non_column_derived_source = _resolve_derived_alias_edges(
            edges,
            lineage_select_expr,
            projection,
            schema,
            file_path,
            diagnostics,
        )
        if has_non_column_derived_source and not edges:
            entries.append(
                _constant_lineage_entry(
                    target_table,
                    target_col,
                    projection if projection is not None else node.expression,
                    file_path,
                )
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


_EXPORTED_FUNCTIONS = (
    "_diagnostic_error",
    "_diagnostic_severity",
    "_record_diagnostic",
    "_fatal_diagnostics",
    "_lineage_node_items_for_select",
    "_lineage_nodes_for_select",
    "_target_column_for_projection",
    "_align_projection_names_to_targets",
    "_leftmost_set_operand",
    "determine_layer",
    "update_to_select",
    "_table_name",
    "_extract_leaf_edges",
    "_walk_leaf",
    "_iter_relation_sources",
    "_collect_ctes",
    "_schema_has_column",
    "_derived_leaf_sources",
    "_indirect_entries_from_select",
    "_extract_indirect",
    "_extract_indirect_from_delete",
    "_handle_delete",
    "format_missing_ddl_warnings",
    "_truncate_diagnostic_text",
    "_format_diagnostic",
    "_diagnostics_by_source_file",
    "_should_write_lineage_output",
    "_trace_lineage",
    "_handle_insert",
    "_handle_update",
    "_handle_create",
    "_handle_merge",
    "_handle_select_into",
    "_extract_values_lineage",
)
_BINDINGS.install(globals(), _EXPORTED_FUNCTIONS)


def install_facade(namespace):
    """Install compatibility exports on the extractor facade."""
    _BINDINGS.install_facade(namespace, _EXPORTED_FUNCTIONS)
