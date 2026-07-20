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

import sqlglot
import yaml
from sqlglot import exp

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
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspectResult,
    validate_inspection_result,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    _infer_table_type,
    _materialized_for_layer,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    legacy_entity_from_entities,
    legacy_related_entities_from_entities,
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
        if not grain_entities:
            return []
        pairs = []
        wanted = {entity.casefold() for entity in grain_entities}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            code = str(entity.get("code") or "").strip()
            if code.casefold() not in wanted:
                continue
            for key in _as_string_list(entity.get("key_columns")):
                pairs.append((key, code))
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
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        if (
            result.status == "blocked"
            or result.table_type != "fact"
            or str(result.inferred_layer or "").upper() != "DWS"
        ):
            continue
        grouped: dict[str, dict[str, Any]] = {}
        for key, entity in _grain_key_entity_pairs(
            result.grain, result.entities
        ):
            entity_code = str(entity or "").strip()
            key_column = str(key or "").strip()
            if not entity_code or not key_column:
                continue
            canonical_code = entity_code.casefold()
            candidate = grouped.setdefault(
                canonical_code,
                {
                    "code": entity_code,
                    "key_columns": [],
                },
            )
            canonical_keys = {
                column.casefold() for column in candidate["key_columns"]
            }
            if key_column.casefold() not in canonical_keys:
                candidate["key_columns"].append(key_column)
        if grouped:
            index[result.table_name] = list(grouped.values())
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


def _canonical_table_reference(value: Any) -> str:
    text = str(value or "").strip().replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _split_column_reference(value: Any) -> tuple[str, str]:
    reference = _canonical_table_reference(value)
    if "." not in reference:
        return "", reference
    table_name, column_name = reference.rsplit(".", 1)
    return table_name, column_name


def _table_reference_matches(
    reference: str,
    table_name: str,
    context: TableContext,
) -> bool:
    wanted = _canonical_table_reference(reference)
    if not wanted:
        return False
    identity = _canonical_table_reference(context.table_identity)
    short_name = _canonical_table_reference(table_name).split(".")[-1]
    if "." in wanted and "." in identity:
        return (
            wanted == identity
            or wanted.endswith(f".{identity}")
            or identity.endswith(f".{wanted}")
        )
    return wanted.split(".")[-1] == short_name


def _context_for_table(
    contexts: dict[str, TableContext],
    table_name: str,
) -> TableContext | None:
    context = contexts.get(table_name)
    if context is not None:
        return context
    wanted = _canonical_table_reference(table_name)
    matches = [
        candidate
        for name, candidate in contexts.items()
        if _canonical_table_reference(name) == wanted
    ]
    return matches[0] if len(matches) == 1 else None


def _direct_grain_key_mapping(
    dimension_table: str,
    dimension_context: TableContext,
    grain_table: str,
    grain_context: TableContext,
    grain_keys: list[str],
    ddl_columns: dict[str, tuple[str, str]],
) -> tuple[str, ...]:
    source_columns = []
    for grain_key in grain_keys:
        matching_sources = set()
        wanted_key = grain_key.casefold()
        for edge in grain_context.column_lineage or []:
            if not isinstance(edge, dict):
                continue
            source_table, source_column = _split_column_reference(
                edge.get("source")
            )
            target_table, target_column = _split_column_reference(
                edge.get("target")
            )
            if (
                target_column != wanted_key
                or not _table_reference_matches(
                    target_table,
                    grain_table,
                    grain_context,
                )
                or not _table_reference_matches(
                    source_table,
                    dimension_table,
                    dimension_context,
                )
                or source_column not in ddl_columns
            ):
                continue
            matching_sources.add(source_column)
        if len(matching_sources) != 1:
            return ()
        source_columns.append(next(iter(matching_sources)))
    if len(set(source_columns)) != len(source_columns):
        return ()
    return tuple(source_columns)


