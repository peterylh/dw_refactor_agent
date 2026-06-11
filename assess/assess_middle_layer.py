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

import json
import argparse
import sys
import re
from pathlib import Path
from collections import defaultdict
import os

import sqlglot
import yaml
from sqlglot import exp

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.context_builder import build_contexts
from assess.code_quality import score_code_quality
from assess.entity_metadata import (
    defined_entity_codes,
    grain_entity_codes,
    grain_key_columns,
    model_entities,
    primary_entity_codes,
)
from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    finalize_dimension,
    make_check,
    rule_meta,
)
from assess.table_inspector import TableInspector, VALID_TABLE_TYPES
from config import PROJECT_CONFIG, PROJECT_ROOT, layer_rank
from ddl_deriver.ddl_deriver import parse_create_table

# ============================================================
# 评分配置
# ============================================================

# 中间层深度 → 得分映射
# 深度 2 (DWD+DWS) 为理想, 1 (只有一层) 为欠佳, 0 为无中间层, ≥3 为过长
MIDDLE_DEPTH_SCORE = {2: 100, 1: 50, 0: 0}
MIDDLE_DEPTH_FALLBACK = 30  # depth ≥ 3

# 复用满分的下游引用数 (引用数 ≥ N 即满分)
REUSE_FULL_SCORE_AT = 3

DEFAULT_WEIGHTS = {
    "reuse": 0.18,
    "depth": 0.18,
    "architecture": 0.18,
    "naming": 0.18,
    "asset_completeness": 0.09,
    "metadata_health": 0.09,
    "code_quality": 0.1,
}

