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
from lineage.asset_graph import build_asset_table_graph


class JobDAG:
    """基于血缘边构建的作业 DAG, 支持序列化持久化."""

    def __init__(self, edges: list | None = None):
        self._edges = edges or []
        self._deps: dict[str, set[str]] = {}
        self._rev: dict[str, set[str]] = {}
        self._build()

    # ── 图构建 ──

    def _build(self):
        deps = defaultdict(set)
        rev = defaultdict(set)
        for e in self._edges:
            src = self._edge_table(e.get("source"))
            tgt = self._edge_table(e.get("target"))
            if src and tgt and src != tgt:
                deps[src].add(tgt)
                rev[tgt].add(src)
        self._deps = dict(deps)
        self._rev = dict(rev)

    @staticmethod
    def _edge_table(ref) -> str:
        if isinstance(ref, dict):
            if ref.get("type") == "column":
                return str(ref.get("id") or "").rsplit(".", 1)[0]
            if ref.get("type") == "table":
                return str(ref.get("id") or "")
            return ""
        return str(ref or "").rsplit(".", 1)[0]

    def add_edge(self, source: str, target: str):
        if source != target:
            self._deps.setdefault(source, set()).add(target)
            self._rev.setdefault(target, set()).add(source)
            self._edges.append({"source": source, "target": target})

    # ── 遍历 ──

    def bfs_downstream(self, seeds: set) -> set:
        visited = set(seeds)
        q = deque(seeds)
        while q:
            t = q.popleft()
            for dt in self._deps.get(t, set()):
                if dt not in visited:
                    visited.add(dt)
                    q.append(dt)
        return visited - seeds

    def get_downstream(self, job: str) -> set[str]:
        return self._deps.get(job, set())

    def compute_in_degree(
        self, jobs_set: set
    ) -> tuple[dict[str, int], dict[str, list[str]]]:
        in_degree = dict.fromkeys(jobs_set, 0)
        adj: dict[str, list[str]] = {j: [] for j in jobs_set}
        for src, targets in self._deps.items():
            if src not in jobs_set:
                continue
            for tgt in targets:
                if tgt in jobs_set:
                    adj[src].append(tgt)
                    in_degree[tgt] = in_degree.get(tgt, 0) + 1
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
            "deps": {k: sorted(v) for k, v in self._deps.items()},
            "rev": {k: sorted(v) for k, v in self._rev.items()},
        }

    @classmethod
    def from_dict(cls, data: dict):
        dag = cls.__new__(cls)
        dag._edges = list(data.get("edges", []))
        dag._deps = {k: set(v) for k, v in data.get("deps", {}).items()}
        dag._rev = {k: set(v) for k, v in data.get("rev", {}).items()}
        return dag

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
    return JobDAG(table_edges)
