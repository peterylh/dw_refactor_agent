"""Governance-aware model views used by assessment consumers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Dict, Union

from dw_refactor_agent.config import (
    MODEL_SECTIONS,
    GovernedModelMetadata,
    NotApplicableModelSection,
    UnavailableModelSection,
    ensure_governed_model,
    get_operational_layer,
    get_semantic_section,
    model_section_status,
)

SemanticSectionValue = Union[
    Dict[str, Any],
    UnavailableModelSection,
    NotApplicableModelSection,
]


class CanonicalSemanticPayload(dict):
    """Explicit marker for semantics already validated by model governance."""


@dataclass(frozen=True)
class AssessmentModelSemantics:
    """Validated semantic sections for one formal model."""

    model: GovernedModelMetadata
    sections: Mapping[str, SemanticSectionValue]

    @classmethod
    def from_metadata(
        cls,
        metadata: Mapping[str, Any],
        *,
        source: str = "",
    ) -> "AssessmentModelSemantics":
        model = ensure_governed_model(metadata, source=source)
        return cls(
            model=model,
            sections={
                section: get_semantic_section(model, section)
                for section in MODEL_SECTIONS
            },
        )

    @property
    def operational_layer(self) -> str | None:
        return get_operational_layer(self.model)

    @property
    def quarantined_sections(self) -> tuple[str, ...]:
        return tuple(
            section
            for section in MODEL_SECTIONS
            if isinstance(self.sections[section], UnavailableModelSection)
        )

    def status(self, section: str) -> str:
        return model_section_status(self.model, section)

    def section(self, section: str) -> SemanticSectionValue:
        return self.sections[section]

    def active_payload(self, section: str) -> dict[str, Any] | None:
        value = self.sections[section]
        return dict(value) if isinstance(value, dict) else None

    @property
    def layer(self) -> str | None:
        classification = self.active_payload("classification")
        value = (classification or {}).get("layer")
        return str(value).upper() if value else None

    @property
    def table_type(self) -> str | None:
        classification = self.active_payload("classification")
        value = (classification or {}).get("table_type")
        return str(value).lower() if value else None

    def canonical_semantic_mapping(self) -> CanonicalSemanticPayload:
        """Return active canonical fields without flattening unavailable data."""
        result = CanonicalSemanticPayload()
        for section in MODEL_SECTIONS:
            payload = self.active_payload(section)
            if payload is not None:
                result.update(payload)
        return result


@dataclass(frozen=True)
class SemanticCoverage:
    """Assessment targets withheld by model governance."""

    eligible_names: tuple[str, ...]
    assessed_names: tuple[str, ...]
    quarantined_names: tuple[str, ...]
    sections: tuple[str, ...]

    @classmethod
    def build(
        cls,
        views: Mapping[str, AssessmentModelSemantics],
        eligible_names: Iterable[str],
        sections: Iterable[str],
    ) -> "SemanticCoverage":
        eligible = tuple(sorted(set(eligible_names)))
        required = tuple(dict.fromkeys(sections))
        quarantined = tuple(
            name
            for name in eligible
            if name in views
            and any(
                views[name].status(section) == "quarantined"
                for section in required
            )
        )
        quarantined_set = set(quarantined)
        return cls(
            eligible_names=eligible,
            assessed_names=tuple(
                name for name in eligible if name not in quarantined_set
            ),
            quarantined_names=quarantined,
            sections=required,
        )

    @property
    def complete(self) -> bool:
        return not self.quarantined_names

    def as_dict(self) -> dict[str, Any]:
        eligible_count = len(self.eligible_names)
        assessed_count = len(self.assessed_names)
        return semantic_coverage_dict(
            eligible_count=eligible_count,
            assessed_count=assessed_count,
            quarantined_names=self.quarantined_names,
            sections=self.sections,
            unit="tables",
        )


def semantic_coverage_dict(
    *,
    eligible_count: int,
    assessed_count: int,
    quarantined_names: Iterable[str],
    sections: Iterable[str],
    unit: str,
    partially_assessed_count: int = 0,
) -> dict[str, Any]:
    """Build coverage using the scoring units owned by one dimension."""
    eligible = max(0, int(eligible_count))
    assessed = max(0, min(int(assessed_count), eligible))
    partial = max(0, int(partially_assessed_count))
    quarantined = tuple(sorted(set(quarantined_names)))
    return {
        "unit": unit,
        "eligible_count": eligible,
        "assessed_count": assessed,
        "partially_assessed_count": partial,
        "quarantined_count": len(quarantined),
        "coverage_pct": (
            round(assessed / eligible * 100, 1) if eligible else 100.0
        ),
        "quarantined_tables": list(quarantined),
        "required_sections": list(dict.fromkeys(sections)),
    }
