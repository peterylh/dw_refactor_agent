#!/usr/bin/env python3
"""
业务语义 catalog 到模型元数据的映射与回写逻辑。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块、维度表 entity/related_entities、DWS grain 以及
DWD/DWS 表中的指标字段回写到 models/{table}.yaml，并把 DWD 事实表的
非原子指标输出为违规项。
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

_src_root = Path(__file__).resolve().parents[3]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspectResult,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    _infer_table_type,
    _layer_from_table_name,
    _materialized_for_layer,
    _normalize_catalog_code,
    catalog_mapping_for_model,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    normalize_entities,
)
from dw_refactor_agent.config import (
    TEXT_ENCODING,
)

WRITE_SCOPES = {"all", "table", "metrics", "grain", "business"}
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
TABLE_METADATA_BLOCKING_VALIDATION_KEYS = {
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    "inconsistent_layer_table_types",
    "inconsistent_layer_sql",
    "inconsistent_upstream_metric_layers",
}
DDL_NON_COLUMN_PREFIXES = {
    "AGGREGATE",
    "CREATE",
    "DISTRIBUTED",
    "DUPLICATE",
    "ENGINE",
    "KEY",
    "PARTITION",
    "PARTITIONED",
    "PRIMARY",
    "PROPERTIES",
    "UNIQUE",
}

from dw_refactor_agent.assessment.llm.model_metadata_updates import (
    _drop_deprecated_execution_config,
    _existing_model_data,
    _inspection_resolution_is_eligible,
    _layer_resolution_for_model,
    _materialized_for_write,
    _validate_write_scope,
    business_metadata_for_result,
    model_path_for_table,
)


def _catalog_model_payload(
    *,
    table_name: str,
    existing: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    layer = str(
        mapping.get("layer")
        or existing.get("layer")
        or _layer_from_table_name(table_name)
    ).upper()
    table_type = str(
        mapping.get("table_type")
        or existing.get("table_type")
        or _infer_table_type(table_name, layer)
    ).strip()
    mapped_execution = mapping.get("execution")
    if isinstance(mapped_execution, dict):
        execution_payload = dict(mapped_execution)
    else:
        execution_payload = dict(existing.get("execution") or {})
    materialized = _materialized_for_write(
        execution_payload.get("materialized")
        or mapping.get("materialized")
        or "",
        layer,
    )

    updated = dict(existing)
    updated.setdefault("version", 2)
    updated["name"] = table_name
    updated["layer"] = layer
    updated["table_type"] = table_type or "other"
    if materialized:
        execution_payload["materialized"] = materialized
        updated["execution"] = execution_payload
        _drop_deprecated_execution_config(updated)

    data_domain = str(mapping.get("data_domain") or "").strip()
    business_area = str(mapping.get("business_area") or "").strip().upper()
    business_process = str(mapping.get("business_process") or "").strip()
    semantic_subject = str(mapping.get("semantic_subject") or "").strip()
    if layer in DATA_DOMAIN_LAYERS and data_domain:
        updated["data_domain"] = data_domain
    else:
        updated.pop("data_domain", None)
    if layer in BUSINESS_AREA_LAYERS and business_area:
        updated["business_area"] = business_area
    else:
        updated.pop("business_area", None)
    if table_type == "dimension" and semantic_subject:
        updated["semantic_subject"] = semantic_subject
        updated.pop("business_process", None)
    elif table_type == "fact":
        if business_process:
            updated["business_process"] = business_process
        else:
            updated.pop("business_process", None)
        updated.pop("semantic_subject", None)
    elif table_type == "dimension":
        updated.pop("business_process", None)
        updated.pop("semantic_subject", None)
    else:
        updated.pop("business_process", None)
        updated.pop("semantic_subject", None)

    if layer == "DIM":
        dimension_role = (
            str(mapping.get("dimension_role") or "").strip().upper()
        )
        dimension_content_type = (
            str(mapping.get("dimension_content_type") or "").strip().upper()
        )
        if dimension_role:
            updated["dimension_role"] = dimension_role
        if dimension_content_type:
            updated["dimension_content_type"] = dimension_content_type
    else:
        updated.pop("dimension_role", None)
        updated.pop("dimension_content_type", None)
    return updated


def _business_processes_from_result(result: TableInspectResult) -> list[str]:
    codes = []
    metric_groups = (
        result.atomic_metrics,
        result.derived_metrics,
        result.calculated_metrics,
    )
    if not any(metric_groups):
        table_process = _normalize_catalog_code(result.business_process)
        if table_process:
            codes.append(table_process)
    for metrics in metric_groups:
        for metric in metrics:
            code = _normalize_catalog_code(metric.get("business_process"))
            if code and code not in codes:
                codes.append(code)
    return codes


def _existing_catalog_assignment(
    *,
    catalog: dict[str, Any],
    table_name: str,
    existing_metadata: dict[str, Any] | None,
    field: str,
) -> dict[str, Any]:
    existing_mapping = catalog_mapping_for_model(
        catalog,
        table_name,
        existing_metadata or {},
    )
    if not existing_mapping.get(field):
        return {}
    return {
        key: value
        for key, value in existing_mapping.items()
        if key
        in {
            "data_domain",
            "business_area",
            "business_process",
            "semantic_subject",
        }
    }


def _semantic_subject_from_result(result: TableInspectResult) -> str:
    entities = normalize_entities(
        result.entities,
        result.entity,
        result.related_entities,
    )
    primary = next(
        (
            entity
            for entity in entities
            if str(entity.get("type") or "").lower() == "primary"
        ),
        None,
    )
    if not primary and entities:
        primary = entities[0]
    return _normalize_catalog_code((primary or {}).get("code"))


def _catalog_has_code(catalog: dict[str, Any], key: str, code: str) -> bool:
    return bool(_catalog_entry_code(catalog, key, code))


def _catalog_entry_code(
    catalog: dict[str, Any],
    key: str,
    code: str,
) -> str:
    wanted = _normalize_catalog_code(code)
    if not wanted:
        return ""
    for entry in catalog.get(key) or []:
        if not isinstance(entry, dict):
            continue
        if _normalize_catalog_code(entry.get("code")) == wanted:
            return str(entry.get("code") or "").strip()
    return ""


def catalog_discovery_model_mapping(
    project: str,
    result: TableInspectResult,
    catalog: dict[str, Any] | None = None,
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return model metadata assignment discovered by table-level LLM."""
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing_metadata,
    )
    if not _inspection_resolution_is_eligible(result, resolution):
        return {}
    layer = resolution.applied_layer
    table_type = resolution.table_type
    catalog = catalog or {}
    mapping: dict[str, Any] = {
        "table": result.table_name,
        "layer": layer,
        "table_type": table_type,
        "materialized": _materialized_for_layer(
            result.declared_layer or layer
        ),
    }
    mapping.update(business_metadata_for_result(project, result, layer))
    if table_type == "dimension":
        semantic_subject = _semantic_subject_from_result(result)
        catalog_subject = _catalog_entry_code(
            catalog,
            "semantic_subjects",
            semantic_subject,
        )
        if catalog_subject:
            mapping["semantic_subject"] = catalog_subject
        else:
            mapping.update(
                _existing_catalog_assignment(
                    catalog=catalog,
                    table_name=result.table_name,
                    existing_metadata=existing_metadata,
                    field="semantic_subject",
                )
            )
        if result.dimension_role:
            mapping["dimension_role"] = result.dimension_role
        if result.dimension_content_type:
            mapping["dimension_content_type"] = result.dimension_content_type
        return mapping

    if table_type == "fact":
        processes = _business_processes_from_result(result)
        catalog_process = (
            _catalog_entry_code(
                catalog,
                "business_processes",
                processes[0],
            )
            if len(processes) == 1
            else ""
        )
        if catalog_process:
            mapping["business_process"] = catalog_process
        else:
            mapping.update(
                _existing_catalog_assignment(
                    catalog=catalog,
                    table_name=result.table_name,
                    existing_metadata=existing_metadata,
                    field="business_process",
                )
            )
        return mapping

    return mapping


