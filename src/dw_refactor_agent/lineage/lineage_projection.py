"""SQL projection expansion helpers for lineage extraction.

The public extractor remains the compatibility facade.  A runtime reference
keeps these helpers coupled to the facade's configurable project context while
placing the projection-specific implementation in its own module.
"""

import re

from sqlglot import exp

from dw_refactor_agent.lineage.runtime_binding import RuntimeBindings

_BINDINGS = RuntimeBindings(
    __name__,
    "dw_refactor_agent.lineage.lineage_extractor",
)


def _delegate(name, *args, **kwargs):
    return getattr(_BINDINGS.runtime(), name)(*args, **kwargs)


def _canonical_column(*args, **kwargs):
    return _delegate("_canonical_column", *args, **kwargs)


def _canonical_identifier(*args, **kwargs):
    return _delegate("_canonical_identifier", *args, **kwargs)


def _collect_ctes(*args, **kwargs):
    return _delegate("_collect_ctes", *args, **kwargs)


def _identifier_match_key(*args, **kwargs):
    return _delegate("_identifier_match_key", *args, **kwargs)


def _iter_relation_sources(*args, **kwargs):
    return _delegate("_iter_relation_sources", *args, **kwargs)


def _record_diagnostic(*args, **kwargs):
    return _delegate("_record_diagnostic", *args, **kwargs)


def _schema_columns_for_table(*args, **kwargs):
    return _delegate("_schema_columns_for_table", *args, **kwargs)


def _strip_db(*args, **kwargs):
    return _delegate("_strip_db", *args, **kwargs)


def _table_name(*args, **kwargs):
    return _delegate("_table_name", *args, **kwargs)


def _unwrap_paren_projection(projection):
    while isinstance(projection, exp.Paren):
        projection = projection.this
    return projection


def _projection_output_name(projection):
    projection = _unwrap_paren_projection(projection)
    if isinstance(projection, exp.Alias):
        return _canonical_column(projection.alias)
    if isinstance(projection, exp.Column):
        return _canonical_column(projection.name)
    if isinstance(projection, exp.Star):
        return ""
    if getattr(projection, "alias_or_name", None):
        return _canonical_column(projection.alias_or_name)
    return ""


def _projection_output_identifier(projection):
    projection = _unwrap_paren_projection(projection)
    if isinstance(projection, exp.Alias):
        return projection.args.get("alias")
    if isinstance(projection, exp.Column):
        return projection.this
    return None


def _lineage_column_arg(projection, column_name):
    identifier = _projection_output_identifier(projection)
    if isinstance(identifier, exp.Identifier) and identifier.args.get(
        "quoted"
    ):
        return exp.to_identifier(column_name, quoted=True)
    return column_name


def _projection_output_names(query_expr):
    query_expr = _unwrap_query_expression(query_expr)
    if isinstance(query_expr, exp.Select):
        return [
            _projection_output_name(item) for item in query_expr.expressions
        ]
    if isinstance(query_expr, exp.SetOperation):
        left = query_expr.args.get("this")
        return _projection_output_names(left) if left is not None else []
    return []


def _projection_items(query_expr):
    query_expr = _unwrap_query_expression(query_expr)
    if isinstance(query_expr, exp.Select):
        return list(query_expr.expressions)
    if isinstance(query_expr, exp.SetOperation):
        left = query_expr.args.get("this")
        return _projection_items(left) if left is not None else []
    return []


def _unwrap_query_expression(query_expr):
    while isinstance(query_expr, exp.Subquery) and isinstance(
        query_expr.this,
        (exp.Select, exp.SetOperation),
    ):
        query_expr = query_expr.this
    return query_expr


def _identifier_needs_quotes(name):
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(name or "")) is None


def _projection_can_inline_through_star(projection):
    if projection is None or _is_star_projection(projection):
        return False
    if isinstance(projection, exp.Column):
        return False
    return not list(projection.find_all(exp.Column))


def _inline_star_projection(projection, output_name):
    inlined = projection.copy()
    output_name = _canonical_column(output_name)
    if not output_name:
        return inlined
    if isinstance(inlined, exp.Alias):
        if _identifier_match_key(inlined.alias) == _identifier_match_key(
            output_name
        ):
            return inlined
        inlined = inlined.this.copy()
    return exp.alias_(
        inlined,
        output_name,
        quoted=_identifier_needs_quotes(output_name),
    )


