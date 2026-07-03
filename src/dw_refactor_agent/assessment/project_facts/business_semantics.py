"""Project-local business semantics catalog helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    _short_table_name,
)
from dw_refactor_agent.config import TEXT_ENCODING

CATALOG_VERSION = 1


def _layer_from_table_name(table_name: str) -> str:
    first = str(table_name or "").split("_", 1)[0].upper()
    return first if first in {"ODS", "DWD", "DWS", "DIM", "ADS"} else "OTHER"


def business_semantics_path(project: str) -> Path:
    path = config.business_semantics_path(project)
    if not path:
        raise ValueError(f"未知项目: {project}")
    return path


def load_business_semantics_catalog(project: str) -> dict[str, Any]:
    return config.load_business_semantics_catalog(project)


def _entry_values(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        values = raw.get("values") or raw.get("items") or []
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return [dict(item) for item in values if isinstance(item, dict)]


def _domain_entries_from_naming(project: str) -> list[dict[str, Any]]:
    naming = config.get_naming_config(project)
    return _entry_values((naming.dictionaries or {}).get("data_domains"))


def _business_area_entries_from_naming(project: str) -> list[dict[str, Any]]:
    naming = config.get_naming_config(project)
    return _entry_values((naming.dictionaries or {}).get("business_areas"))


def _display_name_from_code(code: str) -> str:
    return str(code or "").replace("_", " ").title()


def _infer_table_type(table_name: str, layer: str) -> str:
    if layer == "DIM":
        return "dimension"
    if layer in {"ODS", "ADS"}:
        return "other"
    if layer == "DWS":
        return "fact"
    return "other"


def _materialized_for_layer(layer: str) -> str:
    if layer == "ODS":
        return "source"
    if layer in {"DWD", "DWS"}:
        return "incremental"
    return "full"


def _normalize_catalog_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = re.sub(r"[\s\-/]+", "_", text)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if re.fullmatch(r"[A-Za-z0-9_]+", normalized):
        return normalized.upper()
    return text


def _result_value(result: Any, key: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _result_table_name(result: Any) -> str:
    return _short_table_name(_result_value(result, "table_name", ""))


def _result_table_type(result: Any) -> str:
    return str(_result_value(result, "table_type", "") or "").strip().lower()


def _result_data_domain(result: Any) -> str:
    return str(_result_value(result, "inferred_data_domain", "") or "").strip()


def _result_business_area(result: Any) -> str:
    return (
        str(_result_value(result, "inferred_business_area", "") or "")
        .strip()
        .upper()
    )


def _result_columns(result: Any) -> dict[str, Any]:
    columns = _result_value(result, "columns", {}) or {}
    return columns if isinstance(columns, dict) else {}


def _iter_metric_items(result: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    columns = _result_columns(result)
    for group in ("atomic_metrics", "derived_metrics", "calculated_metrics"):
        raw_items = columns.get(group) or []
        if isinstance(raw_items, list):
            items.extend(
                dict(item) for item in raw_items if isinstance(item, dict)
            )
    return items


def _primary_entity(result: Any) -> dict[str, Any]:
    raw_entities = _result_value(result, "entities", []) or []
    if not raw_entities:
        raw_entity = _result_value(result, "entity", {}) or {}
        if isinstance(raw_entity, dict) and raw_entity:
            raw_entities = [raw_entity]
    if not isinstance(raw_entities, list):
        return {}

    entities = [dict(item) for item in raw_entities if isinstance(item, dict)]
    if not entities:
        return {}
    primary = next(
        (
            entity
            for entity in entities
            if str(entity.get("type") or "").strip().lower() == "primary"
        ),
        None,
    )
    if not primary:
        primary = next(
            (
                entity
                for entity in entities
                if str(entity.get("type") or "").strip().lower() != "foreign"
            ),
            entities[0],
        )
    return primary


def _entry_name_from_entity(entity: dict[str, Any], code: str) -> str:
    name = str(entity.get("name") or "").strip()
    return name or _display_name_from_code(code)


def _seed_entry_index(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        code = _normalize_catalog_code(entry.get("code"))
        if not code:
            continue
        seeded = dict(entry)
        seeded["code"] = code
        seeded.pop("tables", None)
        index[code] = seeded
    return index


def _touch_entry(
    index: dict[str, dict[str, Any]],
    *,
    code: str,
    name: str,
    data_domain: str = "",
    business_area: str = "",
) -> None:
    if not code:
        return
    entry = index.setdefault(
        code,
        {
            "code": code,
            "name": name or _display_name_from_code(code),
            "data_domain": data_domain,
            "business_area": business_area,
        },
    )
    if not entry.get("name") and name:
        entry["name"] = name
    if not entry.get("data_domain") and data_domain:
        entry["data_domain"] = data_domain
    if not entry.get("business_area") and business_area:
        entry["business_area"] = business_area
    entry.pop("tables", None)


def _catalog_dictionary_entries(
    project: str,
    base_catalog: dict[str, Any] | None,
    key: str,
    fallback_loader,
) -> list[dict[str, Any]]:
    if base_catalog:
        entries = _entry_values(base_catalog.get(key))
        if entries:
            return entries
    return fallback_loader(project)


def _dictionary_contains(entries: list[dict[str, Any]], value: str) -> bool:
    normalized = _normalize_catalog_code(value)
    if not normalized:
        return True
    for entry in entries:
        ids = {
            _normalize_catalog_code(entry.get("id")),
            _normalize_catalog_code(entry.get("code")),
        }
        if normalized in ids:
            return True
    return False


def _append_dictionary_candidate(
    entries: list[dict[str, Any]],
    value: str,
    *,
    kind: str,
) -> None:
    code = _normalize_catalog_code(value)
    if not code or _dictionary_contains(entries, code):
        return
    item = {
        "id": code,
        "code": code,
        "name": _display_name_from_code(code),
    }
    if kind == "data_domain" or kind == "business_area":
        entries.append(item)


def build_business_semantics_catalog_from_inspection(
    project: str,
    results: list[Any],
    *,
    base_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build catalog entries from LLM table inspection results.

    This intentionally does not infer process/subject names from table name
    tokens. Business processes come from fact metric semantics; semantic
    subjects come from dimension primary entities.
    """
    if project not in config.PROJECT_CONFIG:
        raise ValueError(f"未知项目: {project}")

    base_catalog = base_catalog or {}
    data_domains = _catalog_dictionary_entries(
        project,
        base_catalog,
        "data_domains",
        _domain_entries_from_naming,
    )
    business_areas = _catalog_dictionary_entries(
        project,
        base_catalog,
        "business_areas",
        _business_area_entries_from_naming,
    )
    process_by_code = _seed_entry_index(
        _entry_values(base_catalog.get("business_processes"))
    )
    subject_by_code = _seed_entry_index(
        _entry_values(base_catalog.get("semantic_subjects"))
    )

    for result in results or []:
        table_name = _result_table_name(result)
        if not table_name:
            continue
        table_type = _result_table_type(result)
        data_domain = _result_data_domain(result)
        business_area = _result_business_area(result)
        _append_dictionary_candidate(
            data_domains,
            data_domain,
            kind="data_domain",
        )
        _append_dictionary_candidate(
            business_areas,
            business_area,
            kind="business_area",
        )

        if table_type == "dimension":
            entity = _primary_entity(result)
            code = _normalize_catalog_code(
                _result_value(result, "semantic_subject", "")
                or entity.get("code")
            )
            if code:
                _touch_entry(
                    subject_by_code,
                    code=code,
                    name=_entry_name_from_entity(entity, code),
                    data_domain=data_domain,
                    business_area=business_area,
                )
            continue

        if table_type != "fact":
            continue
        process_codes = []
        for item in _iter_metric_items(result):
            code = _normalize_catalog_code(item.get("business_process"))
            if code and code not in process_codes:
                process_codes.append(code)
        for code in process_codes:
            _touch_entry(
                process_by_code,
                code=code,
                name=_display_name_from_code(code),
                data_domain=data_domain,
                business_area=business_area,
            )

    return {
        "version": CATALOG_VERSION,
        "project": project,
        "data_domains": data_domains,
        "business_areas": business_areas,
        "business_processes": sorted(
            process_by_code.values(),
            key=lambda item: item["code"],
        ),
        "semantic_subjects": sorted(
            subject_by_code.values(),
            key=lambda item: item["code"],
        ),
    }


