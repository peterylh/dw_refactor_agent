"""Issue diff helpers for refactor run assessments."""

from __future__ import annotations


def _issues_by_fingerprint(assess_result: dict) -> dict:
    issues = {}
    for dimension in (assess_result.get("dimensions") or {}).values():
        for issue in dimension.get("issues") or []:
            fingerprint = str(issue.get("fingerprint") or "").strip()
            if fingerprint:
                issues[fingerprint] = issue
    return issues


def _score_summary(assess_result: dict) -> dict:
    return {
        "overall_score": assess_result.get("overall_score"),
        "dimensions": {
            name: {"score": value.get("score")}
            for name, value in (assess_result.get("dimensions") or {}).items()
        },
    }


def diff_assess_results(baseline: dict, current: dict) -> dict:
    """Compare two assess results by issue fingerprint."""
    baseline_issues = _issues_by_fingerprint(baseline)
    current_issues = _issues_by_fingerprint(current)
    baseline_keys = set(baseline_issues)
    current_keys = set(current_issues)

    fixed = sorted(baseline_keys - current_keys)
    remaining = sorted(baseline_keys & current_keys)
    new = sorted(current_keys - baseline_keys)

    return {
        "summary": {
            "baseline_issue_count": len(baseline_issues),
            "current_issue_count": len(current_issues),
            "fixed_count": len(fixed),
            "remaining_count": len(remaining),
            "new_count": len(new),
        },
        "fixed_issues": [baseline_issues[key] for key in fixed],
        "remaining_issues": [current_issues[key] for key in remaining],
        "new_issues": [current_issues[key] for key in new],
        "scope_score": _score_summary(current),
    }
