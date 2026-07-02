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
    VALID_LAYERS,
    VALID_TABLE_TYPES,
    TableInspector,
    TableInspectResult,
)
from assess.llm.table_inspector import (
    result_to_dict as inspect_result_to_dict,
)
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.project_facts.business_semantics import (
    _display_name_from_code,
    _entry_by_code,
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
    get_business_domain_config,
    load_model_metadata,
    model_metadata_result_path,
)
from lineage.table_graph import load_lineage_data
from lineage.view import LineageView

METRIC_LAYERS = {"DWD", "DWS"}
WRITABLE_METADATA_LAYERS = {"DWD", "DWS", "DIM"}
TABLE_INSPECTOR_LAYER_CANDIDATES = ("DWD", "DWS", "DIM")
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
DIRECT_MODEL_WRITE_SCOPES = {"all", "table", "business"}
DIRECT_MATCH_STOPWORDS = {
    "and",
    "area",
    "business",
    "data",
    "detail",
    "dim",
    "dwd",
    "dws",
    "fact",
    "full",
    "info",
    "layer",
    "model",
    "snapshot",
    "summary",
    "table",
    "type",
}
METRIC_COLUMN_HINTS = {
    "amount",
    "amt",
    "balance",
    "cnt",
    "cost",
    "count",
    "fee",
    "gmv",
    "margin",
    "metric",
    "price",
    "profit",
    "qty",
    "quantity",
    "rate",
    "ratio",
    "score",
    "sum",
    "total",
    "value",
}
DIRECT_APPLICATION_OUTPUT_TOKENS = {
    "ads",
    "cockpit",
    "dashboard",
    "portal",
    "rpt",
    "screen",
    "topn",
}
DIRECT_AMBIGUOUS_APPLICATION_OUTPUT_TOKENS = {
    "alert",
    "alerts",
    "performance",
    "rfm",
    "roi",
}
DIRECT_APPLICATION_OUTPUT_PHRASES = {
    "indicator app",
    "indicator application",
    "metric app",
    "metric application",
    "应用",
    "报表",
    "驾驶舱",
    "看板",
    "大屏",
    "指标应用",
    "专题",
}
DIRECT_APPLICATION_REPORT_TOKENS = {
    "report",
    "reports",
}
DIRECT_APPLICATION_SUMMARY_TOKENS = {"summary"}
DIRECT_APPLICATION_TIME_GRAIN_TOKENS = {
    "daily",
    "day",
    "monthly",
    "month",
    "quarterly",
    "quarter",
    "snapshot",
    "weekly",
    "week",
    "year",
    "yearly",
}
DIRECT_SOURCE_LAYER_TOKENS = {
    "raw",
    "source",
    "src",
    "sync",
}
DIRECT_DIMENSION_NAME_TOKENS = {
    "account",
    "accounts",
    "atm",
    "branch",
    "calendar",
    "campaign",
    "campaigns",
    "category",
    "customer",
    "customers",
    "date",
    "dimension",
    "economic",
    "entity",
    "indicator",
    "indicators",
    "location",
    "locations",
    "master",
    "merchant",
    "merchants",
    "profile",
    "product",
    "products",
    "promotion",
    "reference",
    "segment",
    "segments",
    "store",
}
DIRECT_FACT_EVENT_NAME_TOKENS = {
    "alert",
    "alerts",
    "application",
    "applications",
    "assessment",
    "assessments",
    "detail",
    "event",
    "events",
    "interaction",
    "interactions",
    "inventory",
    "loan",
    "order",
    "orders",
    "payment",
    "payments",
    "regulatory",
    "report",
    "reports",
    "risk",
    "transaction",
    "transactions",
}
TIME_COLUMN_HINTS = {
    "date",
    "day",
    "dt",
    "hour",
    "month",
    "period",
    "quarter",
    "stat_date",
    "time",
    "week",
    "year",
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
        effective_layer == "DIM"
        or (
            effective_layer != "DWS"
            and result.table_type == "dimension"
        )
    )

    if not is_dimension_model:
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
        if get_business_domain_config(project):
            business_metadata = business_metadata_for_result(
                project,
                result,
                applied_layer,
            )
            if applied_layer in DATA_DOMAIN_LAYERS:
                if "data_domain" in business_metadata:
                    updated["data_domain"] = business_metadata["data_domain"]
            else:
                updated.pop("data_domain", None)
            if applied_layer in BUSINESS_AREA_LAYERS:
                if "business_area" in business_metadata:
                    updated["business_area"] = business_metadata[
                        "business_area"
                    ]
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


def _empty_lineage_data() -> dict[str, list[Any]]:
    return {"tables": [], "edges": [], "indirect_edges": []}


def _load_lineage_data_for_direct_generation(
    project: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        return load_lineage_data(project), []
    except FileNotFoundError as exc:
        return (
            _empty_lineage_data(),
            [
                {
                    "type": "lineage_missing",
                    "severity": "degraded",
                    "message": (
                        f"{str(exc)}；冷启动 metadata 生成会缺少上下游传播、"
                        "字段血缘和聚合判断上下文"
                    ),
                }
            ],
        )


def _direct_table_assets(
    project: str,
    lineage_data: dict[str, Any],
    *,
    model_metadata: dict[str, Any] | None = None,
    include_model_files: bool = True,
) -> dict[str, dict[str, Any]]:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = PROJECT_ROOT / project_cfg["dir"]
    if model_metadata is None:
        model_metadata = load_model_metadata(project)
    return (
        build_asset_catalog(
            lineage_data.get("tables") or [],
            model_metadata,
            project_dir,
            edges=lineage_data.get("edges") or [],
            indirect_edges=lineage_data.get("indirect_edges") or [],
            include_model_files=include_model_files,
        ).get("tables")
        or {}
    )


def _safe_read_text(path: Any) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding=TEXT_ENCODING)
    except OSError:
        return ""


def _lineage_view_for_direct_generation(
    project: str, lineage_data: dict[str, Any]
) -> LineageView | None:
    if not any(
        lineage_data.get(key) for key in ("tables", "edges", "indirect_edges")
    ):
        return None
    return LineageView.from_data(project, lineage_data)


def _direct_lineage_text(
    table_name: str,
    lineage_view: LineageView | None,
    *,
    include_downstream: bool = True,
) -> str:
    if not lineage_view:
        return ""
    upstream = sorted(lineage_view.upstream_tables(table_name))
    downstream = (
        sorted(lineage_view.downstream_tables(table_name))
        if include_downstream
        else []
    )
    facts = lineage_view.lineage_facts_for_table(table_name)
    parts: list[str] = []
    if upstream:
        parts.append("upstream " + " ".join(upstream))
    if downstream:
        parts.append("downstream " + " ".join(downstream))
    for key in (
        "aggregate_columns",
        "constant_columns",
        "plain_columns",
        "group_by_sources",
        "source_files",
    ):
        values = facts.get(key) or []
        if values:
            parts.append(f"{key} " + " ".join(str(item) for item in values))
    return "\n".join(parts)


def _asset_column_names(asset: dict[str, Any]) -> list[str]:
    names = []
    for column in (
        ((asset.get("ddl") or {}).get("columns") or [])
        + (asset.get("columns") or [])
    ):
        if not isinstance(column, dict):
            continue
        name = str(column.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _asset_ddl_text(asset: dict[str, Any]) -> str:
    ddl = asset.get("ddl") or {}
    return _safe_read_text(ddl.get("path"))


def _direct_model_match_text(
    table_name: str,
    asset: dict[str, Any],
    lineage_view: LineageView | None,
) -> str:
    parts: list[str] = [table_name]
    ddl_text = _asset_ddl_text(asset)
    if ddl_text:
        parts.append(ddl_text)
        comments = _column_comments_from_ddl(ddl_text)
        if comments:
            parts.append(" ".join(comments.values()))
    for column_name in _asset_column_names(asset):
        parts.append(column_name)
    for task in asset.get("tasks") or []:
        for key in ("file", "expected_table"):
            if task.get(key):
                parts.append(str(task[key]))
        for key in ("output_tables", "lineage_targets"):
            values = task.get(key) or []
            if values:
                parts.append(" ".join(str(item) for item in values))
        parts.append(_safe_read_text(task.get("path")))
    lineage_text = _direct_lineage_text(
        table_name,
        lineage_view,
        include_downstream=False,
    )
    if lineage_text:
        parts.append(lineage_text)
    return "\n".join(part for part in parts if part)


def _split_identifier_tokens(value: Any) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    tokens = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text.lower())
    return [token for token in tokens if token]


def _normalize_match_text(value: Any) -> str:
    return " ".join(_split_identifier_tokens(value))


def _catalog_string_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [
            str(item).strip()
            for item in value.values()
            if str(item).strip()
        ]
    text = str(value or "").strip()
    return [text] if text else []


def _catalog_entry_signals(entry: dict[str, Any]) -> list[str]:
    signals = []
    for key in ("code", "name"):
        for value in _catalog_string_values(entry.get(key)):
            if value not in signals:
                signals.append(value)
    for key in ("alias", "aliases", "keywords", "synonyms"):
        for value in _catalog_string_values(entry.get(key)):
            if value not in signals:
                signals.append(value)
    return signals


def _is_match_token(token: str, signal_token: str) -> bool:
    token = token.strip().lower()
    signal_token = signal_token.strip().lower()
    if not token or not signal_token:
        return False
    if token == signal_token:
        return True
    if token.rstrip("s") == signal_token.rstrip("s"):
        return True
    if len(signal_token) >= 4 and token.startswith(signal_token):
        return True
    return len(token) >= 4 and signal_token.startswith(token)


def _is_weak_match_token(token: str) -> bool:
    if token in DIRECT_MATCH_STOPWORDS:
        return True
    return len(token) < 3 or token.isdigit()


