"""Issue diff helpers for refactor run assessments."""

from __future__ import annotations

from pathlib import Path


def _canonical(value: str) -> str:
    return str(value or "").strip().casefold()


def _short_identifier(name: str) -> str:
    value = str(name or "").strip()
    return value.split(".")[-1].strip()


def _rename_value(item: dict, *keys: str) -> str:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _add_rename_pair(
    table_renames: dict[str, str],
    old_name: str,
    new_name: str,
) -> None:
    old_full = str(old_name or "").strip()
    new_full = str(new_name or "").strip()
    old_short = _short_identifier(old_full)
    new_short = _short_identifier(new_full)
    if not old_short or not new_short:
        return

    table_renames[_canonical(old_short)] = new_short
    if old_full:
        table_renames[_canonical(old_full)] = new_full or new_short


def _add_rename_items(
    table_renames: dict[str, str],
    items,
) -> None:
    if isinstance(items, dict):
        old_name = _rename_value(items, "old", "old_name", "from")
        new_name = _rename_value(items, "new", "new_name", "to")
        if old_name or new_name:
            _add_rename_pair(table_renames, old_name, new_name)
            return
        for old_name, new_name in items.items():
            _add_rename_pair(table_renames, str(old_name), str(new_name))
        return

    for item in items or []:
        if not isinstance(item, dict):
            continue
        old_name = _rename_value(item, "old", "old_name", "from")
        new_name = _rename_value(item, "new", "new_name", "to")
        _add_rename_pair(table_renames, old_name, new_name)


def _table_renames(
    *,
    change_analysis: dict | None = None,
    verification_plan: dict | None = None,
    ddl_changes: list[dict] | None = None,
    rename_mapping=None,
) -> dict[str, str]:
    table_renames: dict[str, str] = {}
    _add_rename_items(table_renames, rename_mapping)

    analysis = change_analysis or {}
    for key in (
        "renamed_tables",
        "table_renames",
        "rename_mapping",
        "renames",
    ):
        _add_rename_items(table_renames, analysis.get(key))

    lineage_diff = analysis.get("lineage_diff") or {}
    for key in (
        "renamed_tables",
        "table_renames",
        "rename_mapping",
        "renames",
    ):
        _add_rename_items(table_renames, lineage_diff.get(key))

    plan_changes = (verification_plan or {}).get("ddl_changes") or []
    for change in list(ddl_changes or []) + list(plan_changes):
        if str(change.get("change_type") or "").upper() != "RENAME":
            continue
        old_name = _rename_value(change, "old", "old_name", "from")
        new_name = _rename_value(change, "new", "new_name", "to")
        _add_rename_pair(table_renames, old_name, new_name)

    return table_renames


def _renamed_identifier(name: str, table_renames: dict[str, str]) -> str:
    value = str(name or "").strip()
    if not value:
        return value
    return table_renames.get(_canonical(value), value)


