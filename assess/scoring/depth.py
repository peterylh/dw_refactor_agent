"""Lineage depth scoring dimension."""

from __future__ import annotations

from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    finalize_dimension,
    make_check,
)
from assess.scoring.config import (
    LINEAGE_DEPTH_RULES,
    MIDDLE_DEPTH_FALLBACK,
    MIDDLE_DEPTH_SCORE,
)
from lineage.table_graph import build_table_graph, build_table_layer_map

# ============================================================
# 链路长度评分 (中间层深度)
# ============================================================


def _max_middle_depth(
    table: str,
    upstream_map: dict,
    table_layers: dict,
    memo: dict = None,
    visiting: set = None,
) -> int:
    if memo is None:
        memo = {}
    if visiting is None:
        visiting = set()

    if table in memo:
        return memo[table]
    if table in visiting:
        return 0

    visiting.add(table)

    layer = table_layers.get(table, "OTHER")
    contribution = 1 if layer in ("DWD", "DWS", "DIM") else 0

    parents = upstream_map.get(table, set())
    if not parents:
        result = contribution
    else:
        max_sub = 0
        for p in parents:
            max_sub = max(
                max_sub,
                _max_middle_depth(
                    p, upstream_map, table_layers, memo, visiting
                ),
            )
        result = contribution + max_sub

    visiting.remove(table)
    memo[table] = result
    return result


def _depth_to_score(depth: int) -> int:
    return MIDDLE_DEPTH_SCORE.get(depth, MIDDLE_DEPTH_FALLBACK)


def score_lineage_depth(
    tables: list,
    edges: list,
    indirect_edges: list,
    *,
    upstream_map: dict | None = None,
    table_layers: dict | None = None,
) -> dict:
    table_layers = (
        table_layers
        if table_layers is not None
        else build_table_layer_map(tables)
    )
    upstream = (
        upstream_map
        if upstream_map is not None
        else build_table_graph(edges, indirect_edges)[0]
    )

    # 不按表名推断缺失层级；models/lineage 中没有声明的表按 OTHER 处理。

    ads = [t for t in tables if t["layer"] == "ADS"]

    checks = []
    scores = []
    depths = []
    for t in ads:
        name = t["name"]
        depth = _max_middle_depth(name, upstream, table_layers)
        score = _depth_to_score(depth)
        scores.append(score)
        depths.append(depth)
        issue = {}
        if depth == 0:
            issue = {
                "severity": SEVERITY_HIGH,
                "title": "ADS链路缺少中间层",
                "message": "ADS到ODS链路中未发现DWD/DWS/DIM中间层",
            }
        elif depth == 1:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "ADS链路中间层不足",
                "message": "ADS链路只有一层中间层",
            }
        elif depth >= 3:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "ADS链路中间层过长",
                "message": f"ADS链路中间层深度={depth}",
            }
        checks.append(
            make_check(
                rule_id="DEPTH_MIDDLE_LAYER_IS_OPTIMAL",
                target_type="table",
                target=name,
                passed=depth == 2,
                expected="最大中间层深度 = 2",
                actual=f"最大中间层深度 = {depth}",
                evidence={"max_middle_depth": depth},
                message=issue.get("message", ""),
                issue=issue or None,
            )
        )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 100.0
    avg_depth = round(sum(depths) / len(depths), 2) if depths else 0.0

    return finalize_dimension(
        dimension="depth",
        score=avg_score,
        checks=checks,
        rules=LINEAGE_DEPTH_RULES,
        summary={
            "avg_middle_depth": avg_depth,
            "ideal_middle_depth": 2,
        },
    )
