#!/usr/bin/env python3
"""
通用字段级 SQL 血缘采集器
使用 sqlglot.lineage() 替代手写 AST 遍历
支持: INSERT, UPDATE, CTAS, CREATE VIEW, SELECT INTO, MERGE
"""

import json, os
from pathlib import Path
import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage


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

_SHORT_LAYER = {
    "ods_": "ODS",
    "dwd_": "DWD",
    "dws_": "DWS",
    "ads_": "ADS",
    "dim_": "DIM",
}


def determine_layer(table_name):
    short = table_name.replace("shop_dm.", "")
    for prefix, layer in _SHORT_LAYER.items():
        if short.startswith(prefix):
            return layer
    return "OTHER"


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
                    "source_table": _table_name(expr).replace("shop_dm.", ""),
                    "source_column": node.name.split(".")[-1],
                    "target_table": target_table.replace("shop_dm.", ""),
                    "target_column": target_col,
                }
            )
        elif isinstance(expr, exp.Column):
            edges.append(
                {
                    "source_table": (expr.table or "UNKNOWN").replace("shop_dm.", ""),
                    "source_column": expr.name,
                    "target_table": target_table.replace("shop_dm.", ""),
                    "target_column": target_col,
                }
            )
        return
    for child in node.downstream:
        _walk_leaf(child, target_table, target_col, edges)


# ============================================================
# 4b. 间接血缘提取: WHERE / JOIN ON / GROUP BY / HAVING
# ============================================================


