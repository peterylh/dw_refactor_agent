"""Shared business metadata helpers for assess scoring."""

from __future__ import annotations

from dw_refactor_agent.assessment.scoring.config import (
    BUSINESS_AREA_LAYERS,
    DATA_DOMAIN_LAYERS,
)


def _declared_data_domain(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    return str(
        model_metadata.get(table_name, {}).get("data_domain") or ""
    ).strip()


def _declared_business_area(
    model_metadata: dict | None, table_name: str
) -> str:
    if not model_metadata:
        return ""
    return (
        str(model_metadata.get(table_name, {}).get("business_area") or "")
        .strip()
        .upper()
    )


def _data_domain_applies(layer: str) -> bool:
    return str(layer or "").upper() in DATA_DOMAIN_LAYERS


def _business_area_applies(layer: str) -> bool:
    return str(layer or "").upper() in BUSINESS_AREA_LAYERS


def _valid_inferred_data_domain(result, business_domain_config) -> str:
    if not business_domain_config:
        return str(getattr(result, "inferred_data_domain", "") or "").strip()
    normalized = business_domain_config.normalize_domain(
        getattr(result, "inferred_data_domain", "")
    )
    return (
        normalized
        if business_domain_config.is_valid_domain(normalized)
        else ""
    )


def _valid_inferred_business_area(result, business_domain_config) -> str:
    if not business_domain_config:
        return (
            str(getattr(result, "inferred_business_area", "") or "")
            .strip()
            .upper()
        )
    normalized = business_domain_config.normalize_business_area(
        getattr(result, "inferred_business_area", "")
    )
    return (
        normalized
        if business_domain_config.is_valid_business_area(normalized)
        else ""
    )
