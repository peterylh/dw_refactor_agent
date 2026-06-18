"""Lineage depth rule definitions."""

from __future__ import annotations

from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    make_check,
)
from assess.rules.engine.base import AssessRule
from assess.scoring.config import (
    MIDDLE_DEPTH_FALLBACK,
    MIDDLE_DEPTH_SCORE,
)

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


class DepthMiddleLayerIsOptimalRule(AssessRule):
    rule_id = "DEPTH_MIDDLE_LAYER_IS_OPTIMAL"
    dimension = "depth"
    domain = "table"
    target = "table"

    def evaluate(self, target: dict, facts: dict) -> dict:
        table_name = target["name"]
        depth = _max_middle_depth(
            table_name,
            facts["upstream"],
            facts["table_layers"],
        )
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
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=depth == 2,
            expected="最大中间层深度 = 2",
            actual=f"最大中间层深度 = {depth}",
            evidence={"max_middle_depth": depth},
            message=issue.get("message", ""),
            issue=issue or None,
        )