def _score_catalog_entry(
    entry: dict[str, Any],
    *,
    table_name: str,
    match_text: str,
) -> tuple[float, list[str]]:
    table_raw = str(table_name or "").lower()
    full_raw = str(match_text or "").lower()
    table_norm = _normalize_match_text(table_name)
    full_norm = _normalize_match_text(match_text)
    table_tokens = set(_split_identifier_tokens(table_name))
    full_tokens = set(_split_identifier_tokens(match_text))
    score = 0.0
    matches: list[str] = []

    for signal in _catalog_entry_signals(entry):
        raw_signal = str(signal or "").strip().lower()
        if not raw_signal or raw_signal.isdigit():
            continue
        norm_signal = _normalize_match_text(raw_signal)
        if raw_signal in table_raw:
            score += 10.0
            matches.append(signal)
        elif raw_signal in full_raw:
            score += 4.0
            matches.append(signal)
        elif norm_signal and norm_signal in table_norm:
            score += 8.0
            matches.append(signal)
        elif norm_signal and norm_signal in full_norm:
            score += 3.0
            matches.append(signal)

        for token in _split_identifier_tokens(signal):
            if _is_weak_match_token(token):
                continue
            if any(_is_match_token(table_token, token) for table_token in table_tokens):
                score += 4.0
                matches.append(token)
            elif any(
                _is_match_token(full_token, token) for full_token in full_tokens
            ):
                score += 0.75
                matches.append(token)

    deduped_matches = []
    for match in matches:
        if match not in deduped_matches:
            deduped_matches.append(match)
    return score, deduped_matches


def _best_catalog_entry_match(
    entries: list[dict[str, Any]],
    *,
    table_name: str,
    match_text: str,
) -> dict[str, Any]:
    best: dict[str, Any] = {}
    for entry in entries:
        score, matches = _score_catalog_entry(
            entry,
            table_name=table_name,
            match_text=match_text,
        )
        if not best or score > best.get("score", 0):
            best = {
                "entry": entry,
                "score": score,
                "matches": matches,
            }
    if not best or best.get("score", 0) <= 0:
        return {}
    return best


def _catalog_entries(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    entries = catalog.get(key) or []
    return [dict(entry) for entry in entries if isinstance(entry, dict)]


def _has_metric_column_hints(asset: dict[str, Any]) -> bool:
    for column_name in _asset_column_names(asset):
        tokens = _split_identifier_tokens(column_name)
        if any(token in METRIC_COLUMN_HINTS for token in tokens):
            return True
    return False


def _direct_task_text(asset: dict[str, Any]) -> str:
    return "\n".join(
        _safe_read_text(task.get("path")) for task in asset.get("tasks") or []
    )


def _direct_generation_layer_from_asset_placement(
    project: str,
    asset: dict[str, Any],
) -> str:
    project_cfg = PROJECT_CONFIG.get(project) or {}
    project_dir = PROJECT_ROOT / str(project_cfg.get("dir") or project)
    for key, expected_dir in (("ddl", "ddl"), ("model", "models")):
        path = (asset.get(key) or {}).get("path")
        if not path:
            continue
        try:
            parts = Path(path).relative_to(project_dir).parts
        except ValueError:
            continue
        if len(parts) >= 2 and parts[0] == "ods" and parts[1] == expected_dir:
            return "ODS"
    return ""


def _direct_has_aggregate_signals(
    asset: dict[str, Any],
    lineage_facts: dict[str, Any],
) -> bool:
    if lineage_facts.get("has_aggregate") or lineage_facts.get("has_group_by"):
        return True

    task_text = _direct_task_text(asset)
    return bool(
        re.search(r"\b(sum|count|avg|min|max)\s*\(", task_text, re.IGNORECASE)
        or re.search(r"\bgroup\s+by\b", task_text, re.IGNORECASE)
    )


def _direct_application_output_signal_strength(
    table_name: str,
    asset: dict[str, Any],
    match_text: str,
    *,
    has_aggregate: bool = False,
    downstream_tables: set[str] | None = None,
) -> str:
    text = f"{table_name}\n{match_text}".lower()
    if any(phrase in text for phrase in DIRECT_APPLICATION_OUTPUT_PHRASES):
        return "strong"

    table_tokens = set(_split_identifier_tokens(table_name))
    if table_tokens & DIRECT_APPLICATION_OUTPUT_TOKENS:
        return "strong"
    if (
        {"metric", "snapshot"} <= table_tokens
        and table_tokens & DIRECT_APPLICATION_REPORT_TOKENS
    ):
        return "strong"
    if table_tokens & DIRECT_AMBIGUOUS_APPLICATION_OUTPUT_TOKENS:
        if has_aggregate and not downstream_tables:
            return "strong"
        return ""

    if not has_aggregate or downstream_tables:
        return ""
    if "by" in table_tokens:
        return "strong"
    if (
        table_tokens & DIRECT_APPLICATION_SUMMARY_TOKENS
        and not (table_tokens & DIRECT_APPLICATION_TIME_GRAIN_TOKENS)
    ):
        return "weak"
    return ""


def _direct_has_application_output_signal(
    table_name: str,
    asset: dict[str, Any],
    match_text: str,
    *,
    has_aggregate: bool = False,
    downstream_tables: set[str] | None = None,
) -> bool:
    return bool(
        _direct_application_output_signal_strength(
            table_name,
            asset,
            match_text,
            has_aggregate=has_aggregate,
            downstream_tables=downstream_tables,
        )
    )


def _direct_has_dimension_layer_signal(
    table_name: str,
    asset: dict[str, Any],
    *,
    process_match: dict[str, Any],
    subject_match: dict[str, Any],
    match_text: str,
    has_aggregate: bool,
) -> bool:
    if has_aggregate:
        return False

    name_tokens = set(_split_identifier_tokens(table_name))
    if (
        name_tokens & {"dimension", "entity", "master", "profile", "reference"}
        and not (name_tokens & DIRECT_FACT_EVENT_NAME_TOKENS)
    ):
        return True
    if (
        name_tokens & DIRECT_DIMENSION_NAME_TOKENS
        and not (name_tokens & DIRECT_FACT_EVENT_NAME_TOKENS)
    ):
        return True

    process_score = float(process_match.get("score") or 0)
    subject_score = float(subject_match.get("score") or 0)
    if subject_score < 2:
        return False

    lowered_match_text = match_text.lower()
    has_dimension_text = any(
        token in lowered_match_text
        for token in (" dimension", "维度", "实体", "属性", "档案", "主数据")
    )
    if has_dimension_text:
        return True
    if subject_score >= process_score + 2:
        return True
    return subject_score >= 8 and not _has_metric_column_hints(asset)


def _direct_has_profile_dimension_signal(
    table_name: str,
    *,
    has_aggregate: bool,
) -> bool:
    if has_aggregate:
        return False
    table_tokens = set(_split_identifier_tokens(table_name))
    return bool(
        table_tokens & {"profile", "master", "reference"}
        and not (table_tokens & DIRECT_FACT_EVENT_NAME_TOKENS)
    )


def _direct_has_event_detail_layer_signal(
    table_name: str,
    *,
    has_aggregate: bool,
    process_score: float,
    has_metric_hints: bool,
    upstream_tables: set[str],
    application_output_strength: str,
) -> bool:
    if has_aggregate or application_output_strength:
        return False
    table_tokens = set(_split_identifier_tokens(table_name))
    if table_tokens & DIRECT_FACT_EVENT_NAME_TOKENS:
        return True
    return bool(process_score >= 2 and (has_metric_hints or upstream_tables))


def _direct_has_source_layer_signal(
    table_name: str,
    asset: dict[str, Any],
    lineage_view: LineageView | None,
) -> bool:
    name_tokens = set(_split_identifier_tokens(table_name))
    if not (name_tokens & DIRECT_SOURCE_LAYER_TOKENS):
        return False
    if asset.get("tasks"):
        return False
    upstream_tables = (
        lineage_view.upstream_tables(table_name) if lineage_view else set()
    )
    return not upstream_tables


def _direct_fixed_layer_signal(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
    lineage_view: LineageView | None,
) -> str:
    seed_layer = _direct_seed_layer(
        table_name,
        asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    )
    if seed_layer in {"ODS", "ADS"}:
        return seed_layer

    placement_layer = _direct_generation_layer_from_asset_placement(
        project, asset
    )
    if placement_layer in {"ODS", "ADS"}:
        return placement_layer
    if _direct_has_source_layer_signal(table_name, asset, lineage_view):
        return "ODS"

    lineage_facts = (
        lineage_view.lineage_facts_for_table(table_name)
        if lineage_view
        else {}
    )
    downstream_tables = (
        lineage_view.downstream_tables(table_name) if lineage_view else set()
    )
    application_output_strength = _direct_application_output_signal_strength(
        table_name,
        asset,
        _direct_model_match_text(table_name, asset, lineage_view),
        has_aggregate=_direct_has_aggregate_signals(asset, lineage_facts),
        downstream_tables=downstream_tables,
    )
    return "ADS" if application_output_strength == "strong" else ""


def _direct_table_inspector_layer_result_is_usable(
    table_inspector_layer_result: dict[str, Any] | None,
) -> bool:
    if not table_inspector_layer_result:
        return False
    if table_inspector_layer_result.get("status") not in {"passed", "warning"}:
        return False
    return float(table_inspector_layer_result.get("confidence") or 0) >= 0.5


def _direct_table_inspector_has_aggregate_reason(
    table_inspector_layer_result: dict[str, Any] | None,
) -> bool:
    if not table_inspector_layer_result:
        return False
    steps = table_inspector_layer_result.get("reasoning_steps") or []
    text = "\n".join(
        [str(table_inspector_layer_result.get("reason") or "")]
        + [str(step) for step in steps]
    ).lower()
    if not text:
        return False
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[\n。；;]+", text)
        if sentence.strip()
    ]
    negative_pattern = re.compile(
        r"(?:没有|无|未包含|不包含|不存在|未进行|非|不是|不符合)"
        r".{0,20}(?:group\s*by|聚合|汇总)|"
        r"(?:group\s*by|聚合|汇总).{0,20}"
        r"(?:没有|无|未包含|不包含|不存在|未进行|非|不是|不符合)",
        re.IGNORECASE,
    )
    positive_pattern = re.compile(
        r"\bgroup\s+by\b|\b(sum|count|avg|min|max)\s*\(|聚合|汇总指标|汇总表",
        re.IGNORECASE,
    )
    return any(
        positive_pattern.search(sentence)
        and not negative_pattern.search(sentence)
        for sentence in sentences
    )