def _is_star_projection(projection):
    return isinstance(projection, exp.Star) or (
        isinstance(projection, exp.Column)
        and isinstance(projection.this, exp.Star)
    )


def _star_projection_table(projection):
    if isinstance(projection, exp.Column) and isinstance(
        projection.this, exp.Star
    ):
        parts = [
            _canonical_identifier(part.name)
            for part in projection.parts
            if _canonical_identifier(part.name)
        ]
        if parts and parts[-1] == "*":
            return ".".join(parts[:-1])
        return _canonical_identifier(projection.table)
    return ""


def _star_has_modifiers(star_expr):
    if not isinstance(star_expr, exp.Star):
        return False
    modifier_args = {"except", "except_", "replace", "rename"}
    return any(star_expr.args.get(arg) for arg in modifier_args)


def _relation_alias(relation):
    return _canonical_identifier(
        getattr(relation, "alias_or_name", None)
        or getattr(relation, "name", "")
    )


def _explicit_relation_alias(relation):
    alias = relation.args.get("alias") if relation is not None else None
    if not alias:
        return ""
    return _canonical_identifier(alias.this.name)


def _relation_match_keys(*names):
    return {
        _identifier_match_key(name)
        for name in names
        if _identifier_match_key(name)
    }


def _column_projection(reference_name, column_name, output_name=None):
    reference_parts = [
        _canonical_identifier(part)
        for part in str(reference_name or "").split(".")
        if _canonical_identifier(part)
    ]
    if len(reference_parts) >= 3:
        column = exp.column(
            column_name,
            table=reference_parts[-1],
            db=reference_parts[-2],
            catalog=reference_parts[-3],
        )
    elif len(reference_parts) == 2:
        column = exp.column(
            column_name,
            table=reference_parts[-1],
            db=reference_parts[-2],
        )
    else:
        column = exp.column(column_name, table=reference_name or None)
    return exp.alias_(column, output_name or column_name, quoted=False)


def _alias_column_names(expression):
    alias = expression.args.get("alias") if expression is not None else None
    if not alias:
        return []
    return [
        _canonical_column(getattr(column, "name", column))
        for column in (alias.args.get("columns") or [])
    ]


def _exposed_columns(output_columns, alias_columns):
    exposed = list(output_columns or [])
    for idx, alias_name in enumerate(alias_columns or []):
        if idx >= len(exposed):
            break
        exposed[idx] = alias_name
    return exposed


def _has_unexpanded_star_projection(query_expr):
    if isinstance(query_expr, exp.Select):
        return any(
            _is_star_projection(projection)
            for projection in query_expr.expressions
        )
    if isinstance(query_expr, exp.SetOperation):
        left = query_expr.args.get("this")
        return _has_unexpanded_star_projection(left)
    return False


def _mark_unresolved_star_source(select_expr, *names):
    keys = {
        _identifier_match_key(name)
        for name in names
        if _identifier_match_key(name)
    }
    if not keys:
        return
    select_expr.meta.setdefault("unresolved_star_sources", set()).update(keys)


def _unresolved_star_source_keys(select_expr):
    return set(
        getattr(select_expr, "meta", {}).get("unresolved_star_sources")
        or set()
    )


def _projection_references_unresolved_source(projection, unresolved_keys):
    if not projection or not unresolved_keys:
        return False
    for column in projection.find_all(exp.Column):
        table_key = _identifier_match_key(column.table)
        if not table_key:
            return True
        if table_key in unresolved_keys:
            return True
    return False


def _relation_source_match_keys(relation):
    if isinstance(relation, exp.Subquery):
        return _relation_match_keys(_relation_alias(relation))
    if isinstance(relation, exp.Table):
        table_name = _table_name(relation)
        return _relation_match_keys(
            _relation_alias(relation),
            _strip_db(table_name),
            table_name,
        )
    return set()


