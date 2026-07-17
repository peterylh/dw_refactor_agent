"""Validation and runtime expansion for grouped verification checks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

FULL_TABLE_SCOPE = "full_table"
TIME_SLICE_SCOPE = "time_slice"
SUPPORTED_CHECK_METHODS = frozenset({"count", "row_compare"})
_GROUP_FIELDS = frozenset(
    {"table", "scope", "methods", "prod_table", "qa_table", "column_mapping"}
)
_SCOPE_FIELDS = {
    FULL_TABLE_SCOPE: frozenset({"mode"}),
    TIME_SLICE_SCOPE: frozenset({"mode", "column", "period", "value"}),
}
_METHOD_FIELDS = {
    "count": frozenset({"method"}),
    "row_compare": frozenset({"method", "exclude_columns"}),
}


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_unknown_fields(
    value: dict, allowed: frozenset[str], field: str
) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise ValueError(f"{field} has unsupported fields: {unknown!r}")


def _validate_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    for index, item in enumerate(value):
        _require_non_empty_string(item, f"{field}[{index}]")


def _validate_column_mapping(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    for index, mapping in enumerate(value):
        item_field = f"{field}[{index}]"
        if not isinstance(mapping, dict):
            raise ValueError(f"{item_field} must be a mapping")
        _require_non_empty_string(mapping.get("prod"), f"{item_field}.prod")
        _require_non_empty_string(mapping.get("qa"), f"{item_field}.qa")


def validate_verification_checks(checks: Any) -> None:
    """Validate the persisted grouped-check contract.

    Each entry owns one table-level compare scope and one or more method
    configurations. Runtime consumers expand the group into ordinary
    per-method checks.
    """
    if not isinstance(checks, list):
        raise ValueError("verification.checks must be a list")
    seen_tables = set()
    for index, group in enumerate(checks):
        prefix = f"verification.checks[{index}]"
        if not isinstance(group, dict):
            raise ValueError(f"{prefix} must be a mapping")
        _reject_unknown_fields(group, _GROUP_FIELDS, prefix)
        table = _require_non_empty_string(
            group.get("table"), f"{prefix}.table"
        )
        table_key = table.casefold()
        if table_key in seen_tables:
            raise ValueError(f"{prefix}.table is duplicated: {table}")
        seen_tables.add(table_key)

        scope = group.get("scope")
        if not isinstance(scope, dict):
            raise ValueError(f"{prefix}.scope must be a mapping")
        mode = scope.get("mode")
        if mode == TIME_SLICE_SCOPE:
            _reject_unknown_fields(
                scope, _SCOPE_FIELDS[mode], f"{prefix}.scope"
            )
            for field in ("column", "period", "value"):
                _require_non_empty_string(
                    scope.get(field), f"{prefix}.scope.{field}"
                )
        elif mode == FULL_TABLE_SCOPE:
            _reject_unknown_fields(
                scope, _SCOPE_FIELDS[mode], f"{prefix}.scope"
            )
        else:
            raise ValueError(
                f"{prefix}.scope.mode must be {FULL_TABLE_SCOPE!r} or "
                f"{TIME_SLICE_SCOPE!r}; received {mode!r}"
            )

        for field in ("prod_table", "qa_table"):
            if field in group:
                _require_non_empty_string(group[field], f"{prefix}.{field}")
        if "column_mapping" in group:
            _validate_column_mapping(
                group["column_mapping"], f"{prefix}.column_mapping"
            )

        methods = group.get("methods")
        if not isinstance(methods, list) or not methods:
            raise ValueError(f"{prefix}.methods must be a non-empty list")
        seen_methods = set()
        for method_index, method_config in enumerate(methods):
            method_prefix = f"{prefix}.methods[{method_index}]"
            if not isinstance(method_config, dict):
                raise ValueError(f"{method_prefix} must be a mapping")
            method = method_config.get("method")
            if method not in SUPPORTED_CHECK_METHODS:
                raise ValueError(
                    f"{method_prefix}.method must be one of "
                    f"{sorted(SUPPORTED_CHECK_METHODS)!r}; received {method!r}"
                )
            _reject_unknown_fields(
                method_config, _METHOD_FIELDS[method], method_prefix
            )
            if method in seen_methods:
                raise ValueError(
                    f"{method_prefix}.method is duplicated: {method}"
                )
            seen_methods.add(method)
            if "exclude_columns" in method_config:
                _validate_string_list(
                    method_config["exclude_columns"],
                    f"{method_prefix}.exclude_columns",
                )


def flatten_verification_checks(checks: list[dict]) -> list[dict]:
    """Expand grouped persisted checks into executable per-method checks."""
    validate_verification_checks(checks)
    flattened = []
    for group in checks:
        common = {
            key: deepcopy(value)
            for key, value in group.items()
            if key not in {"scope", "methods"}
        }
        scope = group["scope"]
        if scope["mode"] == TIME_SLICE_SCOPE:
            common["partition_col"] = scope["column"]
            common["partition_value"] = scope["value"]
        for method_config in group["methods"]:
            check = deepcopy(common)
            check.update(deepcopy(method_config))
            flattened.append(check)
    return flattened