def _indirect_entries_from_select(
    select_expr, target_table, file_path, default_table=None
):
    """从 SELECT 的 WHERE / JOIN ON / GROUP BY / HAVING 中提取间接血缘条目"""
    entries = []
    target_table_short = target_table.replace("shop_dm.", "")

    # 收集 FROM/JOIN 中的来源表名,并建立 别名→真实表名 映射
    from_tables = set()
    alias_map = {}
    from_ = select_expr.args.get("from_")
    if from_:
        for table in from_.find_all(exp.Table):
            tbl = _table_name(table).replace("shop_dm.", "")
            if tbl and tbl != "UNKNOWN":
                from_tables.add(tbl)
                alias = table.alias or table.name
                alias_map[alias] = tbl
    joins = select_expr.args.get("joins") or []
    for join in joins:
        for table in join.find_all(exp.Table):
            tbl = _table_name(table).replace("shop_dm.", "")
            if tbl and tbl != "UNKNOWN":
                from_tables.add(tbl)
                alias = table.alias or table.name
                alias_map[alias] = tbl

    def _resolve_table(col):
        tbl_or_alias = col.table
        if tbl_or_alias:
            return alias_map.get(tbl_or_alias, tbl_or_alias).replace("shop_dm.", "")
        if len(from_tables) == 1:
            return next(iter(from_tables))
        return (default_table or "UNKNOWN").replace("shop_dm.", "")

    def _add_entries(condition_type, expression, columns):
        for col in columns:
            tbl = _resolve_table(col)
            if tbl == "UNKNOWN":
                continue
            entries.append(
                {
                    "lineage_type": "indirect",
                    "source_table": tbl,
                    "source_column": col.name,
                    "target_table": target_table_short,
                    "target_column": "",
                    "condition_type": condition_type,
                    "condition_expression": expression.sql(dialect="doris")
                    if hasattr(expression, "sql")
                    else str(expression),
                    "source_file": file_path,
                }
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


def _extract_indirect_from_with(select_expr, target_table, file_path):
    """从 Select 的 with_ 参数中提取 CTE 定义内部的间接血缘"""
    entries = []
    default_table = target_table.replace("shop_dm.", "")
    with_ = select_expr.args.get("with_")
    if with_:
        for cte in with_.expressions:
            cte_select = cte.this
            if isinstance(cte_select, (exp.Select, exp.SetOperation)):
                entries.extend(
                    _indirect_entries_from_select(
                        cte_select, target_table, file_path, default_table
                    )
                )
    return entries


def _extract_indirect(inner, target_table, file_path):
    """从可能包含 CTE 的 SELECT 中提取间接血缘"""
    entries = []
    default_table = target_table.replace("shop_dm.", "")
    # CTE 定义内部 (存储在 select.args['with_'] 中)
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        with_ = inner.args.get("with_")
        if with_:
            for cte in with_.expressions:
                cte_select = cte.this
                if isinstance(cte_select, (exp.Select, exp.SetOperation)):
                    entries.extend(
                        _indirect_entries_from_select(
                            cte_select, target_table, file_path, default_table
                        )
                    )
    # 主查询
    if isinstance(inner, exp.With):
        inner = inner.this
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        entries.extend(
            _indirect_entries_from_select(inner, target_table, file_path, default_table)
        )
    return entries


def _extract_indirect_from_delete(delete_stmt, file_path):
    """DELETE 语句的 WHERE 条件产生自引用间接血缘"""
    target_table = delete_stmt.this.sql(dialect="doris").replace("shop_dm.", "")
    entries = []
    where = delete_stmt.args.get("where")
    if where:
        for col in where.this.find_all(exp.Column):
            tbl = (col.table or target_table).replace("shop_dm.", "")
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


def _trace_lineage(target_table, select_expr, schema, file_path):
    entries = []
    try:
        nodes = lineage(column=None, sql=select_expr, schema=schema, dialect="doris")
    except Exception as e:
        print(f"    lineage 失败 {target_table}: {e}")
        STATS["lineage_failures"] += 1
        return entries

    for col_name, node in nodes.items():
        edges = _extract_leaf_edges(node, target_table, col_name)
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
    indirect_entries = _extract_indirect(select_expr, target_table, file_path)
    entries.extend(indirect_entries)

    return entries


def _handle_insert(stmt, file_path, schema):
    target_table = stmt.this.sql(dialect="doris")
    inner = stmt.expression
    if isinstance(inner, exp.Values):
        return _extract_values_lineage(target_table, inner, file_path)
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        entries = _trace_lineage(target_table, inner, schema, file_path)
        # 补充CTE定义内部的间接血缘(WITH存放在select.args['with_'])
        indirect_extra = _extract_indirect_from_with(inner, target_table, file_path)
        seen_keys = set()
        for e in entries:
            if e.get("lineage_type") == "indirect":
                seen_keys.add(
                    (
                        e["source_table"],
                        e["source_column"],
                        e["target_table"],
                        e["condition_type"],
                    )
                )
        for e in indirect_extra:
            key = (
                e["source_table"],
                e["source_column"],
                e["target_table"],
                e["condition_type"],
            )
            if key not in seen_keys:
                seen_keys.add(key)
                entries.append(e)
        return entries
    return []


def _handle_update(stmt, file_path, schema):
    target_table = stmt.this.sql(dialect="doris")
    select = update_to_select(stmt)
    return _trace_lineage(target_table, select, schema, file_path)


def _handle_create(stmt, file_path, schema):
    target_table = stmt.this.sql(dialect="doris")
    inner = stmt.args.get("expression")
    if isinstance(inner, (exp.Select, exp.SetOperation)):
        return _trace_lineage(target_table, inner, schema, file_path)
    return []


def _handle_merge(stmt, file_path, schema):
    target_table = stmt.this.sql(dialect="doris")
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
    target_table = into.this.sql(dialect="doris")
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
                    "source_table": (col_ref.table or "UNKNOWN").replace(
                        "shop_dm.", ""
                    ),
                    "source_column": col_ref.name,
                    "target_table": target_table.replace("shop_dm.", ""),
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
    project_dir = Path(__file__).parent.parent / "shop"
    tasks_dir = project_dir / "tasks"
    ddl_dir = project_dir / "ddl"

    # 1. 构建 Schema
    schema = build_schema_from_ddl(ddl_dir)
    table_count = sum(len(tables) for tables in schema.values())
    print(f"Schema: {table_count} 个表")

    # 2. 提取血缘
    all_lineage = []
    for f in sorted(tasks_dir.glob("*.sql")):
        entries = extract_lineage_from_sql(
            f.read_text(encoding="utf-8"), str(f), schema
        )
        all_lineage.extend(entries)
        if entries:
            print(f"  {f.name}: {len(entries)} 条血缘")

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
            )
        else:
            key = (
                e["source_table"],
                e["source_column"],
                e["target_table"],
                e["target_column"],
            )
        if key not in seen:
            seen.add(key)
            unique.append(e)
    all_lineage = unique

    # 4. 分离直接 / 间接血缘
    direct_entries = [e for e in all_lineage if e.get("lineage_type") != "indirect"]
    indirect_entries = [e for e in all_lineage if e.get("lineage_type") == "indirect"]

    # 5. 构建节点 + 边（直接血缘）
    nodes = {}
    tables = {}
    edges = []

    def _ensure_node(tbl, col):
        if tbl not in tables:
            tables[tbl] = {
                "name": tbl,
                "full_name": f"shop_dm.{tbl}",
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
            tables[tbl]["columns"].append({"name": col, "type": "UNKNOWN"})

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
                "source_file": os.path.basename(entry.get("source_file", "")),
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
                "source_file": os.path.basename(entry.get("source_file", "")),
            }
        )

    output = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "tables": list(tables.values()),
        "indirect_edges": indirect_edges,
    }
    output_path = Path(__file__).parent / "lineage_data.json"
    with open(output_path, "w", encoding="utf-8") as fp:
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
