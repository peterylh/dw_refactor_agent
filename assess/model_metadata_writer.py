#!/usr/bin/env python3
"""
LLM 表巡检与模型元数据回写工具。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块以及 DWD/DWS 表中的指标字段回写到
models/{table}.yaml，并把 DWD 事实表的非原子指标输出为违规项。
"""

import argparse
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import yaml

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.assess_middle_layer import load_lineage_data
from assess.context_builder import TableContext, build_contexts
from assess.table_inspector import (
    TableInspectResult,
    TableInspector,
    result_to_dict as inspect_result_to_dict,
)
from config import PROJECT_CONFIG, PROJECT_ROOT, get_business_domain_config


METRIC_LAYERS = {"DWD", "DWS"}
WRITABLE_METADATA_LAYERS = {"DWD", "DWS", "DIM"}
WRITE_SCOPES = {"all", "table", "metrics"}
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}


def build_inspection_contexts(project: str,
                              lineage_data: dict[str, Any]) -> list[TableContext]:
    """构建需要 LLM 巡检并回写模型元数据的表上下文。"""
    return [
        ctx for ctx in build_contexts(project, lineage_data)
        if ctx.layer in WRITABLE_METADATA_LAYERS
    ]


def build_dwd_contexts(project: str,
                       lineage_data: dict[str, Any]) -> list[TableContext]:
    """构建项目 DWD 层表的识别上下文。"""
    return [
        ctx for ctx in build_contexts(project, lineage_data)
        if ctx.layer == "DWD"
    ]


def build_metric_contexts(project: str,
                          lineage_data: dict[str, Any]) -> list[TableContext]:
    """构建项目指标识别上下文，覆盖 DWD 与 DWS。"""
    return [
        ctx for ctx in build_contexts(project, lineage_data)
        if ctx.layer in METRIC_LAYERS
    ]


def model_path_for_table(project: str, table_name: str) -> Path:
    """返回模型 YAML 路径。"""
    project_cfg = PROJECT_CONFIG[project]
    return PROJECT_ROOT / project_cfg["dir"] / "models" / f"{table_name}.yaml"


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
            violations.append({
                "table": result.table_name,
                "column": metric["name"],
                "metric_type": metric_type,
                "reason": metric.get("reason", ""),
                "confidence": metric.get("confidence", 0.0),
            })
    return violations


def metric_names_for_model(result: TableInspectResult) -> list[str]:
    """生成写入 models YAML 的指标名列表。"""
    groups = metric_groups_for_model(result)
    names = []
    for metric in (
        groups["atomic_metrics"]
        + groups["derived_metrics"]
        + groups["calculated_metrics"]
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


def metric_groups_for_model(result: TableInspectResult) -> dict[str, list[str]]:
    """生成写入 models YAML 的分类指标名列表。"""
    return {
        "atomic_metrics": _metric_names(result.atomic_metrics),
        "derived_metrics": _metric_names(result.derived_metrics),
        "calculated_metrics": _metric_names(result.calculated_metrics),
    }


def _merge_detected_upstream_metric_groups(
        contexts: list[TableContext],
        detected_groups: dict[str, dict[str, list[str]]]) -> None:
    """将本轮已识别的上游指标分组注入下游上下文。"""
    for ctx in contexts:
        upstream_metric_groups = dict(ctx.upstream_metric_groups)
        for upstream_table in ctx.upstream_tables:
            groups = detected_groups.get(upstream_table)
            if groups and any(groups.values()):
                upstream_metric_groups[upstream_table] = groups
        ctx.upstream_metric_groups = upstream_metric_groups


def _update_models_for_results(project: str,
                               results: list[TableInspectResult],
                               *,
                               dry_run: bool,
                               write_scope: str) -> tuple[list[dict[str, Any]],
                                                          list[dict[str, Any]]]:
    write_scope = _validate_write_scope(write_scope)
    yaml_updates = []
    skipped_updates = []
    for result in results:
        if result.status == "blocked":
            skipped_updates.append({
                "table": result.table_name,
                "path": str(model_path_for_table(project, result.table_name)),
                "status": result.status,
                "validation": result.validation,
                "updated": False,
                "reason": "validation_blocked",
                "write_scope": write_scope,
            })
            continue
        update = update_model_yaml(project,
                                   result,
                                   dry_run=dry_run,
                                   write_scope=write_scope)
        if update["changed"]:
            yaml_updates.append(update)
    return yaml_updates, skipped_updates


def _violation_count(results: list[TableInspectResult],
                     metric_attr: str | None = None) -> int:
    """统计 DWD fact 中的非原子指标违规数量。"""
    count = 0
    for result in results:
        if result.declared_layer != "DWD" or not result.is_fact_table:
            continue
        if metric_attr:
            count += len(getattr(result, metric_attr))
        else:
            count += len(result.derived_metrics) + len(result.calculated_metrics)
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
        model_data: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "atomic_metrics": _metric_names_from_raw(
            model_data.get("atomic_metrics")),
        "derived_metrics": _metric_names_from_raw(
            model_data.get("derived_metrics")),
        "calculated_metrics": _metric_names_from_raw(
            model_data.get("calculated_metrics")),
    }


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
        result: TableInspectResult) -> list[dict[str, Any]]:
    """返回模型元数据回写层面的警告。"""
    if result.table_type != "dimension":
        return []
    inferred = str(result.inferred_layer or "").strip().upper()
    if inferred in ("", "DIM"):
        return []
    return [{
        "type": "dimension_layer_override",
        "severity": "warning",
        "message": (
            "LLM 表类型为 dimension，但 inferred_layer 不是 DIM；"
            "表信息回写时 layer 会按 dimension 规则强制写为 DIM"
        ),
        "inferred_layer": inferred,
        "applied_layer": "DIM",
    }]


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
        result.inferred_business_area)
    if (
        applied_layer in DATA_DOMAIN_LAYERS
        and business_config.is_valid_domain(data_domain)
    ):
        metadata["data_domain"] = data_domain
    if (
        applied_layer in BUSINESS_AREA_LAYERS
        and business_config.is_valid_business_area(business_area)
    ):
        metadata["business_area"] = business_area
    return metadata


