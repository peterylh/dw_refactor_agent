"""Reusability rule definitions."""

from __future__ import annotations

from assess.result_model import (
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    make_check,
)
from assess.rules.engine.base import AssessRule
from assess.scoring.config import REUSE_FULL_SCORE_AT

# ============================================================
# 复用度评分
# ============================================================


class ReuseDownstreamReachesTargetRule(AssessRule):
    rule_id = "REUSE_DOWNSTREAM_REACHES_TARGET"
    dimension = "reuse"
    domain = "table"
    target = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict:
        downstream_count = len(
            rule_context["downstream"].get(target["name"], set())
        )
        issue = {}
        if downstream_count == 0:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "中间层表无下游复用",
                "message": "中间层表无下游引用",
            }
        elif downstream_count < REUSE_FULL_SCORE_AT:
            issue = {
                "severity": SEVERITY_LOW,
                "title": "中间层表复用不足",
                "message": (
                    f"下游引用数={downstream_count}，"
                    f"低于目标{REUSE_FULL_SCORE_AT}"
                ),
            }
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=target["name"],
            passed=downstream_count >= REUSE_FULL_SCORE_AT,
            expected=f"下游引用数 >= {REUSE_FULL_SCORE_AT}",
            actual=f"下游引用数 = {downstream_count}",
            evidence={
                "layer": target["layer"],
                "downstream_count": downstream_count,
            },
            message=issue.get("message", ""),
            issue=issue or None,
        )
