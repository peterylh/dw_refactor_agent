#!/usr/bin/env python3
"""
数据集市中间层评估工具
评估 DWD/DWS 层的复用度、链路长度(中间层)、模型设计、模型元数据健康度、命名规范。

用法:
    python -m dw_refactor_agent.assessment.assess_middle_layer
    python -m dw_refactor_agent.assessment.assess_middle_layer --project finance_analytics
    python -m dw_refactor_agent.assessment.assess_middle_layer --project shop --refresh-lineage
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 config
_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.llm.context_builder import build_contexts
from dw_refactor_agent.assessment.llm.table_inspector import TableInspector
from dw_refactor_agent.assessment.report import generate_report
from dw_refactor_agent.assessment.result_model import compact_assessment_result
from dw_refactor_agent.assessment.rules import RuleSelection, rule_specs_by_id
from dw_refactor_agent.assessment.rules.dimensions.asset_completeness import (
    score_asset_completeness,
)
from dw_refactor_agent.assessment.rules.dimensions.depth import (
    score_lineage_depth,
)
from dw_refactor_agent.assessment.rules.dimensions.metadata_health import (
    score_metadata_health,
)
from dw_refactor_agent.assessment.rules.dimensions.model_design import (
    score_model_design_health,
)
from dw_refactor_agent.assessment.rules.dimensions.naming import (
    score_naming_conventions,
)
from dw_refactor_agent.assessment.rules.dimensions.reuse import (
    score_reusability,
)
from dw_refactor_agent.assessment.rules.dimensions.task_sql_quality import (
    score_code_quality,
)
from dw_refactor_agent.assessment.scoped_plan import (
    build_scoped_assessment_plan,
    dimension_scope,
    scoped_names,
)
from dw_refactor_agent.assessment.scoring.config import (
    DEFAULT_WEIGHTS,
    normalize_score_weights,
)
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,
    TEXT_ENCODING,
    assess_cache_path,
    assess_result_path,
    lineage_data_path,
    python_module_env,
)
from dw_refactor_agent.lineage.table_graph import load_lineage_data

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


def _sorted_values(values) -> list[str]:
    return sorted(str(value) for value in values if str(value or "").strip())


def _task_name_from_path(task_path: str) -> str:
    name = Path(str(task_path or "")).stem
    if name.endswith("_full_refresh"):
        return name[: -len("_full_refresh")]
    return name


def _task_file_key(task_path: str) -> str:
    return str(task_path or "").replace("\\", "/").strip()


def selected_dimensions_for_rules(only_rules: list[str]) -> set[str]:
    if not only_rules:
        return set()
    specs = rule_specs_by_id()
    unknown = sorted(set(only_rules) - set(specs))
    if unknown:
        raise ValueError(f"未知评估规则: {', '.join(unknown)}")
    return {specs[rule_id].dimension for rule_id in only_rules}


def build_manual_focus_scope_plan(
    *,
    table_names: list[str] | tuple[str, ...] | None = None,
    task_paths: list[str] | tuple[str, ...] | None = None,
) -> dict | None:
    tables = _sorted_values(table_names or [])
    tasks = _sorted_values(
        _task_name_from_path(path) for path in task_paths or []
    )
    task_files = _sorted_values(
        _task_file_key(path) for path in task_paths or []
    )
    if not tables and not tasks:
        return None

    def scoped_dimension(
        *,
        scope_name: str,
        include_tables: bool = False,
        include_tasks: bool = False,
        include_task_files: bool = False,
    ) -> dict:
        result = {
            "mode": "scoped",
            "scope": scope_name,
            "reason": ["manual_focus"],
            "score_semantics": "scope_local",
        }
        if include_tables:
            result["tables"] = tables
        if include_tasks:
            result["tasks"] = tasks
        if include_task_files:
            result["task_files"] = task_files
        return result

    return {
        "mode": "manual_focus",
        "score_semantics": "scope_local",
        "base_scope": {
            "assessment_tables": tables,
            "assessment_tasks": tasks,
        },
        "dimensions": {
            "reuse": scoped_dimension(
                scope_name="tables",
                include_tables=True,
            ),
            "depth": scoped_dimension(
                scope_name="tables",
                include_tables=True,
            ),
            "model_design": scoped_dimension(
                scope_name="tables",
                include_tables=True,
            ),
            "naming": scoped_dimension(
                scope_name="tables_and_tasks",
                include_tables=True,
                include_tasks=True,
            ),
            "asset_completeness": scoped_dimension(
                scope_name="tables_and_tasks",
                include_tables=True,
                include_tasks=True,
            ),
            "metadata_health": scoped_dimension(
                scope_name="tables",
                include_tables=True,
            ),
            "code_quality": scoped_dimension(
                scope_name="tasks",
                include_tasks=True,
                include_task_files=True,
            ),
        },
    }


def complete_manual_focus_scope_plan(
    scope_plan: dict | None,
    context,
) -> dict | None:
    if not scope_plan or scope_plan.get("mode") != "manual_focus":
        return scope_plan

    completed = dict(scope_plan)
    dimensions = {
        name: dict(value)
        for name, value in (scope_plan.get("dimensions") or {}).items()
    }
    model_scope = dimensions.get("model_design") or {}
    table_scope = scoped_names(model_scope, "tables")
    if table_scope is not None and "edges" not in model_scope:
        model_scope["edges"] = [
            {"source": source, "target": target}
            for source, target in sorted(context.table_edges)
            if source in table_scope or target in table_scope
        ]
        dimensions["model_design"] = model_scope
    completed["dimensions"] = dimensions
    return completed


def _has_issues(result: dict) -> bool:
    return any(
        dimension.get("issues")
        for dimension in (result.get("dimensions") or {}).values()
    )


def assess(
    project: str,
    weights: dict = None,
    *,
    selected_dimensions: set[str] | list[str] | tuple[str, ...] | None = None,
    disabled_rules: set[str] | list[str] | tuple[str, ...] | None = None,
    only_rules: set[str] | list[str] | tuple[str, ...] | None = None,
    lineage_data: dict | None = None,
    scope: dict | None = None,
    change_analysis: dict | None = None,
    scope_plan: dict | None = None,
) -> dict:
    weights = normalize_score_weights(weights)
    selected_dimensions = normalize_selected_dimensions(selected_dimensions)
    rule_selection = build_rule_selection(
        disabled_rules=disabled_rules,
        only_rules=only_rules,
    )

    from dw_refactor_agent.config import (
        get_business_domain_config,
        get_naming_config,
        load_model_metadata,
    )

    nc = get_naming_config(project)
    model_metadata = load_model_metadata(project)
    business_domain_config = get_business_domain_config(project)

    data = (
        lineage_data
        if lineage_data is not None
        else load_lineage_data(project)
    )
    project_dir = PROJECT_ROOT / PROJECT_CONFIG[project]["dir"]
    context = AssessmentContext.from_lineage_data(
        project=project,
        lineage_data=data,
        models=model_metadata,
        project_dir=project_dir,
        business_domain_config=business_domain_config,
        naming_config=nc,
    )
    scope_plan = complete_manual_focus_scope_plan(scope_plan, context)
    if scope_plan is None and change_analysis:
        scope_plan = build_scoped_assessment_plan(
            project,
            change_analysis,
            context,
        )

    llm_results = []
    if weights.get("enable_llm", False):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            print("正在调用 DeepSeek API 进行表分类，请稍候...")
            contexts = build_contexts(project, data)
            model_scope = dimension_scope(scope_plan, "model_design")
            scoped_tables = scoped_names(model_scope, "tables")
            if scoped_tables is not None:
                contexts = [
                    item
                    for item in contexts
                    if getattr(item, "table_name", "") in scoped_tables
                ]
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

    reuse_score = score_reusability(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "reuse"),
    )
    depth_score = score_lineage_depth(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "depth"),
    )
    model_design_score = score_model_design_health(
        context,
        llm_results,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "model_design"),
    )
    asset_completeness_score = score_asset_completeness(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "asset_completeness"),
    )
    code_quality_score = score_code_quality(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "code_quality"),
    )
    metadata_health_score = score_metadata_health(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "metadata_health"),
    )
    naming_score = score_naming_conventions(
        context,
        rule_selection=rule_selection,
        scope=dimension_scope(scope_plan, "naming"),
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

    result = dict(
        project=project,
        overall_score=overall_score,
        weights=weights,
        dimensions=dimensions,
    )
    if scope:
        result["scope"] = scope
    if scope_plan:
        result["assessment_mode"] = scope_plan.get("mode", "scoped")
        result["score_semantics"] = scope_plan.get(
            "score_semantics",
            "scope_local",
        )
        result["scope_plan"] = scope_plan
    return compact_assessment_result(result)


def load_lineage_data_file(path: str) -> dict:
    lineage_file = Path(path)
    with open(lineage_file, encoding=TEXT_ENCODING) as f:
        return json.load(f)


def refresh_project_lineage(project: str, parallel: int = 1) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "dw_refactor_agent.lineage.lineage_extractor",
            "--project",
            project,
            "--parallel",
            str(parallel),
        ],
        cwd=PROJECT_ROOT,
        env=python_module_env(),
        check=True,
    )


def is_missing_default_lineage_error(error: FileNotFoundError, project: str):
    message = str(error)
    default_path = lineage_data_path(project)
    return (
        f"未找到 {project} 的血缘数据文件" in message
        or str(default_path) in message
    )


def missing_lineage_guidance(project: str) -> str:
    default_path = lineage_data_path(project)
    return (
        f"错误: 未找到 {project} 的血缘数据文件: {default_path}\n"
        "请先生成血缘数据，或指定已生成的临时血缘文件：\n"
        f"  python -m dw_refactor_agent.lineage.lineage_extractor --project {project}\n"
        f"  python -m dw_refactor_agent.assessment.assess_middle_layer --project {project} "
        "--refresh-lineage\n"
        f"  python -m dw_refactor_agent.assessment.assess_middle_layer --project {project} "
        "--lineage-file /path/to/lineage_data.json\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description="数据集市中间层评估工具 (评分权重支持单独指定，最终自动归一化)"
    )
    parser.add_argument(
        "--project",
        default="shop",
        choices=sorted(PROJECT_CONFIG.keys()),
        help="项目名称 (来自 warehouses/*/warehouse.yaml)",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 warehouses/{project}/artifacts/assessment/assess_result.json)",
    )
    parser.add_argument(
        "--lineage-file",
        help="显式指定血缘 JSON 文件，替代默认 warehouses/{project}/artifacts/lineage/lineage_data.json",
    )
    parser.add_argument(
        "--refresh-lineage",
        action="store_true",
        help="评分前先刷新默认 warehouses/{project}/artifacts/lineage/lineage_data.json",
    )
    parser.add_argument(
        "--lineage-parallel",
        type=int,
        default=1,
        help="刷新血缘时的 task 文件并行度，默认 1",
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
        "--table",
        action="append",
        default=[],
        help="只评估指定表；可重复传入",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help="只评估指定SQL作业文件；可重复传入",
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
    if args.lineage_file and args.refresh_lineage:
        parser.error("--lineage-file 与 --refresh-lineage 不能同时使用")
    if args.lineage_parallel < 1:
        parser.error("--lineage-parallel 必须 >= 1")

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
    if not selected_dimensions and args.only_rule:
        try:
            selected_dimensions = selected_dimensions_for_rules(args.only_rule)
        except ValueError as e:
            parser.error(str(e))

    scope_plan = build_manual_focus_scope_plan(
        table_names=args.table,
        task_paths=args.task,
    )

    lineage_data = None
    if args.lineage_file:
        try:
            lineage_data = load_lineage_data_file(args.lineage_file)
        except FileNotFoundError:
            parser.exit(
                1,
                f"错误: 指定的血缘数据文件不存在: {args.lineage_file}\n",
            )
        except json.JSONDecodeError as e:
            parser.exit(
                1,
                f"错误: 指定的血缘数据文件不是合法 JSON: {args.lineage_file} "
                f"({e})\n",
            )
    elif args.refresh_lineage:
        try:
            refresh_project_lineage(args.project, args.lineage_parallel)
        except subprocess.CalledProcessError as e:
            parser.exit(
                e.returncode or 1,
                f"错误: 刷新 {args.project} 血缘数据失败\n",
            )

    try:
        result = assess(
            args.project,
            weights,
            selected_dimensions=selected_dimensions,
            disabled_rules=args.disable_rule,
            only_rules=args.only_rule,
            lineage_data=lineage_data,
            scope_plan=scope_plan,
        )
    except ValueError as e:
        parser.exit(1, f"错误: {e}\n")
    except FileNotFoundError as e:
        if is_missing_default_lineage_error(e, args.project):
            parser.exit(1, missing_lineage_guidance(args.project))
        raise

    print(generate_report(result, result["weights"], args.project))

    output_path = args.output
    if not output_path:
        output_path = str(assess_result_path(args.project))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入: {output_path}")
    if scope_plan and _has_issues(result):
        sys.exit(1)


if __name__ == "__main__":
    main()