def should_write_metric_groups(result: TableInspectResult,
                               write_scope: str = "all") -> bool:
    """判断是否需要按指标分组更新模型 YAML。"""
    if _validate_write_scope(write_scope) not in {"all", "metrics"}:
        return False
    return (
        result.declared_layer in METRIC_LAYERS
        or result.inferred_layer in METRIC_LAYERS
    )


def update_model_yaml(project: str,
                      result: TableInspectResult,
                      *,
                      dry_run: bool = False,
                      write_scope: str = "all") -> dict[str, Any]:
    """将单表 LLM 巡检元数据和指标名覆盖写入 models/{table}.yaml。"""
    write_scope = _validate_write_scope(write_scope)
    path = model_path_for_table(project, result.table_name)
    if result.status == "blocked":
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
            "updated": False,
            "reason": "validation_blocked",
            "warnings": [],
            "write_scope": write_scope,
        }

    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(existing, dict):
        existing = {}

    existing_metrics = _extract_existing_metric_names(existing)
    existing_groups = _extract_existing_metric_groups(existing)
    detected_groups = metric_groups_for_model(result)
    write_table_metadata = should_write_table_metadata(write_scope)
    write_metric_groups = should_write_metric_groups(result, write_scope)
    detected_metrics = (
        metric_names_for_model(result) if write_metric_groups else []
    )

    updated = dict(existing)
    previous_layer = existing.get("layer")
    previous_table_type = existing.get("table_type")
    previous_data_domain = existing.get("data_domain")
    previous_business_area = existing.get("business_area")
    has_existing_metric_fields = any(
        key in existing for key in (
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
                        "business_area"]
            else:
                updated.pop("business_area", None)

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
                "calculated_metrics"]
        else:
            updated.pop("calculated_metrics", None)
        updated.pop("metrics", None)
    elif write_metric_groups:
        updated.pop("metrics", None)
        updated.pop("atomic_metrics", None)
        updated.pop("derived_metrics", None)
        updated.pop("calculated_metrics", None)

    changed = updated != existing
    metadata_changed = write_table_metadata and (
        updated.get("layer") != previous_layer
        or updated.get("table_type") != previous_table_type
        or updated.get("data_domain") != previous_data_domain
        or updated.get("business_area") != previous_business_area
    )
    metric_changed = write_metric_groups and (
        has_existing_metric_fields
        or detected_groups != existing_groups
    )
    if not dry_run and changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(updated,
                           allow_unicode=True,
                           sort_keys=False),
            encoding="utf-8",
        )

    new_metric_count = 0
    removed_metric_count = 0
    if write_metric_groups:
        new_metric_count = len(
            [name for name in detected_metrics if name not in existing_metrics])
        removed_metric_count = len(
            [name for name in existing_metrics if name not in detected_metrics])

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
        "warnings": metadata_warnings_for_result(result),
        "write_scope": write_scope,
        "metric_count": len(detected_metrics),
        "new_metric_count": new_metric_count,
        "removed_metric_count": removed_metric_count,
        "updated": bool(changed and not dry_run),
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


