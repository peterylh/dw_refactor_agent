"""Helpers for applying rule selection in rule modules."""

from __future__ import annotations

from dw_refactor_agent.assessment.rules.engine.selection import (
    RuleSelection,
    normalize_rule_selection,
)


def rule_enabled(
    selection: RuleSelection | None,
    rule_id: str,
) -> bool:
    return normalize_rule_selection(selection).allows(rule_id)


def selected_rules(
    rules: dict,
    selection: RuleSelection | None,
) -> dict:
    normalized = normalize_rule_selection(selection)
    return {
        rule_id: metadata
        for rule_id, metadata in rules.items()
        if normalized.allows(rule_id)
    }
