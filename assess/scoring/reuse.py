"""Reusability scoring dimension."""

from assess.assessment_context import AssessmentContext
from assess.result_model import (
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    finalize_dimension,
    make_check,
)
from assess.scoring.config import REUSABILITY_RULES, REUSE_FULL_SCORE_AT

# ============================================================
# 复用度评分
# ============================================================


def score_reusability(context: AssessmentContext) -> dict:
    tables = context.tables
    downstream_map = context.downstream
    middle = [t for t in tables if t["layer"] in ("DWD", "DWS", "DIM")]

    checks = []
    scores = []
    downstream_counts = []
    for t in middle:
        name = t["name"]
        cnt = len(downstream_map.get(name, set()))
        score = min(100, cnt / REUSE_FULL_SCORE_AT * 100)
        scores.append(round(score, 1))
        downstream_counts.append(cnt)
        issue = {}
        if cnt == 0:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "中间层表无下游复用",
                "message": "中间层表无下游引用",
            }
        elif cnt < REUSE_FULL_SCORE_AT:
            issue = {
                "severity": SEVERITY_LOW,
                "title": "中间层表复用不足",
                "message": f"下游引用数={cnt}，低于目标{REUSE_FULL_SCORE_AT}",
            }
        checks.append(
            make_check(
                rule_id="REUSE_DOWNSTREAM_REACHES_TARGET",
                target_type="table",
                target=name,
                passed=cnt >= REUSE_FULL_SCORE_AT,
                expected=f"下游引用数 >= {REUSE_FULL_SCORE_AT}",
                actual=f"下游引用数 = {cnt}",
                evidence={
                    "layer": t["layer"],
                    "downstream_count": cnt,
                },
                message=issue.get("message", ""),
                issue=issue or None,
            )
        )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    avg_reuse = (
        round(sum(downstream_counts) / len(downstream_counts), 2)
        if downstream_counts
        else 0.0
    )

    dist = dict(
        high=sum(1 for cnt in downstream_counts if cnt >= REUSE_FULL_SCORE_AT),
        medium=sum(
            1 for cnt in downstream_counts if 1 <= cnt < REUSE_FULL_SCORE_AT
        ),
        none=sum(1 for cnt in downstream_counts if cnt == 0),
    )

    return finalize_dimension(
        dimension="reuse",
        score=avg_score,
        checks=checks,
        rules=REUSABILITY_RULES,
        summary={
            "avg_reuse_count": avg_reuse,
            "distribution": dist,
            "target_downstream_count": REUSE_FULL_SCORE_AT,
        },
    )
