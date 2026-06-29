"""Indexed read view for lineage snapshots."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from lineage.asset_graph import (
    _column_incoming_edges,
    _condition_record,
    _condition_sort_key,
    _edge_record,
    _edge_sort_key,
    _trace_asset_column_sources,
    build_asset_table_graph,
    transient_table_names,
)
from lineage.identifiers import identifier_match_key, short_table_name
from lineage.model import LineageSnapshot
from lineage.table_graph import (
    _table_from_node,
    build_table_edge_source_files,
    build_table_graph,
)

AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)


def _empty_lineage_facts() -> dict[str, Any]:
    return {
        "has_lineage": False,
        "has_group_by": False,
        "has_aggregate": False,
        "aggregate_columns": [],
        "constant_columns": [],
        "plain_columns": [],
        "plain_column_sources": {},
        "group_by_sources": [],
        "source_files": [],
    }


def _short_column_name(sql_text: str) -> str:
    name = str(sql_text or "").strip().replace("`", "").replace('"', "")
    if not name:
        return ""
    return name.split(".")[-1]


def _short_table_name(table_name: str) -> str:
    return short_table_name(table_name)


def _transformation_type_for_expression(expression: str) -> str:
    if AGGREGATE_PATTERN.search(str(expression or "")):
        return "aggregation"
    return "passthrough"


def _source_file_key(source_file: str) -> str:
    return str(source_file or "").replace("\\", "/").strip()


class LineageView:
    """Pre-indexed lineage queries for one snapshot."""

    def __init__(self, snapshot: LineageSnapshot):
        self.snapshot = snapshot
        self._data = snapshot.to_dict()
        self._raw_edges = [edge.raw for edge in snapshot.edges]
        self._raw_indirect_edges = [
            dict(edge) for edge in snapshot.indirect_edges
        ]
        self._transient_tables = transient_table_names(self._data)
        self._transient_table_keys = {
            identifier_match_key(table)
            for table in self._transient_tables
            if table
        }
        self._raw_table_graph = build_table_graph(
            self._raw_edges,
            self._raw_indirect_edges,
        )
        self._asset_table_graph = build_asset_table_graph(self._data)
        self._column_edges = None
        self._incoming = None
        self._column_edges_by_target_table = None
        self._condition_edges_by_target_table = None
        self._lineage_facts_by_table = None
        self._targets_by_source_file = None
        self._table_edge_source_files = None

    @classmethod
    def from_data(cls, project: str, data: dict[str, Any]) -> "LineageView":
        return cls(LineageSnapshot.from_dict(project, data))

    @classmethod
    def from_parts(
        cls,
        project: str,
        tables: list | None,
        edges: list | None,
        indirect_edges: list | None = None,
    ) -> "LineageView":
        return cls.from_data(
            project,
            {
                "tables": tables or [],
                "edges": edges or [],
                "indirect_edges": indirect_edges or [],
            },
        )

    def tables(self) -> list:
        return list(self.snapshot.tables)

    def raw_table_graph(
        self,
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        upstream, downstream = self._raw_table_graph
        return (
            {table: set(parents) for table, parents in upstream.items()},
            {table: set(children) for table, children in downstream.items()},
        )

    def asset_table_graph(
        self,
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        upstream, downstream = self._asset_table_graph
        return (
            {table: set(parents) for table, parents in upstream.items()},
            {table: set(children) for table, children in downstream.items()},
        )

    def upstream_tables(self, table_name: str) -> set[str]:
        upstream, _downstream = self._asset_table_graph
        return set(upstream.get(table_name, set()))

    def downstream_tables(self, table_name: str) -> set[str]:
        _upstream, downstream = self._asset_table_graph
        return set(downstream.get(table_name, set()))

    def _is_transient_table(self, table_name: str) -> bool:
        return identifier_match_key(table_name) in self._transient_table_keys

    def column_lineage_for_table(self, table_name: str) -> list[dict]:
        self._ensure_column_indexes()
        condition_lineage = self._condition_lineage_for_table(table_name)
        lineage = []
        seen = set()

        target_key = identifier_match_key(table_name)
        for edge in self._column_edges_by_target_table.get(target_key, []):
            if not self._is_transient_table(_table_from_node(edge["source"])):
                item = dict(edge)
                if condition_lineage:
                    item["condition_lineage"] = condition_lineage
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    lineage.append(item)
                continue

            for (
                asset_source,
                chain,
                transient_path,
            ) in _trace_asset_column_sources(
                edge["source"],
                self._incoming,
                self._transient_table_keys,
                set(),
            ):
                if self._is_transient_table(_table_from_node(asset_source)):
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

    def lineage_facts_for_table(self, table_name: str) -> dict[str, Any]:
        if self._lineage_facts_by_table is None:
            self._lineage_facts_by_table = self._index_lineage_facts()
        facts = self._lineage_facts_by_table.get(table_name)
        if not facts:
            return _empty_lineage_facts()
        return {
            "has_lineage": facts["has_lineage"],
            "has_group_by": facts["has_group_by"],
            "has_aggregate": facts["has_aggregate"],
            "aggregate_columns": list(facts["aggregate_columns"]),
            "constant_columns": list(facts["constant_columns"]),
            "plain_columns": list(facts["plain_columns"]),
            "plain_column_sources": dict(facts["plain_column_sources"]),
            "group_by_sources": list(facts["group_by_sources"]),
            "source_files": list(facts["source_files"]),
        }

    def targets_by_source_file(self, source_file: str) -> set[str]:
        if self._targets_by_source_file is None:
            self._targets_by_source_file = self._index_targets_by_source_file()
        return set(
            self._targets_by_source_file.get(
                _source_file_key(source_file), set()
            )
        )

    def table_edge_source_files(self) -> dict[tuple[str, str], set[str]]:
        if self._table_edge_source_files is None:
            self._table_edge_source_files = build_table_edge_source_files(
                self._raw_edges,
                self._raw_indirect_edges,
            )
        return {
            edge: set(source_files)
            for edge, source_files in self._table_edge_source_files.items()
        }

    def _ensure_column_indexes(self) -> None:
        if self._column_edges is not None:
            return
        self._column_edges = sorted(
            [
                record
                for edge in self._raw_edges
                for record in [_edge_record(edge)]
                if record.get("source") and record.get("target")
            ],
            key=_edge_sort_key,
        )
        self._incoming = _column_incoming_edges(self._column_edges)
        self._column_edges_by_target_table = (
            self._index_column_edges_by_target()
        )
        self._condition_edges_by_target_table = self._index_condition_edges()

    def _index_column_edges_by_target(self) -> dict[str, list[dict]]:
        grouped = defaultdict(list)
        for edge in self._column_edges:
            target_table = _table_from_node(edge["target"])
            if target_table:
                grouped[identifier_match_key(target_table)].append(edge)
        return dict(grouped)

    def _index_condition_edges(self) -> dict[str, list[dict]]:
        grouped = defaultdict(list)
        typed_condition_edges = [
            edge
            for edge in self._raw_edges
            if isinstance(edge.get("target"), dict)
            and (edge.get("target") or {}).get("type") == "table"
            and edge.get("relation_type") != "direct"
        ]
        condition_edges = sorted(
            typed_condition_edges + self._raw_indirect_edges,
            key=_condition_sort_key,
        )
        for edge in condition_edges:
            target = self._condition_target_table(edge)
            if target:
                grouped[identifier_match_key(target)].append(edge)
        return dict(grouped)

    def _condition_lineage_for_table(self, table_name: str) -> list[dict]:
        self._ensure_column_indexes()
        conditions = []
        seen = set()

        target_key = identifier_match_key(table_name)
        for edge in self._condition_edges_by_target_table.get(target_key, []):
            source = self._condition_source(edge)
            if not source:
                continue

            base = _condition_record(edge)
            if not self._is_transient_table(_table_from_node(source)):
                item = dict(base)
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    conditions.append(item)
                continue

            for (
                asset_source,
                chain,
                transient_path,
            ) in _trace_asset_column_sources(
                source,
                self._incoming,
                self._transient_table_keys,
                set(),
            ):
                if self._is_transient_table(_table_from_node(asset_source)):
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

    def _index_lineage_facts(self) -> dict[str, dict[str, Any]]:
        grouped = defaultdict(
            lambda: {
                "direct_edges": 0,
                "aggregate_columns": set(),
                "constant_columns": set(),
                "plain_columns": {},
                "group_by_sources": set(),
                "source_files": set(),
            }
        )

        for edge in self.snapshot.edges:
            target_table = edge.target.table_name()
            if not target_table:
                continue

            facts = grouped[target_table]
            if edge.source_file:
                facts["source_files"].add(edge.source_file)

            if (
                edge.relation_type == "group_by"
                and edge.source.type == "column"
            ):
                if edge.source.id:
                    facts["group_by_sources"].add(edge.source.id)
                continue

            target_column = edge.target.column_name()
            if edge.relation_type != "direct" or not target_column:
                continue

            facts["direct_edges"] += 1
            transformation = (
                edge.transformation_type
                or _transformation_type_for_expression(edge.expression)
            )
            if transformation == "aggregation":
                facts["aggregate_columns"].add(target_column)
            elif transformation == "constant" or edge.source.type in {
                "literal",
                "expression",
            }:
                facts["constant_columns"].add(target_column)
            elif edge.source.type == "column":
                facts["plain_columns"][target_column] = edge.source.id

        return {
            table: {
                "has_lineage": bool(
                    facts["direct_edges"] or facts["group_by_sources"]
                ),
                "has_group_by": bool(facts["group_by_sources"]),
                "has_aggregate": bool(facts["aggregate_columns"]),
                "aggregate_columns": sorted(facts["aggregate_columns"]),
                "constant_columns": sorted(facts["constant_columns"]),
                "plain_columns": sorted(facts["plain_columns"]),
                "plain_column_sources": dict(
                    sorted(facts["plain_columns"].items())
                ),
                "group_by_sources": sorted(facts["group_by_sources"]),
                "source_files": sorted(facts["source_files"]),
            }
            for table, facts in grouped.items()
        }

    def _index_targets_by_source_file(self) -> dict[str, set[str]]:
        targets = defaultdict(set)

        for edge in self._raw_edges:
            target = self._edge_target_table(edge)
            if not target:
                continue
            source_file = _source_file_key(edge.get("source_file", ""))
            if source_file:
                targets[source_file].add(target)

        for edge in self._raw_indirect_edges:
            target = _short_table_name(edge.get("target_table", ""))
            if not target:
                continue
            source_file = _source_file_key(edge.get("source_file", ""))
            if source_file:
                targets[source_file].add(target)

        return dict(targets)

    @staticmethod
    def _condition_target_table(edge: dict) -> str:
        target = edge.get("target")
        if isinstance(target, dict):
            if target.get("type") == "table":
                return str(target.get("id") or "")
            if target.get("type") == "column":
                return _table_from_node(str(target.get("id") or ""))
            return ""
        return str(edge.get("target_table") or "")

    @staticmethod
    def _condition_source(edge: dict) -> str:
        source = edge.get("source")
        if isinstance(source, dict):
            return str(source.get("id") or "")
        return str(source or "")

    @staticmethod
    def _edge_target_table(edge: dict) -> str:
        target = edge.get("target")
        if isinstance(target, dict):
            target_type = target.get("type")
            target_id = str(target.get("id") or "")
            if target_type == "table":
                return _short_table_name(target_id)
            if target_type == "column":
                return _short_table_name(_table_from_node(target_id))
            return ""
        return _short_table_name(_table_from_node(str(target or "")))