# 加权违规率配置: 严重度 → 权重
SEVERITY_WEIGHT = {SEVERITY_HIGH: 3, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 1}
# 每表扣分上限 (cap)，防止单张高频表拖垮整体评分
PER_TABLE_CAP = 3
ATOMIC_METRIC_RULE_NAME = "原子指标命名 {ACTION_VERB}_{MEASURE_NOUN}"
DERIVED_METRIC_RULE_NAME = (
    "派生指标命名 {TIME_PERIOD}_{MODIFIER...}_{ATOMIC_METRIC}"
)
DWS_ENTITY_RULE_NAME = "DWS表名实体包含于grain.entities"
DIM_ENTITY_RULE_NAME = "DIM表名实体等于entities.primary.code"
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
FILE_RULE_DDL = "DDL文件名与建表表名一致"
FILE_RULE_MODEL_NAME = "Model文件名与模型name一致"
FILE_RULE_TASK_SQL = "Task文件名与产出表一致"
FILE_RULE_TOTAL = "文件命名总计"
ASSET_RULE_DDL_MODEL = "DDL表存在Model"
ASSET_RULE_DDL_TASK = "需执行DDL表存在Task"
ASSET_RULE_MODEL_DDL = "Model存在对应DDL表"
ASSET_RULE_TASK_DDL = "Task产出表存在DDL"
ASSET_RULE_TASK_MODEL = "Task产出表存在Model"
ASSET_RULE_TASK_LINEAGE = "Task血缘目标与实际产出一致"
METADATA_HEALTH_RULES = {
    "METADATA_DIM_HAS_PRIMARY_ENTITY": rule_meta(
        name="entities.primary.code已配置",
        severity=SEVERITY_HIGH,
        title="DIM模型缺少主实体",
        remediation_summary="在模型YAML中补齐entities.primary.code或entity.code",
        strategy="update_model_primary_entity",
        edit_scope=["models"],
    ),
    "METADATA_ENTITY_KEYS_EXIST": rule_meta(
        name="entities.key_columns存在于表字段",
        severity=SEVERITY_HIGH,
        title="实体键字段不存在于表结构",
        remediation_summary="修正entities.key_columns，或补齐DDL中的实体键字段",
        strategy="align_entity_key_columns",
        edit_scope=["models", "ddl"],
    ),
    "METADATA_RELATIONSHIP_FROM_PRIMARY": rule_meta(
        name="entities.relationship.from_entity等于主实体",
        severity=SEVERITY_MEDIUM,
        title="实体关系来源与主实体不一致",
        remediation_summary="修正实体relationship.from_entity为当前模型主实体",
        strategy="update_entity_relationship",
        edit_scope=["models"],
    ),
    "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY": rule_meta(
        name="entities.code不同于主实体",
        severity=SEVERITY_MEDIUM,
        title="关联实体与主实体重复",
        remediation_summary="移除重复实体，或修正关联实体code",
        strategy="deduplicate_model_entities",
        edit_scope=["models"],
    ),
    "METADATA_GRAIN_KEYS_EXIST": rule_meta(
        name="grain.keys存在于表字段",
        severity=SEVERITY_HIGH,
        title="粒度键字段不存在于表结构",
        remediation_summary="修正grain.keys，或补齐DDL中的粒度键字段",
        strategy="align_grain_key_columns",
        edit_scope=["models", "ddl"],
    ),
    "METADATA_GRAIN_ENTITIES_PRESENT": rule_meta(
        name="grain.entities已配置",
        severity=SEVERITY_HIGH,
        title="DWS模型缺少grain.entities",
        remediation_summary="在模型YAML中补齐grain.entities",
        strategy="update_model_grain_entities",
        edit_scope=["models"],
    ),
    "METADATA_GRAIN_ENTITIES_DEFINED": rule_meta(
        name="grain.entities有实体定义",
        severity=SEVERITY_MEDIUM,
        title="grain.entities引用了未定义实体",
        remediation_summary="补齐实体定义，或修正grain.entities为已定义实体",
        strategy="update_model_grain_entities",
        edit_scope=["models"],
    ),
    "METADATA_DATA_DOMAIN_VALID": rule_meta(
        name="data_domain配置有效",
        severity=SEVERITY_MEDIUM,
        title="data_domain配置无效",
        remediation_summary="按命名字典修正模型YAML中的data_domain",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
    "METADATA_BUSINESS_AREA_VALID": rule_meta(
        name="business_area配置有效",
        severity=SEVERITY_MEDIUM,
        title="business_area配置无效",
        remediation_summary="按命名字典修正模型YAML中的business_area",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
}

ASSET_COMPLETENESS_RULES = {
    "ASSET_DDL_HAS_MODEL": rule_meta(
        name=ASSET_RULE_DDL_MODEL,
        severity=SEVERITY_HIGH,
        title="DDL表缺少Model",
        remediation_summary="为该DDL表补齐models/*.yaml元数据文件",
        strategy="create_missing_model",
        edit_scope=["models"],
    ),
    "ASSET_EXECUTABLE_DDL_HAS_TASK": rule_meta(
        name=ASSET_RULE_DDL_TASK,
        severity=SEVERITY_HIGH,
        title="需执行表缺少产出Task",
        remediation_summary="补齐产出该表的tasks/*.sql，或调整模型物化配置",
        strategy="create_missing_task",
        edit_scope=["tasks", "models"],
    ),
    "ASSET_MODEL_HAS_DDL": rule_meta(
        name=ASSET_RULE_MODEL_DDL,
        severity=SEVERITY_HIGH,
        title="Model缺少对应DDL",
        remediation_summary="补齐对应DDL，或删除/修正无效Model",
        strategy="create_missing_ddl",
        edit_scope=["ddl", "models"],
    ),
    "ASSET_TASK_OUTPUT_HAS_DDL": rule_meta(
        name=ASSET_RULE_TASK_DDL,
        severity=SEVERITY_HIGH,
        title="Task产出表缺少DDL",
        remediation_summary="补齐对应DDL，或修正Task产出目标",
        strategy="create_missing_ddl",
        edit_scope=["ddl", "tasks"],
    ),
    "ASSET_TASK_OUTPUT_HAS_MODEL": rule_meta(
        name=ASSET_RULE_TASK_MODEL,
        severity=SEVERITY_HIGH,
        title="Task产出表缺少Model",
        remediation_summary="补齐对应Model，或修正Task产出目标",
        strategy="create_missing_model",
        edit_scope=["models", "tasks"],
    ),
    "ASSET_TASK_LINEAGE_MATCHES_OUTPUT": rule_meta(
        name=ASSET_RULE_TASK_LINEAGE,
        severity=SEVERITY_HIGH,
        title="Task血缘目标与实际产出不一致",
        remediation_summary="刷新血缘，或修正Task中的实际写入目标",
        strategy="refresh_or_fix_task_lineage",
        edit_scope=["tasks", "lineage"],
    ),
}

ASSET_RULE_IDS = {
    ASSET_RULE_DDL_MODEL: "ASSET_DDL_HAS_MODEL",
    ASSET_RULE_DDL_TASK: "ASSET_EXECUTABLE_DDL_HAS_TASK",
    ASSET_RULE_MODEL_DDL: "ASSET_MODEL_HAS_DDL",
    ASSET_RULE_TASK_DDL: "ASSET_TASK_OUTPUT_HAS_DDL",
    ASSET_RULE_TASK_MODEL: "ASSET_TASK_OUTPUT_HAS_MODEL",
    ASSET_RULE_TASK_LINEAGE: "ASSET_TASK_LINEAGE_MATCHES_OUTPUT",
}

REUSABILITY_RULES = {
    "REUSE_DOWNSTREAM_REACHES_TARGET": rule_meta(
        name="中间层表达到目标复用度",
        severity=SEVERITY_LOW,
        title="中间层表复用不足",
        remediation_summary="确认该中间层表是否应保留，或补充下游复用链路",
        strategy="review_reuse_or_downstream_dependencies",
        edit_scope=["tasks", "models"],
    ),
}

LINEAGE_DEPTH_RULES = {
    "DEPTH_MIDDLE_LAYER_IS_OPTIMAL": rule_meta(
        name="ADS链路中间层深度合理",
        severity=SEVERITY_MEDIUM,
        title="ADS链路中间层深度不合理",
        remediation_summary="调整ADS上游链路，使其经过合理的DWD/DWS/DIM中间层",
        strategy="refactor_lineage_depth",
        edit_scope=["tasks", "models"],
    ),
}

ARCHITECTURE_RULES = {
    "ARCH_ALLOWED_DEPENDENCY": rule_meta(
        name="层级依赖方向合理",
        severity=SEVERITY_LOW,
        title="层级依赖方向合理",
        remediation_summary="无需处理",
        strategy="none",
        edit_scope=[],
    ),
    "ARCH_REVERSE_DEPENDENCY": rule_meta(
        name="禁止反向依赖",
        severity=SEVERITY_HIGH,
        title="存在反向依赖",
        remediation_summary="调整作业依赖方向，避免高层数据反向流入低层",
        strategy="refactor_reverse_dependency",
        edit_scope=["tasks"],
    ),
    "ARCH_SAME_LAYER_DEPENDENCY": rule_meta(
        name="避免非必要同层依赖",
        severity=SEVERITY_LOW,
        title="存在同层依赖",
        remediation_summary="确认同层依赖是否必要，必要时沉淀公共上游或调整分层",
        strategy="review_same_layer_dependency",
        edit_scope=["tasks", "models"],
    ),
    "ARCH_SKIP_LAYER_DEPENDENCY": rule_meta(
        name="避免跳层依赖",
        severity=SEVERITY_MEDIUM,
        title="存在跳层依赖",
        remediation_summary="补齐或复用中间层，避免ODS/DWD直接服务高层结果",
        strategy="insert_or_reuse_middle_layer",
        edit_scope=["tasks", "models"],
    ),
    "ARCH_DECLARED_LAYER_MATCHES_LLM": rule_meta(
        name="配置层与LLM推断层一致",
        severity=SEVERITY_MEDIUM,
        title="表层级配置疑似错误",
        remediation_summary="复核模型layer配置，必要时修正models/*.yaml",
        strategy="update_model_layer",
        edit_scope=["models"],
    ),
    "ARCH_DWD_DIMENSION_POSITION": rule_meta(
        name="维度表不应位于DWD",
        severity=SEVERITY_LOW,
        title="维度表位置不当",
        remediation_summary="将维度型表迁移到DIM层，或修正表类型判断",
        strategy="move_dimension_table_to_dim",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "ARCH_TABLE_TYPE_MATCHES_LLM": rule_meta(
        name="配置表类型与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="表类型配置疑似错误",
        remediation_summary="复核table_type配置，必要时修正models/*.yaml",
        strategy="update_model_table_type",
        edit_scope=["models"],
    ),
    "ARCH_DATA_DOMAIN_MATCHES_LLM": rule_meta(
        name="数据域配置与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="数据域配置疑似错误",
        remediation_summary="复核data_domain配置，必要时修正models/*.yaml",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
    "ARCH_BUSINESS_AREA_MATCHES_LLM": rule_meta(
        name="业务板块配置与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="业务板块配置疑似错误",
        remediation_summary="复核business_area配置，必要时修正models/*.yaml",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
}

NAMING_RULES = {
    "NAMING_TABLE_TEMPLATE": rule_meta(
        name="表名符合规范模板",
        severity=SEVERITY_MEDIUM,
        title="表名不符合规范模板",
        remediation_summary="按所在层级的表名模板重命名表，并同步DDL、Task和Model引用",
        strategy="rename_table_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_TABLE_MAX_LENGTH": rule_meta(
        name="表名长度符合限制",
        severity=SEVERITY_LOW,
        title="表名超过长度限制",
        remediation_summary="缩短表名并同步相关DDL、Task和Model引用",
        strategy="rename_table_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_COLUMN_NAME": rule_meta(
        name="列名符合规范",
        severity=SEVERITY_LOW,
        title="字段名不符合规范",
        remediation_summary="按字段命名规则重命名字段，并同步DDL、Task和Model引用",
        strategy="rename_columns_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_ATOMIC_METRIC": rule_meta(
        name=ATOMIC_METRIC_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="原子指标命名不合规",
        remediation_summary="按原子指标命名规则修正指标名，并同步相关引用",
        strategy="rename_metric_and_rewrite_references",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DERIVED_METRIC": rule_meta(
        name=DERIVED_METRIC_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="派生指标命名不合规",
        remediation_summary="按派生指标命名规则修正指标名，并同步相关引用",
        strategy="rename_metric_and_rewrite_references",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DWS_ENTITY_ALIGNMENT": rule_meta(
        name=DWS_ENTITY_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="DWS表名实体与grain.entities不一致",
        remediation_summary="修正DWS表名实体段或模型grain.entities",
        strategy="align_dws_name_with_grain_entities",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DIM_ENTITY_ALIGNMENT": rule_meta(
        name=DIM_ENTITY_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="DIM表名实体与主实体不一致",
        remediation_summary="修正DIM表名实体段或模型主实体配置",
        strategy="align_dim_name_with_primary_entity",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_SEMANTIC_METADATA_ALIGNMENT": rule_meta(
        name="表名语义段与模型元数据一致",
        severity=SEVERITY_MEDIUM,
        title="表名语义段与模型元数据不一致",
        remediation_summary="修正表名中的业务语义段，或修正模型业务元数据",
        strategy="align_table_name_with_model_metadata",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DDL_FILE_NAME": rule_meta(
        name=FILE_RULE_DDL,
        severity=SEVERITY_LOW,
        title="DDL文件名与表名不一致",
        remediation_summary="重命名DDL文件，使文件名与建表表名一致",
        strategy="rename_file",
        edit_scope=["file_path"],
    ),
    "NAMING_MODEL_FILE_NAME": rule_meta(
        name=FILE_RULE_MODEL_NAME,
        severity=SEVERITY_LOW,
        title="Model文件名与模型name不一致",
        remediation_summary="重命名Model文件，或修正模型name",
        strategy="rename_file_or_model",
        edit_scope=["file_path", "models"],
    ),
    "NAMING_TASK_OUTPUT_NAME": rule_meta(
        name=FILE_RULE_TASK_SQL,
        severity=SEVERITY_LOW,
        title="Task文件名与产出表不一致",
        remediation_summary="重命名Task文件，或修正Task产出表",
        strategy="rename_file_or_task_output",
        edit_scope=["file_path", "tasks"],
    ),
}

NAMING_FILE_RULE_IDS = {
    FILE_RULE_DDL: "NAMING_DDL_FILE_NAME",
    FILE_RULE_MODEL_NAME: "NAMING_MODEL_FILE_NAME",
    FILE_RULE_TASK_SQL: "NAMING_TASK_OUTPUT_NAME",
}

def normalize_score_weights(weights: dict | None = None) -> dict:
    merged = DEFAULT_WEIGHTS.copy()
    extra = {}
    if weights:
        for key, value in weights.items():
            if key in DEFAULT_WEIGHTS:
                merged[key] = value
            else:
                extra[key] = value

    invalid = {
        key: value
        for key, value in merged.items()
        if value is None or value < 0
    }
    if invalid:
        invalid_text = ", ".join(
            f"{key}={value}" for key, value in invalid.items())
        raise ValueError(f"权重必须为非负数: {invalid_text}")

    total = sum(merged.values())
    if total <= 0:
        raise ValueError("评分权重之和必须大于 0")

    normalized = {
        key: round(value / total, 6)
        for key, value in merged.items()
    }
    return {**normalized, **extra}


# 依赖违规定义: 通过 src/tgt 层序号差自动判定
# rank_diff = src_rank - tgt_rank
# 正数 → 反向依赖 (高层→低层, 数据倒流)
# 0     → 同层依赖
# -1    → 相邻上层 (正常, ODS→DWD, DWD→DWS, DWS→ADS)
# -2    → 跳过一层 (DWD→ADS 或 ODS→DWS; DIM→ADS 为合理维度引用)
# -3    → 跳过两层 (ODS→ADS)

ARCH_VIOLATION_RULES = [
    # (rank_diff, description, severity, penalty)
    (3, "反向依赖: 跳过三层(ADS→ODS)", SEVERITY_HIGH, 40),
    (2, "反向依赖: 跳过两层", SEVERITY_HIGH, 30),
    (1, "反向依赖: 跳过一层", SEVERITY_HIGH, 20),
    (0, "同层依赖(非必要)", SEVERITY_LOW, 2),
    (-2, "跳过中间层(DWD→ADS 或 ODS→DWS)", SEVERITY_MEDIUM, 5),
    (-3, "跳过两层(ODS→ADS)", SEVERITY_MEDIUM, 10),
]

# ============================================================
# 数据加载与图构建
# ============================================================


def load_lineage_data(project: str) -> dict:
    lineage_dir = Path(__file__).resolve().parent.parent / "lineage"
    project_path = lineage_dir / f"lineage_data_{project}.json"
    if project_path.exists():
        with open(project_path) as f:
            return json.load(f)

    legacy_path = lineage_dir / "lineage_data.json"
    if project == "shop" and legacy_path.exists():
        with open(legacy_path) as f:
            return json.load(f)

    raise FileNotFoundError(
        f"未找到 {project} 的血缘数据文件 (lineage_data_{project}.json)")


def _table_from_node(node_id: str) -> str:
    return node_id.rsplit(".", 1)[0]


def build_table_graph(edges: list, indirect_edges: list) -> tuple[dict, dict]:
    upstream = defaultdict(set)
    downstream = defaultdict(set)

    for e in edges:
        src = _table_from_node(e["source"])
        tgt = _table_from_node(e["target"])
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in indirect_edges:
        src = _table_from_node(ie["source"])
        tgt = ie["target_table"]
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def build_table_layer_map(tables: list) -> dict:
    return {t["name"]: t["layer"] for t in tables}


# ============================================================
# 复用度评分
# ============================================================


def score_reusability(tables: list, downstream_map: dict) -> dict:
    middle = [t for t in tables if t["layer"] in ("DWD", "DWS", "DIM")]

    checks = []
    scores = []
    downstream_counts = []
    for t in middle:
        name = t["name"]
        cnt = len(downstream_map.get(name, set()))
        score = min(100, cnt / REUSE_FULL_SCORE_AT * 100)
        scores.append(round(score, 1))
        downstream_counts.append(cnt)
        issue = {}
        if cnt == 0:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "中间层表无下游复用",
                "message": "中间层表无下游引用",
            }
        elif cnt < REUSE_FULL_SCORE_AT:
            issue = {
                "severity": SEVERITY_LOW,
                "title": "中间层表复用不足",
                "message": f"下游引用数={cnt}，低于目标{REUSE_FULL_SCORE_AT}",
            }
        checks.append(
            make_check(
                rule_id="REUSE_DOWNSTREAM_REACHES_TARGET",
                target_type="table",
                target=name,
                passed=cnt >= REUSE_FULL_SCORE_AT,
                expected=f"下游引用数 >= {REUSE_FULL_SCORE_AT}",
                actual=f"下游引用数 = {cnt}",
                evidence={
                    "layer": t["layer"],
                    "downstream_count": cnt,
                },
                message=issue.get("message", ""),
                issue=issue or None,
            )
        )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    avg_reuse = (
        round(sum(downstream_counts) / len(downstream_counts), 2)
        if downstream_counts
        else 0.0
    )

    dist = dict(
        high=sum(1 for cnt in downstream_counts
                 if cnt >= REUSE_FULL_SCORE_AT),
        medium=sum(1 for cnt in downstream_counts
                   if 1 <= cnt < REUSE_FULL_SCORE_AT),
        none=sum(1 for cnt in downstream_counts if cnt == 0),
    )

    return finalize_dimension(
        dimension="reuse",
        score=avg_score,
        checks=checks,
        rules=REUSABILITY_RULES,
        summary={
            "avg_reuse_count": avg_reuse,
            "distribution": dist,
            "target_downstream_count": REUSE_FULL_SCORE_AT,
        },
    )


# ============================================================
# 链路长度评分 (中间层深度)
# ============================================================


def _max_middle_depth(
    table: str,
    upstream_map: dict,
    table_layers: dict,
    memo: dict = None,
    visiting: set = None,
) -> int:
    if memo is None:
        memo = {}
    if visiting is None:
        visiting = set()

    if table in memo:
        return memo[table]
    if table in visiting:
        return 0

    visiting.add(table)

    layer = table_layers.get(table, "OTHER")
    contribution = 1 if layer in ("DWD", "DWS", "DIM") else 0

    parents = upstream_map.get(table, set())
    if not parents:
        result = contribution
    else:
        max_sub = 0
        for p in parents:
            max_sub = max(
                max_sub,
                _max_middle_depth(p, upstream_map, table_layers, memo,
                                  visiting))
        result = contribution + max_sub

    visiting.remove(table)
    memo[table] = result
    return result


def _depth_to_score(depth: int) -> int:
    return MIDDLE_DEPTH_SCORE.get(depth, MIDDLE_DEPTH_FALLBACK)


def score_lineage_depth(tables: list, edges: list,
                        indirect_edges: list) -> dict:
    table_layers = build_table_layer_map(tables)
    upstream, _ = build_table_graph(edges, indirect_edges)

    # 不按表名推断缺失层级；models/lineage 中没有声明的表按 OTHER 处理。

    ads = [t for t in tables if t["layer"] == "ADS"]

    checks = []
    scores = []
    depths = []
    for t in ads:
        name = t["name"]
        depth = _max_middle_depth(name, upstream, table_layers)
        score = _depth_to_score(depth)
        scores.append(score)
        depths.append(depth)
        issue = {}
        if depth == 0:
            issue = {
                "severity": SEVERITY_HIGH,
                "title": "ADS链路缺少中间层",
                "message": "ADS到ODS链路中未发现DWD/DWS/DIM中间层",
            }
        elif depth == 1:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "ADS链路中间层不足",
                "message": "ADS链路只有一层中间层",
            }
        elif depth >= 3:
            issue = {
                "severity": SEVERITY_MEDIUM,
                "title": "ADS链路中间层过长",
                "message": f"ADS链路中间层深度={depth}",
            }
        checks.append(
            make_check(
                rule_id="DEPTH_MIDDLE_LAYER_IS_OPTIMAL",
                target_type="table",
                target=name,
                passed=depth == 2,
                expected="最大中间层深度 = 2",
                actual=f"最大中间层深度 = {depth}",
                evidence={"max_middle_depth": depth},
                message=issue.get("message", ""),
                issue=issue or None,
            )
        )

    avg_score = round(sum(scores) / len(scores), 1) if scores else 100.0
    avg_depth = round(sum(depths) / len(depths), 2) if depths else 0.0

    return finalize_dimension(
        dimension="depth",
        score=avg_score,
        checks=checks,
        rules=LINEAGE_DEPTH_RULES,
        summary={
            "avg_middle_depth": avg_depth,
            "ideal_middle_depth": 2,
        },
    )


# ============================================================
# 架构合理性评分
# ============================================================


def _declared_table_type(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    raw_type = model_metadata.get(table_name, {}).get("table_type")
    table_type = str(raw_type or "").strip()
    return table_type if table_type in VALID_TABLE_TYPES else ""


def _declared_data_domain(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    return str(model_metadata.get(table_name, {}).get("data_domain") or "").strip()


def _declared_business_area(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    return (
        str(model_metadata.get(table_name, {}).get("business_area") or "")
        .strip()
        .upper()
    )


def _data_domain_applies(layer: str) -> bool:
    return str(layer or "").upper() in DATA_DOMAIN_LAYERS


def _business_area_applies(layer: str) -> bool:
    return str(layer or "").upper() in BUSINESS_AREA_LAYERS


def _valid_inferred_data_domain(result, business_domain_config) -> str:
    if not business_domain_config:
        return str(getattr(result, "inferred_data_domain", "") or "").strip()
    normalized = business_domain_config.normalize_domain(
        getattr(result, "inferred_data_domain", ""))
    return normalized if business_domain_config.is_valid_domain(normalized) else ""


def _valid_inferred_business_area(result, business_domain_config) -> str:
    if not business_domain_config:
        return (
            str(getattr(result, "inferred_business_area", "") or "")
            .strip()
            .upper()
        )
    normalized = business_domain_config.normalize_business_area(
        getattr(result, "inferred_business_area", ""))
    return (
        normalized
        if business_domain_config.is_valid_business_area(normalized)
        else ""
    )


def score_architecture_health(tables: list, edges: list,
                              indirect_edges: list,
                              llm_results: list = None,
                              model_metadata: dict | None = None,
                              business_domain_config=None) -> dict:
    table_layers = build_table_layer_map(tables)
    table_count = len(tables)  # 全部表数 (ODS+DWD+DWS+DIM+ADS)

    # 收集表级边 (去重)
    table_edges = defaultdict(set)
    for e in edges:
        src = _table_from_node(e["source"])
        tgt = _table_from_node(e["target"])
        if src != tgt:
            table_edges[(src, tgt)].add(e.get("source_file", ""))
    for ie in indirect_edges:
        src = _table_from_node(ie["source"])
        tgt = ie["target_table"]
        if src != tgt:
            table_edges[(src, tgt)].add(ie.get("source_file", ""))

    checks = []
    # 每表累计权重 (cap 前)
    table_weight = defaultdict(int)

    def record_check(
        *,
        rule_id: str,
        target_table: str,
        passed: bool,
        expected: str,
        actual: str,
        evidence: dict | None = None,
        message: str = "",
        severity: str | None = None,
        title: str | None = None,
    ) -> None:
        issue = {}
        if severity:
            issue["severity"] = severity
        if title:
            issue["title"] = title
        if message:
            issue["message"] = message
        checks.append(
            make_check(
                rule_id=rule_id,
                target_type="table",
                target=target_table,
                passed=passed,
                expected=expected,
                actual=actual,
                evidence=evidence,
                message=message,
                issue=issue or None,
            )
        )
        if not passed:
            effective_severity = (
                severity
                or ARCHITECTURE_RULES[rule_id]["severity"]
            )
            table_weight[target_table] += SEVERITY_WEIGHT[effective_severity]

    # ---- 规则检测: 跨层/反向/跳层依赖 (归属 target 表) ----
    for (src, tgt), files in table_edges.items():
        src_layer = table_layers.get(src, "OTHER")
        tgt_layer = table_layers.get(tgt, "OTHER")
        src_rank = layer_rank(src_layer)
        tgt_rank = layer_rank(tgt_layer)
        if src_rank < 0 or tgt_rank < 0:
            continue

        rank_diff = src_rank - tgt_rank
        evidence = {
            "source": src,
            "source_layer": src_layer,
            "target": tgt,
            "target_layer": tgt_layer,
            "source_files": sorted(files),
            "rank_diff": rank_diff,
        }

        # ADS 面向应用输出，直接引用公共维度表补充属性是合理的数据集市建模方式。
        if src_layer == "DIM" and tgt_layer == "ADS":
            record_check(
                rule_id="ARCH_ALLOWED_DEPENDENCY",
                target_table=tgt,
                passed=True,
                expected="层级依赖方向合理",
                actual=f"{src}({src_layer}) -> {tgt}({tgt_layer})",
                evidence=evidence,
            )
            continue

        # 正常相邻上层 → 跳过
        if rank_diff == -1:
            record_check(
                rule_id="ARCH_ALLOWED_DEPENDENCY",
                target_table=tgt,
                passed=True,
                expected="层级依赖方向合理",
                actual=f"{src}({src_layer}) -> {tgt}({tgt_layer})",
                evidence=evidence,
            )
            continue

        for diff, desc, severity, _penalty in ARCH_VIOLATION_RULES:
            if rank_diff == diff:
                if severity == SEVERITY_HIGH:
                    rule_id = "ARCH_REVERSE_DEPENDENCY"
                elif rank_diff == 0:
                    rule_id = "ARCH_SAME_LAYER_DEPENDENCY"
                else:
                    rule_id = "ARCH_SKIP_LAYER_DEPENDENCY"
                record_check(
                    rule_id=rule_id,
                    target_table=tgt,
                    passed=False,
                    expected="层级依赖方向合理",
                    actual=f"{src}({src_layer}) -> {tgt}({tgt_layer})",
                    evidence=evidence,
                    message=desc,
                    severity=severity,
                )

    # ---- LLM 检测: 分层配置疑似错误 & 维度表位置不当 (归属被评估表本身) ----
    if llm_results:
        cls_map = {r.table_name: r for r in llm_results}
        table_map = {t["name"]: t for t in tables}
        for name, res in cls_map.items():
            layer = table_map[name]["layer"] if name in table_map else "OTHER"

            record_check(
                rule_id="ARCH_DECLARED_LAYER_MATCHES_LLM",
                target_table=name,
                passed=not res.is_violating_declared_layer,
                expected="配置层与LLM推断层一致",
                actual=f"配置层={layer}, 推断层={res.inferred_layer}",
                evidence={
                    "source_type": "llm",
                    "confidence": getattr(res, "confidence", None),
                },
                message=(
                    "分层配置疑似错误(LLM): "
                    f"配置层={layer}, 推断层={res.inferred_layer}"
                ) if res.is_violating_declared_layer else "",
            )

            is_dwd_dimension = res.table_type == "dimension" and layer == "DWD"
            record_check(
                rule_id="ARCH_DWD_DIMENSION_POSITION",
                target_table=name,
                passed=not is_dwd_dimension,
                expected="维度表不位于DWD层",
                actual=f"配置层={layer}, LLM表类型={res.table_type}",
                evidence={
                    "source_type": "llm",
                    "confidence": getattr(res, "confidence", None),
                },
                message=(
                    "维度表位置不当(LLM): 维度表应置于 DIM 层"
                    if is_dwd_dimension else ""
                ),
            )

            declared_type = _declared_table_type(model_metadata, name)
            if declared_type:
                type_mismatch = declared_type != res.table_type
                record_check(
                    rule_id="ARCH_TABLE_TYPE_MATCHES_LLM",
                    target_table=name,
                    passed=not type_mismatch,
                    expected="配置表类型与LLM推断一致",
                    actual=f"配置类型={declared_type}, 推断类型={res.table_type}",
                    evidence={
                        "source_type": "llm",
                        "confidence": getattr(res, "confidence", None),
                    },
                    message=(
                        "表类型配置疑似错误(LLM): "
                        f"配置类型={declared_type}, 推断类型={res.table_type}"
                    ) if type_mismatch else "",
                )

            if _data_domain_applies(layer):
                inferred_domain = _valid_inferred_data_domain(
                    res,
                    business_domain_config,
                )
                declared_domain = (
                    business_domain_config.normalize_domain(
                        _declared_data_domain(model_metadata, name))
                    if business_domain_config
                    else _declared_data_domain(model_metadata, name)
                )
                if inferred_domain:
                    domain_mismatch = inferred_domain != declared_domain
                    severity = (
                        SEVERITY_MEDIUM
                        if declared_domain else SEVERITY_LOW
                    )
                    record_check(
                        rule_id="ARCH_DATA_DOMAIN_MATCHES_LLM",
                        target_table=name,
                        passed=not domain_mismatch,
                        expected="data_domain与LLM推断一致",
                        actual=(
                            f"配置={declared_domain or '未配置'}, "
                            f"推断={inferred_domain}"
                        ),
                        evidence={
                            "source_type": "llm",
                            "confidence": getattr(res, "confidence", None),
                        },
                        message=(
                            "数据域配置疑似错误(LLM): "
                            f"配置={declared_domain or '未配置'}, "
                            f"推断={inferred_domain}"
                        ) if domain_mismatch else "",
                        severity=severity if domain_mismatch else None,
                    )

            if _business_area_applies(layer):
                inferred_area = _valid_inferred_business_area(
                    res,
                    business_domain_config,
                )
                declared_area = (
                    business_domain_config.normalize_business_area(
                        _declared_business_area(model_metadata, name))
                    if business_domain_config
                    else _declared_business_area(model_metadata, name)
                )
                if inferred_area:
                    area_mismatch = inferred_area != declared_area
                    severity = (
                        SEVERITY_MEDIUM
                        if declared_area else SEVERITY_LOW
                    )
                    record_check(
                        rule_id="ARCH_BUSINESS_AREA_MATCHES_LLM",
                        target_table=name,
                        passed=not area_mismatch,
                        expected="business_area与LLM推断一致",
                        actual=(
                            f"配置={declared_area or '未配置'}, "
                            f"推断={inferred_area}"
                        ),
                        evidence={
                            "source_type": "llm",
                            "confidence": getattr(res, "confidence", None),
                        },
                        message=(
                            "业务板块配置疑似错误(LLM): "
                            f"配置={declared_area or '未配置'}, 推断={inferred_area}"
                        ) if area_mismatch else "",
                        severity=severity if area_mismatch else None,
                    )

    # 每表扣分上限 (cap)
    capped_total = 0
    table_capped = {}
    for tbl, w in table_weight.items():
        capped = min(w, PER_TABLE_CAP)
        table_capped[tbl] = capped
        capped_total += capped

    # 加权违规率评分
    score = max(0, round(100 * (1 - capped_total / table_count), 1)) if table_count else 100.0

    return finalize_dimension(
        dimension="architecture",
        score=score,
        checks=checks,
        rules=ARCHITECTURE_RULES,
        summary={
            "table_count": table_count,
            "capped_total": capped_total,
            "table_capped": table_capped,
        },
    )


# ============================================================
# 命名规范评分
# ============================================================

def _check_table_name_any_template(name: str, layer: str, nc) -> bool:
    ldef = nc.layers.get(layer)
    if not ldef:
        return False
    for segs in ldef.templates:
        if nc._match_segments(name, segs) is not None:
            return True
    return False


def _table_name_diagnostic(name: str, layer: str, nc) -> dict:
    if hasattr(nc, "diagnose_table_name"):
        return nc.diagnose_table_name(name, layer)
    return {
        "actual": name,
        "layer": layer,
        "passed": False,
        "message": "命名配置对象不支持结构化诊断",
    }


def _table_name_max_length(name: str, layer: str, nc) -> int | None:
    if hasattr(nc, "table_max_length_for"):
        return nc.table_max_length_for(name, layer)
    return getattr(nc, "table_name_max_length", None)


def _check_table_name_length(name: str, layer: str, nc) -> bool:
    max_length = _table_name_max_length(name, layer, nc)
    return max_length is None or len(name) <= max_length

def _check_column_name(col_name: str, nc) -> tuple[bool, list[str]]:
    if col_name in nc.common_columns:
        return True, ["通用列名"]

    templates = getattr(nc, "column_templates", None) or (
        [nc.column_segments] if getattr(nc, "column_segments", None) else []
    )
    for template in templates:
        if nc._match_segments(col_name, template) is not None:
            return True, ["字段命名模板"]

    if templates:
        return False, []

    # OR 匹配：字段只要匹配任意一个已知后缀/前缀模式即合规
    matched = []
    sf = nc.types.get("suffix_field")
    if sf and sf.allow:
        for v in sorted(sf.allow, key=len, reverse=True):
            if col_name.endswith(f"_{v}"):
                matched.append(f"后缀 _{v}")
                break
    if not matched:
        pf = nc.types.get("prefix_field")
        if pf and pf.allow:
            for v in sorted(pf.allow, key=len, reverse=True):
                if col_name.startswith(f"{v}_"):
                    matched.append(f"前缀 {v}_")
                    break

    return bool(matched), matched


def _column_name_diagnostic(col_name: str, nc) -> dict:
    if hasattr(nc, "diagnose_column_name"):
        return nc.diagnose_column_name(col_name)
    return {
        "actual": col_name,
        "passed": False,
        "message": "命名配置对象不支持结构化诊断",
    }


def _as_string_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [
        str(item).strip()
        for item in values
        if str(item or "").strip()
    ]


def _dws_name_entities(name: str, nc) -> list[str]:
    return _table_name_type_values(
        name,
        "DWS",
        nc,
        "GRAIN_ENTITY",
        fallback_type_name="ENTITY",
    )


def _table_name_type_values(
    name: str,
    layer: str,
    nc,
    type_name: str,
    *,
    fallback_type_name: str | None = None,
) -> list[str]:
    layer_def = getattr(nc, "layers", {}).get("DWS")
    if layer != "DWS":
        layer_def = getattr(nc, "layers", {}).get(layer)
    if not layer_def:
        return []
    for segments in layer_def.templates:
        matched = nc._match_segments(name, segments)
        if matched is not None:
            values = _as_string_list(matched.get(type_name))
            if values:
                return values
            if fallback_type_name:
                return _as_string_list(matched.get(fallback_type_name))
    return []


def _model_grain_entities(
    table_name: str,
    model_metadata: dict | None,
) -> list[str]:
    if not model_metadata:
        return []
    return grain_entity_codes(model_metadata.get(table_name, {}))


def _model_defined_entities(model_metadata: dict | None) -> set[str]:
    return defined_entity_codes(model_metadata)


def _score_dws_entity_name(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
) -> dict:
    result = _naming_check_result(0, 0, [])
    if layer != "DWS":
        return result
    if not model_metadata or table_name not in model_metadata:
        return result

    expected = _model_grain_entities(table_name, model_metadata)
    if not expected:
        return result

    actual = _dws_name_entities(table_name, nc)
    result["total"] = 1
    violations = []
    if not actual or not set(actual).issubset(set(expected)):
        violations.append(f"表名ENTITY={actual}，grain.entities={expected}")

    if not violations:
        result["passed"] = 1
    else:
        result["violations"] = violations
    return result


def _score_dim_entity_name(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
) -> dict:
    result = _naming_check_result(0, 0, [])
    if layer != "DIM":
        return result
    if not model_metadata or table_name not in model_metadata:
        return result

    expected = _model_entity_codes(model_metadata.get(table_name))
    if not expected:
        result["total"] = 1
        result["violations"] = [
            "缺少entities.primary.code，无法检测DIM表名ENTITY"
        ]
        return result

    actual = _table_name_type_values(
        table_name,
        layer,
        nc,
        "MODEL_ENTITY",
        fallback_type_name="ENTITY",
    )
    result["total"] = 1
    if actual == expected:
        result["passed"] = 1
    else:
        result["violations"] = [
            f"表名MODEL_ENTITY={actual}，entities.primary.code={expected}"
        ]
    return result


def _model_entity_codes(metadata: dict | None) -> list[str]:
    return primary_entity_codes(metadata)


def _table_column_names(table: dict) -> set[str]:
    return {
        str(column.get("name") or "").strip()
        for column in table.get("columns", []) or []
        if str(column.get("name") or "").strip()
    }


def score_metadata_health(
    tables: list,
    nc,
    model_metadata: dict | None,
    business_domain_config=None,
    *,
    asset_catalog: dict | None = None,
) -> dict:
    """检查 models/*.yaml 的结构自洽性与业务元数据有效性。"""
    if not model_metadata:
        return finalize_dimension(
            dimension="metadata_health",
            score=100.0,
            checks=[],
            rules=METADATA_HEALTH_RULES,
        )

    if asset_catalog:
        tables_by_name = {
            name: dict(
                name=name,
                layer=asset.get("layer", "OTHER"),
                columns=asset.get("columns") or [],
            )
            for name, asset in asset_catalog.get("tables", {}).items()
            if asset.get("ddl") or asset.get("lineage_table")
        }
    else:
        tables_by_name = {table["name"]: table for table in tables}
    defined_entities = _model_defined_entities(model_metadata)
    checks = []

    def record(
        table_name: str,
        rule_id: str,
        ok: bool,
        expected: str,
        actual: str,
        evidence: dict | None = None,
        reason: str = "",
        message: str = "",
        severity: str | None = None,
    ) -> None:
        issue = {}
        if reason:
            issue["message"] = message
        if severity:
            issue["severity"] = severity
        checks.append(
            make_check(
                rule_id=rule_id,
                target_type="table",
                target=table_name,
                passed=ok,
                expected=expected,
                actual=actual,
                evidence=evidence,
                message=message,
                issue=issue or None,
            )
        )

    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        table = tables_by_name.get(table_name)
        columns = _table_column_names(table) if table else set()

        entities = model_entities(metadata)
        entity_codes = _model_entity_codes(metadata)
        primary_code = entity_codes[0] if entity_codes else ""
        layer = str(
            metadata.get("layer")
            or (table or {}).get("layer")
            or "OTHER"
        ).upper()
        if layer == "DIM":
            record(
                table_name,
                "METADATA_DIM_HAS_PRIMARY_ENTITY",
                bool(entity_codes),
                "DIM模型配置主实体编码",
                entity_codes[0] if entity_codes else "未配置",
                {"layer": layer},
                "missing",
                "缺少entities.primary.code",
            )

        if table:
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entity_code = str(entity.get("code") or "").strip()
                entity_type = str(entity.get("type") or "").strip().lower()
                key_columns = _as_string_list(entity.get("key_columns"))
                if key_columns:
                    missing_keys = [
                        key for key in key_columns
                        if key not in columns
                    ]
                    record(
                        table_name,
                        "METADATA_ENTITY_KEYS_EXIST",
                        not missing_keys,
                        f"entities[{entity_code}].key_columns存在于表字段",
                        (
                            "全部存在"
                            if not missing_keys
                            else f"缺失字段: {missing_keys}"
                        ),
                        {
                            "entity": entity_code,
                            "key_columns": key_columns,
                            "table_columns": sorted(columns),
                        },
                        "",
                        (
                            f"entities[{entity_code}]"
                            f".key_columns不存在={missing_keys}"
                        ),
                    )
                if entity_type == "primary":
                    continue
                relationship = entity.get("relationship")
                if primary_code and isinstance(relationship, dict):
                    from_entity = str(
                        relationship.get("from_entity") or "").strip()
                    record(
                        table_name,
                        "METADATA_RELATIONSHIP_FROM_PRIMARY",
                        from_entity == primary_code,
                        "relationship.from_entity等于主实体",
                        from_entity,
                        {
                            "entity": entity_code,
                            "primary_entity": primary_code,
                        },
                        "",
                        (
                            f"entities[{entity_code}]"
                            f".relationship.from_entity={from_entity}，"
                            f"primary_entity={primary_code}"
                        ),
                    )
                if primary_code and entity_code:
                    record(
                        table_name,
                        "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY",
                        entity_code != primary_code,
                        "关联实体code不同于主实体",
                        entity_code,
                        {
                            "entity": entity_code,
                            "primary_entity": primary_code,
                        },
                        "",
                        f"entities.code={entity_code} 与主实体重复",
                    )

        grain = metadata.get("grain")
        if table and isinstance(grain, dict):
            grain_keys = grain_key_columns(metadata)
            if grain_keys:
                missing_grain_keys = [
                    key for key in grain_keys
                    if key not in columns
                ]
                record(
                    table_name,
                    "METADATA_GRAIN_KEYS_EXIST",
                    not missing_grain_keys,
                    "grain.keys存在于表字段",
                    (
                        "全部存在"
                        if not missing_grain_keys
                        else f"缺失字段: {missing_grain_keys}"
                    ),
                    {
                        "grain_keys": grain_keys,
                        "table_columns": sorted(columns),
                    },
                    "",
                    f"grain.keys不存在={missing_grain_keys}",
                )

        grain_entities = (
            _as_string_list(grain.get("entities"))
            if isinstance(grain, dict)
            else []
        )
        if layer == "DWS" or grain_entities:
            if grain_entities:
                missing_entities = [
                    entity for entity in grain_entities
                    if entity not in defined_entities
                ]
                record(
                    table_name,
                    "METADATA_GRAIN_ENTITIES_DEFINED",
                    not missing_entities,
                    "grain.entities引用已定义实体",
                    (
                        "全部已定义"
                        if not missing_entities
                        else f"未定义实体: {missing_entities}"
                    ),
                    {
                        "grain_entities": grain_entities,
                        "defined_entities": sorted(defined_entities),
                    },
                    "",
                    f"grain.entities未定义={missing_entities}",
                )
            else:
                record(
                    table_name,
                    "METADATA_GRAIN_ENTITIES_PRESENT",
                    False,
                    "DWS模型配置grain.entities",
                    "未配置",
                    {"layer": layer},
                    "missing",
                    "缺少grain.entities",
                )

        if business_domain_config:
            if _data_domain_applies(layer):
                raw_domain = metadata.get("data_domain")
                normalized_domain = business_domain_config.normalize_domain(
                    raw_domain
                )
                if raw_domain in (None, ""):
                    ok = False
                    reason = "missing"
                    message = "data_domain未配置"
                elif not business_domain_config.is_valid_domain(
                    normalized_domain
                ):
                    ok = False
                    reason = "not_in_dictionary"
                    message = f"data_domain不在字典中: {raw_domain}"
                elif not _type_def_valid(
                    nc,
                    "DATA_DOMAIN_ID",
                    normalized_domain,
                ):
                    ok = False
                    reason = "type_mismatch"
                    message = f"data_domain不符合类型定义: {raw_domain}"
                else:
                    ok = True
                    reason = ""
                    message = ""
                record(
                    table_name,
                    "METADATA_DATA_DOMAIN_VALID",
                    ok,
                    "data_domain存在且符合业务字典",
                    normalized_domain if ok else str(raw_domain or "未配置"),
                    {
                        "raw_value": raw_domain,
                        "normalized_value": normalized_domain,
                    },
                    reason,
                    message,
                    SEVERITY_LOW if reason == "missing" else None,
                )

            if _business_area_applies(layer):
                raw_area = metadata.get("business_area")
                normalized_area = (
                    business_domain_config.normalize_business_area(raw_area)
                )
                if raw_area in (None, ""):
                    ok = False
                    reason = "missing"
                    message = "business_area未配置"
                elif not business_domain_config.is_valid_business_area(
                    normalized_area
                ):
                    ok = False
                    reason = "not_in_dictionary"
                    message = f"business_area不在字典中: {raw_area}"
                elif not _type_def_valid(
                    nc,
                    "BUSINESS_AREA_CODE",
                    normalized_area,
                ):
                    ok = False
                    reason = "type_mismatch"
                    message = f"business_area不符合类型定义: {raw_area}"
                else:
                    ok = True
                    reason = ""
                    message = ""
                record(
                    table_name,
                    "METADATA_BUSINESS_AREA_VALID",
                    ok,
                    "business_area存在且符合业务字典",
                    normalized_area if ok else str(raw_area or "未配置"),
                    {
                        "raw_value": raw_area,
                        "normalized_value": normalized_area,
                    },
                    reason,
                    message,
                    SEVERITY_LOW if reason == "missing" else None,
                )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="metadata_health",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=METADATA_HEALTH_RULES,
    )


def _sort_naming_violations(violations: list) -> list:
    return sorted(
        violations,
        key=lambda item: (
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            if isinstance(item, dict)
            else str(item)
        ),
    )


def _naming_check_result(
    passed: int,
    total: int,
    violations: list,
    diagnostics: list | None = None,
) -> dict:
    result = {
        "passed": passed,
        "total": total,
        "violations": _sort_naming_violations(violations),
    }
    if diagnostics:
        result["diagnostics"] = sorted(
            diagnostics,
            key=lambda item: str(item.get("actual", "")),
        )
    return result


def _metric_rule_name(nc, *rule_names: str) -> str | None:
    metric_rules = getattr(nc, "metric_rules", {}) or {}
    for rule_name in rule_names:
        if metric_rules.get(rule_name):
            return rule_name
    return None


def _metric_rule_label(nc, fallback: str, rule_name: str | None) -> str:
    if not rule_name:
        return fallback
    labels = getattr(nc, "metric_rule_labels", {}) or {}
    return labels.get(rule_name) or fallback


def _check_atomic_metric_name(metric_name: str, nc) -> bool:
    rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    if not rule_name:
        return True
    return nc.match_metric_rule(metric_name, rule_name) is not None


def _check_derived_metric_name(metric_name: str, nc) -> bool:
    rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    if not rule_name:
        return False
    return nc.match_metric_rule(metric_name, rule_name) is not None


def _type_def_valid(nc, type_name: str, value: str) -> bool:
    type_def = getattr(nc, "types", {}).get(type_name)
    return type_def.validate(value) if type_def else True


def _metric_names_from_raw(raw_metrics) -> list[str]:
    if not isinstance(raw_metrics, list):
        return []

    names = []
    for metric in raw_metrics:
        if isinstance(metric, dict):
            name = str(metric.get("name") or "").strip()
        else:
            name = str(metric or "").strip()
        if name:
            names.append(name)
    return names


def _atomic_metric_names_for_table(
    table: dict,
    model_metadata: dict | None,
) -> list[str]:
    raw_metrics = table.get("atomic_metrics")
    if raw_metrics is None and model_metadata:
        metadata = model_metadata.get(table["name"], {})
        raw_metrics = metadata.get("atomic_metrics")
    return _metric_names_from_raw(raw_metrics)


def _derived_metric_names_for_table(
    table: dict,
    model_metadata: dict | None,
) -> list[str]:
    raw_metrics = table.get("derived_metrics")
    if raw_metrics is None and model_metadata:
        metadata = model_metadata.get(table["name"], {})
        raw_metrics = metadata.get("derived_metrics")
    return _metric_names_from_raw(raw_metrics)


def _short_table_name(table_name: str) -> str:
    name = str(table_name or "").strip().rstrip(";")
    if not name:
        return ""
    name = name.replace("`", "").replace('"', "")
    return name.split(".")[-1].strip()


def _relative_asset_path(project_dir: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(project_dir).as_posix()
    except ValueError:
        return file_path.as_posix()


def _display_file_path(project_dir: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(project_dir.parent).as_posix()
    except ValueError:
        return file_path.as_posix()


def _ddl_declared_table_name(ddl_path: Path) -> str:
    text = ddl_path.read_text(encoding="utf-8")
    try:
        table_def = parse_create_table(text)
        if table_def:
            return _short_table_name(table_def.short_name)
    except Exception:
        pass

    match = re.search(
        r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:`?\w+`?\.)?`?(\w+)`?",
        text,
        flags=re.IGNORECASE,
    )
    return _short_table_name(match.group(1)) if match else ""


def _ddl_table_for_naming(ddl_path: Path,
                          model_metadata: dict | None) -> dict | None:
    try:
        table_def = parse_create_table(ddl_path.read_text(encoding="utf-8"))
    except Exception:
        table_def = None
    if not table_def:
        return None

    name = _short_table_name(table_def.short_name)
    if not name:
        return None

    metadata = model_metadata.get(name, {}) if model_metadata else {}
    layer = str(metadata.get("layer") or "OTHER").upper()
    return dict(
        name=name,
        full_name=table_def.full_name,
        layer=layer,
        columns=[
            {"name": column.name, "type": column.data_type}
            for column in table_def.columns
        ],
    )


def _tables_for_naming(
    tables: list,
    project_dir: Path | None,
    model_metadata: dict | None,
) -> list:
    current_tables = []
    for table in tables:
        name = str(table.get("name") or "")
        metadata = model_metadata.get(name, {}) if model_metadata else {}
        current = dict(table)
        if metadata.get("layer"):
            current["layer"] = str(metadata["layer"]).upper()
        current_tables.append(current)

    if not project_dir:
        return current_tables

    ddl_dir = Path(project_dir) / "ddl"
    if not ddl_dir.exists():
        return []

    ddl_tables = {}

    for ddl_path in sorted(ddl_dir.glob("*.sql")):
        table = _ddl_table_for_naming(
            ddl_path,
            model_metadata,
        )
        if table:
            ddl_tables[table["name"]] = table

    return sorted(
        ddl_tables.values(),
        key=lambda item: str(item.get("name") or ""),
    )


def _target_table_sql(target_expr) -> str:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    return target_expr.sql(dialect="doris")


def _extract_task_output_tables(task_path: Path) -> set[str]:
    text = task_path.read_text(encoding="utf-8")
    targets = set()
    try:
        statements = sqlglot.parse(text, dialect="doris")
    except Exception:
        statements = []

    for stmt in statements:
        if isinstance(stmt, exp.Insert):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Update):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Delete):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif (
            isinstance(stmt, exp.Create)
            and stmt.args.get("expression") is not None
        ):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Merge):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.TruncateTable):
            for table in stmt.expressions:
                targets.add(_short_table_name(_target_table_sql(table)))

    if targets:
        return {target for target in targets if target}

    write_patterns = [
        r"\bINSERT\s+(?:OVERWRITE\s+TABLE|INTO)\s+"
        r"(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bUPDATE\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bDELETE\s+FROM\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bTRUNCATE\s+(?:TABLE\s+)?(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bMERGE\s+INTO\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:`?\w+`?\.)?`?(\w+)`?\s+AS\b",
    ]
    for pattern in write_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            target = _short_table_name(match.group(1))
            if target:
                targets.add(target)
    return targets


def _expected_task_table(task_path: Path) -> str:
    stem = task_path.stem
    if task_path.parent.name == "full_refresh" and stem.endswith("_full_refresh"):
        return stem[: -len("_full_refresh")]
    return stem


def _source_file_keys(source_file: str) -> set[str]:
    source = str(source_file or "").replace("\\", "/").strip()
    if not source:
        return set()
    return {source}


def _lineage_targets_by_source_file(
    edges: list | None,
    indirect_edges: list | None,
) -> dict[str, set[str]]:
    targets = defaultdict(set)

    for edge in edges or []:
        target = _short_table_name(_table_from_node(str(edge.get("target") or "")))
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
            targets[key].add(target)

    for edge in indirect_edges or []:
        target = _short_table_name(edge.get("target_table", ""))
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
            targets[key].add(target)

    return dict(targets)


def build_asset_catalog(
    tables: list,
    model_metadata: dict | None,
    project_dir: Path | None,
    *,
    edges: list | None = None,
    indirect_edges: list | None = None,
) -> dict:
    """Collect project asset facts without assigning scores."""
    project_path = Path(project_dir) if project_dir else None
    assets = {}

    def ensure_asset(name: str) -> dict:
        short_name = _short_table_name(name)
        if short_name not in assets:
            assets[short_name] = dict(
                name=short_name,
                layer="OTHER",
                columns=[],
                lineage_table=None,
                ddl=None,
                model=None,
                tasks=[],
            )
        return assets[short_name]

    for table in tables or []:
        name = _short_table_name(table.get("name", ""))
        if not name:
            continue
        asset = ensure_asset(name)
        asset["lineage_table"] = dict(table)
        asset["layer"] = str(table.get("layer") or "OTHER").upper()
        asset["columns"] = list(table.get("columns") or [])

    for name, metadata in (model_metadata or {}).items():
        if not isinstance(metadata, dict):
            continue
        declared_name = _short_table_name(metadata.get("name") or name)
        if not declared_name:
            continue
        asset = ensure_asset(declared_name)
        asset["model"] = dict(
            exists=True,
            path=None,
            file_stem=None,
            declared_name=declared_name,
            metadata=metadata,
        )
        if metadata.get("layer"):
            asset["layer"] = str(metadata["layer"]).upper()

    if project_path:
        ddl_dir = project_path / "ddl"
        if ddl_dir.exists():
            for ddl_path in sorted(ddl_dir.glob("*.sql")):
                table = _ddl_table_for_naming(ddl_path, model_metadata)
                declared_name = (
                    table["name"] if table
                    else _ddl_declared_table_name(ddl_path)
                )
                if not declared_name:
                    continue
                asset = ensure_asset(declared_name)
                columns = list(table.get("columns") or []) if table else []
                asset["ddl"] = dict(
                    exists=True,
                    path=ddl_path,
                    file_stem=ddl_path.stem,
                    declared_name=declared_name,
                    columns=columns,
                )
                asset["columns"] = columns
                if table and table.get("layer") != "OTHER":
                    asset["layer"] = table["layer"]

        models_dir = project_path / "models"
        if models_dir.exists():
            for model_path in sorted(models_dir.glob("*.yaml")):
                try:
                    raw = (
                        yaml.safe_load(
                            model_path.read_text(encoding="utf-8")
                        )
                        or {}
                    )
                except yaml.YAMLError:
                    raw = {}
                if not isinstance(raw, dict):
                    raw = {}
                declared_name = _short_table_name(
                    raw.get("name") or model_path.stem
                )
                asset = ensure_asset(declared_name)
                metadata = (
                    (model_metadata or {}).get(declared_name)
                    or raw
                )
                asset["model"] = dict(
                    exists=True,
                    path=model_path,
                    file_stem=model_path.stem,
                    declared_name=declared_name,
                    metadata=metadata,
                )
                if metadata.get("layer"):
                    asset["layer"] = str(metadata["layer"]).upper()

        tasks_dir = project_path / "tasks"
        lineage_targets = _lineage_targets_by_source_file(
            edges,
            indirect_edges,
        )
        task_facts = []
        if tasks_dir.exists():
            for task_path in sorted(tasks_dir.rglob("*.sql")):
                expected = _expected_task_table(task_path)
                outputs = _extract_task_output_tables(task_path)
                relative_source = task_path.relative_to(tasks_dir).as_posix()
                fact = dict(
                    path=task_path,
                    file=_relative_asset_path(project_path, task_path),
                    expected_table=expected,
                    output_tables=outputs,
                    lineage_targets=lineage_targets.get(
                        relative_source,
                        set(),
                    ),
                    is_full_refresh=(
                        task_path.parent.name == "full_refresh"
                    ),
                )
                task_facts.append(fact)
                linked_names = set(outputs)
                if not linked_names:
                    linked_names.add(expected)
                for table_name in linked_names:
                    ensure_asset(table_name)["tasks"].append(fact)
        else:
            task_facts = []
    else:
        task_facts = []

    return dict(
        project_dir=project_path,
        tables=assets,
        tasks=task_facts,
    )


def _asset_requires_task(asset: dict) -> bool:
    model = asset.get("model") or {}
    metadata = model.get("metadata") or {}
    layer = str(asset.get("layer") or "OTHER").upper()
    materialized = str(
        (metadata.get("config") or {}).get("materialized") or ""
    ).lower()
    return layer != "ODS" and materialized != "source"


def score_asset_completeness(asset_catalog: dict) -> dict:
    """Score DDL/model/task closure and task-lineage consistency."""
    checks = []

    def record(
        asset_name: str,
        rule: str,
        ok: bool,
        message: str,
        *,
        target_type: str = "table",
        expected: str | None = None,
        actual: str | None = None,
        evidence: dict | None = None,
    ) -> None:
        checks.append(
            make_check(
                rule_id=ASSET_RULE_IDS[rule],
                target_type=target_type,
                target=asset_name,
                passed=ok,
                expected=expected or rule,
                actual=actual or ("满足" if ok else message),
                evidence=evidence,
                message="" if ok else message,
            )
        )

    assets = asset_catalog.get("tables") or {}
    for name, asset in sorted(assets.items()):
        has_ddl = bool(asset.get("ddl"))
        has_model = bool(asset.get("model"))
        tasks = asset.get("tasks") or []
        has_output_task = any(
            name in task.get("output_tables", set())
            for task in tasks
        )

        if has_ddl:
            record(
                name,
                ASSET_RULE_DDL_MODEL,
                has_model,
                "缺少Model",
                expected="DDL表存在Model",
                actual="已存在Model" if has_model else "未找到Model",
            )
            if _asset_requires_task(asset):
                record(
                    name,
                    ASSET_RULE_DDL_TASK,
                    has_output_task,
                    "缺少产出该表的Task",
                    expected="非ODS且非source物化表存在产出Task",
                    actual=(
                        "已存在产出Task"
                        if has_output_task
                        else "未找到产出Task"
                    ),
                )

        if has_model:
            record(
                name,
                ASSET_RULE_MODEL_DDL,
                has_ddl,
                "缺少DDL",
                expected="Model存在对应DDL表",
                actual="已存在DDL" if has_ddl else "未找到DDL",
            )

    task_outputs = sorted({
        output
        for task in asset_catalog.get("tasks") or []
        for output in task.get("output_tables", set())
    })
    for output in task_outputs:
        asset = assets.get(output, {})
        record(
            output,
            ASSET_RULE_TASK_DDL,
            bool(asset.get("ddl")),
            "Task产出表缺少DDL",
            expected="Task产出表存在DDL",
            actual="已存在DDL" if asset.get("ddl") else "未找到DDL",
        )
        record(
            output,
            ASSET_RULE_TASK_MODEL,
            bool(asset.get("model")),
            "Task产出表缺少Model",
            expected="Task产出表存在Model",
            actual="已存在Model" if asset.get("model") else "未找到Model",
        )

    for task in asset_catalog.get("tasks") or []:
        outputs = set(task.get("output_tables") or set())
        lineage_targets = set(task.get("lineage_targets") or set())
        actual = (
            f"实际产出={sorted(outputs)}，"
            f"血缘目标={sorted(lineage_targets)}"
        )
        record(
            task["file"],
            ASSET_RULE_TASK_LINEAGE,
            bool(outputs) and lineage_targets == outputs,
            actual,
            target_type="task",
            expected="Task血缘目标与实际产出一致",
            actual=actual,
            evidence={
                "outputs": sorted(outputs),
                "lineage_targets": sorted(lineage_targets),
            },
        )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="asset_completeness",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=ASSET_COMPLETENESS_RULES,
    )


def _empty_file_score() -> dict:
    return dict(
        passed=0,
        total=0,
        checks=[],
    )


def _record_file_check(
    result: dict,
    rule: str,
    file_path: Path,
    project_dir: Path,
    expected: str,
    actual,
    passed: bool,
) -> None:
    result["total"] += 1
    if passed:
        result["passed"] += 1

    if isinstance(actual, (set, list, tuple)):
        actual_display = ", ".join(sorted(str(item) for item in actual)) or "未解析"
    else:
        actual_display = str(actual or "未解析")

    display_file = _display_file_path(project_dir, file_path)
    result["checks"].append(
        make_check(
            rule_id=NAMING_FILE_RULE_IDS[rule],
            target_type="file",
            target=display_file,
            passed=passed,
            expected=rule,
            actual=(
                "一致"
                if passed
                else f"期望: {expected} | 实际: {actual_display}"
            ),
            evidence={
                "file": display_file,
                "expected": expected,
                "actual": actual_display,
            },
            message="" if passed else f"{rule}不一致",
            issue={
                "remediation": {
                    "related_files": [display_file],
                }
            } if not passed else None,
        )
    )



def _score_file_naming_conventions(
    asset_catalog: dict,
) -> dict:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return _empty_file_score()

    result = _empty_file_score()
    for asset in asset_catalog.get("tables", {}).values():
        ddl = asset.get("ddl")
        if ddl:
            _record_file_check(
                result,
                FILE_RULE_DDL,
                ddl["path"],
                project_dir,
                ddl["file_stem"],
                ddl["declared_name"],
                ddl["file_stem"] == ddl["declared_name"],
            )

        model = asset.get("model")
        if model and model.get("path"):
            _record_file_check(
                result,
                FILE_RULE_MODEL_NAME,
                model["path"],
                project_dir,
                model["file_stem"],
                model["declared_name"],
                model["file_stem"] == model["declared_name"],
            )

    for task in asset_catalog.get("tasks") or []:
        _record_file_check(
            result,
            FILE_RULE_TASK_SQL,
            task["path"],
            project_dir,
            task["expected_table"],
            task["output_tables"],
            task["output_tables"] == {task["expected_table"]},
        )

    return result


def _prepare_naming_context(
    tables: list,
    nc,
    model_metadata: dict | None,
    business_domain_config,
    project_dir: Path | None,
    edges: list | None,
    indirect_edges: list | None,
    asset_catalog: dict | None,
) -> dict:
    catalog = asset_catalog or build_asset_catalog(
        tables,
        model_metadata,
        project_dir,
        edges=edges,
        indirect_edges=indirect_edges,
    )
    if catalog.get("project_dir"):
        naming_tables = [
            dict(
                name=name,
                layer=asset.get("layer", "OTHER"),
                columns=asset.get("columns") or [],
            )
            for name, asset in catalog.get("tables", {}).items()
            if asset.get("ddl")
        ]
    else:
        naming_tables = _tables_for_naming(tables, None, model_metadata)

    atomic_rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    derived_rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    return dict(
        nc=nc,
        model_metadata=model_metadata or {},
        business_domain_config=business_domain_config,
        asset_catalog=catalog,
        middle=[
            table
            for table in naming_tables
            if table["layer"] in {"DWD", "DWS", "DIM"}
        ],
        atomic_rule_name=atomic_rule_name,
        derived_rule_name=derived_rule_name,
        atomic_rule_label=_metric_rule_label(
            nc,
            ATOMIC_METRIC_RULE_NAME,
            atomic_rule_name,
        ),
        derived_rule_label=_metric_rule_label(
            nc,
            DERIVED_METRIC_RULE_NAME,
            derived_rule_name,
        ),
    )


def _valid_business_metadata_value(
    metadata: dict,
    field_name: str,
    type_name: str,
    nc,
    business_domain_config,
) -> str:
    raw_value = metadata.get(field_name)
    if raw_value in (None, "") or not business_domain_config:
        return ""
    if field_name == "data_domain":
        normalized = business_domain_config.normalize_domain(raw_value)
        in_dictionary = business_domain_config.is_valid_domain(normalized)
    else:
        normalized = business_domain_config.normalize_business_area(raw_value)
        in_dictionary = business_domain_config.is_valid_business_area(
            normalized
        )
    if not in_dictionary or not _type_def_valid(nc, type_name, normalized):
        return ""
    return normalized


def _score_table_semantic_metadata(
    table_name: str,
    layer: str,
    table_name_valid: bool,
    context: dict,
) -> tuple[dict, list[tuple[str, int, int]]]:
    result = _naming_check_result(0, 0, [])
    summary_checks = []
    if not table_name_valid:
        return result, summary_checks

    metadata = context["model_metadata"].get(table_name)
    business_config = context["business_domain_config"]
    if not isinstance(metadata, dict) or not business_config:
        return result, summary_checks

    checks = [
        (
            _data_domain_applies(layer),
            "data_domain",
            "DATA_DOMAIN_ID",
            "表名DATA_DOMAIN_ID与model.data_domain一致",
        ),
        (
            _business_area_applies(layer),
            "business_area",
            "BUSINESS_AREA_CODE",
            "表名BUSINESS_AREA_CODE与model.business_area一致",
        ),
    ]
    violations = []
    passed = 0
    total = 0
    for applies, field_name, type_name, rule_name in checks:
        if not applies:
            continue
        expected = _valid_business_metadata_value(
            metadata,
            field_name,
            type_name,
            context["nc"],
            business_config,
        )
        if not expected:
            continue
        actual = _table_name_type_values(
            table_name,
            layer,
            context["nc"],
            type_name,
        )
        ok = actual == [expected]
        total += 1
        passed += int(ok)
        summary_checks.append((rule_name, int(ok), 1))
        if not ok:
            violations.append(
                f"表名{type_name}={actual}，"
                f"model.{field_name}={expected}"
            )

    return _naming_check_result(passed, total, violations), summary_checks


def _score_middle_table(table: dict, context: dict) -> dict:
    nc = context["nc"]
    model_metadata = context["model_metadata"]
    name = table["name"]
    layer = table["layer"]
    columns = table.get("columns", [])
    summary_checks = []

    table_name_valid = _check_table_name_any_template(name, layer, nc)
    table_passed = int(table_name_valid)
    table_total = 1
    table_violations = []
    table_diagnostics = []
    if not table_name_valid:
        diagnostic = {
            "check": "table_template",
            **_table_name_diagnostic(name, layer, nc),
        }
        table_violations.append({
            "code": "table_template",
            "rule_id": "NAMING_TABLE_TEMPLATE",
            "expected": "表名符合所在层级命名模板",
            "actual": name,
            "message": f"{name} 不符合 {layer} 层表名模板",
            "evidence": diagnostic,
        })
        table_diagnostics.append(diagnostic)
    summary_checks.append(("表名符合规范模板", table_passed, 1))

    max_length = _table_name_max_length(name, layer, nc)
    if max_length is not None:
        length_ok = _check_table_name_length(name, layer, nc)
        table_total += 1
        table_passed += int(length_ok)
        summary_checks.append((
            f"表名长度 <= {max_length}",
            int(length_ok),
            1,
        ))
        if not length_ok:
            diagnostic = {
                "check": "table_max_length",
                "actual": name,
                "layer": layer,
                "passed": False,
                "expected": {"max_length": max_length},
                "actual_length": len(name),
            }
            table_violations.append({
                "code": "table_max_length",
                "rule_id": "NAMING_TABLE_MAX_LENGTH",
                "expected": f"表名长度 <= {max_length}",
                "actual": {
                    "name": name,
                    "length": len(name),
                },
                "message": f"表名长度 {len(name)} 超过配置上限 {max_length}",
                "evidence": diagnostic,
            })
            table_diagnostics.append(diagnostic)

    atomic_names = (
        _atomic_metric_names_for_table(table, model_metadata)
        if context["atomic_rule_name"]
        else []
    )
    atomic_violations = [
        metric for metric in atomic_names
        if not _check_atomic_metric_name(metric, nc)
    ]
    atomic_passed = len(atomic_names) - len(atomic_violations)
    if context["atomic_rule_name"]:
        summary_checks.append((
            context["atomic_rule_label"],
            atomic_passed,
            len(atomic_names),
        ))

    derived_names = (
        _derived_metric_names_for_table(table, model_metadata)
        if context["derived_rule_name"]
        else []
    )
    derived_violations = [
        metric for metric in derived_names
        if not _check_derived_metric_name(metric, nc)
    ]
    derived_passed = len(derived_names) - len(derived_violations)
    if context["derived_rule_name"]:
        summary_checks.append((
            context["derived_rule_label"],
            derived_passed,
            len(derived_names),
        ))

    metric_columns = set(atomic_names) | set(derived_names)
    column_violations = []
    column_diagnostics = []
    column_passed = 0
    column_total = 0
    for column in columns:
        column_name = column["name"]
        if column_name in metric_columns:
            continue
        column_total += 1
        ok, _matched = _check_column_name(column_name, nc)
        column_passed += int(ok)
        if not ok:
            column_violations.append(column_name)
            column_diagnostics.append(
                _column_name_diagnostic(column_name, nc)
            )
    summary_checks.append(("列名总计", column_passed, column_total))

    dws_entity_checks = (
        _score_dws_entity_name(
            name,
            layer,
            nc,
            model_metadata,
        )
        if table_name_valid
        else _naming_check_result(0, 0, [])
    )
    summary_checks.append((
        DWS_ENTITY_RULE_NAME,
        dws_entity_checks["passed"],
        dws_entity_checks["total"],
    ))
    dim_entity_checks = (
        _score_dim_entity_name(
            name,
            layer,
            nc,
            model_metadata,
        )
        if table_name_valid
        else _naming_check_result(0, 0, [])
    )
    summary_checks.append((
        DIM_ENTITY_RULE_NAME,
        dim_entity_checks["passed"],
        dim_entity_checks["total"],
    ))
    semantic_checks, semantic_summary = _score_table_semantic_metadata(
        name,
        layer,
        table_name_valid,
        context,
    )
    summary_checks.extend(semantic_summary)

    passed = (
        table_passed
        + column_passed
        + atomic_passed
        + derived_passed
        + dws_entity_checks["passed"]
        + dim_entity_checks["passed"]
        + semantic_checks["passed"]
    )
    total = (
        table_total
        + column_total
        + len(atomic_names)
        + len(derived_names)
        + dws_entity_checks["total"]
        + dim_entity_checks["total"]
        + semantic_checks["total"]
    )
    return dict(
        table=name,
        layer=layer,
        table_checks=_naming_check_result(
            table_passed,
            table_total,
            table_violations,
            table_diagnostics,
        ),
        column_checks=_naming_check_result(
            column_passed,
            column_total,
            column_violations,
            column_diagnostics,
        ),
        atomic_metric_checks=_naming_check_result(
            atomic_passed,
            len(atomic_names),
            atomic_violations,
        ),
        derived_metric_checks=_naming_check_result(
            derived_passed,
            len(derived_names),
            derived_violations,
        ),
        dws_entity_checks=dws_entity_checks,
        dim_entity_checks=dim_entity_checks,
        semantic_metadata_checks=semantic_checks,
        score=round(passed / total * 100, 1) if total else 100.0,
        _passed=passed,
        _total=total,
        _summary_checks=summary_checks,
    )


def _naming_issue_context(context: dict, table: str) -> dict:
    related_files = _related_files_for_table(context["asset_catalog"], table)
    return {
        "remediation": {
            "related_files": related_files,
        }
    } if related_files else {}


def _naming_violation_by_code(violations: list, code: str) -> dict | None:
    for violation in violations:
        if isinstance(violation, dict) and violation.get("code") == code:
            return violation
    return None


def _naming_violation_evidence(
    violation: dict | None,
    default: dict,
) -> dict:
    if not violation:
        return default
    evidence = dict(default)
    evidence.update(violation.get("evidence") or {})
    return evidence


def _build_naming_checks(
    table_results: list[dict],
    file_result: dict,
    context: dict,
) -> list[dict]:
    checks = []
    for result in table_results:
        table = result["table"]
        layer = result["layer"]
        issue_context = _naming_issue_context(context, table)

        table_violations = result["table_checks"]["violations"]
        template_violation = _naming_violation_by_code(
            table_violations,
            "table_template",
        )
        checks.append(
            make_check(
                rule_id="NAMING_TABLE_TEMPLATE",
                target_type="table",
                target=table,
                passed=template_violation is None,
                expected="表名符合所在层级命名模板",
                actual=(
                    "符合"
                    if template_violation is None
                    else template_violation["message"]
                ),
                evidence=_naming_violation_evidence(
                    template_violation,
                    {"layer": layer},
                ),
                message=(
                    template_violation["message"]
                    if template_violation else ""
                ),
                issue=issue_context if template_violation else None,
            )
        )

        if result["table_checks"]["total"] > 1:
            length_violation = _naming_violation_by_code(
                table_violations,
                "table_max_length",
            )
            checks.append(
                make_check(
                    rule_id="NAMING_TABLE_MAX_LENGTH",
                    target_type="table",
                    target=table,
                    passed=length_violation is None,
                    expected="表名长度不超过配置上限",
                    actual=(
                        f"长度={len(table)}"
                        if length_violation is None
                        else length_violation["message"]
                    ),
                    evidence=_naming_violation_evidence(
                        length_violation,
                        {"layer": layer, "actual_length": len(table)},
                    ),
                    message=(
                        length_violation["message"]
                        if length_violation else ""
                    ),
                    issue=issue_context if length_violation else None,
                )
            )

        column_checks = result.get("column_checks", {})
        if column_checks.get("total", 0) > 0:
            violations = column_checks.get("violations") or []
            checks.append(
                make_check(
                    rule_id="NAMING_COLUMN_NAME",
                    target_type="table",
                    target=table,
                    passed=not violations,
                    expected="所有非指标字段符合字段命名规则",
                    actual=(
                        "全部合规"
                        if not violations
                        else f"不合规字段: {violations}"
                    ),
                    evidence={
                        "layer": layer,
                        "violations": violations,
                        "checked_count": column_checks.get("total", 0),
                    },
                    message=(
                        f"不合规字段: {', '.join(violations)}"
                        if violations else ""
                    ),
                    issue=issue_context if violations else None,
                )
            )

        metric_specs = [
            (
                result.get("atomic_metric_checks", {}),
                "NAMING_ATOMIC_METRIC",
                "所有原子指标符合指标命名规则",
                "不合规原子指标",
                _atomic_metric_names_for_table(
                    {"name": table},
                    context["model_metadata"],
                ),
            ),
            (
                result.get("derived_metric_checks", {}),
                "NAMING_DERIVED_METRIC",
                "所有派生指标符合指标命名规则",
                "不合规派生指标",
                _derived_metric_names_for_table(
                    {"name": table},
                    context["model_metadata"],
                ),
            ),
        ]
        for check_result, rule_id, expected, label, metric_names in metric_specs:
            if check_result.get("total", 0) <= 0:
                continue
            violations = check_result.get("violations") or []
            for metric_name in metric_names:
                failed = metric_name in violations
                checks.append(
                    make_check(
                        rule_id=rule_id,
                        target_type="metric",
                        target=f"{table}.{metric_name}",
                        passed=not failed,
                        expected=expected,
                        actual=(
                            "合规"
                            if not failed
                            else f"{label}: {metric_name}"
                        ),
                        evidence={
                            "table": table,
                            "layer": layer,
                            "metric": metric_name,
                        },
                        message=f"{label}: {metric_name}" if failed else "",
                        issue=issue_context if failed else None,
                    )
                )

        alignment_specs = [
            (
                result.get("dws_entity_checks", {}),
                "NAMING_DWS_ENTITY_ALIGNMENT",
                "DWS表名实体包含于grain.entities",
            ),
            (
                result.get("dim_entity_checks", {}),
                "NAMING_DIM_ENTITY_ALIGNMENT",
                "DIM表名实体等于主实体",
            ),
            (
                result.get("semantic_metadata_checks", {}),
                "NAMING_SEMANTIC_METADATA_ALIGNMENT",
                "表名语义段与模型元数据一致",
            ),
        ]
        for check_result, rule_id, expected in alignment_specs:
            if check_result.get("total", 0) <= 0:
                continue
            violations = check_result.get("violations") or []
            checks.append(
                make_check(
                    rule_id=rule_id,
                    target_type="table",
                    target=table,
                    passed=not violations,
                    expected=expected,
                    actual="一致" if not violations else "; ".join(violations),
                    evidence={"layer": layer, "violations": violations},
                    message="; ".join(violations) if violations else "",
                    issue=issue_context if violations else None,
                )
            )

    checks.extend(file_result.get("checks") or [])
    return checks


def _build_final_naming_result(
    table_results: list[dict],
    file_result: dict,
    context: dict,
) -> dict:
    total_passed = sum(result["_passed"] for result in table_results)
    total_checks = sum(result["_total"] for result in table_results)
    total_passed += file_result["passed"]
    total_checks += file_result["total"]
    checks = _build_naming_checks(table_results, file_result, context)
    return finalize_dimension(
        dimension="naming",
        score=round(total_passed / total_checks * 100, 1)
        if total_checks else 100.0,
        checks=checks,
        rules=NAMING_RULES,
        summary={
            "file_checks": dict(
                passed=file_result["passed"],
                total=file_result["total"],
            ),
        },
    )


def score_naming_conventions(
    tables: list,
    nc,
    model_metadata: dict | None = None,
    business_domain_config=None,
    *,
    project_dir: Path | None = None,
    edges: list | None = None,
    indirect_edges: list | None = None,
    asset_catalog: dict | None = None,
) -> dict:
    context = _prepare_naming_context(
        tables,
        nc,
        model_metadata,
        business_domain_config,
        project_dir,
        edges,
        indirect_edges,
        asset_catalog,
    )
    table_results = [
        _score_middle_table(table, context)
        for table in context["middle"]
    ]
    file_result = _score_file_naming_conventions(
        context["asset_catalog"],
    )
    return _build_final_naming_result(
        table_results,
        file_result,
        context,
    )


# ============================================================
# 报告格式化
# ============================================================


def _fmt_table(
    headers: list[str],
    rows: list[list],
    col_widths: list[int],
) -> str:
    sep = "─" * (sum(col_widths) + len(col_widths) * 3 + 1)
    line = "│"
    for h, w in zip(headers, col_widths):
        line += f" {h:<{w}} │"
    lines = [line, f"├{sep}┤"]
    for row in rows:
        line = "│"
        for val, w in zip(row, col_widths):
            line += f" {str(val):<{w}} │"
        lines.append(line)
    return "\n".join(lines)


def _related_files_for_table(asset_catalog: dict, table_name: str) -> list[str]:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return []
    asset = (asset_catalog.get("tables") or {}).get(table_name) or {}
    files = []
    ddl = asset.get("ddl") or {}
    if ddl.get("path"):
        files.append(_display_file_path(project_dir, ddl["path"]))
    for task in sorted(asset.get("tasks") or [], key=lambda item: item["file"]):
        files.append(_display_file_path(project_dir, task["path"]))
    model = asset.get("model") or {}
    if model.get("path"):
        files.append(_display_file_path(project_dir, model["path"]))
    return files


def generate_report(scores: dict, weights: dict, project: str) -> str:
    parts = []
    sep = "─" * 62

    overall_score = scores["overall_score"]
    parts.append(
        f"╔{'═' * 62}╗\n"
        f"║{'数据集市中间层评估报告':^62}║\n"
        f"║{'─' * 62}║\n"
        f"║{'项目: ' + project:<24}{'总体评分:':>18}{overall_score:>6.1f} / 100{' ' * 2}║\n"
        f"╠{'═' * 62}╣")

    dims = [
        ("复用度", "reuse"),
        ("链路长度(中间层)", "depth"),
        ("架构合理性", "architecture"),
        ("命名规范", "naming"),
        ("资产完整性", "asset_completeness"),
        ("模型元数据健康度", "metadata_health"),
        ("代码质量", "code_quality"),
    ]
    dimensions = scores["dimensions"]
    for label, key in dims:
        metric = dimensions[key]
        score = metric["score"]
        w = weights[key] * 100
        parts.append(
            f"║ {label:<12} 评分:{score:>5.1f}  权重:{w:>2.0f}%{' ' * 24}║")

    parts.append(f"╚{'═' * 62}╝")

    headers = ["规则ID", "规则", "严重度", "通过", "总计", "合规率"]
    col_w = [32, 28, 8, 6, 6, 8]
    for label, key in dims:
        dimension = dimensions[key]
        parts.append(f"\n{'=' * 62}")
        parts.append(f"【{label}】评分: {dimension['score']}")
        parts.append(f"{'=' * 62}")

        rows = []
        for rule_id, counts in sorted(dimension["rule_summary"].items()):
            rows.append([
                rule_id,
                counts["name"],
                counts["severity"],
                str(counts["pass_count"]),
                str(counts["total"]),
                f"{counts['pct']}%",
            ])
        if not rows:
            rows.append(["(无检查项)", "", "", "0", "0", "0%"])
        parts.append(_fmt_table(headers, rows, col_w))

        issues = dimension["issues"]
        if issues:
            parts.append("\n  问题项:")
            for issue in issues[:30]:
                target = issue["target"]
                remediation = issue.get("remediation") or {}
                parts.append(
                    "    "
                    f"[{issue['severity']}] {issue['title']} | "
                    f"{target['type']}:{target['name']} | "
                    f"{issue['message']}"
                )
                if remediation.get("summary"):
                    parts.append(f"      建议: {remediation['summary']}")
            if len(issues) > 30:
                parts.append(f"    ... (共{len(issues)}个)")
        else:
            parts.append("\n  无问题项")
        parts.append(sep)

    parts.append(f"\n{'=' * 62}")
    return "\n".join(parts)


# ============================================================
# 主入口
# ============================================================


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
    architecture_raw = score_architecture_health(
        tables,
        edges,
        indirect_edges,
        llm_results,
        model_metadata,
        business_domain_config,
    )
    architecture_score = architecture_raw
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

    result = dict(
        project=project,
        overall_score=overall_score,
        weights=weights,
        dimensions=output_dimensions,
    )

    return result


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
