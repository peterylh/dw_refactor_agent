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
from pathlib import Path
from typing import Any, Callable

import yaml

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.llm.context_builder import TableContext, build_contexts
from assess.llm.table_inspector import (
    TableInspector,
    TableInspectResult,
)
from assess.llm.table_inspector import (
    result_to_dict as inspect_result_to_dict,
)
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.project_facts.business_semantics import (
    _infer_table_type,
    _layer_from_table_name,
    _materialized_for_layer,
    _normalize_catalog_code,
    catalog_mapping_for_model,
    load_business_semantics_catalog,
    write_initial_business_semantics_catalog,
)
from assess.project_facts.entity_metadata import normalize_entities
from assess.project_facts.time_period import normalize_time_period
from config import (
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
from lineage.table_graph import load_lineage_data

METRIC_LAYERS = {"DWD", "DWS"}
WRITABLE_METADATA_LAYERS = {"DWD", "DWS", "DIM"}
WRITE_SCOPES = {"all", "table", "metrics", "grain", "business"}
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
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


def build_inspection_contexts(
    project: str, lineage_data: dict[str, Any]
) -> list[TableContext]:
    """构建需要 LLM 巡检并回写模型元数据的表上下文。"""
    return build_contexts(
        project,
        lineage_data,
        layers=WRITABLE_METADATA_LAYERS,
    )


def build_dwd_contexts(
    project: str, lineage_data: dict[str, Any]
) -> list[TableContext]:
    """构建项目 DWD 层表的识别上下文。"""
    return build_contexts(project, lineage_data, layers={"DWD"})


def build_metric_contexts(
    project: str, lineage_data: dict[str, Any]
) -> list[TableContext]:
    """构建项目指标识别上下文，覆盖 DWD 与 DWS。"""
    return build_contexts(project, lineage_data, layers=METRIC_LAYERS)


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


def metric_violations(result: TableInspectResult) -> list[dict[str, Any]]:
    """返回 DWD 事实表中的派生/衍生指标违规项。"""
    if result.declared_layer != "DWD" or not result.is_fact_table:
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


def _merge_detected_upstream_metric_groups(
    contexts: list[TableContext],
    detected_groups: dict[str, dict[str, list[str]]],
) -> None:
    """将本轮已识别的上游指标分组注入下游上下文。"""
    for ctx in contexts:
        upstream_metric_groups = dict(ctx.upstream_metric_groups)
        for upstream_table in ctx.upstream_tables:
            groups = detected_groups.get(upstream_table)
            if groups and any(groups.values()):
                upstream_metric_groups[upstream_table] = groups
        ctx.upstream_metric_groups = upstream_metric_groups


def _update_models_for_results(
    project: str,
    results: list[TableInspectResult],
    *,
    dry_run: bool,
    write_scope: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    write_scope = _validate_write_scope(write_scope)
    yaml_updates = []
    skipped_updates = []
    for result in results:
        update = update_model_yaml(
            project, result, dry_run=dry_run, write_scope=write_scope
        )
        if result.status == "blocked":
            if update["changed"]:
                yaml_updates.append(update)
            else:
                skipped_updates.append(
                    {
                        "table": result.table_name,
                        "path": str(
                            model_path_for_table(project, result.table_name)
                        ),
                        "status": result.status,
                        "validation": result.validation,
                        "updated": False,
                        "reason": "validation_blocked",
                        "write_scope": write_scope,
                    }
                )
            continue
        if update["changed"]:
            yaml_updates.append(update)
    return yaml_updates, skipped_updates


def _violation_count(
    results: list[TableInspectResult], metric_attr: str | None = None
) -> int:
    """统计 DWD fact 中的非原子指标违规数量。"""
    count = 0
    for result in results:
        if result.declared_layer != "DWD" or not result.is_fact_table:
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
    if not grain_entity_index:
        return
    for result in results:
        discovered = discover_related_entities_from_grain(
            result,
            contexts.get(result.table_name),
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


def layer_for_model(result: TableInspectResult) -> str:
    """返回应写入模型 YAML 的层级。维度表强制归入 DIM。"""
    if result.table_type == "dimension":
        return "DIM"
    inferred = str(result.inferred_layer or "").strip().upper()
    if inferred and inferred != "OTHER":
        return inferred
    declared = str(result.declared_layer or "").strip().upper()
    return declared or "OTHER"


def metadata_warnings_for_result(
    result: TableInspectResult,
) -> list[dict[str, Any]]:
    """返回模型元数据回写层面的警告。"""
    if result.table_type != "dimension":
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


def _validate_write_scope(write_scope: str) -> str:
    if write_scope not in WRITE_SCOPES:
        raise ValueError(
            f"write_scope 必须是 {', '.join(sorted(WRITE_SCOPES))} 之一"
        )
    return write_scope


def should_write_table_metadata(write_scope: str) -> bool:
    return _validate_write_scope(write_scope) in {"all", "table"}


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
    return (
        normalized
        if business_config.is_valid_domain(normalized)
        else ""
    )


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
    result: TableInspectResult, write_scope: str = "all"
) -> bool:
    """判断是否需要按指标分组更新模型 YAML。"""
    if _validate_write_scope(write_scope) not in {"all", "metrics"}:
        return False
    return (
        result.declared_layer in METRIC_LAYERS
        or result.inferred_layer in METRIC_LAYERS
    )


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
) -> list[dict[str, Any]]:
    if not entities:
        return []

    effective_layer = str(model_layer or result.declared_layer or "").upper()
    is_dimension_model = (
        effective_layer == "DIM" or result.table_type == "dimension"
    )

    if result.table_type == "fact" and not is_dimension_model:
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
) -> dict[str, Any]:
    """将单表 LLM 巡检元数据和指标名覆盖写入 models/{table}.yaml。"""
    write_scope = _validate_write_scope(write_scope)
    path = model_path_for_table(project, result.table_name)
    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    if not isinstance(existing, dict):
        existing = {}

    if result.status == "blocked":
        can_migrate_grain = write_scope in {"all", "grain"} and any(
            key in existing
            for key in (
                "entities",
                "entity",
                "related_entities",
                "grain",
            )
        )
        if can_migrate_grain:
            updated = dict(existing)
            entity_metadata = _canonical_entities_for_write(
                result,
                _effective_entities(result)
                or normalize_entities(
                    existing.get("entities"),
                    existing.get("entity"),
                    existing.get("related_entities"),
                ),
                model_layer=str(existing.get("layer") or ""),
            )
            grain_metadata = _effective_grain(
                result.grain or existing.get("grain")
            )
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
            _clean_existing_business_metadata_for_layer(
                project,
                updated,
                updated.get("layer") or layer_for_model(result),
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
            return {
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
                "warnings": [],
                "write_scope": write_scope,
            }
        return {
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
            "reason": "validation_blocked",
            "warnings": [],
            "write_scope": write_scope,
        }

    existing_metrics = _extract_existing_metric_names(existing)
    existing_groups = _extract_existing_metric_groups(existing)
    detected_groups = metric_groups_for_model(result)
    write_table_metadata = should_write_table_metadata(write_scope)
    write_metric_groups = should_write_metric_groups(result, write_scope)
    write_grain_metadata = should_write_grain_metadata(result, write_scope)
    detected_metrics = (
        metric_names_for_model(result) if write_metric_groups else []
    )

    updated = dict(existing)
    previous_layer = existing.get("layer")
    previous_table_type = existing.get("table_type")
    previous_data_domain = existing.get("data_domain")
    previous_business_area = existing.get("business_area")
    previous_dimension_role = existing.get("dimension_role")
    previous_dimension_content_type = existing.get("dimension_content_type")
    has_existing_metric_fields = any(
        key in existing
        for key in (
            "metrics",
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
    )
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
        applied_layer = layer_for_model(result)
        updated["layer"] = applied_layer
        updated["table_type"] = result.table_type
        business_config = get_business_domain_config(project)
        business_metadata = {}
        if business_config:
            business_metadata = business_metadata_for_result(
                project,
                result,
                applied_layer,
            )
        has_inferred_data_domain = bool(
            str(result.inferred_data_domain or "").strip()
        )
        has_inferred_business_area = bool(
            str(result.inferred_business_area or "").strip()
        )
        if applied_layer in DATA_DOMAIN_LAYERS:
            if "data_domain" in business_metadata:
                updated["data_domain"] = business_metadata["data_domain"]
            elif business_config and not has_inferred_data_domain:
                existing_data_domain = _existing_data_domain_for_write(
                    business_config,
                    updated.get("data_domain"),
                )
                if existing_data_domain:
                    updated["data_domain"] = existing_data_domain
                else:
                    updated.pop("data_domain", None)
            elif not business_config or has_inferred_data_domain:
                updated.pop("data_domain", None)
        else:
            updated.pop("data_domain", None)
        if applied_layer in BUSINESS_AREA_LAYERS:
            if "business_area" in business_metadata:
                updated["business_area"] = business_metadata["business_area"]
            elif business_config and not has_inferred_business_area:
                existing_business_area = _existing_business_area_for_write(
                    business_config,
                    updated.get("business_area"),
                )
                if existing_business_area:
                    updated["business_area"] = existing_business_area
                else:
                    updated.pop("business_area", None)
            elif not business_config or has_inferred_business_area:
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
    if not write_grain_metadata and has_existing_grain_metadata:
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
        model_layer=str(existing.get("layer") or ""),
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
            or layer_for_model(result),
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

    return {
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
        "warnings": metadata_warnings_for_result(result),
        "write_scope": write_scope,
        "metric_count": len(detected_metrics),
        "new_metric_count": new_metric_count,
        "removed_metric_count": removed_metric_count,
        "grain_changed": grain_changed,
        "updated": bool(changed and not dry_run),
    }


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


def _existing_model_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    return raw if isinstance(raw, dict) else {}


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
    materialized = str(
        (existing.get("config") or {}).get("materialized")
        or mapping.get("materialized")
        or _materialized_for_layer(layer)
    ).strip()

    updated = dict(existing)
    updated.setdefault("version", 2)
    updated["name"] = table_name
    updated["layer"] = layer
    updated["table_type"] = table_type or "other"
    if materialized:
        config_payload = dict(updated.get("config") or {})
        config_payload["materialized"] = materialized
        updated["config"] = config_payload

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
    if semantic_subject:
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
    if result.status == "blocked":
        return {}

    layer = layer_for_model(result)
    catalog = catalog or {}
    mapping: dict[str, Any] = {
        "table": result.table_name,
        "layer": layer,
        "table_type": result.table_type,
        "materialized": _materialized_for_layer(
            result.declared_layer or layer
        ),
    }
    mapping.update(business_metadata_for_result(project, result, layer))
    if result.table_type == "dimension":
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

    if result.table_type == "fact":
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
        raise ValueError("from-catalog 仅支持 write_scope=all/table/business")

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
        raise ValueError("from-catalog 仅支持 write_scope=all/table/business")

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
            f"未找到 {project} 业务语义目录，请先初始化目录"
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
        import config as _config

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
    max_retries: int = 1,
    parallelism: int = 2,
    no_cache: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Use table-level LLM inspection results to initialize/update catalog."""
    data = load_lineage_data(project)
    contexts = build_inspection_contexts(project, data)
    metric_contexts = [ctx for ctx in contexts if ctx.layer in METRIC_LAYERS]
    dwd_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWD"]
    dws_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWS"]
    metadata_only_contexts = [
        ctx for ctx in contexts if ctx.layer not in METRIC_LAYERS
    ]
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()

    inspector = TableInspector(
        api_key=api_key,
        model=model,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()

    dwd_results = inspector.inspect_batch(dwd_contexts)
    detected_groups = {
        result.table_name: metric_groups_for_model(result)
        for result in dwd_results
        if result.status != "blocked"
    }
    _merge_detected_upstream_metric_groups(dws_contexts, detected_groups)
    dws_results = inspector.inspect_batch(dws_contexts)
    metadata_only_results = inspector.inspect_batch(metadata_only_contexts)
    results = dwd_results + dws_results + metadata_only_results
    contexts_by_name = {ctx.table_name: ctx for ctx in contexts}
    enrich_results_with_related_entities(results, contexts_by_name)

    write_result = write_initial_business_semantics_catalog(
        project,
        overwrite=overwrite,
        dry_run=dry_run,
        inspection_results=results,
    )
    model_updates = []
    discovered_catalog = write_result.get("catalog") or {}
    model_metadata = load_model_metadata(project)
    for result in results:
        mapping = catalog_discovery_model_mapping(
            project,
            result,
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
        import config as _config

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


def result_for_report(result: TableInspectResult) -> dict[str, Any]:
    """生成模型元数据回写报告中的单表结果。"""
    data = inspect_result_to_dict(result)
    data["violations"] = metric_violations(result)
    data["metadata_warnings"] = metadata_warnings_for_result(result)
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


def run_metadata_write(
    project: str,
    *,
    api_key: str,
    model: str = "deepseek-v4-flash",
    max_retries: int = 1,
    parallelism: int = 2,
    no_cache: bool = False,
    dry_run: bool = False,
    write_scope: str = "all",
    show_progress: bool = False,
) -> dict[str, Any]:
    """运行项目级 LLM 巡检与模型元数据回写。"""
    write_scope = _validate_write_scope(write_scope)
    data = load_lineage_data(project)
    contexts = build_inspection_contexts(project, data)
    metric_contexts = [ctx for ctx in contexts if ctx.layer in METRIC_LAYERS]
    dwd_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWD"]
    dws_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWS"]
    metadata_only_contexts = [
        ctx for ctx in contexts if ctx.layer not in METRIC_LAYERS
    ]
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()

    inspector = TableInspector(
        api_key=api_key,
        model=model,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()
    dwd_results = inspector.inspect_batch(dwd_contexts)

    detected_groups = {
        result.table_name: metric_groups_for_model(result)
        for result in dwd_results
        if result.status != "blocked"
    }
    _merge_detected_upstream_metric_groups(dws_contexts, detected_groups)
    dws_results = inspector.inspect_batch(dws_contexts)

    metadata_only_results = inspector.inspect_batch(metadata_only_contexts)
    results = dwd_results + dws_results + metadata_only_results
    contexts_by_name = {ctx.table_name: ctx for ctx in contexts}
    enrich_results_with_related_entities(results, contexts_by_name)
    yaml_updates, skipped_updates = _update_models_for_results(
        project, results, dry_run=dry_run, write_scope=write_scope
    )

    return {
        "project": project,
        "write_scope": write_scope,
        "inspected_table_count": len(contexts),
        "metric_table_count": len(metric_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "dwd_table_count": sum(1 for c in contexts if c.layer == "DWD"),
        "dws_table_count": sum(1 for c in contexts if c.layer == "DWS"),
        "dim_table_count": sum(1 for c in contexts if c.layer == "DIM"),
        "fact_table_count": sum(1 for r in results if r.is_fact_table),
        "passed_table_count": sum(1 for r in results if r.status == "passed"),
        "warning_table_count": sum(
            1
            for r in results
            if r.status == "warning" or metadata_warnings_for_result(r)
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
            results, "derived_metrics"
        ),
        "calculated_metric_violation_count": _violation_count(
            results, "calculated_metrics"
        ),
        "non_atomic_metric_violation_count": _violation_count(results),
        "metadata_warning_count": sum(
            len(metadata_warnings_for_result(r)) for r in results
        ),
        "tables": [result_for_report(r) for r in results],
        "model_updates": yaml_updates,
        "model_update_count": len(
            [update for update in yaml_updates if update.get("updated")]
        ),
        "model_change_count": len(yaml_updates),
        "skipped_model_updates": skipped_updates,
    }


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
        help="输出 JSON 文件路径 (默认 {project}/assess/model_metadata_result.json)",
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash", help="DeepSeek 模型名称"
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
        "--init-catalog",
        action="store_true",
        help="按项目DDL初始化业务语义目录",
    )
    parser.add_argument(
        "--catalog-from-llm",
        action="store_true",
        help="调用表级 LLM 巡检结果初始化/更新业务过程和语义主题目录",
    )
    parser.add_argument(
        "--overwrite-catalog",
        action="store_true",
        help="catalog-from-llm/init-catalog 时覆盖已存在目录",
    )
    parser.add_argument(
        "--from-catalog",
        action="store_true",
        help="从业务语义目录刷新/初始化 models",
    )
    parser.add_argument(
        "--write-scope",
        choices=sorted(WRITE_SCOPES),
        default="all",
        help=(
            "models 回写范围: all=表信息+指标+entity/grain, "
            "table=仅表级元数据, metrics=仅指标分组, "
            "grain=仅entity/grain, "
            "business=按models已有业务code从catalog补齐治理信息"
        ),
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
        "--quiet", action="store_true", help="不打印单表巡检进度"
    )
    args = parser.parse_args()

    if args.catalog_from_llm:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
            )
        result = run_catalog_discovery(
            args.project,
            api_key=api_key,
            model=args.model,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            overwrite=args.overwrite_catalog,
            show_progress=not args.quiet,
        )
    elif args.init_catalog and not args.from_catalog:
        result = write_initial_business_semantics_catalog(
            args.project,
            dry_run=args.dry_run,
            overwrite=args.overwrite_catalog,
        )
    elif args.from_catalog:
        result = run_catalog_metadata_write(
            args.project,
            dry_run=args.dry_run,
            write_scope=args.write_scope,
            init_catalog=args.init_catalog,
        )
    else:
        if args.write_scope == "business":
            raise SystemExit("--write-scope business 需要配合 --from-catalog")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
            )

        result = run_metadata_write(
            args.project,
            api_key=api_key,
            model=args.model,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            write_scope=args.write_scope,
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
        paths = ", ".join(
            str(path) for path in (result.get("paths") or {}).values()
        ) or "-"
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
        paths = ", ".join(
            str(path) for path in (result.get("paths") or {}).values()
        ) or "-"
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
                business_process_count=result.get(
                    "business_process_count", 0
                ),
                semantic_subject_count=result.get(
                    "semantic_subject_count", 0
                ),
                updated=result.get("updated"),
            )
        )
        return
    if "catalog" in result:
        catalog = result.get("catalog") or {}
        paths = ", ".join(
            str(path) for path in (result.get("paths") or {}).values()
        ) or "-"
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