def _expand_query_star_projections(
    query_expr,
    schema,
    file_path="",
    target_table="",
    diagnostics=None,
    _cte_context=None,
    _visited=None,
):
    query_expr = _unwrap_query_expression(query_expr)
    if isinstance(query_expr, exp.Select):
        return _expand_select_star_projections(
            query_expr,
            schema,
            file_path=file_path,
            target_table=target_table,
            diagnostics=diagnostics,
            _cte_context=_cte_context,
            _visited=_visited,
        )
    if isinstance(query_expr, exp.SetOperation):
        expanded = query_expr.copy()
        left = expanded.args.get("this")
        right = expanded.args.get("expression")
        output_columns = _projection_output_names(left)
        has_unresolved_output = False
        if isinstance(
            _unwrap_query_expression(left), (exp.Select, exp.SetOperation)
        ):
            (
                expanded_left,
                output_columns,
                has_unresolved_output,
            ) = _expand_query_star_projections(
                left,
                schema,
                file_path=file_path,
                target_table=target_table,
                diagnostics=diagnostics,
                _cte_context=_cte_context,
                _visited=_visited,
            )
            expanded.set("this", expanded_left)
        if isinstance(
            _unwrap_query_expression(right), (exp.Select, exp.SetOperation)
        ):
            (
                expanded_right,
                _right_columns,
                _right_unresolved,
            ) = _expand_query_star_projections(
                right,
                schema,
                file_path=file_path,
                target_table=target_table,
                diagnostics=diagnostics,
                _cte_context=_cte_context,
                _visited=_visited,
            )
            expanded.set("expression", expanded_right)
            has_unresolved_output = has_unresolved_output or _right_unresolved
        return expanded, output_columns, has_unresolved_output
    return query_expr.copy(), [], False


def _expand_select_star_projections(
    select_expr,
    schema,
    file_path="",
    target_table="",
    diagnostics=None,
    _cte_context=None,
    _visited=None,
):
    expanded = select_expr.copy()
    visible_ctes = dict(_cte_context or {})
    visited = set(_visited or set())

    with_ = expanded.args.get("with_") or expanded.args.get("with")
    if with_:
        for cte in with_.expressions or []:
            if not isinstance(cte.this, (exp.Select, exp.SetOperation)):
                continue
            cte_key = _identifier_match_key(cte.alias_or_name)
            if not cte_key:
                continue
            cte_visible = dict(visible_ctes)
            (
                expanded_cte,
                _cte_columns,
                _cte_unresolved,
            ) = _expand_query_star_projections(
                cte.this,
                schema,
                file_path=file_path,
                target_table=target_table,
                diagnostics=diagnostics,
                _cte_context=cte_visible,
                _visited=visited | {cte_key},
            )
            cte.set("this", expanded_cte)
            visible_ctes[cte_key] = {
                "query": expanded_cte,
                "alias_columns": _alias_column_names(cte),
                "has_unresolved_output": _cte_unresolved,
            }

    has_star_projection = any(
        _is_star_projection(projection) for projection in expanded.expressions
    )
    has_unresolved_derived_source = False
    relation_sources = []
    has_unresolved_source = False
    if has_star_projection:
        bare_star = any(
            not _star_projection_table(projection)
            for projection in expanded.expressions
            if _is_star_projection(projection)
        )
        qualified_star_keys = {
            _identifier_match_key(_star_projection_table(projection))
            for projection in expanded.expressions
            if _is_star_projection(projection)
            and _star_projection_table(projection)
        }
        relation_sources, has_unresolved_source = _build_star_relation_sources(
            expanded,
            schema,
            visible_ctes,
            file_path,
            target_table,
            diagnostics,
            visited,
            require_all=bare_star,
            required_keys=qualified_star_keys,
        )
        if not bare_star:
            has_unresolved_derived_source = _expand_explicit_derived_sources(
                expanded,
                schema,
                visible_ctes,
                file_path,
                target_table,
                diagnostics,
                visited,
            )
    if not has_star_projection:
        has_unresolved_derived_source = _expand_explicit_derived_sources(
            expanded,
            schema,
            visible_ctes,
            file_path,
            target_table,
            diagnostics,
            visited,
        )
    expanded_items = []
    for projection in expanded.expressions:
        if not _is_star_projection(projection):
            expanded_items.append(
                {
                    "projection": projection.copy(),
                    "output_name": _projection_output_name(projection),
                }
            )
            continue
        star_expr = (
            projection if isinstance(projection, exp.Star) else projection.this
        )
        if _star_has_modifiers(star_expr):
            _record_diagnostic(
                diagnostics,
                file_path,
                "lineage_star_expand",
                ValueError("Unsupported SELECT * modifier"),
                severity="warning",
                target_table=_strip_db(target_table),
                expression=projection.sql(dialect="doris"),
            )
            expanded_items.append(
                {
                    "projection": projection.copy(),
                    "output_name": _projection_output_name(projection),
                }
            )
            continue
        expanded_star = _expand_star_projection_from_sources(
            projection,
            relation_sources,
            has_unresolved_source,
            file_path,
            target_table,
            diagnostics,
        )
        if not expanded_star:
            expanded_items.append(
                {
                    "projection": projection.copy(),
                    "output_name": _projection_output_name(projection),
                }
            )
            continue
        expanded_items.extend(expanded_star)

    output_columns = [
        _canonical_column(item.get("output_name", ""))
        for item in expanded_items
    ]
    output_counts = {}
    for output_name in output_columns:
        output_key = _identifier_match_key(output_name)
        if output_key:
            output_counts[output_key] = output_counts.get(output_key, 0) + 1

    expanded_projections = []
    for idx, item in enumerate(expanded_items):
        if "projection" in item:
            expanded_projections.append(item["projection"])
            continue
        output_name = item["output_name"]
        output_key = _identifier_match_key(output_name)
        alias_name = output_name
        if output_key and output_counts.get(output_key, 0) > 1:
            alias_name = f"__lineage_star_{idx}"
        expanded_projections.append(
            _column_projection(
                item["reference"],
                item["column"],
                output_name=alias_name,
            )
        )
    expanded.set("expressions", expanded_projections)
    return (
        expanded,
        output_columns,
        _has_unexpanded_star_projection(expanded)
        or has_unresolved_derived_source,
    )


