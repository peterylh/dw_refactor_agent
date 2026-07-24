"""Lineage data loading and raw table graph helpers."""

from __future__ import annotations

import json
from collections import defaultdict

from dw_refactor_agent.config import (
    TEXT_ENCODING,
    determine_operational_layer,
    get_operational_layer,
    lineage_data_path,
)
from dw_refactor_agent.lineage.identifiers import (
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
        f"未找到 {project} 的血缘数据文件 ({project_path})"
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
    include_self_loops: bool = False,
) -> tuple[str, str]:
    source = _remember_table(display_by_key, source_table)
    target = _remember_table(display_by_key, target_table)
    if (
        not source
        or not target
        or (
            not include_self_loops
            and identifier_match_key(source) == identifier_match_key(target)
        )
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


def _edge_relation_type(edge: dict) -> str:
    return str(
        edge.get("relation_type") or edge.get("condition_type") or "direct"
    )


def _edge_expression(edge: dict) -> str:
    return str(
        edge.get("expression") or edge.get("condition_expression") or ""
    )


def _edge_target(edge: dict):
    if "target" in edge:
        return edge.get("target")
    return edge.get("target_table")


def _self_edge_record(
    edge: dict,
    source_table: str,
    target_table: str,
    job_source_files: dict[str, str] | None = None,
) -> dict:
    record = {
        "table": source_table,
        "source_table": source_table,
        "target_table": target_table,
        "source": edge.get("source"),
        "target": _edge_target(edge),
        "relation_type": _edge_relation_type(edge),
        "expression": _edge_expression(edge),
        "source_file": str(edge.get("source_file") or "")
        or (job_source_files or {}).get(
            identifier_match_key(edge.get("job")),
            "",
        ),
    }
    job = str(edge.get("job") or "")
    if job:
        record["job"] = job
    return record


def _dedupe_self_edges(records: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for record in records:
        key = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def collect_table_self_edges(
    edges: list,
    indirect_edges: list,
    jobs: list | None = None,
) -> list[dict]:
    """Return table self-loop lineage facts without adding graph dependencies."""
    records = []
    display_by_key = {}
    job_source_files = {
        identifier_match_key(job.get("name")): str(
            job.get("source_file") or ""
        )
        for job in jobs or []
        if identifier_match_key(job.get("name"))
    }

    for edge in edges:
        src, tgt = _normalize_table_pair(
            _edge_source_table(edge),
            _edge_target_table(edge),
            display_by_key,
            include_self_loops=True,
        )
        if (
            src
            and tgt
            and identifier_match_key(src) == identifier_match_key(tgt)
        ):
            records.append(
                _self_edge_record(
                    edge,
                    src,
                    tgt,
                    job_source_files,
                )
            )

    for edge in indirect_edges:
        src, tgt = _normalize_table_pair(
            _table_from_node(edge.get("source")),
            edge.get("target_table") or _edge_target_table(edge),
            display_by_key,
            include_self_loops=True,
        )
        if (
            src
            and tgt
            and identifier_match_key(src) == identifier_match_key(tgt)
        ):
            records.append(
                _self_edge_record(
                    edge,
                    src,
                    tgt,
                    job_source_files,
                )
            )

    return _dedupe_self_edges(records)


def build_table_graph(
    edges: list,
    indirect_edges: list,
    include_self_loops: bool = False,
) -> tuple[dict, dict]:
    upstream = defaultdict(set)
    downstream = defaultdict(set)
    display_by_key = {}

    for e in edges:
        src, tgt = _normalize_table_pair(
            _edge_source_table(e),
            _edge_target_table(e),
            display_by_key,
            include_self_loops=include_self_loops,
        )
        if src and tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in indirect_edges:
        src, tgt = _normalize_table_pair(
            _table_from_node(ie.get("source")),
            ie.get("target_table") or _edge_target_table(ie),
            display_by_key,
            include_self_loops=include_self_loops,
        )
        if src and tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def build_table_edge_source_files(
    edges: list,
    indirect_edges: list,
    jobs: list | None = None,
) -> dict:
    table_edges = defaultdict(set)
    display_by_key = {}
    job_source_files = {
        identifier_match_key(job.get("name")): str(
            job.get("source_file") or ""
        )
        for job in jobs or []
        if identifier_match_key(job.get("name"))
    }

    def source_file(edge):
        return str(edge.get("source_file") or "") or job_source_files.get(
            identifier_match_key(edge.get("job")),
            "",
        )

    for edge in edges:
        src, tgt = _normalize_table_pair(
            _edge_source_table(edge),
            _edge_target_table(edge),
            display_by_key,
        )
        if src and tgt:
            table_edges[(src, tgt)].add(source_file(edge))

    for edge in indirect_edges:
        src, tgt = _normalize_table_pair(
            _table_from_node(edge.get("source")),
            edge.get("target_table") or _edge_target_table(edge),
            display_by_key,
        )
        if src and tgt:
            table_edges[(src, tgt)].add(source_file(edge))

    return dict(table_edges)


def build_table_layer_map(
    tables: list,
    project: str,
    model_metadata: dict | None = None,
) -> dict:
    layers = {}
    metadata_by_key = {}
    for model_name, metadata in (model_metadata or {}).items():
        key = identifier_match_key(model_name)
        if key in metadata_by_key:
            raise ValueError(
                "model metadata names collide under case-insensitive lookup: "
                f"{model_name!r}"
            )
        metadata_by_key[key] = metadata
    for table in tables:
        name = str(table.get("name") or "")
        if not name:
            continue
        short_name = name.split(".")[-1]
        metadata = metadata_by_key.get(identifier_match_key(short_name))
        layer = (
            get_operational_layer(metadata)
            if metadata is not None
            else determine_operational_layer(short_name, project)
        )
        layers[name] = str(layer or "OTHER").upper()
    return layers
