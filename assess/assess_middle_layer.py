#!/usr/bin/env python3
"""
数据集市中间层评估工具
评估 DWD/DWS 层的复用度、链路长度(中间层)、模型设计、模型元数据健康度、命名规范。

用法:
    python assess/assess_middle_layer.py
    python assess/assess_middle_layer.py --project finance_analytics
    python assess/assess_middle_layer.py --output report.json
    python assess/assess_middle_layer.py --reuse-weight 0.3
    python assess/assess_middle_layer.py --reuse-weight 0.3 --depth-weight 0.2
    python assess/assess_middle_layer.py --include-passed-checks
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.assessment_context import AssessmentContext
from assess.llm.context_builder import build_contexts
from assess.llm.table_inspector import TableInspector
from assess.report import generate_report
from assess.rules import RuleSelection, rule_specs_by_id
from assess.rules.dimensions.asset_completeness import (
    score_asset_completeness,
)
from assess.rules.dimensions.depth import score_lineage_depth
from assess.rules.dimensions.metadata_health import score_metadata_health
from assess.rules.dimensions.model_design import score_model_design_health
from assess.rules.dimensions.naming import score_naming_conventions
from assess.rules.dimensions.reuse import score_reusability
from assess.rules.dimensions.task_sql_quality import score_code_quality
from assess.scoring.config import DEFAULT_WEIGHTS, normalize_score_weights
from config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,
    assess_cache_path,
    assess_result_path,
)
from lineage.table_graph import load_lineage_data

DEFAULT_DIMENSION_ORDER = [
    "reuse",
    "depth",
    "model_design",
    "naming",
    "asset_completeness",
    "metadata_health",
    "code_quality",
]


def normalize_selected_dimensions(
    selected_dimensions: set[str] | list[str] | tuple[str, ...] | None,
) -> set[str] | None:
    if not selected_dimensions:
        return None

    selected = set(selected_dimensions)
    unknown = sorted(set(selected) - set(DEFAULT_DIMENSION_ORDER))
    if unknown:
        raise ValueError(f"未知评估维度: {', '.join(unknown)}")
    return selected


def build_rule_selection(
    *,
    disabled_rules: set[str] | list[str] | tuple[str, ...] | None = None,
    only_rules: set[str] | list[str] | tuple[str, ...] | None = None,
) -> RuleSelection:
    disabled = set(disabled_rules or [])
    only = set(only_rules or [])
    known_rules = set(rule_specs_by_id())
    unknown = sorted((disabled | only) - known_rules)
    if unknown:
        raise ValueError(f"未知评估规则: {', '.join(unknown)}")
    return RuleSelection(disabled=disabled, only=only)


def _filter_dimension_checks(
    dimensions: dict,
    *,
    include_passed_checks: bool,
) -> dict:
    if include_passed_checks:
        return dimensions

    filtered = {}
    for name, dimension in dimensions.items():
        issue_check_ids = {
            check_id
            for issue in dimension.get("issues", [])
            for check_id in issue.get("check_ids", [])
        }
        compact_dimension = dict(dimension)
        compact_dimension["checks"] = [
            check
            for check in dimension.get("checks", [])
            if check.get("id") in issue_check_ids
        ]
        filtered[name] = compact_dimension
    return filtered


def assess(
    project: str,
    weights: dict = None,
    *,
    include_passed_checks: bool = False,
    selected_dimensions: set[str] | list[str] | tuple[str, ...] | None = None,
    disabled_rules: set[str] | list[str] | tuple[str, ...] | None = None,
    only_rules: set[str] | list[str] | tuple[str, ...] | None = None,
    lineage_data: dict | None = None,
    scope: dict | None = None,
) -> dict:
    weights = normalize_score_weights(weights)
    selected_dimensions = normalize_selected_dimensions(selected_dimensions)
    rule_selection = build_rule_selection(
        disabled_rules=disabled_rules,
        only_rules=only_rules,
    )

    from config import (
        get_business_domain_config,
        get_naming_config,
        load_model_metadata,
    )

    nc = get_naming_config(project)
    model_metadata = load_model_metadata(project)
    business_domain_config = get_business_domain_config(project)

    data = lineage_data or load_lineage_data(project)
    llm_results = []
    if weights.get("enable_llm", False):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            print("正在调用 DeepSeek API 进行表分类，请稍候...")
            contexts = build_contexts(project, data)
            cache_file = assess_cache_path(
                project, "middle_layer_inspect.json"
            )
            if weights.get("no_cache", False) and cache_file.exists():
                cache_file.unlink()
            inspector = TableInspector(
                api_key,
                cache_file=cache_file,
                parallelism=weights.get("parallel", 2),
            )
            llm_results = inspector.inspect_batch(contexts)
        else:
            print("警告: 未提供 DEEPSEEK_API_KEY 环境变量，跳过分类。")

    project_dir = PROJECT_ROOT / PROJECT_CONFIG[project]["dir"]
    context = AssessmentContext.from_lineage_data(
        project=project,
        lineage_data=data,
        models=model_metadata,
        project_dir=project_dir,
        business_domain_config=business_domain_config,
        naming_config=nc,
    )

    reuse_score = score_reusability(context, rule_selection=rule_selection)
    depth_score = score_lineage_depth(context, rule_selection=rule_selection)
    model_design_score = score_model_design_health(
        context,
        llm_results,
        rule_selection=rule_selection,
    )
    asset_completeness_score = score_asset_completeness(
        context,
        rule_selection=rule_selection,
    )
    code_quality_score = score_code_quality(
        context,
        rule_selection=rule_selection,
    )
    metadata_health_score = score_metadata_health(
        context,
        rule_selection=rule_selection,
    )
    naming_score = score_naming_conventions(
        context,
        rule_selection=rule_selection,
    )

    dimensions = dict(
        reuse=reuse_score,
        depth=depth_score,
        model_design=model_design_score,
        naming=naming_score,
        asset_completeness=asset_completeness_score,
        metadata_health=metadata_health_score,
        code_quality=code_quality_score,
    )
    dimension_keys = [
        key
        for key in DEFAULT_DIMENSION_ORDER
        if selected_dimensions is None or key in selected_dimensions
    ]
    dimensions = {key: dimensions[key] for key in dimension_keys}
    selected_weight_total = sum(weights[key] for key in dimension_keys)
    overall_score = round(
        sum(weights[key] * dimensions[key]["score"] for key in dimension_keys)
        / selected_weight_total,
        1,
    )
    output_dimensions = _filter_dimension_checks(
        dimensions,
        include_passed_checks=include_passed_checks,
    )

    result = dict(
        project=project,
        overall_score=overall_score,
        weights=weights,
        dimensions=output_dimensions,
    )
    if scope:
        result["scope"] = scope
    return result


def main():
    parser = argparse.ArgumentParser(
        description="数据集市中间层评估工具 (评分权重支持单独指定，最终自动归一化)"
    )
    parser.add_argument(
        "--project",
        default="shop",
        choices=["shop", "finance_analytics"],
        help="项目名称 (shop / finance_analytics)",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 {project}/assess/assess_result.json)",
    )
    parser.add_argument(
        "--reuse-weight",
        type=float,
        default=DEFAULT_WEIGHTS["reuse"],
        help="复用度权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--depth-weight",
        type=float,
        default=DEFAULT_WEIGHTS["depth"],
        help="链路长度权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--model-design-weight",
        type=float,
        default=DEFAULT_WEIGHTS["model_design"],
        help="模型设计权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--metadata-health-weight",
        type=float,
        default=DEFAULT_WEIGHTS["metadata_health"],
        help="元数据健康度权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--naming-weight",
        type=float,
        default=DEFAULT_WEIGHTS["naming"],
        help="命名规范权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--asset-completeness-weight",
        type=float,
        default=DEFAULT_WEIGHTS["asset_completeness"],
        help="资产完整性权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--code-quality-weight",
        type=float,
        default=DEFAULT_WEIGHTS["code_quality"],
        help="代码质量权重，可单独指定，最终会自动归一化",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="调用 DeepSeek API 进行 LLM 智能分层检测",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用 LLM 缓存，强制重新调用 API",
    )
    parser.add_argument(
        "--parallel", type=int, default=2, help="LLM 并发调用数，默认 2"
    )
    parser.add_argument(
        "--include-passed-checks",
        action="store_true",
        help="输出通过检查项的完整 checks 证据；默认只输出 issue 关联的失败 checks",
    )
    parser.add_argument(
        "--disable-rule",
        action="append",
        default=[],
        help="禁用指定规则ID；可重复传入",
    )
    parser.add_argument(
        "--only-rule",
        action="append",
        default=[],
        help="只运行指定规则ID；可重复传入",
    )
    parser.add_argument(
        "--reuse", action="store_true", help="只输出复用度维度"
    )
    parser.add_argument(
        "--depth", action="store_true", help="只输出链路长度维度"
    )
    parser.add_argument(
        "--model-design", action="store_true", help="只输出模型设计维度"
    )
    parser.add_argument(
        "--naming", action="store_true", help="只输出命名规范维度"
    )
    parser.add_argument(
        "--asset-completeness",
        action="store_true",
        help="只输出资产完整性维度",
    )
    parser.add_argument(
        "--metadata-health",
        action="store_true",
        help="只输出模型元数据健康度维度",
    )
    parser.add_argument(
        "--code-quality", action="store_true", help="只输出代码质量维度"
    )
    args = parser.parse_args()

    weights = dict(
        reuse=args.reuse_weight,
        depth=args.depth_weight,
        model_design=args.model_design_weight,
        naming=args.naming_weight,
        asset_completeness=args.asset_completeness_weight,
        metadata_health=args.metadata_health_weight,
        code_quality=args.code_quality_weight,
        enable_llm=args.llm,
        no_cache=args.no_cache,
        parallel=args.parallel,
    )
    selected_dimensions = set()
    for enabled, dimension in [
        (args.reuse, "reuse"),
        (args.depth, "depth"),
        (args.model_design, "model_design"),
        (args.naming, "naming"),
        (args.asset_completeness, "asset_completeness"),
        (args.metadata_health, "metadata_health"),
        (args.code_quality, "code_quality"),
    ]:
        if enabled:
            selected_dimensions.add(dimension)

    result = assess(
        args.project,
        weights,
        include_passed_checks=args.include_passed_checks,
        selected_dimensions=selected_dimensions,
        disabled_rules=args.disable_rule,
        only_rules=args.only_rule,
    )

    print(generate_report(result, result["weights"], args.project))

    output_path = args.output
    if not output_path:
        output_path = str(assess_result_path(args.project))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入: {output_path}")


if __name__ == "__main__":
    main()