def _expand_explicit_derived_sources(
    select_expr,
    schema,
    cte_context,
    file_path,
    target_table,
    diagnostics,
    visited,
):
    has_unresolved_source = False
    for relation in _iter_relation_sources(select_expr):
        if not isinstance(relation, exp.Subquery):
            if not isinstance(relation, exp.Table):
                continue
            table_name = _table_name(relation)
            table_short = _strip_db(table_name)
            table_key = _identifier_match_key(table_short)
            is_qualified_table = bool(
                relation.args.get("db") or relation.args.get("catalog")
            )
            if is_qualified_table or table_key not in cte_context:
                continue
            cte_info = cte_context[table_key]
            if not isinstance(cte_info, dict):
                continue
            if not cte_info.get("has_unresolved_output", False):
                continue
            has_unresolved_source = True
            _mark_unresolved_star_source(
                select_expr,
                _relation_alias(relation),
                table_short,
            )
            continue
        alias = _relation_alias(relation)
        if not alias or not isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            continue
        (
            expanded_inner,
            _output_columns,
            has_unresolved_output,
        ) = _expand_query_star_projections(
            relation.this,
            schema,
            file_path=file_path,
            target_table=target_table,
            diagnostics=diagnostics,
            _cte_context=cte_context,
            _visited=visited,
        )
        relation.set("this", expanded_inner)
        if has_unresolved_output:
            has_unresolved_source = True
            _mark_unresolved_star_source(select_expr, alias)
    return has_unresolved_source


def _build_star_relation_sources(
    select_expr,
    schema,
    cte_context,
    file_path,
    target_table,
    diagnostics,
    visited,
    require_all=False,
    required_keys=None,
):
    sources = []
    has_unresolved_source = False
    required_keys = set(required_keys or set())
    for relation in _iter_relation_sources(select_expr):
        relation_keys = _relation_source_match_keys(relation)
        if not require_all and not (relation_keys & required_keys):
            continue
        source = _star_relation_source(
            relation,
            schema,
            cte_context,
            file_path,
            target_table,
            diagnostics,
            visited,
        )
        if source:
            sources.append(source)
        else:
            has_unresolved_source = True
    return sources, has_unresolved_source


