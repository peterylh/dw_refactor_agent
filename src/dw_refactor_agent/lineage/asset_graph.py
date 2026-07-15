"""Asset graph projections built from complete lineage data."""

from __future__ import annotations

import json
from collections import defaultdict

from dw_refactor_agent.lineage.identifiers import (
    column_ref_match_key,
    identifier_match_key,
    short_table_name,
    split_column_ref,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.job_lineage import (
    job_name_from_source_file,
    resolve_job_dependencies,
)
from dw_refactor_agent.lineage.table_graph import (
    _table_from_node,
    collect_table_self_edges,
)


def transient_table_names(lineage_data: dict) -> set[str]:
    """Return process/temporary table names that asset views bypass."""
    names = set()
    for table in lineage_data.get("tables") or []:
        if table.get("is_transient") or table.get("dataset_type") in {
            "process",
            "temporary",
        }:
            for value in (table.get("name"), table.get("full_name")):
                name = str(value or "").strip()
                if name:
                    names.add(name)

    return names


def _table_match_key(table_name: str) -> str:
    return identifier_match_key(table_name)


def _job_match_key(job_name: str) -> str:
    return identifier_match_key(job_name)


def _job_source_file_map(lineage_data: dict) -> dict[str, str]:
    return {
        _job_match_key(job.get("name")): str(job.get("source_file") or "")
        for job in lineage_data.get("jobs") or []
        if _job_match_key(job.get("name"))
    }


def _edge_job(edge: dict) -> str:
    job = str(edge.get("job") or "")
    if job:
        return job
    source_file = str(edge.get("source_file") or "")
    return job_name_from_source_file(source_file) if source_file else ""


def _edge_job_scope(edge: dict) -> str:
    """Return the non-public Job occurrence key carried by an Edge."""
    job = str(edge.get("job") or "")
    if job:
        return job
    return str(edge.get("source_file") or "").replace("\\", "/").strip()


def _edge_source_file(
    edge: dict,
    job_source_files: dict[str, str] | None = None,
) -> str:
    source_file = str(edge.get("source_file") or "")
    if source_file:
        return source_file
    return (job_source_files or {}).get(
        _job_match_key(edge.get("job")),
        "",
    )


def _dataset_context(lineage_data: dict) -> dict:
    exact_candidates = defaultdict(list)
    identity_candidates = defaultdict(list)
    short_candidates = defaultdict(list)
    for table in lineage_data.get("tables") or []:
        name = str(table.get("name") or "")
        full_name = str(table.get("full_name") or "")
        identity_name = full_name or name
        if not identity_name:
            continue
        record = {
            "key": table_identity_match_key(identity_name),
            "dataset_type": str(table.get("dataset_type") or ""),
            "name": name,
            "full_name": full_name,
        }
        if table.get("is_transient") and not record["dataset_type"]:
            record["dataset_type"] = "temporary"
        for value in {name, full_name}:
            if value:
                exact_candidates[_table_match_key(value)].append(record)
        identity_candidates[record["key"]].append(record)
        short_candidates[
            _table_match_key(short_table_name(identity_name))
        ].append(record)

    def unique_candidates(candidates):
        unique = {}
        for candidate in candidates:
            unique.setdefault(candidate["key"], candidate)
        return list(unique.values())

    exact = {
        key: values[0]
        for key, candidates in exact_candidates.items()
        for values in [unique_candidates(candidates)]
        if len(values) == 1
    }
    identities = {
        key: values[0]
        for key, candidates in identity_candidates.items()
        for values in [unique_candidates(candidates)]
        if len(values) == 1
    }
    short = {
        key: values[0]
        for key, candidates in short_candidates.items()
        for values in [unique_candidates(candidates)]
        if len(values) == 1
    }

    jobs = lineage_data.get("jobs") or []
    local_outputs = defaultdict(set)
    for job in jobs:
        job_key = _job_match_key(job.get("name"))
        for output in job.get("outputs") or []:
            local_outputs[job_key].add(
                _dataset_record(output, exact, identities, short)["key"]
            )

    resolved_producers = {}
    dependencies, _diagnostics = resolve_job_dependencies(
        jobs,
        lineage_data.get("tables") or [],
    )
    for dependency in dependencies:
        consumer_key = _job_match_key(dependency.get("downstream_job"))
        producer = str(dependency.get("upstream_job") or "")
        for dataset in dependency.get("datasets") or []:
            dataset_key = _dataset_record(
                dataset,
                exact,
                identities,
                short,
            )["key"]
            resolved_producers[(consumer_key, dataset_key)] = producer

    return {
        "exact": exact,
        "identities": identities,
        "short": short,
        "local_outputs": dict(local_outputs),
        "resolved_producers": resolved_producers,
        "job_source_files": _job_source_file_map(lineage_data),
        "job_scoped": lineage_data.get("format_version") == 2,
    }


def _dataset_record(
    table_name: str,
    exact: dict,
    identities: dict,
    short: dict,
) -> dict:
    table_text = str(table_name or "")
    record = exact.get(_table_match_key(table_text))
    if record is None:
        record = identities.get(table_identity_match_key(table_text))
    if record is None and "." not in table_text:
        record = short.get(_table_match_key(table_text))
    if record is not None:
        return record
    return {
        "key": table_identity_match_key(table_text),
        "dataset_type": "managed",
        "name": table_text,
        "full_name": table_text,
    }


def _dataset_for(table_name: str, context: dict) -> dict:
    return _dataset_record(
        table_name,
        context["exact"],
        context["identities"],
        context["short"],
    )


def _is_bypass_dataset(dataset: dict) -> bool:
    return dataset.get("dataset_type") in {"process", "temporary"}


def _scoped_table_node(
    table_name: str,
    job_name: str,
    endpoint: str,
    context: dict,
) -> tuple:
    dataset = _dataset_for(table_name, context)
    dataset_key = dataset["key"]
    if not _is_bypass_dataset(dataset):
        return "asset", dataset_key

    job_key = _job_match_key(job_name)
    if not context["job_scoped"]:
        return "process", job_key, dataset_key
    if endpoint == "target" or dataset.get("dataset_type") == "temporary":
        return "process", job_key, dataset_key
    if dataset_key in context["local_outputs"].get(job_key, set()):
        return "process", job_key, dataset_key
    producer = context["resolved_producers"].get((job_key, dataset_key))
    return "process", _job_match_key(producer) or job_key, dataset_key


def _is_bypass_node(node: tuple) -> bool:
    return bool(node) and node[0] == "process"


def _same_dataset(first: str, second: str, context: dict) -> bool:
    return (
        _dataset_for(first, context)["key"]
        == _dataset_for(
            second,
            context,
        )["key"]
    )


def _column_node_match_key(node: str) -> tuple:
    return column_ref_match_key(node)


def _is_transient_table(
    table_name: str, transient_table_keys: set[str]
) -> bool:
    return _table_match_key(table_name) in transient_table_keys


def _edge_record(
    edge: dict,
    job_source_files: dict[str, str] | None = None,
) -> dict[str, str]:
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
    record = {
        "source": source_id,
        "target": target_id,
        "expression": str(edge.get("expression") or ""),
        "source_file": _edge_source_file(edge, job_source_files),
    }
    job = str(edge.get("job") or "")
    if job:
        record["job"] = job
    return record


def _edge_sort_key(edge: dict) -> tuple[str, str, str, str, str]:
    return (
        str(edge.get("target") or ""),
        str(edge.get("source") or ""),
        str(edge.get("expression") or ""),
        str(edge.get("job") or ""),
        str(edge.get("source_file") or ""),
    )


def _condition_record(
    edge: dict,
    job_source_files: dict[str, str] | None = None,
) -> dict[str, str]:
    if isinstance(edge.get("source"), dict):
        source = str((edge.get("source") or {}).get("id") or "")
        condition_type = str(edge.get("relation_type") or "").upper()
        condition_expression = str(edge.get("expression") or "")
    else:
        source = str(edge.get("source") or "")
        condition_type = str(edge.get("condition_type") or "")
        condition_expression = str(edge.get("condition_expression") or "")
    record = {
        "source": source,
        "condition_type": condition_type,
        "condition_expression": condition_expression,
        "source_file": _edge_source_file(edge, job_source_files),
    }
    job = str(edge.get("job") or "")
    if job:
        record["job"] = job
    return record


def _condition_sort_key(edge: dict) -> tuple[str, str, str, str, str]:
    return (
        str(edge.get("source") or ""),
        str(edge.get("condition_type") or ""),
        str(edge.get("condition_expression") or ""),
        str(edge.get("job") or ""),
        str(edge.get("source_file") or ""),
    )


def _iter_table_edges(lineage_data: dict):
    for edge in lineage_data.get("edges") or []:
        source_table = _table_from_node(edge.get("source"))
        target_table = _table_from_node(edge.get("target"))
        if source_table and target_table:
            yield edge, source_table, target_table
    for edge in lineage_data.get("indirect_edges") or []:
        source_table = _table_from_node(edge.get("source"))
        target_table = str(
            edge.get("target_table")
            or _table_from_node(edge.get("target"))
            or ""
        )
        if source_table and target_table:
            yield edge, source_table, target_table


def _scoped_table_graph_data(lineage_data: dict) -> dict:
    context = _dataset_context(lineage_data)
    downstream = defaultdict(set)
    display_by_node = {}
    provenance = defaultdict(lambda: {"jobs": set(), "source_files": set()})

    for edge, source_table, target_table in _iter_table_edges(lineage_data):
        job_scope = _edge_job_scope(edge)
        source_node = _scoped_table_node(
            source_table,
            job_scope,
            "source",
            context,
        )
        target_node = _scoped_table_node(
            target_table,
            job_scope,
            "target",
            context,
        )
        if source_node == target_node:
            continue
        downstream[source_node].add(target_node)
        if not _is_bypass_node(source_node):
            display_by_node.setdefault(source_node, source_table)
        if not _is_bypass_node(target_node):
            display_by_node.setdefault(target_node, target_table)

        facts = provenance[(source_node, target_node)]
        job = _edge_job(edge)
        if job:
            facts["jobs"].add(job)
        source_file = _edge_source_file(edge, context["job_source_files"])
        if source_file:
            facts["source_files"].add(source_file)

    return {
        "context": context,
        "downstream": dict(downstream),
        "display_by_node": display_by_node,
        "provenance": dict(provenance),
    }


def _trace_scoped_assets(
    node: tuple,
    downstream: dict,
    visiting: set[tuple],
) -> set[tuple]:
    assets = set()
    for child in downstream.get(node, set()):
        if child in visiting:
            continue
        if _is_bypass_node(child):
            assets.update(
                _trace_scoped_assets(
                    child,
                    downstream,
                    visiting | {child},
                )
            )
        else:
            assets.add(child)
    return assets


def build_asset_table_edge_metadata(lineage_data: dict) -> dict:
    """Return Job and SQL-path evidence for collapsed asset table edges."""
    graph_data = _scoped_table_graph_data(lineage_data)
    downstream = graph_data["downstream"]
    display_by_node = graph_data["display_by_node"]
    provenance = graph_data["provenance"]
    metadata = defaultdict(lambda: {"jobs": set(), "source_files": set()})

    def visit(source, current, jobs, source_files, visiting):
        for child in downstream.get(current, set()):
            if child in visiting:
                continue
            edge_facts = provenance.get(
                (current, child),
                {"jobs": set(), "source_files": set()},
            )
            next_jobs = jobs | edge_facts["jobs"]
            next_files = source_files | edge_facts["source_files"]
            if _is_bypass_node(child):
                visit(
                    source,
                    child,
                    next_jobs,
                    next_files,
                    visiting | {child},
                )
                continue
            if child == source:
                continue
            pair = (display_by_node[source], display_by_node[child])
            metadata[pair]["jobs"].update(next_jobs)
            metadata[pair]["source_files"].update(next_files)

    for source in sorted(display_by_node, key=lambda node: repr(node)):
        visit(source, source, set(), set(), {source})

    return {
        pair: {
            "jobs": set(facts["jobs"]),
            "source_files": set(facts["source_files"]),
        }
        for pair, facts in metadata.items()
    }


def build_asset_table_graph(lineage_data: dict) -> tuple[dict, dict]:
    """Build an asset graph with process occurrences routed by owning Job."""
    graph_data = _scoped_table_graph_data(lineage_data)
    scoped_downstream = graph_data["downstream"]
    display_by_node = graph_data["display_by_node"]
    asset_upstream = {}
    asset_downstream = {}

    for source_node, source_display in display_by_node.items():
        children = _trace_scoped_assets(
            source_node,
            scoped_downstream,
            {source_node},
        )
        child_displays = {
            display_by_node[child]
            for child in children
            if child != source_node and child in display_by_node
        }
        if child_displays:
            asset_downstream[source_display] = child_displays
        for child in children:
            if child == source_node or child not in display_by_node:
                continue
            asset_upstream.setdefault(display_by_node[child], set()).add(
                source_display
            )

    return asset_upstream, asset_downstream


def build_asset_self_edges(lineage_data: dict) -> list[dict]:
    """Return self-loop facts for non-transient asset tables."""
    transient_table_keys = {
        _table_match_key(table)
        for table in transient_table_names(lineage_data)
        if table
    }
    return [
        edge
        for edge in collect_table_self_edges(
            lineage_data.get("edges") or [],
            lineage_data.get("indirect_edges") or [],
            lineage_data.get("jobs") or [],
        )
        if not _is_transient_table(edge.get("table", ""), transient_table_keys)
    ]


def _column_scope_key(
    node: str,
    job_name: str,
    endpoint: str,
    context: dict,
) -> tuple:
    split_ref = split_column_ref(node)
    if split_ref is None:
        return (), _column_node_match_key(node)
    table_name, column_name = split_ref
    return (
        _scoped_table_node(table_name, job_name, endpoint, context),
        identifier_match_key(column_name),
    )


def _public_edge_record(edge: dict) -> dict:
    return {
        key: value
        for key, value in edge.items()
        if key not in {"_job_scope", "_source_key", "_target_key"}
    }


def _scoped_column_edges(lineage_data: dict) -> tuple[list[dict], dict]:
    context = _dataset_context(lineage_data)
    edges = []
    for edge in lineage_data.get("edges") or []:
        record = _edge_record(edge, context["job_source_files"])
        if not record.get("source") or not record.get("target"):
            continue
        job_scope = _edge_job_scope(edge)
        record["_job_scope"] = job_scope
        record["_source_key"] = _column_scope_key(
            record["source"],
            job_scope,
            "source",
            context,
        )
        record["_target_key"] = _column_scope_key(
            record["target"],
            job_scope,
            "target",
            context,
        )
        edges.append(record)
    return sorted(edges, key=_edge_sort_key), context


def _column_incoming_edges(
    edges: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    incoming = defaultdict(list)
    for edge in edges:
        if edge["source"] and edge["target"]:
            target_key = edge.get("_target_key") or _column_node_match_key(
                edge["target"]
            )
            incoming[target_key].append(edge)
    for target, target_edges in incoming.items():
        incoming[target] = sorted(target_edges, key=_edge_sort_key)
    return dict(incoming)


def _trace_asset_column_sources(
    node: str,
    incoming: dict[str, list[dict[str, str]]],
    transient_table_keys: set[str],
    visiting: set[str],
    node_key=None,
) -> list[tuple[str, list[dict[str, str]], list[str]]]:
    table = _table_from_node(node)
    scoped_table_node = (
        node_key[0]
        if isinstance(node_key, tuple)
        and len(node_key) == 2
        and isinstance(node_key[0], tuple)
        else None
    )
    if scoped_table_node is not None:
        is_bypass = _is_bypass_node(scoped_table_node)
    else:
        is_bypass = _is_transient_table(table, transient_table_keys)
    if not is_bypass:
        return [(node, [], [])]
    node_key = node_key or _column_node_match_key(node)
    if node_key in visiting:
        return []

    traces = []
    for edge in incoming.get(node_key, []):
        for asset_source, chain, path in _trace_asset_column_sources(
            edge["source"],
            incoming,
            transient_table_keys,
            visiting | {node_key},
            edge.get("_source_key"),
        ):
            traces.append(
                (
                    asset_source,
                    chain + [_public_edge_record(edge)],
                    path + [node],
                )
            )
    return traces


def _condition_target_table(edge: dict) -> str:
    target = edge.get("target")
    if isinstance(target, dict):
        return str(target.get("id") or "")
    return str(edge.get("target_table") or "")


def _sorted_condition_edges(lineage_data: dict) -> list[dict]:
    typed_edges = [
        edge
        for edge in lineage_data.get("edges") or []
        if isinstance(edge.get("target"), dict)
        and (edge.get("target") or {}).get("type") == "table"
        and edge.get("relation_type") != "direct"
    ]
    return sorted(
        typed_edges + list(lineage_data.get("indirect_edges") or []),
        key=_condition_sort_key,
    )


def _build_condition_edge_index(
    lineage_data: dict,
    context: dict,
) -> dict[tuple, list[dict]]:
    indexed = defaultdict(list)
    for edge in _sorted_condition_edges(lineage_data):
        target = _condition_target_table(edge)
        if not target:
            continue
        key = (
            _dataset_for(target, context)["key"],
            _job_match_key(_edge_job_scope(edge)),
        )
        indexed[key].append(edge)
    return dict(indexed)


def _asset_condition_lineage(
    lineage_data: dict,
    table_name: str,
    incoming: dict[str, list[dict[str, str]]],
    transient_table_keys: set[str],
    context: dict,
    job_scope: str = "",
    condition_edges: list[dict] | None = None,
) -> list[dict]:
    conditions = []
    seen = set()
    indirect_edges = condition_edges
    if indirect_edges is None:
        indirect_edges = _sorted_condition_edges(lineage_data)

    for edge in indirect_edges:
        if job_scope and _job_match_key(
            _edge_job_scope(edge)
        ) != _job_match_key(job_scope):
            continue
        edge_target = _condition_target_table(edge)
        if not _same_dataset(edge_target, table_name, context):
            continue
        if isinstance(edge.get("source"), dict):
            source = str((edge.get("source") or {}).get("id") or "")
        else:
            source = str(edge.get("source") or "")
        if not source:
            continue

        base = _condition_record(edge, context["job_source_files"])
        source_key = _column_scope_key(
            source,
            _edge_job_scope(edge),
            "source",
            context,
        )
        if not _is_bypass_node(source_key[0]):
            item = dict(base)
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                conditions.append(item)
            continue

        for asset_source, chain, transient_path in _trace_asset_column_sources(
            source,
            incoming,
            transient_table_keys,
            set(),
            source_key,
        ):
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
    transient_table_keys = {
        _table_match_key(table) for table in transient_tables if table
    }
    edges, context = _scoped_column_edges(lineage_data)
    incoming = _column_incoming_edges(edges)
    condition_edge_index = _build_condition_edge_index(lineage_data, context)
    target_dataset_key = _dataset_for(table_name, context)["key"]
    lineage = []
    seen = set()
    conditions_by_job = {}

    for edge in sorted(edges, key=_edge_sort_key):
        if not _same_dataset(
            _table_from_node(edge["target"]),
            table_name,
            context,
        ):
            continue
        job_scope = str(edge.get("_job_scope") or "")
        job_key = _job_match_key(job_scope)
        if job_key not in conditions_by_job:
            scoped_condition_edges = condition_edge_index.get(
                (target_dataset_key, job_key),
                [],
            )
            conditions_by_job[job_key] = _asset_condition_lineage(
                lineage_data,
                table_name,
                incoming,
                transient_table_keys,
                context,
                job_scope=job_scope,
                condition_edges=scoped_condition_edges,
            )
        condition_lineage = conditions_by_job[job_key]

        if not _is_bypass_node(edge["_source_key"][0]):
            item = _public_edge_record(edge)
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
            transient_table_keys,
            set(),
            edge.get("_source_key"),
        ):
            item = {
                "source": asset_source,
                "target": edge["target"],
                "expression": edge["expression"],
                "source_file": edge["source_file"],
                "transient_path": transient_path,
                "expression_chain": chain + [_public_edge_record(edge)],
            }
            if edge.get("job"):
                item["job"] = edge["job"]
            if condition_lineage:
                item["condition_lineage"] = condition_lineage
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                lineage.append(item)

    return lineage
