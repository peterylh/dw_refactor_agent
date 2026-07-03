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


def business_semantics_dir(project: str) -> Path:
    path = config.business_semantics_dir(project)
    if not path:
        raise ValueError(f"未知项目: {project}")
    return path


def business_semantics_paths(project: str) -> dict[str, Path]:
    paths = config.business_semantics_paths(project)
    if not paths:
        raise ValueError(f"未知项目: {project}")
    return paths


def business_taxonomy_path(project: str) -> Path:
    path = config.business_taxonomy_path(project)
    if not path:
        raise ValueError(f"未知项目: {project}")
    return path


def business_processes_path(project: str) -> Path:
    path = config.business_processes_path(project)
    if not path:
        raise ValueError(f"未知项目: {project}")
    return path


def semantic_subjects_path(project: str) -> Path:
    path = config.semantic_subjects_path(project)
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
    base_catalog: dict[str, Any] | None,
    key: str,
) -> list[dict[str, Any]]:
    if base_catalog:
        return _entry_values(base_catalog.get(key))
    return []


def _catalog_code_candidates(value: Any) -> set[str]:
    normalized = _normalize_catalog_code(value)
    if not normalized:
        return set()
    candidates = {normalized}
    if normalized.isdigit():
        candidates.add(normalized.zfill(2))
    return candidates


