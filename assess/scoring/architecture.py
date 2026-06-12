"""Architecture health scoring dimension."""

from collections import defaultdict

from assess.project_facts.business_metadata import (
    _business_area_applies,
    _declared_business_area,
    _declared_data_domain,
    _data_domain_applies,
    _valid_inferred_business_area,
    _valid_inferred_data_domain,
)
from assess.result_model import finalize_dimension, make_check
from assess.scoring.config import (
    ARCHITECTURE_RULES,
    ARCH_VIOLATION_RULES,
    PER_TABLE_CAP,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_WEIGHT,
)
from assess.llm.table_inspector import VALID_TABLE_TYPES
from config import layer_rank
from lineage.table_graph import _table_from_node, build_table_layer_map

def _declared_table_type(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    raw_type = model_metadata.get(table_name, {}).get("table_type")
    table_type = str(raw_type or "").strip()
    return table_type if table_type in VALID_TABLE_TYPES else ""

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