def _star_relation_source(
    relation,
    schema,
    cte_context,
    file_path,
    target_table,
    diagnostics,
    visited,
):
    if isinstance(relation, exp.Subquery):
        alias = _relation_alias(relation)
        if not alias or not isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            return None
        (
            expanded_inner,
            output_columns,
            has_unresolved_output,
        ) = _expand_query_star_projections(
            relation.this,
            schema,
            file_path=file_path,
            target_table=target_table,
            diagnostics=diagnostics,
            _cte_context=cte_context,
            _visited=visited,
        )
        relation.set("this", expanded_inner)
        if has_unresolved_output:
            return None
        alias_columns = _alias_column_names(relation)
        actual_columns = _exposed_columns(
            _projection_output_names(expanded_inner),
            alias_columns,
        )
        return {
            "reference": alias,
            "columns": _exposed_columns(output_columns, alias_columns),
            "actual_columns": actual_columns,
            "projections": _projection_items(expanded_inner),
            "match_keys": _relation_match_keys(alias),
        }

    if not isinstance(relation, exp.Table):
        return None

    table_name = _table_name(relation)
    table_short = _strip_db(table_name)
    alias = _explicit_relation_alias(relation)
    table_key = _identifier_match_key(table_short)
    is_qualified_table = bool(
        relation.args.get("db") or relation.args.get("catalog")
    )
    if (
        not is_qualified_table
        and table_key in cte_context
        and table_key not in visited
    ):
        cte_info = cte_context[table_key]
        cte_query = (
            cte_info.get("query") if isinstance(cte_info, dict) else cte_info
        )
        alias_columns = (
            cte_info.get("alias_columns", [])
            if isinstance(cte_info, dict)
            else []
        )
        cte_previously_unresolved = (
            cte_info.get("has_unresolved_output", False)
            if isinstance(cte_info, dict)
            else False
        )
        (
            expanded_cte,
            output_columns,
            has_unresolved_output,
        ) = _expand_query_star_projections(
            cte_query,
            schema,
            file_path=file_path,
            target_table=target_table,
            diagnostics=diagnostics,
            _cte_context=cte_context,
            _visited=visited | {table_key},
        )
        cte_context[table_key] = {
            "query": expanded_cte,
            "alias_columns": alias_columns,
            "has_unresolved_output": (
                cte_previously_unresolved or has_unresolved_output
            ),
        }
        if cte_previously_unresolved or has_unresolved_output:
            return None
        actual_columns = _exposed_columns(
            _projection_output_names(expanded_cte),
            alias_columns,
        )
        return {
            "reference": alias or table_short,
            "columns": _exposed_columns(output_columns, alias_columns),
            "actual_columns": actual_columns,
            "projections": _projection_items(expanded_cte),
            "match_keys": _relation_match_keys(alias, table_short, table_name),
        }

    columns = _schema_columns_for_table(schema, table_name)
    if not columns:
        _record_diagnostic(
            diagnostics,
            file_path,
            "lineage_star_expand",
            ValueError(
                f"Missing schema columns for table: {_strip_db(table_name)}"
            ),
            severity="warning",
            target_table=_strip_db(target_table),
        )
        return None
    return {
        "reference": alias or table_name,
        "columns": columns,
        "actual_columns": columns,
        "match_keys": _relation_match_keys(alias, table_short, table_name),
    }


def _expand_star_projection_from_sources(
    projection,
    relation_sources,
    has_unresolved_source,
    file_path,
    target_table,
    diagnostics,
):
    def _expanded_items(source):
        projections = source.get("projections") or []
        source_columns = source["columns"]
        actual_columns = source.get("actual_columns", source_columns)
        items = []
        for idx, (output_name, actual_column) in enumerate(
            zip(source_columns, actual_columns)
        ):
            source_projection = (
                projections[idx] if idx < len(projections) else None
            )
            if not output_name and source_projection is not None:
                items.append(
                    {
                        "projection": source_projection.copy(),
                        "output_name": output_name,
                    }
                )
                continue
            if _projection_can_inline_through_star(source_projection):
                items.append(
                    {
                        "projection": _inline_star_projection(
                            source_projection,
                            output_name,
                        ),
                        "output_name": output_name,
                    }
                )
                continue
            items.append(
                {
                    "reference": source["reference"],
                    "column": actual_column,
                    "output_name": output_name,
                }
            )
        return items

    qualifier = _star_projection_table(projection)
    if qualifier:
        qualifier_key = _identifier_match_key(qualifier)
        matched_sources = [
            source
            for source in relation_sources
            if qualifier_key in source["match_keys"]
        ]
        if not matched_sources:
            _record_diagnostic(
                diagnostics,
                file_path,
                "lineage_star_expand",
                ValueError(
                    f"Cannot expand SELECT star for alias: {qualifier}"
                ),
                severity="warning",
                target_table=_strip_db(target_table),
                expression=projection.sql(dialect="doris"),
            )
            return []
        return [
            item
            for source in matched_sources
            for item in _expanded_items(source)
        ]

    if has_unresolved_source:
        return []
    return [
        item for source in relation_sources for item in _expanded_items(source)
    ]