def build_initial_business_semantics_catalog(
    project: str,
    *,
    inspection_results: list[Any] | None = None,
    base_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if project not in config.PROJECT_CONFIG:
        raise ValueError(f"未知项目: {project}")

    if inspection_results is not None:
        return build_business_semantics_catalog_from_inspection(
            project,
            inspection_results,
            base_catalog=base_catalog,
        )

    data_domains = _domain_entries_from_naming(project)
    business_areas = _business_area_entries_from_naming(project)
    return {
        "version": CATALOG_VERSION,
        "project": project,
        "data_domains": data_domains,
        "business_areas": business_areas,
        "business_processes": [],
        "semantic_subjects": [],
    }


def write_initial_business_semantics_catalog(
    project: str,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    inspection_results: list[Any] | None = None,
) -> dict[str, Any]:
    path = business_semantics_path(project)
    if path.exists() and not overwrite:
        catalog = load_business_semantics_catalog(project)
        return {
            "project": project,
            "path": str(path),
            "changed": False,
            "updated": False,
            "catalog": catalog,
        }

    base_catalog = (
        load_business_semantics_catalog(project) if path.exists() else {}
    )
    catalog = build_initial_business_semantics_catalog(
        project,
        inspection_results=inspection_results,
        base_catalog=base_catalog,
    )
    changed = overwrite or not path.exists()
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False),
            encoding=TEXT_ENCODING,
        )
        config.clear_business_semantics_cache()
        config.clear_naming_config_cache()
    return {
        "project": project,
        "path": str(path),
        "changed": changed,
        "updated": bool(changed and not dry_run),
        "catalog": catalog,
    }


