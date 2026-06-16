"""Asset graph projections built from complete lineage data."""
from __future__ import annotations

import json
from collections import defaultdict

from lineage.table_graph import _table_from_node, build_table_graph


def transient_table_names(lineage_data: dict) -> set[str]:
    """Return transient table names recorded in lineage metadata."""
    names = set()
    for table in lineage_data.get("tables") or []:
        if table.get("is_transient"):
            name = str(table.get("name") or "").strip()
            if name:
                names.add(name)

    return names


def _all_graph_tables(upstream: dict, downstream: dict) -> set[str]:
    names = set(upstream) | set(downstream)
    for tables in upstream.values():
        names.update(tables)
    for tables in downstream.values():
        names.update(tables)
    return names


def _edge_record(edge: dict) -> dict[str, str]:
    source = edge.get("source")
    target = edge.get("target")
    if isinstance(source, dict) or isinstance(target, dict):
        if (
            not isinstance(source, dict)
            or not isinstance(target, dict)
            or source.get("type") != "column"
            or target.get("type") != "column"
            or edge.get("relation_type", "direct") != "direct"
        ):
            return {}
        source_id = str(source.get("id") or "")
        target_id = str(target.get("id") or "")
    else:
        source_id = str(source or "")
        target_id = str(target or "")
    return {
        "source": source_id,
        "target": target_id,
        "expression": str(edge.get("expression") or ""),
        "source_file": str(edge.get("source_file") or ""),
    }


def _edge_sort_key(edge: dict) -> tuple[str, str, str, str]:
    return (
        str(edge.get("target") or ""),
        str(edge.get("source") or ""),
        str(edge.get("expression") or ""),
        str(edge.get("source_file") or ""),
    )


def _condition_record(edge: dict) -> dict[str, str]:
    if isinstance(edge.get("source"), dict):
        source = str((edge.get("source") or {}).get("id") or "")
        condition_type = str(edge.get("relation_type") or "").upper()
        condition_expression = str(edge.get("expression") or "")
    else:
        source = str(edge.get("source") or "")
        condition_type = str(edge.get("condition_type") or "")
        condition_expression = str(edge.get("condition_expression") or "")
    return {
        "source": source,
        "condition_type": condition_type,
        "condition_expression": condition_expression,
        "source_file": str(edge.get("source_file") or ""),
    }


def _condition_sort_key(edge: dict) -> tuple[str, str, str, str]:
    return (
        str(edge.get("source") or ""),
        str(edge.get("condition_type") or ""),
        str(edge.get("condition_expression") or ""),
        str(edge.get("source_file") or ""),
    )


def _collapse_upstream(
        table: str,
        upstream: dict,
        transient_tables: set[str],
        visiting: set[str],
) -> set[str]:
    result = set()
    for parent in upstream.get(table, set()):
        if parent in visiting:
            continue
        if parent in transient_tables:
            result.update(
                _collapse_upstream(
                    parent,
                    upstream,
                    transient_tables,
                    visiting | {parent},
                )
            )
        else:
            result.add(parent)
    return result


def _collapse_downstream(
        table: str,
        downstream: dict,
        transient_tables: set[str],
        visiting: set[str],
) -> set[str]:
    result = set()
    for child in downstream.get(table, set()):
        if child in visiting:
            continue
        if child in transient_tables:
            result.update(
                _collapse_downstream(
                    child,
                    downstream,
                    transient_tables,
                    visiting | {child},
                )
            )
        else:
            result.add(child)
    return result


def build_asset_table_graph(lineage_data: dict) -> tuple[dict, dict]:
    """Build a formal asset graph by removing and bypassing transient tables."""
    upstream, downstream = build_table_graph(
        lineage_data.get("edges") or [],
        lineage_data.get("indirect_edges") or [],
    )
    transient_tables = transient_table_names(lineage_data)
    if not transient_tables:
        return upstream, downstream

    asset_tables = _all_graph_tables(upstream, downstream) - transient_tables
    asset_upstream = {}
    asset_downstream = {}

    for table in asset_tables:
        parents = {
            parent
            for parent in _collapse_upstream(
                table,
                upstream,
                transient_tables,
                {table},
            )
            if parent != table and parent not in transient_tables
        }
        if parents:
            asset_upstream[table] = parents

        children = {
            child
            for child in _collapse_downstream(
                table,
                downstream,
                transient_tables,
                {table},
            )
            if child != table and child not in transient_tables
        }
        if children:
            asset_downstream[table] = children

    return asset_upstream, asset_downstream


