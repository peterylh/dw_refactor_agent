#!/usr/bin/env python3
"""
LLM 表巡检与模型元数据回写工具。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块、维度表 entity/related_entities、DWS grain 以及
DWD/DWS 表中的指标字段回写到 models/{table}.yaml，并把 DWD 事实表的
非原子指标输出为违规项。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

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
    MetadataWriteTargets,
    build_generate_plan,
    build_refresh_plan,
    catalog_plan_for_generate,
    catalog_plan_for_refresh,
    run_inspection_pipeline,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspector,
    TableInspectResult,
    normalize_chat_completions_url,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    dict_to_result as inspect_dict_to_result,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    result_to_dict as inspect_result_to_dict,
)
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    _infer_table_type,
    _layer_from_table_name,
    _materialized_for_layer,
    _normalize_catalog_code,
    build_business_semantics_catalog_from_inspection,
    build_initial_business_semantics_catalog,
    catalog_mapping_for_model,
    load_business_semantics_catalog,
    write_initial_business_semantics_catalog,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    normalize_entities,
)
from dw_refactor_agent.assessment.project_facts.time_period import (
    normalize_time_period,
)
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,
    TEXT_ENCODING,
    assess_cache_path,
    asset_role_for_layer,
    business_semantics_paths,
    get_business_domain_config,
    load_model_metadata,
    model_metadata_result_path,
)
from dw_refactor_agent.execution.model_config import EXECUTION_CONFIG_FIELDS
from dw_refactor_agent.lineage.table_graph import load_lineage_data

WRITE_SCOPES = {"all", "table", "metrics", "grain", "business"}
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
TABLE_METADATA_BLOCKING_VALIDATION_KEYS = {
    RESOLUTION_REINSPECTION_ERROR_KEY,
    "inconsistent_layer_table_types",
    "inconsistent_layer_sql",
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


@dataclass
class GenerateModelMetadataPlan:
    model_metadata: dict[str, dict[str, Any]]
    model_paths: dict[str, Path]
    model_updates: list[dict[str, Any]]
    planned_deleted_model_files: list[str]


def _new_table_inspector(
    api_key: str,
    *,
    model: str,
    base_url: str | None = None,
    cache_file: Path | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
) -> TableInspector:
    kwargs: dict[str, Any] = {
        "model": model,
        "cache_file": cache_file,
        "max_retries": max_retries,
        "parallelism": parallelism,
        "request_timeout": request_timeout,
    }
    if base_url:
        kwargs["base_url"] = normalize_chat_completions_url(base_url)
    try:
        return TableInspector(api_key, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        kwargs.pop("base_url", None)
        kwargs.pop("request_timeout", None)
        return TableInspector(api_key, **kwargs)


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
    project_dir = PROJECT_ROOT / project_cfg["dir"]
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


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = str(value or "").strip()
    return [value] if value else []


def _is_time_grain_key(key: str, time_column: str = "") -> bool:
    key_lower = str(key or "").strip().lower()
    if not key_lower:
        return True
    if time_column and key_lower == str(time_column).strip().lower():
        return True
    return any(
        token in key_lower
        for token in (
            "date",
            "day",
            "dt",
            "hour",
            "month",
            "period",
            "quarter",
            "time",
            "week",
            "year",
        )
    )


def _grain_key_entity_pairs(
    grain: dict[str, Any], entities: list[dict[str, Any]] | None = None
) -> list[tuple[str, str]]:
    if not isinstance(grain, dict):
        return []
    grain_entities = _as_string_list(grain.get("entities"))
    if entities:
        pairs = []
        wanted = set(grain_entities)
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            code = str(entity.get("code") or "").strip()
            if wanted and code not in wanted:
                continue
            for key in _as_string_list(entity.get("key_columns")):
                pairs.append((key, code))
        if pairs:
            return pairs

    keys = _as_string_list(grain.get("keys"))
    time_column = str(grain.get("time_column") or "")
    entity_keys = [
        key for key in keys if not _is_time_grain_key(key, time_column)
    ]
    if not entity_keys or not grain_entities:
        return []
    if len(grain_entities) == len(entity_keys):
        return list(zip(entity_keys, grain_entities))
    if len(grain_entities) == 1:
        return [(key, grain_entities[0]) for key in entity_keys]

    pairs = []
    for entity in grain_entities:
        entity_prefix = entity.lower()
        for key in entity_keys:
            if key.lower().startswith(entity_prefix):
                pairs.append((key, entity))
                break
    return pairs


def _build_grain_entity_index(
    results: list[TableInspectResult],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for result in results:
        if result.status == "blocked":
            continue
        for key, entity in _grain_key_entity_pairs(
            result.grain, result.entities
        ):
            index.setdefault(key, entity)
    return index


def _column_comments_from_ddl(ddl: str) -> dict[str, str]:
    comments = {}
    for line in str(ddl or "").splitlines():
        name_match = re.match(r"\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s+", line)
        if not name_match:
            continue
        name = name_match.group(1)
        if name.upper() in DDL_NON_COLUMN_PREFIXES:
            continue
        comment_match = re.search(
            r"COMMENT\s+'([^']*)'", line, flags=re.IGNORECASE
        )
        comments[name] = (
            comment_match.group(1).strip() if comment_match else ""
        )
    return comments


def _entity_name_from_comment(comment: str) -> str:
    name = str(comment or "").strip()
    for suffix in ("ID", "Id", "id", "编号", "编码", "标识"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def _related_entity_identity(
    item: dict[str, Any],
) -> tuple[str, tuple[str, ...]]:
    return (
        str(item.get("code") or "").strip(),
        tuple(_as_string_list(item.get("key_columns"))),
    )


def _merge_related_entities(
    current: list[dict[str, Any]], discovered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for item in current + discovered:
        if not isinstance(item, dict):
            continue
        identity = _related_entity_identity(item)
        if not identity[0] or not identity[1] or identity in seen:
            continue
        merged.append(item)
        seen.add(identity)
    return merged


def discover_related_entities_from_grain(
    result: TableInspectResult,
    context: TableContext | None,
    grain_entity_index: dict[str, str],
) -> list[dict[str, Any]]:
    """从 DWS grain 使用情况反推维度表承载的层级实体。"""
    if result.table_type != "dimension" or not result.entity or not context:
        return []
    primary_code = str(result.entity.get("code") or "").strip()
    primary_keys = set(_as_string_list(result.entity.get("key_columns")))
    if not primary_code or not primary_keys:
        return []

    comments_by_column = _column_comments_from_ddl(context.ddl)
    discovered = []
    for key_column, related_code in sorted(grain_entity_index.items()):
        if key_column in primary_keys or related_code == primary_code:
            continue
        if key_column not in comments_by_column:
            continue
        comment = comments_by_column.get(key_column, "")
        discovered.append(
            {
                "code": related_code,
                "name": _entity_name_from_comment(comment),
                "key_columns": [key_column],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": primary_code,
                },
            }
        )
    return discovered


def enrich_results_with_related_entities(
    results: list[TableInspectResult], contexts: dict[str, TableContext]
) -> None:
    grain_entity_index = _build_grain_entity_index(results)
    for result in results:
        context = contexts.get(result.table_name)
        if not grain_entity_index:
            continue
        discovered = discover_related_entities_from_grain(
            result,
            context,
            grain_entity_index,
        )
        if discovered:
            result.related_entities = _merge_related_entities(
                result.related_entities,
                discovered,
            )
            result.entities = normalize_entities(
                result.entities,
                result.entity,
                result.related_entities,
            )


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
        item["type"] = "foreign"
        relationship = item.get("relationship")
        if isinstance(relationship, dict):
            relationship = dict(relationship)
        else:
            relationship = {"type": "many_to_one"}
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


def _catalog_table_assets(project: str) -> dict[str, dict[str, Any]]:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = PROJECT_ROOT / project_cfg["dir"]
    return (
        build_asset_catalog(
            [],
            load_model_metadata(project),
            project_dir,
        ).get("tables")
        or {}
    )


def _project_dir(project: str) -> Path:
    project_cfg = PROJECT_CONFIG[project]
    return PROJECT_ROOT / project_cfg["dir"]


def _model_roots(project: str) -> list[Path]:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = _project_dir(project)
    catalog = str(project_cfg.get("catalog") or "internal")
    database = str(project_cfg.get("db") or "")
    return [
        project_dir / "ods" / "models" / catalog / database,
        project_dir / "mid" / "models",
        project_dir / "ads" / "models",
    ]


def _model_files(project: str) -> list[Path]:
    files: list[Path] = []
    for root in _model_roots(project):
        if root.exists():
            files.extend(sorted(root.rglob("*.yaml")))
    return sorted(files)


def _generated_model_path_for_table(
    project: str,
    table_name: str,
    layer: str | None,
) -> Path:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = _project_dir(project)
    catalog = str(project_cfg.get("catalog") or "internal")
    database = str(project_cfg.get("db") or "")
    filename = f"{table_name}.yaml"
    role = asset_role_for_layer(layer)
    if role == "ods":
        return project_dir / "ods" / "models" / catalog / database / filename
    if role in {"mid", "ads"}:
        return project_dir / role / "models" / filename
    return project_dir / "mid" / "models" / filename


def _generate_model_table_assets(project: str) -> dict[str, dict[str, Any]]:
    return (
        build_asset_catalog(
            [],
            {},
            _project_dir(project),
        ).get("tables")
        or {}
    )


def _ensure_metadata_catalog_skeleton(
    project: str,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    init_result = write_initial_business_semantics_catalog(
        project,
        overwrite=False,
        dry_run=dry_run,
    )
    written_names = sorted(init_result.get("written_names") or [])
    catalog = init_result.get("catalog") or load_business_semantics_catalog(
        project
    )
    report = {
        "catalog_initialized": bool(written_names),
        "catalog_init_written_names": [] if dry_run else written_names,
        "planned_catalog_written_names": written_names if dry_run else [],
    }
    return catalog, report


def _generate_metadata_catalog_for_plan(
    project: str,
    *,
    dry_run: bool,
    update_catalog: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if update_catalog:
        return _ensure_metadata_catalog_skeleton(project, dry_run=dry_run)

    catalog = load_business_semantics_catalog(project)
    if not catalog:
        catalog = build_initial_business_semantics_catalog(
            project,
            base_catalog={},
        )
    return catalog, {
        "catalog_initialized": False,
        "catalog_init_written_names": [],
        "planned_catalog_written_names": [],
    }


def _catalog_entries_by_code(
    catalog: dict[str, Any],
    key: str,
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for entry in catalog.get(key) or []:
        if not isinstance(entry, dict):
            continue
        code = _normalize_catalog_code(entry.get("code"))
        if not code:
            continue
        normalized = dict(entry)
        normalized["code"] = code
        normalized.pop("tables", None)
        entries[code] = normalized
    return entries


def _catalog_entry_changes(
    base_catalog: dict[str, Any],
    candidate_catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    changes = []
    for section in ("business_processes", "semantic_subjects"):
        before = _catalog_entries_by_code(base_catalog, section)
        after = _catalog_entries_by_code(candidate_catalog, section)
        for code, entry in sorted(after.items()):
            previous = before.get(code)
            if previous is None:
                changes.append(
                    {
                        "section": section,
                        "action": "add",
                        "code": code,
                        "entry": entry,
                    }
                )
            elif previous != entry:
                changes.append(
                    {
                        "section": section,
                        "action": "update",
                        "code": code,
                        "previous": previous,
                        "entry": entry,
                    }
                )
    return changes


def _empty_catalog_update_report() -> dict[str, Any]:
    return {
        "catalog_update": None,
        "catalog_change_count": 0,
        "catalog_updates": [],
        "planned_catalog_updates": [],
    }


def _resolved_catalog_results_from_inspection_results(
    results: list[TableInspectResult],
    *,
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
) -> list[TableInspectResult]:
    resolved_results = []
    for result in results or []:
        resolution = _layer_resolution_for_model(
            result,
            existing_model=model_metadata.get(result.table_name, {}),
            policy=resolution_policy,
        )
        if not _inspection_resolution_is_eligible(result, resolution):
            continue
        resolved = replace(
            result,
            inferred_layer=resolution.applied_layer,
            table_type=resolution.table_type,
        )
        if resolved.table_type not in {"fact", "dimension"}:
            continue
        resolved_results.append(resolved)
    return resolved_results


def _resolved_catalog_results_from_llm_result(
    llm_result: dict[str, Any],
    *,
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
) -> list[TableInspectResult]:
    results = []
    for item in llm_result.get("tables") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() == "blocked":
            continue
        results.append(inspect_dict_to_result(item))
    return _resolved_catalog_results_from_inspection_results(
        results,
        model_metadata=model_metadata,
        resolution_policy=resolution_policy,
    )


def _merge_llm_catalog_discoveries(
    project: str,
    *,
    llm_result: dict[str, Any] | None,
    inspection_results: list[TableInspectResult] | None = None,
    base_catalog: dict[str, Any],
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
    dry_run: bool,
) -> dict[str, Any]:
    if inspection_results is None and not llm_result:
        return _empty_catalog_update_report()

    if inspection_results is not None:
        catalog_results = _resolved_catalog_results_from_inspection_results(
            inspection_results,
            model_metadata=model_metadata,
            resolution_policy=resolution_policy,
        )
    else:
        catalog_results = _resolved_catalog_results_from_llm_result(
            llm_result or {},
            model_metadata=model_metadata,
            resolution_policy=resolution_policy,
        )
    candidate_catalog = build_business_semantics_catalog_from_inspection(
        project,
        catalog_results,
        base_catalog=base_catalog,
    )
    changes = _catalog_entry_changes(base_catalog, candidate_catalog)
    if not changes:
        return _empty_catalog_update_report()

    write_result = write_initial_business_semantics_catalog(
        project,
        overwrite=True,
        dry_run=dry_run,
        inspection_results=catalog_results,
    )
    written_names = sorted(write_result.get("written_names") or [])
    update = {
        "project": project,
        "path": write_result.get("path"),
        "paths": write_result.get("paths") or {},
        "changed": True,
        "updated": bool(write_result.get("updated")),
        "dry_run": dry_run,
        "change_count": len(changes),
        "changes": changes,
        "written_names": [] if dry_run else written_names,
        "planned_written_names": written_names if dry_run else [],
    }
    return {
        "catalog_update": update,
        "catalog_change_count": len(changes),
        "catalog_updates": [] if dry_run else changes,
        "planned_catalog_updates": changes if dry_run else [],
    }


def _asset_role_from_generate_asset(
    project: str,
    asset: dict[str, Any],
) -> str:
    ddl = asset.get("ddl") or {}
    ddl_path = ddl.get("path")
    if not ddl_path:
        return ""
    try:
        parts = Path(ddl_path).relative_to(_project_dir(project)).parts
    except ValueError:
        return ""
    if (
        len(parts) >= 2
        and parts[1] == "ddl"
        and parts[0]
        in {
            "ods",
            "mid",
            "ads",
        }
    ):
        return parts[0]
    return ""


def _generate_asset_role_layer(asset_role: str) -> str:
    if asset_role == "ods":
        return "ODS"
    if asset_role == "ads":
        return "ADS"
    if asset_role == "mid":
        return "DWD"
    return ""


def _generate_model_mapping(
    catalog: dict[str, Any],
    table_name: str,
    *,
    asset_role: str = "",
) -> dict[str, Any]:
    mapping = catalog_mapping_for_model(catalog, table_name, {})
    asset_layer = _generate_asset_role_layer(asset_role)
    mapped_layer = str(mapping.get("layer") or "").upper()
    name_layer = _layer_from_table_name(table_name)
    if mapped_layer == "OTHER":
        mapped_layer = ""
    if name_layer == "OTHER":
        name_layer = ""
    if asset_layer in {"ODS", "ADS"}:
        layer = asset_layer
    else:
        layer = mapped_layer or name_layer or asset_layer or "OTHER"
    table_type = str(
        mapping.get("table_type") or _infer_table_type(table_name, layer)
    ).strip()
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name=table_name,
            fallback_layer=layer,
            fallback_table_type=table_type,
            policy=LayerResolutionPolicy(
                mode="generate",
                candidate_layers=("DWD", "DWS", "DIM"),
                fixed_layer=layer if layer in {"ODS", "ADS"} else "",
                fallback_source="direct_rule",
            ),
        )
    )
    layer = resolution.applied_layer
    table_type = resolution.table_type
    materialized = str(
        mapping.get("materialized") or _materialized_for_layer(layer)
    ).strip()
    mapping.update(
        {
            "table": table_name,
            "layer": layer,
            "table_type": table_type or "other",
            "materialized": materialized,
        }
    )
    return mapping


def _generate_model_update_payload(
    *,
    table_name: str,
    path: Path,
    previous: dict[str, Any],
    updated: dict[str, Any],
    dry_run: bool,
    write_scope: str,
    source: str = "direct_generation",
) -> dict[str, Any]:
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
    changed = updated != previous
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
        "source": source,
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


def plan_generate_model_metadata(
    project: str,
    catalog: dict[str, Any],
    *,
    replace_existing_models: bool,
    write_scope: str,
) -> GenerateModelMetadataPlan:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("generate 仅支持 write_scope=all/table/business")

    model_files = _model_files(project)
    planned_deleted_model_files = (
        [str(path) for path in model_files] if replace_existing_models else []
    )
    model_metadata: dict[str, dict[str, Any]] = {}
    model_paths: dict[str, Path] = {}
    model_updates = []
    for table_name, asset in sorted(
        _generate_model_table_assets(project).items()
    ):
        ddl = asset.get("ddl") or {}
        if not ddl.get("exists"):
            continue
        mapping = _generate_model_mapping(
            catalog,
            table_name,
            asset_role=_asset_role_from_generate_asset(project, asset),
        )
        path = _generated_model_path_for_table(
            project,
            table_name,
            mapping.get("layer"),
        )
        existing = (
            {} if replace_existing_models else _existing_model_data(path)
        )
        updated = _catalog_model_payload(
            table_name=table_name,
            existing=existing,
            mapping=mapping,
        )
        model_metadata[table_name] = updated
        model_paths[table_name] = path
        model_updates.append(
            _generate_model_update_payload(
                table_name=table_name,
                path=path,
                previous=dict(existing),
                updated=updated,
                dry_run=True,
                write_scope=write_scope,
            )
        )
    return GenerateModelMetadataPlan(
        model_metadata=model_metadata,
        model_paths=model_paths,
        model_updates=model_updates,
        planned_deleted_model_files=planned_deleted_model_files,
    )


def _write_generated_model_metadata(
    project: str,
    plan: MetadataFlowPlan,
    final_model_metadata: dict[str, dict[str, Any]],
    *,
    dry_run: bool,
    delete_existing: bool,
    refinement_updates: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    deleted_model_files: list[str] = []
    if delete_existing and not dry_run:
        for path in _model_files(project):
            path.unlink()
            deleted_model_files.append(str(path))
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    refinements_by_table = {
        str(update.get("table") or ""): update
        for update in refinement_updates or []
        if isinstance(update, dict) and str(update.get("table") or "")
    }
    model_updates = []
    for table_name, metadata in sorted(final_model_metadata.items()):
        path = plan.write_targets.model_paths.get(table_name)
        if path is None:
            path = _generated_model_path_for_table(
                project,
                table_name,
                metadata.get("layer"),
            )
        previous = {} if delete_existing else _existing_model_data(path)
        update = _generate_model_update_payload(
            table_name=table_name,
            path=path,
            previous=dict(previous),
            updated=metadata,
            dry_run=dry_run,
            write_scope=plan.write_scope,
        )
        if table_name in refinements_by_table:
            update = _merge_final_update_with_refinement(
                update,
                refinements_by_table[table_name],
            )
        if update["changed"] and not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(
                    metadata,
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding=TEXT_ENCODING,
            )
        model_updates.append(update)

    if not dry_run:
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    return model_updates, deleted_model_files


def _merge_final_update_with_refinement(
    final_update: dict[str, Any],
    refinement_update: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(refinement_update)
    merged.pop("model_metadata", None)
    merged["path"] = final_update.get("path")
    merged["changed"] = bool(
        final_update.get("changed") or refinement_update.get("changed")
    )
    merged["metadata_changed"] = bool(
        final_update.get("metadata_changed")
        or refinement_update.get("metadata_changed")
    )
    merged["business_changed"] = bool(
        final_update.get("business_changed")
        or refinement_update.get("business_changed")
    )
    merged["updated"] = final_update.get("updated", False)
    merged["source"] = "llm_refinement"
    for key in (
        "write_scope",
        "layer",
        "table_type",
        "data_domain",
        "business_area",
        "business_process",
        "semantic_subject",
        "dimension_role",
        "dimension_content_type",
    ):
        if key in final_update:
            merged[key] = final_update[key]
    return merged


def _final_model_metadata_with_refinements(
    base_model_metadata: dict[str, dict[str, Any]],
    llm_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    final_model_metadata = {
        table_name: dict(metadata)
        for table_name, metadata in base_model_metadata.items()
    }
    for update in llm_result.get("model_updates") or []:
        table_name = str(update.get("table") or "").strip()
        if not table_name:
            continue
        refined_metadata = update.get("model_metadata")
        if not isinstance(refined_metadata, dict):
            continue
        if update.get("status") == "blocked" and update.get("reason") not in {
            "validation_blocked_schema_migration",
            "validation_blocked_table_metadata_only",
        }:
            continue
        final_model_metadata[table_name] = dict(refined_metadata)
    return final_model_metadata


def _strip_internal_model_metadata(result: dict[str, Any] | None) -> None:
    if not result:
        return
    for update in result.get("model_updates") or []:
        if isinstance(update, dict):
            update.pop("model_metadata", None)


def run_generate_model_metadata(
    project: str,
    *,
    api_key: str | None = None,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    write_scope: str = "all",
    update_catalog: bool = True,
    replace_existing_models: bool = True,
    show_progress: bool = False,
    expose_layer_hints: bool = True,
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("generate 仅支持 write_scope=all/table/business")

    catalog, catalog_report = _generate_metadata_catalog_for_plan(
        project,
        dry_run=dry_run,
        update_catalog=update_catalog,
    )
    base_plan = plan_generate_model_metadata(
        project,
        catalog,
        replace_existing_models=replace_existing_models,
        write_scope=write_scope,
    )

    generate_plan = build_generate_plan(
        project,
        write_scope=write_scope,
        base_model_metadata=base_plan.model_metadata,
        model_paths=base_plan.model_paths,
        planned_deleted_model_files=base_plan.planned_deleted_model_files,
        replace_existing_models=replace_existing_models,
    )
    llm_result: dict[str, Any] | None = None
    final_model_metadata = {
        table_name: dict(metadata)
        for table_name, metadata in generate_plan.base_model_metadata.items()
    }
    catalog_update_report = _empty_catalog_update_report()
    if api_key:
        llm_result = run_metadata_write(
            project,
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            parallelism=parallelism,
            request_timeout=request_timeout,
            no_cache=no_cache,
            dry_run=True,
            write_scope=write_scope,
            show_progress=show_progress,
            model_metadata=generate_plan.base_model_metadata,
            metric_groups=generate_plan.metric_groups,
            model_paths=generate_plan.write_targets.model_paths,
            resolution_policy=generate_plan.resolution_policy,
            include_model_metadata=True,
            update_catalog=False,
            expose_layer_hints=expose_layer_hints,
        )
        final_model_metadata = _final_model_metadata_with_refinements(
            generate_plan.base_model_metadata,
            llm_result,
        )
        if update_catalog:
            catalog_update_report = _merge_llm_catalog_discoveries(
                project,
                llm_result=llm_result,
                base_catalog=catalog,
                model_metadata=generate_plan.base_model_metadata,
                resolution_policy=generate_plan.resolution_policy,
                dry_run=dry_run,
            )
        _strip_internal_model_metadata(llm_result)

    refinement_updates = (llm_result or {}).get("model_updates") or []
    model_updates, deleted_model_files = _write_generated_model_metadata(
        project,
        generate_plan,
        final_model_metadata,
        dry_run=dry_run,
        delete_existing=replace_existing_models,
        refinement_updates=refinement_updates,
    )

    changed_updates = [update for update in model_updates if update["changed"]]
    result = {
        "project": project,
        "source": "direct_model_generation",
        "mode": "generate",
        "write_scope": write_scope,
        "update_catalog": update_catalog,
        "replace_existing_models": replace_existing_models,
        "planned_deleted_model_files": base_plan.planned_deleted_model_files,
        "deleted_model_files": deleted_model_files,
        "generated_model_count": len(base_plan.model_updates),
        "model_updates": changed_updates,
        "model_update_count": len(
            [update for update in changed_updates if update.get("updated")]
        ),
        "model_change_count": len(changed_updates),
        "llm_result": llm_result,
        "inspection_result": llm_result,
        "flow": {
            "mode": "generate",
            "prior_source": "direct_rule",
            "llm_enabled": bool(api_key),
            "base_model_count": len(base_plan.model_metadata),
            "final_model_count": len(final_model_metadata),
        },
    }
    result.update(catalog_report)
    result.update(catalog_update_report)
    return result


def run_direct_model_generation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Backward-compatible alias; new code should use generate naming."""
    return run_generate_model_metadata(*args, **kwargs)


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
    materialized = _materialized_for_write(
        (existing.get("execution") or {}).get("materialized")
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
        execution_payload = dict(updated.get("execution") or {})
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
    for metrics in (
        result.atomic_metrics,
        result.derived_metrics,
        result.calculated_metrics,
    ):
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
    wanted = _normalize_catalog_code(code)
    if not wanted:
        return False
    for entry in catalog.get(key) or []:
        if not isinstance(entry, dict):
            continue
        if _normalize_catalog_code(entry.get("code")) == wanted:
            return True
    return False


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
        if _catalog_has_code(
            catalog,
            "semantic_subjects",
            semantic_subject,
        ):
            mapping["semantic_subject"] = semantic_subject
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
        if len(processes) == 1 and _catalog_has_code(
            catalog,
            "business_processes",
            processes[0],
        ):
            mapping["business_process"] = processes[0]
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


def run_catalog_metadata_write(
    project: str,
    *,
    dry_run: bool = False,
    write_scope: str = "business",
    init_catalog: bool = False,
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("catalog 回写仅支持 write_scope=all/table/business")

    init_result = None
    if init_catalog:
        init_result = write_initial_business_semantics_catalog(
            project,
            overwrite=False,
            dry_run=dry_run,
        )

    catalog = (
        (init_result or {}).get("catalog")
        if init_result and dry_run
        else load_business_semantics_catalog(project)
    )
    if not catalog:
        raise FileNotFoundError(
            f"未找到 {project} 业务语义目录，请先初始化三份 catalog YAML"
        )

    updates = []
    for table_name, asset in sorted(_catalog_table_assets(project).items()):
        ddl = asset.get("ddl") or {}
        if not ddl.get("exists"):
            continue
        mapping = catalog_mapping_for_model(
            catalog,
            table_name,
            load_model_metadata(project).get(table_name, {}),
        )
        updates.append(
            update_model_yaml_from_catalog(
                project,
                table_name,
                mapping,
                dry_run=dry_run,
                write_scope=write_scope,
            )
        )
    if not dry_run:
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    changed_updates = [update for update in updates if update["changed"]]
    return {
        "project": project,
        "source": "catalog",
        "write_scope": write_scope,
        "paths": {
            name: str(path)
            for name, path in business_semantics_paths(project).items()
        },
        "written_names": (init_result or {}).get("written_names") or [],
        "inspected_table_count": len(updates),
        "model_updates": changed_updates,
        "model_update_count": len(
            [update for update in changed_updates if update.get("updated")]
        ),
        "model_change_count": len(changed_updates),
    }


def run_catalog_discovery(
    project: str,
    *,
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Use table-level LLM inspection results to initialize/update catalog."""
    data = load_lineage_data(project)
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()

    inspector = _new_table_inspector(
        api_key=api_key,
        model=model,
        base_url=base_url,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
        request_timeout=request_timeout,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()

    model_metadata = load_model_metadata(project)
    resolution_policy = LayerResolutionPolicy(mode="refresh")

    inspection = run_inspection_pipeline(
        project,
        data,
        inspector,
        metric_group_builder=metric_groups_for_model,
        result_enricher=enrich_results_with_related_entities,
        base_model_metadata=model_metadata,
        metric_result_is_eligible=lambda result: (
            _metric_result_is_eligible_for_propagation(
                result,
                existing_model=model_metadata.get(result.table_name),
                resolution_policy=resolution_policy,
            )
        ),
        result_layer_resolver=lambda _ctx, result: layer_for_model(
            result,
            existing_model=model_metadata.get(result.table_name),
            policy=resolution_policy,
        ),
    )
    contexts = inspection.contexts
    dwd_contexts = inspection.dwd_contexts
    dws_contexts = inspection.dws_contexts
    metadata_only_contexts = inspection.metadata_only_contexts
    results = inspection.results
    resolved_results = _resolved_results_for_catalog_discovery(
        results,
        model_metadata,
    )

    write_result = write_initial_business_semantics_catalog(
        project,
        overwrite=overwrite,
        dry_run=dry_run,
        inspection_results=resolved_results,
    )
    model_updates = []
    discovered_catalog = write_result.get("catalog") or {}
    resolved_results_by_table = {
        result.table_name: result for result in resolved_results
    }
    for result in results:
        resolved_result = resolved_results_by_table.get(result.table_name)
        if resolved_result is None:
            continue
        mapping = catalog_discovery_model_mapping(
            project,
            resolved_result,
            discovered_catalog,
            model_metadata.get(result.table_name, {}),
        )
        if not mapping:
            continue
        update = update_model_yaml_from_catalog(
            project,
            result.table_name,
            mapping,
            dry_run=dry_run,
            write_scope="business",
        )
        if update["changed"]:
            model_updates.append(update)
    if not dry_run and model_updates:
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    return {
        "project": project,
        "source": "llm_catalog_discovery",
        "path": write_result["path"],
        "paths": write_result.get("paths") or {},
        "written_names": write_result.get("written_names") or [],
        "changed": write_result["changed"],
        "updated": write_result["updated"],
        "catalog": write_result["catalog"],
        "inspected_table_count": len(contexts),
        "dwd_table_count": len(dwd_contexts),
        "dws_table_count": len(dws_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "fact_table_count": sum(
            1 for result in results if result.is_fact_table
        ),
        "dimension_table_count": sum(
            1 for result in results if result.table_type == "dimension"
        ),
        "business_process_count": len(
            (write_result.get("catalog") or {}).get("business_processes") or []
        ),
        "semantic_subject_count": len(
            (write_result.get("catalog") or {}).get("semantic_subjects") or []
        ),
        "model_updates": model_updates,
        "model_update_count": len(
            [update for update in model_updates if update.get("updated")]
        ),
        "model_change_count": len(model_updates),
        "tables": [result_for_report(result) for result in results],
    }


def result_for_report(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
) -> dict[str, Any]:
    """生成模型元数据回写报告中的单表结果。"""
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing_model,
        policy=resolution_policy,
    )
    data = inspect_result_to_dict(result)
    data["violations"] = metric_violations(
        result,
        applied_layer=resolution.applied_layer,
        applied_table_type=resolution.table_type,
    )
    data["metadata_warnings"] = warnings_for_resolution(result, resolution)
    return data


def _format_progress_message(event: dict[str, Any]) -> str:
    table_label = (
        f"[{event.get('index', '?')}/{event.get('total', '?')}] "
        f"{event.get('table')}({event.get('layer')})"
    )
    event_name = event.get("event")
    if event_name == "start":
        return f"{table_label} 开始巡检"
    if event_name == "cache_hit":
        return f"{table_label} 命中缓存，跳过 API"
    if event_name == "api_call":
        return (
            f"{table_label} 调用 DeepSeek "
            f"({event.get('attempt')}/{event.get('max_attempts')})"
        )
    if event_name == "api_error":
        return (
            f"{table_label} DeepSeek 调用失败 "
            f"({event.get('attempt')}/{event.get('max_attempts')}): "
            f"{event.get('error')}"
        )
    if event_name == "validation_retry":
        validation = event.get("validation") or {}
        issue_count = sum(len(items) for items in validation.values())
        return (
            f"{table_label} 返回校验为 {event.get('status')}，"
            f"发现 {issue_count} 个字段问题，准备重试"
        )
    if event_name == "unexpected_error":
        return f"{table_label} 巡检异常: {event.get('error')}"
    if event_name == "finish":
        metric_count = (
            int(event.get("atomic_metric_count", 0) or 0)
            + int(event.get("derived_metric_count", 0) or 0)
            + int(event.get("calculated_metric_count", 0) or 0)
        )
        return (
            f"{table_label} 完成: status={event.get('status')}, "
            f"retry={event.get('retry_count')}, metrics={metric_count} "
            f"(atomic={event.get('atomic_metric_count')}, "
            f"derived={event.get('derived_metric_count')}, "
            f"calculated={event.get('calculated_metric_count')})"
        )
    return f"{table_label} {event_name}"


def build_progress_callback() -> Callable[[dict[str, Any]], None]:
    """构建线程安全的 CLI 进度输出回调。"""
    print_lock = threading.Lock()

    def callback(event: dict[str, Any]) -> None:
        with print_lock:
            print(_format_progress_message(event), flush=True)

    return callback


def _metadata_flow_plan_for_write(
    project: str,
    *,
    write_scope: str,
    update_catalog: bool,
    model_metadata: dict[str, dict[str, Any]] | None,
    metric_groups: dict[str, dict[str, list[str]]] | None,
    model_paths: dict[str, Path] | None,
    resolution_policy: LayerResolutionPolicy | None,
) -> MetadataFlowPlan:
    if (
        model_metadata is None
        and model_paths is None
        and resolution_policy is None
    ):
        plan = build_refresh_plan(project, write_scope=write_scope)
        plan = replace(
            plan,
            catalog_plan=catalog_plan_for_refresh(llm=update_catalog),
        )
        if metric_groups is not None:
            plan = replace(plan, metric_groups=dict(metric_groups))
        return plan

    policy = resolution_policy or LayerResolutionPolicy(mode="refresh")
    mode = policy.mode
    prior_source = (
        "direct_rule"
        if policy.fallback_source == "direct_rule"
        else "declared"
    )
    catalog_plan = (
        catalog_plan_for_generate(llm=update_catalog)
        if mode == "generate"
        else catalog_plan_for_refresh(llm=update_catalog)
    )
    return MetadataFlowPlan(
        mode=mode,
        prior_source=prior_source,
        write_scope=write_scope,
        base_model_metadata=dict(
            model_metadata
            if model_metadata is not None
            else load_model_metadata(project)
        ),
        metric_groups=dict(metric_groups or {}),
        write_targets=MetadataWriteTargets(
            model_paths=dict(model_paths or {})
        ),
        resolution_policy=policy,
        catalog_plan=catalog_plan,
    )


def run_metadata_write(
    project: str,
    *,
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    write_scope: str = "all",
    show_progress: bool = False,
    model_metadata: dict[str, dict[str, Any]] | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
    model_paths: dict[str, Path] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
    include_model_metadata: bool = False,
    update_catalog: bool = True,
    expose_layer_hints: bool = True,
) -> dict[str, Any]:
    """运行项目级 LLM 巡检与模型元数据回写。"""
    write_scope = _validate_write_scope(write_scope)
    plan = _metadata_flow_plan_for_write(
        project,
        write_scope=write_scope,
        update_catalog=update_catalog,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
        model_paths=model_paths,
        resolution_policy=resolution_policy,
    )
    if plan.catalog_plan.ensure_skeleton:
        base_catalog, catalog_report = _ensure_metadata_catalog_skeleton(
            project,
            dry_run=dry_run,
        )
    else:
        base_catalog = load_business_semantics_catalog(project)
        catalog_report = {
            "catalog_initialized": False,
            "catalog_init_written_names": [],
            "planned_catalog_written_names": [],
        }
    catalog_update_report = _empty_catalog_update_report()
    data = load_lineage_data(project)
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()

    inspector = _new_table_inspector(
        api_key=api_key,
        model=model,
        base_url=base_url,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
        request_timeout=request_timeout,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()

    inspection = run_inspection_pipeline(
        project,
        data,
        inspector,
        metric_group_builder=metric_groups_for_model,
        result_enricher=enrich_results_with_related_entities,
        base_model_metadata=plan.base_model_metadata,
        metric_groups=plan.metric_groups
        if metric_groups is not None
        else None,
        expose_layer_hints=expose_layer_hints,
        metric_result_is_eligible=lambda result: (
            _metric_result_is_eligible_for_propagation(
                result,
                existing_model=(plan.base_model_metadata or {}).get(
                    result.table_name
                ),
                resolution_policy=plan.resolution_policy,
            )
        ),
        result_layer_resolver=lambda _ctx, result: layer_for_model(
            result,
            existing_model=(plan.base_model_metadata or {}).get(
                result.table_name
            ),
            policy=plan.resolution_policy,
        ),
    )
    contexts = inspection.contexts
    metric_contexts = inspection.metric_contexts
    metadata_only_contexts = inspection.metadata_only_contexts
    results = inspection.results
    yaml_updates, skipped_updates = write_model_updates_from_plan(
        project,
        results,
        plan,
        dry_run=dry_run,
        use_plan_existing_metadata=model_metadata is not None,
        include_model_metadata=include_model_metadata,
    )
    reports = [
        result_for_report(
            result,
            existing_model=(plan.base_model_metadata or {}).get(
                result.table_name
            ),
            resolution_policy=plan.resolution_policy,
        )
        for result in results
    ]
    if plan.catalog_plan.merge_llm_discoveries:
        catalog_update_report = _merge_llm_catalog_discoveries(
            project,
            llm_result=None,
            inspection_results=results,
            base_catalog=base_catalog,
            model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
            dry_run=dry_run,
        )

    result = {
        "project": project,
        "write_scope": plan.write_scope,
        "inspected_table_count": len(contexts),
        "metric_table_count": len(metric_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "dwd_table_count": len(inspection.dwd_contexts),
        "dws_table_count": len(inspection.dws_contexts),
        "dim_table_count": len(inspection.metadata_only_contexts),
        "fact_table_count": sum(1 for r in results if r.is_fact_table),
        "passed_table_count": sum(1 for r in results if r.status == "passed"),
        "warning_table_count": sum(
            1
            for result, report in zip(results, reports)
            if result.status == "warning" or report.get("metadata_warnings")
        ),
        "blocked_table_count": sum(
            1 for r in results if r.status == "blocked"
        ),
        "atomic_metric_count": sum(len(r.atomic_metrics) for r in results),
        "derived_metric_count": sum(len(r.derived_metrics) for r in results),
        "calculated_metric_count": sum(
            len(r.calculated_metrics) for r in results
        ),
        "metric_count": sum(len(metric_names_for_model(r)) for r in results),
        "derived_metric_violation_count": _violation_count(
            results,
            "derived_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "calculated_metric_violation_count": _violation_count(
            results,
            "calculated_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "non_atomic_metric_violation_count": _violation_count(
            results,
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "metadata_warning_count": sum(
            len(report.get("metadata_warnings") or []) for report in reports
        ),
        "tables": reports,
        "model_updates": yaml_updates,
        "model_update_count": len(
            [update for update in yaml_updates if update.get("updated")]
        ),
        "model_change_count": len(yaml_updates),
        "skipped_model_updates": skipped_updates,
    }
    result.update(catalog_report)
    result.update(catalog_update_report)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM 表巡检与模型元数据回写工具"
    )
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 warehouses/{project}/artifacts/assessment/model_metadata_result.json)",
    )
    parser.add_argument(
        "--mode",
        choices=("refresh", "generate"),
        default="refresh",
        help="运行模式: refresh=刷新现有 models, generate=冷启动重建 models",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="调用表级 LLM 巡检补全模型元数据",
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash", help="DeepSeek 模型名称"
    )
    parser.add_argument(
        "--base-url",
        help="DeepSeek/OpenAI-compatible chat completions API 地址",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="LLM 返回校验失败时的最大重试次数",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出巡检结果，不写入 models YAML",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="忽略本地缓存，强制重新调用 API",
    )
    parser.add_argument(
        "--parallel", type=int, default=2, help="LLM 并发调用数，默认 2"
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=60,
        help="单次 LLM 请求超时时间（秒）",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="不打印单表巡检进度"
    )
    args = parser.parse_args()

    if args.mode == "refresh" and not args.llm:
        result = run_catalog_metadata_write(
            args.project,
            dry_run=args.dry_run,
            write_scope="business",
            init_catalog=False,
        )
    elif args.mode == "refresh":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
            )

        result = run_metadata_write(
            args.project,
            api_key=api_key,
            model=args.model,
            base_url=normalize_chat_completions_url(args.base_url),
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            write_scope="all",
            show_progress=not args.quiet,
            update_catalog=True,
        )
    else:
        api_key = None
        if args.llm:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise SystemExit(
                    "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
                )
        result = run_generate_model_metadata(
            args.project,
            api_key=api_key,
            model=args.model,
            base_url=normalize_chat_completions_url(args.base_url),
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            write_scope="all",
            update_catalog=True,
            replace_existing_models=True,
            show_progress=not args.quiet,
        )

    output_path = (
        Path(args.output)
        if args.output
        else model_metadata_result_path(args.project)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    print(f"结果已写入: {output_path}")
    if result.get("source") == "catalog":
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "回写来源: catalog, "
            "目录文件: {paths}, 本次写入目录: {written_names}, "
            "巡检表: {inspected_table_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
                paths=paths,
                written_names=written_names,
                inspected_table_count=result.get("inspected_table_count", 0),
                model_change_count=result.get("model_change_count", 0),
                model_update_count=result.get("model_update_count", 0),
            )
        )
        return
    if result.get("source") == "llm_catalog_discovery":
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "目录发现: {path}, 文件: {paths}, 本次写入: {written_names}, "
            "巡检表: {inspected_table_count}, "
            "业务过程: {business_process_count}, "
            "语义主题: {semantic_subject_count}, 已写入: {updated}".format(
                paths=paths,
                written_names=written_names,
                path=result.get("path"),
                inspected_table_count=result.get("inspected_table_count", 0),
                business_process_count=result.get("business_process_count", 0),
                semantic_subject_count=result.get("semantic_subject_count", 0),
                updated=result.get("updated"),
            )
        )
        return
    if result.get("source") == "direct_model_generation":
        planned_catalog = (
            ", ".join(result.get("planned_catalog_written_names") or []) or "-"
        )
        written_catalog = (
            ", ".join(result.get("catalog_init_written_names") or []) or "-"
        )
        print(
            "冷启动生成: planned_catalog={planned_catalog}, "
            "written_catalog={written_catalog}, "
            "计划删除模型: {planned_delete_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
                planned_catalog=planned_catalog,
                written_catalog=written_catalog,
                planned_delete_count=len(
                    result.get("planned_deleted_model_files") or []
                ),
                model_change_count=result.get("model_change_count", 0),
                model_update_count=result.get("model_update_count", 0),
            )
        )
        return
    if "catalog" in result:
        catalog = result.get("catalog") or {}
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "目录初始化: {path}, 文件: {paths}, 本次写入: {written_names}, "
            "业务过程: {process_count}, 语义主题: {subject_count}, 已写入: {updated}".format(
                path=result.get("path"),
                paths=paths,
                written_names=written_names,
                process_count=len(catalog.get("business_processes") or []),
                subject_count=len(catalog.get("semantic_subjects") or []),
                updated=result.get("updated"),
            )
        )
        return
    print(
        "回写范围: {write_scope}, "
        "巡检表: {inspected_table_count}, 指标表: {metric_table_count}, "
        "仅元数据表: {metadata_only_table_count}, DWD表: {dwd_table_count}, "
        "DWS表: {dws_table_count}, DIM表: {dim_table_count}, "
        "事实表: {fact_table_count}, "
        "指标: {metric_count}, 原子指标: {atomic_metric_count}, "
        "派生指标: {derived_metric_count}, 衍生指标: {calculated_metric_count}, "
        "非原子指标违规: {non_atomic_metric_violation_count}, "
        "元数据警告: {metadata_warning_count}, "
        "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
