"""Identifier indexes for assess rules.

These helpers reuse lineage's canonical identifier matching rules for object
identity while preserving original spelling for governance checks.
"""

from __future__ import annotations

from collections.abc import Iterable

from lineage.identifiers import identifier_match_key


def column_name_index(column_names: Iterable[str]) -> dict[str, str]:
    """Return first-seen display column names keyed by canonical identity."""
    index: dict[str, str] = {}
    for column_name in column_names:
        display_name = str(column_name or "").strip()
        key = identifier_match_key(display_name)
        if key:
            index.setdefault(key, display_name)
    return index


def missing_identifier_names(
    requested_names: Iterable[str],
    available_names: Iterable[str],
) -> list[str]:
    """Return requested names missing by case-insensitive identity."""
    available = column_name_index(available_names)
    missing = []
    for requested_name in requested_names:
        display_name = str(requested_name or "").strip()
        if (
            display_name
            and identifier_match_key(display_name) not in available
        ):
            missing.append(display_name)
    return missing


def identifier_spelling_mismatches(
    requested_names: Iterable[str],
    available_names: Iterable[str],
) -> list[dict[str, str]]:
    """Return names that match by identity but differ in exact spelling."""
    available = column_name_index(available_names)
    mismatches = []
    seen: set[tuple[str, str]] = set()
    for requested_name in requested_names:
        model_column = str(requested_name or "").strip()
        key = identifier_match_key(model_column)
        ddl_column = available.get(key)
        if not model_column or not ddl_column or model_column == ddl_column:
            continue
        pair = (model_column, ddl_column)
        if pair in seen:
            continue
        seen.add(pair)
        mismatches.append(
            {
                "model_column": model_column,
                "ddl_column": ddl_column,
            }
        )
    return mismatches
