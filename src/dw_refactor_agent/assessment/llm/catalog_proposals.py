"""Audit-only catalog proposals derived from table inspection results."""

from __future__ import annotations

import json
from typing import Any

from dw_refactor_agent.assessment.llm.inspection_contract import (
    business_process_codes,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    _normalize_catalog_code,
)

CATALOG_PROPOSAL_SCHEMA_VERSION = 1
_CATALOG_SECTION_BY_KIND = {
    "business_process": "business_processes",
    "semantic_subject": "semantic_subjects",
}


def empty_catalog_proposal_report() -> dict[str, Any]:
    return {
        "catalog_proposal_schema_version": CATALOG_PROPOSAL_SCHEMA_VERSION,
        "catalog_proposals": [],
        "catalog_proposal_count": 0,
        "catalog_proposal_conflicts": [],
        "catalog_proposal_conflict_count": 0,
    }


def _confirmed_codes(catalog: dict[str, Any]) -> dict[str, set[str]]:
    confirmed = {}
    for kind, section in _CATALOG_SECTION_BY_KIND.items():
        confirmed[kind] = {
            code
            for entry in catalog.get(section) or []
            if isinstance(entry, dict)
            for code in [_normalize_catalog_code(entry.get("code"))]
            if code
        }
    return confirmed


def _display_name_from_code(code: str) -> str:
    return str(code or "").replace("_", " ").title()


def _primary_entity(result: TableInspectResult) -> dict[str, Any]:
    entities = [
        entity for entity in result.entities if isinstance(entity, dict)
    ]
    primary = next(
        (
            entity
            for entity in entities
            if str(entity.get("type") or "").casefold() == "primary"
        ),
        None,
    )
    return dict(primary or (entities[0] if entities else {}))


def _business_process_evidence(
    result: TableInspectResult,
    code: str,
) -> list[dict[str, Any]]:
    evidence = []
    if _normalize_catalog_code(result.business_process) == code:
        evidence.append(
            {
                "type": "table_assignment",
                "table": result.table_name,
                "field": "business_process",
                "value": result.business_process,
            }
        )
    for group in (
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
    ):
        for metric in result.columns.get(group) or []:
            if (
                not isinstance(metric, dict)
                or _normalize_catalog_code(metric.get("business_process"))
                != code
            ):
                continue
            evidence.append(
                {
                    "type": "metric_assignment",
                    "table": result.table_name,
                    "group": group,
                    "metric": str(metric.get("name") or ""),
                    "value": str(metric.get("business_process") or ""),
                }
            )
    return evidence


def _result_proposal_items(
    result: TableInspectResult,
) -> list[dict[str, Any]]:
    if result.status == "blocked":
        return []
    items = []
    if result.table_type == "fact":
        for raw_code in business_process_codes(
            result.business_process,
            (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            ),
        ):
            code = _normalize_catalog_code(raw_code)
            if not code:
                continue
            items.append(
                {
                    "kind": "business_process",
                    "code": code,
                    "display_name": _display_name_from_code(code),
                    "source_table": result.table_name,
                    "evidence": _business_process_evidence(result, code),
                }
            )
    if result.table_type == "dimension":
        entity = _primary_entity(result)
        code = _normalize_catalog_code(entity.get("code"))
        if code:
            items.append(
                {
                    "kind": "semantic_subject",
                    "code": code,
                    "display_name": str(entity.get("name") or "").strip()
                    or _display_name_from_code(code),
                    "source_table": result.table_name,
                    "evidence": [
                        {
                            "type": "primary_entity",
                            "table": result.table_name,
                            "entity_code": str(entity.get("code") or ""),
                            "key_columns": sorted(
                                {
                                    str(column).strip()
                                    for column in entity.get("key_columns")
                                    or []
                                    if str(column).strip()
                                },
                                key=str.casefold,
                            ),
                        }
                    ],
                }
            )
    return items


def _dedupe_display_values(values: list[str]) -> list[str]:
    by_key = {}
    for value in values:
        stripped = str(value or "").strip()
        if stripped:
            by_key.setdefault(stripped.casefold(), stripped)
    return sorted(by_key.values(), key=lambda item: (item.casefold(), item))


def _dedupe_source_tables(values: list[str]) -> list[str]:
    by_key = {}
    for value in values:
        stripped = str(value or "").strip()
        if stripped:
            by_key.setdefault(stripped.casefold(), stripped)
    return sorted(by_key.values(), key=lambda item: (item.casefold(), item))


def _dedupe_evidence(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {
        json.dumps(value, ensure_ascii=False, sort_keys=True): value
        for value in values
        if isinstance(value, dict)
    }
    return [dict(by_key[key]) for key in sorted(by_key)]


def build_catalog_proposal_report(
    results: list[TableInspectResult],
    *,
    confirmed_catalog: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic proposals without mutating the confirmed catalog."""
    confirmed = _confirmed_codes(confirmed_catalog)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for result in sorted(
        results or [],
        key=lambda item: (item.table_name.casefold(), item.table_name),
    ):
        for item in _result_proposal_items(result):
            kind = item["kind"]
            code = item["code"]
            if code in confirmed[kind]:
                continue
            group = grouped.setdefault(
                (kind, code),
                {
                    "display_names": [],
                    "source_tables": [],
                    "evidence": [],
                },
            )
            group["display_names"].append(item["display_name"])
            group["source_tables"].append(item["source_table"])
            group["evidence"].extend(item["evidence"])

    proposals = []
    conflicts = []
    for (kind, code), group in sorted(grouped.items()):
        display_names = _dedupe_display_values(group["display_names"])
        source_tables = _dedupe_source_tables(group["source_tables"])
        conflict = len(display_names) > 1
        proposal = {
            "kind": kind,
            "code": code,
            "display_name": None if conflict else display_names[0],
            "source_tables": source_tables,
            "evidence": _dedupe_evidence(group["evidence"]),
            "status": "conflict" if conflict else "proposed",
        }
        if conflict:
            proposal["display_name_candidates"] = display_names
            conflicts.append(
                {
                    "kind": kind,
                    "code": code,
                    "display_name_candidates": display_names,
                    "source_tables": source_tables,
                    "status": "conflict",
                }
            )
        proposals.append(proposal)

    return {
        "catalog_proposal_schema_version": CATALOG_PROPOSAL_SCHEMA_VERSION,
        "catalog_proposals": proposals,
        "catalog_proposal_count": len(proposals),
        "catalog_proposal_conflicts": conflicts,
        "catalog_proposal_conflict_count": len(conflicts),
    }