def _dictionary_value(
    entries: list[dict[str, Any]],
    value: str,
    *,
    value_field: str,
) -> str:
    candidates = _catalog_code_candidates(value)
    if not candidates:
        return ""
    for entry in entries:
        ids = {
            _normalize_catalog_code(entry.get("id")),
            _normalize_catalog_code(entry.get("code")),
        }
        if not candidates & ids:
            continue
        selected = entry.get(value_field) or entry.get("id") or entry.get("code")
        return str(selected or "").strip()
    return ""


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

    if base_catalog is None:
        base_catalog = load_business_semantics_catalog(project)
    else:
        base_catalog = base_catalog or {}
    data_domains = _catalog_dictionary_entries(
        base_catalog,
        "data_domains",
    )
    business_areas = _catalog_dictionary_entries(
        base_catalog,
        "business_areas",
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
        data_domain = _dictionary_value(
            data_domains,
            _result_data_domain(result),
            value_field="id",
        )
        business_area = _dictionary_value(
            business_areas,
            _result_business_area(result),
            value_field="code",
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

    catalog = {
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
    for key in ("source", "project_context"):
        if base_catalog.get(key):
            catalog[key] = base_catalog[key]
    return catalog


def build_initial_business_semantics_catalog(
    project: str,
    *,
    inspection_results: list[Any] | None = None,
    base_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if project not in config.PROJECT_CONFIG:
        raise ValueError(f"未知项目: {project}")

    if base_catalog is None:
        base_catalog = load_business_semantics_catalog(project)
    else:
        base_catalog = base_catalog or {}

    if inspection_results is not None:
        return build_business_semantics_catalog_from_inspection(
            project,
            inspection_results,
            base_catalog=base_catalog,
        )

    data_domains = _catalog_dictionary_entries(
        base_catalog,
        "data_domains",
    )
    business_areas = _catalog_dictionary_entries(
        base_catalog,
        "business_areas",
    )
    catalog = {
        "version": CATALOG_VERSION,
        "project": project,
        "data_domains": data_domains,
        "business_areas": business_areas,
        "business_processes": [],
        "semantic_subjects": [],
    }
    for key in ("source", "project_context"):
        if base_catalog.get(key):
            catalog[key] = base_catalog[key]
    return catalog


def _base_catalog_file_payload(catalog: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "version": catalog.get("version") or CATALOG_VERSION,
        "project": catalog.get("project"),
    }
    if catalog.get("source"):
        payload["source"] = catalog.get("source")
    return payload


def _split_catalog_payloads(
    catalog: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    taxonomy = _base_catalog_file_payload(catalog)
    if catalog.get("project_context"):
        taxonomy["project_context"] = catalog.get("project_context")
    taxonomy["data_domains"] = catalog.get("data_domains") or []
    taxonomy["business_areas"] = catalog.get("business_areas") or []

    processes = _base_catalog_file_payload(catalog)
    processes["business_processes"] = (
        catalog.get("business_processes") or []
    )

    subjects = _base_catalog_file_payload(catalog)
    subjects["semantic_subjects"] = catalog.get("semantic_subjects") or []

    return {
        "taxonomy": taxonomy,
        "business_processes": processes,
        "semantic_subjects": subjects,
    }


def _catalog_write_names(
    paths: dict[str, Path],
    *,
    overwrite: bool,
    has_inspection_results: bool,
) -> set[str]:
    existing_names = {name for name, path in paths.items() if path.exists()}
    if overwrite:
        names = set(paths)
        if has_inspection_results and "taxonomy" in existing_names:
            names.discard("taxonomy")
        return names
    return set(paths) - existing_names


def _effective_catalog_after_write(
    *,
    candidate: dict[str, Any],
    base_catalog: dict[str, Any],
    paths: dict[str, Path],
    write_names: set[str],
) -> dict[str, Any]:
    effective = dict(candidate)
    if "taxonomy" not in write_names and paths["taxonomy"].exists():
        for key in ("data_domains", "business_areas"):
            effective[key] = base_catalog.get(key) or []
        for key in ("source", "project_context"):
            if base_catalog.get(key):
                effective[key] = base_catalog[key]
            else:
                effective.pop(key, None)
    if (
        "business_processes" not in write_names
        and paths["business_processes"].exists()
    ):
        effective["business_processes"] = (
            base_catalog.get("business_processes") or []
        )
    if (
        "semantic_subjects" not in write_names
        and paths["semantic_subjects"].exists()
    ):
        effective["semantic_subjects"] = (
            base_catalog.get("semantic_subjects") or []
        )
    return effective


def write_initial_business_semantics_catalog(
    project: str,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    inspection_results: list[Any] | None = None,
) -> dict[str, Any]:
    directory = business_semantics_dir(project)
    paths = business_semantics_paths(project)
    base_catalog = load_business_semantics_catalog(project)
    candidate_catalog = build_initial_business_semantics_catalog(
        project,
        inspection_results=inspection_results,
        base_catalog=base_catalog,
    )
    write_names = _catalog_write_names(
        paths,
        overwrite=overwrite,
        has_inspection_results=inspection_results is not None,
    )
    catalog = _effective_catalog_after_write(
        candidate=candidate_catalog,
        base_catalog=base_catalog,
        paths=paths,
        write_names=write_names,
    )
    payloads = _split_catalog_payloads(candidate_catalog)
    changed = bool(write_names)
    if changed and not dry_run:
        directory.mkdir(parents=True, exist_ok=True)
        for name in sorted(write_names):
            paths[name].write_text(
                yaml.safe_dump(
                    payloads[name],
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding=TEXT_ENCODING,
            )
        config.clear_business_semantics_cache()
        config.clear_naming_config_cache()
    return {
        "project": project,
        "path": str(directory),
        "paths": {name: str(path) for name, path in paths.items()},
        "written_names": sorted(write_names),
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


def _catalog_domain_id(catalog: dict[str, Any], value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    domains = _entry_values(catalog.get("data_domains"))
    domain_ids = {
        str(entry.get("id") or "").strip()
        for entry in domains
        if str(entry.get("id") or "").strip()
    }
    if raw in domain_ids:
        return raw
    if raw.isdigit():
        padded = raw.zfill(2)
        if padded in domain_ids:
            return padded
    upper = raw.upper()
    for entry in domains:
        domain_id = str(entry.get("id") or "").strip()
        code = str(entry.get("code") or domain_id).strip().upper()
        if domain_id and upper == code:
            return domain_id
    return ""


def _catalog_business_area_code(catalog: dict[str, Any], value: Any) -> str:
    code = str(value or "").strip().upper()
    if not code:
        return ""
    for entry in _entry_values(catalog.get("business_areas")):
        area_code = str(entry.get("code") or "").strip().upper()
        if area_code and code == area_code:
            return area_code
    return ""


def _catalog_taxonomy_metadata(
    catalog: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, str]:
    metadata = {}
    data_domain = _catalog_domain_id(catalog, entry.get("data_domain"))
    business_area = _catalog_business_area_code(
        catalog,
        entry.get("business_area"),
    )
    if data_domain:
        metadata["data_domain"] = data_domain
    if business_area:
        metadata["business_area"] = business_area
    return metadata


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
        mapping = {
            "table": short_name,
            "layer": layer,
            "table_type": table_type or "dimension",
            "semantic_subject": str(subject.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }
        mapping.update(_catalog_taxonomy_metadata(catalog, subject))
        return mapping

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
        mapping = {
            "table": short_name,
            "layer": layer,
            "table_type": table_type or "fact",
            "business_process": str(process.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }
        mapping.update(_catalog_taxonomy_metadata(catalog, process))
        return mapping

    return {"table": short_name}
