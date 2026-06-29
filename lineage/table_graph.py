"""Lineage data loading and raw table graph helpers."""

from __future__ import annotations

import json
from collections import defaultdict

from config import TEXT_ENCODING, lineage_data_path
from lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    split_column_ref,
)

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
            return canonical_qualified_identifier(node_id.get("id"))
        else:
            return ""
    split_ref = split_column_ref(node_id)
    if split_ref is not None:
        return split_ref[0]
    return canonical_qualified_identifier(node_id)


def _remember_table(display_by_key: dict, table_name: str) -> str:
    table_key = identifier_match_key(table_name)
    if not table_key:
        return ""
    return display_by_key.setdefault(table_key, table_name)


def _normalize_table_pair(
    source_table: str,
    target_table: str,
    display_by_key: dict,
) -> tuple[str, str]:
    source = _remember_table(display_by_key, source_table)
    target = _remember_table(display_by_key, target_table)
    if (
        not source
        or not target
        or identifier_match_key(source) == identifier_match_key(target)
    ):
        return "", ""
    return source, target


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
    display_by_key = {}

    for e in edges:
        src, tgt = _normalize_table_pair(
            _edge_source_table(e),
            _edge_target_table(e),
            display_by_key,
        )
        if src and tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in indirect_edges:
        src, tgt = _normalize_table_pair(
            _table_from_node(ie.get("source")),
            ie.get("target_table") or _edge_target_table(ie),
            display_by_key,
        )
        if src and tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def build_table_edge_source_files(edges: list, indirect_edges: list) -> dict:
    table_edges = defaultdict(set)
    display_by_key = {}

    for edge in edges:
        src, tgt = _normalize_table_pair(
            _edge_source_table(edge),
            _edge_target_table(edge),
            display_by_key,
        )
        if src and tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))

    for edge in indirect_edges:
        src, tgt = _normalize_table_pair(
            _table_from_node(edge.get("source")),
            edge.get("target_table") or _edge_target_table(edge),
            display_by_key,
        )
        if src and tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))

    return dict(table_edges)


def build_table_layer_map(tables: list) -> dict:
    return {t["name"]: t["layer"] for t in tables}
