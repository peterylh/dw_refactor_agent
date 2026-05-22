import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class TableContext:
    table_name: str
    layer: str
    columns: list[dict]
    ddl: str
    etl_sql: str
    upstream_tables: list[str]
    downstream_tables: list[str]
    depth_from_ods: int = 0


def extract_dependencies(lineage_data: dict) -> tuple[dict, dict]:
    """提取表级上下游关系"""
    upstream = defaultdict(set)
    downstream = defaultdict(set)

    def _table_from_node(node_id: str) -> str:
        return node_id.rsplit(".", 1)[0]

    for e in lineage_data.get("edges", []):
        src = _table_from_node(e["source"])
        tgt = _table_from_node(e["target"])
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in lineage_data.get("indirect_edges", []):
        src = _table_from_node(ie["source"])
        tgt = ie["target_table"]
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def build_contexts(project: str,
                   lineage_data: dict,
                   ddl_dir: Path = None,
                   tasks_dir: Path = None) -> list[TableContext]:
    """为 DWD/DWS 层所有表构建分类上下文"""
    if not ddl_dir:
        ddl_dir = Path(__file__).resolve().parent.parent / project / "ddl"
    if not tasks_dir:
        tasks_dir = Path(__file__).resolve().parent.parent / project / "tasks"

    upstream, downstream = extract_dependencies(lineage_data)
    contexts = []

    memo = {}
    def get_depth_from_ods(table_name: str, visiting: set = None) -> int:
        if visiting is None: visiting = set()
        if table_name in memo: return memo[table_name]
        if table_name in visiting: return 0
        visiting.add(table_name)
        
        parents = upstream.get(table_name, set())
        if not parents:
            result = 0 if table_name.startswith("ods_") else 1
        else:
            result = min(get_depth_from_ods(p, visiting) for p in parents) + 1
            
        visiting.remove(table_name)
        memo[table_name] = result
        return result

    for table in lineage_data.get("tables", []):
        layer = table.get("layer", "")
        if layer not in ("DWD", "DWS", "DIM"):
            continue

        name = table["name"]

        # Read DDL
        ddl_path = ddl_dir / f"{name}.sql"
        ddl_content = ddl_path.read_text(
            encoding="utf-8") if ddl_path.exists() else ""

        # Read ETL
        task_path = tasks_dir / f"{name}.sql"
        etl_content = task_path.read_text(
            encoding="utf-8") if task_path.exists() else ""

        contexts.append(
            TableContext(table_name=name,
                         layer=layer,
                         columns=table.get("columns", []),
                         ddl=ddl_content,
                         etl_sql=etl_content,
                         upstream_tables=sorted(list(upstream.get(name,
                                                                  set()))),
                         downstream_tables=sorted(
                             list(downstream.get(name, set()))),
                         depth_from_ods=get_depth_from_ods(name)))

    return contexts
