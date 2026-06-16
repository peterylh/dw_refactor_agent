#!/usr/bin/env python3
"""
通用字段级 SQL 血缘采集器
使用 sqlglot.lineage() 替代手写 AST 遍历
支持: INSERT, UPDATE, CTAS, CREATE VIEW, SELECT INTO, MERGE
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage

from config import PROJECT_CONFIG
from config import determine_layer as determine_config_layer
from doris_sql import normalize_create_table_for_sqlglot
from lineage.sql_task_facts import extract_task_table_facts

AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)


# ============================================================
# 0. 项目配置
# ============================================================

CURRENT_PROJECT = "shop"
CURRENT_CATALOG = "internal"
CURRENT_DB = "shop_dm"


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


def _canonical_identifier(name):
    """Return the logical identifier name without SQL quote wrappers."""
    if name is None:
        return ""
    text = str(name).strip()
    while len(text) >= 2 and (
        (text[0] == text[-1] == "`") or (text[0] == text[-1] == '"')
    ):
        text = text[1:-1].strip()
    return text


def _canonical_qualified_identifier(name):
    text = str(name or "").strip()
    if not text:
        return ""
    return ".".join(
        _canonical_identifier(part)
        for part in text.split(".")
        if str(part).strip()
    )


def _default_catalog():
    return _canonical_identifier(CURRENT_CATALOG) or "internal"


def _default_db():
    return _canonical_identifier(CURRENT_DB)


def _table_identity(name, default_catalog=None, default_db=None):
    """Return (catalog, database, table), filling project defaults as needed."""
    full_name = _canonical_qualified_identifier(name)
    parts = [part for part in full_name.split(".") if part]
    if not parts:
        return "", "", ""

    catalog = _canonical_identifier(default_catalog or _default_catalog())
    database = _canonical_identifier(default_db or _default_db())
    if len(parts) == 1:
        return catalog, database, parts[0]
    if len(parts) == 2:
        return catalog, parts[0], parts[1]
    return parts[-3], parts[-2], parts[-1]


def _qualified_table_name(catalog, database, table):
    catalog = _canonical_identifier(catalog)
    database = _canonical_identifier(database)
    table = _canonical_identifier(table)
    return ".".join(part for part in (catalog, database, table) if part)


def _display_table_name(name, strip_current_db=False):
    """Format a table name for output, hiding the default internal catalog."""
    catalog, database, table = _table_identity(name)
    if not table:
        return ""
    if catalog != _default_catalog():
        return _qualified_table_name(catalog, database, table)
    if strip_current_db and database == _default_db():
        return table
    if database:
        return f"{database}.{table}"
    return table


def _strip_db(name):
    return _display_table_name(name, strip_current_db=True)


def _canonical_column(name):
    return _canonical_identifier(name)


def _canonical_lineage_entry(entry):
    cleaned = dict(entry)
    for key in ("source_table", "target_table"):
        if key in cleaned:
            cleaned[key] = _strip_db(cleaned[key])
    for key in ("source_column", "target_column"):
        if key in cleaned:
            cleaned[key] = _canonical_column(cleaned[key])
    return cleaned


def _node_id(table_name, column_name):
    return f"{_strip_db(table_name)}.{_canonical_column(column_name)}"


def _column_source(table_name, column_name):
    return {"type": "column", "id": _node_id(table_name, column_name)}


def _column_target(table_name, column_name):
    return {"type": "column", "id": _node_id(table_name, column_name)}


def _table_target(table_name):
    return {"type": "table", "id": _strip_db(table_name)}


def _literal_source(value):
    return {"type": "literal", "value": value}


def _expression_source(expression):
    return {"type": "expression", "expression": expression}


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
    return isinstance(node, exp.Literal)


def _literal_value(expression):
    node = expression.this if isinstance(expression, exp.Alias) else expression
    if isinstance(node, exp.Literal):
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
    requested_catalog, requested_db, requested_table = _table_identity(
        table_name
    )
    if not requested_table:
        return None

    for catalog, database, table, columns in _iter_schema_tables(schema):
        if (
            catalog == requested_catalog
            and database == requested_db
            and table == requested_table
            and columns
        ):
            return [_canonical_column(col_name) for col_name in columns]
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


def _register_task_table_schema(schema, table_name, columns):
    catalog, database, table_short = _table_identity(table_name)
    clean_columns = [
        _canonical_column(column_name)
        for column_name in (columns or [])
        if _canonical_column(column_name)
    ]
    if not table_short or not clean_columns:
        return
    schema.setdefault(catalog, {}).setdefault(database, {})[table_short] = {
        column_name: "UNKNOWN" for column_name in clean_columns
    }


def _created_table_columns(stmt):
    target_columns = _target_columns(stmt.this)
    if target_columns:
        return target_columns
    inner = stmt.args.get("expression")
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _projection_output_names(inner)
    return []


def _infer_table_for_column(schema, preferred_table, column_name):
    column_name = _canonical_column(column_name)
    preferred = _strip_db(preferred_table)
    if preferred and _schema_has_column(schema, preferred, column_name):
        return preferred

    matches = []
    for catalog, database, table_name, columns in _iter_schema_tables(schema):
        if column_name in columns:
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


def build_schema_from_texts(sql_texts):
    schema = {}
    for text in sql_texts:
        for stmt in sqlglot.parse(
            normalize_create_table_for_sqlglot(text),
            dialect="doris",
        ):
            if stmt is None:
                continue
            if isinstance(stmt, exp.Create) and isinstance(
                stmt.this, exp.Schema
            ):
                full_name = _canonical_qualified_identifier(
                    stmt.this.this.sql(dialect="doris")
                )
                col_map = {}
                for col in stmt.this.expressions:
                    if isinstance(col, exp.ColumnDef):
                        col_map[_canonical_column(col.this.name)] = (
                            col.args.get("kind").sql(dialect="doris")
                            if col.args.get("kind")
                            else "UNKNOWN"
                        )
                if col_map:
                    catalog, database, table = _table_identity(full_name)
                    schema.setdefault(catalog, {}).setdefault(database, {})[
                        table
                    ] = col_map
    return schema


def _projection_output_name(projection):
    if isinstance(projection, exp.Alias):
        return _canonical_column(projection.alias)
    if isinstance(projection, exp.Column):
        return _canonical_column(projection.name)
    if getattr(projection, "alias_or_name", None):
        return _canonical_column(projection.alias_or_name)
    return ""


def _projection_output_names(query_expr):
    if isinstance(query_expr, exp.Select):
        return [
            _projection_output_name(item) for item in query_expr.expressions
        ]
    if isinstance(query_expr, exp.SetOperation):
        left = query_expr.args.get("this")
        return _projection_output_names(left) if left is not None else []
    return []


def _lineage_nodes_for_select(select_expr, schema):
    nodes = {}
    projections = (
        select_expr.expressions if isinstance(select_expr, exp.Select) else []
    )
    for idx, col_name in enumerate(_projection_output_names(select_expr)):
        if not col_name:
            continue
        if idx < len(projections) and not list(
            projections[idx].find_all(exp.Column)
        ):
            continue
        try:
            nodes[col_name] = lineage(
                column=col_name,
                sql=select_expr.copy(),
                schema=schema,
                dialect="doris",
            )
        except Exception:
            continue
    return nodes


def build_schema_from_ddl(ddl_dir):
    texts = [
        f.read_text(encoding="utf-8") for f in Path(ddl_dir).glob("*.sql")
    ]
    return build_schema_from_texts(texts)


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
    requested_catalog, requested_db, requested_table = _table_identity(
        table_name
    )
    column_name = _canonical_column(column_name)
    for catalog, database, table, columns in _iter_schema_tables(schema):
        if (
            catalog == requested_catalog
            and database == requested_db
            and table == requested_table
            and column_name in columns
        ):
            return True
    return False


def _derived_leaf_sources(select_expr, column_name, schema):
    """将派生表/CTE 输出列追溯到物理源表列。"""
    try:
        node = lineage(
            column=column_name,
            sql=select_expr.copy(),
            schema=schema,
            dialect="doris",
        )
    except Exception:
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
):
    """从 SELECT 的 WHERE / JOIN ON / GROUP BY / HAVING 中提取间接血缘条目"""
    entries = []
    target_table_short = _strip_db(target_table)
    _visited = _visited or set()

    # 收集当前 SELECT 作用域中的物理表、派生表和 CTE 映射。
    from_tables = set()
    alias_map = {}
    derived_sources = {}
    relation_aliases = []
    ctes = _collect_ctes(select_expr)

    def _remember_alias(alias):
        if alias and alias not in relation_aliases:
            relation_aliases.append(alias)

    for relation in _iter_relation_sources(select_expr):
        if isinstance(relation, exp.Subquery) and isinstance(
            relation.this, (exp.Select, exp.SetOperation)
        ):
            alias = _canonical_identifier(relation.alias_or_name)
            if alias:
                derived_sources[alias] = relation.this
                _remember_alias(alias)
        elif isinstance(relation, exp.Table):
            tbl = _strip_db(_table_name(relation))
            alias = _canonical_identifier(
                relation.alias_or_name or relation.name
            )
            if tbl in ctes:
                derived_sources[alias] = ctes[tbl]
                derived_sources[tbl] = ctes[tbl]
                _remember_alias(alias)
            elif tbl and tbl != "UNKNOWN":
                from_tables.add(tbl)
                alias_map[alias] = tbl
                alias_map[_canonical_identifier(relation.name)] = tbl
                _remember_alias(alias)

    def _resolve_column_sources(col):
        tbl_or_alias = _canonical_identifier(col.table)
        col_name = _canonical_column(col.name)
        if tbl_or_alias:
            if tbl_or_alias in derived_sources:
                return _derived_leaf_sources(
                    derived_sources[tbl_or_alias], col_name, schema
                )
            return [
                (
                    _strip_db(alias_map.get(tbl_or_alias, tbl_or_alias)),
                    col_name,
                )
            ]

        derived_aliases = [a for a in relation_aliases if a in derived_sources]
        if len(derived_aliases) == 1:
            sources = _derived_leaf_sources(
                derived_sources[derived_aliases[0]], col_name, schema
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


def _extract_indirect(inner, target_table, file_path, schema):
    """从可能包含 CTE 的 SELECT 中提取间接血缘"""
    entries = []
    default_table = _strip_db(target_table)
    # 主查询
    if isinstance(inner, exp.With):
        inner = inner.this
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        entries.extend(
            _indirect_entries_from_select(
                inner, target_table, file_path, schema, default_table
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


def extract_lineage_from_sql(sql_text, file_path, schema):
    entries = []
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
    except Exception as e:
        print(f"  解析失败 {file_path}: {e}")
        STATS["parse_failures"] += 1
        return entries

    task_schema = _copy_schema(schema)
    for stmt in statements:
        if stmt is None:
            continue
        if isinstance(stmt, exp.Insert):
            entries.extend(_handle_insert(stmt, file_path, task_schema))
        elif isinstance(stmt, exp.Update):
            entries.extend(_handle_update(stmt, file_path, task_schema))
        elif isinstance(stmt, exp.Create):
            entries.extend(_handle_create(stmt, file_path, task_schema))
            _register_task_table_schema(
                task_schema,
                _target_table_sql(stmt.this),
                _created_table_columns(stmt),
            )
        elif isinstance(stmt, exp.Merge):
            entries.extend(_handle_merge(stmt, file_path, task_schema))
        elif isinstance(stmt, exp.Delete):
            entries.extend(_handle_delete(stmt, file_path))
        elif isinstance(stmt, exp.Select) and stmt.args.get("into"):
            entries.extend(_handle_select_into(stmt, file_path, task_schema))
    return [_canonical_lineage_entry(entry) for entry in entries]


def _trace_lineage(
    target_table, select_expr, schema, file_path, target_columns=None
):
    entries = []
    nodes = _lineage_nodes_for_select(select_expr, schema)
    if not nodes and not _projection_output_names(select_expr):
        STATS["lineage_failures"] += 1
        return entries

    for idx, (col_name, node) in enumerate(nodes.items()):
        target_col = (
            target_columns[idx]
            if target_columns is not None and idx < len(target_columns)
            else col_name
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
                entries.append(
                    {
                        **edge,
                        "lineage_type": "direct",
                        "expression": node.expression.sql(dialect="doris")
                        if hasattr(node.expression, "sql")
                        else str(node.expression),
                        "source_file": file_path,
                    }
                )

    if isinstance(select_expr, exp.Select):
        for idx, projection in enumerate(select_expr.expressions):
            if list(projection.find_all(exp.Column)):
                continue
            if isinstance(projection, exp.Star) or list(
                projection.find_all(exp.Star)
            ):
                continue
            target_col = (
                target_columns[idx]
                if target_columns is not None and idx < len(target_columns)
                else projection.alias_or_name
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
        select_expr, target_table, file_path, schema
    )
    entries.extend(indirect_entries)

    return entries


def _handle_insert(stmt, file_path, schema):
    target_table = _target_table_sql(stmt.this)
    target_columns = _target_columns(stmt.this)
    if target_columns is None:
        target_columns = _schema_columns_for_table(schema, target_table)
    inner = stmt.expression
    if isinstance(inner, exp.Values):
        return _extract_values_lineage(target_table, inner, file_path)
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _trace_lineage(
            target_table, inner, schema, file_path, target_columns
        )
    return []


def _handle_update(stmt, file_path, schema):
    target_table = _target_table_sql(stmt.this)
    select = update_to_select(stmt)
    return _trace_lineage(target_table, select, schema, file_path)


def _handle_create(stmt, file_path, schema):
    target_table = _target_table_sql(stmt.this)
    target_columns = _target_columns(stmt.this)
    inner = stmt.args.get("expression")
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _trace_lineage(
            target_table, inner, schema, file_path, target_columns
        )
    return []


def _handle_merge(stmt, file_path, schema):
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
                _trace_lineage(target_table, select, schema, file_path)
            )
        elif isinstance(action, exp.Insert):
            inner = action.expression
            if isinstance(inner, exp.Select):
                entries.extend(
                    _trace_lineage(target_table, inner, schema, file_path)
                )
            elif isinstance(inner, exp.Tuple):
                entries.extend(
                    _extract_values_lineage(target_table, action, file_path)
                )
    return entries


def _handle_select_into(stmt, file_path, schema):
    into = stmt.args.get("into")
    if not into:
        return []
    target_table = _target_table_sql(into.this)
    return _trace_lineage(target_table, stmt, schema, file_path)


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


def _normalize_transient_tables(transient_tables):
    unique = {}
    for table in transient_tables or []:
        name = _strip_db(table.get("name", ""))
        source_file = table.get("source_file", "")
        if not name:
            continue
        normalized = dict(table)
        normalized["name"] = name
        normalized["source_file"] = source_file
        normalized["is_transient"] = bool(normalized.get("is_transient", True))
        key = (
            name,
            source_file,
            normalized.get("created_statement_index"),
            normalized.get("dropped_statement_index"),
        )
        unique[key] = normalized
    return sorted(
        unique.values(),
        key=lambda item: (
            item.get("source_file", ""),
            item.get("created_statement_index", -1),
            item.get("name", ""),
        ),
    )


def _transient_table_occurrence(table):
    return {
        "source_file": table.get("source_file", ""),
        "created_statement_index": table.get("created_statement_index"),
        "dropped_statement_index": table.get("dropped_statement_index"),
        "is_ctas": bool(table.get("is_ctas", False)),
        "is_temporary": bool(table.get("is_temporary", False)),
        "dropped_in_same_task": bool(table.get("dropped_in_same_task", False)),
    }


def build_lineage_output(all_lineage, schema, transient_tables=None):
    """Build serialized lineage output, preserving transient table metadata."""
    unique = []
    seen = set()
    for e in all_lineage:
        is_indirect = e.get("lineage_type") == "indirect"
        if is_indirect:
            key = (
                e.get("source_table", ""),
                e.get("source_column", ""),
                e.get("target_table", ""),
                e.get("condition_type", ""),
                e.get("condition_expression", ""),
                e.get("source_file", ""),
            )
        elif e.get("source_type"):
            key = (
                e.get("source_type", ""),
                e.get("source_value", ""),
                e.get("source_expression", ""),
                e.get("target_table", ""),
                e.get("target_column", ""),
                e.get("expression", ""),
                e.get("source_file", ""),
            )
        else:
            key = (
                e.get("source_table", ""),
                e.get("source_column", ""),
                e.get("target_table", ""),
                e.get("target_column", ""),
                e.get("expression", ""),
                e.get("source_file", ""),
            )
        if key not in seen:
            seen.add(key)
            unique.append(e)
    all_lineage = sorted(
        unique,
        key=lambda e: (
            e.get("source_file", ""),
            e.get("lineage_type", "direct"),
            e.get("source_type", ""),
            e.get("source_table", ""),
            e.get("source_column", ""),
            e.get("source_value", ""),
            e.get("source_expression", ""),
            e.get("target_table", ""),
            e.get("target_column", ""),
            e.get("condition_type", ""),
            e.get("condition_expression", ""),
            e.get("expression", ""),
        ),
    )

    direct_entries = [
        e for e in all_lineage if e.get("lineage_type") != "indirect"
    ]
    indirect_entries = [
        e for e in all_lineage if e.get("lineage_type") == "indirect"
    ]

    tables = {}
    edges = []
    transient_tables = _normalize_transient_tables(transient_tables)
    transient_sources_by_table = {}
    transient_occurrences_by_table = {}
    for table in transient_tables:
        transient_sources_by_table.setdefault(table["name"], set()).add(
            table.get("source_file", "")
        )
        transient_occurrences_by_table.setdefault(table["name"], []).append(
            _transient_table_occurrence(table)
        )

    schema_columns_by_table = {}
    schema_type_by_table_col = {}
    for catalog, database, raw_tbl, cols in _iter_schema_tables(schema):
        full_table_name = _qualified_table_name(catalog, database, raw_tbl)
        tbl = _strip_db(full_table_name)
        if not tbl:
            continue
        table_columns = schema_columns_by_table.setdefault(tbl, [])
        for raw_col, col_type in (cols or {}).items():
            col = _canonical_column(raw_col)
            if not col:
                continue
            key = (tbl, col)
            if key in schema_type_by_table_col:
                continue
            schema_type_by_table_col[key] = col_type
            table_columns.append((col, col_type))

    column_names_by_table = {}
    column_objects_by_table = {}

    def _schema_column_type(tbl, col):
        tbl = _strip_db(tbl)
        col = _canonical_column(col)
        return schema_type_by_table_col.get((tbl, col), "UNKNOWN")

    def _schema_has_table(tbl):
        tbl = _strip_db(tbl)
        return tbl in schema_columns_by_table

    def _ensure_column_index(tbl):
        if tbl not in column_objects_by_table:
            column_objects_by_table[tbl] = {
                c["name"]: c for c in tables[tbl]["columns"]
            }
            column_names_by_table[tbl] = set(column_objects_by_table[tbl])
        return column_names_by_table[tbl], column_objects_by_table[tbl]

    def _ensure_table(tbl):
        tbl = _strip_db(tbl)
        if not tbl:
            return
        if tbl not in tables:
            tables[tbl] = {
                "name": tbl,
                "full_name": _display_table_name(tbl),
                "layer": determine_layer(tbl),
                "columns": [],
            }
            column_names_by_table[tbl] = set()
            column_objects_by_table[tbl] = {}
        if tbl in transient_sources_by_table and not _schema_has_table(tbl):
            tables[tbl]["is_transient"] = True
            tables[tbl]["transient_sources"] = sorted(
                transient_sources_by_table[tbl]
            )
            tables[tbl]["transient_occurrences"] = sorted(
                transient_occurrences_by_table.get(tbl, []),
                key=lambda item: (
                    item.get("source_file", ""),
                    item.get("created_statement_index") or -1,
                    item.get("dropped_statement_index") or -1,
                ),
            )

    def _ensure_column(tbl, col):
        tbl = _strip_db(tbl)
        col = _canonical_column(col)
        if not tbl or not col:
            return
        _ensure_table(tbl)
        column_names, column_objects = _ensure_column_index(tbl)
        if col not in column_names:
            column = {"name": col, "type": _schema_column_type(tbl, col)}
            tables[tbl]["columns"].append(column)
            column_names.add(col)
            column_objects[col] = column

    def _direct_source(entry):
        source_type = str(entry.get("source_type") or "").strip()
        if source_type == "literal":
            return _literal_source(entry.get("source_value", ""))
        if source_type == "expression":
            return _expression_source(entry.get("source_expression", ""))
        return _column_source(
            entry.get("source_table", ""), entry.get("source_column", "")
        )

    def _direct_transformation(entry):
        if entry.get("transformation_type"):
            return str(entry["transformation_type"])
        return _transformation_type_for_expression(entry.get("expression", ""))

    for entry in direct_entries:
        tgt_tbl = _strip_db(entry.get("target_table", ""))
        tgt_col = _canonical_column(entry.get("target_column", ""))
        source_type = str(entry.get("source_type") or "column")
        if source_type == "column":
            src_tbl = _strip_db(entry.get("source_table", ""))
            src_col = _canonical_column(entry.get("source_column", ""))
            if src_tbl == "UNKNOWN":
                continue
            _ensure_column(src_tbl, src_col)
        if not tgt_tbl or not tgt_col:
            continue
        _ensure_column(tgt_tbl, tgt_col)
        edges.append(
            {
                "source": _direct_source(entry),
                "target": _column_target(tgt_tbl, tgt_col),
                "relation_type": "direct",
                "transformation_type": _direct_transformation(entry),
                "expression": entry.get("expression", ""),
                "source_file": entry.get("source_file", ""),
            }
        )

    for entry in indirect_entries:
        src_tbl = _strip_db(entry.get("source_table", ""))
        src_col = _canonical_column(entry.get("source_column", ""))
        tgt_tbl = _strip_db(entry.get("target_table", ""))
        if src_tbl == "UNKNOWN":
            continue
        _ensure_column(src_tbl, src_col)
        _ensure_table(tgt_tbl)
        relation_type = _relation_type_for_condition(
            entry.get("condition_type", "")
        )
        edges.append(
            {
                "source": _column_source(src_tbl, src_col),
                "target": _table_target(tgt_tbl),
                "relation_type": relation_type,
                "transformation_type": relation_type,
                "expression": entry.get("condition_expression", ""),
                "source_file": entry.get("source_file", ""),
            }
        )

    for table in transient_tables:
        _ensure_table(table.get("name", ""))

    for tbl_name, cols in schema_columns_by_table.items():
        if tbl_name in tables:
            column_names, column_objects = _ensure_column_index(tbl_name)
            for col_name, col_type in cols:
                if col_name not in column_names:
                    column = {"name": col_name, "type": col_type}
                    tables[tbl_name]["columns"].append(column)
                    column_names.add(col_name)
                    column_objects[col_name] = column
                elif column_objects[col_name].get("type") == "UNKNOWN":
                    column_objects[col_name]["type"] = col_type

    return {
        "edges": sorted(
            edges,
            key=lambda e: (
                e["source_file"],
                e.get("relation_type", ""),
                _target_sort_key(e.get("target")),
                _source_sort_key(e.get("source")),
                e.get("expression", ""),
            ),
        ),
        "tables": sorted(tables.values(), key=lambda t: t["name"]),
    }


# ============================================================
# 6. 主流程
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="SQL 血缘采集器")
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称, 对应 PROJECT_CONFIG 中的 key",
    )
    args = parser.parse_args()
    configure_project(args.project)
    STATS["parse_failures"] = 0
    STATS["lineage_failures"] = 0
    cfg = PROJECT_CONFIG[args.project]
    project_dir = Path(__file__).parent.parent / cfg["dir"]
    tasks_dir = project_dir / "tasks"
    ddl_dir = project_dir / "ddl"

    # 1. 构建 Schema
    schema = build_schema_from_ddl(ddl_dir)
    table_count = sum(len(tables) for tables in schema.values())
    print(f"Schema: {table_count} 个表")

    # 2. 提取血缘
    all_lineage = []
    transient_tables = []
    task_files = sorted(tasks_dir.glob("*.sql"))
    full_refresh_dir = tasks_dir / "full_refresh"
    if full_refresh_dir.exists():
        task_files.extend(sorted(full_refresh_dir.glob("*.sql")))
    for f in task_files:
        source_file = f.relative_to(tasks_dir).as_posix()
        sql_text = f.read_text(encoding="utf-8")
        task_facts = extract_task_table_facts(sql_text, source_file)
        transient_tables.extend(task_facts["transient_tables"])
        entries = extract_lineage_from_sql(sql_text, source_file, schema)
        all_lineage.extend(entries)
        if entries:
            print(f"  {source_file}: {len(entries)} 条血缘")
    all_lineage = [_canonical_lineage_entry(entry) for entry in all_lineage]

    output = build_lineage_output(
        all_lineage,
        schema,
        transient_tables=transient_tables,
    )
    output_path = (
        Path(__file__).parent / f"lineage_data_{CURRENT_PROJECT}.json"
    )
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(output, fp, ensure_ascii=False, indent=2)
    legacy_output_path = None
    if CURRENT_PROJECT == "shop":
        legacy_output_path = Path(__file__).parent / "lineage_data.json"
        with open(legacy_output_path, "w", encoding="utf-8") as fp:
            json.dump(output, fp, ensure_ascii=False, indent=2)

    print("\n血缘提取完成!")
    direct_count = sum(
        1 for edge in output["edges"] if edge.get("relation_type") == "direct"
    )
    indirect_count = len(output["edges"]) - direct_count
    node_count = sum(
        len(table.get("columns", [])) for table in output["tables"]
    )
    transient_count = sum(
        1 for table in output["tables"] if table.get("is_transient")
    )
    print(f"  直接血缘: {direct_count} 条边")
    print(f"  间接血缘: {indirect_count} 条边")
    print(f"  节点数: {node_count}")
    print(f"  表数: {len(output['tables'])}")
    print(f"  临时表: {transient_count}")
    if STATS["parse_failures"]:
        print(f"  解析失败: {STATS['parse_failures']} 个文件")
    if STATS["lineage_failures"]:
        print(f"  lineage 失败: {STATS['lineage_failures']} 个目标表")
    print(f"  输出: {output_path}")
    if legacy_output_path:
        print(f"  兼容输出: {legacy_output_path}")

    table_map = {table["name"]: table for table in output["tables"]}
    for layer in ["ODS", "DWD", "DWS", "ADS"]:
        layer_tables = [
            (name, info)
            for name, info in table_map.items()
            if info["layer"] == layer
        ]
        if layer_tables:
            print(f"\n[{layer}]")
            for name, info in sorted(layer_tables):
                cols = info["columns"]
                print(
                    f"  {name} ({len(cols)}): {', '.join(c['name'] for c in cols[:10])}{'...' if len(cols) > 10 else ''}"
                )

    others = [
        (name, info)
        for name, info in table_map.items()
        if info["layer"] == "OTHER"
    ]
    if others:
        print("\n[UNRESOLVED]")
        for name, info in sorted(others):
            print(f"  {name} ({len(info['columns'])} cols)")

    return output


if __name__ == "__main__":
    main()