DIRECT_AGGREGATE_SUMMARY_NAME_TOKENS = {
    "aggregate",
    "aggregation",
    "daily",
    "day",
    "effect",
    "hourly",
    "monthly",
    "quarterly",
    "snapshot",
    "summary",
    "weekly",
    "yearly",
}


def _direct_has_aggregate_summary_name_signal(table_name: str) -> bool:
    tokens = set(_split_identifier_tokens(table_name))
    return bool(tokens & DIRECT_AGGREGATE_SUMMARY_NAME_TOKENS)


def _direct_apply_aggregate_summary_guard(
    table_name: str,
    inspected_layer: str,
    *,
    has_aggregate: bool,
) -> str:
    """Do not let aggregate summary facts collapse into DIM/DWD metadata."""
    layer = str(inspected_layer or "").upper()
    if layer == "DIM" and has_aggregate:
        return "DWS"
    if (
        layer == "DWD"
        and has_aggregate
        and _direct_has_aggregate_summary_name_signal(table_name)
    ):
        return "DWS"
    return layer


def _direct_infer_layer(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    seed_layer: str,
    process_match: dict[str, Any],
    subject_match: dict[str, Any],
    lineage_view: LineageView | None,
    match_text: str,
    table_inspector_layer_result: dict[str, Any] | None = None,
    prefer_table_inspector: bool = False,
) -> str:
    normalized_seed = str(seed_layer or "").strip().upper()
    placement_layer = _direct_generation_layer_from_asset_placement(
        project, asset
    )
    has_source_layer_signal = _direct_has_source_layer_signal(
        table_name, asset, lineage_view
    )

    if (
        normalized_seed == "ODS"
        or placement_layer == "ODS"
        or has_source_layer_signal
    ):
        return "ODS"

    lineage_facts = (
        lineage_view.lineage_facts_for_table(table_name)
        if lineage_view
        else {}
    )
    has_aggregate = _direct_has_aggregate_signals(asset, lineage_facts)
    upstream_tables = (
        lineage_view.upstream_tables(table_name) if lineage_view else set()
    )
    downstream_tables = (
        lineage_view.downstream_tables(table_name) if lineage_view else set()
    )
    application_output_strength = _direct_application_output_signal_strength(
        table_name,
        asset,
        match_text,
        has_aggregate=has_aggregate,
        downstream_tables=downstream_tables,
    )

    if normalized_seed == "ADS":
        return "ADS"

    if (
        application_output_strength == "strong"
        and normalized_seed not in {"ODS", "DWD", "DWS"}
    ):
        return "ADS"

    if _direct_has_profile_dimension_signal(
        table_name,
        has_aggregate=has_aggregate,
    ):
        return "DIM"

    if (
        prefer_table_inspector
        and _direct_table_inspector_layer_result_is_usable(
            table_inspector_layer_result
        )
    ):
        inspected_layer = str(
            table_inspector_layer_result.get("layer") or ""
        ).upper()
        if inspected_layer in VALID_LAYERS and inspected_layer != "OTHER":
            inspected_layer = _direct_apply_aggregate_summary_guard(
                table_name,
                inspected_layer,
                has_aggregate=(
                    has_aggregate
                    or _direct_table_inspector_has_aggregate_reason(
                        table_inspector_layer_result
                    )
                ),
            )
            if inspected_layer == "ADS" and _direct_has_event_detail_layer_signal(
                table_name,
                has_aggregate=has_aggregate,
                process_score=float(process_match.get("score") or 0),
                has_metric_hints=_has_metric_column_hints(asset),
                upstream_tables=upstream_tables,
                application_output_strength=application_output_strength,
            ):
                return "DWD"
            return inspected_layer

    if normalized_seed and normalized_seed != "OTHER":
        return normalized_seed

    if placement_layer:
        return placement_layer

    if _direct_table_inspector_layer_result_is_usable(
        table_inspector_layer_result
    ):
        inspected_layer = str(
            table_inspector_layer_result.get("layer") or ""
        ).upper()
        if inspected_layer in VALID_LAYERS:
            inspected_layer = _direct_apply_aggregate_summary_guard(
                table_name,
                inspected_layer,
                has_aggregate=(
                    has_aggregate
                    or _direct_table_inspector_has_aggregate_reason(
                        table_inspector_layer_result
                    )
                ),
            )
            if inspected_layer == "ADS" and _direct_has_event_detail_layer_signal(
                table_name,
                has_aggregate=has_aggregate,
                process_score=float(process_match.get("score") or 0),
                has_metric_hints=_has_metric_column_hints(asset),
                upstream_tables=upstream_tables,
                application_output_strength=application_output_strength,
            ):
                return "DWD"
            return inspected_layer

    if application_output_strength == "strong":
        return "ADS"

    if _direct_has_dimension_layer_signal(
        table_name,
        asset,
        process_match=process_match,
        subject_match=subject_match,
        match_text=match_text,
        has_aggregate=has_aggregate,
    ):
        return "DIM"

    if has_aggregate:
        if downstream_tables:
            return "DWS"
        if upstream_tables:
            return "ADS"
        return "DWS"
    if (
        float(process_match.get("score") or 0) >= 2
        or _has_metric_column_hints(asset)
        or upstream_tables
    ):
        return "DWD"
    if float(subject_match.get("score") or 0) >= 2:
        return "DIM"
    return "OTHER"


def _direct_seed_layer(
    table_name: str,
    asset: dict[str, Any],
    *,
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
) -> str:
    for candidate in (
        existing.get("layer") if use_existing_model_metadata else "",
        asset.get("layer") if use_existing_model_metadata else "",
        _layer_from_table_name(table_name),
    ):
        layer = str(candidate or "").upper()
        if layer and layer != "OTHER":
            return layer
    return "OTHER"


def _direct_needs_table_inspector_layer_inference(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
) -> bool:
    seed_layer = _direct_seed_layer(
        table_name,
        asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    )
    if seed_layer and seed_layer != "OTHER":
        return False
    return not _direct_generation_layer_from_asset_placement(project, asset)


def _direct_table_inspector_candidate_reason(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
    cold_start_full_metadata: bool,
    lineage_view: LineageView | None,
) -> str:
    if _direct_fixed_layer_signal(
        project=project,
        table_name=table_name,
        asset=asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
        lineage_view=lineage_view,
    ):
        return ""
    if cold_start_full_metadata:
        return "cold_start_full_metadata"
    if _direct_needs_table_inspector_layer_inference(
        project=project,
        table_name=table_name,
        asset=asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    ):
        return "missing_layer"
    return ""


def _direct_table_inspector_skip_reason(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
    lineage_view: LineageView | None,
) -> str:
    fixed_layer = _direct_fixed_layer_signal(
        project=project,
        table_name=table_name,
        asset=asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
        lineage_view=lineage_view,
    )
    if fixed_layer:
        return f"fixed_{fixed_layer.lower()}_layer_signal"
    seed_layer = _direct_seed_layer(
        table_name,
        asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    )
    if seed_layer and seed_layer != "OTHER":
        return "explicit_layer_signal"
    if _direct_generation_layer_from_asset_placement(project, asset):
        return "asset_placement_layer_signal"
    return "not_required"


def _direct_table_inspector_declared_layer(
    *,
    project: str,
    table_name: str,
    asset: dict[str, Any],
    existing: dict[str, Any],
    use_existing_model_metadata: bool,
    lineage_view: LineageView | None,
) -> str:
    seed_layer = _direct_seed_layer(
        table_name,
        asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    )
    if seed_layer and seed_layer != "OTHER":
        return seed_layer
    placement_layer = _direct_generation_layer_from_asset_placement(
        project, asset
    )
    if placement_layer:
        return placement_layer
    if _direct_has_source_layer_signal(table_name, asset, lineage_view):
        return "ODS"
    return "OTHER"


def _direct_catalog_has_business_entries(catalog: dict[str, Any]) -> bool:
    return bool(
        catalog.get("business_processes") or catalog.get("semantic_subjects")
    )


def _direct_catalog_option_entries(raw_entries: Any) -> list[dict[str, Any]]:
    entries = []
    if not isinstance(raw_entries, list):
        return entries
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "").strip()
        if not code:
            continue
        entry = {
            "code": code,
            "name": str(raw.get("name") or "").strip(),
        }
        for key in ("data_domain", "business_area"):
            value = str(raw.get(key) or "").strip()
            if value:
                entry[key] = value
        entries.append(entry)
    return entries


def _direct_business_semantics_options(
    catalog: dict[str, Any],
) -> dict[str, Any]:
    options: dict[str, Any] = {}
    processes = _direct_catalog_option_entries(
        catalog.get("business_processes") or []
    )
    subjects = _direct_catalog_option_entries(
        catalog.get("semantic_subjects") or []
    )
    if processes:
        options["business_processes"] = processes
    if subjects:
        options["semantic_subjects"] = subjects
    return options


