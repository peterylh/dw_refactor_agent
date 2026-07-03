"""Base classes for assessment rules."""

from __future__ import annotations

from dw_refactor_agent.assessment.rules.engine.selection import (
    RuleSelection,
    normalize_rule_selection,
)


class AssessRule:
    """Base class for one independently addressable assessment rule."""

    rule_id = ""
    dimension = ""
    domain = ""
    target = ""

    @classmethod
    def is_enabled(cls, selection: RuleSelection | None = None) -> bool:
        return normalize_rule_selection(selection).allows(cls.rule_id)
