"""Section-aware cold-start candidate resolution and quarantine cascade."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable

from dw_refactor_agent.assessment.llm.generation_contract import (
    _validate_entities,
    _validate_execution,
    _validate_semantics,
)
from dw_refactor_agent.assessment.llm.inspection_contract import (
    canonical_semantic_code,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    HARD_BLOCK_ISSUE_CODES,
    InspectionIssue,
    issue_for_code,
    sort_issues,
)
from dw_refactor_agent.assessment.llm.inspection_recovery import (
    RecoveredInspectionCandidate,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
    dict_to_result,
    result_to_dict,
)
from dw_refactor_agent.assessment.semantic_models import (
    AssessmentModelSemantics,
)
from dw_refactor_agent.config.model_governance import (
    MODEL_SCHEMA_V3,
    MODEL_SECTION_FIELDS,
    MODEL_SECTION_LEGACY_ALIAS_FIELDS,
    MODEL_SECTIONS,
    STRUCTURE_SECTIONS,
    UnsupportedModelGovernanceError,
    validate_model_metadata,
)
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    short_table_name,
)
from dw_refactor_agent.lineage.view import LineageView

SECTION_DECISION_SCHEMA_VERSION = 1
PROPAGATION_PROVENANCE_SCHEMA_VERSION = 1
EFFECTIVE_CANDIDATE_SCHEMA_VERSION = 1

_SECTION_ORDER = {
    section: index for index, section in enumerate(MODEL_SECTIONS)
}
_SECTION_STATUSES = frozenset({"active", "not_applicable", "quarantined"})
_SAFE_OR_WARNING_ISSUES = frozenset(
    {
        "ambiguous_min_max_aggregation",
        "duplicate_columns_same_group",
        "hallucinated_column_unreferenced",
    }
)
_METRIC_GROUPS = (
    "atomic_metrics",
    "derived_metrics",
    "calculated_metrics",
)


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _issue_summary(issue: InspectionIssue) -> str:
    location = issue.path or issue.table
    items = ", ".join(issue.items)
    return ": ".join(part for part in (issue.code, location, items) if part)


def _table_key(value: Any) -> str:
    return identifier_match_key(str(value or ""))


def _short_key(value: Any) -> str:
    return identifier_match_key(short_table_name(str(value or "")))


def _sorted_statuses(statuses: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((section, statuses[section]) for section in MODEL_SECTIONS)


def _sorted_reasons(
    reasons: dict[str, set[str]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        (section, tuple(sorted(reasons.get(section) or ())))
        for section in MODEL_SECTIONS
        if reasons.get(section)
    )


@dataclass(frozen=True)
class SectionDecision:
    """Immutable status and evidence for every formal semantic section."""

    table_name: str
    statuses: tuple[tuple[str, str], ...]
    reasons: tuple[tuple[str, tuple[str, ...]], ...] = ()
    issues: tuple[InspectionIssue, ...] = ()
    hard_block_issues: tuple[InspectionIssue, ...] = ()
    schema_version: int = SECTION_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SECTION_DECISION_SCHEMA_VERSION:
            raise ValueError("unsupported section decision schema")
        status_map = dict(self.statuses)
        if tuple(status_map) != MODEL_SECTIONS:
            raise ValueError("section decision must cover every model section")
        if set(status_map.values()) - _SECTION_STATUSES:
            raise ValueError("section decision contains an unknown status")
        reason_map = dict(self.reasons)
        if set(reason_map) - set(MODEL_SECTIONS):
            raise ValueError(
                "section decision contains an unknown reason section"
            )
        for section, section_reasons in self.reasons:
            if status_map[section] != "quarantined" or not section_reasons:
                raise ValueError("only quarantined sections may have reasons")

    def status(self, section: str) -> str:
        return dict(self.statuses)[section]

    def reasons_for(self, section: str) -> tuple[str, ...]:
        return dict(self.reasons).get(section, ())

    @property
    def quarantined_sections(self) -> tuple[str, ...]:
        return tuple(
            section
            for section, status in self.statuses
            if status == "quarantined"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table": self.table_name,
            "sections": dict(self.statuses),
            "reasons": {
                section: list(reasons) for section, reasons in self.reasons
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "hard_block_issues": [
                issue.to_dict() for issue in self.hard_block_issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionDecision":
        if not isinstance(data, dict):
            raise ValueError("section decision must be an object")
        sections = data.get("sections")
        reasons = data.get("reasons") or {}
        if not isinstance(sections, dict) or not isinstance(reasons, dict):
            raise ValueError("section decision sections/reasons are invalid")
        raw_issues = data.get("issues") or []
        raw_hard_issues = data.get("hard_block_issues") or []
        if not isinstance(raw_issues, list) or not isinstance(
            raw_hard_issues, list
        ):
            raise ValueError("section decision issues must be lists")
        return cls(
            schema_version=int(data.get("schema_version") or 0),
            table_name=str(data.get("table") or ""),
            statuses=tuple(
                (section, str(sections.get(section) or ""))
                for section in MODEL_SECTIONS
            ),
            reasons=tuple(
                (
                    section,
                    tuple(
                        str(reason) for reason in reasons.get(section) or []
                    ),
                )
                for section in MODEL_SECTIONS
                if reasons.get(section)
            ),
            issues=sort_issues(
                InspectionIssue.from_dict(issue) for issue in raw_issues
            ),
            hard_block_issues=sort_issues(
                InspectionIssue.from_dict(issue) for issue in raw_hard_issues
            ),
        )


@dataclass(frozen=True)
class PropagationProvenance:
    """One section dependency used by fixed-point quarantine propagation."""

    source_table: str
    source_section: str
    target_table: str
    target_section: str
    evidence_kind: str
    schema_version: int = PROPAGATION_PROVENANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROPAGATION_PROVENANCE_SCHEMA_VERSION:
            raise ValueError("unsupported propagation provenance schema")
        if self.source_section not in MODEL_SECTIONS:
            raise ValueError("unknown source propagation section")
        if self.target_section not in MODEL_SECTIONS:
            raise ValueError("unknown target propagation section")
        if not self.evidence_kind:
            raise ValueError("propagation evidence kind is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_table": self.source_table,
            "source_section": self.source_section,
            "target_table": self.target_table,
            "target_section": self.target_section,
            "evidence_kind": self.evidence_kind,
        }


@dataclass(frozen=True)
class EffectiveInspectionCandidate:
    """Immutable recovered payload after section masking."""

    table_name: str
    payload_json: str
    decision: SectionDecision
    schema_version: int = EFFECTIVE_CANDIDATE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        table_name: str,
        payload: dict[str, Any],
        decision: SectionDecision,
    ) -> "EffectiveInspectionCandidate":
        return cls(
            table_name=table_name,
            payload_json=_stable_json(payload),
            decision=decision,
        )

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("effective inspection payload is not an object")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table": self.table_name,
            "payload": self.payload,
            "decision": self.decision.to_dict(),
        }


@dataclass(frozen=True)
class ResolvedGenerationCandidate:
    """Complete project candidate and its deterministic resolution audit."""

    models_json: str
    decisions: tuple[SectionDecision, ...]
    provenance: tuple[PropagationProvenance, ...]
    effective_inspections: tuple[EffectiveInspectionCandidate, ...]
    fixed_point_iterations: int
    validation_json: str

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        value = json.loads(self.models_json)
        if not isinstance(value, dict):
            raise ValueError("resolved model candidate is not an object")
        return value

    @property
    def validation(self) -> dict[str, Any]:
        value = json.loads(self.validation_json)
        if not isinstance(value, dict):
            raise ValueError("resolved candidate validation is not an object")
        return value

    @property
    def quarantined_tables(self) -> tuple[str, ...]:
        return tuple(
            decision.table_name
            for decision in self.decisions
            if decision.quarantined_sections
        )

    @property
    def hard_blocked_tables(self) -> tuple[str, ...]:
        return tuple(
            decision.table_name
            for decision in self.decisions
            if decision.hard_block_issues
        )

    @property
    def status(self) -> str:
        if (
            self.validation.get("status") == "blocked"
            or self.hard_blocked_tables
        ):
            return "blocked"
        if self.quarantined_tables:
            return "quarantined"
        return "active"

    def report(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "complete": self.status == "active",
            "fixed_point_iterations": self.fixed_point_iterations,
            "quarantined_table_count": len(self.quarantined_tables),
            "quarantined_tables": list(self.quarantined_tables),
            "hard_blocked_table_count": len(self.hard_blocked_tables),
            "hard_blocked_tables": list(self.hard_blocked_tables),
            "section_decisions": [
                decision.to_dict() for decision in self.decisions
            ],
            "propagation_provenance": [
                edge.to_dict() for edge in self.provenance
            ],
            "effective_inspections": [
                candidate.to_dict() for candidate in self.effective_inspections
            ],
            "validation": self.validation,
        }


def _report_payload(report: dict[str, Any]) -> dict[str, Any]:
    recovered = report.get("recovered_candidate")
    if isinstance(recovered, dict) and isinstance(
        recovered.get("payload"), dict
    ):
        return copy.deepcopy(recovered["payload"])
    return {
        key: copy.deepcopy(report.get(key))
        for key in (
            "inferred_layer",
            "table_type",
            "business_process",
            "business_process_mode",
            "business_process_sources",
            "business_process_conflicts",
            "inferred_data_domain",
            "inferred_business_area",
            "dimension_role",
            "dimension_content_type",
            "confidence",
            "reasoning_steps",
            "columns",
            "entities",
            "grain",
        )
    }


def _report_issues(report: dict[str, Any]) -> tuple[InspectionIssue, ...]:
    raw_issues = report.get("issues") or []
    if not isinstance(raw_issues, list):
        raise ValueError("inspection report issues must be a list")
    return sort_issues(InspectionIssue.from_dict(item) for item in raw_issues)


def _catalog_codes(catalog: dict[str, Any], section: str) -> set[str]:
    return {
        code
        for entry in catalog.get(section) or []
        if isinstance(entry, dict)
        for raw_code in (entry.get("code"), entry.get("id"))
        for code in [canonical_semantic_code(raw_code)]
        if code
    }


def _primary_entity_code(payload: dict[str, Any]) -> str:
    entities = [
        item
        for item in payload.get("entities") or []
        if isinstance(item, dict)
    ]
    primary = next(
        (
            item
            for item in entities
            if str(item.get("type") or "").casefold() == "primary"
        ),
        entities[0] if entities else {},
    )
    return canonical_semantic_code(primary.get("code"))


def _unconfirmed_catalog_issues(
    table_name: str,
    payload: dict[str, Any],
    catalog: dict[str, Any],
) -> list[InspectionIssue]:
    issues = []
    table_type = str(payload.get("table_type") or "").casefold()
    if table_type == "fact":
        columns = payload.get("columns") or {}
        confirmed = _catalog_codes(catalog, "business_processes")
        table_process = canonical_semantic_code(
            payload.get("business_process")
        )
        if table_process and table_process not in confirmed:
            issues.append(
                issue_for_code(
                    "business_process_unknown",
                    table=table_name,
                    path="business_process",
                    items=(table_process,),
                )
            )
        for group in _METRIC_GROUPS:
            for metric in columns.get(group) or []:
                if not isinstance(metric, dict):
                    continue
                metric_process = canonical_semantic_code(
                    metric.get("business_process")
                )
                if metric_process and metric_process not in confirmed:
                    metric_name = str(metric.get("name") or "").strip()
                    path = f"columns.{group}"
                    if metric_name:
                        path = f"{path}.{metric_name}"
                    issues.append(
                        issue_for_code(
                            "business_process_unknown",
                            table=table_name,
                            path=f"{path}.business_process",
                            items=(metric_process,),
                            sections=("metrics",),
                        )
                    )
    elif table_type == "dimension":
        subject = _primary_entity_code(payload)
        if subject and subject not in _catalog_codes(
            catalog, "semantic_subjects"
        ):
            issues.append(
                issue_for_code(
                    "semantic_subject_unknown",
                    table=table_name,
                    path="entities.primary.code",
                    items=(subject,),
                )
            )
    return issues


def _initial_statuses(
    metadata: dict[str, Any], *, inspected: bool
) -> dict[str, str]:
    layer = str(
        metadata.get("layer") or metadata.get("operational_layer") or ""
    ).upper()
    table_type = str(metadata.get("table_type") or "").casefold()
    statuses = {section: "active" for section in STRUCTURE_SECTIONS}
    statuses["metrics"] = (
        "active"
        if layer in {"DWD", "DWS"} and table_type == "fact"
        else "not_applicable"
    )
    if not inspected and layer in {"ODS", "ADS"}:
        for section in MODEL_SECTIONS[1:]:
            if not any(
                field in metadata for field in MODEL_SECTION_FIELDS[section]
            ):
                statuses[section] = "not_applicable"
    return statuses


def _reason_for_issue(issue: InspectionIssue, section: str) -> str:
    if issue.code in {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_content_parse_failed",
        "inspection_low_confidence",
        "inspection_missing",
        "inspection_request_rejected",
        "inspection_transport_failed",
        "resolution_requires_reinspection",
    }:
        return "inspection_unavailable"
    if section == "metrics":
        return "metrics_incomplete"
    if section == "business_semantics":
        if issue.code == "business_process_missing":
            return "business_process_missing"
        if issue.code in {
            "business_process_unknown",
            "semantic_subject_unknown",
        }:
            return "catalog_code_unconfirmed"
        return "business_semantics_untrusted"
    if section == "entities":
        return "entities_incomplete"
    if section == "grain":
        return "grain_incomplete"
    return "classification_untrusted"


def _quarantine_structure_bundle(
    statuses: dict[str, str],
    reasons: dict[str, set[str]],
    *,
    reason: str,
) -> None:
    for section in STRUCTURE_SECTIONS:
        statuses[section] = "quarantined"
        reasons.setdefault(section, set()).add(
            reason
            if reason == "inspection_unavailable"
            else "structure_bundle_incomplete"
        )
    statuses["metrics"] = "quarantined"
    reasons.setdefault("metrics", set()).add(
        "inspection_unavailable"
        if reason == "inspection_unavailable"
        else "dependent_structure_unavailable"
    )


def build_local_section_decision(
    table_name: str,
    metadata: dict[str, Any],
    *,
    inspection_report: dict[str, Any] | None,
    catalog: dict[str, Any],
    additional_issues: Iterable[InspectionIssue] = (),
) -> SectionDecision:
    """Decide local section availability before any cross-table evidence."""
    inspected = inspection_report is not None
    payload = _report_payload(inspection_report or {})
    decision_metadata = dict(metadata)
    if inspected:
        decision_metadata.update(
            {
                field: payload.get(field)
                for field in ("inferred_layer", "table_type")
                if payload.get(field)
            }
        )
        if payload.get("inferred_layer"):
            decision_metadata["layer"] = payload["inferred_layer"]
    statuses = _initial_statuses(decision_metadata, inspected=inspected)
    reasons: dict[str, set[str]] = {}
    issues = list(additional_issues)
    if inspection_report is not None:
        issues.extend(_report_issues(inspection_report))
        issues.extend(
            _unconfirmed_catalog_issues(
                table_name,
                _report_payload(inspection_report),
                catalog,
            )
        )
        if (
            str(inspection_report.get("status") or "").casefold() == "blocked"
            and not issues
        ):
            issues.append(
                issue_for_code(
                    "inspection_blocked_summary_unexpanded",
                    table=table_name,
                    stage="local_validation",
                )
            )

    hard_block_issues = [
        issue for issue in issues if issue.code in HARD_BLOCK_ISSUE_CODES
    ]
    classification_conflict = bool(
        inspection_report
        and (
            str(metadata.get("layer") or "").upper()
            != str(payload.get("inferred_layer") or "").upper()
            or str(metadata.get("table_type") or "").casefold()
            != str(payload.get("table_type") or "").casefold()
        )
    )
    for issue in issues:
        if (
            issue.code in HARD_BLOCK_ISSUE_CODES
            or issue.code in _SAFE_OR_WARNING_ISSUES
        ):
            continue
        affected = set(issue.sections)
        if affected.intersection(STRUCTURE_SECTIONS):
            primary_reason = _reason_for_issue(
                issue,
                next(
                    (
                        section
                        for section in STRUCTURE_SECTIONS
                        if section in affected
                    ),
                    "classification",
                ),
            )
            _quarantine_structure_bundle(
                statuses,
                reasons,
                reason=primary_reason,
            )
            for section in affected.intersection(STRUCTURE_SECTIONS):
                reasons.setdefault(section, set()).add(
                    _reason_for_issue(issue, section)
                )
        elif "metrics" in affected:
            if statuses["metrics"] == "not_applicable":
                if classification_conflict:
                    _quarantine_structure_bundle(
                        statuses,
                        reasons,
                        reason="classification_untrusted",
                    )
                continue
            statuses["metrics"] = "quarantined"
            reasons.setdefault("metrics", set()).add(
                _reason_for_issue(issue, "metrics")
            )

    if (
        statuses["metrics"] == "quarantined"
        and str(
            metadata.get("table_type") or payload.get("table_type") or ""
        ).casefold()
        == "fact"
    ):
        table_process = canonical_semantic_code(
            payload.get("business_process")
        )
        if table_process not in _catalog_codes(catalog, "business_processes"):
            _quarantine_structure_bundle(
                statuses,
                reasons,
                reason="business_semantics_untrusted",
            )

    return SectionDecision(
        table_name=table_name,
        statuses=_sorted_statuses(statuses),
        reasons=_sorted_reasons(reasons),
        issues=sort_issues(issues),
        hard_block_issues=sort_issues(hard_block_issues),
    )


def _decision_with_upstream_quarantine(
    decision: SectionDecision,
    target_section: str,
) -> SectionDecision:
    statuses = dict(decision.statuses)
    reasons = {
        section: set(section_reasons)
        for section, section_reasons in decision.reasons
    }
    if target_section in STRUCTURE_SECTIONS:
        _quarantine_structure_bundle(
            statuses,
            reasons,
            reason="upstream_section_unavailable",
        )
        for section in STRUCTURE_SECTIONS:
            reasons.setdefault(section, set()).add(
                "upstream_section_unavailable"
            )
    else:
        statuses[target_section] = "quarantined"
        reasons.setdefault(target_section, set()).add(
            "upstream_section_unavailable"
        )
    return SectionDecision(
        table_name=decision.table_name,
        statuses=_sorted_statuses(statuses),
        reasons=_sorted_reasons(reasons),
        issues=decision.issues,
        hard_block_issues=decision.hard_block_issues,
    )


def _resolve_decision_key(
    table_name: str,
    decisions_by_key: dict[str, SectionDecision],
) -> str:
    exact = _table_key(table_name)
    if exact in decisions_by_key:
        return exact
    wanted_short = _short_key(table_name)
    matches = [
        key
        for key, decision in decisions_by_key.items()
        if _short_key(decision.table_name) == wanted_short
    ]
    return matches[0] if len(matches) == 1 else ""


def resolve_fixed_point(
    decisions: Iterable[SectionDecision],
    provenance: Iterable[PropagationProvenance],
) -> tuple[tuple[SectionDecision, ...], int]:
    """Cascade unavailable source sections monotonically to true dependants."""
    decisions_by_key = {}
    for decision in decisions:
        key = _table_key(decision.table_name)
        if not key or key in decisions_by_key:
            raise ValueError(
                "section decision table identities must be unique"
            )
        decisions_by_key[key] = decision
    stable_edges = tuple(
        sorted(
            {
                _stable_json(edge.to_dict()): edge for edge in provenance
            }.values(),
            key=lambda edge: (
                _table_key(edge.source_table),
                _SECTION_ORDER[edge.source_section],
                _table_key(edge.target_table),
                _SECTION_ORDER[edge.target_section],
                edge.evidence_kind,
            ),
        )
    )
    max_iterations = len(decisions_by_key) * len(MODEL_SECTIONS) + 1
    for iteration in range(1, max_iterations + 1):
        changed = False
        for edge in stable_edges:
            source_key = _resolve_decision_key(
                edge.source_table, decisions_by_key
            )
            target_key = _resolve_decision_key(
                edge.target_table, decisions_by_key
            )
            if not source_key or not target_key:
                continue
            source = decisions_by_key[source_key]
            target = decisions_by_key[target_key]
            if source.status(edge.source_section) == "active":
                continue
            revised = _decision_with_upstream_quarantine(
                target,
                edge.target_section,
            )
            if revised != target:
                decisions_by_key[target_key] = revised
                changed = True
        if not changed:
            return (
                tuple(
                    sorted(
                        decisions_by_key.values(),
                        key=lambda item: (
                            _table_key(item.table_name),
                            item.table_name,
                        ),
                    )
                ),
                iteration,
            )
    raise RuntimeError("section quarantine fixed-point did not converge")


def _known_table_name(
    reference: str,
    table_names: Iterable[str],
) -> str:
    by_key = {_table_key(name): name for name in table_names}
    exact = by_key.get(_table_key(reference))
    if exact:
        return exact
    wanted_short = _short_key(reference)
    matches = [
        name for name in by_key.values() if _short_key(name) == wanted_short
    ]
    return matches[0] if len(matches) == 1 else ""


def _resolved_upstream_table_names(
    upstream: dict[str, set[str]],
    target_name: str,
    table_names: Iterable[str],
) -> tuple[str, ...]:
    names = tuple(table_names)
    resolved = set()
    for target_ref, source_refs in upstream.items():
        resolved_target = _known_table_name(str(target_ref), names)
        if _table_key(resolved_target) != _table_key(target_name):
            continue
        for source_ref in source_refs:
            source_name = _known_table_name(str(source_ref), names)
            if source_name:
                resolved.add(source_name)
    return tuple(sorted(resolved, key=lambda name: (_table_key(name), name)))


def _metric_names(payload: dict[str, Any]) -> set[str]:
    columns = payload.get("columns") or {}
    return {
        str(item.get("name") or "").strip().casefold()
        for group in _METRIC_GROUPS
        for item in columns.get(group) or []
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _current_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(report.get(key))
        for key in (
            "inferred_layer",
            "table_type",
            "business_process",
            "business_process_mode",
            "business_process_sources",
            "business_process_conflicts",
            "inferred_data_domain",
            "inferred_business_area",
            "dimension_role",
            "dimension_content_type",
            "confidence",
            "reasoning_steps",
            "columns",
            "entities",
            "grain",
        )
    }


def _entity_codes_by_key(payload: dict[str, Any]) -> dict[str, str]:
    resolved = {}
    for entity in payload.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        code = canonical_semantic_code(entity.get("code"))
        if not code:
            continue
        for column in entity.get("key_columns") or []:
            key = str(column or "").strip().casefold()
            if key:
                resolved[key] = code
    return resolved


def _add_entity_alignment_edges(
    edges: list[PropagationProvenance],
    *,
    view: LineageView,
    names: list[str],
    recovered_by_name: dict[str, dict[str, Any]],
    current_by_name: dict[str, dict[str, Any]],
) -> None:
    for target_name in names:
        recovered_target = _entity_codes_by_key(recovered_by_name[target_name])
        current_target = _entity_codes_by_key(current_by_name[target_name])
        if current_target == recovered_target:
            continue
        for lineage in view.column_lineage_for_table(target_name):
            source_ref = str(lineage.get("source") or "")
            target_ref = str(lineage.get("target") or "")
            if "." not in source_ref or "." not in target_ref:
                continue
            source_table_ref, source_column = source_ref.rsplit(".", 1)
            target_table_ref, target_column = target_ref.rsplit(".", 1)
            source_name = _known_table_name(source_table_ref, names)
            lineage_target = _known_table_name(target_table_ref, names)
            if not source_name or _table_key(lineage_target) != _table_key(
                target_name
            ):
                continue
            source_codes = _entity_codes_by_key(current_by_name[source_name])
            source_code = source_codes.get(source_column.casefold())
            target_code = current_target.get(target_column.casefold())
            prior_target_code = recovered_target.get(target_column.casefold())
            if (
                source_code
                and source_code == target_code
                and source_code != prior_target_code
            ):
                edges.append(
                    PropagationProvenance(
                        source_table=source_name,
                        source_section="entities",
                        target_table=target_name,
                        target_section="entities",
                        evidence_kind="entity_key_lineage_alignment",
                    )
                )


def _add_reverse_grain_entity_edges(
    edges: list[PropagationProvenance],
    *,
    view: LineageView,
    names: list[str],
    recovered_by_name: dict[str, dict[str, Any]],
    current_by_name: dict[str, dict[str, Any]],
) -> None:
    for dimension_name in names:
        recovered_codes = set(
            _entity_codes_by_key(recovered_by_name[dimension_name]).values()
        )
        current_codes = set(
            _entity_codes_by_key(current_by_name[dimension_name]).values()
        )
        added_codes = current_codes - recovered_codes
        if not added_codes:
            continue
        for grain_name in names:
            if grain_name == dimension_name:
                continue
            grain_codes = {
                canonical_semantic_code(code)
                for code in (
                    current_by_name[grain_name].get("grain") or {}
                ).get("entities")
                or []
                if canonical_semantic_code(code)
            }
            if not added_codes.intersection(grain_codes):
                continue
            has_direct_lineage = any(
                _known_table_name(
                    str(lineage.get("source") or "").rsplit(".", 1)[0],
                    names,
                )
                == dimension_name
                for lineage in view.column_lineage_for_table(grain_name)
                if "." in str(lineage.get("source") or "")
            )
            if not has_direct_lineage:
                continue
            for source_section in ("entities", "grain"):
                edges.append(
                    PropagationProvenance(
                        source_table=grain_name,
                        source_section=source_section,
                        target_table=dimension_name,
                        target_section="entities",
                        evidence_kind="grain_related_entity_discovery",
                    )
                )


def collect_propagation_provenance(
    inspection_reports: Iterable[dict[str, Any]],
    *,
    lineage_data: dict[str, Any] | None = None,
) -> tuple[PropagationProvenance, ...]:
    """Collect only explicit metric/process dependencies used by resolution."""
    reports = [
        report for report in inspection_reports if isinstance(report, dict)
    ]
    names = [str(report.get("table_name") or "") for report in reports]
    recovered_by_name = {
        name: _report_payload(report) for name, report in zip(names, reports)
    }
    current_by_name = {
        name: _current_report_payload(report)
        for name, report in zip(names, reports)
    }
    edges: list[PropagationProvenance] = []
    for target_name, payload in recovered_by_name.items():
        columns = payload.get("columns") or {}
        for group in _METRIC_GROUPS:
            for metric in columns.get(group) or []:
                if not isinstance(metric, dict):
                    continue
                source = _known_table_name(
                    str(metric.get("base_metric_table") or ""),
                    names,
                )
                if source:
                    edges.append(
                        PropagationProvenance(
                            source_table=source,
                            source_section="metrics",
                            target_table=target_name,
                            target_section="metrics",
                            evidence_kind="declared_base_metric",
                        )
                    )

    if lineage_data:
        view = LineageView.from_data("", lineage_data)
        for target_name, payload in recovered_by_name.items():
            target_metrics = _metric_names(payload)
            if not target_metrics:
                continue
            for lineage in view.column_lineage_for_table(target_name):
                target = str(lineage.get("target") or "")
                source = str(lineage.get("source") or "")
                target_column = target.rsplit(".", 1)[-1].casefold()
                source_table = _known_table_name(
                    source.rsplit(".", 1)[0] if "." in source else "",
                    names,
                )
                source_column = source.rsplit(".", 1)[-1].casefold()
                source_metrics = _metric_names(
                    recovered_by_name.get(source_table) or {}
                )
                if (
                    source_table
                    and target_column in target_metrics
                    and source_column in source_metrics
                ):
                    edges.append(
                        PropagationProvenance(
                            source_table=source_table,
                            source_section="metrics",
                            target_table=target_name,
                            target_section="metrics",
                            evidence_kind="direct_column_lineage",
                        )
                    )

        _add_entity_alignment_edges(
            edges,
            view=view,
            names=names,
            recovered_by_name=recovered_by_name,
            current_by_name=current_by_name,
        )
        _add_reverse_grain_entity_edges(
            edges,
            view=view,
            names=names,
            recovered_by_name=recovered_by_name,
            current_by_name=current_by_name,
        )

        upstream, _downstream = view.asset_table_graph()
        reports_by_key = {
            _table_key(name): report for name, report in zip(names, reports)
        }
        for target_name, report in zip(names, reports):
            recovered_process = canonical_semantic_code(
                _report_payload(report).get("business_process")
            )
            propagated_process = canonical_semantic_code(
                report.get("business_process")
            )
            if recovered_process or not propagated_process:
                continue
            for source_name in _resolved_upstream_table_names(
                upstream,
                target_name,
                names,
            ):
                source_report = reports_by_key.get(_table_key(source_name))
                if source_report is None:
                    continue
                if (
                    canonical_semantic_code(
                        source_report.get("business_process")
                    )
                    != propagated_process
                ):
                    continue
                edges.append(
                    PropagationProvenance(
                        source_table=source_name,
                        source_section="business_semantics",
                        target_table=target_name,
                        target_section="business_semantics",
                        evidence_kind="reconciled_process_lineage",
                    )
                )

    for source_name, payload in current_by_name.items():
        columns = payload.get("columns") or {}
        for group in _METRIC_GROUPS:
            for metric in columns.get(group) or []:
                if not isinstance(metric, dict) or (
                    metric.get("inference_source")
                    != "consumer_aggregate_evidence"
                ):
                    continue
                consumer = _known_table_name(
                    str(metric.get("consumer_table") or ""), names
                )
                if consumer:
                    edges.append(
                        PropagationProvenance(
                            source_table=consumer,
                            source_section="metrics",
                            target_table=source_name,
                            target_section="metrics",
                            evidence_kind="consumer_aggregate_promotion",
                        )
                    )

    reports_by_key = {
        _table_key(name): report for name, report in zip(names, reports)
    }
    for target_name, report in zip(names, reports):
        if str(report.get("business_process_mode") or "").casefold() != (
            "composite"
        ):
            continue
        if (
            str(
                _report_payload(report).get("business_process_mode") or ""
            ).casefold()
            == "composite"
        ):
            continue
        for source_ref in report.get("business_process_sources") or []:
            source_name = _known_table_name(str(source_ref), names)
            if (
                not source_name
                or _table_key(source_name) not in reports_by_key
            ):
                continue
            for source_section in ("business_semantics", "metrics"):
                edges.append(
                    PropagationProvenance(
                        source_table=source_name,
                        source_section=source_section,
                        target_table=target_name,
                        target_section="business_semantics",
                        evidence_kind="composite_process_contribution",
                    )
                )

    by_payload = {_stable_json(edge.to_dict()): edge for edge in edges}
    return tuple(
        sorted(
            by_payload.values(),
            key=lambda edge: (
                _table_key(edge.source_table),
                _SECTION_ORDER[edge.source_section],
                _table_key(edge.target_table),
                _SECTION_ORDER[edge.target_section],
                edge.evidence_kind,
            ),
        )
    )


def _mask_effective_inspection(
    payload: dict[str, Any],
    decision: SectionDecision,
) -> dict[str, Any]:
    effective = copy.deepcopy(payload)
    if decision.status("classification") != "active":
        for field in (
            "inferred_layer",
            "table_type",
            "dimension_role",
            "dimension_content_type",
        ):
            effective.pop(field, None)
    if decision.status("business_semantics") != "active":
        for field in (
            "business_process",
            "business_process_mode",
            "business_process_sources",
            "business_process_conflicts",
            "inferred_data_domain",
            "inferred_business_area",
        ):
            effective.pop(field, None)
    if decision.status("entities") != "active":
        effective.pop("entities", None)
    if decision.status("grain") != "active":
        effective.pop("grain", None)
    if decision.status("metrics") != "active":
        columns = copy.deepcopy(effective.get("columns") or {})
        for group in _METRIC_GROUPS:
            columns.pop(group, None)
        effective["columns"] = columns
    return effective


def prepare_inspection_for_propagation(
    result: TableInspectResult,
    *,
    metadata: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[TableInspectResult, SectionDecision]:
    """Resolve and mask one recovered result before cross-table evidence use."""
    report = result_to_dict(result)
    if report.get("recovered_candidate") is None:
        report["recovered_candidate"] = RecoveredInspectionCandidate.create(
            table_name=result.table_name,
            payload=_report_payload(report),
            repair_audit=result.repair_audit,
        ).to_dict()
    decision = build_local_section_decision(
        result.table_name,
        metadata,
        inspection_report=report,
        catalog=catalog,
    )
    effective_payload = _mask_effective_inspection(
        _report_payload(report),
        decision,
    )
    semantic_fields = {
        "inferred_layer",
        "table_type",
        "business_process",
        "business_process_mode",
        "business_process_sources",
        "business_process_conflicts",
        "inferred_data_domain",
        "inferred_business_area",
        "dimension_role",
        "dimension_content_type",
        "columns",
        "entities",
        "entity",
        "related_entities",
        "grain",
    }
    effective_report = {
        key: copy.deepcopy(value)
        for key, value in report.items()
        if key not in semantic_fields
    }
    effective_report.update(effective_payload)
    effective_report["issues"] = [issue.to_dict() for issue in decision.issues]
    effective_report["table_name"] = result.table_name
    effective_report["declared_layer"] = result.declared_layer
    effective_report["first_attempt_inferred_layer"] = (
        result.first_attempt_inferred_layer
        or str(_report_payload(report).get("inferred_layer") or "")
    )
    effective_report["context_hash"] = result.context_hash
    effective_report["catalog_snapshot_hash"] = result.catalog_snapshot_hash
    effective_report["asset_manifest_hash"] = result.asset_manifest_hash
    effective_report["resume_eligible"] = result.resume_eligible
    effective_result = dict_to_result(effective_report)
    effective_result.reuse_source = result.reuse_source
    return effective_result, decision


def _canonical_v3_model(
    metadata: dict[str, Any],
    decision: SectionDecision,
    *,
    operational_layer: str,
) -> dict[str, Any]:
    view = AssessmentModelSemantics.from_metadata(metadata)
    section_payloads = {
        section: view.active_payload(section) or {}
        for section in MODEL_SECTIONS
    }
    semantic_fields = {
        field
        for section in MODEL_SECTIONS
        for field in (
            MODEL_SECTION_FIELDS[section]
            + MODEL_SECTION_LEGACY_ALIAS_FIELDS[section]
        )
    }
    candidate = {
        key: copy.deepcopy(value)
        for key, value in metadata.items()
        if key not in semantic_fields
        and key not in {"version", "governance", "operational_layer"}
    }
    candidate["version"] = MODEL_SCHEMA_V3
    candidate["name"] = str(metadata.get("name") or decision.table_name)
    candidate["operational_layer"] = operational_layer
    for section in MODEL_SECTIONS:
        if decision.status(section) == "active":
            candidate.update(copy.deepcopy(section_payloads[section]))
    if decision.quarantined_sections:
        candidate["governance"] = {
            "status": "quarantined",
            "schema_version": 1,
            "withheld_sections": list(decision.quarantined_sections),
            "reasons": {
                section: list(decision.reasons_for(section))
                for section in decision.quarantined_sections
            },
        }
    return candidate


def _metadata_with_effective_inspection(
    metadata: dict[str, Any],
    report: dict[str, Any] | None,
    decision: SectionDecision,
) -> dict[str, Any]:
    candidate = copy.deepcopy(metadata)
    if report is None:
        return candidate
    payload = _current_report_payload(report)
    if decision.status("classification") == "active":
        classification_mapping = {
            "inferred_layer": "layer",
            "table_type": "table_type",
            "dimension_role": "dimension_role",
            "dimension_content_type": "dimension_content_type",
        }
        for source_field, target_field in classification_mapping.items():
            value = payload.get(source_field)
            if value:
                candidate[target_field] = copy.deepcopy(value)
    if decision.status("business_semantics") == "active":
        business_mapping = {
            "business_process": "business_process",
            "business_process_mode": "business_process_mode",
            "business_process_sources": "business_process_sources",
            "inferred_data_domain": "data_domain",
            "inferred_business_area": "business_area",
        }
        for source_field, target_field in business_mapping.items():
            value = payload.get(source_field)
            if value:
                candidate[target_field] = copy.deepcopy(value)
    if decision.status("entities") == "active" and payload.get("entities"):
        candidate["entities"] = copy.deepcopy(payload["entities"])
    if decision.status("grain") == "active" and payload.get("grain"):
        candidate["grain"] = copy.deepcopy(payload["grain"])
    return candidate


def _validate_effective_models(
    models: dict[str, dict[str, Any]],
    *,
    expected_tables: Iterable[str],
    catalog: dict[str, Any],
    validation_assets: dict[str, dict[str, Any]],
    effective_inspections: Iterable[EffectiveInspectionCandidate],
    decisions: Iterable[SectionDecision],
) -> dict[str, Any]:
    errors = []
    expected_names = tuple(str(table) for table in expected_tables)
    actual_names = tuple(str(table) for table in models)
    expected_keys = {_table_key(table) for table in expected_names}
    actual_keys = {_table_key(table) for table in actual_names}
    for identity_kind, names in (
        ("expected", expected_names),
        ("actual", actual_names),
    ):
        keys = [_table_key(name) for name in names]
        if "" in keys or len(keys) != len(set(keys)):
            errors.append(
                {
                    "type": "candidate_set_identity_conflict",
                    "table": "",
                    "message": (
                        f"{identity_kind} model identities are empty or "
                        "case-insensitively ambiguous"
                    ),
                }
            )
    if expected_keys != actual_keys:
        errors.append(
            {
                "type": "candidate_set_mismatch",
                "table": "",
                "message": "effective model set differs from asset manifest",
            }
        )
    catalog_sections = {
        "data_domain": "data_domains",
        "business_area": "business_areas",
        "business_process": "business_processes",
        "semantic_subject": "semantic_subjects",
    }
    inspections_by_key = {
        _table_key(candidate.table_name): candidate.payload
        for candidate in effective_inspections
    }
    for table_name, model in sorted(
        models.items(), key=lambda item: _table_key(item[0])
    ):
        try:
            validate_model_metadata(model, source=table_name)
        except UnsupportedModelGovernanceError as exc:
            errors.append(
                {
                    "type": "effective_model_invalid",
                    "table": table_name,
                    "message": str(exc),
                }
            )
            continue
        if _table_key(model.get("name")) != _table_key(table_name):
            errors.append(
                {
                    "type": "model_identity_mismatch",
                    "table": table_name,
                    "message": "model name differs from manifest table identity",
                }
            )
        asset = validation_assets.get(table_name) or {}
        if asset:
            errors.extend(_validate_execution(table_name, model, asset))
            errors.extend(_validate_entities(table_name, model, asset))
        inspection = inspections_by_key.get(_table_key(table_name))
        if inspection is not None:
            errors.extend(
                _validate_semantics(table_name, model, inspection, catalog)
            )
        if asset:
            ddl_columns = {
                str(column.get("name") or "").strip().casefold()
                for column in (asset.get("ddl") or {}).get("columns") or []
                if str(column.get("name") or "").strip()
            }
            for group in _METRIC_GROUPS:
                for metric in model.get(group) or []:
                    metric_name = str(
                        (
                            metric.get("name")
                            if isinstance(metric, dict)
                            else metric
                        )
                        or ""
                    ).strip()
                    if (
                        metric_name
                        and metric_name.casefold() not in ddl_columns
                    ):
                        errors.append(
                            {
                                "type": "formal_column_missing",
                                "table": table_name,
                                "message": (
                                    f"{group} column {metric_name} is absent "
                                    "from DDL"
                                ),
                            }
                        )
        for source in model.get("business_process_sources") or []:
            if not _known_table_name(str(source), expected_names):
                errors.append(
                    {
                        "type": "business_process_source_unknown",
                        "table": table_name,
                        "message": f"business_process_source={source} is unknown",
                    }
                )
        for field, catalog_section in catalog_sections.items():
            value = model.get(field)
            if value and canonical_semantic_code(value) not in _catalog_codes(
                catalog, catalog_section
            ):
                errors.append(
                    {
                        "type": "catalog_code_unconfirmed",
                        "table": table_name,
                        "message": f"{field}={value} is not confirmed",
                    }
                )
        for process in model.get("business_processes") or []:
            if canonical_semantic_code(process) not in _catalog_codes(
                catalog, "business_processes"
            ):
                errors.append(
                    {
                        "type": "catalog_code_unconfirmed",
                        "table": table_name,
                        "message": f"business_process={process} is not confirmed",
                    }
                )
    for decision in decisions:
        for issue in decision.hard_block_issues:
            errors.append(
                {
                    "type": "hard_block_issue",
                    "code": issue.code,
                    "table": decision.table_name,
                    "message": _issue_summary(issue),
                }
            )
    errors = list({_stable_json(error): error for error in errors}.values())
    errors.sort(
        key=lambda error: (
            _table_key(error.get("table")),
            str(error.get("type") or ""),
            str(error.get("code") or ""),
            str(error.get("message") or ""),
        )
    )
    return {
        "status": "blocked" if errors else "passed",
        "stage": "effective_candidate",
        "error_count": len(errors),
        "errors": errors,
    }


def resolve_generation_candidate(
    model_metadata: dict[str, dict[str, Any]],
    *,
    inspection_reports: Iterable[dict[str, Any]],
    catalog: dict[str, Any],
    operational_layers: dict[str, str],
    expected_tables: Iterable[str] | None = None,
    validation_assets: dict[str, dict[str, Any]] | None = None,
    generation_issues: Iterable[dict[str, Any]] = (),
    local_decisions: Iterable[dict[str, Any] | SectionDecision] = (),
    lineage_data: dict[str, Any] | None = None,
) -> ResolvedGenerationCandidate:
    """Resolve local decisions, provenance, fixed point, and v3 candidate."""
    models = copy.deepcopy(model_metadata)
    expected_table_names = tuple(
        expected_tables
        if expected_tables is not None
        else operational_layers.keys()
    )
    reports = [
        copy.deepcopy(report)
        for report in inspection_reports
        if isinstance(report, dict)
    ]
    report_by_key = {
        _table_key(report.get("table_name")): report for report in reports
    }
    local_decisions_by_key = {}
    for raw_decision in local_decisions:
        decision = (
            raw_decision
            if isinstance(raw_decision, SectionDecision)
            else SectionDecision.from_dict(raw_decision)
        )
        key = _table_key(decision.table_name)
        if not key or key in local_decisions_by_key:
            raise ValueError(
                "local section decision identities must be unique"
            )
        local_decisions_by_key[key] = decision
    additional_by_key: dict[str, list[InspectionIssue]] = {}
    for raw_issue in generation_issues:
        issue = InspectionIssue.from_dict(raw_issue)
        additional_by_key.setdefault(_table_key(issue.table), []).append(issue)

    local_decisions = []
    for table_name, metadata in sorted(
        models.items(), key=lambda item: _table_key(item[0])
    ):
        key = _table_key(table_name)
        report = report_by_key.get(key)
        prior_decision = local_decisions_by_key.get(key)
        if prior_decision is not None:
            if report is None:
                if any(
                    prior_decision.status(section) == "active"
                    for section in MODEL_SECTIONS
                ):
                    raise ValueError(
                        "uninspected local decisions cannot activate semantics"
                    )
                additional_issues = tuple(additional_by_key.get(key, ()))
                combined_issues = sort_issues(
                    (*prior_decision.issues, *additional_issues)
                )
                local_decisions.append(
                    SectionDecision(
                        table_name=prior_decision.table_name,
                        statuses=prior_decision.statuses,
                        reasons=prior_decision.reasons,
                        issues=combined_issues,
                        hard_block_issues=sort_issues(
                            (
                                *prior_decision.hard_block_issues,
                                *(
                                    issue
                                    for issue in combined_issues
                                    if issue.code in HARD_BLOCK_ISSUE_CODES
                                ),
                            )
                        ),
                    )
                )
                continue
            report = copy.deepcopy(report)
            report["issues"] = [
                issue.to_dict() for issue in prior_decision.issues
            ]
            report["status"] = "passed"
        local_decisions.append(
            build_local_section_decision(
                table_name,
                metadata,
                inspection_report=report,
                catalog=catalog,
                additional_issues=additional_by_key.get(key, ()),
            )
        )
    provenance = collect_propagation_provenance(
        reports,
        lineage_data=lineage_data,
    )
    decisions, iterations = resolve_fixed_point(local_decisions, provenance)
    decisions_by_key = {
        _table_key(item.table_name): item for item in decisions
    }

    effective_models = {}
    effective_inspections = []
    for table_name, metadata in sorted(
        models.items(), key=lambda item: _table_key(item[0])
    ):
        key = _table_key(table_name)
        decision = decisions_by_key[key]
        operational_layer = str(
            operational_layers.get(table_name)
            or operational_layers.get(key)
            or metadata.get("layer")
            or metadata.get("operational_layer")
            or ""
        ).upper()
        report = report_by_key.get(key)
        candidate_metadata = _metadata_with_effective_inspection(
            metadata,
            report,
            decision,
        )
        effective_models[table_name] = _canonical_v3_model(
            candidate_metadata,
            decision,
            operational_layer=operational_layer,
        )
        if report is not None:
            effective_inspections.append(
                EffectiveInspectionCandidate.create(
                    table_name=table_name,
                    payload=_mask_effective_inspection(
                        _current_report_payload(report),
                        decision,
                    ),
                    decision=decision,
                )
            )

    validation = _validate_effective_models(
        effective_models,
        expected_tables=expected_table_names,
        catalog=catalog,
        validation_assets=validation_assets or {},
        effective_inspections=effective_inspections,
        decisions=decisions,
    )
    return ResolvedGenerationCandidate(
        models_json=_stable_json(effective_models),
        decisions=decisions,
        provenance=provenance,
        effective_inspections=tuple(effective_inspections),
        fixed_point_iterations=iterations,
        validation_json=_stable_json(validation),
    )
