"""Model design health scoring dimension."""

import re
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

from assess.llm.table_inspector import VALID_TABLE_TYPES
from assess.project_facts.business_metadata import (
    _business_area_applies,
    _declared_business_area,
    _declared_data_domain,
    _data_domain_applies,
    _valid_inferred_business_area,
    _valid_inferred_data_domain,
)
from assess.project_facts.entity_metadata import grain_key_columns
from assess.result_model import finalize_dimension, make_check
from assess.scoring.config import (
    ARCH_VIOLATION_RULES,
    MODEL_DESIGN_RULES,
    PER_TABLE_CAP,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_WEIGHT,
)
from config import layer_rank
from lineage.table_graph import _table_from_node, build_table_layer_map

AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)

EVENT_KEY_TOKENS = (
    "alert",
    "application",
    "assessment",
    "detail",
    "event",
    "item",
    "log",
    "order",
    "payment",
    "transaction",
)


def _declared_table_type(model_metadata: dict | None, table_name: str) -> str:
    if not model_metadata:
        return ""
    raw_type = model_metadata.get(table_name, {}).get("table_type")
    table_type = str(raw_type or "").strip()
    return table_type if table_type in VALID_TABLE_TYPES else ""


def _short_column_name(sql_text: str) -> str:
    name = str(sql_text or "").strip().replace("`", "").replace('"', "")
    if not name:
        return ""
    return name.split(".")[-1]


def _select_group_by_columns(select: exp.Select) -> list[str]:
    group = select.args.get("group")
    if not group:
        return []
    columns = []
    for expression in group.expressions:
        name = _short_column_name(expression.sql(dialect="doris"))
        if name and name not in columns:
            columns.append(name)
    return sorted(columns)


def _select_aggregate_aliases(select: exp.Select) -> list[str]:
    aliases = []
    for expression in select.expressions:
        if not list(expression.find_all(exp.AggFunc)):
            continue
        alias = expression.alias_or_name
        if alias:
            aliases.append(_short_column_name(alias))
    return sorted({alias for alias in aliases if alias})


def _select_group_output_columns(select: exp.Select,
                                 group_by_columns: list[str]) -> list[str]:
    group_set = set(group_by_columns)
    outputs = set(group_by_columns)
    for expression in select.expressions:
        if not isinstance(expression, exp.Alias):
            continue
        source_name = _short_column_name(expression.this.sql(dialect="doris"))
        alias = _short_column_name(expression.alias_or_name)
        if source_name in group_set and alias:
            outputs.add(alias)
    return sorted(outputs)


def _extract_sql_facts_with_sqlglot(sql_text: str) -> dict | None:
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
    except Exception:
        return None
    if not statements:
        return None

    group_by_columns = []
    group_output_columns = []
    aggregate_aliases = []
    has_aggregate = False
    for statement in statements:
        if statement is None:
            continue
        for select in statement.find_all(exp.Select):
            select_group_columns = _select_group_by_columns(select)
            for column in select_group_columns:
                if column not in group_by_columns:
                    group_by_columns.append(column)
            for column in _select_group_output_columns(
                select,
                select_group_columns,
            ):
                if column not in group_output_columns:
                    group_output_columns.append(column)
            aliases = _select_aggregate_aliases(select)
            for alias in aliases:
                if alias not in aggregate_aliases:
                    aggregate_aliases.append(alias)
            if list(select.find_all(exp.AggFunc)):
                has_aggregate = True

    return {
        "has_group_by": bool(group_by_columns),
        "has_aggregate": has_aggregate,
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_output_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
    }


