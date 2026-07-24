"""Lineage depth dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.depth import (
    DepthMiddleLayerIsOptimalRule,
    _depth_to_score,
    _max_middle_depth,
)
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import LINEAGE_DEPTH_RULES


def score_lineage_depth(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
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

    table_names = scoped_names(scope, "tables")
    eligible_names = [
        table["name"]
        for table in tables
        if (context.operational_layer(table["name"]) or table.get("layer"))
        == "ADS"
        and (table_names is None or table["name"] in table_names)
    ]
    coverage = context.semantic_coverage(
        eligible_names,
        ("classification",),
    )
    assessed_names = set(coverage.assessed_names)
    # 不按表名推断缺失层级；models/lineage 中没有声明的表按 OTHER 处理。
    ads = [
        table
        for table in tables
        if table.get("layer") == "ADS" and table["name"] in assessed_names
    ]
    if table_names is not None:
        ads = [t for t in ads if t["name"] in table_names]

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
    effective_score = (
        round(sum(scores) / len(coverage.eligible_names), 1)
        if coverage.eligible_names
        else avg_score
    )
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
        coverage=coverage.as_dict(),
        effective_score=effective_score,
    )
