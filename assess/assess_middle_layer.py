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
import re
import sys
from pathlib import Path
from collections import defaultdict
import os

# 将项目根目录加入 sys.path 以便导入 config
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.context_builder import build_contexts
from assess.table_inspector import TableInspector
from config import layer_rank

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
# -2    → 跳过一层 (DWD→ADS 或 ODS→DWS)
# -3    → 跳过两层 (ODS→ADS)

ARCH_VIOLATION_RULES = [
    # (rank_diff, description, severity, penalty)
    (3, "反向依赖: 跳过三层(ADS→ODS)", "严重", 40),
    (2, "反向依赖: 跳过两层", "严重", 30),
    (1, "反向依赖: 跳过一层", "高", 20),
    (0, "同层依赖(非必要)", "低", 2),
    (-2, "跳过中间层(DWD/DIM→ADS 或 ODS→DWS)", "低", 5),
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


def score_architecture_health(tables: list, edges: list,
                              indirect_edges: list,
                              llm_results: list = None) -> dict:
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
                    description=f"分层配置疑似错误(LLM): 配置层={layer}, 推断层={res.inferred_layer}",
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

def _check_table_name_length(name: str, nc) -> bool:
    max_length = getattr(nc, "table_name_max_length", None)
    return max_length is None or len(name) <= max_length

def _check_column_name(col_name: str, nc) -> tuple[bool, list[str]]:
    if col_name in nc.common_columns:
        return True, ["通用列名"]

    # OR 匹配：字段只要匹配任意一个已知后缀/前缀模式即合规
    matched = []
    sf = nc.types.get("suffix_field")
    if sf and sf.values:
        for v in sorted(sf.values, key=len, reverse=True):
            if col_name.endswith(f"_{v}"):
                matched.append(f"后缀 _{v}")
                break
    if not matched:
        pf = nc.types.get("prefix_field")
        if pf and pf.values:
            for v in sorted(pf.values, key=len, reverse=True):
                if col_name.startswith(f"{v}_"):
                    matched.append(f"前缀 {v}_")
                    break

    return bool(matched), matched


def score_naming_conventions(tables: list, nc) -> dict:
    middle = [t for t in tables if t["layer"] in ("DWD", "DWS", "DIM")]

    table_results = []
    total_checks = 0
    total_passed = 0
    for t in middle:
        name = t["name"]
        layer = t["layer"]
        columns = t.get("columns", [])

        # --- 表名检查 ---
        tbl_passed = 0
        tbl_total = 1
        tbl_violations = []
        if _check_table_name_any_template(name, layer, nc):
            tbl_passed += 1
        else:
            tbl_violations.append(f"违反: 表名符合规范模板")
        if getattr(nc, "table_name_max_length", None) is not None:
            tbl_total += 1
            if _check_table_name_length(name, nc):
                tbl_passed += 1
            else:
                tbl_violations.append(f"违反: 表名长度 <= {nc.table_name_max_length}")

        # --- 字段检查 ---
        col_violations = []
        col_passed = 0
        col_total = len(columns)

        for col in columns:
            col_name = col["name"]
            ok, matched = _check_column_name(col_name, nc)
            if ok:
                col_passed += 1
            else:
                col_violations.append(col_name)

        table_pass = tbl_passed + col_passed
        table_check = tbl_total + col_total
        table_score = round(table_pass / table_check *
                            100, 1) if table_check else 100.0

        table_results.append(
            dict(
                table=name,
                layer=layer,
                table_checks=dict(passed=tbl_passed,
                                  total=tbl_total,
                                  violations=tbl_violations),
                column_checks=dict(
                    passed=col_passed,
                    total=col_total,
                    violations=sorted(col_violations),
                ),
                score=table_score,
            ))

        total_passed += table_pass
        total_checks += table_check

    overall = round(total_passed / total_checks *
                    100, 1) if total_checks else 100.0

    # 规则汇总
    rule_summary = {}
    passed = sum(1 for t in middle if _check_table_name_any_template(t["name"], t["layer"], nc))
    total = len(middle)
    rule_summary["表名符合规范模板"] = dict(
        pass_count=passed,
        total=total,
        pct=round(passed / total * 100, 1) if total else 0,
    )

    max_length = getattr(nc, "table_name_max_length", None)
    if max_length is not None:
        passed = sum(1 for t in middle if _check_table_name_length(t["name"], nc))
        rule_summary[f"表名长度 <= {max_length}"] = dict(
            pass_count=passed,
            total=total,
            pct=round(passed / total * 100, 1) if total else 0,
        )

    col_total = 0
    col_passed = 0
    for t in middle:
        for col in t.get("columns", []):
            col_name = col["name"]
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
    for k, v in rule_summary.items():
        if v["total"]:
            v["pct"] = round(v["pass_count"] / v["total"] * 100, 1)
    # 确保 col 总结显示
    pct = round(col_passed / col_total * 100, 1) if col_total else 0
    rule_summary["列名总计"] = dict(
        pass_count=col_passed,
        total=col_total,
        pct=pct,
    )

    return dict(score=overall,
                details=table_results,
                rule_summary=rule_summary)


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
        if issues:
            if not has_viz:
                parts.append(f"\n  偏离详情:")
                has_viz = True
            parts.append(
                f"\n    {r['table']}({r['layer']}) [得分: {r['score']}]")
            for iss in issues:
                parts.append(f"      {iss}")

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

    from config import get_naming_config
    nc = get_naming_config(project)

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
            inspector = TableInspector(api_key, cache_file=cache_file)
            llm_results = inspector.inspect_batch(contexts)
        else:
            print("警告: 未提供 DEEPSEEK_API_KEY 环境变量，跳过分类。")

    _, downstream = build_table_graph(edges, indirect_edges)

    reuse_score = build_metric_result(score_reusability(tables, downstream))
    depth_score = build_metric_result(
        score_lineage_depth(tables, edges, indirect_edges))
    architecture_raw = score_architecture_health(tables, edges, indirect_edges,
                                                  llm_results)
    architecture_score = build_metric_result(architecture_raw)
    naming_score = build_metric_result(score_naming_conventions(tables, nc))

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
    args = parser.parse_args()

    weights = dict(
        reuse=args.reuse_weight,
        depth=args.depth_weight,
        architecture=args.architecture_weight,
        naming=args.naming_weight,
        enable_llm=args.llm,
        no_cache=args.no_cache,
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
