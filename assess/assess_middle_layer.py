#!/usr/bin/env python3
"""
数据集市中间层评估工具
评估 DWD/DWS 层的复用度、链路长度(中间层)、架构合理性、命名规范。

用法:
    python assess/assess_middle_layer.py
    python assess/assess_middle_layer.py --project finance_analytics
    python assess/assess_middle_layer.py --output report.json
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
    "reuse": 0.25,
    "depth": 0.25,
    "architecture": 0.25,
    "naming": 0.25,
}

# 加权违规率配置: 严重度 → 权重
SEVERITY_WEIGHT = {"严重": 4, "高": 3, "中": 2, "低": 1}
# 每表扣分上限 (cap)，防止单张高频表拖垮整体评分
PER_TABLE_CAP = 4
ATOMIC_METRIC_RULE_NAME = "原子指标命名 {ACTION_VERB}_{MEASURE_NOUN}"
DERIVED_METRIC_RULE_NAME = (
    "派生指标命名 {TIME_PERIOD}_{MODIFIER...}_{ATOMIC_METRIC}"
)
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
FILE_RULE_DDL = "DDL文件名与建表表名一致"
FILE_RULE_MODEL_TABLE = "Model文件名与表名一致"
FILE_RULE_MODEL_NAME = "Model文件名与模型name一致"
FILE_RULE_TASK_SQL = "Task文件名与产出表一致"
FILE_RULE_TASK_LINEAGE = "Task血缘目标与产出表一致"
FILE_RULE_TOTAL = "文件命名总计"

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


def _has_derived_metric_rule(nc) -> bool:
    return _metric_rule_name(nc, "derived", "derived_metrics") is not None


def _type_def_valid(nc, type_name: str, value: str) -> bool:
    type_def = getattr(nc, "types", {}).get(type_name)
    return type_def.validate(value) if type_def else True


def _score_business_metadata_for_table(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
    business_domain_config,
) -> dict:
    empty_checks = {
        "passed": 0,
        "total": 0,
        "violations": [],
        "data_domain_applicable": False,
        "data_domain_passed": False,
        "business_area_applicable": False,
        "business_area_passed": False,
    }
    if not business_domain_config:
        return empty_checks

    metadata = model_metadata.get(table_name, {}) if model_metadata else {}
    raw_domain = metadata.get("data_domain")
    raw_area = metadata.get("business_area")
    data_domain = business_domain_config.normalize_domain(raw_domain)
    business_area = business_domain_config.normalize_business_area(raw_area)
    checks = {
        "passed": 0,
        "total": 0,
        "violations": [],
        "data_domain_applicable": _data_domain_applies(layer),
        "data_domain_passed": False,
        "business_area_applicable": _business_area_applies(layer),
        "business_area_passed": False,
    }

    if checks["data_domain_applicable"]:
        checks["total"] += 1
        if (
            data_domain
            and business_domain_config.is_valid_domain(data_domain)
            and _type_def_valid(nc, "DATA_DOMAIN_ID", data_domain)
        ):
            checks["passed"] += 1
            checks["data_domain_passed"] = True
        else:
            display_domain = (
                raw_domain if raw_domain not in (None, "") else "未配置"
            )
            checks["violations"].append(
                f"数据域不在字典: {display_domain}"
            )

    if checks["business_area_applicable"]:
        checks["total"] += 1
        if (
            business_area
            and business_domain_config.is_valid_business_area(business_area)
            and _type_def_valid(nc, "BUSINESS_AREA_CODE", business_area)
        ):
            checks["passed"] += 1
            checks["business_area_passed"] = True
        else:
            display_area = raw_area if raw_area not in (None, "") else "未配置"
            checks["violations"].append(
                f"业务板块不在字典: {display_area}"
            )

    return checks


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


def _model_declared_name(model_path: Path) -> str:
    try:
        data = yaml.safe_load(model_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("name") or "").strip()


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
    project_dir: Path | None,
    tables: list,
    edges: list | None,
    indirect_edges: list | None,
) -> dict:
    if not project_dir:
        return _empty_file_score()

    project_dir = Path(project_dir)
    result = _empty_file_score()
    table_names = {str(t.get("name") or "") for t in tables}
    ddl_table_names = set()

    ddl_dir = project_dir / "ddl"
    if ddl_dir.exists():
        for ddl_path in sorted(ddl_dir.glob("*.sql")):
            expected = ddl_path.stem
            actual = _ddl_declared_table_name(ddl_path)
            if actual:
                ddl_table_names.add(actual)
            _record_file_check(
                result,
                FILE_RULE_DDL,
                ddl_path,
                project_dir,
                expected,
                actual,
                actual == expected,
            )
    table_names.update(ddl_table_names)

    models_dir = project_dir / "models"
    if models_dir.exists():
        for model_path in sorted(models_dir.glob("*.yaml")):
            expected = model_path.stem
            actual_name = _model_declared_name(model_path)
            _record_file_check(
                result,
                FILE_RULE_MODEL_TABLE,
                model_path,
                project_dir,
                expected,
                expected if expected in table_names else "未找到同名表",
                expected in table_names,
            )
            _record_file_check(
                result,
                FILE_RULE_MODEL_NAME,
                model_path,
                project_dir,
                expected,
                actual_name,
                actual_name == expected,
            )

    tasks_dir = project_dir / "tasks"
    lineage_targets = _lineage_targets_by_source_file(edges, indirect_edges)
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.rglob("*.sql")):
            expected = _expected_task_table(task_path)
            actual_targets = _extract_task_output_tables(task_path)
            _record_file_check(
                result,
                FILE_RULE_TASK_SQL,
                task_path,
                project_dir,
                expected,
                actual_targets,
                actual_targets == {expected},
            )

            relative_key = task_path.relative_to(tasks_dir).as_posix()
            lineage_targets_for_file = lineage_targets.get(relative_key) or set()
            _record_file_check(
                result,
                FILE_RULE_TASK_LINEAGE,
                task_path,
                project_dir,
                expected,
                lineage_targets_for_file,
                lineage_targets_for_file == {expected},
            )

    return _finalize_file_score(result)


def score_naming_conventions(
    tables: list,
    nc,
    model_metadata: dict | None = None,
    business_domain_config=None,
    *,
    project_dir: Path | None = None,
    edges: list | None = None,
    indirect_edges: list | None = None,
) -> dict:
    middle = [t for t in tables if t["layer"] in ("DWD", "DWS", "DIM")]
    atomic_rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    derived_rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    has_atomic_metric_rule = atomic_rule_name is not None
    has_derived_metric_rule = derived_rule_name is not None
    atomic_rule_label = _metric_rule_label(
        nc, ATOMIC_METRIC_RULE_NAME, atomic_rule_name)
    derived_rule_label = _metric_rule_label(
        nc, DERIVED_METRIC_RULE_NAME, derived_rule_name)

    table_results = []
    total_checks = 0
    total_passed = 0
    business_domain_total = 0
    business_domain_passed = 0
    business_area_total = 0
    business_area_passed = 0
    checked_business_tables = set()

    def record_business_summary(checks: dict) -> None:
        nonlocal business_domain_total
        nonlocal business_domain_passed
        nonlocal business_area_total
        nonlocal business_area_passed
        if not checks["total"]:
            return
        if checks.get("data_domain_applicable"):
            business_domain_total += 1
        if checks.get("data_domain_passed"):
            business_domain_passed += 1
        if checks.get("business_area_applicable"):
            business_area_total += 1
        if checks.get("business_area_passed"):
            business_area_passed += 1

    for t in middle:
        name = t["name"]
        layer = t["layer"]
        columns = t.get("columns", [])

        # --- 表名检查 ---
        tbl_passed = 0
        tbl_total = 1
        tbl_violations = []
        tbl_diagnostics = []
        if _check_table_name_any_template(name, layer, nc):
            tbl_passed += 1
        else:
            tbl_violations.append(f"违反: 表名符合规范模板")
            tbl_diagnostics.append(
                {
                    "check": "table_template",
                    **_table_name_diagnostic(name, layer, nc),
                }
            )
        max_length = _table_name_max_length(name, layer, nc)
        if max_length is not None:
            tbl_total += 1
            if _check_table_name_length(name, layer, nc):
                tbl_passed += 1
            else:
                tbl_violations.append(f"违反: 表名长度 <= {max_length}")
                tbl_diagnostics.append(
                    {
                        "check": "table_max_length",
                        "actual": name,
                        "layer": layer,
                        "passed": False,
                        "expected": {"max_length": max_length},
                        "actual_length": len(name),
                    }
                )

        # --- 原子指标检查 ---
        metric_violations = []
        metric_passed = 0
        metric_names = (
            _atomic_metric_names_for_table(t, model_metadata)
            if has_atomic_metric_rule
            else []
        )
        metric_name_set = set(metric_names)
        metric_total = len(metric_names)
        for metric_name in metric_names:
            if _check_atomic_metric_name(metric_name, nc):
                metric_passed += 1
            else:
                metric_violations.append(metric_name)

        # --- 派生指标检查 ---
        derived_metric_violations = []
        derived_metric_passed = 0
        derived_metric_names = (
            _derived_metric_names_for_table(t, model_metadata)
            if has_derived_metric_rule
            else []
        )
        derived_metric_name_set = set(derived_metric_names)
        derived_metric_total = len(derived_metric_names)
        for metric_name in derived_metric_names:
            if _check_derived_metric_name(metric_name, nc):
                derived_metric_passed += 1
            else:
                derived_metric_violations.append(metric_name)

        # --- 字段检查 ---
        # 指标是列的一种专项类型，已由指标规则检查，不再重复进入通用字段规则。
        col_violations = []
        col_diagnostics = []
        col_passed = 0
        col_total = 0
        checked_metric_name_set = metric_name_set | derived_metric_name_set

        for col in columns:
            col_name = col["name"]
            if col_name in checked_metric_name_set:
                continue
            col_total += 1
            ok, matched = _check_column_name(col_name, nc)
            if ok:
                col_passed += 1
            else:
                col_violations.append(col_name)
                col_diagnostics.append(_column_name_diagnostic(col_name, nc))

        # --- 业务域/板块字典检查 ---
        business_checks = _score_business_metadata_for_table(
            name,
            layer,
            nc,
            model_metadata,
            business_domain_config,
        )
        if business_checks["total"]:
            checked_business_tables.add(name)
            record_business_summary(business_checks)

        table_pass = (
            tbl_passed
            + col_passed
            + metric_passed
            + derived_metric_passed
            + business_checks["passed"]
        )
        table_check = (
            tbl_total
            + col_total
            + metric_total
            + derived_metric_total
            + business_checks["total"]
        )
        table_score = round(table_pass / table_check *
                            100, 1) if table_check else 100.0

        table_results.append(
            dict(
                table=name,
                layer=layer,
                table_checks=_naming_check_result(
                    tbl_passed,
                    tbl_total,
                    tbl_violations,
                    tbl_diagnostics,
                ),
                column_checks=_naming_check_result(
                    col_passed,
                    col_total,
                    col_violations,
                    col_diagnostics,
                ),
                atomic_metric_checks=_naming_check_result(
                    metric_passed,
                    metric_total,
                    metric_violations,
                ),
                derived_metric_checks=_naming_check_result(
                    derived_metric_passed,
                    derived_metric_total,
                    derived_metric_violations,
                ),
                business_metadata_checks=business_checks,
                score=table_score,
            ))

        total_passed += table_pass
        total_checks += table_check

    if business_domain_config:
        for t in tables:
            name = t["name"]
            if name in checked_business_tables:
                continue
            if model_metadata and name not in model_metadata:
                continue
            business_checks = _score_business_metadata_for_table(
                name,
                t["layer"],
                nc,
                model_metadata,
                business_domain_config,
            )
            if not business_checks["total"]:
                continue
            checked_business_tables.add(name)
            record_business_summary(business_checks)
            table_score = round(
                business_checks["passed"] / business_checks["total"] * 100,
                1,
            )
            table_results.append(
                dict(
                    table=name,
                    layer=t["layer"],
                    table_checks=_naming_check_result(0, 0, []),
                    column_checks=_naming_check_result(0, 0, []),
                    atomic_metric_checks=_naming_check_result(0, 0, []),
                    derived_metric_checks=_naming_check_result(0, 0, []),
                    business_metadata_checks=business_checks,
                    score=table_score,
                ))
            total_passed += business_checks["passed"]
            total_checks += business_checks["total"]

    if business_domain_config and model_metadata:
        for name, metadata in model_metadata.items():
            if name in checked_business_tables:
                continue
            business_checks = _score_business_metadata_for_table(
                name,
                str(metadata.get("layer") or "OTHER").upper(),
                nc,
                model_metadata,
                business_domain_config,
            )
            if not business_checks["total"]:
                continue
            checked_business_tables.add(name)
            record_business_summary(business_checks)
            table_score = round(
                business_checks["passed"] / business_checks["total"] * 100,
                1,
            )
            table_results.append(
                dict(
                    table=name,
                    layer=str(metadata.get("layer") or "OTHER").upper(),
                    table_checks=_naming_check_result(0, 0, []),
                    column_checks=_naming_check_result(0, 0, []),
                    atomic_metric_checks=_naming_check_result(0, 0, []),
                    derived_metric_checks=_naming_check_result(0, 0, []),
                    business_metadata_checks=business_checks,
                    score=table_score,
                ))
            total_passed += business_checks["passed"]
            total_checks += business_checks["total"]

    file_result = _score_file_naming_conventions(
        project_dir,
        tables,
        edges,
        indirect_edges,
    )
    total_passed += file_result["passed"]
    total_checks += file_result["total"]

    overall = round(total_passed / total_checks *
                    100, 1) if total_checks else 100.0

    # 规则汇总
    rule_summary = {}
    passed = sum(
        1 for t in middle
        if _check_table_name_any_template(t["name"], t["layer"], nc)
    )
    total = len(middle)
    rule_summary["表名符合规范模板"] = dict(
        pass_count=passed,
        total=total,
        pct=round(passed / total * 100, 1) if total else 0,
    )

    table_max_lengths = sorted({
        max_length
        for t in middle
        for max_length in [_table_name_max_length(t["name"], t["layer"], nc)]
        if max_length is not None
    })
    for max_length in table_max_lengths:
        relevant_tables = [
            t for t in middle
            if _table_name_max_length(t["name"], t["layer"], nc) == max_length
        ]
        passed = sum(
            1 for t in relevant_tables
            if _check_table_name_length(t["name"], t["layer"], nc)
        )
        rule_summary[f"表名长度 <= {max_length}"] = dict(
            pass_count=passed,
            total=len(relevant_tables),
            pct=round(passed / len(relevant_tables) * 100, 1)
            if relevant_tables else 0,
        )

    col_total = 0
    col_passed = 0
    for t in middle:
        checked_metric_name_set = set(
            _atomic_metric_names_for_table(t, model_metadata)
            if has_atomic_metric_rule
            else []
        )
        if has_derived_metric_rule:
            checked_metric_name_set.update(
                _derived_metric_names_for_table(t, model_metadata))
        for col in t.get("columns", []):
            col_name = col["name"]
            if col_name in checked_metric_name_set:
                continue
            col_total += 1
            ok, matched = _check_column_name(col_name, nc)
            if ok:
                col_passed += 1
            for m in matched:
                if m not in rule_summary:
                    rule_summary[m] = {"pass_count": 0, "total": 0}
                rule_summary[m]["pass_count"] += 1
                rule_summary[m]["total"] += 1
            if not ok:
                rule_summary.setdefault("无匹配模式", {"pass_count": 0, "total": 0})
                rule_summary["无匹配模式"]["total"] += 1
    for _, v in rule_summary.items():
        if v["total"]:
            v["pct"] = round(v["pass_count"] / v["total"] * 100, 1)
    # 确保 col 总结显示
    pct = round(col_passed / col_total * 100, 1) if col_total else 0
    rule_summary["列名总计"] = dict(
        pass_count=col_passed,
        total=col_total,
        pct=pct,
    )

    if has_atomic_metric_rule:
        metric_total = 0
        metric_passed = 0
        for t in middle:
            for metric_name in _atomic_metric_names_for_table(t, model_metadata):
                metric_total += 1
                if _check_atomic_metric_name(metric_name, nc):
                    metric_passed += 1
        rule_summary[atomic_rule_label] = dict(
            pass_count=metric_passed,
            total=metric_total,
            pct=round(metric_passed / metric_total * 100, 1)
            if metric_total else 0,
        )

    if has_derived_metric_rule:
        metric_total = 0
        metric_passed = 0
        for t in middle:
            for metric_name in _derived_metric_names_for_table(t, model_metadata):
                metric_total += 1
                if _check_derived_metric_name(metric_name, nc):
                    metric_passed += 1
        rule_summary[derived_rule_label] = dict(
            pass_count=metric_passed,
            total=metric_total,
            pct=round(metric_passed / metric_total * 100, 1)
            if metric_total else 0,
        )

    if business_domain_config:
        rule_summary["数据域属于字典"] = dict(
            pass_count=business_domain_passed,
            total=business_domain_total,
            pct=round(business_domain_passed / business_domain_total * 100, 1)
            if business_domain_total else 0,
        )
        rule_summary["业务板块属于字典"] = dict(
            pass_count=business_area_passed,
            total=business_area_total,
            pct=round(business_area_passed / business_area_total * 100, 1)
            if business_area_total else 0,
        )

    rule_summary.update(file_result["rule_summary"])

    return dict(score=overall,
                details=table_results,
                rule_summary=rule_summary,
                file_checks=dict(
                    passed=file_result["passed"],
                    total=file_result["total"],
                ),
                file_details=file_result["details"])


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


def _format_naming_diagnostic(diagnostic: dict) -> str:
    actual = diagnostic.get("actual", "")
    if diagnostic.get("check") == "table_max_length":
        expected = diagnostic.get("expected", {})
        return (
            f"{actual}: 长度 {diagnostic.get('actual_length')} "
            f"> {expected.get('max_length')}"
        )

    attempts = diagnostic.get("attempts") or []
    failed_attempts = [
        attempt for attempt in attempts if not attempt.get("passed")
    ]
    if failed_attempts:
        best = max(
            failed_attempts,
            key=lambda item: (
                item.get("failure", {}).get("consumed_chars", -1),
                -len(str(item.get("failure", {}).get("actual_remaining", ""))),
            ),
        )
        rule = best.get("rule") or {}
        failure = best.get("failure") or {}
        rule_name = rule.get("name") or "未命名规则"
        desc = rule.get("description") or ""
        expr = best.get("expression") or ""
        expected = failure.get("expected")
        if expected is None:
            expected = failure.get("segment", {}).get("type", {})
        return (
            f"{actual}: 规则 {rule_name}"
            f"{'(' + desc + ')' if desc else ''}; "
            f"表达式 {expr}; "
            f"失败段 {failure.get('position')}, "
            f"原因 {failure.get('code')}; "
            f"期望 {expected}; "
            f"实际剩余 {failure.get('actual_remaining', '')}"
        )

    rule = diagnostic.get("rule") or {}
    if rule:
        return (
            f"{actual}: 规则 {rule.get('name')} "
            f"{rule.get('description', '')}".strip()
        )
    return f"{actual}: {diagnostic.get('message', '未匹配命名规则')}"


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
        business_checks = r.get("business_metadata_checks", {})
        if business_checks.get("violations"):
            issues.extend(business_checks["violations"])
        if issues:
            if not has_viz:
                parts.append(f"\n  偏离详情:")
                has_viz = True
            parts.append(
                f"\n    {r['table']}({r['layer']}) [得分: {r['score']}]")
            for iss in issues:
                parts.append(f"      {iss}")
            diagnostics = []
            diagnostics.extend(r["table_checks"].get("diagnostics", []))
            diagnostics.extend(r["column_checks"].get("diagnostics", [])[:5])
            diagnostics.extend(
                r.get("atomic_metric_checks", {}).get("diagnostics", [])[:5])
            diagnostics.extend(
                r.get("derived_metric_checks", {}).get("diagnostics", [])[:5])
            if diagnostics:
                parts.append("      诊断:")
                for diagnostic in diagnostics[:8]:
                    parts.append(
                        f"        - {_format_naming_diagnostic(diagnostic)}")

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
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

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
    naming_score = build_metric_result(
        score_naming_conventions(
            tables,
            nc,
            model_metadata,
            business_domain_config,
            project_dir=project_dir,
            edges=edges,
            indirect_edges=indirect_edges,
        ))

    overall_raw = round(
        weights["reuse"] * reuse_score["raw"] +
        weights["depth"] * depth_score["raw"] +
        weights["architecture"] * architecture_score["raw"] +
        weights["naming"] * naming_score["raw"],
        1,
    )
    overall_display = round(
        weights["reuse"] * reuse_score["display"] +
        weights["depth"] * depth_score["display"] +
        weights["architecture"] * architecture_score["display"] +
        weights["naming"] * naming_score["display"],
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
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="数据集市中间层评估工具")
    parser.add_argument("--project",
                        default="shop",
                        choices=["shop", "finance_analytics"],
                        help="项目名称 (shop / finance_analytics)")
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 assess/assess_result_{project}.json)")
    parser.add_argument("--reuse-weight", type=float, default=0.25)
    parser.add_argument("--depth-weight", type=float, default=0.25)
    parser.add_argument("--architecture-weight", type=float, default=0.25)
    parser.add_argument("--naming-weight", type=float, default=0.25)
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
        enable_llm=args.llm,
        no_cache=args.no_cache,
        parallel=args.parallel,
    )

    result = assess(args.project, weights)

    print(generate_report(result, weights, args.project))

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
