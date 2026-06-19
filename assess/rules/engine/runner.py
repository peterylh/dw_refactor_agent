"""Rule grouping runner metadata."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from assess.rules.engine.base import AssessRule
from assess.rules.engine.registry import (
    RuleSpec,
    rule_classes_by_id,
)
from assess.rules.engine.selection import (
    RuleSelection,
    normalize_rule_selection,
)


@dataclass(frozen=True)
class RuleGroup:
    domain: str
    target: str
    rule_ids: list[str]


class RuleRunner:
    """Groups enabled rules by domain and target for cheap dispatch."""

    def __init__(
        self,
        selection: RuleSelection | None = None,
        specs: dict[str, RuleSpec] | None = None,
        rule_classes: dict[str, type[AssessRule]] | None = None,
    ):
        self.selection = normalize_rule_selection(selection)
        self.rule_classes = rule_classes or rule_classes_by_id()
        self.specs = specs or self._specs_from_rule_classes()
        self._groups = self._build_groups()

    def is_enabled(self, rule_id: str) -> bool:
        return rule_id in self.specs and self.selection.allows(rule_id)

    def rule_ids_for(self, domain: str, target: str) -> list[str]:
        return list(self._groups.get((domain, target), []))

    def rules_for(
        self,
        domain: str,
        target: str,
        dimension: str | None = None,
    ) -> list[AssessRule]:
        return [
            self.rule_classes[rule_id]()
            for rule_id in self.rule_ids_for(domain, target)
            if dimension is None or self.specs[rule_id].dimension == dimension
        ]

    def run(
        self,
        domain: str,
        target: str,
        targets: list,
        rule_context: dict | None = None,
        dimension: str | None = None,
    ) -> list[dict]:
        checks = []
        rule_context = rule_context or {}
        for candidate in targets:
            for rule in self.rules_for(domain, target, dimension):
                checks.extend(
                    self._normalize_result(
                        rule.evaluate(candidate, rule_context)
                    )
                )
        return checks

    def run_rules(
        self,
        rule_ids: list[str],
        targets: list,
        rule_context: dict | None = None,
    ) -> list[dict]:
        checks = []
        rule_context = rule_context or {}
        for candidate in targets:
            for rule_id in rule_ids:
                if not self.is_enabled(rule_id):
                    continue
                rule_class = self.rule_classes[rule_id]
                checks.extend(
                    self._normalize_result(
                        rule_class().evaluate(candidate, rule_context)
                    )
                )
        return checks

    def groups(self) -> list[RuleGroup]:
        return [
            RuleGroup(domain, target, list(rule_ids))
            for (domain, target), rule_ids in sorted(self._groups.items())
        ]

    def _specs_from_rule_classes(self) -> dict[str, RuleSpec]:
        return {
            rule_id: RuleSpec(
                rule_id=rule_id,
                dimension=rule_class.dimension,
                domain=rule_class.domain,
                target=rule_class.target,
            )
            for rule_id, rule_class in self.rule_classes.items()
        }

    def _build_groups(self) -> dict[tuple[str, str], list[str]]:
        groups = defaultdict(list)
        for rule_id, spec in self.specs.items():
            if not self.selection.allows(rule_id):
                continue
            groups[(spec.domain, spec.target)].append(rule_id)
        return dict(groups)

    @staticmethod
    def _normalize_result(result) -> list[dict]:
        if result is None:
            return []
        if isinstance(result, list):
            return [item for item in result if item is not None]
        return [result]
