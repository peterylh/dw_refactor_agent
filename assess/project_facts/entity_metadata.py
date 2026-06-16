"""Entity/grain metadata normalization helpers."""
from __future__ import annotations

from typing import Any


VALID_ENTITY_TYPES = {"primary", "unique", "foreign", "natural"}


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = str(value or "").strip()
    return [value] if value else []


def normalize_entity(
    raw: dict[str, Any],
    *,
    default_type: str = "foreign",
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    code = str(raw.get("code") or raw.get("name") or "").strip()
    if not code:
        return {}

    entity_type = str(raw.get("type") or default_type).strip().lower()
    if entity_type not in VALID_ENTITY_TYPES:
        entity_type = default_type

    key_columns = as_string_list(
        raw.get("key_columns")
        or raw.get("keys")
        or raw.get("expr")
    )

    entity: dict[str, Any] = {
        "code": code,
        "type": entity_type,
    }
    name = str(raw.get("name") or "").strip()
    if name and name != code:
        entity["name"] = name
    if key_columns:
        entity["key_columns"] = key_columns
    relationship = raw.get("relationship")
    if isinstance(relationship, dict) and relationship:
        entity["relationship"] = dict(relationship)
    return entity


def normalize_entities(
    entities: Any = None,
    legacy_entity: Any = None,
    legacy_related_entities: Any = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    def add(item: dict[str, Any]) -> None:
        if not item:
            return
        identity = (
            str(item.get("code") or ""),
            str(item.get("type") or ""),
            tuple(as_string_list(item.get("key_columns"))),
        )
        if identity in seen:
            return
        normalized.append(item)
        seen.add(identity)

    if isinstance(entities, list):
        for raw in entities:
            add(normalize_entity(raw, default_type="foreign"))

    if isinstance(legacy_entity, dict):
        add(normalize_entity(legacy_entity, default_type="primary"))

    if isinstance(legacy_related_entities, list):
        for raw in legacy_related_entities:
            add(normalize_entity(raw, default_type="foreign"))

    return normalized


def legacy_entity_from_entities(
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    for entity in entities:
        if str(entity.get("type") or "").lower() != "primary":
            continue
        legacy = {
            "code": entity.get("code"),
            "key_columns": as_string_list(entity.get("key_columns")),
        }
        return {key: value for key, value in legacy.items() if value}
    return {}


def legacy_related_entities_from_entities(
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    related = []
    for entity in entities:
        if str(entity.get("type") or "").lower() == "primary":
            continue
        relationship = entity.get("relationship")
        if not isinstance(relationship, dict):
            continue
        item = {
            "code": entity.get("code"),
            "name": entity.get("name", ""),
            "key_columns": as_string_list(entity.get("key_columns")),
            "relationship": dict(relationship),
        }
        related.append({key: value for key, value in item.items() if value})
    return related


def model_entities(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    return normalize_entities(
        metadata.get("entities"),
        metadata.get("entity"),
        metadata.get("related_entities"),
    )


def primary_entity_codes(metadata: dict[str, Any] | None) -> list[str]:
    codes = []
    for entity in model_entities(metadata):
        if str(entity.get("type") or "").lower() != "primary":
            continue
        code = str(entity.get("code") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def defined_entity_codes(model_metadata: dict[str, Any] | None) -> set[str]:
    if not model_metadata:
        return set()
    defined = set()
    for metadata in model_metadata.values():
        for entity in model_entities(metadata):
            code = str(entity.get("code") or "").strip()
            if code:
                defined.add(code)
    return defined


def grain_entity_codes(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    grain = metadata.get("grain")
    if not isinstance(grain, dict):
        return []
    return as_string_list(grain.get("entities"))


def entity_key_columns_by_code(
    metadata: dict[str, Any] | None,
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for entity in model_entities(metadata):
        code = str(entity.get("code") or "").strip()
        if code:
            index.setdefault(code, []).extend(
                as_string_list(entity.get("key_columns")))
    return index


def grain_key_columns(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    grain = metadata.get("grain")
    if not isinstance(grain, dict):
        return []

    keys = as_string_list(grain.get("keys"))
    if keys:
        return keys

    key_columns_by_entity = entity_key_columns_by_code(metadata)
    result = []
    for code in grain_entity_codes(metadata):
        for key in key_columns_by_entity.get(code, []):
            if key not in result:
                result.append(key)
    for key in as_string_list(grain.get("additional_key_columns")):
        if key not in result:
            result.append(key)
    time_column = str(grain.get("time_column") or "").strip()
    if time_column and time_column not in result:
        result.append(time_column)
    return result
