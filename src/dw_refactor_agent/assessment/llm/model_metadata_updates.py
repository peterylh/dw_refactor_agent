#!/usr/bin/env python3
"""
模型元数据 YAML 的解析、规范化与更新逻辑。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块、维度表 entity/related_entities、DWS grain 以及
DWD/DWS 表中的指标字段回写到 models/{table}.yaml，并把 DWD 事实表的
非原子指标输出为违规项。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

_src_root = Path(__file__).resolve().parents[3]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.llm.context_builder import (
    TableContext,
    build_contexts,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolution,
    LayerResolutionInput,
    LayerResolutionPolicy,
    resolve_layer,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    METRIC_LAYERS,
    WRITABLE_METADATA_LAYERS,
    MetadataFlowPlan,
)
from dw_refactor_agent.assessment.llm.model_metadata_runtime import (
    project_root,
)
from dw_refactor_agent.assessment.llm.model_metadata_semantics import (  # noqa: F401
    _apply_entity_code_replacements,
    _as_string_list,
    _build_grain_entity_index,
    _canonical_entity_code_for_keys,
    _canonical_table_reference,
    _catalog_code_lookup,
    _column_comments_from_ddl,
    _context_for_table,
    _contributing_metric_source_evidence,
    _dimension_key_code_index,
    _dimension_key_lineage_matches,
    _dimension_primary_entities,
    _direct_grain_key_mapping,
    _direct_upstream_dimension_entities,
    _dwd_process_sources_are_equivalent,
    _entity_codes_from_direct_lineage,
    _entity_name_from_comment,
    _grain_key_entity_pairs,
    _is_count_aggregate,
    _is_strict_row_preserving_select,
    _is_time_grain_key,
    _mark_composite_business_processes,
    _merge_related_entities,
    _metric_process_source_results,
    _preferred_equivalent_code,
    _process_reconciliation_is_eligible,
    _promote_count_aggregates_to_atomic,
    _reconcile_business_processes,
    _reconcile_dimension_entity_codes,
    _reconcile_entity_codes,
    _related_entity_identity,
    _remove_stale_metric_validation,
    _result_for_table_reference,
    _set_result_business_process,
    _single_primary_entity,
    _split_column_reference,
    _table_reference_matches,
    discover_related_entities_from_grain,
    enrich_results_with_project_semantics,
    enrich_results_with_related_entities,
    reconcile_project_semantics,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspectResult,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    _infer_table_type,
    _materialized_for_layer,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    normalize_entities,
)
from dw_refactor_agent.assessment.project_facts.time_period import (
    normalize_time_period,
)
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    asset_role_for_layer,
    get_business_domain_config,
)
from dw_refactor_agent.execution.model_config import EXECUTION_CONFIG_FIELDS

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


def build_inspection_contexts(
    project: str,
    lineage_data: dict[str, Any],
    *,
    model_metadata: dict[str, dict[str, Any]] | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
) -> list[TableContext]:
    """构建需要 LLM 巡检并回写模型元数据的表上下文。"""
    return build_contexts(
        project,
        lineage_data,
        layers=WRITABLE_METADATA_LAYERS,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
    )


def build_dwd_contexts(
    project: str,
    lineage_data: dict[str, Any],
    *,
    model_metadata: dict[str, dict[str, Any]] | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
) -> list[TableContext]:
    """构建项目 DWD 层表的识别上下文。"""
    return build_contexts(
        project,
        lineage_data,
        layers={"DWD"},
        model_metadata=model_metadata,
        metric_groups=metric_groups,
    )


def build_metric_contexts(
    project: str,
    lineage_data: dict[str, Any],
    *,
    model_metadata: dict[str, dict[str, Any]] | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
) -> list[TableContext]:
    """构建项目指标识别上下文，覆盖 DWD 与 DWS。"""
    return build_contexts(
        project,
        lineage_data,
        layers=METRIC_LAYERS,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
    )


def model_path_for_table(
    project: str,
    table_name: str,
    *,
    layer: str | None = None,
) -> Path:
    """返回模型 YAML 路径。"""
    project_cfg = PROJECT_CONFIG[project]
    project_dir = project_root() / project_cfg["dir"]
    filename = f"{table_name}.yaml"
    catalog = str(project_cfg.get("catalog") or "internal")
    database = str(project_cfg.get("db") or "")
    model_dirs = [
        project_dir / "ods" / "models" / catalog / database,
        project_dir / "mid" / "models",
        project_dir / "ads" / "models",
    ]
    for model_dir in model_dirs:
        candidate = model_dir / filename
        if candidate.exists():
            return candidate

    role = asset_role_for_layer(layer)
    if role == "ods":
        return project_dir / "ods" / "models" / catalog / database / filename
    if role in {"mid", "ads"}:
        role_dir = project_dir / role / "models"
        return role_dir / filename
    return project_dir / "mid" / "models" / filename


def metric_violations(
    result: TableInspectResult,
    *,
    applied_layer: str | None = None,
    applied_table_type: str | None = None,
) -> list[dict[str, Any]]:
    """返回 DWD 事实表中的派生/衍生指标违规项。"""
    effective_layer = str(applied_layer or result.inferred_layer or "").upper()
    effective_table_type = str(
        applied_table_type or result.table_type or ""
    ).lower()
    if effective_layer != "DWD" or effective_table_type != "fact":
        return []

    violations = []
    for metric_type, metrics in (
        ("derived", result.derived_metrics),
        ("calculated", result.calculated_metrics),
    ):
        for metric in metrics:
            violations.append(
                {
                    "table": result.table_name,
                    "column": metric["name"],
                    "metric_type": metric_type,
                    "reason": metric.get("reason", ""),
                    "confidence": metric.get("confidence", 0.0),
                }
            )
    return violations


def metric_names_for_model(result: TableInspectResult) -> list[str]:
    """生成写入 models YAML 的指标名列表。"""
    names = []
    for metric in (
        _metric_names(result.atomic_metrics)
        + _metric_names(result.derived_metrics)
        + _metric_names(result.calculated_metrics)
    ):
        if metric not in names:
            names.append(metric)
    return names


def _metric_names(metrics: list[dict[str, Any]]) -> list[str]:
    names = []
    for metric in metrics:
        name = str(metric.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _aggregation_from_expression(expression: str) -> str:
    text = str(expression or "")
    if re.search(r"\bCOUNT\s*\(\s*DISTINCT\b", text, re.IGNORECASE):
        return "COUNT_DISTINCT"
    matched = re.search(r"\b(SUM|AVG|MIN|MAX|COUNT)\s*\(", text, re.IGNORECASE)
    return matched.group(1).upper() if matched else ""


def _derived_metric_for_model(metric: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": str(metric.get("name") or "").strip(),
    }
    for key in (
        "base_metric",
        "base_metric_table",
        "time_period",
        "expression",
    ):
        if key == "time_period":
            value = normalize_time_period(metric.get(key))
        else:
            value = str(metric.get(key) or "").strip()
        if value:
            payload[key] = value
    aggregation = str(metric.get("aggregation") or "").strip().upper()
    if not aggregation:
        aggregation = _aggregation_from_expression(
            payload.get("expression", "")
        )
    if aggregation:
        payload["aggregation"] = aggregation
    return payload


def _derived_metrics_for_model(
    metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    seen = set()
    for metric in metrics:
        payload = _derived_metric_for_model(metric)
        name = payload.get("name")
        if name and name not in seen:
            seen.add(name)
            items.append(payload)
    return items


def metric_groups_for_model(
    result: TableInspectResult,
) -> dict[str, list[Any]]:
    """生成写入 models YAML 的分类指标名列表。"""
    return {
        "atomic_metrics": _metric_names(result.atomic_metrics),
        "derived_metrics": _derived_metrics_for_model(result.derived_metrics),
        "calculated_metrics": _metric_names(result.calculated_metrics),
    }


def _update_models_for_results(
    project: str,
    results: list[TableInspectResult],
    *,
    dry_run: bool,
    write_scope: str,
    existing_model_metadata: dict[str, dict[str, Any]] | None = None,
    model_paths: dict[str, Path] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
    include_model_metadata: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    write_scope = _validate_write_scope(write_scope)
    yaml_updates = []
    skipped_updates = []
    for result in results:
        existing_model = None
        if existing_model_metadata is not None:
            existing_model = existing_model_metadata.get(result.table_name)
        update = update_model_yaml(
            project,
            result,
            dry_run=dry_run,
            write_scope=write_scope,
            existing_model=existing_model,
            path=(model_paths or {}).get(result.table_name),
            resolution_policy=resolution_policy,
            include_model_metadata=include_model_metadata,
        )
        if result.status == "blocked":
            if update["changed"]:
                yaml_updates.append(update)
            else:
                skipped_updates.append(
                    {
                        "table": result.table_name,
                        "path": update.get(
                            "path",
                            str(
                                model_path_for_table(
                                    project,
                                    result.table_name,
                                )
                            ),
                        ),
                        "status": result.status,
                        "validation": result.validation,
                        "updated": False,
                        "reason": update.get(
                            "reason",
                            "validation_blocked",
                        ),
                        "warnings": update.get("warnings", []),
                        "write_scope": write_scope,
                    }
                )
            continue
        if update["changed"]:
            yaml_updates.append(update)
    return yaml_updates, skipped_updates


def write_model_updates_from_plan(
    project: str,
    results: list[TableInspectResult],
    plan: MetadataFlowPlan,
    *,
    dry_run: bool,
    use_plan_existing_metadata: bool = True,
    include_model_metadata: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _update_models_for_results(
        project,
        results,
        dry_run=dry_run,
        write_scope=plan.write_scope,
        existing_model_metadata=(
            plan.base_model_metadata if use_plan_existing_metadata else None
        ),
        model_paths=plan.write_targets.model_paths,
        resolution_policy=plan.resolution_policy,
        include_model_metadata=include_model_metadata,
    )


def _violation_count(
    results: list[TableInspectResult],
    metric_attr: str | None = None,
    *,
    existing_model_metadata: dict[str, dict[str, Any]] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
) -> int:
    """统计 DWD fact 中的非原子指标违规数量。"""
    count = 0
    existing_model_metadata = existing_model_metadata or {}
    for result in results:
        resolution = _layer_resolution_for_model(
            result,
            existing_model=existing_model_metadata.get(result.table_name),
            policy=resolution_policy,
        )
        if (
            resolution.applied_layer != "DWD"
            or resolution.table_type != "fact"
        ):
            continue
        if metric_attr:
            count += len(getattr(result, metric_attr))
        else:
            count += len(result.derived_metrics) + len(
                result.calculated_metrics
            )
    return count


def _metric_names_from_raw(raw_metrics: Any) -> list[str]:
    names = []
    if isinstance(raw_metrics, dict):
        iterable = []
        for group_metrics in raw_metrics.values():
            if isinstance(group_metrics, list):
                iterable.extend(group_metrics)
    elif isinstance(raw_metrics, list):
        iterable = raw_metrics
    else:
        iterable = []

    for item in iterable:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("column") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _extract_existing_metric_names(model_data: dict[str, Any]) -> list[str]:
    names = []
    for key in (
        "metrics",
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
    ):
        for name in _metric_names_from_raw(model_data.get(key, []) or []):
            if name and name not in names:
                names.append(name)
    return names


def _extract_existing_metric_groups(
    model_data: dict[str, Any],
) -> dict[str, list[str]]:
    return {
        "atomic_metrics": _metric_names_from_raw(
            model_data.get("atomic_metrics")
        ),
        "derived_metrics": _metric_names_from_raw(
            model_data.get("derived_metrics")
        ),
        "calculated_metrics": _metric_names_from_raw(
            model_data.get("calculated_metrics")
        ),
    }


def _layer_resolution_for_model(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None = None,
    policy: LayerResolutionPolicy | None = None,
) -> LayerResolution:
    existing_model = existing_model or {}
    policy = policy or LayerResolutionPolicy(mode="refresh")
    declared_layer = str(
        result.declared_layer or existing_model.get("layer") or ""
    ).strip()
    declared_table_type = _table_type_prior_for_model(
        result.table_name,
        declared_layer,
        existing_model,
    )
    return resolve_layer(
        LayerResolutionInput(
            table_name=result.table_name,
            declared_layer=declared_layer,
            declared_table_type=declared_table_type,
            fallback_layer=str(existing_model.get("layer") or declared_layer),
            fallback_table_type=declared_table_type,
            inspection_result=result,
            policy=policy,
        )
    )


def _table_type_prior_for_model(
    table_name: str,
    declared_layer: str,
    existing_model: dict[str, Any],
) -> str:
    existing_type = str(existing_model.get("table_type") or "").strip()
    if existing_type:
        return existing_type
    layer = str(declared_layer or existing_model.get("layer") or "").upper()
    return _infer_table_type(table_name, layer)


def layer_for_model(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None = None,
    policy: LayerResolutionPolicy | None = None,
) -> str:
    """返回应写入模型 YAML 的层级。维度表强制归入 DIM。"""
    return _layer_resolution_for_model(
        result,
        existing_model=existing_model,
        policy=policy,
    ).applied_layer


def _resolution_changes_inspection_contract(
    result: TableInspectResult,
    resolution: LayerResolution,
) -> bool:
    inspected_table_type = str(result.table_type or "").strip().lower()
    resolved_table_type = str(resolution.table_type or "").strip().lower()
    if inspected_table_type != resolved_table_type:
        return True
    if inspected_table_type != "fact":
        return False
    inspected_layer = str(result.inferred_layer or "").strip().upper()
    resolved_layer = str(resolution.applied_layer or "").strip().upper()
    return inspected_layer != resolved_layer


def _mark_resolution_reinspection_required(
    result: TableInspectResult,
    resolution: LayerResolution,
) -> None:
    if resolution.validation.get("llm_confidence_below_min"):
        message = (
            f"llm_confidence={resolution.llm_confidence} below "
            f"min_llm_confidence="
            f"{resolution.validation.get('min_llm_confidence')}"
        )
    elif _resolution_changes_inspection_contract(result, resolution):
        message = (
            f"inspected={result.inferred_layer}/{result.table_type}, "
            f"resolved={resolution.applied_layer}/{resolution.table_type}"
        )
    else:
        return
    validation = dict(result.validation or {})
    issues = list(validation.get(RESOLUTION_REINSPECTION_ERROR_KEY) or [])
    if message not in issues:
        issues.append(message)
    validation[RESOLUTION_REINSPECTION_ERROR_KEY] = issues
    result.validation = validation


def _inspection_resolution_is_eligible(
    result: TableInspectResult,
    resolution: LayerResolution,
) -> bool:
    """Return whether LLM-derived semantic fields may be consumed."""
    return bool(
        result.status != "blocked"
        and resolution.source == "table_inspector"
        and not resolution.validation.get("llm_confidence_below_min")
        and resolution.llm_confidence is not None
    )


def _metric_result_is_eligible_for_propagation(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None,
    resolution_policy: LayerResolutionPolicy,
) -> bool:
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing_model,
        policy=resolution_policy,
    )
    return bool(
        _inspection_resolution_is_eligible(result, resolution)
        and resolution.applied_layer == "DWD"
        and resolution.table_type == "fact"
    )


def _dimension_warnings_for_resolution(
    result: TableInspectResult,
    resolution: LayerResolution,
) -> list[dict[str, Any]]:
    if result.table_type != "dimension":
        return []
    if resolution.applied_layer != "DIM":
        return []
    inferred = str(result.inferred_layer or "").strip().upper()
    if inferred in ("", "DIM"):
        return []
    return [
        {
            "type": "dimension_layer_override",
            "severity": "warning",
            "message": (
                "LLM 表类型为 dimension，但 inferred_layer 不是 DIM；"
                "表信息回写时 layer 会按 dimension 规则强制写为 DIM"
            ),
            "inferred_layer": inferred,
            "applied_layer": "DIM",
        }
    ]


def warnings_for_resolution(
    result: TableInspectResult,
    resolution: LayerResolution,
) -> list[dict[str, Any]]:
    """返回 resolver 和模型元数据回写层面的警告。"""
    return list(resolution.warnings) + _dimension_warnings_for_resolution(
        result,
        resolution,
    )


def metadata_warnings_for_result(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None = None,
    policy: LayerResolutionPolicy | None = None,
) -> list[dict[str, Any]]:
    """返回模型元数据回写层面的警告。"""
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing_model,
        policy=policy,
    )
    return warnings_for_resolution(result, resolution)


def _validate_write_scope(write_scope: str) -> str:
    if write_scope not in WRITE_SCOPES:
        raise ValueError(
            f"write_scope 必须是 {', '.join(sorted(WRITE_SCOPES))} 之一"
        )
    return write_scope


def should_write_table_metadata(write_scope: str) -> bool:
    return _validate_write_scope(write_scope) in {"all", "table"}


def _blocked_table_metadata_preserves_contract(
    existing: dict[str, Any],
    resolution: LayerResolution,
) -> bool:
    """Return whether a blocked result can safely fill table metadata only."""
    if not existing:
        return True
    existing_layer = str(existing.get("layer") or "").strip().upper()
    existing_table_type = str(existing.get("table_type") or "").strip().lower()
    if not existing_table_type and any(
        key in existing
        for key in (
            "metrics",
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
    ):
        existing_table_type = "fact"
    return (
        not existing_layer or existing_layer == resolution.applied_layer
    ) and (
        not existing_table_type or existing_table_type == resolution.table_type
    )


def business_metadata_for_result(
    project: str,
    result: TableInspectResult,
    layer: str | None = None,
) -> dict[str, str]:
    """返回可安全写入 models 的业务域/板块元数据。"""
    business_config = get_business_domain_config(project)
    if not business_config:
        return {}

    applied_layer = str(layer or layer_for_model(result) or "").upper()
    metadata = {}
    data_domain = business_config.normalize_domain(result.inferred_data_domain)
    business_area = business_config.normalize_business_area(
        result.inferred_business_area
    )
    if applied_layer in DATA_DOMAIN_LAYERS and business_config.is_valid_domain(
        data_domain
    ):
        metadata["data_domain"] = data_domain
    if (
        applied_layer in BUSINESS_AREA_LAYERS
        and business_config.is_valid_business_area(business_area)
    ):
        metadata["business_area"] = business_area
    return metadata


def _existing_data_domain_for_write(
    business_config,
    value: Any,
) -> str:
    if not business_config:
        return ""
    normalized = business_config.normalize_domain(value)
    return normalized if business_config.is_valid_domain(normalized) else ""


def _existing_business_area_for_write(
    business_config,
    value: Any,
) -> str:
    if not business_config:
        return ""
    normalized = business_config.normalize_business_area(value)
    return (
        normalized
        if business_config.is_valid_business_area(normalized)
        else ""
    )


def _clean_existing_business_metadata_for_layer(
    project: str,
    metadata: dict[str, Any],
    layer: str,
) -> None:
    business_config = get_business_domain_config(project)
    applied_layer = str(layer or "").upper()
    if applied_layer in DATA_DOMAIN_LAYERS:
        data_domain = _existing_data_domain_for_write(
            business_config,
            metadata.get("data_domain"),
        )
        if data_domain:
            metadata["data_domain"] = data_domain
        else:
            metadata.pop("data_domain", None)
    else:
        metadata.pop("data_domain", None)

    if applied_layer in BUSINESS_AREA_LAYERS:
        business_area = _existing_business_area_for_write(
            business_config,
            metadata.get("business_area"),
        )
        if business_area:
            metadata["business_area"] = business_area
        else:
            metadata.pop("business_area", None)
    else:
        metadata.pop("business_area", None)


def should_write_metric_groups(
    result: TableInspectResult,
    write_scope: str = "all",
    *,
    applied_layer: str | None = None,
    table_type: str | None = None,
) -> bool:
    """判断是否需要按指标分组更新模型 YAML。"""
    if _validate_write_scope(write_scope) not in {"all", "metrics"}:
        return False
    effective_layer = str(applied_layer or result.inferred_layer or "").upper()
    effective_table_type = str(table_type or result.table_type or "").lower()
    return effective_layer in METRIC_LAYERS and effective_table_type == "fact"


def should_write_grain_metadata(
    result: TableInspectResult, write_scope: str = "all"
) -> bool:
    """判断是否需要更新 entity/grain 元数据。"""
    if _validate_write_scope(write_scope) not in {"all", "grain"}:
        return False
    return bool(
        result.entities
        or result.entity
        or result.related_entities
        or result.grain
    )


def _effective_entities(result: TableInspectResult) -> list[dict[str, Any]]:
    entities = normalize_entities(
        result.entities,
        result.entity,
        result.related_entities,
    )
    if entities:
        return entities

    inferred = []
    for key, code in _grain_key_entity_pairs(result.grain):
        inferred.append(
            {
                "code": code,
                "type": "foreign",
                "key_columns": [key],
            }
        )
    return normalize_entities(inferred)


def _dedupe_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for entity in entities:
        code = str(entity.get("code") or "").strip()
        keys = tuple(_as_string_list(entity.get("key_columns")))
        identity = (code, keys)
        if not code or identity in seen:
            continue
        deduped.append(entity)
        seen.add(identity)
    return deduped


def _canonical_entities_for_write(
    result: TableInspectResult,
    entities: list[dict[str, Any]],
    *,
    model_layer: str = "",
    model_table_type: str = "",
) -> list[dict[str, Any]]:
    if not entities:
        return []

    effective_layer = str(model_layer or result.declared_layer or "").upper()
    effective_table_type = str(
        model_table_type or result.table_type or ""
    ).lower()
    is_dimension_model = (
        effective_layer == "DIM" or effective_table_type == "dimension"
    )

    if effective_table_type == "fact" and not is_dimension_model:
        if effective_layer == "DWD":
            canonical = []
            for entity in entities:
                item = dict(entity)
                if str(item.get("type") or "").lower() == "primary":
                    item["type"] = "primary"
                else:
                    item["type"] = "foreign"
                item.pop("relationship", None)
                canonical.append(item)
            return _dedupe_entities(canonical)

        canonical = []
        for entity in entities:
            item = dict(entity)
            item["type"] = "foreign"
            item.pop("relationship", None)
            canonical.append(item)
        return _dedupe_entities(canonical)

    if not is_dimension_model:
        return _dedupe_entities(entities)

    primary = next(
        (
            entity
            for entity in entities
            if str(entity.get("type") or "").lower() == "primary"
        ),
        None,
    )
    if not primary:
        primary = next(
            (
                entity
                for entity in entities
                if str(entity.get("type") or "").lower() != "foreign"
            ),
            entities[0],
        )

    primary_code = str(primary.get("code") or "").strip()
    canonical_primary = dict(primary)
    canonical_primary["type"] = "primary"
    canonical_primary.pop("relationship", None)

    canonical = [canonical_primary]
    for entity in entities:
        code = str(entity.get("code") or "").strip()
        if not code or code == primary_code:
            continue
        item = dict(entity)
        entity_type = str(item.get("type") or "").strip().lower()
        if entity_type in {"unique", "natural"}:
            item["type"] = entity_type
            item.pop("relationship", None)
            canonical.append(item)
            continue
        item["type"] = "foreign"
        relationship = item.get("relationship")
        if isinstance(relationship, dict):
            relationship = dict(relationship)
        else:
            relationship = {}
        if not str(relationship.get("type") or "").strip():
            relationship["type"] = "many_to_one"
        if not str(relationship.get("from_entity") or "").strip():
            relationship["from_entity"] = primary_code
        item["relationship"] = relationship
        canonical.append(item)

    return _dedupe_entities(canonical)


def _effective_grain(grain: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(grain or {})
    entities = _as_string_list(payload.get("entities"))
    additional_key_columns = _as_string_list(
        payload.get("additional_key_columns")
    )
    time_column = str(payload.get("time_column") or "").strip()
    time_period = normalize_time_period(payload.get("time_period"))

    if (
        not entities
        and not additional_key_columns
        and not time_column
        and not time_period
    ):
        return {}

    normalized: dict[str, Any] = {}
    if entities:
        normalized["entities"] = entities
    if additional_key_columns:
        normalized["additional_key_columns"] = additional_key_columns
    if time_column:
        normalized["time_column"] = time_column
    if time_period:
        normalized["time_period"] = time_period
    return normalized


def _canonical_grain_for_write(
    grain: dict[str, Any], entities: list[dict[str, Any]]
) -> dict[str, Any]:
    if not grain or not entities:
        return grain

    entity_codes = [
        str(entity.get("code") or "").strip()
        for entity in entities
        if str(entity.get("code") or "").strip()
    ]
    grain_entities = _as_string_list(grain.get("entities"))
    if (
        grain_entities
        and entity_codes
        and len(grain_entities) == len(entity_codes)
        and any(code not in entity_codes for code in grain_entities)
    ):
        grain = dict(grain)
        grain["entities"] = entity_codes
    return grain


def update_model_yaml(
    project: str,
    result: TableInspectResult,
    *,
    dry_run: bool = False,
    write_scope: str = "all",
    existing_model: dict[str, Any] | None = None,
    path: Path | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
    include_model_metadata: bool = False,
) -> dict[str, Any]:
    """将单表 LLM 巡检元数据和指标名覆盖写入 models/{table}.yaml。"""
    write_scope = _validate_write_scope(write_scope)
    if path is None:
        path = model_path_for_table(project, result.table_name)
    existing = dict(existing_model) if existing_model is not None else {}
    if existing_model is None and path.exists():
        existing = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    if not isinstance(existing, dict):
        existing = {}
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing,
        policy=resolution_policy,
    )
    if result.status != "blocked":
        _mark_resolution_reinspection_required(result, resolution)
    resolution_warnings = warnings_for_resolution(result, resolution)
    requires_reinspection = bool(
        result.validation.get(RESOLUTION_REINSPECTION_ERROR_KEY)
    )
    blocked_contract_change = bool(
        result.status == "blocked"
        and not _blocked_table_metadata_preserves_contract(
            existing,
            resolution,
        )
    )
    write_blocked_table_metadata_only = (
        result.status == "blocked"
        and not requires_reinspection
        and not blocked_contract_change
        and not any(
            result.validation.get(key)
            for key in TABLE_METADATA_BLOCKING_VALIDATION_KEYS
        )
        and result.confidence > 0
        and resolution.source == "table_inspector"
        and should_write_table_metadata(write_scope)
    )

    if result.status == "blocked" and not write_blocked_table_metadata_only:
        can_migrate_grain = (
            not requires_reinspection
            and not blocked_contract_change
            and write_scope in {"all", "grain"}
            and any(
                key in existing
                for key in (
                    "entities",
                    "entity",
                    "related_entities",
                    "grain",
                )
            )
        )
        if can_migrate_grain:
            updated = dict(existing)
            existing_layer = str(existing.get("layer") or "").upper()
            existing_table_type = str(existing.get("table_type") or "").lower()
            existing_entities = normalize_entities(
                existing.get("entities"),
                existing.get("entity"),
                existing.get("related_entities"),
            )
            if not existing_entities:
                existing_entities = normalize_entities(
                    [
                        {
                            "code": code,
                            "type": "foreign",
                            "key_columns": [key],
                        }
                        for key, code in _grain_key_entity_pairs(
                            existing.get("grain") or {}
                        )
                    ]
                )
            if existing_table_type or existing_layer == "DIM":
                entity_metadata = _canonical_entities_for_write(
                    result,
                    existing_entities,
                    model_layer=existing_layer,
                    model_table_type=(
                        existing_table_type
                        or ("dimension" if existing_layer == "DIM" else "")
                    ),
                )
            else:
                entity_metadata = _dedupe_entities(existing_entities)
            grain_metadata = _effective_grain(existing.get("grain"))
            grain_metadata = _canonical_grain_for_write(
                grain_metadata,
                entity_metadata,
            )
            if entity_metadata:
                updated["entities"] = entity_metadata
            else:
                updated.pop("entities", None)
            updated.pop("entity", None)
            updated.pop("related_entities", None)
            if grain_metadata:
                updated["grain"] = grain_metadata
            else:
                updated.pop("grain", None)
            if existing_layer:
                _clean_existing_business_metadata_for_layer(
                    project,
                    updated,
                    existing_layer,
                )
            changed = updated != existing
            if not dry_run and changed:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    yaml.safe_dump(
                        updated, allow_unicode=True, sort_keys=False
                    ),
                    encoding=TEXT_ENCODING,
                )
            update = {
                "table": result.table_name,
                "path": str(path),
                "status": result.status,
                "changed": changed,
                "metadata_changed": False,
                "metric_changed": False,
                "metric_count": 0,
                "new_metric_count": 0,
                "removed_metric_count": 0,
                "grain_changed": changed,
                "updated": bool(changed and not dry_run),
                "reason": "validation_blocked_schema_migration",
                "warnings": resolution_warnings,
                "write_scope": write_scope,
            }
            if include_model_metadata:
                update["model_metadata"] = updated
            return update
        update = {
            "table": result.table_name,
            "path": str(path),
            "status": result.status,
            "changed": False,
            "metadata_changed": False,
            "metric_changed": False,
            "metric_count": 0,
            "new_metric_count": 0,
            "removed_metric_count": 0,
            "grain_changed": False,
            "updated": False,
            "reason": (
                RESOLUTION_REINSPECTION_ERROR_KEY
                if requires_reinspection
                else (
                    "validation_blocked_contract_change"
                    if blocked_contract_change
                    else "validation_blocked"
                )
            ),
            "warnings": resolution_warnings,
            "write_scope": write_scope,
        }
        if include_model_metadata:
            update["model_metadata"] = existing
        return update

    existing_metrics = _extract_existing_metric_names(existing)
    existing_groups = _extract_existing_metric_groups(existing)
    has_existing_metric_fields = any(
        key in existing
        for key in (
            "metrics",
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
    )
    write_table_metadata = should_write_table_metadata(write_scope)
    metric_contract_active = should_write_metric_groups(
        result,
        write_scope,
        applied_layer=resolution.applied_layer,
        table_type=resolution.table_type,
    )
    write_metric_groups = bool(
        not write_blocked_table_metadata_only
        and _validate_write_scope(write_scope) in {"all", "metrics"}
        and (metric_contract_active or has_existing_metric_fields)
    )
    detected_groups = (
        metric_groups_for_model(result)
        if metric_contract_active
        else {
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
        }
    )
    write_grain_metadata = (
        False
        if write_blocked_table_metadata_only
        else should_write_grain_metadata(result, write_scope)
    )
    detected_metrics = (
        metric_names_for_model(result) if metric_contract_active else []
    )

    updated = dict(existing)
    previous_layer = existing.get("layer")
    previous_table_type = existing.get("table_type")
    previous_data_domain = existing.get("data_domain")
    previous_business_area = existing.get("business_area")
    previous_dimension_role = existing.get("dimension_role")
    previous_dimension_content_type = existing.get("dimension_content_type")
    should_write_base_fields = (
        write_table_metadata
        or bool(detected_metrics)
        or (write_metric_groups and has_existing_metric_fields)
        or write_grain_metadata
    )
    if should_write_base_fields:
        updated.setdefault("version", 2)
        updated.setdefault("name", result.table_name)
    if write_table_metadata:
        applied_layer = resolution.applied_layer
        updated["layer"] = applied_layer
        updated["table_type"] = resolution.table_type
        business_config = get_business_domain_config(project)
        business_metadata = {}
        if business_config:
            business_metadata = business_metadata_for_result(
                project,
                result,
                applied_layer,
            )
        if applied_layer in DATA_DOMAIN_LAYERS:
            if "data_domain" in business_metadata:
                updated["data_domain"] = business_metadata["data_domain"]
            elif business_config:
                existing_data_domain = _existing_data_domain_for_write(
                    business_config,
                    updated.get("data_domain"),
                )
                if existing_data_domain:
                    updated["data_domain"] = existing_data_domain
                else:
                    updated.pop("data_domain", None)
            else:
                updated.pop("data_domain", None)
        else:
            updated.pop("data_domain", None)
        if applied_layer in BUSINESS_AREA_LAYERS:
            if "business_area" in business_metadata:
                updated["business_area"] = business_metadata["business_area"]
            elif business_config:
                existing_business_area = _existing_business_area_for_write(
                    business_config,
                    updated.get("business_area"),
                )
                if existing_business_area:
                    updated["business_area"] = existing_business_area
                else:
                    updated.pop("business_area", None)
            else:
                updated.pop("business_area", None)
        else:
            updated.pop("business_area", None)
        if applied_layer == "DIM":
            if result.dimension_role:
                updated["dimension_role"] = result.dimension_role
            if result.dimension_content_type:
                updated["dimension_content_type"] = (
                    result.dimension_content_type
                )
        else:
            updated.pop("dimension_role", None)
            updated.pop("dimension_content_type", None)

    if should_write_base_fields and (
        "execution" in updated or "config" in updated or write_table_metadata
    ):
        materialized_layer = str(
            updated.get("layer") or result.declared_layer or ""
        ).upper()
        execution_payload = dict(updated.get("execution") or {})
        execution_payload["materialized"] = _materialized_for_write(
            execution_payload.get("materialized"),
            materialized_layer,
        )
        updated["execution"] = execution_payload
        _drop_deprecated_execution_config(updated)

    if write_metric_groups and detected_metrics:
        if detected_groups["atomic_metrics"]:
            updated["atomic_metrics"] = detected_groups["atomic_metrics"]
        else:
            updated.pop("atomic_metrics", None)
        if detected_groups["derived_metrics"]:
            updated["derived_metrics"] = detected_groups["derived_metrics"]
        else:
            updated.pop("derived_metrics", None)
        if detected_groups["calculated_metrics"]:
            updated["calculated_metrics"] = detected_groups[
                "calculated_metrics"
            ]
        else:
            updated.pop("calculated_metrics", None)
        updated.pop("metrics", None)
    elif write_metric_groups:
        updated.pop("metrics", None)
        updated.pop("atomic_metrics", None)
        updated.pop("derived_metrics", None)
        updated.pop("calculated_metrics", None)

    previous_grain = existing.get("grain")
    previous_entities = existing.get("entities")
    previous_related_entities = existing.get("related_entities")
    has_existing_grain_metadata = any(
        key in existing
        for key in (
            "entities",
            "entity",
            "related_entities",
            "grain",
        )
    )
    if (
        not write_blocked_table_metadata_only
        and not write_grain_metadata
        and has_existing_grain_metadata
    ):
        write_grain_metadata = _validate_write_scope(write_scope) in {
            "all",
            "grain",
        }
    grain_metadata = _effective_grain(result.grain)
    entity_metadata = _canonical_entities_for_write(
        result,
        _effective_entities(result)
        or normalize_entities(
            existing.get("entities"),
            existing.get("entity"),
            existing.get("related_entities"),
        ),
        model_layer=str(
            updated.get("layer")
            or existing.get("layer")
            or resolution.applied_layer
        ),
        model_table_type=resolution.table_type,
    )
    grain_metadata = _canonical_grain_for_write(
        grain_metadata,
        entity_metadata,
    )
    if write_grain_metadata:
        if entity_metadata:
            updated["entities"] = entity_metadata
        else:
            updated.pop("entities", None)
        updated.pop("entity", None)
        updated.pop("related_entities", None)
        if grain_metadata:
            updated["grain"] = grain_metadata
        else:
            updated.pop("grain", None)

    if should_write_base_fields:
        _clean_existing_business_metadata_for_layer(
            project,
            updated,
            updated.get("layer")
            or existing.get("layer")
            or resolution.applied_layer,
        )

    changed = updated != existing
    metadata_changed = write_table_metadata and (
        updated.get("layer") != previous_layer
        or updated.get("table_type") != previous_table_type
        or updated.get("data_domain") != previous_data_domain
        or updated.get("business_area") != previous_business_area
        or updated.get("dimension_role") != previous_dimension_role
        or (
            updated.get("dimension_content_type")
            != previous_dimension_content_type
        )
    )
    metric_changed = write_metric_groups and (
        has_existing_metric_fields or detected_groups != existing_groups
    )
    grain_changed = write_grain_metadata and (
        updated.get("grain") != previous_grain
        or updated.get("entities") != previous_entities
        or updated.get("entity") != existing.get("entity")
        or updated.get("related_entities") != previous_related_entities
    )
    if not dry_run and changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(updated, allow_unicode=True, sort_keys=False),
            encoding=TEXT_ENCODING,
        )

    new_metric_count = 0
    removed_metric_count = 0
    if write_metric_groups:
        new_metric_count = len(
            [name for name in detected_metrics if name not in existing_metrics]
        )
        removed_metric_count = len(
            [name for name in existing_metrics if name not in detected_metrics]
        )

    update = {
        "table": result.table_name,
        "path": str(path),
        "status": result.status,
        "changed": changed,
        "metadata_changed": metadata_changed,
        "metric_changed": metric_changed,
        "previous_layer": previous_layer,
        "layer": updated.get("layer"),
        "previous_table_type": previous_table_type,
        "table_type": updated.get("table_type"),
        "previous_data_domain": previous_data_domain,
        "data_domain": updated.get("data_domain"),
        "previous_business_area": previous_business_area,
        "business_area": updated.get("business_area"),
        "previous_dimension_role": previous_dimension_role,
        "dimension_role": updated.get("dimension_role"),
        "previous_dimension_content_type": previous_dimension_content_type,
        "dimension_content_type": updated.get("dimension_content_type"),
        "warnings": resolution_warnings,
        "write_scope": write_scope,
        "metric_count": len(detected_metrics),
        "new_metric_count": new_metric_count,
        "removed_metric_count": removed_metric_count,
        "grain_changed": grain_changed,
        "updated": bool(changed and not dry_run),
    }
    if write_blocked_table_metadata_only:
        update["reason"] = "validation_blocked_table_metadata_only"
    if include_model_metadata:
        update["model_metadata"] = updated
    return update


def _existing_model_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    return raw if isinstance(raw, dict) else {}


def _materialized_for_write(value: Any, layer: str) -> str:
    materialized = str(value or "").strip().lower()
    if materialized in {"incremental", "full"}:
        return materialized
    if materialized == "snapshot":
        return "incremental"
    return _materialized_for_layer(layer)


def _drop_deprecated_execution_config(model: dict[str, Any]) -> None:
    raw_config = model.get("config")
    if not isinstance(raw_config, dict):
        return

    config_payload = dict(raw_config)
    for key in EXECUTION_CONFIG_FIELDS:
        config_payload.pop(key, None)

    if config_payload:
        model["config"] = config_payload
    else:
        model.pop("config", None)
