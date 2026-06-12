"""Project-local business semantics catalog helpers."""

from pathlib import Path
from typing import Any

import yaml

import config
from assess.project_facts.asset_catalog import (
    _short_table_name,
    build_asset_catalog,
)

CATALOG_VERSION = 1
PROCESS_TABLE_LAYERS = {"DWD", "DWS"}
MODEL_TABLE_LAYERS = {"ODS", "DWD", "DWS", "DIM", "ADS"}
FACT_TOKENS = {
    "alert",
    "application",
    "assessment",
    "detail",
    "event",
    "interaction",
    "inventory",
    "item",
    "order",
    "payment",
    "risk",
    "summary",
    "transaction",
}
TIME_GRAIN_TOKENS = {"daily", "day", "df", "di", "ds", "monthly", "month"}
DIMENSION_SUFFIX_TOKENS = {"base", "dim", "info", "snapshot"}


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


def _layer_from_table_name(table_name: str) -> str:
    first = str(table_name or "").split("_", 1)[0].upper()
    return first if first in MODEL_TABLE_LAYERS else "OTHER"


def _process_code_from_table(table_name: str) -> str:
    layer = _layer_from_table_name(table_name)
    remainder = table_name[len(layer) + 1:] if layer != "OTHER" else table_name
    tokens = [
        token
        for token in remainder.split("_")
        if token and token.lower() not in TIME_GRAIN_TOKENS
    ]
    return "_".join(tokens).upper() or table_name.upper()


def _subject_code_from_table(table_name: str) -> str:
    layer = _layer_from_table_name(table_name)
    remainder = table_name[len(layer) + 1:] if layer != "OTHER" else table_name
    tokens = [
        token
        for token in remainder.split("_")
        if token
        and token.lower() not in TIME_GRAIN_TOKENS
        and token.lower() not in DIMENSION_SUFFIX_TOKENS
    ]
    return "_".join(tokens).upper() or _process_code_from_table(table_name)


def _display_name_from_code(code: str) -> str:
    return str(code or "").replace("_", " ").title()


def _keyword_text(*parts: Any) -> str:
    tokens = []
    for part in parts:
        if isinstance(part, list):
            tokens.extend(str(item).lower() for item in part)
        else:
            tokens.append(str(part or "").lower())
    return " ".join(tokens)


def _infer_entry(entries: list[dict[str, Any]], table_name: str) -> str:
    table_text = table_name.lower().replace("_", " ")
    for entry in entries:
        haystack = _keyword_text(
            entry.get("id"),
            entry.get("code"),
            entry.get("name"),
            entry.get("keywords"),
        )
        keywords = {
            token
            for token in haystack.replace("_", " ").split()
            if token
        }
        if any(keyword in table_text for keyword in keywords):
            return str(entry.get("id") or entry.get("code") or "").strip()
    for entry in entries:
        code = str(entry.get("code") or "").strip().upper()
        if code in {"OTHR", "OTHER"}:
            return str(entry.get("id") or code)
    return str(entries[0].get("id") or entries[0].get("code") or "").strip(
    ) if entries else ""


def _infer_business_area(entries: list[dict[str, Any]], table_name: str) -> str:
    value = _infer_entry(entries, table_name)
    for entry in entries:
        if value == str(entry.get("id") or "").strip():
            return str(entry.get("code") or value).strip().upper()
    return value.upper()


def _infer_table_type(table_name: str, layer: str) -> str:
    if layer == "DIM":
        return "dimension"
    if layer in {"ODS", "ADS"}:
        return "other"
    if layer == "DWS":
        return "fact"
    if layer == "DWD":
        lowered = table_name.lower()
        if any(token in lowered for token in FACT_TOKENS):
            return "fact"
        return "dimension"
    return "other"


def _materialized_for_layer(layer: str) -> str:
    if layer == "ODS":
        return "source"
    if layer in {"DWD", "DWS"}:
        return "incremental"
    return "full"


