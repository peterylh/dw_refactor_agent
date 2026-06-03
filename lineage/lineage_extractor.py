#!/usr/bin/env python3
"""
通用字段级 SQL 血缘采集器
使用 sqlglot.lineage() 替代手写 AST 遍历
支持: INSERT, UPDATE, CTAS, CREATE VIEW, SELECT INTO, MERGE
"""

import json, argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import PROJECT_CONFIG, determine_layer as determine_config_layer

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage


# ============================================================
# 0. 项目配置
# ============================================================

CURRENT_PROJECT = "shop"
CURRENT_DB = "shop_dm"


def configure_project(project_name):
    global CURRENT_PROJECT, CURRENT_DB
    cfg = PROJECT_CONFIG.get(project_name)
    if not cfg:
        raise ValueError(f"未知项目: {project_name}, 可选: {list(PROJECT_CONFIG.keys())}")
    CURRENT_PROJECT = project_name
    CURRENT_DB = cfg["db"]


def _strip_db(name):
    return name.replace(f"{CURRENT_DB}.", "")


def _target_table_sql(target_expr):
    """返回写入目标表名,不包含 INSERT/CREATE 目标列清单。"""
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    return target_expr.sql(dialect="doris")


def _target_columns(target_expr):
    """返回 INSERT/CTAS 显式声明的目标列,用于按 SELECT 位置对齐。"""
    if not isinstance(target_expr, exp.Schema):
        return None
    columns = []
    for col in target_expr.expressions:
        if isinstance(col, exp.ColumnDef):
            columns.append(col.this.name)
        elif hasattr(col, "name"):
            columns.append(col.name)
    return columns or None


# ============================================================
# 1. Schema 构建: 从 DDL 解析
# ============================================================


def build_schema_from_texts(sql_texts):
    schema = {}
    for text in sql_texts:
        for stmt in sqlglot.parse(text, dialect="doris"):
            if stmt is None:
                continue
            if isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Schema):
                full_name = stmt.this.this.sql(dialect="doris")
                col_map = {}
                for col in stmt.this.expressions:
                    if isinstance(col, exp.ColumnDef):
                        col_map[col.this.name] = (
                            col.args.get("kind").sql(dialect="doris")
                            if col.args.get("kind")
                            else "UNKNOWN"
                        )
                if col_map:
                    parts = full_name.split(".")
                    if len(parts) == 2:
                        schema.setdefault(parts[0], {})[parts[1]] = col_map
                    else:
                        schema[full_name] = col_map
    return schema


def build_schema_from_ddl(ddl_dir):
    texts = [f.read_text(encoding="utf-8") for f in Path(ddl_dir).glob("*.sql")]
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
    if tbl_expr.args.get("db"):
        parts.append(tbl_expr.args["db"].name)
    parts.append(tbl_expr.name)
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
                    "source_column": node.name.split(".")[-1],
                    "target_table": _strip_db(target_table),
                    "target_column": target_col,
                }
            )
        elif isinstance(expr, exp.Column):
            edges.append(
                {
                    "source_table": _strip_db(expr.table or "UNKNOWN"),
                    "source_column": expr.name,
                    "target_table": _strip_db(target_table),
                    "target_column": target_col,
                }
            )
        return
    for child in node.downstream:
        _walk_leaf(child, target_table, target_col, edges)


# ============================================================
# 4b. 间接血缘提取: WHERE / JOIN ON / GROUP BY / HAVING
# ============================================================


def _iter_relation_sources(select_expr):
    from_ = select_expr.args.get("from_")
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
    with_ = select_expr.args.get("with_")
    if not with_:
        return ctes
    for cte in with_.expressions:
        if isinstance(cte.this, (exp.Select, exp.SetOperation)):
            ctes[cte.alias_or_name] = cte.this
    return ctes


def _schema_has_column(schema, table_name, column_name):
    table_short = _strip_db(table_name)
    for db_tables in schema.values():
        cols = db_tables.get(table_short)
        if cols and column_name in cols:
            return True
    return False


