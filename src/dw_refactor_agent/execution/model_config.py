"""Execution model configuration validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


@dataclass(frozen=True)
class SliceConfig:
    param: str
    column: str
    period: str


def normalize_materialized(job_name: str, value: Any) -> str:
    materialized = str(value or "incremental").strip().lower()
    if materialized == "snapshot":
        raise ExecutionConfigError(
            f"[{job_name}] materialized: snapshot is no longer supported. "
            "Migrate to:\n"
            "config:\n"
            "  materialized: incremental\n"
            "execution:\n"
            "  slice:\n"
            "    param: etl_date\n"
            "    column: snapshot_date\n"
            "    period: D"
        )
    if materialized not in ALLOWED_MATERIALIZED:
        allowed = ", ".join(sorted(ALLOWED_MATERIALIZED))
        raise ExecutionConfigError(
            f"[{job_name}] config.materialized must be one of: {allowed}"
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
            f"[{job_name}] config.full_refresh_strategy must be one of: "
            f"{allowed}"
        )

    if materialized == "incremental" and strategy == "replace_all":
        raise ExecutionConfigError(
            f"[{job_name}] incremental models must use replay_slices, "
            "companion, or legacy_full_refresh"
        )
    if materialized == "full" and strategy != "replace_all":
        raise ExecutionConfigError(
            f"[{job_name}] full models must use full_refresh_strategy: "
            "replace_all"
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
