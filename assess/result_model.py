"""Shared assessment result model helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


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


def target_ref(target_type: str, name: str) -> dict[str, str]:
    return {
        "type": target_type,
        "name": str(name),
    }


def make_check(
    *,
    rule_id: str,
    target_type: str,
    target: str,
    passed: bool,
    expected: str,
    actual: str,
    evidence: dict[str, Any] | None = None,
    message: str = "",
    issue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    check = {
        "rule_id": rule_id,
        "target": target_ref(target_type, target),
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
    }
    if evidence:
        check["evidence"] = evidence
    if message:
        check["message"] = message
    if issue:
        check["_issue"] = issue
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
        key: value
        for key, value in check.items()
        if not key.startswith("_")
    }


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
            "severity": override.get("severity") or rule.get("severity", ""),
            "rule_id": rule_id,
            "target": deepcopy(check["target"]),
            "title": override.get("title") or rule.get("title", rule_id),
            "message": override.get("message")
            or check.get("message")
            or check.get("actual", ""),
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
        numbered_checks.append(numbered)

    result = {
        "score": score,
        "rule_summary": build_rule_summary(numbered_checks, rules),
        "checks": [_clean_check(check) for check in numbered_checks],
        "issues": issues_from_checks(dimension, numbered_checks, rules),
    }
    if summary:
        result["summary"] = summary
    return result