def _project_tables_from_ddl(project: str) -> list[dict[str, Any]]:
    cfg = config.PROJECT_CONFIG[project]
    project_dir = config.PROJECT_ROOT / cfg["dir"]
    catalog = build_asset_catalog([], {}, project_dir)
    tables = []
    for name, asset in sorted((catalog.get("tables") or {}).items()):
        ddl = asset.get("ddl") or {}
        if not ddl.get("exists"):
            continue
        table_name = _short_table_name(name)
        layer = _layer_from_table_name(table_name)
        if layer not in MODEL_TABLE_LAYERS:
            continue
        tables.append({
            "name": table_name,
            "layer": layer,
            "columns": ddl.get("columns") or [],
        })
    return tables


def build_initial_business_semantics_catalog(project: str) -> dict[str, Any]:
    if project not in config.PROJECT_CONFIG:
        raise ValueError(f"未知项目: {project}")

    data_domains = _domain_entries_from_naming(project)
    business_areas = _business_area_entries_from_naming(project)
    process_by_code = {}
    subject_by_code = {}
    for table in _project_tables_from_ddl(project):
        table_name = table["name"]
        layer = table["layer"]
        if layer not in PROCESS_TABLE_LAYERS and layer != "DIM":
            continue
        table_type = _infer_table_type(table_name, layer)
        data_domain = _infer_entry(data_domains, table_name)
        business_area = _infer_business_area(business_areas, table_name)
        if table_type == "dimension" or layer == "DIM":
            subject_code = _subject_code_from_table(table_name)
            subject = subject_by_code.setdefault(
                subject_code,
                {
                    "code": subject_code,
                    "name": _display_name_from_code(subject_code),
                    "data_domain": data_domain,
                    "business_area": business_area,
                    "tables": [],
                },
            )
            subject["tables"].append(table_name)
            continue

        if layer not in PROCESS_TABLE_LAYERS:
            continue
        process_code = _process_code_from_table(table_name)
        process = process_by_code.setdefault(
            process_code,
            {
                "code": process_code,
                "name": _display_name_from_code(process_code),
                "data_domain": data_domain,
                "business_area": business_area,
                "tables": [],
            },
        )
        process["tables"].append(table_name)

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


def write_initial_business_semantics_catalog(
    project: str,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
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

    catalog = build_initial_business_semantics_catalog(project)
    changed = overwrite or not path.exists()
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        config._business_semantics_cache.clear()
    return {
        "project": project,
        "path": str(path),
        "changed": changed,
        "updated": bool(changed and not dry_run),
        "catalog": catalog,
    }


def catalog_mapping_for_table(catalog: dict[str, Any],
                              table_name: str) -> dict[str, Any]:
    short_name = _short_table_name(table_name)
    for subject in catalog.get("semantic_subjects") or []:
        if not isinstance(subject, dict):
            continue
        if short_name not in {
            _short_table_name(table) for table in subject.get("tables") or []
        }:
            continue
        layer = _layer_from_table_name(short_name)
        return {
            "table": short_name,
            "layer": "DIM" if layer in {"DWD", "DIM"} else layer,
            "table_type": "dimension",
            "data_domain": str(subject.get("data_domain") or "").strip(),
            "business_area": str(subject.get("business_area") or "").strip(),
            "semantic_subject": str(subject.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }

    for process in catalog.get("business_processes") or []:
        if not isinstance(process, dict):
            continue
        if short_name not in {
            _short_table_name(table) for table in process.get("tables") or []
        }:
            continue
        layer = _layer_from_table_name(short_name)
        return {
            "table": short_name,
            "layer": layer,
            "table_type": "fact",
            "data_domain": str(process.get("data_domain") or "").strip(),
            "business_area": str(process.get("business_area") or "").strip(),
            "business_process": str(process.get("code") or "").strip(),
            "materialized": _materialized_for_layer(layer),
        }

    for mapping in catalog.get("mappings") or []:
        if _short_table_name(mapping.get("table")) == short_name:
            return dict(mapping)
    return {}
