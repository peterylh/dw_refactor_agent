#!/usr/bin/env python3
"""
数据集市中间层评估工具
评估 DWD/DWS 层的复用度、链路长度(中间层)、架构合理性、模型元数据健康度、命名规范。

用法:
    python assess/assess_middle_layer.py
    python assess/assess_middle_layer.py --project finance_analytics
    python assess/assess_middle_layer.py --output report.json
    python assess/assess_middle_layer.py --reuse-weight 0.3
    python assess/assess_middle_layer.py --reuse-weight 0.3 --depth-weight 0.2
    python assess/assess_middle_layer.py --include-passed-checks
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.llm.context_builder import build_contexts
from assess.llm.table_inspector import TableInspector
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.scoring.architecture import score_architecture_health
from assess.scoring.asset_completeness import score_asset_completeness
from assess.scoring.config import *  # re-export scoring constants/rules
from assess.scoring.depth import score_lineage_depth
from assess.scoring.metadata_health import score_metadata_health
from assess.scoring.naming import score_naming_conventions
from assess.scoring.reuse import score_reusability
from assess.scoring.task_sql_quality import score_code_quality
from lineage.table_graph import (
    _table_from_node,
    build_table_graph,
    build_table_layer_map,
    load_lineage_data,
)
from assess.report import generate_report
from config import PROJECT_CONFIG, PROJECT_ROOT


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
            check for check in dimension.get("checks", [])
            if check.get("id") in issue_check_ids
        ]
        filtered[name] = compact_dimension
    return filtered


def assess(
    project: str,
    weights: dict = None,
    *,
    include_passed_checks: bool = False,
) -> dict:
    weights = normalize_score_weights(weights)

    from config import (
        get_business_domain_config,
        get_naming_config,
        load_model_metadata,
    )
    nc = get_naming_config(project)
    model_metadata = load_model_metadata(project)
    business_domain_config = get_business_domain_config(project)

    data = load_lineage_data(project)
    edges = data.get("edges", [])
    indirect_edges = data.get("indirect_edges", [])
    tables = data.get("tables", [])

    llm_results = []
    if weights.get("enable_llm", False):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            print("正在调用 DeepSeek API 进行表分类，请稍候...")
            contexts = build_contexts(project, data)
            cache_file = Path(__file__).resolve(
            ).parent / "cache" / f"inspect_{project}.json"
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

    _, downstream = build_table_graph(edges, indirect_edges)

    reuse_score = score_reusability(tables, downstream)
    depth_score = score_lineage_depth(tables, edges, indirect_edges)
    architecture_score = score_architecture_health(
        tables,
        edges,
        indirect_edges,
        llm_results,
        model_metadata,
        business_domain_config,
    )
    project_dir = PROJECT_ROOT / PROJECT_CONFIG[project]["dir"]
    asset_catalog = build_asset_catalog(
        tables,
        model_metadata,
        project_dir,
        edges=edges,
        indirect_edges=indirect_edges,
    )
    asset_completeness_score = score_asset_completeness(asset_catalog)
    code_quality_score = score_code_quality(asset_catalog)
    metadata_health_score = score_metadata_health(
        tables,
        nc,
        model_metadata,
        business_domain_config,
        asset_catalog=asset_catalog,
    )
    naming_score = score_naming_conventions(
        tables,
        nc,
        model_metadata,
        business_domain_config,
        project_dir=project_dir,
        edges=edges,
        indirect_edges=indirect_edges,
        asset_catalog=asset_catalog,
    )

    dimensions = dict(
        reuse=reuse_score,
        depth=depth_score,
        architecture=architecture_score,
        naming=naming_score,
        asset_completeness=asset_completeness_score,
        metadata_health=metadata_health_score,
        code_quality=code_quality_score,
    )
    overall_score = round(
        sum(
            weights[key] * dimensions[key]["score"]
            for key in [
                "reuse",
                "depth",
                "architecture",
                "naming",
                "asset_completeness",
                "metadata_health",
                "code_quality",
            ]
        ),
        1,
    )
    output_dimensions = _filter_dimension_checks(
        dimensions,
        include_passed_checks=include_passed_checks,
    )

    return dict(
        project=project,
        overall_score=overall_score,
        weights=weights,
        dimensions=output_dimensions,
    )


def main():
    parser = argparse.ArgumentParser(
        description="数据集市中间层评估工具 (评分权重支持单独指定，最终自动归一化)")
    parser.add_argument("--project",
                        default="shop",
                        choices=["shop", "finance_analytics"],
                        help="项目名称 (shop / finance_analytics)")
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 assess/assess_result_{project}.json)")
    parser.add_argument("--reuse-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["reuse"],
                        help="复用度权重，可单独指定，最终会自动归一化")
    parser.add_argument("--depth-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["depth"],
                        help="链路长度权重，可单独指定，最终会自动归一化")
    parser.add_argument("--architecture-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["architecture"],
                        help="架构合理性权重，可单独指定，最终会自动归一化")
    parser.add_argument("--metadata-health-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["metadata_health"],
                        help="元数据健康度权重，可单独指定，最终会自动归一化")
    parser.add_argument("--naming-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["naming"],
                        help="命名规范权重，可单独指定，最终会自动归一化")
    parser.add_argument("--asset-completeness-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["asset_completeness"],
                        help="资产完整性权重，可单独指定，最终会自动归一化")
    parser.add_argument("--code-quality-weight",
                        type=float,
                        default=DEFAULT_WEIGHTS["code_quality"],
                        help="代码质量权重，可单独指定，最终会自动归一化")
    parser.add_argument("--llm",
                        action="store_true",
                        help="调用 DeepSeek API 进行 LLM 智能分层检测")
    parser.add_argument("--no-cache",
                        action="store_true",
                        help="禁用 LLM 缓存，强制重新调用 API")
    parser.add_argument("--parallel",
                        type=int,
                        default=2,
                        help="LLM 并发调用数，默认 2")
    parser.add_argument(
        "--include-passed-checks",
        action="store_true",
        help="输出通过检查项的完整 checks 证据；默认只输出 issue 关联的失败 checks")
    args = parser.parse_args()

    weights = dict(
        reuse=args.reuse_weight,
        depth=args.depth_weight,
        architecture=args.architecture_weight,
        naming=args.naming_weight,
        asset_completeness=args.asset_completeness_weight,
        metadata_health=args.metadata_health_weight,
        code_quality=args.code_quality_weight,
        enable_llm=args.llm,
        no_cache=args.no_cache,
        parallel=args.parallel,
    )

    result = assess(
        args.project,
        weights,
        include_passed_checks=args.include_passed_checks,
    )

    print(generate_report(result, result["weights"], args.project))

    output_path = args.output
    if not output_path:
        output_path = str(
            Path(__file__).resolve().parent /
            f"assess_result_{args.project}.json")

    with open(output_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入: {output_path}")


if __name__ == "__main__":
    main()
