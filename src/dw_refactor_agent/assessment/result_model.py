"""Shared assessment result model helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "assess.diagnostic.v1"
SEVERITY_HIGH = "高"
SEVERITY_MEDIUM = "中"
SEVERITY_LOW = "低"
SEVERITY_ORDER = [SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW]


def rule_meta(
    *,
    name: str,
    severity: str,
    title: str,
    remediation_summary: str,
    strategy: str,
    edit_scope: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "severity": severity,
        "title": title,
        "remediation": {
            "summary": remediation_summary,
            "strategy": strategy,
            "edit_scope": edit_scope or [],
        },
    }


def target_ref(
    target_type: str,
    name: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = {
        "type": target_type,
        "name": str(name),
    }
    for key, value in (detail or {}).items():
        if value not in (None, "", []):
            target[key] = value
    return target


def make_check(
    *,
    rule_id: str,
    target_type: str,
    target: str,
    passed: bool,
    expected: Any,
    actual: Any,
    target_detail: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    diagnostic: dict[str, Any] | None = None,
    summary: str = "",
    message: str = "",
    issue: dict[str, Any] | None = None,
    fingerprint_discriminator: str = "",
) -> dict[str, Any]:
    check = {
        "rule_id": rule_id,
        "target": target_ref(target_type, target, target_detail),
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
    }
    if evidence:
        check["evidence"] = evidence
    if diagnostic:
        check["diagnostic"] = diagnostic
    if summary:
        check["summary"] = summary
    if message:
        check["message"] = message
    if issue:
        check["_issue"] = issue
    if fingerprint_discriminator:
        check["_fingerprint_discriminator"] = str(fingerprint_discriminator)
    return check


def _merge_remediation(
    base: dict[str, Any],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    remediation = deepcopy(base)
    for key, value in (override or {}).items():
        if value not in (None, "", []):
            remediation[key] = value
    return remediation


def _clean_check(check: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in check.items() if not key.startswith("_")
    }


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _enrich_check(
    *,
    dimension: str,
    check: dict[str, Any],
    rule: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(check)
    override = enriched.get("_issue") or {}
    remediation = _merge_remediation(
        rule.get("remediation", {}),
        override.get("remediation"),
    )
    enriched["schema_version"] = SCHEMA_VERSION
    enriched["dimension"] = dimension
    enriched["status"] = "passed" if enriched.get("passed") else "failed"
    enriched["severity"] = override.get("severity") or rule.get(
        "severity",
        "",
    )
    default_summary = (
        rule.get("name") if enriched.get("passed") else rule.get("title")
    )
    enriched["summary"] = (
        enriched.get("summary")
        or default_summary
        or enriched.get("message")
        or _message_text(enriched.get("actual", ""))
    )
    if remediation and not enriched.get("passed"):
        enriched["remediation"] = remediation
    return enriched


def build_rule_summary(
    checks: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for check in checks:
        rule_id = check["rule_id"]
        rule = rules.get(rule_id, {})
        item = summary.setdefault(
            rule_id,
            {
                "name": rule.get("name", rule_id),
                "severity": rule.get("severity", ""),
                "pass_count": 0,
                "total": 0,
                "pct": 0.0,
            },
        )
        item["total"] += 1
        if check["passed"]:
            item["pass_count"] += 1

    for item in summary.values():
        item["pct"] = (
            round(item["pass_count"] / item["total"] * 100, 1)
            if item["total"]
            else 0.0
        )
    return summary


def issue_fingerprint(dimension: str, check: dict[str, Any]) -> str:
    target = check.get("target") or {}
    target_type = str(target.get("type") or "")
    target_name = str(target.get("name") or "")
    if target_type in {"column", "metric"} and target.get("qualified_name"):
        target_name = str(target.get("qualified_name") or "")
    parts = [
        dimension,
        str(check.get("rule_id") or ""),
        target_type,
        target_name,
    ]
    discriminator = str(check.get("_fingerprint_discriminator") or "").strip()
    if discriminator and target_name == str(target.get("name") or ""):
        parts.append(discriminator)
    return "|".join(parts)


def issues_from_checks(
    dimension: str,
    checks: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues = []
    for check in checks:
        if check["passed"]:
            continue
        rule_id = check["rule_id"]
        rule = rules.get(rule_id, {})
        override = check.get("_issue") or {}
        issue_id = f"{dimension}.iss_{len(issues) + 1:03d}"
        remediation = _merge_remediation(
            rule.get("remediation", {}),
            override.get("remediation"),
        )
        issue = {
            "id": issue_id,
            "fingerprint": issue_fingerprint(dimension, check),
            "severity": override.get("severity") or rule.get("severity", ""),
            "rule_id": rule_id,
            "target": deepcopy(check["target"]),
            "title": override.get("title") or rule.get("title", rule_id),
            "message": override.get("message")
            or check.get("message")
            or check.get("summary")
            or _message_text(check.get("actual", "")),
            "remediation": remediation,
            "check_ids": [check["id"]],
        }
        issues.append(issue)
    return issues


def finalize_dimension(
    *,
    dimension: str,
    score: float,
    checks: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    numbered_checks = []
    for index, check in enumerate(checks, start=1):
        numbered = dict(check)
        numbered["id"] = f"{dimension}.chk_{index:03d}"
        numbered_checks.append(
            _enrich_check(
                dimension=dimension,
                check=numbered,
                rule=rules.get(numbered["rule_id"], {}),
            )
        )

    result = {
        "score": score,
        "rule_summary": build_rule_summary(numbered_checks, rules),
        "checks": [_clean_check(check) for check in numbered_checks],
        "issues": issues_from_checks(dimension, numbered_checks, rules),
    }
    if summary:
        result["summary"] = summary
    return result


DIAGNOSTIC_CONTRACT = {
    "primary_entry": "dimensions.*.issues",
    "stable_identity": "issues[].fingerprint",
    "issue_id_scope": "report_local",
    "remediation_source": "issues[].remediation",
    "diagnostic_source": "issues[].diagnostic",
    "rule_summary_source": "dimensions.*.rule_summary",
}


def compact_assessment_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return the default issue-primary assessment JSON shape."""
    compact = deepcopy(result)
    compact["diagnostic_contract"] = deepcopy(DIAGNOSTIC_CONTRACT)

    for dimension_name, dimension in (compact.get("dimensions") or {}).items():
        checks_by_id = {
            check.get("id"): check for check in dimension.get("checks") or []
        }
        diagnostic_catalog = {}
        for issue in dimension.get("issues") or []:
            check = _issue_check(issue, checks_by_id)
            if check:
                diagnostic = _compact_issue_diagnostic(
                    dimension_name,
                    check,
                    diagnostic_catalog,
                )
                if diagnostic:
                    issue["diagnostic"] = diagnostic
            issue.pop("check_ids", None)

        dimension.pop("checks", None)
        if diagnostic_catalog:
            dimension["diagnostic_catalog"] = {
                "naming_rules": dict(sorted(diagnostic_catalog.items()))
            }

    return compact