def _derived_leaf_sources(select_expr, column_name, schema):
    """将派生表/CTE 输出列追溯到物理源表列。"""
    try:
        node = lineage(
            column=column_name,
            sql=select_expr,
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
    select_expr, target_table, file_path, schema, default_table=None, _visited=None
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
            alias = relation.alias_or_name
            if alias:
                derived_sources[alias] = relation.this
                _remember_alias(alias)
        elif isinstance(relation, exp.Table):
            tbl = _strip_db(_table_name(relation))
            alias = relation.alias_or_name or relation.name
            if tbl in ctes:
                derived_sources[alias] = ctes[tbl]
                derived_sources[tbl] = ctes[tbl]
                _remember_alias(alias)
            elif tbl and tbl != "UNKNOWN":
                from_tables.add(tbl)
                alias_map[alias] = tbl
                alias_map[relation.name] = tbl
                _remember_alias(alias)

    def _resolve_column_sources(col):
        tbl_or_alias = col.table
        if tbl_or_alias:
            if tbl_or_alias in derived_sources:
                return _derived_leaf_sources(
                    derived_sources[tbl_or_alias], col.name, schema
                )
            return [(_strip_db(alias_map.get(tbl_or_alias, tbl_or_alias)), col.name)]

        derived_aliases = [a for a in relation_aliases if a in derived_sources]
        if len(derived_aliases) == 1:
            sources = _derived_leaf_sources(
                derived_sources[derived_aliases[0]], col.name, schema
            )
            if sources:
                return sources
        if len(from_tables) == 1:
            return [(next(iter(from_tables)), col.name)]
        if default_table:
            return [(_strip_db(default_table), col.name)]
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
                        "source_column": src_col,
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
            tbl = _strip_db(col.table or target_table)
            entries.append(
                {
                    "lineage_type": "indirect",
                    "source_table": tbl,
                    "source_column": col.name,
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

    for stmt in statements:
        if stmt is None:
            continue
        if isinstance(stmt, exp.Insert):
            entries.extend(_handle_insert(stmt, file_path, schema))
        elif isinstance(stmt, exp.Update):
            entries.extend(_handle_update(stmt, file_path, schema))
        elif isinstance(stmt, exp.Create):
            entries.extend(_handle_create(stmt, file_path, schema))
        elif isinstance(stmt, exp.Merge):
            entries.extend(_handle_merge(stmt, file_path, schema))
        elif isinstance(stmt, exp.Delete):
            entries.extend(_handle_delete(stmt, file_path))
        elif isinstance(stmt, exp.Select) and stmt.args.get("into"):
            entries.extend(_handle_select_into(stmt, file_path, schema))
    return entries


def _trace_lineage(target_table, select_expr, schema, file_path, target_columns=None):
    entries = []
    try:
        nodes = lineage(column=None, sql=select_expr, schema=schema, dialect="doris")
    except Exception as e:
        print(f"    lineage 失败 {target_table}: {e}")
        STATS["lineage_failures"] += 1
        return entries

    for idx, (col_name, node) in enumerate(nodes.items()):
        target_col = (
            target_columns[idx]
            if target_columns is not None and idx < len(target_columns)
            else col_name
        )
        edges = _extract_leaf_edges(node, target_table, target_col)
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

    # 间接血缘: WHERE / JOIN ON / GROUP BY / HAVING
    indirect_entries = _extract_indirect(select_expr, target_table, file_path, schema)
    entries.extend(indirect_entries)

    return entries


def _handle_insert(stmt, file_path, schema):
    target_table = _target_table_sql(stmt.this)
    target_columns = _target_columns(stmt.this)
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
        return _trace_lineage(target_table, inner, schema, file_path, target_columns)
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
            entries.extend(_trace_lineage(target_table, select, schema, file_path))
        elif isinstance(action, exp.Insert):
            inner = action.expression
            if isinstance(inner, exp.Select):
                entries.extend(_trace_lineage(target_table, inner, schema, file_path))
            elif isinstance(inner, exp.Tuple):
                entries.extend(_extract_values_lineage(target_table, action, file_path))
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
        cols = [c.sql() for c in (insert_or_values.args.get("this").expressions or [])]
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
                    "source_column": col_ref.name,
                    "target_table": _strip_db(target_table),
                    "target_column": col_name,
                    "expression": val.sql(dialect="doris")
                    if hasattr(val, "sql")
                    else str(val),
                    "source_file": file_path,
                }
            )
    return entries


# ============================================================
# 6. 主流程
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="SQL 血缘采集器")
    parser.add_argument("--project", default="shop", choices=list(PROJECT_CONFIG.keys()),
                        help="项目名称, 对应 PROJECT_CONFIG 中的 key")
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
    task_files = sorted(tasks_dir.glob("*.sql"))
    full_refresh_dir = tasks_dir / "full_refresh"
    if full_refresh_dir.exists():
        task_files.extend(sorted(full_refresh_dir.glob("*.sql")))
    for f in task_files:
        source_file = f.relative_to(tasks_dir).as_posix()
        entries = extract_lineage_from_sql(
            f.read_text(encoding="utf-8"), source_file, schema
        )
        all_lineage.extend(entries)
        if entries:
            print(f"  {source_file}: {len(entries)} 条血缘")

    # 3. 去重
    unique = []
    seen = set()
    for e in all_lineage:
        is_indirect = e.get("lineage_type") == "indirect"
        if is_indirect:
            key = (
                e["source_table"],
                e["source_column"],
                e["target_table"],
                e["condition_type"],
                e.get("condition_expression", ""),
                e.get("source_file", ""),
            )
        else:
            key = (
                e["source_table"],
                e["source_column"],
                e["target_table"],
                e["target_column"],
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
            e.get("source_table", ""),
            e.get("source_column", ""),
            e.get("target_table", ""),
            e.get("target_column", ""),
            e.get("condition_type", ""),
            e.get("condition_expression", ""),
            e.get("expression", ""),
        ),
    )

    # 4. 分离直接 / 间接血缘
    direct_entries = [e for e in all_lineage if e.get("lineage_type") != "indirect"]
    indirect_entries = [e for e in all_lineage if e.get("lineage_type") == "indirect"]

    # 5. 构建节点 + 边（直接血缘）
    nodes = {}
    tables = {}
    edges = []

    def _schema_column_type(tbl, col):
        for db_tables in schema.values():
            table_cols = db_tables.get(tbl)
            if table_cols and col in table_cols:
                return table_cols[col]
        return "UNKNOWN"

    def _ensure_node(tbl, col):
        if tbl not in tables:
            tables[tbl] = {
                "name": tbl,
                "full_name": f"{CURRENT_DB}.{tbl}",
                "layer": determine_layer(tbl),
                "columns": [],
            }
        node_id = f"{tbl}.{col}"
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "table": tbl,
                "column": col,
                "layer": determine_layer(tbl),
            }
        if col not in {c["name"] for c in tables[tbl]["columns"]}:
            tables[tbl]["columns"].append(
                {"name": col, "type": _schema_column_type(tbl, col)}
            )

    for entry in direct_entries:
        src_tbl, src_col = entry["source_table"], entry["source_column"]
        tgt_tbl, tgt_col = entry["target_table"], entry["target_column"]
        if src_tbl == "UNKNOWN":
            continue
        _ensure_node(src_tbl, src_col)
        _ensure_node(tgt_tbl, tgt_col)
        edges.append(
            {
                "source": f"{src_tbl}.{src_col}",
                "target": f"{tgt_tbl}.{tgt_col}",
                "expression": entry.get("expression", ""),
                "source_file": entry.get("source_file", ""),
            }
        )

    # 6. 构建间接血缘边
    indirect_edges = []
    for entry in indirect_entries:
        src_tbl, src_col = entry["source_table"], entry["source_column"]
        if src_tbl == "UNKNOWN":
            continue
        _ensure_node(src_tbl, src_col)
        indirect_edges.append(
            {
                "source": f"{src_tbl}.{src_col}",
                "target_table": entry["target_table"],
                "condition_type": entry["condition_type"],
                "condition_expression": entry.get("condition_expression", ""),
                "source_file": entry.get("source_file", ""),
            }
        )

    # 7. 合并 DDL 中无血缘边的列到 tables 输出
    for db_name, db_tables in schema.items():
        for tbl_name, cols in db_tables.items():
            if tbl_name in tables:
                existing_cols = {c["name"]: c for c in tables[tbl_name]["columns"]}
                for col_name, col_type in cols.items():
                    if col_name not in existing_cols:
                        tables[tbl_name]["columns"].append(
                            {"name": col_name, "type": col_type}
                        )
                    elif existing_cols[col_name].get("type") == "UNKNOWN":
                        existing_cols[col_name]["type"] = col_type

    output = {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(
            edges,
            key=lambda e: (
                e["source_file"],
                e["source"],
                e["target"],
                e.get("expression", ""),
            ),
        ),
        "tables": sorted(tables.values(), key=lambda t: t["name"]),
        "indirect_edges": sorted(
            indirect_edges,
            key=lambda e: (
                e["source_file"],
                e["source"],
                e["target_table"],
                e["condition_type"],
                e.get("condition_expression", ""),
            ),
        ),
    }
    output_path = Path(__file__).parent / f"lineage_data_{CURRENT_PROJECT}.json"
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(output, fp, ensure_ascii=False, indent=2)
    legacy_output_path = None
    if CURRENT_PROJECT == "shop":
        legacy_output_path = Path(__file__).parent / "lineage_data.json"
        with open(legacy_output_path, "w", encoding="utf-8") as fp:
            json.dump(output, fp, ensure_ascii=False, indent=2)

    print(f"\n血缘提取完成!")
    print(f"  直接血缘: {len(edges)} 条边")
    print(f"  间接血缘: {len(indirect_edges)} 条边")
    print(f"  节点数: {len(nodes)}")
    print(f"  表数: {len(tables)}")
    if STATS["parse_failures"]:
        print(f"  解析失败: {STATS['parse_failures']} 个文件")
    if STATS["lineage_failures"]:
        print(f"  lineage 失败: {STATS['lineage_failures']} 个目标表")
    print(f"  输出: {output_path}")
    if legacy_output_path:
        print(f"  兼容输出: {legacy_output_path}")

    for layer in ["ODS", "DWD", "DWS", "ADS"]:
        layer_tables = [(n, i) for n, i in tables.items() if i["layer"] == layer]
        if layer_tables:
            print(f"\n[{layer}]")
            for name, info in sorted(layer_tables):
                cols = info["columns"]
                print(
                    f"  {name} ({len(cols)}): {', '.join(c['name'] for c in cols[:10])}{'...' if len(cols) > 10 else ''}"
                )

    others = [(n, i) for n, i in tables.items() if i["layer"] == "OTHER"]
    if others:
        print(f"\n[UNRESOLVED]")
        for name, info in sorted(others):
            print(f"  {name} ({len(info['columns'])} cols)")

    return output


if __name__ == "__main__":
    main()
