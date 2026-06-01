#!/usr/bin/env python3
"""
DWD 指标提取与模型回写工具。

复用 table_inspector 的单次 DeepSeek 调用结果，将 DWD 表中的
指标字段按 atomic_metrics / derived_metrics 覆盖写入
models/{table}.yaml，并把 DWD 事实表的 derived_metrics 输出为违规项。
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

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
from config import PROJECT_CONFIG, PROJECT_ROOT


def build_dwd_contexts(project: str,
                       lineage_data: dict[str, Any]) -> list[TableContext]:
    """构建项目 DWD 层表的识别上下文。"""
    return [
        ctx for ctx in build_contexts(project, lineage_data)
        if ctx.layer == "DWD"
    ]


def model_path_for_table(project: str, table_name: str) -> Path:
    """返回模型 YAML 路径。"""
    project_cfg = PROJECT_CONFIG[project]
    return PROJECT_ROOT / project_cfg["dir"] / "models" / f"{table_name}.yaml"


def metric_violations(result: TableInspectResult) -> list[dict[str, Any]]:
    """返回 DWD 事实表中的派生指标违规项。"""
    if result.declared_layer != "DWD" or not result.is_fact_table:
        return []
    return [
        {
            "table": result.table_name,
            "column": metric["name"],
            "metric_type": "derived",
            "reason": metric.get("reason", ""),
            "confidence": metric.get("confidence", 0.0),
        }
        for metric in result.derived_metrics
    ]


def metric_names_for_model(result: TableInspectResult) -> list[str]:
    """生成写入 models YAML 的指标名列表。"""
    groups = metric_groups_for_model(result)
    names = []
    for metric in groups["atomic_metrics"] + groups["derived_metrics"]:
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
    }


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
    for key in ("metrics", "atomic_metrics", "derived_metrics"):
        for name in _metric_names_from_raw(model_data.get(key, []) or []):
            if name and name not in names:
                names.append(name)
    return names


def update_model_yaml(project: str,
                      result: TableInspectResult,
                      *,
                      dry_run: bool = False) -> dict[str, Any]:
    """将单表指标名覆盖写入 models/{table}.yaml。"""
    path = model_path_for_table(project, result.table_name)
    path_exists = path.exists()
    existing = {}
    if path_exists:
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(existing, dict):
        existing = {}

    existing_metrics = _extract_existing_metric_names(existing)
    detected_groups = metric_groups_for_model(result)
    detected_metrics = metric_names_for_model(result)

    updated = dict(existing)
    if path_exists or detected_metrics:
        updated.setdefault("version", 2)
        updated.setdefault("name", result.table_name)
        updated.setdefault("layer", "DWD")
    if detected_metrics:
        if detected_groups["atomic_metrics"]:
            updated["atomic_metrics"] = detected_groups["atomic_metrics"]
        else:
            updated.pop("atomic_metrics", None)
        if detected_groups["derived_metrics"]:
            updated["derived_metrics"] = detected_groups["derived_metrics"]
        else:
            updated.pop("derived_metrics", None)
        updated.pop("metrics", None)
    else:
        updated.pop("metrics", None)
        updated.pop("atomic_metrics", None)
        updated.pop("derived_metrics", None)

    changed = updated != existing
    if not dry_run and changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(updated,
                           allow_unicode=True,
                           sort_keys=False),
            encoding="utf-8",
        )

    return {
        "table": result.table_name,
        "path": str(path),
        "status": result.status,
        "metric_count": len(detected_metrics),
        "new_metric_count": len(
            [name for name in detected_metrics if name not in existing_metrics]),
        "removed_metric_count": len(
            [name for name in existing_metrics if name not in detected_metrics]),
        "updated": bool(changed and not dry_run),
    }


def result_for_report(result: TableInspectResult) -> dict[str, Any]:
    """生成指标检测报告中的单表结果。"""
    data = inspect_result_to_dict(result)
    data["violations"] = metric_violations(result)
    return data


def run_detection(project: str,
                  *,
                  api_key: str,
                  model: str = "deepseek-v4-flash",
                  max_retries: int = 1,
                  parallelism: int = 2,
                  no_cache: bool = False,
                  dry_run: bool = False) -> dict[str, Any]:
    """运行项目级 DWD 指标检测。"""
    data = load_lineage_data(project)
    contexts = build_dwd_contexts(project, data)
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
    results = inspector.inspect_batch(contexts)

    yaml_updates = []
    skipped_updates = []
    for result in results:
        if result.declared_layer != "DWD":
            continue
        if result.status == "blocked":
            skipped_updates.append({
                "table": result.table_name,
                "path": str(model_path_for_table(project, result.table_name)),
                "status": result.status,
                "validation": result.validation,
                "updated": False,
                "reason": "validation_blocked",
            })
            continue
        update = update_model_yaml(project, result, dry_run=dry_run)
        if (result.is_fact_table or update["metric_count"] > 0
                or update["removed_metric_count"] > 0):
            yaml_updates.append(update)

    return {
        "project": project,
        "dwd_table_count": len(contexts),
        "fact_table_count": sum(1 for r in results if r.is_fact_table),
        "passed_table_count": sum(1 for r in results if r.status == "passed"),
        "warning_table_count": sum(1 for r in results if r.status == "warning"),
        "blocked_table_count": sum(1 for r in results if r.status == "blocked"),
        "atomic_metric_count": sum(len(r.atomic_metrics) for r in results),
        "metric_count": sum(len(metric_names_for_model(r)) for r in results),
        "derived_metric_violation_count": sum(
            len(metric_violations(r)) for r in results),
        "tables": [result_for_report(r) for r in results],
        "model_updates": yaml_updates,
        "skipped_model_updates": skipped_updates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DWD 指标提取与模型回写工具")
    parser.add_argument("--project",
                        default="shop",
                        choices=list(PROJECT_CONFIG.keys()),
                        help="项目名称")
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 assess/metric_result_{project}.json)")
    parser.add_argument("--model",
                        default="deepseek-v4-flash",
                        help="DeepSeek 模型名称")
    parser.add_argument("--max-retries",
                        type=int,
                        default=1,
                        help="LLM 返回校验失败时的最大重试次数")
    parser.add_argument("--dry-run",
                        action="store_true",
                        help="只输出检测结果，不写入 models YAML")
    parser.add_argument("--no-cache",
                        action="store_true",
                        help="忽略本地缓存，强制重新调用 API")
    parser.add_argument("--parallel",
                        type=int,
                        default=2,
                        help="LLM 并发调用数，默认 2")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API")

    result = run_detection(
        args.project,
        api_key=api_key,
        model=args.model,
        max_retries=args.max_retries,
        parallelism=args.parallel,
        no_cache=args.no_cache,
        dry_run=args.dry_run,
    )

    output_path = Path(args.output) if args.output else (
        Path(__file__).resolve().parent /
        f"metric_result_{args.project}.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"结果已写入: {output_path}")
    print(
        "DWD表: {dwd_table_count}, 事实表: {fact_table_count}, "
        "指标: {metric_count}, 原子指标: {atomic_metric_count}, 派生指标违规: "
        "{derived_metric_violation_count}".format(**result))


if __name__ == "__main__":
    main()