def _direct_depth_from_ods(
    *,
    project: str,
    table_name: str,
    table_assets: dict[str, dict[str, Any]],
    lineage_view: LineageView | None,
    memo: dict[str, int],
    visiting: set[str] | None = None,
) -> int:
    if table_name in memo:
        return memo[table_name]
    if visiting is None:
        visiting = set()
    if table_name in visiting:
        return 1

    asset = table_assets.get(table_name) or {}
    asset_layer = str(asset.get("layer") or "").upper()
    if (
        asset_layer == "ODS"
        or _layer_from_table_name(table_name) == "ODS"
        or _direct_generation_layer_from_asset_placement(project, asset)
        == "ODS"
        or _direct_has_source_layer_signal(table_name, asset, lineage_view)
    ):
        memo[table_name] = 0
        return 0

    upstream_tables = (
        sorted(lineage_view.upstream_tables(table_name))
        if lineage_view
        else []
    )
    if not upstream_tables:
        memo[table_name] = 1
        return 1

    visiting.add(table_name)
    depth = min(
        _direct_depth_from_ods(
            project=project,
            table_name=upstream,
            table_assets=table_assets,
            lineage_view=lineage_view,
            memo=memo,
            visiting=visiting,
        )
        for upstream in upstream_tables
    ) + 1
    visiting.remove(table_name)
    memo[table_name] = depth
    return depth


def _direct_inspection_context(
    *,
    catalog: dict[str, Any],
    project: str,
    table_name: str,
    asset: dict[str, Any],
    table_assets: dict[str, dict[str, Any]],
    lineage_view: LineageView | None,
    depth_memo: dict[str, int],
    declared_layer: str = "OTHER",
    candidate_layers: tuple[str, ...] = TABLE_INSPECTOR_LAYER_CANDIDATES,
) -> TableContext:
    upstream_tables = (
        sorted(lineage_view.upstream_tables(table_name))
        if lineage_view
        else []
    )
    downstream_tables = (
        sorted(lineage_view.downstream_tables(table_name))
        if lineage_view
        else []
    )
    business_domain_config = get_business_domain_config(project)
    business_domain_options = (
        business_domain_config.prompt_options()
        if business_domain_config
        else {}
    )
    return TableContext(
        table_name=table_name,
        layer=str(declared_layer or "OTHER").upper(),
        ddl=_asset_ddl_text(asset),
        etl_sql=_direct_task_text(asset),
        upstream_tables=upstream_tables,
        downstream_tables=downstream_tables,
        depth_from_ods=_direct_depth_from_ods(
            project=project,
            table_name=table_name,
            table_assets=table_assets,
            lineage_view=lineage_view,
            memo=depth_memo,
        ),
        upstream_metric_groups={},
        column_lineage=(
            lineage_view.column_lineage_for_table(table_name)
            if lineage_view
            else []
        ),
        declared_data_domain="",
        declared_business_area="",
        project_context=str(catalog.get("project_context") or "").strip(),
        business_domain_options=business_domain_options,
        business_semantics_options=_direct_business_semantics_options(catalog),
        candidate_layers=candidate_layers,
    )


def _direct_table_inspector_layer_result_from_inspection(
    result: TableInspectResult,
) -> dict[str, Any]:
    inferred_layer = str(result.inferred_layer or "OTHER").upper()
    declared_layer = str(result.declared_layer or "OTHER").upper()
    if inferred_layer in VALID_LAYERS and inferred_layer != "OTHER":
        applied_layer = inferred_layer
    elif declared_layer in VALID_LAYERS and declared_layer != "OTHER":
        applied_layer = declared_layer
    else:
        applied_layer = (
            inferred_layer if inferred_layer in VALID_LAYERS else "OTHER"
        )
    reasoning = [
        str(step).strip()
        for step in result.reasoning_steps
        if str(step).strip()
    ]
    return {
        "status": result.status,
        "layer": applied_layer,
        "inferred_layer": inferred_layer,
        "table_type": result.table_type,
        "confidence": result.confidence,
        "reason": "；".join(reasoning[:3]),
        "reasoning_steps": reasoning,
        "validation": result.validation,
        "retry_count": result.retry_count,
        "metric_count": len(metric_names_for_model(result)),
        "entity_count": len(_effective_entities(result)),
        "has_grain": bool(_effective_grain(result.grain)),
        "_inspection_result": result,
        "source": "table_inspector_layer_inference",
    }


def _create_table_inspector(
    *,
    api_key: str,
    inspector_kwargs: dict[str, Any],
) -> TableInspector:
    try:
        return TableInspector(api_key=api_key, **inspector_kwargs)
    except TypeError as exc:
        if "request_timeout" not in inspector_kwargs:
            raise
        if "request_timeout" not in str(exc):
            raise
        fallback_kwargs = dict(inspector_kwargs)
        fallback_kwargs.pop("request_timeout", None)
        return TableInspector(api_key=api_key, **fallback_kwargs)


