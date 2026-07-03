"""Rule enable/disable selection."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuleSelection:
    """Rule filter used by assess rule modules.

    ``only`` limits execution to a fixed allow-list. ``disabled`` removes
    individual rules from the default set.
    """

    disabled: set[str] = field(default_factory=set)
    only: set[str] = field(default_factory=set)

    def allows(self, rule_id: str) -> bool:
        if self.only and rule_id not in self.only:
            return False
        return rule_id not in self.disabled


def normalize_rule_selection(selection: RuleSelection | None) -> RuleSelection:
    return selection or RuleSelection()
