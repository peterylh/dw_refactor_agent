"""Shared semantic contracts for cold-start LLM inspection results."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


def canonical_semantic_code(value: Any) -> str:
    """Normalize one process or entity code for contract comparisons."""
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = re.sub(r"[\s\-/]+", "_", text)
    return re.sub(r"_+", "_", normalized).strip("_").upper()


def business_process_codes(
    table_process: Any,
    metric_groups: Iterable[Iterable[dict[str, Any]]],
) -> list[str]:
    """Return unique process codes from both table and metric evidence."""
    codes: list[str] = []
    candidates = [table_process]
    for metrics in metric_groups:
        candidates.extend(
            metric.get("business_process")
            for metric in metrics
            if isinstance(metric, dict)
        )
    for candidate in candidates:
        code = canonical_semantic_code(candidate)
        if code and code not in codes:
            codes.append(code)
    return codes


def validate_generate_inspection_contract(
    result: Any,
    ddl_columns: set[str],
) -> dict[str, list[str]]:
    """Validate raw LLM semantics that would otherwise fail publication."""
    validation: dict[str, list[str]] = {}
    table_type = str(result.table_type or "").strip().lower()
    if table_type == "fact":
        process_codes = business_process_codes(
            result.business_process,
            (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            ),
        )
        process_mode = str(
            getattr(result, "business_process_mode", "") or ""
        ).strip()
        process_sources = {
            str(source).strip().casefold()
            for source in (
                getattr(result, "business_process_sources", []) or []
            )
            if str(source).strip()
        }
        process_conflicts = [
            str(metric).strip()
            for metric in (
                getattr(result, "business_process_conflicts", []) or []
            )
            if str(metric).strip()
        ]
        if process_mode == "composite":
            issues = []
            if str(result.inferred_layer or "").upper() != "DWS":
                issues.append("composite process mode is only valid for DWS")
            if str(result.business_process or "").strip():
                issues.append(
                    "composite process mode must not declare one table process"
                )
            if len(process_sources) < 2:
                issues.append(
                    "composite process mode requires two contributing sources"
                )
            if not process_codes:
                issues.append(
                    "composite process mode requires an evidenced "
                    "business process"
                )
            if process_conflicts:
                issues.append(
                    "metrics have conflicting business process evidence: "
                    + ", ".join(sorted(process_conflicts))
                )
            if issues:
                validation["composite_process_invalid"] = issues
        elif not process_codes:
            validation["business_process_missing"] = [
                "fact inspection requires one business process"
            ]
        elif len(process_codes) > 1:
            validation["business_process_ambiguous"] = process_codes

    entities = [
        entity for entity in result.entities if isinstance(entity, dict)
    ]
    entity_codes = [
        canonical_semantic_code(entity.get("code"))
        for entity in entities
        if canonical_semantic_code(entity.get("code"))
    ]
    duplicate_codes = sorted(
        code for code, count in Counter(entity_codes).items() if count > 1
    )
    if duplicate_codes:
        validation["duplicate_entity_codes"] = duplicate_codes
    if table_type == "bridge":
        distinct_codes = sorted(set(entity_codes))
        if len(distinct_codes) < 2:
            validation["bridge_entities_invalid"] = [
                "bridge inspection requires at least two distinct entities"
            ]
        grain_entities = {
            canonical_semantic_code(code)
            for code in (result.grain or {}).get("entities") or []
            if canonical_semantic_code(code)
        }
        if set(distinct_codes) != grain_entities:
            validation["bridge_grain_invalid"] = [
                "bridge grain.entities must cover every participating entity"
            ]
        metric_names = [
            str(metric.get("name") or "").strip()
            for metrics in (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            )
            for metric in metrics
            if isinstance(metric, dict)
            and str(metric.get("name") or "").strip()
        ]
        process_codes = business_process_codes(
            result.business_process,
            (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            ),
        )
        if process_codes or metric_names:
            issues = []
            if process_codes:
                issues.append(
                    "bridge must not declare business_process: "
                    + ", ".join(process_codes)
                )
            if metric_names:
                issues.append(
                    "bridge must not declare metrics: "
                    + ", ".join(sorted(set(metric_names)))
                )
            validation["bridge_semantics_invalid"] = issues

    ddl_by_name = {
        str(column).strip().casefold()
        for column in ddl_columns
        if str(column).strip()
    }
    entity_key_issues = []
    for entity in entities:
        code = canonical_semantic_code(entity.get("code")) or "<missing>"
        key_columns = [
            str(column).strip()
            for column in entity.get("key_columns") or []
            if str(column).strip()
        ]
        if not key_columns:
            entity_key_issues.append(f"{code}: key_columns is required")
        for key_column in key_columns:
            if key_column.casefold() not in ddl_by_name:
                entity_key_issues.append(
                    f"{code}: key column {key_column} is absent from DDL"
                )
    if entity_key_issues:
        validation["entity_key_missing"] = entity_key_issues

    grain = result.grain if isinstance(result.grain, dict) else {}
    known_entity_codes = set(entity_codes)
    unknown_grain_entities = sorted(
        {
            canonical_semantic_code(code)
            for code in grain.get("entities") or []
            if canonical_semantic_code(code)
            and canonical_semantic_code(code) not in known_entity_codes
        }
    )
    if unknown_grain_entities:
        validation["grain_entity_unknown"] = unknown_grain_entities

    missing_grain_columns = []
    grain_columns = list(grain.get("additional_key_columns") or [])
    time_column = str(grain.get("time_column") or "").strip()
    if time_column:
        grain_columns.append(time_column)
    for column in grain_columns:
        column_name = str(column).strip()
        if column_name and column_name.casefold() not in ddl_by_name:
            missing_grain_columns.append(column_name)
    if missing_grain_columns:
        validation["grain_column_missing"] = sorted(set(missing_grain_columns))

    if str(result.table_type or "").strip().lower() == "dimension":
        primary_codes = [
            canonical_semantic_code(entity.get("code"))
            for entity in entities
            if str(entity.get("type") or "").strip().lower() == "primary"
        ]
        if len(primary_codes) != 1:
            validation["dimension_primary_entity_invalid"] = [
                "dimension inspection requires exactly one primary entity"
            ]
    return validation
