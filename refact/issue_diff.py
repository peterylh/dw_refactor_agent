"""Issue diff helpers for refactor run assessments."""

from __future__ import annotations

import re
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
    if target_type in {"file", "task"}:
        return _scope_name(name)
    return name


def _short_name(name: str) -> str:
    return str(name or "").strip().strip("`").split(".")[-1]


def _rename_mapping(change_analysis: dict | None) -> dict[str, str]:
    if not change_analysis:
        return {}

    mapping = {}
    for old_name, new_name in (
        change_analysis.get("rename_mapping") or {}
    ).items():
        old_short = _short_name(old_name)
        new_short = _short_name(new_name)
        if old_short and new_short:
            mapping[old_short] = new_short

    for rename in change_analysis.get("renames") or []:
        old_short = _short_name(rename.get("old") or rename.get("old_name"))
        new_short = _short_name(rename.get("new") or rename.get("new_name"))
        if old_short and new_short:
            mapping[old_short] = new_short

    for change in change_analysis.get("ddl_changes") or []:
        if change.get("change_type") != "RENAME":
            continue
        old_short = _short_name(change.get("old_name"))
        new_short = _short_name(change.get("new_name"))
        if old_short and new_short:
            mapping[old_short] = new_short
    return mapping


def _map_identifier_text(value: str, rename_mapping: dict[str, str]) -> str:
    mapped = str(value or "")
    for old_name, new_name in sorted(
        rename_mapping.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(old_name)}(?![A-Za-z0-9_])"
        )
        mapped = pattern.sub(new_name, mapped)
    return mapped


def _map_scope_name(name: str, rename_mapping: dict[str, str]) -> str:
    return rename_mapping.get(name, name)


def _issue_in_scope(
    issue: dict,
    dimension_scope: dict | None,
    rename_mapping: dict[str, str] | None = None,
) -> bool:
    if not dimension_scope or dimension_scope.get("mode") != "scoped":
        return True

    rename_mapping = rename_mapping or {}
    target = issue.get("target") or {}
    target_type = str(target.get("type") or "").strip()
    target_name = _map_scope_name(
        _target_table_name(target),
        rename_mapping,
    )
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
    rename_mapping: dict[str, str] | None = None,
) -> dict:
    rename_mapping = rename_mapping or {}
    issues = {}
    for dimension_name, dimension in (
        assess_result.get("dimensions") or {}
    ).items():
        dimension_scope = _dimension_scope(scope_plan, dimension_name)
        for issue in dimension.get("issues") or []:
            if not _issue_in_scope(
                issue,
                dimension_scope,
                rename_mapping=rename_mapping,
            ):
                continue
            fingerprint = str(issue.get("fingerprint") or "").strip()
            if fingerprint:
                fingerprint = _map_identifier_text(
                    fingerprint,
                    rename_mapping,
                )
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
    change_analysis: dict | None = None,
) -> dict:
    """Compare two assess results by issue fingerprint."""
    rename_mapping = _rename_mapping(change_analysis)
    baseline_issues = _issues_by_fingerprint(
        baseline,
        scope_plan,
        rename_mapping=rename_mapping,
    )
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
