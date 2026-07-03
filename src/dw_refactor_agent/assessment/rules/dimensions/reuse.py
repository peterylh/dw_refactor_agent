"""Reusability dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.reuse import (
    ReuseDownstreamReachesTargetRule,
)
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import (
    REUSABILITY_RULES,
    REUSE_FULL_SCORE_AT,
)


def score_reusability(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    rules = selected_rules(REUSABILITY_RULES, rule_selection)
    rule = ReuseDownstreamReachesTargetRule()
    if not rule.is_enabled(rule_selection):
        return finalize_dimension(
            dimension="reuse",
            score=100.0,
            checks=[],
            rules=rules,
            summary={
                "avg_reuse_count": 0.0,
                "distribution": dict(high=0, medium=0, none=0),
                "target_downstream_count": REUSE_FULL_SCORE_AT,
            },
        )

    tables = context.tables
    downstream_map = context.downstream
    middle = [t for t in tables if t["layer"] in ("DWD", "DWS", "DIM")]
    table_names = scoped_names(scope, "tables")
    if table_names is not None:
        middle = [t for t in middle if t["name"] in table_names]

    scores = []
    downstream_counts = []
    for table in middle:
        name = table["name"]
        count = len(downstream_map.get(name, set()))
        score = min(100, count / REUSE_FULL_SCORE_AT * 100)
        scores.append(round(score, 1))
        downstream_counts.append(count)
    checks = RuleRunner(rule_selection).run(
        "table",
        "table",
        middle,
        {"downstream": downstream_map},
        dimension="reuse",
    )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    avg_reuse = (
        round(sum(downstream_counts) / len(downstream_counts), 2)
        if downstream_counts
        else 0.0
    )

    dist = dict(
        high=sum(
            1 for count in downstream_counts if count >= REUSE_FULL_SCORE_AT
        ),
        medium=sum(
            1
            for count in downstream_counts
            if 1 <= count < REUSE_FULL_SCORE_AT
        ),
        none=sum(1 for count in downstream_counts if count == 0),
    )

    return finalize_dimension(
        dimension="reuse",
        score=avg_score,
        checks=checks,
        rules=rules,
        summary={
            "avg_reuse_count": avg_reuse,
            "distribution": dist,
            "target_downstream_count": REUSE_FULL_SCORE_AT,
        },
    )
