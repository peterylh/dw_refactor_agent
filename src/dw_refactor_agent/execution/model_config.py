"""Execution model configuration validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dw_refactor_agent.config import (
    GovernedModelMetadata,
    UnsupportedModelGovernanceError,
    ensure_governed_model,
    get_execution_contract,
)


class ExecutionConfigError(ValueError):
    """Raised when model execution configuration is invalid."""


ALLOWED_MATERIALIZED = {"incremental", "full"}
ALLOWED_STRATEGIES = {
    "replay_slices",
    "companion",
    "legacy_full_refresh",
    "replace_all",
}
ALLOWED_PERIODS = {"D", "M", "W", "H"}
EXECUTION_CONFIG_FIELDS = {"materialized", "full_refresh_strategy"}


@dataclass(frozen=True)
class SliceConfig:
    param: str
    column: str
    period: str


def governed_execution_model(
    job_name: str,
    raw_model: Mapping[str, Any],
    *,
    source: str = "",
) -> GovernedModelMetadata:
    """Validate a formal model at the execution boundary."""
    if not isinstance(raw_model, Mapping):
        raise ExecutionConfigError(
            f"[{job_name}] model metadata must be a mapping"
        )
    raw_config = raw_model.get("config") or {}
    if isinstance(raw_config, dict):
        deprecated = sorted(EXECUTION_CONFIG_FIELDS.intersection(raw_config))
        if deprecated:
            old_fields = ", ".join(f"config.{key}" for key in deprecated)
            new_fields = ", ".join(f"execution.{key}" for key in deprecated)
            raise ExecutionConfigError(
                f"[{job_name}] {old_fields} is no longer supported; "
                f"use {new_fields}"
            )
    try:
        return ensure_governed_model(
            raw_model,
            source=source or f"execution model {job_name}",
        )
    except UnsupportedModelGovernanceError as exc:
        raise ExecutionConfigError(f"[{job_name}] {exc}") from exc


def execution_config_for_model(job_name: str, raw_model: dict) -> dict:
    model = governed_execution_model(job_name, raw_model)
    try:
        return get_execution_contract(model)
    except UnsupportedModelGovernanceError as exc:
        raise ExecutionConfigError(f"[{job_name}] {exc}") from exc


def normalize_materialized(job_name: str, value: Any) -> str:
    materialized = str(value or "incremental").strip().lower()
    if materialized == "snapshot":
        raise ExecutionConfigError(
            f"[{job_name}] materialized: snapshot is no longer supported. "
            "Migrate to:\n"
            "execution:\n"
            "  materialized: incremental\n"
            "  slice:\n"
            "    param: etl_date\n"
            "    column: snapshot_date\n"
            "    period: D"
        )
    if materialized not in ALLOWED_MATERIALIZED:
        allowed = ", ".join(sorted(ALLOWED_MATERIALIZED))
        raise ExecutionConfigError(
            f"[{job_name}] execution.materialized must be one of: {allowed}"
        )
    return materialized


def default_strategy(materialized: str) -> str:
    if materialized == "incremental":
        return "replay_slices"
    return "replace_all"


def normalize_strategy(
    job_name: str,
    materialized: str,
    value: Any,
) -> str:
    strategy = str(value or default_strategy(materialized)).strip().lower()
    if strategy not in ALLOWED_STRATEGIES:
        allowed = ", ".join(sorted(ALLOWED_STRATEGIES))
        raise ExecutionConfigError(
            f"[{job_name}] execution.full_refresh_strategy must be one of: "
            f"{allowed}"
        )

    if materialized == "incremental" and strategy == "replace_all":
        raise ExecutionConfigError(
            f"[{job_name}] incremental models must use replay_slices, "
            "companion, or legacy_full_refresh"
        )
    if materialized == "full" and strategy != "replace_all":
        raise ExecutionConfigError(
            f"[{job_name}] full models must use "
            "execution.full_refresh_strategy: replace_all"
        )
    return strategy


def slice_config_from_mapping(
    job_name: str,
    value: Any,
    *,
    label: str,
) -> SliceConfig | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ExecutionConfigError(f"[{job_name}] {label} must be a mapping")

    param = str(value.get("param") or "").strip()
    column = str(value.get("column") or "").strip()
    period = str(value.get("period") or "").strip().upper()
    if not param or not column or not period:
        raise ExecutionConfigError(
            f"[{job_name}] {label} requires param, column, and period"
        )
    if period not in ALLOWED_PERIODS:
        allowed = ", ".join(sorted(ALLOWED_PERIODS))
        raise ExecutionConfigError(
            f"[{job_name}] {label}.period must be one of: {allowed}"
        )
    return SliceConfig(param=param, column=column, period=period)
