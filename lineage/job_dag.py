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

import json
from collections import defaultdict, deque


class JobDAG:
    """基于血缘边构建的作业 DAG, 支持序列化持久化."""

    def __init__(self, edges: list = None):
        self._edges = edges or []
        self._deps: dict[str, set[str]] = {}   # source → [targets]
        self._rev: dict[str, set[str]] = {}    # target → [sources]
        self._build()

    # ── 图构建 ──

    def _build(self):
        deps = defaultdict(set)
        rev = defaultdict(set)
        for e in self._edges:
            src = e["source"].rsplit(".", 1)[0]
            tgt = e["target"].rsplit(".", 1)[0]
            if src != tgt:
                deps[src].add(tgt)
                rev[tgt].add(src)
        self._deps = dict(deps)
        self._rev = dict(rev)

    def add_edge(self, source: str, target: str):
        """动态添加一条边, source/target 为简单表名."""
        if source != target:
            self._deps.setdefault(source, set()).add(target)
            self._rev.setdefault(target, set()).add(source)
            self._edges.append({"source": source, "target": target})

    # ── 遍历 ──

    def bfs_downstream(self, seeds: set) -> set:
        """BFS 下游追踪, 返回 seeds 下游的所有表 (不含 seeds)."""
        visited = set(seeds)
        q = deque(seeds)
        while q:
            t = q.popleft()
            for dt in self._deps.get(t, set()):
                if dt not in visited:
                    visited.add(dt)
                    q.append(dt)
        return visited - seeds

    def topological_sort(self, jobs_set: set) -> list:
        """Kahn 拓扑排序.  jobs_set 内存在环时抛出 ValueError."""
        in_degree = {j: 0 for j in jobs_set}
        adj = defaultdict(set)

        for src, targets in self._deps.items():
            if src not in jobs_set:
                continue
            for tgt in targets:
                if tgt in jobs_set:
                    adj[src].add(tgt)
                    in_degree[tgt] = in_degree.get(tgt, 0) + 1

        queue = deque([j for j, d in in_degree.items() if d == 0])
        result = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj.get(node, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(jobs_set):
            cycle = set(jobs_set) - set(result)
            raise ValueError(f"Detected cycle among jobs: {sorted(cycle)}")

        return result

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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