def _column_incoming_edges(
        edges: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    incoming = defaultdict(list)
    for edge in edges:
        if edge["source"] and edge["target"]:
            incoming[edge["target"]].append(edge)
    for target, target_edges in incoming.items():
        incoming[target] = sorted(target_edges, key=_edge_sort_key)
    return dict(incoming)


def _trace_asset_column_sources(
        node: str,
        incoming: dict[str, list[dict[str, str]]],
        transient_tables: set[str],
        visiting: set[str],
) -> list[tuple[str, list[dict[str, str]], list[str]]]:
    table = _table_from_node(node)
    if table not in transient_tables:
        return [(node, [], [])]
    if node in visiting:
        return []

    traces = []
    for edge in incoming.get(node, []):
        for asset_source, chain, path in _trace_asset_column_sources(
            edge["source"],
            incoming,
            transient_tables,
            visiting | {node},
        ):
            traces.append((asset_source, chain + [edge], path + [node]))
    return traces


def _asset_condition_lineage(
        lineage_data: dict,
        table_name: str,
        incoming: dict[str, list[dict[str, str]]],
        transient_tables: set[str],
) -> list[dict]:
    conditions = []
    seen = set()
    typed_condition_edges = [
        edge for edge in lineage_data.get("edges") or []
        if isinstance(edge.get("target"), dict)
        and (edge.get("target") or {}).get("type") == "table"
        and edge.get("relation_type") != "direct"
    ]
    legacy_condition_edges = lineage_data.get("indirect_edges") or []
    indirect_edges = sorted(
        typed_condition_edges + legacy_condition_edges,
        key=_condition_sort_key,
    )

    for edge in indirect_edges:
        if isinstance(edge.get("target"), dict):
            edge_target = str((edge.get("target") or {}).get("id") or "")
        else:
            edge_target = str(edge.get("target_table") or "")
        if edge_target != table_name:
            continue
        if isinstance(edge.get("source"), dict):
            source = str((edge.get("source") or {}).get("id") or "")
        else:
            source = str(edge.get("source") or "")
        if not source:
            continue

        base = _condition_record(edge)
        if _table_from_node(source) not in transient_tables:
            item = dict(base)
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                conditions.append(item)
            continue

        for asset_source, chain, transient_path in _trace_asset_column_sources(
            source,
            incoming,
            transient_tables,
            set(),
        ):
            if _table_from_node(asset_source) in transient_tables:
                continue
            item = {
                **base,
                "source": asset_source,
                "transient_path": transient_path,
                "expression_chain": chain,
            }
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                conditions.append(item)

    return conditions


def build_asset_column_lineage(
        lineage_data: dict,
        table_name: str,
) -> list[dict]:
    """Return column lineage for an asset table with transient fields bypassed."""
    transient_tables = transient_table_names(lineage_data)
    edges = [
        record
        for edge in lineage_data.get("edges") or []
        for record in [_edge_record(edge)]
        if record.get("source") and record.get("target")
    ]
    incoming = _column_incoming_edges(edges)
    condition_lineage = _asset_condition_lineage(
        lineage_data,
        table_name,
        incoming,
        transient_tables,
    )
    lineage = []
    seen = set()

    for edge in sorted(edges, key=_edge_sort_key):
        if _table_from_node(edge["target"]) != table_name:
            continue

        if _table_from_node(edge["source"]) not in transient_tables:
            item = dict(edge)
            if condition_lineage:
                item["condition_lineage"] = condition_lineage
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                lineage.append(item)
            continue

        for asset_source, chain, transient_path in _trace_asset_column_sources(
            edge["source"],
            incoming,
            transient_tables,
            set(),
        ):
            if _table_from_node(asset_source) in transient_tables:
                continue
            item = {
                "source": asset_source,
                "target": edge["target"],
                "expression": edge["expression"],
                "source_file": edge["source_file"],
                "transient_path": transient_path,
                "expression_chain": chain + [edge],
            }
            if condition_lineage:
                item["condition_lineage"] = condition_lineage
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                lineage.append(item)

    return lineage