def _entry_by_code(entries: Any, code: str) -> dict[str, Any]:
    wanted = _normalize_catalog_code(code)
    if not wanted:
        return {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if _normalize_catalog_code(entry.get("code")) == wanted:
            return dict(entry)
    return {}


def catalog_mapping_for_model(
    catalog: dict[str, Any],
    table_name: str,
    model_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build catalog-backed model metadata from existing model references.

    The model owns table-to-process/subject assignment. The catalog only
    enriches those references with governed domain and area metadata.
    """
    short_name = _short_table_name(table_name)
    metadata = model_metadata or {}
    layer = str(
        metadata.get("layer") or _layer_from_table_name(short_name)
    ).upper()
    table_type = str(metadata.get("table_type") or "").strip()

    semantic_subject = _normalize_catalog_code(
        metadata.get("semantic_subject")
    )
    if semantic_subject:
        subject = _entry_by_code(
            catalog.get("semantic_subjects") or [],
            semantic_subject,
        )
        if not subject:
            return {"table": short_name}
        return {
            "table": short_name,
            "layer": layer,
            "table_type": table_type or "dimension",
            "data_domain": str(subject.get("data_domain") or "").strip(),
            "business_area": str(subject.get("business_area") or "").strip(),
            "semantic_subject": str(subject.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }

    business_process = _normalize_catalog_code(
        metadata.get("business_process")
    )
    if business_process:
        process = _entry_by_code(
            catalog.get("business_processes") or [],
            business_process,
        )
        if not process:
            return {"table": short_name}
        return {
            "table": short_name,
            "layer": layer,
            "table_type": table_type or "fact",
            "data_domain": str(process.get("data_domain") or "").strip(),
            "business_area": str(process.get("business_area") or "").strip(),
            "business_process": str(process.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }

    return {"table": short_name}
