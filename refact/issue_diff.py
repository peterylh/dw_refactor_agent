"""Issue diff helpers for refactor run assessments."""

from __future__ import annotations

from pathlib import Path


def _scope_name(name: str) -> str:
    value = str(name or "").replace("\\", "/").strip()
    stem = Path(value).stem
    if stem.endswith("_full_refresh"):
        stem = stem[: -len("_full_refresh")]
    return stem or value


def _target_table_name(target: dict) -> str:
    name = str(target.get("name") or "").strip()
    target_type = str(target.get("type") or "").strip()
    if target_type in {"column", "metric"} and "." in name:
        return name.split(".", 1)[0]
    if target_type == "file":
        return _scope_name(name)
    return name


def _issue_in_scope(issue: dict, dimension_scope: dict | None) -> bool:
    if not dimension_scope or dimension_scope.get("mode") != "scoped":
        return True

    target = issue.get("target") or {}
    target_type = str(target.get("type") or "").strip()
    target_name = _target_table_name(target)
    table_names = set(dimension_scope.get("tables") or [])
    task_names = set(dimension_scope.get("tasks") or [])

    if target_type == "task":
        return target_name in task_names
    if target_type == "file":
        return target_name in table_names or target_name in task_names
    if target_type in {"table", "column", "metric"}:
        return target_name in table_names
    return target_name in table_names or target_name in task_names


def _dimension_scope(scope_plan: dict | None, dimension: str) -> dict | None:
    if not scope_plan:
        return None
    return (scope_plan.get("dimensions") or {}).get(dimension)


def _issues_by_fingerprint(
    assess_result: dict,
    scope_plan: dict | None = None,
) -> dict:
    issues = {}
    for dimension_name, dimension in (
        assess_result.get("dimensions") or {}
    ).items():
        dimension_scope = _dimension_scope(scope_plan, dimension_name)
        for issue in dimension.get("issues") or []:
            if not _issue_in_scope(issue, dimension_scope):
                continue
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


def diff_assess_results(
    baseline: dict,
    current: dict,
    scope_plan: dict | None = None,
) -> dict:
    """Compare two assess results by issue fingerprint."""
    baseline_issues = _issues_by_fingerprint(baseline, scope_plan)
    current_issues = _issues_by_fingerprint(current, scope_plan)
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
