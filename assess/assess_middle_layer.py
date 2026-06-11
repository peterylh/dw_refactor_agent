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
from assess.entity_metadata import (
    defined_entity_codes,
    grain_entity_codes,
    grain_key_columns,
    model_entities,
    primary_entity_codes,
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
    "reuse": 0.2,
    "depth": 0.2,
    "architecture": 0.2,
    "naming": 0.2,
    "asset_completeness": 0.1,
    "metadata_health": 0.1,
}

# 加权违规率配置: 严重度 → 权重
SEVERITY_WEIGHT = {"严重": 4, "高": 3, "中": 2, "低": 1}
# 每表扣分上限 (cap)，防止单张高频表拖垮整体评分
PER_TABLE_CAP = 4
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
REPAIR_RULE_TABLE_MAX_LENGTH = "TABLE_NAME_MAX_LENGTH"
REPAIR_RULE_DWS_ENTITY = "DWS_ENTITY_ALIGNMENT"
REPAIR_RULE_DIM_ENTITY = "DIM_ENTITY_ALIGNMENT"
REPAIR_RULE_SEMANTIC_METADATA = "TABLE_SEMANTIC_METADATA_ALIGNMENT"
REPAIR_RULE_ATOMIC_METRIC = "ATOMIC_METRIC"
REPAIR_RULE_DERIVED_METRIC = "DERIVED_METRIC"
REPAIR_FILE_RULE_REFS = {
    FILE_RULE_DDL: "DDL_FILE_NAME",
    FILE_RULE_MODEL_NAME: "MODEL_FILE_NAME",
    FILE_RULE_TASK_SQL: "TASK_OUTPUT_NAME",
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


def build_metric_result(metric: dict, display_score: float | None = None) -> dict:
    raw = metric["score"]
    display = raw if display_score is None else display_score
    result = dict(metric)
    del result["score"]
    result["raw"] = raw
    result["display"] = display
    return result


# 依赖违规定义: 通过 src/tgt 层序号差自动判定
# rank_diff = src_rank - tgt_rank
# 正数 → 反向依赖 (高层→低层, 数据倒流)
# 0     → 同层依赖
# -1    → 相邻上层 (正常, ODS→DWD, DWD→DWS, DWS→ADS)
# -2    → 跳过一层 (DWD→ADS 或 ODS→DWS; DIM→ADS 为合理维度引用)
# -3    → 跳过两层 (ODS→ADS)

ARCH_VIOLATION_RULES = [
    # (rank_diff, description, severity, penalty)
    (3, "反向依赖: 跳过三层(ADS→ODS)", "严重", 40),
    (2, "反向依赖: 跳过两层", "严重", 30),
    (1, "反向依赖: 跳过一层", "高", 20),
    (0, "同层依赖(非必要)", "低", 2),
    (-2, "跳过中间层(DWD→ADS 或 ODS→DWS)", "低", 5),
    (-3, "跳过两层(ODS→ADS)", "中", 10),
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

    rows = []
    for t in middle:
        name = t["name"]
        cnt = len(downstream_map.get(name, set()))
        score = min(100, cnt / REUSE_FULL_SCORE_AT * 100)
        rows.append(
            dict(table=name,
                 layer=t["layer"],
                 downstream_count=cnt,
                 score=round(score, 1)))

    avg_score = round(sum(r["score"]
                          for r in rows) / len(rows), 1) if rows else 0.0
    avg_reuse = (round(
        sum(r["downstream_count"]
            for r in rows) / len(rows), 2) if rows else 0.0)

    dist = dict(
        high=sum(1 for r in rows
                 if r["downstream_count"] >= REUSE_FULL_SCORE_AT),
        medium=sum(1 for r in rows
                   if 1 <= r["downstream_count"] < REUSE_FULL_SCORE_AT),
        none=sum(1 for r in rows if r["downstream_count"] == 0),
    )

    return dict(
        score=avg_score,
        avg_reuse_count=avg_reuse,
        details=rows,
        distribution=dist,
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

    rows = []
    for t in ads:
        name = t["name"]
        depth = _max_middle_depth(name, upstream, table_layers)
        score = _depth_to_score(depth)
        rows.append(dict(table=name, max_middle_depth=depth, score=score))

    avg_score = round(sum(r["score"]
                          for r in rows) / len(rows), 1) if rows else 100.0
    avg_depth = round(sum(r["max_middle_depth"]
                          for r in rows) / len(rows), 2) if rows else 0.0

    return dict(score=avg_score, avg_middle_depth=avg_depth, details=rows)


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

    violations = []
    # 每表累计权重 (cap 前)
    table_weight = defaultdict(int)

    # ---- 规则检测: 跨层/反向/跳层依赖 (归属 target 表) ----
    for (src, tgt), files in table_edges.items():
        src_layer = table_layers.get(src, "OTHER")
        tgt_layer = table_layers.get(tgt, "OTHER")
        src_rank = layer_rank(src_layer)
        tgt_rank = layer_rank(tgt_layer)
        if src_rank < 0 or tgt_rank < 0:
            continue

        rank_diff = src_rank - tgt_rank

        # ADS 面向应用输出，直接引用公共维度表补充属性是合理的数据集市建模方式。
        if src_layer == "DIM" and tgt_layer == "ADS":
            continue

        # 正常相邻上层 → 跳过
        if rank_diff == -1:
            continue

        for diff, desc, severity, _penalty in ARCH_VIOLATION_RULES:
            if rank_diff == diff:
                weight = SEVERITY_WEIGHT[severity]
                violations.append(
                    dict(
                        source=f"{src}({src_layer})",
                        target=f"{tgt}({tgt_layer})",
                        severity=severity,
                        weight=weight,
                        description=desc,
                        source_file=", ".join(sorted(files)),
                        belongs_to=tgt,
                    ))
                table_weight[tgt] += weight

    # ---- LLM 检测: 分层配置疑似错误 & 维度表位置不当 (归属被评估表本身) ----
    if llm_results:
        cls_map = {r.table_name: r for r in llm_results}
        table_map = {t["name"]: t for t in tables}
        for name, res in cls_map.items():
            layer = table_map[name]["layer"] if name in table_map else "OTHER"

            if res.is_violating_declared_layer:
                weight = SEVERITY_WEIGHT["中"]
                violations.append(dict(
                    source=f"{name}({layer})",
                    target=f"{name}({res.inferred_layer})",
                    severity="中",
                    weight=weight,
                    description=(
                        "分层配置疑似错误(LLM): "
                        f"配置层={layer}, 推断层={res.inferred_layer}"
                    ),
                    source_file="",
                    source_type="llm",
                    belongs_to=name,
                ))
                table_weight[name] += weight

            if res.table_type == "dimension" and layer == "DWD":
                weight = SEVERITY_WEIGHT["低"]
                violations.append(dict(
                    source=f"{name}({layer})",
                    target="建议: DIM",
                    severity="低",
                    weight=weight,
                    description="维度表位置不当(LLM): 维度表应置于 DIM 层",
                    source_file="",
                    source_type="llm",
                    belongs_to=name,
                ))
                table_weight[name] += weight

            declared_type = _declared_table_type(model_metadata, name)
            if declared_type and declared_type != res.table_type:
                weight = SEVERITY_WEIGHT["中"]
                violations.append(dict(
                    source=f"{name}({declared_type})",
                    target=f"{name}({res.table_type})",
                    severity="中",
                    weight=weight,
                    description=(
                        "表类型配置疑似错误(LLM): "
                        f"配置类型={declared_type}, 推断类型={res.table_type}"
                    ),
                    source_file="",
                    source_type="llm",
                    belongs_to=name,
                ))
                table_weight[name] += weight

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
                if inferred_domain and inferred_domain != declared_domain:
                    severity = "中" if declared_domain else "低"
                    weight = SEVERITY_WEIGHT[severity]
                    violations.append(dict(
                        source=(
                            f"{name}(data_domain="
                            f"{declared_domain or '未配置'})"
                        ),
                        target=f"{name}(data_domain={inferred_domain})",
                        severity=severity,
                        weight=weight,
                        description=(
                            "数据域配置疑似错误(LLM): "
                            f"配置={declared_domain or '未配置'}, "
                            f"推断={inferred_domain}"
                        ),
                        source_file="",
                        source_type="llm",
                        belongs_to=name,
                    ))
                    table_weight[name] += weight

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
                if inferred_area and inferred_area != declared_area:
                    severity = "中" if declared_area else "低"
                    weight = SEVERITY_WEIGHT[severity]
                    violations.append(dict(
                        source=(
                            f"{name}(business_area="
                            f"{declared_area or '未配置'})"
                        ),
                        target=f"{name}(business_area={inferred_area})",
                        severity=severity,
                        weight=weight,
                        description=(
                            "业务板块配置疑似错误(LLM): "
                            f"配置={declared_area or '未配置'}, 推断={inferred_area}"
                        ),
                        source_file="",
                        source_type="llm",
                        belongs_to=name,
                    ))
                    table_weight[name] += weight

    # 每表扣分上限 (cap)
    capped_total = 0
    table_capped = {}
    for tbl, w in table_weight.items():
        capped = min(w, PER_TABLE_CAP)
        table_capped[tbl] = capped
        capped_total += capped

    # 加权违规率评分
    score = max(0, round(100 * (1 - capped_total / table_count), 1)) if table_count else 100.0

    summary = defaultdict(int)
    for v in violations:
        summary[v["severity"]] += 1

    return dict(
        score=score,
        table_count=table_count,
        capped_total=capped_total,
        table_capped=table_capped,
        violation_summary=dict(summary),
        violations=violations,
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


def _metadata_check_result(
    passed: int,
    total: int,
    violations: list[dict],
    rule_summary: dict[str, dict],
    details: list[dict],
) -> dict:
    return dict(
        score=round(passed / total * 100, 1) if total else 100.0,
        passed=passed,
        total=total,
        violations=violations,
        rule_summary=rule_summary,
        details=details,
    )


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
        return _metadata_check_result(0, 0, [], {}, [])

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
    passed = 0
    total = 0
    violations = []
    details = []
    rule_summary = defaultdict(lambda: dict(pass_count=0, total=0, pct=0.0))

    def record(
        table_name: str,
        rule: str,
        ok: bool,
        message: str = "",
        reason: str = "",
    ) -> None:
        nonlocal passed, total
        total += 1
        rule_summary[rule]["total"] += 1
        if ok:
            passed += 1
            rule_summary[rule]["pass_count"] += 1
        else:
            violation = dict(table=table_name, rule=rule, message=message)
            if reason:
                violation["reason"] = reason
            violations.append(violation)
            details.append(violation)

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
                "entities.primary.code已配置",
                bool(entity_codes),
                "缺少entities.primary.code",
                "missing",
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
                        "entities.key_columns存在于表字段",
                        not missing_keys,
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
                        "entities.relationship.from_entity等于主实体",
                        from_entity == primary_code,
                        (
                            f"entities[{entity_code}]"
                            f".relationship.from_entity={from_entity}，"
                            f"primary_entity={primary_code}"
                        ),
                    )
                if primary_code and entity_code:
                    record(
                        table_name,
                        "entities.code不同于主实体",
                        entity_code != primary_code,
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
                    "grain.keys存在于表字段",
                    not missing_grain_keys,
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
                    "grain.entities有实体定义",
                    not missing_entities,
                    f"grain.entities未定义={missing_entities}",
                )
            else:
                record(
                    table_name,
                    "grain.entities有实体定义",
                    False,
                    "缺少grain.entities",
                    "missing",
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
                    "data_domain配置有效",
                    ok,
                    message,
                    reason,
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
                    "business_area配置有效",
                    ok,
                    message,
                    reason,
                )

    summary = {}
    for rule, counts in rule_summary.items():
        total_count = counts["total"]
        pass_count = counts["pass_count"]
        summary[rule] = dict(
            pass_count=pass_count,
            total=total_count,
            pct=round(pass_count / total_count * 100, 1)
            if total_count else 0,
        )
    return _metadata_check_result(passed, total, violations, summary, details)


def _naming_check_result(
    passed: int,
    total: int,
    violations: list,
    diagnostics: list | None = None,
) -> dict:
    result = {
        "passed": passed,
        "total": total,
        "violations": sorted(violations),
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
    passed = 0
    total = 0
    details = []
    rule_summary = defaultdict(lambda: dict(pass_count=0, total=0, pct=0.0))

    def record(asset_name: str, rule: str, ok: bool, message: str) -> None:
        nonlocal passed, total
        total += 1
        rule_summary[rule]["total"] += 1
        if ok:
            passed += 1
            rule_summary[rule]["pass_count"] += 1
        else:
            details.append(
                dict(asset=asset_name, rule=rule, message=message)
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
            record(name, ASSET_RULE_DDL_MODEL, has_model, "缺少Model")
            if _asset_requires_task(asset):
                record(
                    name,
                    ASSET_RULE_DDL_TASK,
                    has_output_task,
                    "缺少产出该表的Task",
                )

        if has_model:
            record(name, ASSET_RULE_MODEL_DDL, has_ddl, "缺少DDL")

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
        )
        record(
            output,
            ASSET_RULE_TASK_MODEL,
            bool(asset.get("model")),
            "Task产出表缺少Model",
        )

    for task in asset_catalog.get("tasks") or []:
        outputs = set(task.get("output_tables") or set())
        lineage_targets = set(task.get("lineage_targets") or set())
        record(
            task["file"],
            ASSET_RULE_TASK_LINEAGE,
            bool(outputs) and lineage_targets == outputs,
            (
                f"实际产出={sorted(outputs)}，"
                f"血缘目标={sorted(lineage_targets)}"
            ),
        )

    summary = {}
    for rule, counts in rule_summary.items():
        rule_total = counts["total"]
        rule_passed = counts["pass_count"]
        summary[rule] = dict(
            pass_count=rule_passed,
            total=rule_total,
            pct=round(rule_passed / rule_total * 100, 1)
            if rule_total else 0,
        )
    return dict(
        score=round(passed / total * 100, 1) if total else 100.0,
        passed=passed,
        total=total,
        rule_summary=summary,
        details=details,
    )


def _empty_file_score() -> dict:
    return dict(
        passed=0,
        total=0,
        rule_summary={},
        details=[],
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

    summary = result["rule_summary"].setdefault(
        rule,
        {"pass_count": 0, "total": 0},
    )
    summary["total"] += 1
    if passed:
        summary["pass_count"] += 1
        return

    if isinstance(actual, (set, list, tuple)):
        actual_display = ", ".join(sorted(str(item) for item in actual)) or "未解析"
    else:
        actual_display = str(actual or "未解析")

    result["details"].append(
        dict(
            file=_display_file_path(project_dir, file_path),
            rule=rule,
            expected=expected,
            actual=actual_display,
        )
    )


def _finalize_file_score(result: dict) -> dict:
    for summary in result["rule_summary"].values():
        total = summary["total"]
        summary["pct"] = (
            round(summary["pass_count"] / total * 100, 1)
            if total else 0
        )

    result["rule_summary"][FILE_RULE_TOTAL] = dict(
        pass_count=result["passed"],
        total=result["total"],
        pct=round(result["passed"] / result["total"] * 100, 1)
        if result["total"] else 0,
    )
    return result


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

    return _finalize_file_score(result)


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
        table_violations.append("违反: 表名符合规范模板")
        table_diagnostics.append({
            "check": "table_template",
            **_table_name_diagnostic(name, layer, nc),
        })
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
            table_violations.append(f"违反: 表名长度 <= {max_length}")
            table_diagnostics.append({
                "check": "table_max_length",
                "actual": name,
                "layer": layer,
                "passed": False,
                "expected": {"max_length": max_length},
                "actual_length": len(name),
            })

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


def _build_rule_summary(
    table_results: list[dict],
    context: dict,
    file_result: dict,
) -> dict:
    counts = defaultdict(lambda: dict(pass_count=0, total=0))
    required_rules = [
        "表名符合规范模板",
        "列名总计",
        DWS_ENTITY_RULE_NAME,
        DIM_ENTITY_RULE_NAME,
    ]
    if context["atomic_rule_name"]:
        required_rules.append(context["atomic_rule_label"])
    if context["derived_rule_name"]:
        required_rules.append(context["derived_rule_label"])
    for rule in required_rules:
        counts[rule]

    for result in table_results:
        for rule, passed, total in result["_summary_checks"]:
            counts[rule]["pass_count"] += passed
            counts[rule]["total"] += total

    summary = {
        rule: dict(
            pass_count=value["pass_count"],
            total=value["total"],
            pct=round(value["pass_count"] / value["total"] * 100, 1)
            if value["total"] else 0,
        )
        for rule, value in counts.items()
    }
    summary.update(file_result["rule_summary"])
    return summary


def _build_final_naming_result(
    table_results: list[dict],
    rule_summary: dict,
    file_result: dict,
    context: dict,
) -> dict:
    total_passed = sum(result["_passed"] for result in table_results)
    total_checks = sum(result["_total"] for result in table_results)
    total_passed += file_result["passed"]
    total_checks += file_result["total"]
    repair_payload = _build_naming_repair_payload(
        table_results,
        file_result,
        context,
    )
    details = []
    for result in table_results:
        clean = {
            key: value
            for key, value in result.items()
            if not key.startswith("_")
        }
        details.append(_strip_parser_diagnostics(clean))
    return dict(
        score=round(total_passed / total_checks * 100, 1)
        if total_checks else 100.0,
        details=details,
        rule_summary=rule_summary,
        file_checks=dict(
            passed=file_result["passed"],
            total=file_result["total"],
        ),
        file_details=file_result["details"],
        rule_catalog=repair_payload["rule_catalog"],
        repair_items=repair_payload["repair_items"],
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
    rule_summary = _build_rule_summary(
        table_results,
        context,
        file_result,
    )
    return _build_final_naming_result(
        table_results,
        rule_summary,
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


def _best_failed_attempt(attempts: list[dict]) -> dict:
    failed_attempts = [
        attempt for attempt in attempts if not attempt.get("passed")
    ]
    if not failed_attempts:
        return {}
    return max(
        failed_attempts,
        key=lambda item: (
            item.get("failure", {}).get("consumed_chars", -1),
            -len(str(item.get("failure", {}).get("actual_remaining", ""))),
        ),
    )


def _failure_for_repair(failure: dict) -> dict:
    keys = [
        "code",
        "position",
        "expected",
        "actual",
        "actual_remaining",
    ]
    return {
        key: failure[key]
        for key in keys
        if key in failure and failure[key] not in (None, "")
    }


def _catalog_patterns_from_failure(failure: dict) -> list[str]:
    expected = failure.get("expected")
    if not isinstance(expected, list):
        return []
    code = str(failure.get("code") or "")
    if "pattern" not in code:
        return []
    return [str(item) for item in expected]


def _catalog_allowed_values_from_failure(failure: dict) -> list[str]:
    expected = failure.get("expected")
    if not isinstance(expected, list):
        return []
    code = str(failure.get("code") or "")
    if "allowed" not in code:
        return []
    return [str(item) for item in expected]


def _add_rule_catalog_entry(
    catalog: dict,
    rule_ref: str,
    *,
    target_type: str,
    summary: str,
    expression: str | None = None,
    failure: dict | None = None,
    constraints: dict | None = None,
) -> None:
    entry = catalog.setdefault(
        rule_ref,
        {
            "target_type": target_type,
            "summary": summary or rule_ref,
        },
    )
    if expression and "expression" not in entry:
        entry["expression"] = expression
    patterns = _catalog_patterns_from_failure(failure or {})
    if patterns:
        entry["patterns"] = patterns
    allowed_values = _catalog_allowed_values_from_failure(failure or {})
    if allowed_values:
        entry["allowed_values"] = allowed_values
    clean_constraints = {
        key: value
        for key, value in (constraints or {}).items()
        if value not in (None, "")
    }
    if clean_constraints:
        entry["constraints"] = clean_constraints


def _rule_ref_from_attempt(attempt: dict, fallback: str) -> str:
    rule = attempt.get("rule") or {}
    return str(rule.get("name") or fallback)


def _summary_from_attempt(attempt: dict, fallback: str) -> str:
    rule = attempt.get("rule") or {}
    return str(rule.get("description") or fallback)


def _expected_from_attempt(attempt: dict, target_type: str) -> str:
    failure = attempt.get("failure") or {}
    expected = failure.get("expected")
    expression = attempt.get("expression")
    if target_type == "column" and isinstance(expected, list):
        return "匹配 " + " 或 ".join(str(item) for item in expected)
    if target_type == "table" and expression:
        return f"表达式 {expression}"
    if isinstance(expected, list):
        return "取值为 " + ", ".join(str(item) for item in expected)
    if expected not in (None, ""):
        return f"期望 {expected}"
    if expression:
        return f"表达式 {expression}"
    return ""


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


def _repair_item(
    *,
    target_type: str,
    table: str,
    layer: str,
    obj: str,
    rule_ref: str,
    problem: str,
    expected: str,
    failure: dict | None,
    fix_scope: list[str],
    related_files: list[str],
) -> dict:
    item = dict(
        target_type=target_type,
        table=table,
        layer=layer,
        object=obj,
        rule_ref=rule_ref,
        problem=problem,
        expected=expected,
        fix_scope=fix_scope,
        related_files=related_files,
    )
    clean_failure = _failure_for_repair(failure or {})
    if clean_failure:
        item["failure"] = clean_failure
    return item


def _repair_from_parser_diagnostic(
    *,
    diagnostic: dict,
    target_type: str,
    table: str,
    layer: str,
    fallback_rule: str,
    object_name: str,
    catalog: dict,
    asset_catalog: dict,
) -> dict | None:
    attempt = _best_failed_attempt(diagnostic.get("attempts") or [])
    if not attempt:
        return None
    rule_ref = _rule_ref_from_attempt(attempt, fallback_rule)
    summary = _summary_from_attempt(attempt, rule_ref)
    failure = attempt.get("failure") or {}
    _add_rule_catalog_entry(
        catalog,
        rule_ref,
        target_type=target_type,
        summary=summary,
        expression=attempt.get("expression"),
        failure=failure,
        constraints=(attempt.get("rule") or {}).get("constraints"),
    )
    object_label = {
        "table": "表名",
        "column": "字段名",
    }.get(target_type, "对象")
    return _repair_item(
        target_type=target_type,
        table=table,
        layer=layer,
        obj=object_name,
        rule_ref=rule_ref,
        problem=f"{object_label}不符合 {summary}",
        expected=_expected_from_attempt(attempt, target_type),
        failure=failure,
        fix_scope=["ddl", "tasks", "models"],
        related_files=_related_files_for_table(asset_catalog, table),
    )


def _repair_from_table_max_length(
    *,
    diagnostic: dict,
    table: str,
    layer: str,
    catalog: dict,
    asset_catalog: dict,
) -> dict:
    expected = diagnostic.get("expected") or {}
    max_length = expected.get("max_length")
    _add_rule_catalog_entry(
        catalog,
        REPAIR_RULE_TABLE_MAX_LENGTH,
        target_type="table",
        summary=f"表名长度 <= {max_length}",
        constraints={"max_length": max_length},
    )
    return _repair_item(
        target_type="table",
        table=table,
        layer=layer,
        obj=table,
        rule_ref=REPAIR_RULE_TABLE_MAX_LENGTH,
        problem=f"表名长度超过 {max_length}",
        expected=f"长度 <= {max_length}",
        failure={
            "code": "max_length_exceeded",
            "actual": diagnostic.get("actual"),
            "expected": max_length,
        },
        fix_scope=["ddl", "tasks", "models"],
        related_files=_related_files_for_table(asset_catalog, table),
    )


def _metric_rule_ref(rule_name: str | None, fallback: str) -> str:
    if rule_name == "atomic":
        return REPAIR_RULE_ATOMIC_METRIC
    if rule_name == "derived":
        return REPAIR_RULE_DERIVED_METRIC
    return str(rule_name or fallback)


def _add_simple_catalog_entry(
    catalog: dict,
    rule_ref: str,
    target_type: str,
    summary: str,
) -> None:
    _add_rule_catalog_entry(
        catalog,
        rule_ref,
        target_type=target_type,
        summary=summary,
    )


def _build_naming_repair_payload(
    table_results: list[dict],
    file_result: dict,
    context: dict,
) -> dict:
    catalog = {}
    repair_items = []
    asset_catalog = context["asset_catalog"]
    for result in table_results:
        table = result["table"]
        layer = result["layer"]
        related_files = _related_files_for_table(asset_catalog, table)

        for diagnostic in result["table_checks"].get("diagnostics", []):
            if diagnostic.get("check") == "table_max_length":
                repair_items.append(
                    _repair_from_table_max_length(
                        diagnostic=diagnostic,
                        table=table,
                        layer=layer,
                        catalog=catalog,
                        asset_catalog=asset_catalog,
                    )
                )
                continue
            item = _repair_from_parser_diagnostic(
                diagnostic=diagnostic,
                target_type="table",
                table=table,
                layer=layer,
                fallback_rule=f"TABLE_{layer}",
                object_name=table,
                catalog=catalog,
                asset_catalog=asset_catalog,
            )
            if item:
                repair_items.append(item)

        for diagnostic in result["column_checks"].get("diagnostics", []):
            item = _repair_from_parser_diagnostic(
                diagnostic=diagnostic,
                target_type="column",
                table=table,
                layer=layer,
                fallback_rule="COLUMN_DEFAULT",
                object_name=diagnostic.get("actual") or "",
                catalog=catalog,
                asset_catalog=asset_catalog,
            )
            if item:
                repair_items.append(item)

        atomic_rule = _metric_rule_ref(
            context.get("atomic_rule_name"),
            REPAIR_RULE_ATOMIC_METRIC,
        )
        for metric in result.get("atomic_metric_checks", {}).get(
            "violations", []
        ):
            _add_simple_catalog_entry(
                catalog,
                atomic_rule,
                "atomic_metric",
                context.get("atomic_rule_label") or ATOMIC_METRIC_RULE_NAME,
            )
            repair_items.append(
                _repair_item(
                    target_type="atomic_metric",
                    table=table,
                    layer=layer,
                    obj=metric,
                    rule_ref=atomic_rule,
                    problem="原子指标名不符合命名规则",
                    expected=context.get("atomic_rule_label") or "",
                    failure={"code": "metric_rule_mismatch"},
                    fix_scope=["models", "ddl", "tasks"],
                    related_files=related_files,
                )
            )

        derived_rule = _metric_rule_ref(
            context.get("derived_rule_name"),
            REPAIR_RULE_DERIVED_METRIC,
        )
        for metric in result.get("derived_metric_checks", {}).get(
            "violations", []
        ):
            _add_simple_catalog_entry(
                catalog,
                derived_rule,
                "derived_metric",
                context.get("derived_rule_label") or DERIVED_METRIC_RULE_NAME,
            )
            repair_items.append(
                _repair_item(
                    target_type="derived_metric",
                    table=table,
                    layer=layer,
                    obj=metric,
                    rule_ref=derived_rule,
                    problem="派生指标名不符合命名规则",
                    expected=context.get("derived_rule_label") or "",
                    failure={"code": "metric_rule_mismatch"},
                    fix_scope=["models", "ddl", "tasks"],
                    related_files=related_files,
                )
            )

        model_checks = [
            (
                result.get("dws_entity_checks", {}),
                REPAIR_RULE_DWS_ENTITY,
                "DWS表名实体需要包含于grain.entities",
            ),
            (
                result.get("dim_entity_checks", {}),
                REPAIR_RULE_DIM_ENTITY,
                "DIM表名实体需要等于entities.primary.code",
            ),
            (
                result.get("semantic_metadata_checks", {}),
                REPAIR_RULE_SEMANTIC_METADATA,
                "表名语义段需要与模型元数据一致",
            ),
        ]
        for check, rule_ref, summary in model_checks:
            violations = check.get("violations") or []
            if not violations:
                continue
            _add_simple_catalog_entry(
                catalog,
                rule_ref,
                "model_metadata",
                summary,
            )
            for violation in violations:
                repair_items.append(
                    _repair_item(
                        target_type="model_metadata",
                        table=table,
                        layer=layer,
                        obj=table,
                        rule_ref=rule_ref,
                        problem=summary,
                        expected=violation,
                        failure={"code": "metadata_alignment_mismatch"},
                        fix_scope=["models"],
                        related_files=related_files,
                    )
                )

    for detail in file_result.get("details") or []:
        rule = detail["rule"]
        rule_ref = REPAIR_FILE_RULE_REFS.get(rule, rule)
        _add_simple_catalog_entry(catalog, rule_ref, "file", rule)
        repair_items.append(
            _repair_item(
                target_type="file",
                table=str(detail.get("expected") or ""),
                layer="",
                obj=detail["file"],
                rule_ref=rule_ref,
                problem=f"{rule}不一致",
                expected=(
                    f"期望 {detail.get('expected')}，"
                    f"实际 {detail.get('actual')}"
                ),
                failure={"code": "file_name_mismatch"},
                fix_scope=["file_path"],
                related_files=[detail["file"]],
            )
        )

    return {
        "rule_catalog": dict(sorted(catalog.items())),
        "repair_items": repair_items,
    }


def _strip_parser_diagnostics(value):
    if isinstance(value, dict):
        return {
            key: _strip_parser_diagnostics(child)
            for key, child in value.items()
            if key != "diagnostics"
        }
    if isinstance(value, list):
        return [_strip_parser_diagnostics(child) for child in value]
    return value


def _format_naming_repair_item(item: dict) -> str:
    obj = item.get("object") or item.get("table") or ""
    problem = item.get("problem") or ""
    expected = item.get("expected") or ""
    files = item.get("related_files") or []
    location = f"；文件 {', '.join(files[:3])}" if files else ""
    return f"{item.get('target_type')}: {obj} - {problem}；{expected}{location}"


def generate_report(scores: dict, weights: dict, project: str) -> str:
    parts = []
    sep = "─" * 62

    # ============================================================
    # 头部 & 总体评分
    # ============================================================
    overall_raw = scores["overall_raw"]
    overall_display = scores["overall_display"]
    parts.append(
        f"╔{'═' * 62}╗\n"
        f"║{'数据集市中间层评估报告':^62}║\n"
        f"║{'─' * 62}║\n"
        f"║{'项目: ' + project:<24}{'总体评分(展示):':>18}{overall_display:>6.1f} / 100{' ' * 2}║\n"
        f"║{'':<24}{'总体评分(原始):':>18}{overall_raw:>6.1f} / 100{' ' * 2}║\n"
        f"╠{'═' * 62}╣")

    dims = [
        ("复用度", "reuse"),
        ("链路长度(中间层)", "depth"),
        ("架构合理性", "architecture"),
        ("命名规范", "naming"),
        ("资产完整性", "asset_completeness"),
        ("模型元数据健康度", "metadata_health"),
    ]
    for label, key in dims:
        metric = scores[key]
        disp = metric["display"]
        raw = metric["raw"]
        w = weights[key] * 100
        parts.append(
            f"║ {label:<12} 展示:{disp:>5.1f} 原始:{raw:>5.1f}  权重:{w:>2.0f}%{' ' * 11}║")

    parts.append(f"╚{'═' * 62}╝")

    # ============================================================
    # 复用度
    # ============================================================
    reuse = scores["reuse"]
    parts.append(f"\n{'=' * 62}")
    parts.append(
        f"【复用度】评分(展示/原始): {reuse['display']} / {reuse['raw']}  |  平均复用次数: {reuse['avg_reuse_count']}")
    parts.append(f"{'=' * 62}")

    headers = ["表名", "层", "下游引用", "得分"]
    col_w = [34, 6, 10, 6]
    rows = []
    for r in reuse["details"]:
        rows.append([
            r["table"], r["layer"],
            str(r["downstream_count"]),
            str(r["score"])
        ])
    parts.append(_fmt_table(headers, rows, col_w))

    d = reuse["distribution"]
    parts.append(f"\n  分布: 高复用(≥{REUSE_FULL_SCORE_AT})={d['high']}, "
                 f"一般(1-2)={d['medium']}, 无引用={d['none']}")
    parts.append(sep)

    # ============================================================
    # 链路长度
    # ============================================================
    depth = scores["depth"]
    parts.append(f"\n{'=' * 62}")
    parts.append(
        f"【链路长度(中间层深度)】评分(展示/原始): {depth['display']} / {depth['raw']}  |  平均深度: {depth['avg_middle_depth']}"
    )
    parts.append(f"{'=' * 62}")

    headers = ["ADS表", "最大中间层深度", "得分", "含义"]
    col_w = [38, 14, 6, 20]
    rows = []
    for r in depth["details"]:
        d = r["max_middle_depth"]
        meaning = {2: "DWD+DWS 完整", 1: "仅一层中间", 0: "无中间层"}.get(d)
        if meaning is None:
            meaning = "链路过长"
        rows.append([r["table"], str(d), str(r["score"]), meaning])
    parts.append(_fmt_table(headers, rows, col_w))

    parts.append(f"\n  深度分对照: depth=2→100 (DWD+DWS完整), "
                 f"depth=1→50 (仅一层), depth=0→0, depth≥3→30")
    parts.append(sep)

    # ============================================================
    # 架构合理性
    # ============================================================
    architecture = scores["architecture"]
    parts.append(f"\n{'=' * 62}")
    parts.append(
        f"【架构合理性】评分: {architecture['display']}  |  合规率: {architecture['raw']}")
    parts.append(f"{'=' * 62}")

    # 按规则汇总
    rule_groups = defaultdict(lambda: dict(label="", sev="", weight=0, count=0, tables=set(), has_llm=False))
    for v in architecture["violations"]:
        key = v["description"]
        if key not in rule_groups:
            rule_groups[key] = dict(label=key,
                                    sev=v["severity"],
                                    weight=v["weight"],
                                    count=0,
                                    tables=set(),
                                    has_llm=v.get("source_type") == "llm")
        rule_groups[key]["count"] += 1
        rule_groups[key]["tables"].add(v["belongs_to"])

    headers = ["违规类型", "严重度", "权重", "次数", "涉及表"]
    col_w = [36, 8, 6, 6, 30]
    rows = []
    for g in rule_groups.values():
        label = f"[LLM推断] {g['label']}" if g["has_llm"] else g["label"]
        tables_str = ", ".join(sorted(g["tables"]))
        rows.append([label, g["sev"], str(g["weight"]), str(g["count"]), tables_str])
    if not rows:
        rows.append(["(无违规)", "", "", "", ""])
    parts.append(_fmt_table(headers, rows, col_w))

    tc = architecture["table_count"]
    ct = architecture["capped_total"]
    compliance = max(0, round(100 * (1 - ct / tc), 1)) if tc else 100.0
    parts.append(
        f"\n  Σ(每表 cap 后权重) = {ct}  |  总表数 = {tc}  |  合规率 = {compliance}  |  评分 = {architecture['raw']}")

    if architecture["violations"]:
        parts.append(f"\n  违规详情 (权重/cap后):")
        for v in architecture["violations"]:
            llm_tag = "[LLM推断] " if v.get("source_type") == "llm" else ""
            capped = min(architecture["table_capped"].get(v["belongs_to"], 0), PER_TABLE_CAP)
            parts.append(
                f"    ✗ {llm_tag}{v['source']} → {v['target']}  [{v['severity']}/{v['weight']}]  "
                f"{v['description']}  (归属: {v['belongs_to']}, 该表 cap 后: {capped})"
            )
    else:
        parts.append(f"\n  无违规 ✓")

    if any(v.get("source_type") == "llm" for v in architecture["violations"]):
        parts.append(f"\n  * 分层配置合理性与维度表位置由 LLM 推断，仅供参考，不一定 100% 正确")
    parts.append(sep)

    # ============================================================
    # 资产完整性
    # ============================================================
    asset_completeness = scores["asset_completeness"]
    parts.append(f"\n{'=' * 62}")
    parts.append(
        "【资产完整性】评分(展示/原始): "
        f"{asset_completeness['display']} / "
        f"{asset_completeness['raw']}"
    )
    parts.append(f"{'=' * 62}")

    headers = ["规则", "通过", "总计", "合规率"]
    col_w = [36, 6, 6, 8]
    rows = []
    for desc, counts in sorted(
        asset_completeness["rule_summary"].items()
    ):
        rows.append([
            desc,
            str(counts["pass_count"]),
            str(counts["total"]),
            f"{counts['pct']}%",
        ])
    if not rows:
        rows.append(["(无检查项)", "0", "0", "0%"])
    parts.append(_fmt_table(headers, rows, col_w))

    if asset_completeness["details"]:
        parts.append("\n  缺失或不一致详情:")
        for detail in asset_completeness["details"][:30]:
            parts.append(
                f"    {detail['asset']} | {detail['rule']} | "
                f"{detail['message']}"
            )
        if len(asset_completeness["details"]) > 30:
            parts.append(
                f"    ... (共{len(asset_completeness['details'])}个)"
            )
    else:
        parts.append("\n  无违规 ✓")
    parts.append(sep)

    # ============================================================
    # 模型元数据健康度
    # ============================================================
    metadata_health = scores["metadata_health"]
    parts.append(f"\n{'=' * 62}")
    parts.append(
        f"【模型元数据健康度】评分(展示/原始): {metadata_health['display']} / "
        f"{metadata_health['raw']}"
    )
    parts.append(f"{'=' * 62}")

    headers = ["规则", "通过", "总计", "合规率"]
    col_w = [36, 6, 6, 8]
    rows = []
    for desc, cnts in sorted(metadata_health["rule_summary"].items()):
        rows.append([
            desc,
            str(cnts["pass_count"]),
            str(cnts["total"]),
            f"{cnts['pct']}%",
        ])
    if not rows:
        rows.append(["(无检查项)", "0", "0", "0%"])
    parts.append(_fmt_table(headers, rows, col_w))

    if metadata_health["violations"]:
        parts.append(f"\n  偏离详情:")
        for violation in metadata_health["violations"][:30]:
            parts.append(
                "    "
                f"{violation['table']} | {violation['rule']} | "
                f"{violation['message']}"
            )
        if len(metadata_health["violations"]) > 30:
            parts.append(f"    ... (共{len(metadata_health['violations'])}个)")
    else:
        parts.append(f"\n  无违规 ✓")
    parts.append(sep)

    # ============================================================
    # 命名规范
    # ============================================================
    naming = scores["naming"]
    parts.append(f"\n{'=' * 62}")
    parts.append(f"【命名规范】评分(展示/原始): {naming['display']} / {naming['raw']}")
    parts.append(f"{'=' * 62}")

    # 规则汇总表
    headers = ["规则", "通过", "总计", "合规率"]
    col_w = [36, 6, 6, 8]
    rows = []
    for desc, cnts in sorted(naming["rule_summary"].items()):
        rows.append([
            desc,
            str(cnts["pass_count"]),
            str(cnts["total"]), f"{cnts['pct']}%"
        ])
    parts.append(_fmt_table(headers, rows, col_w))

    # 表级详情 (只显示有违规的表)
    has_viz = False
    repair_items_by_table = defaultdict(list)
    for item in naming.get("repair_items", []):
        table = item.get("table")
        if table:
            repair_items_by_table[table].append(item)
    for r in naming["details"]:
        issues = []
        issues.extend(r["table_checks"]["violations"])
        if r["column_checks"]["violations"]:
            issues.append(
                f"不合规字段: {', '.join(r['column_checks']['violations'][:10])}")
            if len(r["column_checks"]["violations"]) > 10:
                issues[
                    -1] += f"... (共{len(r['column_checks']['violations'])}个)"
        metric_checks = r.get("atomic_metric_checks", {})
        if metric_checks.get("violations"):
            issues.append(
                "不合规原子指标: "
                f"{', '.join(metric_checks['violations'][:10])}"
            )
            if len(metric_checks["violations"]) > 10:
                issues[
                    -1] += f"... (共{len(metric_checks['violations'])}个)"
        derived_metric_checks = r.get("derived_metric_checks", {})
        if derived_metric_checks.get("violations"):
            issues.append(
                "不合规派生指标: "
                f"{', '.join(derived_metric_checks['violations'][:10])}"
            )
            if len(derived_metric_checks["violations"]) > 10:
                issues[
                    -1] += (
                        f"... (共{len(derived_metric_checks['violations'])}个)"
                    )
        dim_entity_checks = r.get("dim_entity_checks", {})
        if dim_entity_checks.get("violations"):
            issues.extend(dim_entity_checks["violations"])
        semantic_checks = r.get("semantic_metadata_checks", {})
        if semantic_checks.get("violations"):
            issues.extend(semantic_checks["violations"])
        if issues:
            if not has_viz:
                parts.append(f"\n  偏离详情:")
                has_viz = True
            parts.append(
                f"\n    {r['table']}({r['layer']}) [得分: {r['score']}]")
            for iss in issues:
                parts.append(f"      {iss}")
            repair_items = repair_items_by_table.get(r["table"], [])
            if repair_items:
                parts.append("      修复任务:")
                for item in repair_items[:8]:
                    parts.append(
                        f"        - {_format_naming_repair_item(item)}")

    file_details = naming.get("file_details") or []
    if file_details:
        if not has_viz:
            parts.append(f"\n  偏离详情:")
            has_viz = True
        parts.append(f"\n    文件命名偏离:")
        for detail in file_details[:20]:
            parts.append(
                "      "
                f"{detail['file']} | {detail['rule']} | "
                f"期望: {detail['expected']} | 实际: {detail['actual']}"
            )
        if len(file_details) > 20:
            parts.append(f"      ... (共{len(file_details)}个)")

    if not has_viz:
        parts.append(f"\n  无违规 ✓")

    parts.append(f"\n{'=' * 62}")
    return "\n".join(parts)


# ============================================================
# 主入口
# ============================================================


def assess(project: str, weights: dict = None) -> dict:
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

    reuse_score = build_metric_result(score_reusability(tables, downstream))
    depth_score = build_metric_result(
        score_lineage_depth(tables, edges, indirect_edges))
    architecture_raw = score_architecture_health(
        tables,
        edges,
        indirect_edges,
        llm_results,
        model_metadata,
        business_domain_config,
    )
    architecture_score = build_metric_result(architecture_raw)
    project_dir = PROJECT_ROOT / PROJECT_CONFIG[project]["dir"]
    asset_catalog = build_asset_catalog(
        tables,
        model_metadata,
        project_dir,
        edges=edges,
        indirect_edges=indirect_edges,
    )
    asset_completeness_score = build_metric_result(
        score_asset_completeness(asset_catalog)
    )
    metadata_health_score = build_metric_result(
        score_metadata_health(
            tables,
            nc,
            model_metadata,
            business_domain_config,
            asset_catalog=asset_catalog,
        )
    )
    naming_score = build_metric_result(
        score_naming_conventions(
            tables,
            nc,
            model_metadata,
            business_domain_config,
            project_dir=project_dir,
            edges=edges,
            indirect_edges=indirect_edges,
            asset_catalog=asset_catalog,
        ))

    overall_raw = round(
        weights["reuse"] * reuse_score["raw"] +
        weights["depth"] * depth_score["raw"] +
        weights["architecture"] * architecture_score["raw"] +
        weights["naming"] * naming_score["raw"] +
        weights["asset_completeness"]
        * asset_completeness_score["raw"] +
        weights["metadata_health"] * metadata_health_score["raw"],
        1,
    )
    overall_display = round(
        weights["reuse"] * reuse_score["display"] +
        weights["depth"] * depth_score["display"] +
        weights["architecture"] * architecture_score["display"] +
        weights["naming"] * naming_score["display"] +
        weights["asset_completeness"]
        * asset_completeness_score["display"] +
        weights["metadata_health"] * metadata_health_score["display"],
        1,
    )

    result = dict(
        project=project,
        overall_raw=overall_raw,
        overall_display=overall_display,
        weights=weights,
        reuse=reuse_score,
        depth=depth_score,
        architecture=architecture_score,
        naming=naming_score,
        asset_completeness=asset_completeness_score,
        metadata_health=metadata_health_score,
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
    args = parser.parse_args()

    weights = dict(
        reuse=args.reuse_weight,
        depth=args.depth_weight,
        architecture=args.architecture_weight,
        naming=args.naming_weight,
        asset_completeness=args.asset_completeness_weight,
        metadata_health=args.metadata_health_weight,
        enable_llm=args.llm,
        no_cache=args.no_cache,
        parallel=args.parallel,
    )

    result = assess(args.project, weights)

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