def _normalize_identifier_name(
    name: str,
    table_renames: dict[str, str],
) -> str:
    value = str(name or "").strip()
    renamed = _renamed_identifier(value, table_renames)
    if renamed != value:
        return renamed

    value_key = _canonical(value)
    for old_key, new_name in sorted(
        table_renames.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        prefix = f"{old_key}."
        if value_key.startswith(prefix):
            return f"{new_name}{value[len(old_key) :]}"
    return value


def _normalize_file_or_task_name(
    name: str,
    table_renames: dict[str, str],
) -> str:
    value = str(name or "").replace("\\", "/").strip()
    renamed = _renamed_identifier(value, table_renames)
    if renamed != value:
        return renamed
    if not value:
        return value

    parts = value.split("/")
    filename = parts[-1]
    suffix = Path(filename).suffix
    stem = Path(filename).stem
    renamed_stem = _renamed_identifier(stem, table_renames)
    if renamed_stem == stem and stem.endswith("_full_refresh"):
        base_stem = stem[: -len("_full_refresh")]
        renamed_base = _renamed_identifier(base_stem, table_renames)
        if renamed_base != base_stem:
            renamed_stem = f"{renamed_base}_full_refresh"
    if renamed_stem == stem:
        return value

    parts[-1] = f"{renamed_stem}{suffix}"
    return "/".join(parts)


def _normalize_issue_target_name(
    target_name: str,
    target_type: str,
    table_renames: dict[str, str],
) -> str:
    if target_type in {"file", "task"}:
        return _normalize_file_or_task_name(target_name, table_renames)
    return _normalize_identifier_name(target_name, table_renames)


def _normalize_discriminator(
    discriminator: str,
    table_renames: dict[str, str],
) -> str:
    value = str(discriminator or "").strip()
    if ":" not in value:
        return _normalize_identifier_name(value, table_renames)

    prefix, target_name = value.split(":", 1)
    normalized = _normalize_identifier_name(target_name, table_renames)
    normalized = _normalize_file_or_task_name(normalized, table_renames)
    return f"{prefix}:{normalized}"


def _normalized_fingerprint(
    fingerprint: str,
    table_renames: dict[str, str],
) -> str:
    value = str(fingerprint or "").strip()
    if not table_renames:
        return value

    parts = value.split("|")
    if len(parts) < 4:
        return value
    target_type = str(parts[2] or "").strip()
    parts[3] = _normalize_issue_target_name(
        parts[3],
        target_type,
        table_renames,
    )
    for index in range(4, len(parts)):
        parts[index] = _normalize_discriminator(
            parts[index],
            table_renames,
        )
    return "|".join(parts)


def _scope_name(name: str) -> str:
    value = str(name or "").replace("\\", "/").strip()
    stem = Path(value).stem
    if stem.endswith("_full_refresh"):
        stem = stem[: -len("_full_refresh")]
    return stem or value


def _target_table_name(target: dict) -> str:
    name = str(target.get("name") or "").strip()
    target_type = str(target.get("type") or "").strip()
    if target_type in {"column", "metric"}:
        qualified_name = str(target.get("qualified_name") or "").strip()
        if "." in qualified_name:
            return qualified_name.split(".", 1)[0]
        if "." in name:
            return name.split(".", 1)[0]
    if target_type in {"file", "task"}:
        return _scope_name(name)
    return name


def _scope_keys(names, table_renames: dict[str, str]) -> set[str]:
    keys = set()
    for name in names or []:
        scoped_name = _scope_name(str(name))
        keys.add(_canonical(scoped_name))
        keys.add(
            _canonical(_normalize_identifier_name(scoped_name, table_renames))
        )
        keys.add(
            _canonical(
                _normalize_file_or_task_name(scoped_name, table_renames)
            )
        )
    return keys


def _issue_in_scope(
    issue: dict,
    dimension_scope: dict | None,
    table_renames: dict[str, str] | None = None,
) -> bool:
    if not dimension_scope or dimension_scope.get("mode") != "scoped":
        return True

    table_renames = table_renames or {}
    target = issue.get("target") or {}
    target_type = str(target.get("type") or "").strip()
    target_name = _target_table_name(target)
    table_names = _scope_keys(
        dimension_scope.get("tables") or [], table_renames
    )
    task_names = _scope_keys(dimension_scope.get("tasks") or [], table_renames)
    normalized_table = _canonical(
        _normalize_identifier_name(target_name, table_renames)
    )
    normalized_task = _canonical(
        _normalize_file_or_task_name(target_name, table_renames)
    )

    if target_type == "task":
        return normalized_task in task_names
    if target_type == "file":
        return normalized_table in table_names or normalized_task in task_names
    if target_type in {"table", "column", "metric"}:
        return normalized_table in table_names
    return normalized_table in table_names or normalized_task in task_names


def _dimension_scope(scope_plan: dict | None, dimension: str) -> dict | None:
    if not scope_plan:
        return None
    return (scope_plan.get("dimensions") or {}).get(dimension)


def _issues_by_fingerprint(
    assess_result: dict,
    scope_plan: dict | None = None,
    table_renames: dict[str, str] | None = None,
) -> dict:
    issues = {}
    table_renames = table_renames or {}
    for dimension_name, dimension in (
        assess_result.get("dimensions") or {}
    ).items():
        dimension_scope = _dimension_scope(scope_plan, dimension_name)
        for issue in dimension.get("issues") or []:
            if not _issue_in_scope(issue, dimension_scope, table_renames):
                continue
            fingerprint = str(issue.get("fingerprint") or "").strip()
            if fingerprint:
                key = _normalized_fingerprint(fingerprint, table_renames)
                issues[key] = issue
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
    *,
    change_analysis: dict | None = None,
    verification_plan: dict | None = None,
    ddl_changes: list[dict] | None = None,
    rename_mapping=None,
) -> dict:
    """Compare two assess results by issue fingerprint."""
    table_renames = _table_renames(
        change_analysis=change_analysis,
        verification_plan=verification_plan,
        ddl_changes=ddl_changes,
        rename_mapping=rename_mapping,
    )
    baseline_issues = _issues_by_fingerprint(
        baseline,
        scope_plan,
        table_renames,
    )
    current_issues = _issues_by_fingerprint(
        current,
        scope_plan,
        table_renames,
    )
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