def run_metadata_write(project: str,
                       *,
                       api_key: str,
                       model: str = "deepseek-v4-flash",
                       max_retries: int = 1,
                       parallelism: int = 2,
                       no_cache: bool = False,
                       dry_run: bool = False,
                       write_scope: str = "all",
                       show_progress: bool = False) -> dict[str, Any]:
    """运行项目级 LLM 巡检与模型元数据回写。"""
    write_scope = _validate_write_scope(write_scope)
    data = load_lineage_data(project)
    contexts = build_inspection_contexts(project, data)
    metric_contexts = [ctx for ctx in contexts if ctx.layer in METRIC_LAYERS]
    dwd_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWD"]
    dws_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWS"]
    metadata_only_contexts = [
        ctx for ctx in contexts
        if ctx.layer not in METRIC_LAYERS
    ]
    cache_file = Path(__file__).resolve(
    ).parent / "cache" / f"inspect_{project}.json"
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
    yaml_updates, skipped_updates = _update_models_for_results(
        project, dwd_results, dry_run=dry_run, write_scope=write_scope)

    detected_groups = {
        result.table_name: metric_groups_for_model(result)
        for result in dwd_results
        if result.status != "blocked"
    }
    _merge_detected_upstream_metric_groups(dws_contexts, detected_groups)
    dws_results = inspector.inspect_batch(dws_contexts)
    dws_updates, dws_skipped_updates = _update_models_for_results(
        project, dws_results, dry_run=dry_run, write_scope=write_scope)
    yaml_updates.extend(dws_updates)
    skipped_updates.extend(dws_skipped_updates)

    metadata_only_results = inspector.inspect_batch(metadata_only_contexts)
    metadata_only_updates, metadata_only_skipped_updates = (
        _update_models_for_results(project,
                                   metadata_only_results,
                                   dry_run=dry_run,
                                   write_scope=write_scope)
    )
    yaml_updates.extend(metadata_only_updates)
    skipped_updates.extend(metadata_only_skipped_updates)

    results = dwd_results + dws_results + metadata_only_results

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
            1 for r in results
            if r.status == "warning" or metadata_warnings_for_result(r)),
        "blocked_table_count": sum(1 for r in results if r.status == "blocked"),
        "atomic_metric_count": sum(len(r.atomic_metrics) for r in results),
        "derived_metric_count": sum(len(r.derived_metrics) for r in results),
        "calculated_metric_count": sum(
            len(r.calculated_metrics) for r in results),
        "metric_count": sum(len(metric_names_for_model(r)) for r in results),
        "derived_metric_violation_count": _violation_count(
            results, "derived_metrics"),
        "calculated_metric_violation_count": _violation_count(
            results, "calculated_metrics"),
        "non_atomic_metric_violation_count": _violation_count(results),
        "metadata_warning_count": sum(
            len(metadata_warnings_for_result(r)) for r in results),
        "tables": [result_for_report(r) for r in results],
        "model_updates": yaml_updates,
        "model_update_count": len([
            update for update in yaml_updates
            if update.get("updated")
        ]),
        "model_change_count": len(yaml_updates),
        "skipped_model_updates": skipped_updates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 表巡检与模型元数据回写工具")
    parser.add_argument("--project",
                        default="shop",
                        choices=list(PROJECT_CONFIG.keys()),
                        help="项目名称")
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 assess/model_metadata_result_{project}.json)")
    parser.add_argument("--model",
                        default="deepseek-v4-flash",
                        help="DeepSeek 模型名称")
    parser.add_argument("--max-retries",
                        type=int,
                        default=1,
                        help="LLM 返回校验失败时的最大重试次数")
    parser.add_argument("--dry-run",
                        action="store_true",
                        help="只输出巡检结果，不写入 models YAML")
    parser.add_argument("--write-scope",
                        choices=sorted(WRITE_SCOPES),
                        default="all",
                        help=(
                            "models 回写范围: all=表信息+指标, "
                            "table=仅表级元数据, metrics=仅指标分组"
                        ))
    parser.add_argument("--no-cache",
                        action="store_true",
                        help="忽略本地缓存，强制重新调用 API")
    parser.add_argument("--parallel",
                        type=int,
                        default=2,
                        help="LLM 并发调用数，默认 2")
    parser.add_argument("--quiet",
                        action="store_true",
                        help="不打印单表巡检进度")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API")

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

    output_path = Path(args.output) if args.output else (
        Path(__file__).resolve().parent /
        f"model_metadata_result_{args.project}.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"结果已写入: {output_path}")
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
            **result))


if __name__ == "__main__":
    main()