def _issue_check(
    issue: dict[str, Any],
    checks_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for check_id in issue.get("check_ids") or []:
        check = checks_by_id.get(check_id)
        if check:
            return check
    return None


def _compact_issue_diagnostic(
    dimension_name: str,
    check: dict[str, Any],
    diagnostic_catalog: dict[str, Any],
) -> dict[str, Any]:
    if dimension_name == "naming" and check.get("diagnostic"):
        return _compact_naming_diagnostic(check, diagnostic_catalog)

    diagnostic = {}
    if check.get("expected") not in (None, "", [], {}):
        diagnostic["expected"] = deepcopy(check["expected"])
    if check.get("actual") not in (None, "", [], {}):
        diagnostic["actual"] = deepcopy(check["actual"])
    evidence = {}
    if check.get("evidence") not in (None, "", [], {}):
        evidence.update(deepcopy(check["evidence"]))
    if check.get("diagnostic") not in (None, "", [], {}):
        evidence["raw"] = deepcopy(check["diagnostic"])
    if evidence:
        diagnostic["evidence"] = evidence
    return diagnostic


def _compact_naming_diagnostic(
    check: dict[str, Any],
    diagnostic_catalog: dict[str, Any],
) -> dict[str, Any]:
    raw = check.get("diagnostic") or {}
    diagnostic = {}
    expected = _compact_naming_expected(check.get("expected"))
    if expected not in (None, "", [], {}):
        diagnostic["expected"] = expected

    if check.get("actual") not in (None, "", [], {}):
        diagnostic["actual"] = deepcopy(check["actual"])

    evidence = {}
    if raw.get("code"):
        evidence["code"] = raw["code"]

    attempts = []
    for attempt in raw.get("attempts") or []:
        compact_attempt = _compact_naming_attempt(
            attempt,
            diagnostic_catalog,
        )
        if compact_attempt:
            attempts.append(compact_attempt)
    if attempts:
        evidence["attempts"] = attempts

    failure = _compact_naming_failure(raw.get("failure"), {})
    if failure:
        evidence["failure"] = failure

    for key in ("actual_length", "max_length"):
        if raw.get(key) not in (None, "", [], {}):
            evidence[key] = raw[key]

    if evidence:
        diagnostic["evidence"] = evidence

    return diagnostic


def _compact_naming_expected(value: Any) -> Any:
    if not isinstance(value, dict):
        return deepcopy(value)

    compact = {}
    if value.get("description"):
        compact["description"] = value["description"]

    rule_refs = _naming_expected_rule_refs(value)
    if rule_refs:
        compact["rule_refs"] = rule_refs

    return compact


def _naming_expected_rule_refs(value: dict[str, Any]) -> list[str]:
    refs = value.get("rule_refs") or value.get("rule_names") or []
    if not refs:
        refs = []
        for attempt in value.get("attempts") or []:
            rule_ref = (
                attempt.get("rule_ref")
                or attempt.get("rule_name")
                or (attempt.get("rule") or {}).get("name")
            )
            if rule_ref:
                refs.append(rule_ref)

    unique_refs = []
    seen = set()
    for ref in refs:
        ref_text = str(ref).strip()
        if ref_text and ref_text not in seen:
            unique_refs.append(ref_text)
            seen.add(ref_text)
    return unique_refs


def _compact_naming_attempt(
    attempt: dict[str, Any],
    diagnostic_catalog: dict[str, Any],
) -> dict[str, Any]:
    rule = attempt.get("rule") or {}
    rule_ref = str(rule.get("name") or "").strip()
    if rule_ref:
        _add_naming_rule_catalog(rule_ref, attempt, diagnostic_catalog)

    position_index = _segment_position_index(
        attempt.get("segments") or attempt.get("nodes") or []
    )
    failure = _compact_naming_failure(
        attempt.get("failure"),
        position_index,
    )
    compact = {}
    if rule_ref:
        compact["rule_ref"] = rule_ref
    if failure:
        compact["failure"] = failure
    return compact


def _add_naming_rule_catalog(
    rule_ref: str,
    attempt: dict[str, Any],
    diagnostic_catalog: dict[str, Any],
) -> None:
    if rule_ref in diagnostic_catalog:
        return

    item = {}
    if attempt.get("expression"):
        item["expression"] = attempt["expression"]

    segments = _catalog_segments(attempt.get("segments") or [])
    if segments:
        item["segments"] = segments

    nodes = _catalog_segments(attempt.get("nodes") or [])
    if nodes:
        item["nodes"] = nodes

    if item:
        diagnostic_catalog[rule_ref] = item


def _catalog_segments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog = []
    ordinal = 0
    for item in items or []:
        if not _include_catalog_segment(item):
            continue
        ordinal += 1
        catalog.append(_compact_catalog_segment(item, ordinal))
    return catalog


def _segment_position_index(
    items: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    index = {}
    ordinal = 0
    for item in items or []:
        if not _include_catalog_segment(item):
            continue
        ordinal += 1
        position = item.get("position")
        if position is None:
            position = ordinal
        index[int(position)] = {
            "name": str(item.get("name") or ""),
            "ordinal": ordinal,
        }
    return index


def _include_catalog_segment(item: dict[str, Any]) -> bool:
    kind = item.get("kind")
    name = str(item.get("name") or "")
    if kind in {"type", "rule"}:
        return bool(name)
    if kind == "literal":
        return bool(name and name != "_")
    return False


def _compact_catalog_segment(
    item: dict[str, Any],
    ordinal: int,
) -> dict[str, Any]:
    segment = {
        "name": str(item.get("name") or ""),
        "ordinal": ordinal,
        "kind": item.get("kind"),
    }
    if item.get("repeat"):
        segment["repeat"] = deepcopy(item["repeat"])

    type_def = item.get("type") or {}
    for key in ("label", "allow", "patterns", "values_from"):
        if type_def.get(key) not in (None, "", [], {}):
            segment[key] = deepcopy(type_def[key])

    return {key: value for key, value in segment.items() if value}


def _compact_naming_failure(
    failure: dict[str, Any] | None,
    position_index: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(failure, dict):
        return {}

    compact = {}
    if failure.get("code"):
        compact["code"] = failure["code"]

    segment = _failure_segment(failure, position_index)
    if segment:
        compact["segment"] = segment

    expected = _compact_failure_expected(failure.get("expected"))
    if expected not in (None, "", [], {}):
        compact["expected"] = expected

    actual = failure.get("actual")
    if actual in (None, "", [], {}):
        actual = failure.get("actual_remaining")
    if actual not in (None, "", [], {}):
        compact["actual"] = actual

    if failure.get("message"):
        compact["message"] = failure["message"]
    if failure.get("paths"):
        compact["paths"] = deepcopy(failure["paths"])

    return compact


def _failure_segment(
    failure: dict[str, Any],
    position_index: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    raw_segment = failure.get("segment") or {}
    if not isinstance(raw_segment, dict):
        return {}
    position = raw_segment.get("position") or failure.get("position")
    if position is not None:
        segment = position_index.get(int(position))
        if segment:
            return segment

    if not _include_catalog_segment(raw_segment):
        return {}
    return {
        "name": str(raw_segment.get("name") or ""),
        "ordinal": int(position or 1),
    }


def _compact_failure_expected(value: Any) -> Any:
    if not isinstance(value, list):
        return deepcopy(value)
    return [_compact_expected_item(item) for item in value]


def _compact_expected_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return deepcopy(item)
    compact = {}
    for key in ("kind", "name", "repeat"):
        if item.get(key) not in (None, "", [], {}):
            compact[key] = deepcopy(item[key])
    return compact or deepcopy(item)