def _resolved_results_for_catalog_discovery(
    results: list[TableInspectResult],
    model_metadata: dict[str, dict[str, Any]],
) -> list[TableInspectResult]:
    resolved = []
    for result in results:
        resolution = _layer_resolution_for_model(
            result,
            existing_model=model_metadata.get(result.table_name, {}),
        )
        if not _inspection_resolution_is_eligible(result, resolution):
            continue
        resolved.append(
            replace(
                result,
                inferred_layer=resolution.applied_layer,
                table_type=resolution.table_type,
            )
        )
    return resolved


def update_model_yaml_from_catalog(
    project: str,
    table_name: str,
    mapping: dict[str, Any],
    *,
    dry_run: bool = False,
    write_scope: str = "business",
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("catalog 回写仅支持 write_scope=all/table/business")

    path = model_path_for_table(
        project,
        table_name,
        layer=mapping.get("layer"),
    )
    existing = _existing_model_data(path)
    previous = dict(existing)
    updated = _catalog_model_payload(
        table_name=table_name,
        existing=existing,
        mapping=mapping,
    )
    if write_scope == "table":
        for key in (
            "data_domain",
            "business_area",
            "business_process",
            "semantic_subject",
        ):
            if key not in previous:
                updated.pop(key, None)
        for key in (
            "dimension_role",
            "dimension_content_type",
        ):
            if key not in previous:
                updated.pop(key, None)
            else:
                updated[key] = previous[key]

    changed = updated != previous
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(updated, allow_unicode=True, sort_keys=False),
            encoding=TEXT_ENCODING,
        )

    business_changed = any(
        updated.get(key) != previous.get(key)
        for key in (
            "data_domain",
            "business_area",
            "business_process",
            "semantic_subject",
            "dimension_role",
            "dimension_content_type",
        )
    )
    return {
        "table": table_name,
        "path": str(path),
        "status": "passed",
        "changed": changed,
        "metadata_changed": any(
            updated.get(key) != previous.get(key)
            for key in ("layer", "table_type")
        ),
        "business_changed": business_changed,
        "metric_changed": False,
        "grain_changed": False,
        "updated": bool(changed and not dry_run),
        "write_scope": write_scope,
        "source": "catalog",
        "previous_layer": previous.get("layer"),
        "layer": updated.get("layer"),
        "previous_table_type": previous.get("table_type"),
        "table_type": updated.get("table_type"),
        "previous_data_domain": previous.get("data_domain"),
        "data_domain": updated.get("data_domain"),
        "previous_business_area": previous.get("business_area"),
        "business_area": updated.get("business_area"),
        "business_process": updated.get("business_process"),
        "semantic_subject": updated.get("semantic_subject"),
        "dimension_role": updated.get("dimension_role"),
        "dimension_content_type": updated.get("dimension_content_type"),
    }