def _derived_output_column_lookup(query_expr):
    lookup = {}
    ambiguous_keys = set()
    for output_name in _projection_output_names(query_expr):
        key = _identifier_match_key(output_name)
        if not key:
            continue
        existing = lookup.get(key)
        if existing is not None and existing != output_name:
            ambiguous_keys.add(key)
            continue
        lookup[key] = output_name
    for key in ambiguous_keys:
        lookup.pop(key, None)
    return lookup


def _derived_output_lookups_for_select(select_expr):
    lookups = {}
    ctes = _collect_ctes(select_expr)
    ctes_by_key = {
        _identifier_match_key(cte_name): cte_query
        for cte_name, cte_query in ctes.items()
    }

    for relation in _iter_relation_sources(select_expr):
        if isinstance(relation, exp.Subquery) and isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            alias = _canonical_identifier(relation.alias_or_name)
            if alias:
                lookup = _derived_output_column_lookup(relation.this)
                if lookup:
                    lookups[_identifier_match_key(alias)] = lookup
        elif isinstance(relation, exp.Table):
            tbl = _strip_db(_table_name(relation))
            tbl_key = _identifier_match_key(tbl)
            if tbl_key not in ctes_by_key:
                continue
            lookup = _derived_output_column_lookup(ctes_by_key[tbl_key])
            if not lookup:
                continue
            alias = _canonical_identifier(
                relation.alias_or_name or relation.name
            )
            for name in (alias, tbl):
                if name:
                    lookups[_identifier_match_key(name)] = lookup

    return lookups


def _enclosing_select(expression):
    current = getattr(expression, "parent", None)
    while current is not None:
        if isinstance(current, exp.Select):
            return current
        current = getattr(current, "parent", None)
    return None


def _normalize_derived_column_reference_case(query_expr):
    """Match quoted derived-table column references like `ALIAS` to `alias`."""
    normalized = query_expr.copy()
    if not isinstance(normalized, (exp.Select, exp.SetOperation)):
        return normalized

    for select_expr in list(normalized.find_all(exp.Select)):
        output_lookups = _derived_output_lookups_for_select(select_expr)
        if not output_lookups:
            continue
        for column in list(select_expr.find_all(exp.Column)):
            if _enclosing_select(column) is not select_expr:
                continue
            identifier = column.this
            if not isinstance(identifier, exp.Identifier):
                continue
            if not identifier.args.get("quoted"):
                continue
            table_key = _identifier_match_key(column.table)
            if not table_key:
                continue
            output_lookup = output_lookups.get(table_key)
            if not output_lookup:
                continue
            output_name = output_lookup.get(_identifier_match_key(column.name))
            if not output_name or output_name == column.name:
                continue
            column.set("this", exp.to_identifier(output_name, quoted=True))

    return normalized


def _named_struct_field_expressions(named_struct):
    if not (
        isinstance(named_struct, exp.Anonymous)
        and str(named_struct.this).upper() == "NAMED_STRUCT"
    ):
        return {}
    fields = {}
    values = list(named_struct.expressions or [])
    for idx in range(0, len(values) - 1, 2):
        key_expr = values[idx]
        value_expr = values[idx + 1]
        if not isinstance(key_expr, exp.Literal) or not key_expr.is_string:
            continue
        field_key = _identifier_match_key(key_expr.this)
        if not field_key:
            continue
        fields.setdefault(field_key, []).append(value_expr.copy())
    return fields


