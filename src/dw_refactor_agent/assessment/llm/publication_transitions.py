"""Pure refresh, inspection-breaker, and publication transition planning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from dw_refactor_agent.assessment.llm.generation_candidate_resolver import (
    SectionDecision,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    HARD_BLOCK_ISSUE_CODES,
    InspectionIssue,
    ParsedInspectionCandidate,
    UnknownInspectionIssueError,
)
from dw_refactor_agent.assessment.semantic_models import (
    AssessmentModelSemantics,
)
from dw_refactor_agent.config import MODEL_SECTIONS
from dw_refactor_agent.config.model_governance import STRUCTURE_SECTIONS
from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    short_table_name,
)

_BREAKER_FAILURE_CODES = frozenset(
    {"inspection_transport_failed", "inspection_content_parse_failed"}
)
_CONFIGURATION_FAILURE_CODES = frozenset(
    {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_request_rejected",
    }
)
_CANDIDATE_STATUSES = frozenset(
    {"complete", "quarantined", "blocked", "unknown"}
)
_STRUCTURE_BUNDLE_LAYERS = frozenset({"DIM", "DWD", "DWS"})


def _identity_key(value: Any) -> str:
    return identifier_match_key(
        canonical_qualified_identifier(str(value or ""))
    )


def _short_key(value: Any) -> str:
    return _identity_key(short_table_name(str(value or "")))


def _identity_index(names: Iterable[str]) -> dict[str, str]:
    index = {}
    for raw_name in names:
        name = str(raw_name or "")
        key = _identity_key(name)
        if not key or key in index:
            raise ValueError("table identities must be non-empty and unique")
        index[key] = name
    return index


def _resolve_identity(reference: Any, names: Iterable[str]) -> str:
    index = _identity_index(names)
    exact = index.get(_identity_key(reference))
    if exact:
        return exact
    wanted_short = _short_key(reference)
    matches = [
        name for name in index.values() if _short_key(name) == wanted_short
    ]
    return matches[0] if len(matches) == 1 else ""


def _issues_from_reports(
    reports: Iterable[dict[str, Any]],
    target_tables: Iterable[str],
) -> tuple[InspectionIssue, ...]:
    issues = []
    for report in reports:
        report_table = _resolve_identity(
            report.get("table_name"), target_tables
        )
        raw_issues = report.get("issues") or []
        if not isinstance(raw_issues, list):
            raise UnknownInspectionIssueError(
                "inspection report issues must be a list"
            )
        for item in raw_issues:
            if not isinstance(item, dict):
                raise UnknownInspectionIssueError(
                    "inspection report issue must be an object"
                )
            issue = InspectionIssue.from_dict(item)
            if (
                issue.table
                and _resolve_identity(issue.table, target_tables)
                != report_table
            ):
                raise UnknownInspectionIssueError(
                    "inspection issue table differs from its report"
                )
            issues.append(issue)
    return tuple(issues)


@dataclass(frozen=True)
class InspectionRunTransition:
    """Run-level breaker decision independent from semantic quarantine."""

    status: str
    target_tables: tuple[str, ...]
    settled_tables: tuple[str, ...]
    valid_structured_tables: tuple[str, ...]
    service_failure_tables: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    candidate_status_override: str = ""
    recoverable: bool = False
    retryable: bool = False
    retry_action: str = ""

    @property
    def triggered(self) -> bool:
        return self.status in {"inspection_failure", "blocked"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "triggered": self.triggered,
            "target_count": len(self.target_tables),
            "target_tables": list(self.target_tables),
            "settled_count": len(self.settled_tables),
            "settled_tables": list(self.settled_tables),
            "valid_structured_count": len(self.valid_structured_tables),
            "valid_structured_tables": list(self.valid_structured_tables),
            "service_failure_count": len(self.service_failure_tables),
            "service_failure_tables": list(self.service_failure_tables),
            "reasons": list(self.reasons),
            "candidate_status_override": self.candidate_status_override,
            "recoverable": self.recoverable,
            "retryable": self.retryable,
            "retry_action": self.retry_action,
        }


def plan_inspection_run_transition(
    *,
    llm_enabled: bool,
    inspection_targets: Iterable[str],
    reports: Iterable[dict[str, Any]],
    settled_tables: Iterable[str] | None = None,
    run_issues: Iterable[dict[str, Any] | InspectionIssue] = (),
) -> InspectionRunTransition:
    """Apply the project-level inspection breaker to settled typed reports."""
    targets = tuple(
        sorted(_identity_index(inspection_targets).values(), key=_identity_key)
    )
    if not llm_enabled:
        return InspectionRunTransition(
            status="not_applicable",
            target_tables=targets,
            settled_tables=(),
            valid_structured_tables=(),
        )

    raw_reports = tuple(reports)
    if any(not isinstance(report, dict) for report in raw_reports):
        return InspectionRunTransition(
            status="blocked",
            target_tables=targets,
            settled_tables=(),
            valid_structured_tables=(),
            reasons=("invalid_inspection_candidate_contract",),
            candidate_status_override="unknown",
        )
    report_items = raw_reports
    report_by_target = {}
    unresolved_reports = []
    for report in report_items:
        resolved = _resolve_identity(report.get("table_name"), targets)
        if not resolved or resolved in report_by_target:
            unresolved_reports.append(str(report.get("table_name") or ""))
            continue
        report_by_target[resolved] = report

    settled_refs = (
        tuple(settled_tables)
        if settled_tables is not None
        else tuple(report.get("table_name") for report in report_items)
    )
    settled = set()
    unresolved_settled = []
    for reference in settled_refs:
        resolved = _resolve_identity(reference, targets)
        if not resolved:
            unresolved_settled.append(str(reference or ""))
        else:
            settled.add(resolved)

    try:
        issues = list(_issues_from_reports(report_items, targets))
        for raw_issue in run_issues:
            issues.append(
                raw_issue
                if isinstance(raw_issue, InspectionIssue)
                else InspectionIssue.from_dict(raw_issue)
            )
    except (TypeError, ValueError, UnknownInspectionIssueError):
        return InspectionRunTransition(
            status="blocked",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=(),
            reasons=("invalid_inspection_issue_contract",),
            candidate_status_override="unknown",
        )

    issue_codes = {issue.code for issue in issues}
    failures_by_table = {
        _resolve_identity(issue.table, targets)
        for issue in issues
        if issue.code in _BREAKER_FAILURE_CODES
    }
    failures_by_table.discard("")
    service_failures = tuple(sorted(failures_by_table, key=_identity_key))
    valid = []
    invalid_candidate_contract = False
    issue_codes_by_table = {}
    for issue in issues:
        issue_table = _resolve_identity(issue.table, targets)
        if issue_table:
            issue_codes_by_table.setdefault(issue_table, set()).add(issue.code)
    for target, report in report_by_target.items():
        parsed = report.get("parsed_candidate")
        if parsed is None:
            if not issue_codes_by_table.get(target, set()).intersection(
                _BREAKER_FAILURE_CODES
                | _CONFIGURATION_FAILURE_CODES
                | HARD_BLOCK_ISSUE_CODES
            ):
                invalid_candidate_contract = True
            continue
        try:
            parsed_candidate = ParsedInspectionCandidate.from_dict(parsed)
        except (TypeError, ValueError):
            invalid_candidate_contract = True
            continue
        if _resolve_identity(parsed_candidate.table_name, targets) != target:
            invalid_candidate_contract = True
            continue
        valid.append(target)
    if invalid_candidate_contract or unresolved_reports:
        return InspectionRunTransition(
            status="blocked",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
            reasons=("invalid_inspection_candidate_contract",),
            candidate_status_override="unknown",
        )

    if issue_codes.intersection(HARD_BLOCK_ISSUE_CODES):
        return InspectionRunTransition(
            status="blocked",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
            service_failure_tables=service_failures,
            reasons=("internal_or_deterministic_inspection_block",),
            candidate_status_override="unknown",
        )
    if issue_codes.intersection(_CONFIGURATION_FAILURE_CODES):
        return InspectionRunTransition(
            status="inspection_failure",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
            service_failure_tables=service_failures,
            reasons=("inspection_configuration_failure",),
            candidate_status_override="quarantined",
            recoverable=True,
            retry_action="fix_configuration",
        )
    if unresolved_settled or settled != set(targets):
        return InspectionRunTransition(
            status="inspection_failure",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
            reasons=("inspection_settled_set_incomplete",),
            candidate_status_override="unknown",
            recoverable=True,
            retry_action="resume_recovery",
        )

    if targets and not valid:
        return InspectionRunTransition(
            status="inspection_failure",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=(),
            service_failure_tables=service_failures,
            reasons=("inspection_zero_valid_structured_results",),
            candidate_status_override="quarantined",
            recoverable=True,
            retryable=True,
            retry_action="retry",
        )
    if len(service_failures) > len(targets) / 2:
        return InspectionRunTransition(
            status="inspection_failure",
            target_tables=targets,
            settled_tables=tuple(sorted(settled, key=_identity_key)),
            valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
            service_failure_tables=service_failures,
            reasons=("inspection_service_degraded",),
            candidate_status_override="quarantined",
            recoverable=True,
            retryable=True,
            retry_action="retry",
        )
    return InspectionRunTransition(
        status="healthy",
        target_tables=targets,
        settled_tables=tuple(sorted(settled, key=_identity_key)),
        valid_structured_tables=tuple(sorted(valid, key=_identity_key)),
        service_failure_tables=service_failures,
    )


@dataclass(frozen=True)
class PublicationTransition:
    """Candidate and gate outcome without performing filesystem writes."""

    status: str
    candidate_status: str
    published: bool
    complete: bool
    formal_files_state: str
    finalization_status: str
    recovery_required: bool
    would_publish_status: str = ""
    reason: str = ""
    recoverable: bool = False
    retryable: bool = False
    retry_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = {
            "status": self.status,
            "candidate_status": self.candidate_status,
            "published": self.published,
            "complete": self.complete,
            "formal_files_state": self.formal_files_state,
            "finalization_status": self.finalization_status,
            "recovery_required": self.recovery_required,
            "recoverable": self.recoverable,
            "retryable": self.retryable,
        }
        for key, value in (
            ("would_publish_status", self.would_publish_status),
            ("reason", self.reason),
            ("retry_action", self.retry_action),
        ):
            if value:
                result[key] = value
        return result


def plan_publication_transition(
    *,
    candidate_status: str,
    inspection_transition: InspectionRunTransition,
    dry_run: bool = False,
    require_complete: bool = False,
) -> PublicationTransition:
    """Distinguish hard block, breaker, strict rejection, and publication."""
    if candidate_status not in _CANDIDATE_STATUSES:
        raise ValueError(f"unknown candidate status: {candidate_status!r}")
    effective_candidate_status = (
        candidate_status
        if candidate_status in {"blocked", "unknown"}
        else (
            inspection_transition.candidate_status_override or candidate_status
        )
    )
    if (
        inspection_transition.status == "blocked"
        or candidate_status == "blocked"
    ):
        planned_status = "blocked"
        reason = "deterministic_or_internal_block"
    elif inspection_transition.status == "inspection_failure":
        planned_status = "not_published_inspection_failure"
        reason = (
            inspection_transition.reasons[0]
            if inspection_transition.reasons
            else "inspection_service_degraded"
        )
    elif candidate_status == "unknown":
        planned_status = "blocked"
        reason = "deterministic_or_internal_block"
    elif effective_candidate_status == "quarantined" and require_complete:
        planned_status = "not_published_incomplete"
        reason = "require_complete"
    elif effective_candidate_status == "quarantined":
        planned_status = "published_with_quarantine"
        reason = ""
    else:
        planned_status = "published"
        reason = ""

    status = "dry_run" if dry_run else planned_status
    published = not dry_run and planned_status in {
        "published",
        "published_with_quarantine",
    }
    return PublicationTransition(
        status=status,
        would_publish_status=planned_status if dry_run else "",
        candidate_status=effective_candidate_status,
        published=published,
        complete=effective_candidate_status == "complete",
        formal_files_state="published" if published else "unchanged",
        finalization_status="not_started",
        recovery_required=False,
        reason=reason,
        recoverable=inspection_transition.recoverable,
        retryable=inspection_transition.retryable,
        retry_action=inspection_transition.retry_action,
    )


@dataclass(frozen=True)
class RefreshSectionTransition:
    table_name: str
    section: str
    existing_status: str
    candidate_status: str
    effective_status: str
    effective_source: str
    action: str
    reason: str = ""
    clear_governance: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table_name,
            "section": self.section,
            "existing_status": self.existing_status,
            "candidate_status": self.candidate_status,
            "effective_status": self.effective_status,
            "effective_source": self.effective_source,
            "action": self.action,
            "reason": self.reason,
            "clear_governance": self.clear_governance,
        }


@dataclass(frozen=True)
class RefreshTransitionPlan:
    status: str
    transitions: tuple[RefreshSectionTransition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blocked_transition_count": sum(
                item.action.startswith("blocked_") for item in self.transitions
            ),
            "transitions": [item.to_dict() for item in self.transitions],
        }


def _candidate_issue_reason(decision: SectionDecision, section: str) -> str:
    if any(
        issue.retryable and section in issue.sections
        for issue in decision.issues
    ):
        return "retryable_inspection_failure"
    return "semantic_quarantine"


def plan_refresh_transitions(
    existing_models: Mapping[str, Mapping[str, Any]],
    *,
    candidate_decisions: Iterable[SectionDecision] = (),
    requested_sections: Iterable[str] = MODEL_SECTIONS,
    llm_enabled: bool = True,
    retention_eligible: Mapping[str, Iterable[str]] | None = None,
) -> RefreshTransitionPlan:
    """Plan section-level refresh without mutating or writing formal models."""
    requested = tuple(dict.fromkeys(str(item) for item in requested_sections))
    unknown_sections = set(requested) - set(MODEL_SECTIONS)
    if unknown_sections:
        raise ValueError(
            "unknown requested model sections: "
            + ", ".join(sorted(unknown_sections))
        )
    model_index = _identity_index(existing_models)
    decisions = {}
    for decision in candidate_decisions:
        table_name = _resolve_identity(
            decision.table_name, model_index.values()
        )
        key = _identity_key(table_name)
        if not key or key in decisions:
            raise ValueError(
                "candidate decision identities must resolve uniquely"
            )
        decisions[key] = decision
    eligible_by_key = None
    if retention_eligible is not None:
        eligible_by_key = {}
        for reference, sections in retention_eligible.items():
            table_name = _resolve_identity(reference, model_index.values())
            key = _identity_key(table_name)
            if not key or key in eligible_by_key:
                raise ValueError("retention identities must resolve uniquely")
            eligible_by_key[key] = frozenset(sections)

    def active_retention_allowed(table_name: str, section: str) -> bool:
        return eligible_by_key is not None and section in (
            eligible_by_key.get(_identity_key(table_name)) or ()
        )

    transitions = []
    operational_layers = {}
    for table_name, metadata in sorted(
        existing_models.items(), key=lambda item: _identity_key(item[0])
    ):
        view = AssessmentModelSemantics.from_metadata(
            metadata, source=table_name
        )
        operational_layers[_identity_key(table_name)] = str(
            view.operational_layer or ""
        ).upper()
        decision = decisions.get(_identity_key(table_name))
        decision_is_blocked = bool(
            decision
            and (
                decision.hard_block_issues
                or any(
                    issue.code in HARD_BLOCK_ISSUE_CODES
                    for issue in decision.issues
                )
            )
        )
        for section in MODEL_SECTIONS:
            existing_status = view.status(section)
            candidate_status = (
                decision.status(section) if decision is not None else "missing"
            )
            common = {
                "table_name": table_name,
                "section": section,
                "existing_status": existing_status,
                "candidate_status": candidate_status,
            }
            if decision_is_blocked:
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status="quarantined",
                        effective_source="none",
                        action="blocked_hard_block_issue",
                        reason="internal_or_deterministic_block",
                    )
                )
                continue
            if section not in requested:
                if (
                    existing_status == "active"
                    and not active_retention_allowed(table_name, section)
                ):
                    transitions.append(
                        RefreshSectionTransition(
                            **common,
                            effective_status="quarantined",
                            effective_source="none",
                            action="blocked_existing_active_stale",
                            reason="retention_fingerprint_changed",
                        )
                    )
                    continue
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status=existing_status,
                        effective_source="existing",
                        action="preserve_unrequested",
                    )
                )
                continue
            if not llm_enabled:
                if (
                    existing_status == "active"
                    and not active_retention_allowed(table_name, section)
                ):
                    transitions.append(
                        RefreshSectionTransition(
                            **common,
                            effective_status="quarantined",
                            effective_source="none",
                            action="blocked_existing_active_stale",
                            reason="retention_fingerprint_changed",
                        )
                    )
                    continue
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status=existing_status,
                        effective_source="existing",
                        action=(
                            "retain_existing_active"
                            if existing_status == "active"
                            else "retain_existing_governance"
                        ),
                        reason="inspection_not_requested",
                    )
                )
                continue
            if decision is None:
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status="quarantined",
                        effective_source="none",
                        action="blocked_candidate_missing",
                        reason="inspection_state_unknown",
                    )
                )
                continue
            if (
                candidate_status == "quarantined"
                and existing_status == "active"
            ):
                retention_allowed = active_retention_allowed(
                    table_name, section
                )
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status=(
                            "active" if retention_allowed else "quarantined"
                        ),
                        effective_source=(
                            "existing" if retention_allowed else "none"
                        ),
                        action=(
                            "retain_existing_active"
                            if retention_allowed
                            else "blocked_existing_active_stale"
                        ),
                        reason=(
                            _candidate_issue_reason(decision, section)
                            if retention_allowed
                            else "retention_fingerprint_changed"
                        ),
                    )
                )
                continue
            if candidate_status == "active":
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status="active",
                        effective_source="candidate",
                        action=(
                            "activate_candidate"
                            if existing_status == "quarantined"
                            else "update_active"
                        ),
                        clear_governance=existing_status == "quarantined",
                    )
                )
                continue
            if candidate_status == "quarantined":
                transitions.append(
                    RefreshSectionTransition(
                        **common,
                        effective_status="quarantined",
                        effective_source="candidate",
                        action="retain_candidate_quarantine",
                        reason=_candidate_issue_reason(decision, section),
                    )
                )
                continue
            transitions.append(
                RefreshSectionTransition(
                    **common,
                    effective_status="not_applicable",
                    effective_source="none",
                    action="apply_candidate_not_applicable",
                    clear_governance=existing_status == "quarantined",
                )
            )
    transitions_by_table = {}
    for item in transitions:
        transitions_by_table.setdefault(
            _identity_key(item.table_name), []
        ).append(item)
    invalid_bundle_tables = set()
    for table_key, table_transitions in transitions_by_table.items():
        if operational_layers.get(table_key) not in _STRUCTURE_BUNDLE_LAYERS:
            continue
        if any(
            item.action.startswith("blocked_") for item in table_transitions
        ):
            continue
        statuses = {
            item.section: item.effective_status for item in table_transitions
        }
        structure_statuses = [
            statuses[section] for section in STRUCTURE_SECTIONS
        ]
        structure_quarantined = any(
            status == "quarantined" for status in structure_statuses
        )
        if (
            structure_quarantined
            and not all(
                status == "quarantined" for status in structure_statuses
            )
        ) or (structure_quarantined and statuses["metrics"] != "quarantined"):
            invalid_bundle_tables.add(table_key)
    if invalid_bundle_tables:
        transitions = [
            (
                replace(
                    item,
                    effective_status="quarantined",
                    effective_source="none",
                    action="blocked_structure_bundle_incomplete",
                    reason="structure_bundle_incomplete",
                    clear_governance=False,
                )
                if _identity_key(item.table_name) in invalid_bundle_tables
                else item
            )
            for item in transitions
        ]
    blocked = any(item.action.startswith("blocked_") for item in transitions)
    return RefreshTransitionPlan(
        status="blocked" if blocked else "ready",
        transitions=tuple(transitions),
    )


def plan_no_llm_generation_decisions(
    inspection_targets: Iterable[str],
    model_names: Iterable[str],
) -> tuple[SectionDecision, ...]:
    """Create explicit all-semantic quarantine for uninspected MID models."""
    names = tuple(_identity_index(model_names).values())
    decisions = []
    seen = set()
    for target in inspection_targets:
        table_name = _resolve_identity(target, names)
        key = _identity_key(table_name)
        if not key or key in seen:
            raise ValueError(
                "inspection targets must resolve uniquely to candidate models"
            )
        seen.add(key)
        decisions.append(
            SectionDecision(
                table_name=table_name,
                statuses=tuple(
                    (section, "quarantined") for section in MODEL_SECTIONS
                ),
                reasons=tuple(
                    (section, ("inspection_not_requested",))
                    for section in MODEL_SECTIONS
                ),
            )
        )
    return tuple(
        sorted(decisions, key=lambda item: _identity_key(item.table_name))
    )
