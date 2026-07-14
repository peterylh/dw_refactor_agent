#!/usr/bin/env python3
"""
作业 DAG 生成: 基于显式 Job 输入输出构建可序列化的有向无环图,
支持拓扑排序与下游追踪, 供重构验证和正常运行共用。

用法:
    from dw_refactor_agent.lineage.job_dag import job_dag_from_lineage

    dag = job_dag_from_lineage(lineage_data)
    order = dag.topological_sort({"prepare_sales", "build_report"})
    dag.save("warehouses/shop/artifacts/lineage/job_dag.json")

    dag2 = JobDAG.load("warehouses/shop/artifacts/lineage/job_dag.json")
    downstream = dag2.bfs_downstream({"dwd_order_detail"})
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.lineage.asset_graph import (
    build_asset_self_edges,
    build_asset_table_graph,
)
from dw_refactor_agent.lineage.contract import (
    FORMAT_VERSION,
    validate_job_dag_v2,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    split_column_ref,
)
from dw_refactor_agent.lineage.job_lineage import resolve_job_dependencies


class JobDAG:
    """基于血缘边构建的作业 DAG, 支持序列化持久化."""

    def __init__(
        self,
        edges: list | None = None,
        self_edges: list | None = None,
    ):
        self._format_version = 1
        self._jobs: list[str] = []
        self._data_dependencies: list[dict] = []
        self._edges = edges or []
        self._provided_self_edges = list(self_edges or [])
        self._self_edges: list[dict] = []
        self._deps: dict[str, set[str]] = {}
        self._rev: dict[str, set[str]] = {}
        self._node_by_key: dict[str, str] = {}
        self._build()

    @classmethod
    def from_jobs(
        cls,
        jobs: list[str],
        data_dependencies: list[dict],
    ) -> "JobDAG":
        """Build a version 2 DAG from explicit Jobs and dataset evidence."""
        dag = cls.__new__(cls)
        dag._format_version = FORMAT_VERSION
        dag._jobs = sorted(jobs, key=identifier_match_key)
        dag._data_dependencies = [
            {
                "upstream_job": dependency["upstream_job"],
                "downstream_job": dependency["downstream_job"],
                "datasets": list(dependency["datasets"]),
            }
            for dependency in data_dependencies
        ]
        dag._edges = []
        dag._provided_self_edges = []
        dag._self_edges = []
        dag._deps = {job: set() for job in dag._jobs}
        dag._rev = {job: set() for job in dag._jobs}
        dag._node_by_key = {}
        for job in dag._jobs:
            cls._remember_node(dag._node_by_key, job)
        for dependency in dag._data_dependencies:
            upstream = dag._resolve_node(dependency["upstream_job"])
            downstream = dag._resolve_node(dependency["downstream_job"])
            dag._deps[upstream].add(downstream)
            dag._rev[downstream].add(upstream)
        validate_job_dag_v2(dag.to_dict())
        return dag

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
        for job in self._jobs:
            self._remember_node(node_by_key, job)
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

    @property
    def format_version(self) -> int:
        return self._format_version

    @property
    def jobs(self) -> list[str]:
        return list(self._jobs)

    @property
    def data_dependencies(self) -> list[dict]:
        return [
            {
                "upstream_job": dependency["upstream_job"],
                "downstream_job": dependency["downstream_job"],
                "datasets": list(dependency["datasets"]),
            }
            for dependency in self._data_dependencies
        ]

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

        queue = deque(
            sorted(
                (j for j, degree in in_degree.items() if degree == 0),
                key=self._node_key,
            )
        )
        result = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in sorted(adj.get(node, []), key=self._node_key):
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
            current = sorted(
                (j for j in remaining if in_degree.get(j, 0) == 0),
                key=self._node_key,
            )
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
        if self._format_version == FORMAT_VERSION:
            return {
                "format_version": FORMAT_VERSION,
                "jobs": list(self._jobs),
                "data_dependencies": self.data_dependencies,
                "deps": {
                    job: sorted(
                        self._deps.get(job, set()), key=identifier_match_key
                    )
                    for job in self._jobs
                },
                "rev": {
                    job: sorted(
                        self._rev.get(job, set()), key=identifier_match_key
                    )
                    for job in self._jobs
                },
            }
        return {
            "edges": list(self._edges),
            "self_edges": self.self_edges,
            "deps": {k: sorted(v) for k, v in self._deps.items()},
            "rev": {k: sorted(v) for k, v in self._rev.items()},
        }

    @classmethod
    def from_dict(cls, data: dict):
        if "format_version" in data:
            format_version = data["format_version"]
            if type(format_version) is not int or format_version not in {1, 2}:
                raise ValueError(
                    "job DAG format_version must be integer 1 or 2; "
                    f"received {format_version!r}"
                )
        if data.get("format_version") == FORMAT_VERSION:
            validate_job_dag_v2(data)
            return cls.from_jobs(
                list(data["jobs"]),
                list(data["data_dependencies"]),
            )
        dag = cls.__new__(cls)
        dag._format_version = 1
        dag._jobs = []
        dag._data_dependencies = []
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
        data = self.to_dict()
        if self._format_version == FORMAT_VERSION:
            validate_job_dag_v2(data)
        with open(path, "w", encoding=TEXT_ENCODING) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding=TEXT_ENCODING) as f:
            return cls.from_dict(json.load(f))


def asset_job_dag_from_lineage(lineage_data: dict) -> JobDAG:
    """Build the legacy table-node compatibility DAG from lineage edges."""
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


def job_dag_from_lineage(lineage_data: dict) -> JobDAG:
    """Build a Job DAG from explicit version 2 Job dataset facts.

    Legacy lineage snapshots continue to use the table-based compatibility
    graph because they do not contain reliable Job input/output facts.
    """
    data = lineage_data or {}
    if data.get("format_version") != FORMAT_VERSION:
        return asset_job_dag_from_lineage(data)

    validate_lineage_v2(data)
    dependencies, _diagnostics = resolve_job_dependencies(
        data["jobs"],
        data["tables"],
    )
    return JobDAG.from_jobs(
        [job["name"] for job in data["jobs"]],
        dependencies,
    )