def _lateral_named_struct_field_lookups(select_expr):
    lookups = {}
    for lateral in select_expr.args.get("laterals") or []:
        if not isinstance(lateral, exp.Lateral):
            continue
        alias = lateral.args.get("alias")
        if not alias:
            continue
        alias_names = [
            _canonical_identifier(column.name)
            for column in (alias.args.get("columns") or [])
            if _canonical_identifier(column.name)
        ]
        if not alias_names:
            alias_name = _canonical_identifier(alias.this.name)
            if alias_name:
                alias_names = [alias_name]
        if not alias_names:
            continue

        explode = lateral.this
        if not isinstance(explode, exp.Explode):
            continue
        array_expr = explode.this
        if not isinstance(array_expr, exp.Array):
            continue

        field_values = {}
        for item in array_expr.expressions or []:
            for field_key, values in _named_struct_field_expressions(
                item
            ).items():
                field_values.setdefault(field_key, []).extend(values)
        if not field_values:
            continue

        for alias_name in alias_names:
            lookups[_identifier_match_key(alias_name)] = field_values
    return lookups


def _lineage_expression_for_lateral_field(values):
    copied = [value.copy() for value in values if value is not None]
    if not copied:
        return None
    if len(copied) == 1:
        return copied[0]
    return exp.Coalesce(this=copied[0], expressions=copied[1:])


def _rewrite_lateral_named_struct_fields(query_expr):
    """Inline exploded NAMED_STRUCT fields so sqlglot can qualify lineage."""
    rewritten = query_expr.copy()
    if not isinstance(rewritten, (exp.Select, exp.SetOperation)):
        return rewritten

    for select_expr in list(rewritten.find_all(exp.Select)):
        lookups = _lateral_named_struct_field_lookups(select_expr)
        if not lookups:
            continue
        for column in list(select_expr.find_all(exp.Column)):
            if _enclosing_select(column) is not select_expr:
                continue
            table_key = _identifier_match_key(column.table)
            if not table_key:
                continue
            field_values = lookups.get(table_key)
            if not field_values:
                continue
            replacement = _lineage_expression_for_lateral_field(
                field_values.get(_identifier_match_key(column.name))
            )
            if replacement is not None:
                column.replace(replacement)

    return rewritten


_EXPORTED_FUNCTIONS = (
    "_unwrap_paren_projection",
    "_projection_output_name",
    "_projection_output_identifier",
    "_lineage_column_arg",
    "_projection_output_names",
    "_projection_items",
    "_unwrap_query_expression",
    "_identifier_needs_quotes",
    "_projection_can_inline_through_star",
    "_inline_star_projection",
    "_is_star_projection",
    "_star_projection_table",
    "_star_has_modifiers",
    "_relation_alias",
    "_explicit_relation_alias",
    "_relation_match_keys",
    "_column_projection",
    "_alias_column_names",
    "_exposed_columns",
    "_has_unexpanded_star_projection",
    "_mark_unresolved_star_source",
    "_unresolved_star_source_keys",
    "_projection_references_unresolved_source",
    "_relation_source_match_keys",
    "_expand_query_star_projections",
    "_expand_select_star_projections",
    "_expand_explicit_derived_sources",
    "_build_star_relation_sources",
    "_star_relation_source",
    "_expand_star_projection_from_sources",
    "_derived_output_column_lookup",
    "_derived_output_lookups_for_select",
    "_enclosing_select",
    "_normalize_derived_column_reference_case",
    "_named_struct_field_expressions",
    "_lateral_named_struct_field_lookups",
    "_lineage_expression_for_lateral_field",
    "_rewrite_lateral_named_struct_fields",
)
_BINDINGS.install(globals(), _EXPORTED_FUNCTIONS)


def call(name, runtime, *args, **kwargs):
    """Call one projection helper through an explicit facade."""
    return _BINDINGS.call(name, runtime, *args, **kwargs)


def preserve_facade_metadata(namespace):
    """Restore projection signatures and docs on extractor wrappers."""
    _BINDINGS.preserve_metadata(namespace, _EXPORTED_FUNCTIONS)


def install_facade(namespace):
    """Install projection compatibility exports on the extractor facade."""
    _BINDINGS.install_facade(namespace, _EXPORTED_FUNCTIONS)
