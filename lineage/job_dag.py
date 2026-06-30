#!/usr/bin/env python3
"""
作业 DAG 生成: 基于血缘边构建可序列化的有向无环图,
支持拓扑排序与下游追踪, 供重构验证和正常运行共用。

用法:
    from lineage.job_dag import JobDAG

    dag = JobDAG(lineage_data["edges"])
    order = dag.topological_sort({"dwd_order_detail", "dws_store_sales", "ads_sales"})
    dag.save("lineage/job_dag.json")

    dag2 = JobDAG.load("lineage/job_dag.json")
    downstream = dag2.bfs_downstream({"dwd_order_detail"})
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import TEXT_ENCODING
from lineage.asset_graph import build_asset_self_edges, build_asset_table_graph
from lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    split_column_ref,
)


class JobDAG:
    """基于血缘边构建的作业 DAG, 支持序列化持久化."""

    def __init__(
        self,
        edges: list | None = None,
        self_edges: list | None = None,
    ):
        self._edges = edges or []
        self._provided_self_edges = list(self_edges or [])
        self._self_edges: list[dict] = []
        self._deps: dict[str, set[str]] = {}
        self._rev: dict[str, set[str]] = {}
        self._node_by_key: dict[str, str] = {}
        self._build()

    # ── 图构建 ──

    def _build(self):
        deps = defaultdict(set)
        rev = defaultdict(set)
        node_by_key = {}
        self_edges = []
        for e in self._edges:
            src = self._remember_node(
                node_by_key, self._edge_table(e.get("source"))
            )
            tgt = self._remember_node(
                node_by_key, self._edge_table(e.get("target"))
            )
            if not src or not tgt:
                continue
            if self._node_key(src) == self._node_key(tgt):
                self_edges.append(self._self_edge_record(e, src, tgt))
            else:
                deps[src].add(tgt)
                rev[tgt].add(src)
        self_edges.extend(self._provided_self_edges)
        self._deps = dict(deps)
        self._rev = dict(rev)
        self._node_by_key = node_by_key
        self._self_edges = self._dedupe_self_edges(self_edges)

    @staticmethod
    def _edge_table(ref) -> str:
        if isinstance(ref, dict):
            if ref.get("type") == "column":
                return JobDAG._edge_table(ref.get("id", ""))
            if ref.get("type") == "table":
                return canonical_qualified_identifier(ref.get("id"))
            return ""
        split_ref = split_column_ref(ref)
        if split_ref is not None:
            return split_ref[0]
        return canonical_qualified_identifier(ref)

    @staticmethod
    def _node_key(node: str) -> str:
        return identifier_match_key(node)

    @classmethod
    def _remember_node(cls, node_by_key: dict, node: str) -> str:
        node_key = cls._node_key(node)
        if not node_key:
            return ""
        return node_by_key.setdefault(node_key, node)

    @staticmethod
    def _self_edge_record(edge: dict, source: str, target: str) -> dict:
        record = {
            "table": source,
            "source_table": source,
            "target_table": target,
        }
        if isinstance(edge, dict):
            record["source"] = edge.get("source")
            record["target"] = edge.get("target")
            for key in (
                "relation_type",
                "transformation_type",
                "expression",
                "source_file",
            ):
                if key in edge:
                    record[key] = edge.get(key)
        else:
            record["source"] = source
            record["target"] = target
        return record

    @staticmethod
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

    def _resolve_node(self, node: str) -> str:
        return self._node_by_key.get(self._node_key(node), node)

    def _rebuild_node_index(self) -> None:
        node_by_key = {}
        for source, targets in self._deps.items():
            self._remember_node(node_by_key, source)
            for target in targets:
                self._remember_node(node_by_key, target)
        for target, sources in self._rev.items():
            self._remember_node(node_by_key, target)
            for source in sources:
                self._remember_node(node_by_key, source)
        self._node_by_key = node_by_key

    def add_edge(self, source: str, target: str):
        source = self._remember_node(self._node_by_key, source)
        target = self._remember_node(self._node_by_key, target)
        if (
            source
            and target
            and self._node_key(source) != self._node_key(target)
        ):
            self._deps.setdefault(source, set()).add(target)
            self._rev.setdefault(target, set()).add(source)
            self._edges.append({"source": source, "target": target})
        elif source and target:
            self._self_edges = self._dedupe_self_edges(
                [
                    *self._self_edges,
                    self._self_edge_record(
                        {"source": source, "target": target},
                        source,
                        target,
                    ),
                ]
            )

    @property
    def self_edges(self) -> list[dict]:
        return [dict(edge) for edge in self._self_edges]

    # ── 遍历 ──

    def bfs_downstream(self, seeds: set) -> set:
        seed_keys = {
            self._node_key(seed) for seed in seeds if self._node_key(seed)
        }
        visited_keys = set(seed_keys)
        visited_nodes = {}
        q = deque(self._resolve_node(seed) for seed in seeds)
        while q:
            t = q.popleft()
            t = self._resolve_node(t)
            for dt in self._deps.get(t, set()):
                dt_key = self._node_key(dt)
                if dt_key not in visited_keys:
                    visited_keys.add(dt_key)
                    visited_nodes[dt_key] = dt
                    q.append(dt)
        return {
            node
            for node_key, node in visited_nodes.items()
            if node_key not in seed_keys
        }

    def get_downstream(self, job: str) -> set[str]:
        return self._deps.get(self._resolve_node(job), set())

    def compute_in_degree(
        self, jobs_set: set
    ) -> tuple[dict[str, int], dict[str, list[str]]]:
        jobs_by_key = {
            self._node_key(job): job for job in jobs_set if self._node_key(job)
        }
        in_degree = dict.fromkeys(jobs_set, 0)
        adj: dict[str, list[str]] = {j: [] for j in jobs_set}
        for src, targets in self._deps.items():
            source_job = jobs_by_key.get(self._node_key(src))
            if source_job is None:
                continue
            for tgt in targets:
                target_job = jobs_by_key.get(self._node_key(tgt))
                if target_job is not None:
                    adj[source_job].append(target_job)
                    in_degree[target_job] = in_degree.get(target_job, 0) + 1
        return in_degree, adj

    def topological_sort(self, jobs_set: set) -> list:
        in_degree, adj = self.compute_in_degree(jobs_set)

        queue = deque([j for j, d in in_degree.items() if d == 0])
        result = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(jobs_set):
            cycle = set(jobs_set) - set(result)
            raise ValueError(f"Detected cycle among jobs: {sorted(cycle)}")

        return result

    def topological_layers(self, jobs_set: set) -> list[list[str]]:
        in_degree, adj = self.compute_in_degree(jobs_set)

        layers = []
        remaining = set(jobs_set)
        while remaining:
            current = [j for j in remaining if in_degree.get(j, 0) == 0]
            if not current:
                raise ValueError(
                    f"Detected cycle among jobs: {sorted(remaining)}"
                )
            layers.append(current)
            for node in current:
                for neighbor in adj.get(node, []):
                    in_degree[neighbor] -= 1
                remaining.remove(node)

        return layers

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {
            "edges": list(self._edges),
            "self_edges": self.self_edges,
            "deps": {k: sorted(v) for k, v in self._deps.items()},
            "rev": {k: sorted(v) for k, v in self._rev.items()},
        }

    @classmethod
    def from_dict(cls, data: dict):
        dag = cls.__new__(cls)
        dag._edges = list(data.get("edges", []))
        dag._provided_self_edges = []
        dag._self_edges = cls._dedupe_self_edges(
            list(data.get("self_edges") or [])
        )
        if not dag._self_edges:
            dag._self_edges = cls._dedupe_self_edges(
                cls._self_edges_from_raw_edges(dag._edges)
            )
        dag._deps = {k: set(v) for k, v in data.get("deps", {}).items()}
        dag._rev = {k: set(v) for k, v in data.get("rev", {}).items()}
        dag._rebuild_node_index()
        return dag

    @classmethod
    def _self_edges_from_raw_edges(cls, edges: list) -> list[dict]:
        records = []
        node_by_key = {}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = cls._remember_node(
                node_by_key,
                cls._edge_table(edge.get("source")),
            )
            target = cls._remember_node(
                node_by_key,
                cls._edge_table(edge.get("target")),
            )
            if (
                source
                and target
                and cls._node_key(source) == cls._node_key(target)
            ):
                records.append(cls._self_edge_record(edge, source, target))
        return records

    def save(self, path):
        with open(path, "w", encoding=TEXT_ENCODING) as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding=TEXT_ENCODING) as f:
            return cls.from_dict(json.load(f))


def asset_job_dag_from_lineage(lineage_data: dict) -> JobDAG:
    """Build a table DAG from formal asset dependencies, bypassing transient tables."""
    _upstream, downstream = build_asset_table_graph(lineage_data or {})
    table_edges = []
    seen = set()
    for source, targets in sorted(downstream.items()):
        for target in sorted(targets):
            if not source or not target or source == target:
                continue
            key = (source, target)
            if key in seen:
                continue
            seen.add(key)
            table_edges.append({"source": source, "target": target})
    return JobDAG(
        table_edges,
        self_edges=build_asset_self_edges(lineage_data or {}),
    )