def _extract_sql_facts_with_regex(sql_text: str) -> dict:
    group_by_columns = []
    group_match = re.search(
        r"\bGROUP\s+BY\s+(.+?)(?:\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|;|$)",
        str(sql_text or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if group_match:
        raw_columns = group_match.group(1)
        for raw_column in raw_columns.split(","):
            name = _short_column_name(raw_column.strip())
            if name and name not in group_by_columns:
                group_by_columns.append(name)

    aggregate_aliases = []
    for match in re.finditer(
        r"\b(?:SUM|COUNT|AVG|MIN|MAX)\s*\([^)]*\)\s+AS\s+`?(\w+)`?",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    ):
        alias = _short_column_name(match.group(1))
        if alias and alias not in aggregate_aliases:
            aggregate_aliases.append(alias)

    return {
        "has_group_by": bool(group_by_columns),
        "has_aggregate": bool(AGGREGATE_PATTERN.search(str(sql_text or ""))),
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_by_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
    }


def extract_model_design_sql_facts(sql_text: str) -> dict:
    """Extract SQL facts needed by model design checks."""
    parsed = _extract_sql_facts_with_sqlglot(sql_text)
    if parsed is not None:
        return parsed
    return _extract_sql_facts_with_regex(sql_text)


def _table_metadata(model_metadata: dict | None, table_name: str) -> dict:
    if not model_metadata:
        return {}
    metadata = model_metadata.get(table_name)
    return metadata if isinstance(metadata, dict) else {}


def _table_type(model_metadata: dict | None, table_name: str) -> str:
    table_type = str(
        _table_metadata(model_metadata, table_name).get("table_type") or ""
    ).strip()
    return table_type if table_type in VALID_TABLE_TYPES else ""


def _is_fact_table(model_metadata: dict | None, table_name: str) -> bool:
    return _table_type(model_metadata, table_name) == "fact"


def _task_sql_text(task: dict) -> str:
    sql_text = str(task.get("sql") or "")
    if sql_text:
        return sql_text
    path = task.get("path")
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return ""


def _task_source_file(task: dict) -> str:
    return str(
        task.get("source_file")
        or task.get("file")
        or task.get("path")
        or ""
    )


def _table_tasks(asset_catalog: dict | None, table_name: str) -> list[dict]:
    if not asset_catalog:
        return []
    table_asset = (asset_catalog.get("tables") or {}).get(table_name) or {}
    tasks = table_asset.get("tasks") or []
    return [task for task in tasks if isinstance(task, dict)]


def _table_sql_facts(asset_catalog: dict | None, table_name: str) -> dict:
    group_by_columns = set()
    group_output_columns = set()
    aggregate_aliases = set()
    source_files = []
    has_group_by = False
    has_aggregate = False
    for task in _table_tasks(asset_catalog, table_name):
        sql_text = _task_sql_text(task)
        if not sql_text:
            continue
        facts = extract_model_design_sql_facts(sql_text)
        has_group_by = has_group_by or facts["has_group_by"]
        has_aggregate = has_aggregate or facts["has_aggregate"]
        group_by_columns.update(facts.get("group_by_columns") or [])
        group_output_columns.update(facts.get("group_output_columns") or [])
        aggregate_aliases.update(facts.get("aggregate_aliases") or [])
        source_file = _task_source_file(task)
        if source_file and source_file not in source_files:
            source_files.append(source_file)
    return {
        "has_group_by": has_group_by,
        "has_aggregate": has_aggregate,
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_output_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
        "source_files": sorted(source_files),
    }


def _table_column_names(table: dict) -> list[str]:
    names = []
    for column in table.get("columns") or []:
        if not isinstance(column, dict):
            continue
        name = str(column.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _has_event_key(table: dict, metadata: dict) -> bool:
    candidates = _table_column_names(table)
    for entity in metadata.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        candidates.extend(
            str(key or "").strip()
            for key in entity.get("key_columns") or []
        )
    for candidate in candidates:
        name = candidate.lower()
        if not name.endswith(("_id", "_no", "_key")):
            continue
        if any(token in name for token in EVENT_KEY_TOKENS):
            return True
    return False


def _grain_group_by_mismatch(metadata: dict, sql_facts: dict) -> dict:
    grain_keys = set(grain_key_columns(metadata))
    group_outputs = set(sql_facts.get("group_output_columns") or [])
    missing_in_group_by = sorted(grain_keys - group_outputs)
    extra_group_by = sorted(group_outputs - grain_keys)
    return {
        "grain_keys": sorted(grain_keys),
        "group_by_columns": sql_facts.get("group_by_columns") or [],
        "group_output_columns": sorted(group_outputs),
        "missing_in_group_by": missing_in_group_by,
        "extra_group_by": extra_group_by,
        "matched": not missing_in_group_by and not extra_group_by,
    }


def score_model_design_health(
    tables: list,
    edges: list,
    indirect_edges: list,
    llm_results: list = None,
    model_metadata: dict | None = None,
    business_domain_config=None,
    asset_catalog: dict | None = None,
) -> dict:
    """Score model design health.

    This starts as the architecture ruleset and will grow model-specific
    checks for layer boundaries and grain clarity.
    """
    table_layers = build_table_layer_map(tables)
    table_count = len(tables)

    table_edges = defaultdict(set)
    for edge in edges:
        src = _table_from_node(edge["source"])
        tgt = _table_from_node(edge["target"])
        if src != tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))
    for edge in indirect_edges:
        src = _table_from_node(edge["source"])
        tgt = edge["target_table"]
        if src != tgt:
            table_edges[(src, tgt)].add(edge.get("source_file", ""))

    checks = []
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
                or MODEL_DESIGN_RULES[rule_id]["severity"]
            )
            table_weight[target_table] += SEVERITY_WEIGHT[effective_severity]

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

    if llm_results:
        cls_map = {result.table_name: result for result in llm_results}
        table_map = {table["name"]: table for table in tables}
        for name, result in cls_map.items():
            layer = table_map[name]["layer"] if name in table_map else "OTHER"

            record_check(
                rule_id="ARCH_DECLARED_LAYER_MATCHES_LLM",
                target_table=name,
                passed=not result.is_violating_declared_layer,
                expected="配置层与LLM推断层一致",
                actual=f"配置层={layer}, 推断层={result.inferred_layer}",
                evidence={
                    "source_type": "llm",
                    "confidence": getattr(result, "confidence", None),
                },
                message=(
                    "分层配置疑似错误(LLM): "
                    f"配置层={layer}, 推断层={result.inferred_layer}"
                ) if result.is_violating_declared_layer else "",
            )

            is_dwd_dimension = (
                result.table_type == "dimension" and layer == "DWD"
            )
            record_check(
                rule_id="ARCH_DWD_DIMENSION_POSITION",
                target_table=name,
                passed=not is_dwd_dimension,
                expected="维度表不位于DWD层",
                actual=f"配置层={layer}, LLM表类型={result.table_type}",
                evidence={
                    "source_type": "llm",
                    "confidence": getattr(result, "confidence", None),
                },
                message=(
                    "维度表位置不当(LLM): 维度表应置于 DIM 层"
                    if is_dwd_dimension else ""
                ),
            )

            declared_type = _declared_table_type(model_metadata, name)
            if declared_type:
                type_mismatch = declared_type != result.table_type
                record_check(
                    rule_id="ARCH_TABLE_TYPE_MATCHES_LLM",
                    target_table=name,
                    passed=not type_mismatch,
                    expected="配置表类型与LLM推断一致",
                    actual=(
                        f"配置类型={declared_type}, "
                        f"推断类型={result.table_type}"
                    ),
                    evidence={
                        "source_type": "llm",
                        "confidence": getattr(result, "confidence", None),
                    },
                    message=(
                        "表类型配置疑似错误(LLM): "
                        f"配置类型={declared_type}, 推断类型={result.table_type}"
                    ) if type_mismatch else "",
                )

            if _data_domain_applies(layer):
                inferred_domain = _valid_inferred_data_domain(
                    result,
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
                            "confidence": getattr(result, "confidence", None),
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
                    result,
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
                            "confidence": getattr(result, "confidence", None),
                        },
                        message=(
                            "业务板块配置疑似错误(LLM): "
                            f"配置={declared_area or '未配置'}, 推断={inferred_area}"
                        ) if area_mismatch else "",
                        severity=severity if area_mismatch else None,
                    )

    for table in tables:
        table_name = str(table.get("name") or "").strip()
        layer = str(table.get("layer") or "OTHER").upper()
        metadata = _table_metadata(model_metadata, table_name)
        if not table_name or not _is_fact_table(model_metadata, table_name):
            continue

        sql_facts = _table_sql_facts(asset_catalog, table_name)
        if layer == "DWD":
            has_aggregation = (
                sql_facts["has_group_by"] or sql_facts["has_aggregate"]
            )
            record_check(
                rule_id="MODEL_DWD_FACT_NO_AGGREGATION",
                target_table=table_name,
                passed=not has_aggregation,
                expected="DWD事实表不包含GROUP BY或聚合函数",
                actual=(
                    "存在聚合"
                    if has_aggregation
                    else "未发现聚合"
                ),
                evidence=sql_facts,
                message=(
                    "DWD事实表疑似承载汇总逻辑，应保持明细粒度"
                    if has_aggregation else ""
                ),
            )
            has_event_key = _has_event_key(table, metadata)
            record_check(
                rule_id="MODEL_DWD_FACT_HAS_EVENT_KEY",
                target_table=table_name,
                passed=has_event_key,
                expected="DWD事实表包含事件/流水/明细键",
                actual="存在事件键候选" if has_event_key else "未发现事件键候选",
                evidence={
                    "columns": _table_column_names(table),
                    "entities": metadata.get("entities") or [],
                },
                message=(
                    "DWD事实表缺少明显事件键，粒度可能不清晰"
                    if not has_event_key else ""
                ),
            )

        if layer == "DWS":
            grain = metadata.get("grain")
            has_grain = isinstance(grain, dict) and bool(grain)
            record_check(
                rule_id="MODEL_DWS_GRAIN_PRESENT",
                target_table=table_name,
                passed=has_grain,
                expected="DWS事实表配置grain",
                actual="已配置grain" if has_grain else "未配置grain",
                evidence={"grain": grain or {}},
                message="DWS事实表缺少grain元数据" if not has_grain else "",
            )
            if has_grain and sql_facts["has_group_by"]:
                mismatch = _grain_group_by_mismatch(metadata, sql_facts)
                record_check(
                    rule_id="MODEL_DWS_GRAIN_MATCHES_GROUP_BY",
                    target_table=table_name,
                    passed=mismatch["matched"],
                    expected="grain键与GROUP BY输出粒度一致",
                    actual=(
                        "一致"
                        if mismatch["matched"]
                        else (
                            "不一致: "
                            f"grain缺失于GROUP BY={mismatch['missing_in_group_by']}, "
                            f"GROUP BY额外字段={mismatch['extra_group_by']}"
                        )
                    ),
                    evidence={**sql_facts, **mismatch},
                    message=(
                        "DWS事实表声明粒度与SQL GROUP BY不一致"
                        if not mismatch["matched"] else ""
                    ),
                )

    capped_total = 0
    table_capped = {}
    for table_name, weight in table_weight.items():
        capped = min(weight, PER_TABLE_CAP)
        table_capped[table_name] = capped
        capped_total += capped

    score = (
        max(0, round(100 * (1 - capped_total / table_count), 1))
        if table_count
        else 100.0
    )

    return finalize_dimension(
        dimension="model_design",
        score=score,
        checks=checks,
        rules=MODEL_DESIGN_RULES,
        summary={
            "table_count": table_count,
            "capped_total": capped_total,
            "table_capped": table_capped,
        },
    )
