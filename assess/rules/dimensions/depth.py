"""Lineage depth dimension execution."""

from __future__ import annotations

from assess.assessment_context import AssessmentContext
from assess.result_model import finalize_dimension
from assess.rules.definitions.depth import (
    DepthMiddleLayerIsOptimalRule,
    _depth_to_score,
    _max_middle_depth,
)
from assess.rules.engine.filtering import selected_rules
from assess.rules.engine.runner import RuleRunner
from assess.rules.engine.selection import RuleSelection
from assess.scoring.config import LINEAGE_DEPTH_RULES


def score_lineage_depth(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
) -> dict:
    rules = selected_rules(LINEAGE_DEPTH_RULES, rule_selection)
    rule = DepthMiddleLayerIsOptimalRule()
    if not rule.is_enabled(rule_selection):
        return finalize_dimension(
            dimension="depth",
            score=100.0,
            checks=[],
            rules=rules,
            summary={
                "avg_middle_depth": 0.0,
                "ideal_middle_depth": 2,
            },
        )

    tables = context.tables
    table_layers = context.table_layers
    upstream = context.upstream

    # 不按表名推断缺失层级；models/lineage 中没有声明的表按 OTHER 处理。
    ads = [t for t in tables if t["layer"] == "ADS"]

    scores = []
    depths = []
    for table in ads:
        name = table["name"]
        depth = _max_middle_depth(name, upstream, table_layers)
        score = _depth_to_score(depth)
        scores.append(score)
        depths.append(depth)
    checks = RuleRunner(rule_selection).run(
        "table",
        "table",
        ads,
        {
            "upstream": upstream,
            "table_layers": table_layers,
        },
        dimension="depth",
    )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 100.0
    avg_depth = round(sum(depths) / len(depths), 2) if depths else 0.0

    return finalize_dimension(
        dimension="depth",
        score=avg_score,
        checks=checks,
        rules=rules,
        summary={
            "avg_middle_depth": avg_depth,
            "ideal_middle_depth": 2,
        },
    )