def _direct_infer_layers_with_table_inspector(
    *,
    catalog: dict[str, Any],
    project: str,
    table_assets: dict[str, dict[str, Any]],
    all_table_assets: dict[str, dict[str, Any]] | None = None,
    existing_by_table: dict[str, dict[str, Any]] | None = None,
    use_existing_model_metadata: bool = True,
    lineage_view: LineageView | None,
    api_key: str,
    model: str,
    base_url: str,
    max_retries: int,
    parallelism: int,
    request_timeout: int,
    no_cache: bool,
    show_progress: bool,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not table_assets:
        return {}, []

    cache_file = assess_cache_path(project, "table_inspector_layer.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()
    inspector = _create_table_inspector(
        api_key=api_key,
        inspector_kwargs={
            "model": model,
            "base_url": base_url,
            "cache_file": cache_file,
            "max_retries": max_retries,
            "parallelism": parallelism,
            "request_timeout": request_timeout,
        },
    )

    if show_progress:
        inspector.progress_callback = build_progress_callback()

    depth_memo: dict[str, int] = {}
    all_table_assets = all_table_assets or table_assets
    existing_by_table = existing_by_table or {}
    contexts = [
        _direct_inspection_context(
            catalog=catalog,
            project=project,
            table_name=table_name,
            asset=asset,
            table_assets=all_table_assets,
            lineage_view=lineage_view,
            depth_memo=depth_memo,
            declared_layer=_direct_table_inspector_declared_layer(
                project=project,
                table_name=table_name,
                asset=asset,
                existing=existing_by_table.get(table_name, {}),
                use_existing_model_metadata=use_existing_model_metadata,
                lineage_view=lineage_view,
            ),
        )
        for table_name, asset in sorted(table_assets.items())
    ]
    inspection_results = inspector.inspect_batch(contexts)
    layer_results = {
        result.table_name: _direct_table_inspector_layer_result_from_inspection(
            result
        )
        for result in inspection_results
    }
    warnings = []
    for table_name, result in layer_results.items():
        if result.get("status") == "passed":
            continue
        if result.get("status") == "warning":
            warnings.append(
                {
                    "type": "table_inspector_layer_warning",
                    "severity": "warning",
                    "table": table_name,
                    "message": result.get("reason")
                    or "Table inspector returned validation warnings",
                    "validation": result.get("validation") or {},
                }
            )
            continue
        warnings.append(
            {
                "type": "table_inspector_layer_failed",
                "severity": "warning",
                "table": table_name,
                "message": result.get("reason")
                or "Table inspector layer inference failed",
                "validation": result.get("validation") or {},
            }
        )
    return layer_results, warnings


def _direct_materialized(
    *,
    layer: str,
    table_type: str,
    table_name: str,
    asset: dict[str, Any],
    match_text: str,
) -> str:
    normalized_layer = str(layer or "").upper()
    if normalized_layer == "ODS":
        return _materialized_for_layer(normalized_layer)

    text = f"{table_name}\n{_asset_ddl_text(asset)}".lower()
    ddl = asset.get("ddl") or {}
    key_columns = [str(item).lower() for item in ddl.get("key_columns") or []]
    if "snapshot" in text or "快照" in text:
        return "snapshot"
    if table_type == "dimension" and any(
        _is_time_grain_key(column) for column in key_columns
    ):
        return "snapshot"
    if _direct_has_incremental_refresh(asset, table_name):
        return "incremental"
    return _materialized_for_layer(normalized_layer)


def _direct_has_incremental_refresh(
    asset: dict[str, Any], table_name: str
) -> bool:
    task_text = _direct_task_text(asset).lower()
    if not task_text:
        return False
    if "truncate table" in task_text:
        return False
    target = str(table_name or "").lower()
    return "delete from" in task_text and target in task_text


def _direct_infer_table_type(
    *,
    table_name: str,
    layer: str,
    existing: dict[str, Any],
    asset: dict[str, Any],
    process_match: dict[str, Any],
    subject_match: dict[str, Any],
    lineage_view: LineageView | None,
    table_inspector_layer_result: dict[str, Any] | None = None,
) -> str:
    existing_type = str(existing.get("table_type") or "").strip().lower()
    if existing_type:
        return existing_type

    name = str(table_name or "").lower()
    match_text = _direct_model_match_text(table_name, asset, lineage_view)
    lowered_match_text = match_text.lower()
    process_score = float(process_match.get("score") or 0)
    subject_score = float(subject_match.get("score") or 0)
    lineage_facts = (
        lineage_view.lineage_facts_for_table(table_name)
        if lineage_view
        else {}
    )
    has_metric_hints = _has_metric_column_hints(asset)
    has_fact_text = any(
        token in lowered_match_text
        for token in (" fact", "事实", "汇总", "明细事实", "snapshot fact")
    )
    has_dimension_text = any(
        token in lowered_match_text
        for token in (" dimension", "维度", "实体", "属性")
    )

    if layer == "ODS" or name.startswith("ods_"):
        return "other"
    if layer == "ADS" or name.startswith("ads_"):
        return "other"
    if layer == "DIM" or name.startswith("dim_"):
        return "dimension"
    if layer == "DWS":
        return "fact"
    if _direct_table_inspector_layer_result_is_usable(
        table_inspector_layer_result
    ):
        inspected_table_type = str(
            table_inspector_layer_result.get("table_type") or ""
        ).strip().lower()
        if inspected_table_type in (VALID_TABLE_TYPES - {"other"}):
            return inspected_table_type
    if layer == "DWD" and _direct_has_event_detail_layer_signal(
        table_name,
        has_aggregate=bool(lineage_facts.get("has_aggregate")),
        process_score=process_score,
        has_metric_hints=has_metric_hints,
        upstream_tables=(
            lineage_view.upstream_tables(table_name)
            if lineage_view
            else set()
        ),
        application_output_strength="",
    ):
        return "fact"
    if layer == "DWD" and subject_score >= 2 and has_dimension_text:
        return "dimension"
    if layer == "DWD" and process_score >= 2 and (
        has_metric_hints or lineage_facts.get("has_aggregate") or has_fact_text
    ):
        return "fact"
    if subject_score >= 2 and subject_score >= process_score + 2:
        return "dimension"
    if process_score >= 2:
        return "fact"
    if lineage_facts.get("has_aggregate"):
        return "fact"
    return _infer_table_type(table_name, layer)


def _direct_existing_catalog_mapping(
    catalog: dict[str, Any],
    table_name: str,
    existing: dict[str, Any],
) -> dict[str, Any]:
    mapping = catalog_mapping_for_model(catalog, table_name, existing)
    if mapping.get("business_process") or mapping.get("semantic_subject"):
        assignment = "existing_business_process"
        if mapping.get("semantic_subject"):
            assignment = "existing_semantic_subject"
        mapping["assignment_source"] = assignment
        mapping["assignment_reason"] = "existing_model_metadata"
    return mapping


def _direct_apply_table_inspector_layer_mapping(
    mapping: dict[str, Any],
    table_inspector_layer_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _direct_table_inspector_layer_result_is_usable(
        table_inspector_layer_result
    ):
        return mapping

    inspected_layer = str(
        table_inspector_layer_result.get("layer") or ""
    ).upper()
    inspected_table_type = str(
        table_inspector_layer_result.get("table_type") or ""
    ).lower()
    if inspected_layer == "ADS":
        mapping["table_type"] = "other"
    elif (
        inspected_table_type in VALID_TABLE_TYPES
        and inspected_table_type != "other"
    ):
        mapping["table_type"] = inspected_table_type
    if inspected_layer in VALID_LAYERS and inspected_layer != "OTHER":
        mapping["layer"] = (
            "DIM" if inspected_table_type == "dimension" else inspected_layer
        )
        mapping["materialized"] = _materialized_for_layer(mapping["layer"])
    return mapping


def _direct_apply_table_inspector_metadata_mapping(
    *,
    project: str,
    mapping: dict[str, Any],
    table_inspector_layer_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _direct_table_inspector_layer_result_is_usable(
        table_inspector_layer_result
    ):
        return mapping

    result = table_inspector_layer_result.get("_inspection_result")
    if not isinstance(result, TableInspectResult):
        return mapping

    mapping["_table_inspector_result"] = result
    business_metadata = business_metadata_for_result(
        project,
        result,
        str(mapping.get("layer") or ""),
    )
    for key, allowed_layers in (
        ("data_domain", DATA_DOMAIN_LAYERS),
        ("business_area", BUSINESS_AREA_LAYERS),
    ):
        if mapping.get(key):
            continue
        layer = str(mapping.get("layer") or "").upper()
        value = str(business_metadata.get(key) or "").strip()
        if not value and layer in allowed_layers:
            value = str(getattr(result, f"inferred_{key}") or "").strip()
        if value:
            mapping[key] = value

    table_type = str(mapping.get("table_type") or result.table_type).lower()
    if table_type == "dimension":
        semantic_subject = _semantic_subject_from_result(result)
        if semantic_subject and not mapping.get("semantic_subject"):
            mapping["semantic_subject"] = semantic_subject
            mapping.pop("business_process", None)
        if result.dimension_role and not mapping.get("dimension_role"):
            mapping["dimension_role"] = result.dimension_role
        if result.dimension_content_type and not mapping.get(
            "dimension_content_type"
        ):
            mapping["dimension_content_type"] = result.dimension_content_type
        if (
            mapping.get("semantic_subject")
            and mapping.get("assignment_source") == "fallback"
        ):
            mapping.update(
                {
                    "assignment_source": "table_inspector_metadata_inference",
                    "assignment_reason": "table_inspector_semantic_subject",
                    "assignment_score": max(
                        float(mapping.get("assignment_score") or 0),
                        float(result.confidence or 0),
                    ),
                }
            )
        return mapping

    if table_type == "fact":
        processes = _business_processes_from_result(result)
        if len(processes) == 1 and not mapping.get("business_process"):
            mapping["business_process"] = processes[0]
            mapping.pop("semantic_subject", None)
        if (
            mapping.get("business_process")
            and mapping.get("assignment_source") == "fallback"
        ):
            mapping.update(
                {
                    "assignment_source": "table_inspector_metadata_inference",
                    "assignment_reason": "table_inspector_business_process",
                    "assignment_score": max(
                        float(mapping.get("assignment_score") or 0),
                        float(result.confidence or 0),
                    ),
                }
            )

    return mapping


def _direct_catalog_mapping_for_model(
    catalog: dict[str, Any],
    project: str,
    table_name: str,
    asset: dict[str, Any],
    *,
    existing: dict[str, Any],
    lineage_view: LineageView | None,
    use_existing_model_metadata: bool = True,
    table_inspector_layer_result: dict[str, Any] | None = None,
    prefer_table_inspector_layer: bool = False,
) -> dict[str, Any]:
    def finalize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
        finalized = _direct_apply_table_inspector_metadata_mapping(
            project=project,
            mapping=mapping,
            table_inspector_layer_result=table_inspector_layer_result,
        )
        _fill_dimension_fallback_metadata(finalized, asset)
        return finalized

    if use_existing_model_metadata:
        existing_mapping = _direct_existing_catalog_mapping(
            catalog, table_name, existing
        )
        if existing_mapping.get("business_process") or existing_mapping.get(
            "semantic_subject"
        ):
            existing_mapping = _direct_apply_table_inspector_layer_mapping(
                existing_mapping,
                table_inspector_layer_result,
            )
            return finalize_mapping(existing_mapping)

    match_text = _direct_model_match_text(table_name, asset, lineage_view)
    seed_layer = _direct_seed_layer(
        table_name,
        asset,
        existing=existing,
        use_existing_model_metadata=use_existing_model_metadata,
    )
    process_match = _best_catalog_entry_match(
        _catalog_entries(catalog, "business_processes"),
        table_name=table_name,
        match_text=match_text,
    )
    subject_match = _best_catalog_entry_match(
        _catalog_entries(catalog, "semantic_subjects"),
        table_name=table_name,
        match_text=match_text,
    )
    layer = _direct_infer_layer(
        project=project,
        table_name=table_name,
        asset=asset,
        seed_layer=seed_layer,
        process_match=process_match,
        subject_match=subject_match,
        lineage_view=lineage_view,
        match_text=match_text,
        table_inspector_layer_result=table_inspector_layer_result,
        prefer_table_inspector=prefer_table_inspector_layer,
    )
    table_type = _direct_infer_table_type(
        table_name=table_name,
        layer=layer,
        existing=existing if use_existing_model_metadata else {},
        asset=asset,
        process_match=process_match,
        subject_match=subject_match,
        lineage_view=lineage_view,
        table_inspector_layer_result=table_inspector_layer_result,
    )
    applied_layer = "DIM" if table_type == "dimension" else layer
    mapping: dict[str, Any] = {
        "table": table_name,
        "layer": applied_layer,
        "table_type": table_type or "other",
        "materialized": _direct_materialized(
            layer=applied_layer,
            table_type=table_type,
            table_name=table_name,
            asset=asset,
            match_text=match_text,
        ),
        "assignment_source": "direct_catalog_match",
    }
    if (
        _direct_table_inspector_layer_result_is_usable(
            table_inspector_layer_result
        )
        and str(table_inspector_layer_result.get("layer") or "").upper()
        == layer
    ):
        mapping.update(
            {
                "layer_assignment_source": "table_inspector_layer_inference",
                "layer_assignment_reason": str(
                    table_inspector_layer_result.get("reason") or ""
                ).strip(),
                "layer_assignment_score": table_inspector_layer_result.get(
                    "confidence", 0
                ),
            }
        )
    else:
        mapping["layer_assignment_source"] = "direct_rule"

    if table_type == "dimension" and subject_match.get("score", 0) >= 2:
        subject = subject_match["entry"]
        mapping.update(
            {
                "data_domain": str(subject.get("data_domain") or "").strip(),
                "business_area": str(subject.get("business_area") or "").strip(),
                "semantic_subject": str(subject.get("code") or "").strip(),
                "dimension_role": str(
                    subject.get("dimension_role") or "BASE"
                ).strip(),
                "dimension_content_type": str(
                    subject.get("dimension_content_type") or "INFO"
                ).strip(),
                "assignment_reason": (
                    "semantic_subject_match:"
                    + ",".join(str(item) for item in subject_match["matches"])
                ),
                "assignment_score": subject_match["score"],
            }
        )
        return finalize_mapping(mapping)

    if table_type == "fact" and process_match.get("score", 0) >= 2:
        process = process_match["entry"]
        mapping.update(
            {
                "data_domain": str(process.get("data_domain") or "").strip(),
                "business_area": str(process.get("business_area") or "").strip(),
                "business_process": str(process.get("code") or "").strip(),
                "assignment_reason": (
                    "business_process_match:"
                    + ",".join(str(item) for item in process_match["matches"])
                ),
                "assignment_score": process_match["score"],
            }
        )
        return finalize_mapping(mapping)

    mapping.update(
        {
            "assignment_source": "fallback",
            "assignment_reason": "no_catalog_assignment_matched",
            "assignment_score": max(
                float(process_match.get("score") or 0),
                float(subject_match.get("score") or 0),
            ),
        }
    )
    return finalize_mapping(mapping)


def _apply_direct_lineage_business_process_propagation(
    catalog: dict[str, Any],
    mappings: dict[str, dict[str, Any]],
    lineage_view: LineageView | None,
) -> None:
    if not lineage_view:
        return

    processes = _catalog_entries(catalog, "business_processes")
    for _ in range(max(1, len(mappings))):
        changed = False
        for table_name, mapping in mappings.items():
            if mapping.get("business_process"):
                continue
            if mapping.get("table_type") != "fact":
                continue
            if str(mapping.get("layer") or "").upper() not in {"DWS", "ADS"}:
                continue

            upstream_sources: dict[str, list[str]] = {}
            for upstream_table in sorted(
                lineage_view.upstream_tables(table_name)
            ):
                upstream_mapping = mappings.get(upstream_table) or {}
                process_code = str(
                    upstream_mapping.get("business_process") or ""
                ).strip()
                if not process_code:
                    continue
                upstream_sources.setdefault(process_code, []).append(
                    upstream_table
                )

            if len(upstream_sources) != 1:
                continue

            process_code, source_tables = next(iter(upstream_sources.items()))
            process = _entry_by_code(processes, process_code)
            if not process:
                continue
            mapping.update(
                {
                    "data_domain": str(
                        process.get("data_domain") or ""
                    ).strip(),
                    "business_area": str(
                        process.get("business_area") or ""
                    ).strip(),
                    "business_process": process_code,
                    "assignment_source": "direct_lineage_propagation",
                    "assignment_reason": (
                        "upstream_business_process:" + ",".join(source_tables)
                    ),
                    "assignment_score": max(
                        float(mapping.get("assignment_score") or 0),
                        2.0,
                    ),
                }
            )
            changed = True
        if not changed:
            break


def _entry_display_name(entry: dict[str, Any], code: str) -> str:
    return str(entry.get("name") or "").strip() or _display_name_from_code(code)


DIM_ENTITY_SUFFIX_TOKENS = {
    "base",
    "dim",
    "dimension",
    "history",
    "info",
    "master",
    "profile",
    "reference",
    "snapshot",
}


def _strip_entity_key_suffix(value: str) -> str:
    return re.sub(r"(?:_id|_key|_code|_no|_number)$", "", value.lower())


def _singularize_entity_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _fallback_entity_code_from_identifier(value: str) -> str:
    stripped = _strip_entity_key_suffix(value)
    tokens = [
        _singularize_entity_token(token)
        for token in _split_identifier_tokens(stripped)
        if token not in DIM_ENTITY_SUFFIX_TOKENS
    ]
    if not tokens:
        return ""
    if tokens[0] in {"dwd", "dws", "ods", "ads"}:
        tokens = tokens[1:]
    if tokens and tokens[0] == "dim":
        tokens = tokens[1:]
    if not tokens:
        return ""
    return "_".join(tokens[:3]).upper()


def _candidate_dimension_key_columns(asset: dict[str, Any]) -> list[str]:
    ddl = asset.get("ddl") or {}
    column_names = _asset_column_names(asset)
    key_columns = [
        str(column).strip()
        for column in ddl.get("key_columns") or []
        if str(column).strip()
    ]
    candidates = []
    for column in key_columns + column_names:
        column_lower = column.lower()
        if column in candidates or _is_time_grain_key(column_lower):
            continue
        if (
            column_lower.endswith(("_id", "_key", "_code", "_no", "_number"))
            or column in key_columns
        ):
            candidates.append(column)
    return candidates


def _fallback_dimension_entity(
    *,
    table_name: str,
    asset: dict[str, Any],
    code: str = "",
) -> dict[str, Any]:
    keys = _candidate_dimension_key_columns(asset)
    if not keys:
        return {}
    entity_code = (
        _normalize_catalog_code(code)
        or _fallback_entity_code_from_identifier(keys[0])
        or _fallback_entity_code_from_identifier(table_name)
    )
    if not entity_code:
        return {}
    return {
        "code": entity_code,
        "type": "primary",
        "name": _display_name_from_code(entity_code),
        "key_columns": keys[:1],
    }


def _fill_dimension_fallback_metadata(
    mapping: dict[str, Any],
    asset: dict[str, Any],
) -> None:
    if str(mapping.get("layer") or "").upper() != "DIM":
        return
    if str(mapping.get("table_type") or "").lower() != "dimension":
        return
    fallback_entity = _fallback_dimension_entity(
        table_name=str(mapping.get("table") or ""),
        asset=asset,
        code=str(mapping.get("semantic_subject") or ""),
    )
    if fallback_entity and not mapping.get("semantic_subject"):
        mapping["semantic_subject"] = fallback_entity["code"]
    mapping.setdefault("dimension_role", "BASE")
    mapping.setdefault("dimension_content_type", "INFO")


def _column_matches_entry(column_name: str, entry: dict[str, Any]) -> bool:
    column_tokens = set(_split_identifier_tokens(column_name))
    for signal in _catalog_entry_signals(entry):
        for token in _split_identifier_tokens(signal):
            if _is_weak_match_token(token):
                continue
            if any(
                _is_match_token(column_token, token)
                for column_token in column_tokens
            ):
                return True
    return False


def _candidate_key_columns_for_entry(
    asset: dict[str, Any],
    entry: dict[str, Any],
) -> list[str]:
    column_names = _asset_column_names(asset)
    ddl = asset.get("ddl") or {}
    key_columns = [
        str(column).strip()
        for column in ddl.get("key_columns") or []
        if str(column).strip()
    ]
    candidates = []
    for column in key_columns + column_names:
        column_lower = column.lower()
        if column in candidates:
            continue
        if _is_time_grain_key(column_lower):
            continue
        if not (
            column_lower.endswith("_id")
            or column_lower == "id"
            or column in key_columns
        ):
            continue
        if _column_matches_entry(column, entry):
            candidates.append(column)
    return candidates


def _direct_entities_for_model(
    catalog: dict[str, Any],
    mapping: dict[str, Any],
    asset: dict[str, Any],
) -> list[dict[str, Any]]:
    subjects = _catalog_entries(catalog, "semantic_subjects")
    if mapping.get("semantic_subject"):
        subject = _entry_by_code(subjects, mapping["semantic_subject"])
        if not subject:
            fallback = _fallback_dimension_entity(
                table_name=str(mapping.get("table") or ""),
                asset=asset,
                code=str(mapping.get("semantic_subject") or ""),
            )
            return [fallback] if fallback else []
        code = str(subject.get("code") or "").strip()
        keys = _candidate_key_columns_for_entry(asset, subject)
        if not code or not keys:
            return []
        return [
            {
                "code": code,
                "type": "primary",
                "name": _entry_display_name(subject, code),
                "key_columns": keys,
            }
        ]

    if mapping.get("table_type") == "dimension":
        fallback = _fallback_dimension_entity(
            table_name=str(mapping.get("table") or ""),
            asset=asset,
        )
        return [fallback] if fallback else []

    if mapping.get("table_type") != "fact":
        return []

    entities = []
    seen = set()
    for subject in subjects:
        code = str(subject.get("code") or "").strip()
        keys = _candidate_key_columns_for_entry(asset, subject)
        if not code or not keys or code in seen:
            continue
        seen.add(code)
        entities.append(
            {
                "code": code,
                "type": "foreign",
                "name": _entry_display_name(subject, code),
                "key_columns": keys,
            }
        )
    return entities


def _infer_time_column(asset: dict[str, Any]) -> str:
    for column in _asset_column_names(asset):
        column_lower = column.lower()
        if column_lower in TIME_COLUMN_HINTS:
            return column
    for column in _asset_column_names(asset):
        if _is_time_grain_key(column):
            return column
    return ""


def _infer_time_period_from_name(table_name: str, time_column: str) -> str:
    text = f"{table_name}_{time_column}".lower()
    if any(token in text for token in ("hour", "hourly", "_hh")):
        return "H"
    if any(token in text for token in ("week", "weekly")):
        return "W"
    if any(token in text for token in ("month", "monthly")):
        return "M"
    if any(token in text for token in ("quarter", "quarterly")):
        return "Q"
    if any(token in text for token in ("year", "yearly")):
        return "Y"
    if any(token in text for token in ("date", "daily", "day", "_dt")):
        return "D"
    return ""


def _description_from_ddl(ddl_text: str) -> str:
    for line in str(ddl_text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            continue
        description = stripped[2:].strip()
        if not description or description.lower().startswith("table_id:"):
            continue
        return description
    return ""


def _direct_extra_model_metadata(
    *,
    catalog: dict[str, Any],
    mapping: dict[str, Any],
    asset: dict[str, Any],
    table_name: str,
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    ddl_text = _asset_ddl_text(asset)
    description = _description_from_ddl(ddl_text)
    if description:
        extra["description"] = description

    entities = _direct_entities_for_model(catalog, mapping, asset)
    if entities:
        extra["entities"] = entities
    if mapping.get("table_type") == "fact" and mapping.get("layer") == "DWS":
        grain: dict[str, Any] = {}
        entity_codes = [
            str(entity.get("code") or "").strip()
            for entity in entities
            if str(entity.get("code") or "").strip()
        ]
        time_column = _infer_time_column(asset)
        time_period = _infer_time_period_from_name(table_name, time_column)
        if entity_codes:
            grain["entities"] = entity_codes
        if time_column:
            grain["time_column"] = time_column
        if time_period:
            grain["time_period"] = time_period
        if grain:
            extra["grain"] = grain
    return extra


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
    elif table_type == "fact" and business_process:
        updated["business_process"] = business_process
        updated.pop("semantic_subject", None)
    elif table_type == "dimension":
        updated.pop("business_process", None)

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


def _direct_mapping_preserving_existing_governance(
    *,
    table_name: str,
    existing: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Keep existing governance metadata when direct matching is inconclusive."""
    if not existing:
        return mapping

    preserved = dict(mapping)
    layer = str(
        preserved.get("layer")
        or existing.get("layer")
        or _layer_from_table_name(table_name)
    ).upper()

    if (
        layer in DATA_DOMAIN_LAYERS
        and not str(preserved.get("data_domain") or "").strip()
        and str(existing.get("data_domain") or "").strip()
    ):
        preserved["data_domain"] = existing["data_domain"]
    if (
        layer in BUSINESS_AREA_LAYERS
        and not str(preserved.get("business_area") or "").strip()
        and str(existing.get("business_area") or "").strip()
    ):
        preserved["business_area"] = existing["business_area"]
    return preserved


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


def catalog_discovery_model_mapping(
    result: TableInspectResult,
) -> dict[str, Any]:
    """Return model metadata assignment discovered by table-level LLM."""
    if result.status == "blocked":
        return {}

    layer = layer_for_model(result)
    mapping: dict[str, Any] = {
        "table": result.table_name,
        "layer": layer,
        "table_type": result.table_type,
        "data_domain": result.inferred_data_domain,
        "business_area": result.inferred_business_area,
        "materialized": _materialized_for_layer(
            result.declared_layer or layer
        ),
    }
    if result.table_type == "dimension":
        semantic_subject = _semantic_subject_from_result(result)
        if semantic_subject:
            mapping["semantic_subject"] = semantic_subject
        if result.dimension_role:
            mapping["dimension_role"] = result.dimension_role
        if result.dimension_content_type:
            mapping["dimension_content_type"] = result.dimension_content_type
        return mapping

    if result.table_type == "fact":
        processes = _business_processes_from_result(result)
        if len(processes) == 1:
            mapping["business_process"] = processes[0]
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
            "dimension_role",
            "dimension_content_type",
        ):
            if key not in previous:
                updated.pop(key, None)
            else:
                updated[key] = previous[key]

    changed = updated != previous
    config_changed = updated.get("config") != previous.get("config")
    documentation_changed = updated.get("description") != previous.get(
        "description"
    )
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
        "config_changed": config_changed,
        "documentation_changed": documentation_changed,
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


def _apply_table_inspector_payload_to_direct_model(
    updated: dict[str, Any],
    result: TableInspectResult | None,
    *,
    write_scope: str,
) -> None:
    if (
        not isinstance(result, TableInspectResult)
        or result.status == "blocked"
        or _validate_write_scope(write_scope) != "all"
    ):
        return

    model_layer = str(updated.get("layer") or "").upper()
    if model_layer in {"ODS", "ADS"}:
        updated.pop("atomic_metrics", None)
        updated.pop("derived_metrics", None)
        updated.pop("calculated_metrics", None)
        updated.pop("metrics", None)
        updated.pop("entities", None)
        updated.pop("entity", None)
        updated.pop("related_entities", None)
        updated.pop("grain", None)
        return

    can_write_metrics = (
        model_layer in METRIC_LAYERS
        and str(updated.get("table_type") or "").lower() == "fact"
        and float(result.confidence or 0) >= 0.5
    )
    if can_write_metrics:
        detected_groups = metric_groups_for_model(result)
        detected_metrics = metric_names_for_model(result)
        if detected_metrics:
            for key in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            ):
                if detected_groups[key]:
                    updated[key] = detected_groups[key]
                else:
                    updated.pop(key, None)
        else:
            updated.pop("atomic_metrics", None)
            updated.pop("derived_metrics", None)
            updated.pop("calculated_metrics", None)
        updated.pop("metrics", None)
    elif _validate_write_scope(write_scope) == "all":
        updated.pop("atomic_metrics", None)
        updated.pop("derived_metrics", None)
        updated.pop("calculated_metrics", None)
        updated.pop("metrics", None)

    if should_write_grain_metadata(result, write_scope):
        entity_metadata = _canonical_entities_for_write(
            result,
            _effective_entities(result),
            model_layer=str(updated.get("layer") or ""),
        )
        if model_layer == "DIM":
            grain_metadata = {}
        else:
            grain_metadata = _canonical_grain_for_write(
                _effective_grain(result.grain),
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


def update_model_yaml_from_direct_generation(
    project: str,
    table_name: str,
    mapping: dict[str, Any],
    *,
    catalog: dict[str, Any],
    asset: dict[str, Any],
    dry_run: bool = False,
    write_scope: str = "all",
    base_existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in DIRECT_MODEL_WRITE_SCOPES:
        raise ValueError("generate-models 仅支持 write_scope=all/table/business")

    path = model_path_for_table(
        project,
        table_name,
        layer=mapping.get("layer"),
    )
    existing = _existing_model_data(path)
    previous = dict(existing)
    payload_existing = existing if base_existing is None else dict(base_existing)
    payload_mapping = (
        _direct_mapping_preserving_existing_governance(
            table_name=table_name,
            existing=existing,
            mapping=mapping,
        )
        if base_existing is None
        else mapping
    )
    updated = _catalog_model_payload(
        table_name=table_name,
        existing=payload_existing,
        mapping=payload_mapping,
    )
    if write_scope == "table":
        for key in (
            "data_domain",
            "business_area",
            "business_process",
            "semantic_subject",
            "dimension_role",
            "dimension_content_type",
        ):
            if key not in previous:
                updated.pop(key, None)
            else:
                updated[key] = previous[key]

    if write_scope == "all":
        extra = _direct_extra_model_metadata(
            catalog=catalog,
            mapping=mapping,
            asset=asset,
            table_name=table_name,
        )
        if extra.get("description") and not updated.get("description"):
            updated["description"] = extra["description"]
        for key in ("entities", "grain"):
            if extra.get(key) and not updated.get(key):
                updated[key] = extra[key]
        _apply_table_inspector_payload_to_direct_model(
            updated,
            mapping.get("_table_inspector_result"),
            write_scope=write_scope,
        )

    changed = updated != previous
    config_changed = updated.get("config") != previous.get("config")
    documentation_changed = updated.get("description") != previous.get(
        "description"
    )
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
    metric_changed = any(
        updated.get(key) != previous.get(key)
        for key in (
            "metrics",
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
    )
    grain_changed = any(
        updated.get(key) != previous.get(key)
        for key in ("entities", "grain")
    )
    detected_metrics = _extract_existing_metric_names(updated)
    previous_metrics = _extract_existing_metric_names(previous)
    entity_count = len(
        normalize_entities(
            updated.get("entities"),
            updated.get("entity"),
            updated.get("related_entities"),
        )
    )
    has_grain = bool(_effective_grain(updated.get("grain")))
    inspection_result = mapping.get("_table_inspector_result")
    metric_generation_source = ""
    if (
        isinstance(inspection_result, TableInspectResult)
        and inspection_result.status != "blocked"
        and float(inspection_result.confidence or 0) >= 0.5
        and str(updated.get("layer") or "").upper() in METRIC_LAYERS
        and str(updated.get("table_type") or "").lower() == "fact"
        and _validate_write_scope(write_scope) == "all"
    ):
        metric_generation_source = "table_inspector"
    return {
        "table": table_name,
        "path": str(path),
        "status": "passed",
        "changed": changed,
        "metadata_changed": any(
            updated.get(key) != previous.get(key)
            for key in ("layer", "table_type")
        ),
        "config_changed": config_changed,
        "documentation_changed": documentation_changed,
        "business_changed": business_changed,
        "metric_changed": metric_changed,
        "metric_count": len(detected_metrics),
        "new_metric_count": len(
            [name for name in detected_metrics if name not in previous_metrics]
        ),
        "removed_metric_count": len(
            [name for name in previous_metrics if name not in detected_metrics]
        ),
        "grain_changed": grain_changed,
        "entity_count": entity_count,
        "has_grain": has_grain,
        "updated": bool(changed and not dry_run),
        "write_scope": write_scope,
        "source": "direct_generation",
        "metric_generation_source": metric_generation_source,
        "assignment_source": mapping.get("assignment_source", ""),
        "assignment_reason": mapping.get("assignment_reason", ""),
        "assignment_score": mapping.get("assignment_score", 0),
        "layer_assignment_source": mapping.get("layer_assignment_source", ""),
        "layer_assignment_reason": mapping.get("layer_assignment_reason", ""),
        "layer_assignment_score": mapping.get("layer_assignment_score", 0),
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


def run_direct_model_generation(
    project: str,
    *,
    dry_run: bool = False,
    write_scope: str = "all",
    ignore_existing_models: bool = False,
    infer_layer_with_llm: bool = False,
    api_key: str = "",
    model: str = "deepseek-v4-flash",
    base_url: str = "",
    max_retries: int = 1,
    parallelism: int = 4,
    request_timeout: int = 180,
    no_cache: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Generate model YAML from catalog, DDL, tasks, and lineage facts."""
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in DIRECT_MODEL_WRITE_SCOPES:
        raise ValueError("generate-models 仅支持 write_scope=all/table/business")
    if infer_layer_with_llm and not api_key:
        raise ValueError("infer_layer_with_llm=True 时必须提供 api_key")

    catalog = load_business_semantics_catalog(project)
    if not catalog:
        raise FileNotFoundError(
            f"未找到 {project}/business_semantics.yaml，请先初始化目录"
        )

    lineage_data, warnings = _load_lineage_data_for_direct_generation(project)
    if ignore_existing_models and not _direct_catalog_has_business_entries(
        catalog
    ):
        warnings.append(
            {
                "type": "business_semantics_catalog_empty",
                "severity": "degraded",
                "message": (
                    "business_semantics.yaml 未配置 business_processes 或 "
                    "semantic_subjects；冷启动业务域、业务板块、业务过程和"
                    "语义主题归属会明显降级"
                ),
            }
        )
    lineage_view = _lineage_view_for_direct_generation(project, lineage_data)
    model_metadata = {} if ignore_existing_models else load_model_metadata(project)
    assets = _direct_table_assets(
        project,
        lineage_data,
        model_metadata=model_metadata,
        include_model_files=not ignore_existing_models,
    )
    updates = []
    table_assets: dict[str, dict[str, Any]] = {}
    existing_by_table: dict[str, dict[str, Any]] = {}
    mappings: dict[str, dict[str, Any]] = {}
    for table_name, asset in sorted(assets.items()):
        ddl = asset.get("ddl") or {}
        lineage_table = asset.get("lineage_table") or {}
        tasks = asset.get("tasks") or []
        if not ddl.get("exists") and not lineage_table and not tasks:
            continue
        existing = model_metadata.get(table_name, {})
        table_assets[table_name] = asset
        existing_by_table[table_name] = existing

    table_inspector_layer_results: dict[str, dict[str, Any]] = {}
    table_inspector_candidate_details: list[dict[str, str]] = []
    table_inspector_skip_reasons: dict[str, int] = {}
    if infer_layer_with_llm:
        cold_start_full_metadata = (
            ignore_existing_models and write_scope == "all"
        )
        llm_candidates = {}
        for table_name, asset in sorted(table_assets.items()):
            existing = existing_by_table.get(table_name, {})
            reason = _direct_table_inspector_candidate_reason(
                project=project,
                table_name=table_name,
                asset=asset,
                existing=existing,
                use_existing_model_metadata=not ignore_existing_models,
                cold_start_full_metadata=cold_start_full_metadata,
                lineage_view=lineage_view,
            )
            if reason:
                llm_candidates[table_name] = asset
                table_inspector_candidate_details.append(
                    {"table": table_name, "reason": reason}
                )
                continue
            skip_reason = _direct_table_inspector_skip_reason(
                project=project,
                table_name=table_name,
                asset=asset,
                existing=existing,
                use_existing_model_metadata=not ignore_existing_models,
                lineage_view=lineage_view,
            )
            table_inspector_skip_reasons[skip_reason] = (
                table_inspector_skip_reasons.get(skip_reason, 0) + 1
            )
        (
            table_inspector_layer_results,
            table_inspector_warnings,
        ) = _direct_infer_layers_with_table_inspector(
            catalog=catalog,
            project=project,
            table_assets=llm_candidates,
            all_table_assets=table_assets,
            existing_by_table=existing_by_table,
            use_existing_model_metadata=not ignore_existing_models,
            lineage_view=lineage_view,
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            parallelism=parallelism,
            request_timeout=request_timeout,
            no_cache=no_cache,
            show_progress=show_progress,
        )
        warnings.extend(table_inspector_warnings)

    for table_name, asset in sorted(table_assets.items()):
        existing = existing_by_table.get(table_name, {})
        mappings[table_name] = _direct_catalog_mapping_for_model(
            catalog,
            project,
            table_name,
            asset,
            existing=existing,
            lineage_view=lineage_view,
            use_existing_model_metadata=not ignore_existing_models,
            table_inspector_layer_result=table_inspector_layer_results.get(
                table_name
            ),
            prefer_table_inspector_layer=ignore_existing_models,
        )

    _apply_direct_lineage_business_process_propagation(
        catalog,
        mappings,
        lineage_view,
    )

    for table_name, asset in sorted(table_assets.items()):
        mapping = mappings[table_name]
        updates.append(
            update_model_yaml_from_direct_generation(
                project,
                table_name,
                mapping,
                catalog=catalog,
                asset=asset,
                dry_run=dry_run,
                write_scope=write_scope,
                base_existing={} if ignore_existing_models else None,
            )
        )
    if not dry_run:
        import config as _config

        _config.clear_model_metadata_cache()

    changed_updates = [update for update in updates if update["changed"]]
    return {
        "project": project,
        "source": "direct_generation",
        "write_scope": write_scope,
        "ignore_existing_models": ignore_existing_models,
        "infer_layer_with_llm": infer_layer_with_llm,
        "request_timeout": request_timeout if infer_layer_with_llm else 0,
        "catalog_path": str(
            PROJECT_ROOT
            / PROJECT_CONFIG[project]["dir"]
            / "business_semantics.yaml"
        ),
        "warning_count": len(warnings),
        "warnings": warnings,
        "inspected_table_count": len(updates),
        "model_updates": changed_updates,
        "model_update_count": len(
            [update for update in changed_updates if update.get("updated")]
        ),
        "model_change_count": len(changed_updates),
        "assigned_business_process_count": len(
            [
                update
                for update in updates
                if update.get("business_process")
                and update.get("assignment_source") != "fallback"
            ]
        ),
        "assigned_semantic_subject_count": len(
            [
                update
                for update in updates
                if update.get("semantic_subject")
                and update.get("assignment_source") != "fallback"
            ]
        ),
        "table_inspector_layer_inference_attempt_count": len(
            table_inspector_layer_results
        ),
        "table_inspector_layer_inference_candidate_count": len(
            table_inspector_candidate_details
        ),
        "table_inspector_layer_inference_candidates": (
            table_inspector_candidate_details
        ),
        "table_inspector_layer_inference_skip_reasons": (
            table_inspector_skip_reasons
        ),
        "table_inspector_layer_inference_count": len(
            [
                update
                for update in updates
                if update.get("layer_assignment_source")
                == "table_inspector_layer_inference"
            ]
        ),
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
            f"未找到 {project}/business_semantics.yaml，请先初始化目录"
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
        "catalog_path": str(
            PROJECT_ROOT
            / PROJECT_CONFIG[project]["dir"]
            / "business_semantics.yaml"
        ),
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
    base_url: str = "",
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 180,
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

    inspector_kwargs = {
        "model": model,
        "cache_file": cache_file,
        "max_retries": max_retries,
        "parallelism": parallelism,
        "request_timeout": request_timeout,
    }
    if base_url:
        inspector_kwargs["base_url"] = base_url
    inspector = _create_table_inspector(
        api_key=api_key,
        inspector_kwargs=inspector_kwargs,
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
    for result in results:
        mapping = catalog_discovery_model_mapping(result)
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
    base_url: str = "",
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 180,
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

    inspector_kwargs = {
        "model": model,
        "cache_file": cache_file,
        "max_retries": max_retries,
        "parallelism": parallelism,
        "request_timeout": request_timeout,
    }
    if base_url:
        inspector_kwargs["base_url"] = base_url
    inspector = _create_table_inspector(
        api_key=api_key,
        inspector_kwargs=inspector_kwargs,
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
        "--base-url",
        default=os.environ.get("LLM_BASE_URL", ""),
        help=(
            "OpenAI-compatible API Base URL，默认使用 DeepSeek；"
            "也可通过 LLM_BASE_URL 或 DEEPSEEK_BASE_URL 设置"
        ),
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
        help="按项目DDL初始化 business_semantics.yaml",
    )
    parser.add_argument(
        "--catalog-from-llm",
        action="store_true",
        help="调用表级 LLM 巡检结果初始化/更新 business_semantics.yaml",
    )
    parser.add_argument(
        "--overwrite-catalog",
        action="store_true",
        help="catalog-from-llm/init-catalog 时覆盖已存在目录",
    )
    parser.add_argument(
        "--from-catalog",
        action="store_true",
        help="从 business_semantics.yaml 刷新/初始化 models",
    )
    parser.add_argument(
        "--generate-models",
        action="store_true",
        help=(
            "基于 business_semantics.yaml、DDL、task 和 lineage "
            "直接生成/补齐 models YAML，默认不调用 LLM"
        ),
    )
    parser.add_argument(
        "--infer-layer-with-llm",
        action="store_true",
        help=(
            "仅用于 --generate-models: 当没有现有 layer、表名前缀或 ODS "
            "目录等明确分层信息时，调用 LLM 判断 layer"
        ),
    )
    parser.add_argument(
        "--ignore-existing-models",
        action="store_true",
        help=(
            "仅用于 --generate-models: 不读取现有 models YAML 作为推断先验，"
            "按 business_semantics、DDL、task 和 lineage 从零生成"
        ),
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
        "--parallel", type=int, default=4, help="LLM 并发调用数，默认 4"
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=180,
        help="单次 LLM 请求超时时间（秒），默认 180",
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
            base_url=args.base_url,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
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
    elif args.generate_models:
        api_key = ""
        if args.infer_layer_with_llm:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise SystemExit(
                    "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 LLM 推断 layer"
                )
        result = run_direct_model_generation(
            args.project,
            dry_run=args.dry_run,
            write_scope=args.write_scope,
            ignore_existing_models=args.ignore_existing_models,
            infer_layer_with_llm=args.infer_layer_with_llm,
            api_key=api_key,
            model=args.model,
            base_url=args.base_url,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
            no_cache=args.no_cache,
            show_progress=not args.quiet,
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
            base_url=args.base_url,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
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
        print(
            "回写来源: catalog, "
            "巡检表: {inspected_table_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
                **result
            )
        )
        return
    if result.get("source") == "direct_generation":
        print(
            "直接生成: "
            "巡检表: {inspected_table_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}, "
            "业务过程归属: {assigned_business_process_count}, "
            "语义主题归属: {assigned_semantic_subject_count}, "
            "表巡检分层: "
            "{table_inspector_layer_inference_count}/"
            "{table_inspector_layer_inference_attempt_count}"
            " (候选 {table_inspector_layer_inference_candidate_count}), "
            "警告: {warning_count}".format(**result)
        )
        return
    if result.get("source") == "llm_catalog_discovery":
        print(
            "目录发现: {path}, "
            "巡检表: {inspected_table_count}, "
            "业务过程: {business_process_count}, "
            "语义主题: {semantic_subject_count}, 已写入: {updated}".format(
                **result
            )
        )
        return
    if "catalog" in result:
        catalog = result.get("catalog") or {}
        print(
            "目录初始化: {path}, "
            "业务过程: {process_count}, 语义主题: {subject_count}, 已写入: {updated}".format(
                path=result.get("path"),
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
