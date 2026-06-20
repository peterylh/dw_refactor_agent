"""Lineage data loading and raw table graph helpers."""

from __future__ import annotations

import json
from collections import defaultdict

from config import TEXT_ENCODING, lineage_data_path

# ============================================================
# 数据加载与图构建
# ============================================================


def load_lineage_data(project: str) -> dict:
    project_path = lineage_data_path(project)
    if project_path.exists():
        with open(project_path, encoding=TEXT_ENCODING) as f:
            return json.load(f)

    raise FileNotFoundError(
        f"未找到 {project} 的血缘数据文件 ({project}/lineage/lineage_data.json)"
    )


def _table_from_node(node_id: str) -> str:
    if isinstance(node_id, dict):
        if node_id.get("type") == "column":
            node_id = node_id.get("id", "")
        elif node_id.get("type") == "table":
            return str(node_id.get("id") or "")
        else:
            return ""
    return str(node_id or "").rsplit(".", 1)[0]


def _edge_source_table(edge: dict) -> str:
    source = edge.get("source")
    if isinstance(source, dict) and source.get("type") != "column":
        return ""
    return _table_from_node(source)


def _edge_target_table(edge: dict) -> str:
    target = edge.get("target")
    return _table_from_node(target)


def build_table_graph(edges: list, indirect_edges: list) -> tuple[dict, dict]:
    upstream = defaultdict(set)
    downstream = defaultdict(set)

    for e in edges:
        src = _edge_source_table(e)
        tgt = _edge_target_table(e)
        if src and tgt and src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in indirect_edges:
        src = _table_from_node(ie["source"])
        tgt = ie["target_table"]
        if src and tgt and src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def build_table_edge_source_files(edges: list, indirect_edges: list) -> dict:
    table_edges = defaultdict(set)

    for edge in edges:
        src = _edge_source_table(edge)
        tgt = _edge_target_table(edge)
        if src and tgt and src != tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))

    for edge in indirect_edges:
        src = _table_from_node(edge.get("source"))
        tgt = edge.get("target_table")
        if not tgt and edge.get("target"):
            tgt = _edge_target_table(edge)
        if src and tgt and src != tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))

    return dict(table_edges)


def build_table_layer_map(tables: list) -> dict:
    return {t["name"]: t["layer"] for t in tables}