def discover_related_entities_from_grain(
    result: TableInspectResult,
    context: TableContext | None,
    grain_entity_index: dict[str, list[dict[str, Any]]],
    contexts: dict[str, TableContext] | None = None,
) -> list[dict[str, Any]]:
    """从直接字段血缘证明的 DWS grain 反推维度表关联实体。"""
    if (
        result.table_type != "dimension"
        or not result.entity
        or not context
        or not contexts
    ):
        return []
    primary_code = str(result.entity.get("code") or "").strip()
    primary_keys = {
        key.casefold()
        for key in _as_string_list(result.entity.get("key_columns"))
    }
    if not primary_code or not primary_keys:
        return []

    comments_by_column = _column_comments_from_ddl(context.ddl)
    ddl_columns = {
        column.casefold(): (column, comment)
        for column, comment in comments_by_column.items()
    }
    mappings_by_code: dict[
        str,
        dict[frozenset[str], tuple[str, ...]],
    ] = {}
    display_codes = {}
    for grain_table, candidates in grain_entity_index.items():
        grain_context = _context_for_table(contexts, grain_table)
        if grain_context is None:
            continue
        for candidate in candidates:
            related_code = str(candidate.get("code") or "").strip()
            canonical_code = related_code.casefold()
            if not related_code or canonical_code == primary_code.casefold():
                continue
            mapping = _direct_grain_key_mapping(
                result.table_name,
                context,
                grain_table,
                grain_context,
                _as_string_list(candidate.get("key_columns")),
                ddl_columns,
            )
            if not mapping:
                continue
            display_codes.setdefault(canonical_code, related_code)
            mappings_by_code.setdefault(canonical_code, {}).setdefault(
                frozenset(mapping),
                mapping,
            )

    resolved_mappings = {
        code: next(iter(mappings.values()))
        for code, mappings in mappings_by_code.items()
        if len(mappings) == 1
    }
    codes_by_column: dict[str, set[str]] = {}
    for code, mappings in mappings_by_code.items():
        for key_columns in mappings.values():
            for key_column in key_columns:
                codes_by_column.setdefault(key_column, set()).add(code)

    discovered = []
    for canonical_code, key_columns in sorted(resolved_mappings.items()):
        if any(
            key_column in primary_keys
            or len(codes_by_column.get(key_column, set())) != 1
            for key_column in key_columns
        ):
            continue
        actual_columns = [ddl_columns[key][0] for key in key_columns]
        comment = next(
            (
                ddl_columns[key][1]
                for key in key_columns
                if ddl_columns[key][1]
            ),
            "",
        )
        discovered.append(
            {
                "code": display_codes[canonical_code],
                "name": _entity_name_from_comment(comment),
                "key_columns": actual_columns,
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
            contexts,
        )
        if discovered:
            result.resume_eligible = False
            result.related_entities = _merge_related_entities(
                result.related_entities,
                discovered,
            )
            result.entities = normalize_entities(
                result.entities,
                result.entity,
                result.related_entities,
            )


def enrich_results_with_project_semantics(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None = None,
) -> None:
    """Enrich related entities, then reconcile project-wide semantic codes."""
    enrich_results_with_related_entities(results, contexts)
    reconcile_project_semantics(results, contexts, catalog=catalog)
    _mark_composite_business_processes(results, contexts)
    promoted_results = [
        result
        for result in results
        if _promote_count_aggregates_to_atomic(result)
    ]
    if promoted_results:
        for result in promoted_results:
            context = _context_for_table(contexts, result.table_name)
            if context is not None:
                validate_inspection_result(result, context)
        _reconcile_business_processes(results, contexts, catalog=catalog)


def _promote_count_aggregates_to_atomic(
    result: TableInspectResult,
) -> bool:
    """Normalize target-grain row counts that do not have a base metric."""
    if (
        result.table_type != "fact"
        or str(result.inferred_layer or "").upper() != "DWS"
    ):
        return False
    promoted = []
    remaining = []
    atomic_names = {
        str(metric.get("name") or "").strip().casefold()
        for metric in result.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    for metric in result.derived_metrics:
        if (
            not isinstance(metric, dict)
            or str(metric.get("base_metric") or "").strip()
            or not _is_count_aggregate(metric.get("expression"))
        ):
            remaining.append(metric)
            continue
        name = str(metric.get("name") or "").strip()
        if not name:
            remaining.append(metric)
            continue
        normalized = {
            key: metric[key]
            for key in (
                "name",
                "data_type",
                "business_process",
                "action",
                "measure",
                "description",
                "reason",
                "confidence",
            )
            if key in metric
        }
        normalized["action"] = str(normalized.get("action") or "COUNT").strip()
        if name.casefold() not in atomic_names:
            result.columns.setdefault("atomic_metrics", []).append(normalized)
            atomic_names.add(name.casefold())
        promoted.append(name)
    if not promoted:
        return False

    result.columns["derived_metrics"] = remaining
    _remove_stale_metric_validation(result, promoted)
    result.resume_eligible = False
    message = (
        "semantic_reconciliation: promoted target-grain count aggregates "
        "to atomic metrics"
    )
    if message not in result.reasoning_steps:
        result.reasoning_steps.append(message)
    return True


def _is_count_aggregate(expression: Any) -> bool:
    text = str(expression or "").strip()
    if not text:
        return False
    try:
        parsed = sqlglot.parse_one(text, read="doris")
    except sqlglot.errors.SqlglotError:
        shorthand = re.fullmatch(
            r"(COUNT\s*\([^()]+\))\s+WHERE\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if shorthand is None:
            return False
        try:
            count = sqlglot.parse_one(shorthand.group(1), read="doris")
            predicate = sqlglot.parse_one(shorthand.group(2), read="doris")
        except sqlglot.errors.SqlglotError:
            return False
        forbidden_predicate_nodes = (
            exp.AggFunc,
            exp.Window,
            exp.Select,
            exp.Subquery,
        )
        return isinstance(count, exp.Count) and not any(
            predicate.find(node_type) is not None
            for node_type in forbidden_predicate_nodes
        )
    if isinstance(parsed, exp.Count):
        return True
    if not isinstance(parsed, exp.Sum) or not isinstance(
        parsed.this, exp.Case
    ):
        return False
    case = parsed.this
    values = [branch.args.get("true") for branch in case.args.get("ifs") or []]
    default = case.args.get("default")
    if default is not None:
        values.append(default)
    numeric_values = []
    for value in values:
        if not isinstance(value, exp.Literal) or value.is_string:
            return False
        try:
            numeric_values.append(float(value.this))
        except (TypeError, ValueError):
            return False
    return (
        bool(numeric_values)
        and 1.0 in numeric_values
        and set(numeric_values) <= {0.0, 1.0}
    )


def _remove_stale_metric_validation(
    result: TableInspectResult,
    metric_names: list[str],
) -> None:
    wanted = {name.casefold() for name in metric_names}
    validation = dict(result.validation or {})
    for key in (
        "missing_base_metrics",
        "missing_base_metric_tables",
        "invalid_base_metrics",
        "invalid_base_metric_tables",
        "ambiguous_base_metrics",
        "invalid_time_periods",
        "invalid_metric_expressions",
    ):
        remaining = [
            value
            for value in validation.get(key) or []
            if str(value).split(":", 1)[0].strip().casefold() not in wanted
        ]
        if remaining:
            validation[key] = remaining
        else:
            validation.pop(key, None)
    result.validation = validation


def reconcile_project_semantics(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None = None,
) -> None:
    """Reconcile only semantics supported by unique project-wide evidence."""
    _reconcile_dimension_entity_codes(
        results,
        contexts,
        catalog=catalog,
    )
    _reconcile_entity_codes(results, contexts)
    _reconcile_business_processes(results, contexts, catalog=catalog)


def _mark_composite_business_processes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> None:
    """Mark DWS facts whose metrics are contributed by multiple sources."""
    for result in results:
        if (
            result.table_type != "fact"
            or str(result.inferred_layer or "").upper() != "DWS"
            or str(result.business_process or "").strip()
            or result.business_process_mode
        ):
            continue
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        evidence = _contributing_metric_source_evidence(
            result,
            context,
            results,
            contexts,
        )
        if len(evidence) < 2:
            continue
        process_evidence = [
            (source, metrics)
            for _identity, source, metrics in evidence
            if source.table_type == "fact"
            and source.status != "blocked"
            and str(source.business_process or "").strip()
        ]
        if not process_evidence:
            continue
        metric_process_evidence: dict[int, set[str]] = {}
        metrics_by_identity: dict[int, dict[str, Any]] = {}
        for source, metrics in process_evidence:
            process = str(source.business_process or "").strip()
            for metric in metrics:
                identity = id(metric)
                metrics_by_identity[identity] = metric
                metric_process_evidence.setdefault(identity, set()).add(
                    process
                )
        process_conflicts = []
        for identity, processes in metric_process_evidence.items():
            metric = metrics_by_identity[identity]
            current_process = str(metric.get("business_process") or "").strip()
            if current_process:
                processes.add(current_process)
            canonical_processes = {
                process.casefold() for process in processes if process
            }
            if len(canonical_processes) > 1:
                process_conflicts.append(str(metric.get("name") or "").strip())
                continue
            if not current_process and len(canonical_processes) == 1:
                metric["business_process"] = sorted(
                    processes,
                    key=lambda process: (process.casefold(), process),
                )[0]
        process_codes = {
            str(metric.get("business_process") or "").strip().casefold()
            for group in (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            )
            for metric in group
            if isinstance(metric, dict)
            and str(metric.get("business_process") or "").strip()
        }
        if not process_codes and not process_conflicts:
            continue
        result.business_process_mode = "composite"
        result.business_process_sources = [
            identity for identity, _source, _metrics in evidence
        ]
        result.business_process_conflicts = sorted(
            {metric_name for metric_name in process_conflicts if metric_name},
            key=str.casefold,
        )
        result.resume_eligible = False
        result.validation = {
            key: values
            for key, values in (result.validation or {}).items()
            if key
            not in {
                "business_process_missing",
                "business_process_ambiguous",
            }
        }
        message = (
            "semantic_reconciliation: marked multi-source DWS as composite"
        )
        if message not in result.reasoning_steps:
            result.reasoning_steps.append(message)


def _contributing_metric_source_evidence(
    result: TableInspectResult,
    context: TableContext,
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[tuple[str, TableInspectResult, list[dict[str, Any]]]]:
    target_metrics = [
        metric
        for group in (
            result.atomic_metrics,
            result.derived_metrics,
            result.calculated_metrics,
        )
        for metric in group
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    ]
    metrics_by_name = {
        str(metric.get("name") or "").strip().casefold(): metric
        for metric in target_metrics
    }
    references: dict[str, list[dict[str, Any]]] = {}
    for metric in result.derived_metrics:
        if not isinstance(metric, dict):
            continue
        reference = str(metric.get("base_metric_table") or "").strip()
        if not reference or (
            not str(metric.get("base_metric") or "").strip()
            and not _is_count_aggregate(metric.get("expression"))
        ):
            continue
        references.setdefault(reference, []).append(metric)

    for edge in context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if (
            target_column not in metrics_by_name
            or (
                target_table
                and not _table_reference_matches(
                    target_table,
                    result.table_name,
                    context,
                )
            )
            or not source_table
        ):
            continue
        source = _result_for_table_reference(
            results,
            contexts,
            source_table,
        )
        if source is None:
            continue
        source_metric_names = {
            str(metric.get("name") or "").strip().casefold()
            for group in (
                source.atomic_metrics,
                source.derived_metrics,
                source.calculated_metrics,
            )
            for metric in group
            if isinstance(metric, dict)
            and str(metric.get("name") or "").strip()
        }
        if source_column not in source_metric_names:
            continue
        references.setdefault(source_table, []).append(
            metrics_by_name[target_column]
        )

    evidence = []
    seen_identities = set()
    for reference in sorted(references):
        source = _result_for_table_reference(results, contexts, reference)
        if source is None or source is result:
            continue
        source_context = _context_for_table(contexts, source.table_name)
        identity = (
            source_context.table_identity
            if source_context is not None and source_context.table_identity
            else source.table_name
        )
        if (
            identity
            and not _table_reference_matches(
                identity,
                result.table_name,
                context,
            )
            and identity.casefold() not in seen_identities
        ):
            metrics = list(
                {
                    id(metric): metric for metric in references[reference]
                }.values()
            )
            evidence.append((identity, source, metrics))
            seen_identities.add(identity.casefold())
    return sorted(evidence, key=lambda item: item[0].casefold())


def _reconcile_business_processes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None,
) -> None:
    established_codes = _catalog_code_lookup(
        catalog,
        "business_processes",
    )
    for _iteration in range(len(results) or 1):
        changed = False
        for result in results:
            if not _process_reconciliation_is_eligible(result):
                continue
            context = _context_for_table(contexts, result.table_name)
            if context is None:
                continue
            sources = _metric_process_source_results(
                result,
                context,
                results,
                contexts,
            )
            source_processes = {
                str(source.business_process or "").strip()
                for source in sources
                if str(source.business_process or "").strip()
            }
            if len(source_processes) != 1:
                continue
            if str(
                result.inferred_layer or ""
            ).upper() == "DWD" and not _dwd_process_sources_are_equivalent(
                result,
                context,
                sources,
                contexts,
            ):
                continue
            canonical_process = _preferred_equivalent_code(
                next(iter(source_processes)),
                result.business_process,
                established_codes,
            )
            if not canonical_process:
                continue
            if _set_result_business_process(result, canonical_process):
                changed = True
        if not changed:
            break


def _process_reconciliation_is_eligible(
    result: TableInspectResult,
) -> bool:
    if result.table_type != "fact" or str(
        result.inferred_layer or ""
    ).upper() not in {"DWD", "DWS"}:
        return False
    if result.business_process_mode == "composite":
        return False
    blocking_keys = {
        key for key, values in (result.validation or {}).items() if values
    }
    return not blocking_keys or blocking_keys <= {
        "business_process_missing",
        "business_process_ambiguous",
    }


def _metric_process_source_results(
    result: TableInspectResult,
    context: TableContext,
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[TableInspectResult]:
    sources = []
    for _identity, source, _metrics in _contributing_metric_source_evidence(
        result,
        context,
        results,
        contexts,
    ):
        if source.table_type != "fact" or source.status == "blocked":
            return []
        if source not in sources:
            sources.append(source)
    references = {
        str(metric.get("base_metric_table") or "").strip()
        for metric in result.derived_metrics
        if isinstance(metric, dict)
        and str(metric.get("base_metric_table") or "").strip()
    }
    references.update(
        str(table_name).strip()
        for table_name, groups in (
            context.upstream_metric_groups or {}
        ).items()
        if any(groups.values())
    )
    for reference in sorted(references):
        source = _result_for_table_reference(
            results,
            contexts,
            reference,
        )
        if (
            source is None
            or source.table_type != "fact"
            or source.status == "blocked"
        ):
            return []
        if source not in sources:
            sources.append(source)
    return sources


def _dwd_process_sources_are_equivalent(
    result: TableInspectResult,
    context: TableContext,
    sources: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> bool:
    if (
        len(sources) != 1
        or result.derived_metrics
        or result.calculated_metrics
    ):
        return False
    if not _is_strict_row_preserving_select(context.etl_sql):
        return False
    source = sources[0]
    source_context = _context_for_table(contexts, source.table_name)
    if source_context is None:
        return False
    source_metrics = {
        str(metric.get("name") or "").strip().casefold()
        for metric in source.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    target_metrics = {
        str(metric.get("name") or "").strip().casefold()
        for metric in result.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    if not source_metrics or not target_metrics:
        return False
    source_primary = _single_primary_entity(source)
    target_primary = _single_primary_entity(result)
    if source_primary is None or target_primary is None:
        return False
    if (
        str(source_primary.get("code") or "").strip().casefold()
        != str(target_primary.get("code") or "").strip().casefold()
        or source.grain != result.grain
    ):
        return False
    source_keys = {
        key.casefold()
        for key in _as_string_list(source_primary.get("key_columns"))
    }
    target_keys = {
        key.casefold()
        for key in _as_string_list(target_primary.get("key_columns"))
    }
    if not source_keys or source_keys != target_keys:
        return False
    matched_targets = set()
    matched_target_keys = set()
    for edge in context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if not _table_reference_matches(
            source_table,
            source.table_name,
            source_context,
        ) or not _table_reference_matches(
            target_table,
            result.table_name,
            context,
        ):
            continue
        if source_column in source_metrics and target_column in target_metrics:
            matched_targets.add(target_column)
        if source_column in source_keys and target_column in target_keys:
            matched_target_keys.add(target_column)
    return (
        matched_targets == target_metrics
        and matched_target_keys == target_keys
    )


def _is_strict_row_preserving_select(sql_text: str) -> bool:
    if not str(sql_text or "").strip():
        return False
    try:
        statements = sqlglot.parse(sql_text, read="doris")
    except sqlglot.errors.SqlglotError:
        return False
    selects = [
        query
        for statement in statements
        for query in statement.find_all(exp.Select)
    ]
    if len(selects) != 1:
        return False
    query = selects[0]
    if any(
        query.args.get(key) is not None
        for key in (
            "where",
            "having",
            "qualify",
            "distinct",
            "group",
            "limit",
            "offset",
        )
    ):
        return False
    from_clause = query.args.get("from") or query.args.get("from_")
    source = getattr(from_clause, "this", None)
    allowed_table_args = {"this", "db", "catalog", "alias"}
    if (
        not isinstance(source, exp.Table)
        or any(
            value is not None and key not in allowed_table_args
            for key, value in source.args.items()
        )
        or query.args.get("laterals")
    ):
        return False
    return not any(
        query.find(node_type) is not None
        for node_type in (
            exp.AggFunc,
            exp.Join,
            exp.Lateral,
            exp.Pivot,
            exp.TableSample,
            exp.Unnest,
            exp.Window,
        )
    )


def _single_primary_entity(
    result: TableInspectResult,
) -> dict[str, Any] | None:
    primary = [
        entity
        for entity in result.entities
        if isinstance(entity, dict)
        and str(entity.get("type") or "").casefold() == "primary"
    ]
    return primary[0] if len(primary) == 1 else None


def _catalog_code_lookup(
    catalog: dict[str, Any] | None,
    section: str,
) -> dict[str, str]:
    entries = (
        (catalog or {}).get(section) or [] if isinstance(catalog, dict) else []
    )
    return {
        str(entry.get("code") or "").strip().casefold(): str(
            entry.get("code") or ""
        ).strip()
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("code") or "").strip()
    }


def _preferred_equivalent_code(
    source_code: str,
    target_code: str,
    established_codes: dict[str, str],
) -> str:
    candidates = {
        str(code or "").strip().casefold(): str(code or "").strip()
        for code in (source_code, target_code)
        if str(code or "").strip()
    }
    established = {
        canonical: established_codes[canonical]
        for canonical in candidates
        if canonical in established_codes
    }
    if len(established) > 1:
        return ""
    if established:
        return next(iter(established.values()))
    return str(source_code or "").strip()


def _set_result_business_process(
    result: TableInspectResult,
    process: str,
) -> bool:
    process = str(process or "").strip()
    if not process:
        return False
    changed = result.business_process != process
    result.business_process = process
    for group_name in (
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
    ):
        for metric in result.columns.get(group_name) or []:
            if not isinstance(metric, dict):
                continue
            if metric.get("business_process") != process:
                metric["business_process"] = process
                changed = True
    if changed:
        result.resume_eligible = False
        result.validation = {
            key: values
            for key, values in (result.validation or {}).items()
            if key
            not in {
                "business_process_missing",
                "business_process_ambiguous",
            }
        }
    return changed


def _reconcile_dimension_entity_codes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None,
) -> None:
    entries = _dimension_primary_entities(results, contexts)
    if len(entries) < 2:
        return
    established_codes = _catalog_code_lookup(catalog, "semantic_subjects")
    adjacency: dict[int, set[int]] = {
        index: set() for index in range(len(entries))
    }
    incoming: dict[int, set[int]] = {
        index: set() for index in range(len(entries))
    }
    for target_index, (
        target_table,
        target_context,
        target_primary,
    ) in enumerate(entries):
        for source_index, (
            source_table,
            source_context,
            source_primary,
        ) in enumerate(entries):
            if (
                source_index == target_index
                or not _dimension_key_lineage_matches(
                    target_table,
                    target_context,
                    target_primary,
                    source_table,
                    source_context,
                    source_primary,
                )
            ):
                continue
            adjacency[target_index].add(source_index)
            adjacency[source_index].add(target_index)
            incoming[target_index].add(source_index)

    unseen = set(adjacency)
    while unseen:
        seed = min(unseen)
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency[current] - component:
                component.add(neighbor)
                frontier.append(neighbor)
        unseen.difference_update(component)
        if len(component) < 2:
            continue
        component_codes = {
            str(entries[index][2].get("code") or "").strip().casefold(): str(
                entries[index][2].get("code") or ""
            ).strip()
            for index in component
            if str(entries[index][2].get("code") or "").strip()
        }
        established = {
            canonical: established_codes[canonical]
            for canonical in component_codes
            if canonical in established_codes
        }
        canonical_code = ""
        if len(established) == 1:
            canonical_code = next(iter(established.values()))
        elif not established:
            roots = [
                index
                for index in component
                if not (incoming[index] & component)
            ]
            root_codes = {
                str(entries[index][2].get("code") or "").strip()
                for index in roots
                if str(entries[index][2].get("code") or "").strip()
            }
            if len(root_codes) == 1:
                canonical_code = next(iter(root_codes))
        if not canonical_code:
            continue
        for index in component:
            table_name = entries[index][0]
            result = _result_for_table_reference(
                results,
                contexts,
                table_name,
            )
            if result is None:
                continue
            primary_indexes = [
                entity_index
                for entity_index, entity in enumerate(result.entities)
                if isinstance(entity, dict)
                and str(entity.get("type") or "").casefold() == "primary"
            ]
            if len(primary_indexes) != 1:
                continue
            primary_index = primary_indexes[0]
            if (
                str(
                    result.entities[primary_index].get("code") or ""
                ).casefold()
                != canonical_code.casefold()
            ):
                _apply_entity_code_replacements(
                    result,
                    {primary_index: canonical_code},
                )


def _dimension_key_lineage_matches(
    target_table: str,
    target_context: TableContext,
    target_primary: dict[str, Any],
    source_table: str,
    source_context: TableContext,
    source_primary: dict[str, Any],
) -> bool:
    upstream_matches = [
        upstream
        for upstream in target_context.upstream_tables or []
        if _table_reference_matches(upstream, source_table, source_context)
    ]
    if len(upstream_matches) != 1:
        return False
    target_keys = {
        key.casefold()
        for key in _as_string_list(target_primary.get("key_columns"))
    }
    source_keys = {
        key.casefold()
        for key in _as_string_list(source_primary.get("key_columns"))
    }
    if not target_keys or not source_keys:
        return False
    matched_targets = set()
    for edge in target_context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        edge_source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        edge_target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if (
            source_column in source_keys
            and target_column in target_keys
            and _table_reference_matches(
                edge_source_table,
                source_table,
                source_context,
            )
            and _table_reference_matches(
                edge_target_table,
                target_table,
                target_context,
            )
        ):
            matched_targets.add(target_column)
    return matched_targets == target_keys


def _reconcile_entity_codes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> None:
    dimension_entities = _dimension_primary_entities(results, contexts)
    if not dimension_entities:
        return
    for result in results:
        if result.table_type == "dimension" or not result.entities:
            continue
        context = _context_for_table(contexts, result.table_name)
        proposals: dict[int, str] = {}
        for index, entity in enumerate(result.entities):
            if str(entity.get("type") or "").casefold() != "foreign":
                continue
            code = _canonical_entity_code_for_keys(
                result,
                context,
                entity,
                dimension_entities,
            )
            if (
                code
                and code.casefold() != str(entity.get("code") or "").casefold()
            ):
                proposals[index] = code
        proposed_counts: dict[str, int] = {}
        for code in proposals.values():
            canonical = code.casefold()
            proposed_counts[canonical] = proposed_counts.get(canonical, 0) + 1
        existing_codes = {
            str(entity.get("code") or "").casefold()
            for entity in result.entities
            if str(entity.get("code") or "").strip()
        }
        replacements = {
            index: code
            for index, code in proposals.items()
            if proposed_counts.get(code.casefold()) == 1
            and code.casefold() not in existing_codes
        }
        if replacements:
            _apply_entity_code_replacements(result, replacements)


def _dimension_primary_entities(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[tuple[str, TableContext, dict[str, Any]]]:
    entries = []
    for result in results:
        if result.table_type != "dimension" or result.status == "blocked":
            continue
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        primary = [
            entity
            for entity in result.entities
            if isinstance(entity, dict)
            and str(entity.get("type") or "").casefold() == "primary"
        ]
        if len(primary) == 1:
            entries.append((result.table_name, context, primary[0]))
    return entries


def _dimension_key_code_index(
    entries: list[tuple[str, TableContext, dict[str, Any]]],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for _table_name, _context, entity in entries:
        code = str(entity.get("code") or "").strip()
        for key_column in _as_string_list(entity.get("key_columns")):
            key = key_column.casefold()
            if key not in {"id", "key", "code"}:
                index.setdefault(key, set()).add(code)
    return index


def _canonical_entity_code_for_keys(
    result: TableInspectResult,
    context: TableContext | None,
    entity: dict[str, Any],
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> str:
    key_columns = _as_string_list(entity.get("key_columns"))
    if not key_columns:
        return ""
    lineage_codes = _entity_codes_from_direct_lineage(
        result,
        context,
        key_columns,
        dimension_entities,
    )
    if len(lineage_codes) == 1:
        return next(iter(lineage_codes))
    reachable_dimension_entities = _direct_upstream_dimension_entities(
        context,
        dimension_entities,
    )
    key_code_index = _dimension_key_code_index(reachable_dimension_entities)
    key_code_sets = [
        key_code_index.get(key_column.casefold(), set())
        for key_column in key_columns
    ]
    if any(len(codes) != 1 for codes in key_code_sets):
        return ""
    key_codes = {next(iter(codes)) for codes in key_code_sets}
    return next(iter(key_codes)) if len(key_codes) == 1 else ""


def _direct_upstream_dimension_entities(
    context: TableContext | None,
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> list[tuple[str, TableContext, dict[str, Any]]]:
    if context is None:
        return []
    reachable = []
    for table_name, dimension_context, primary in dimension_entities:
        matches = [
            upstream_table
            for upstream_table in context.upstream_tables or []
            if _table_reference_matches(
                upstream_table,
                table_name,
                dimension_context,
            )
        ]
        if len(matches) == 1:
            reachable.append((table_name, dimension_context, primary))
    return reachable


def _entity_codes_from_direct_lineage(
    result: TableInspectResult,
    context: TableContext | None,
    key_columns: list[str],
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> set[str]:
    if context is None:
        return set()
    codes_by_key: list[set[str]] = []
    for key_column in key_columns:
        matching_codes = set()
        for edge in context.column_lineage or []:
            if not isinstance(edge, dict):
                continue
            source_table, source_column = _split_column_reference(
                edge.get("source")
            )
            target_table, target_column = _split_column_reference(
                edge.get("target")
            )
            if (
                target_column != key_column.casefold()
                or not _table_reference_matches(
                    target_table,
                    result.table_name,
                    context,
                )
            ):
                continue
            for (
                dimension_table,
                dimension_context,
                primary,
            ) in dimension_entities:
                dimension_keys = {
                    key.casefold()
                    for key in _as_string_list(primary.get("key_columns"))
                }
                if (
                    source_column in dimension_keys
                    and _table_reference_matches(
                        source_table,
                        dimension_table,
                        dimension_context,
                    )
                ):
                    matching_codes.add(str(primary.get("code") or "").strip())
        if matching_codes:
            codes_by_key.append(matching_codes)
    if len(codes_by_key) != len(key_columns):
        return set()
    common_codes = set(codes_by_key[0])
    for codes in codes_by_key[1:]:
        common_codes.intersection_update(codes)
    return common_codes


def _apply_entity_code_replacements(
    result: TableInspectResult,
    replacements: dict[int, str],
) -> None:
    safe_replacements = {}
    for index, new_code in replacements.items():
        canonical_new = str(new_code or "").strip().casefold()
        conflicts = []
        for other_index, entity in enumerate(result.entities):
            if other_index == index:
                continue
            effective_code = replacements.get(
                other_index,
                str(entity.get("code") or "").strip(),
            )
            if str(effective_code or "").strip().casefold() == canonical_new:
                conflicts.append(other_index)
        if conflicts:
            message = (
                "semantic_reconciliation_skipped: canonical entity code "
                f"{new_code} already exists in {result.table_name}"
            )
            if message not in result.reasoning_steps:
                result.reasoning_steps.append(message)
            continue
        safe_replacements[index] = new_code
    if not safe_replacements:
        return
    result.resume_eligible = False
    old_to_new = {
        str(result.entities[index].get("code") or "").strip().casefold(): code
        for index, code in safe_replacements.items()
    }
    entities = []
    for index, entity in enumerate(result.entities):
        item = dict(entity)
        if index in safe_replacements:
            new_code = safe_replacements[index]
            item["code"] = new_code
        relationship = item.get("relationship")
        if isinstance(relationship, dict):
            relationship = dict(relationship)
            from_entity = str(relationship.get("from_entity") or "").casefold()
            if from_entity in old_to_new:
                relationship["from_entity"] = old_to_new[from_entity]
            item["relationship"] = relationship
        entities.append(item)
    result.entities = normalize_entities(entities)
    result.entity = legacy_entity_from_entities(result.entities)
    result.related_entities = legacy_related_entities_from_entities(
        result.entities
    )
    grain = dict(result.grain or {})
    grain["entities"] = [
        old_to_new.get(str(code).casefold(), code)
        for code in grain.get("entities") or []
    ]
    result.grain = grain


def _result_for_table_reference(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    reference: str,
) -> TableInspectResult | None:
    matches = []
    for result in results:
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        if _table_reference_matches(reference, result.table_name, context):
            matches.append(result)
    return matches[0] if len(matches) == 1 else None


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
