"""Model design health rule definitions."""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
from sqlglot import exp

from dw_refactor_agent.assessment.llm.table_inspector import VALID_TABLE_TYPES
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    AssetCatalog,
    TaskAsset,
)
from dw_refactor_agent.assessment.project_facts.business_metadata import (
    _business_area_applies,
    _data_domain_applies,
    _declared_business_area,
    _declared_data_domain,
    _valid_inferred_business_area,
    _valid_inferred_data_domain,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    grain_key_columns,
    model_entities,
)
from dw_refactor_agent.assessment.project_facts.identifier_index import (
    missing_identifier_names,
)
from dw_refactor_agent.assessment.result_model import make_check
from dw_refactor_agent.assessment.rules.engine.base import AssessRule
from dw_refactor_agent.assessment.scoring.config import (
    ARCH_VIOLATION_RULES,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)
from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.lineage.identifiers import (
    column_ref_match_key,
    identifier_match_key,
)
from dw_refactor_agent.lineage.view import LineageView
from dw_refactor_agent.sql.doris import extract_doris_partition_column

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
DATE_PARTITION_COLUMN = "data_dt"


class _ModelDesignRule(AssessRule):
    dimension = "model_design"
    target = "table"

    def check(
        self,
        *,
        target_table: str,
        passed: bool,
        expected: str,
        actual: str,
        evidence: dict | None = None,
        message: str = "",
        severity: str | None = None,
        title: str | None = None,
    ) -> dict:
        issue = {}
        if severity:
            issue["severity"] = severity
        if title:
            issue["title"] = title
        if message:
            issue["message"] = message
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=target_table,
            passed=passed,
            expected=expected,
            actual=actual,
            evidence=evidence,
            message=message,
            issue=issue or None,
        )


def _dependency_actual(target: dict) -> str:
    return (
        f"{target['source']}({target['source_layer']}) -> "
        f"{target['target_table']}({target['target_layer']})"
    )


def _design_facts_for_target(target: dict, rule_context: dict) -> dict:
    getter = rule_context.get("design_facts_for")
    if getter:
        return getter(target["table_name"])
    return target.get("design_facts") or {}


def _has_design_evidence(design_facts: dict) -> bool:
    return bool(
        design_facts.get("source_files")
        or (design_facts.get("lineage") or {}).get("has_lineage")
    )


def _upstream_tables_from_context(
    rule_context: dict,
    table_name: str,
) -> list[str]:
    getter = rule_context.get("upstream_tables_for")
    if getter:
        return getter(table_name)
    return _upstream_tables_for(
        table_name, rule_context.get("table_edges", {})
    )


def _upstream_table_layers_from_context(
    rule_context: dict,
    table_name: str,
) -> dict[str, str]:
    table_layers = rule_context.get("table_layers") or {}
    return {
        upstream: table_layers.get(upstream, "OTHER")
        for upstream in _upstream_tables_from_context(
            rule_context,
            table_name,
        )
    }


def _dependency_violation(target: dict) -> tuple[str, str, str] | None:
    if (
        target["source_layer"] == "DIM" and target["target_layer"] == "ADS"
    ) or target["rank_diff"] == -1:
        return None
    rank_diff = target["rank_diff"]
    for diff, desc, severity, _penalty in ARCH_VIOLATION_RULES:
        if rank_diff != diff:
            continue
        if severity == SEVERITY_HIGH:
            return "ARCH_REVERSE_DEPENDENCY", desc, severity
        if rank_diff == 0:
            return "ARCH_SAME_LAYER_DEPENDENCY", desc, severity
        return "ARCH_SKIP_LAYER_DEPENDENCY", desc, severity
    return None


class ArchReverseDependencyRule(_ModelDesignRule):
    rule_id = "ARCH_REVERSE_DEPENDENCY"
    domain = "dependency"
    target = "edge"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        violation = _dependency_violation(target)
        if not violation or violation[0] != self.rule_id:
            return None
        _rule_id, desc, severity = violation
        return self.check(
            target_table=target["target_table"],
            passed=False,
            expected="层级依赖方向合理",
            actual=_dependency_actual(target),
            evidence=target["evidence"],
            message=desc,
            severity=severity,
        )


class ArchSameLayerDependencyRule(_ModelDesignRule):
    rule_id = "ARCH_SAME_LAYER_DEPENDENCY"
    domain = "dependency"
    target = "edge"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        violation = _dependency_violation(target)
        if not violation or violation[0] != self.rule_id:
            return None
        _rule_id, desc, severity = violation
        return self.check(
            target_table=target["target_table"],
            passed=False,
            expected="层级依赖方向合理",
            actual=_dependency_actual(target),
            evidence=target["evidence"],
            message=desc,
            severity=severity,
        )


class ArchSkipLayerDependencyRule(_ModelDesignRule):
    rule_id = "ARCH_SKIP_LAYER_DEPENDENCY"
    domain = "dependency"
    target = "edge"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        violation = _dependency_violation(target)
        if not violation or violation[0] != self.rule_id:
            return None
        _rule_id, desc, severity = violation
        return self.check(
            target_table=target["target_table"],
            passed=False,
            expected="层级依赖方向合理",
            actual=_dependency_actual(target),
            evidence=target["evidence"],
            message=desc,
            severity=severity,
        )


class ArchDeclaredLayerMatchesLlmRule(_ModelDesignRule):
    rule_id = "ARCH_DECLARED_LAYER_MATCHES_LLM"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict:
        result = target["llm_result"]
        layer = target["layer"]
        return self.check(
            target_table=target["table_name"],
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
            )
            if result.is_violating_declared_layer
            else "",
        )


class ArchDwdDimensionPositionRule(_ModelDesignRule):
    rule_id = "ARCH_DWD_DIMENSION_POSITION"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict:
        result = target["llm_result"]
        layer = target["layer"]
        is_dwd_dimension = result.table_type == "dimension" and layer == "DWD"
        return self.check(
            target_table=target["table_name"],
            passed=not is_dwd_dimension,
            expected="维度表不位于DWD层",
            actual=f"配置层={layer}, LLM表类型={result.table_type}",
            evidence={
                "source_type": "llm",
                "confidence": getattr(result, "confidence", None),
            },
            message=(
                "维度表位置不当(LLM): 维度表应置于 DIM 层"
                if is_dwd_dimension
                else ""
            ),
        )


class ArchTableTypeMatchesLlmRule(_ModelDesignRule):
    rule_id = "ARCH_TABLE_TYPE_MATCHES_LLM"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        result = target["llm_result"]
        declared_type = _declared_table_type(
            rule_context["model_metadata"],
            target["table_name"],
        )
        if not declared_type:
            return None
        type_mismatch = declared_type != result.table_type
        return self.check(
            target_table=target["table_name"],
            passed=not type_mismatch,
            expected="配置表类型与LLM推断一致",
            actual=f"配置类型={declared_type}, 推断类型={result.table_type}",
            evidence={
                "source_type": "llm",
                "confidence": getattr(result, "confidence", None),
            },
            message=(
                "表类型配置疑似错误(LLM): "
                f"配置类型={declared_type}, 推断类型={result.table_type}"
            )
            if type_mismatch
            else "",
        )


class ArchDataDomainMatchesLlmRule(_ModelDesignRule):
    rule_id = "ARCH_DATA_DOMAIN_MATCHES_LLM"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        layer = target["layer"]
        result = target["llm_result"]
        if not _data_domain_applies(layer):
            return None
        inferred_domain = _valid_inferred_data_domain(
            result,
            rule_context["business_domain_config"],
        )
        if not inferred_domain:
            return None
        if rule_context["business_domain_config"]:
            declared_domain = rule_context[
                "business_domain_config"
            ].normalize_domain(
                _declared_data_domain(
                    rule_context["model_metadata"], target["table_name"]
                )
            )
        else:
            declared_domain = _declared_data_domain(
                rule_context["model_metadata"],
                target["table_name"],
            )
        domain_mismatch = inferred_domain != declared_domain
        severity = SEVERITY_MEDIUM if declared_domain else SEVERITY_LOW
        return self.check(
            target_table=target["table_name"],
            passed=not domain_mismatch,
            expected="data_domain与LLM推断一致",
            actual=(
                f"配置={declared_domain or '未配置'}, 推断={inferred_domain}"
            ),
            evidence={
                "source_type": "llm",
                "confidence": getattr(result, "confidence", None),
            },
            message=(
                "数据域配置疑似错误(LLM): "
                f"配置={declared_domain or '未配置'}, 推断={inferred_domain}"
            )
            if domain_mismatch
            else "",
            severity=severity if domain_mismatch else None,
        )


class ArchBusinessAreaMatchesLlmRule(_ModelDesignRule):
    rule_id = "ARCH_BUSINESS_AREA_MATCHES_LLM"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        layer = target["layer"]
        result = target["llm_result"]
        if not _business_area_applies(layer):
            return None
        inferred_area = _valid_inferred_business_area(
            result,
            rule_context["business_domain_config"],
        )
        if not inferred_area:
            return None
        if rule_context["business_domain_config"]:
            declared_area = rule_context[
                "business_domain_config"
            ].normalize_business_area(
                _declared_business_area(
                    rule_context["model_metadata"],
                    target["table_name"],
                )
            )
        else:
            declared_area = _declared_business_area(
                rule_context["model_metadata"],
                target["table_name"],
            )
        area_mismatch = inferred_area != declared_area
        severity = SEVERITY_MEDIUM if declared_area else SEVERITY_LOW
        return self.check(
            target_table=target["table_name"],
            passed=not area_mismatch,
            expected="business_area与LLM推断一致",
            actual=f"配置={declared_area or '未配置'}, 推断={inferred_area}",
            evidence={
                "source_type": "llm",
                "confidence": getattr(result, "confidence", None),
            },
            message=(
                "业务板块配置疑似错误(LLM): "
                f"配置={declared_area or '未配置'}, 推断={inferred_area}"
            )
            if area_mismatch
            else "",
            severity=severity if area_mismatch else None,
        )


class ModelDwdFactNoAggregationRule(_ModelDesignRule):
    rule_id = "MODEL_DWD_FACT_NO_AGGREGATION"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWD" or not target["is_fact_table"]:
            return None
        design_facts = _design_facts_for_target(target, rule_context)
        has_aggregation = (
            design_facts["has_group_by"] or design_facts["has_aggregate"]
        )
        return self.check(
            target_table=target["table_name"],
            passed=not has_aggregation,
            expected="DWD事实表不包含GROUP BY或聚合函数",
            actual="存在聚合" if has_aggregation else "未发现聚合",
            evidence=design_facts,
            message=(
                "DWD事实表疑似承载汇总逻辑，应保持明细粒度"
                if has_aggregation
                else ""
            ),
        )


class ModelDwsGrainPresentRule(_ModelDesignRule):
    rule_id = "MODEL_DWS_GRAIN_PRESENT"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or not target["is_fact_table"]:
            return None
        grain = target["metadata"].get("grain")
        has_grain = isinstance(grain, dict) and bool(grain)
        return self.check(
            target_table=target["table_name"],
            passed=has_grain,
            expected="DWS事实表配置grain",
            actual="已配置grain" if has_grain else "未配置grain",
            evidence={"grain": grain or {}},
            message="DWS事实表缺少grain元数据" if not has_grain else "",
        )


class ModelDwsGrainMatchesGroupByRule(_ModelDesignRule):
    rule_id = "MODEL_DWS_GRAIN_MATCHES_GROUP_BY"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or not target["is_fact_table"]:
            return None
        metadata = target["metadata"]
        grain = metadata.get("grain")
        has_grain = isinstance(grain, dict) and bool(grain)
        design_facts = _design_facts_for_target(target, rule_context)
        if not has_grain or not design_facts["has_group_by"]:
            return None
        mismatch = _grain_group_by_mismatch(metadata, design_facts)
        return self.check(
            target_table=target["table_name"],
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
            evidence={**design_facts, **mismatch},
            message=(
                "DWS事实表声明粒度与SQL GROUP BY不一致"
                if not mismatch["matched"]
                else ""
            ),
        )


class ModelDwdFactHasEventKeyRule(_ModelDesignRule):
    rule_id = "MODEL_DWD_FACT_HAS_EVENT_KEY"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWD" or not target["is_fact_table"]:
            return None
        has_event_key = _has_event_key(target["table"], target["metadata"])
        return self.check(
            target_table=target["table_name"],
            passed=has_event_key,
            expected="DWD事实表包含事件/流水/明细键",
            actual="存在事件键候选" if has_event_key else "未发现事件键候选",
            evidence={
                "columns": _table_column_names(target["table"]),
                "entities": target["metadata"].get("entities") or [],
            },
            message=(
                "DWD事实表缺少明显事件键，粒度可能不清晰"
                if not has_event_key
                else ""
            ),
        )


class ModelDwsFactHasAggregationRule(_ModelDesignRule):
    rule_id = "MODEL_DWS_FACT_HAS_AGGREGATION"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or not target["is_fact_table"]:
            return None
        design_facts = _design_facts_for_target(target, rule_context)
        if not _has_design_evidence(design_facts):
            return None
        return self.check(
            target_table=target["table_name"],
            passed=design_facts["has_aggregate"],
            expected="DWS事实表包含聚合逻辑",
            actual="存在聚合"
            if design_facts["has_aggregate"]
            else "未发现聚合",
            evidence=design_facts,
            message=(
                "DWS事实表疑似只是明细透传，缺少汇总逻辑"
                if not design_facts["has_aggregate"]
                else ""
            ),
        )


class ModelDwsSelectFieldsMatchGrainRule(_ModelDesignRule):
    rule_id = "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or not target["is_fact_table"]:
            return None
        metadata = target["metadata"]
        grain = metadata.get("grain")
        has_grain = isinstance(grain, dict) and bool(grain)
        design_facts = _design_facts_for_target(target, rule_context)
        if not has_grain or not design_facts["has_group_by"]:
            return None
        leakage = _dws_plain_field_leakage(metadata, design_facts)
        return self.check(
            target_table=target["table_name"],
            passed=not leakage["leaked_columns"],
            expected="DWS SELECT普通字段属于声明粒度或GROUP BY来源",
            actual=(
                "存在明细字段泄漏"
                if leakage["leaked_columns"]
                else "未发现明细字段泄漏"
            ),
            evidence=leakage,
            message=(
                "DWS输出字段包含非聚合且不属于粒度的明细字段"
                if leakage["leaked_columns"]
                else ""
            ),
        )


class ModelDimNoMetricGroupsRule(_ModelDesignRule):
    rule_id = "MODEL_DIM_NO_METRIC_GROUPS"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        metric_groups = target["metric_groups"]
        if not (
            target["layer"] == "DIM"
            or _table_type(
                rule_context["model_metadata"], target["table_name"]
            )
            == "dimension"
        ):
            return None
        if not metric_groups:
            return None
        return self.check(
            target_table=target["table_name"],
            passed=False,
            expected="DIM模型不配置指标分组",
            actual="存在指标分组",
            evidence={"metric_groups": metric_groups},
            message="DIM模型包含指标分组，应移除或调整表类型",
        )


class ModelDimInfoDirectOdsOnlyRule(_ModelDesignRule):
    rule_id = "MODEL_DIM_INFO_DIRECT_ODS_ONLY"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        metadata = target["metadata"]
        table_type = str(metadata.get("table_type") or "").strip().lower()
        content_type = (
            str(metadata.get("dimension_content_type") or "").strip().upper()
        )
        is_dim_info = (
            target["layer"] == "DIM"
            and table_type == "dimension"
            and content_type == "INFO"
        )
        if not is_dim_info:
            return None

        upstream_layers = _upstream_table_layers_from_context(
            rule_context,
            target["table_name"],
        )
        invalid_upstreams = [
            {"table": table_name, "layer": layer}
            for table_name, layer in sorted(upstream_layers.items())
            if layer != "ODS"
        ]

        design_facts = _design_facts_for_target(target, rule_context)
        lineage_facts = design_facts.get("lineage") or {}
        aggregate_columns = sorted(
            set(design_facts.get("aggregate_aliases") or [])
            | set(lineage_facts.get("aggregate_columns") or [])
        )
        has_aggregate = bool(
            design_facts.get("has_aggregate")
            or lineage_facts.get("has_aggregate")
        )
        window_metric_columns = sorted(
            design_facts.get("window_metric_aliases") or []
        )

        reason_codes = []
        if invalid_upstreams:
            reason_codes.append("non_ods_upstream")
        if has_aggregate:
            reason_codes.append("aggregate_output")
        if window_metric_columns:
            reason_codes.append("window_metric")

        return self.check(
            target_table=target["table_name"],
            passed=not reason_codes,
            expected="DIM INFO仅直接沉淀ODS实体属性，不承载行为事实或指标加工",
            actual=(
                "存在非INFO加工: " + ", ".join(reason_codes)
                if reason_codes
                else "未发现非INFO加工"
            ),
            evidence={
                "upstream_tables": [
                    {"table": table_name, "layer": layer}
                    for table_name, layer in sorted(upstream_layers.items())
                ],
                "invalid_upstream_tables": invalid_upstreams,
                "has_aggregate": has_aggregate,
                "aggregate_columns": aggregate_columns,
                "window_metric_columns": window_metric_columns,
                "group_by_sources": (
                    lineage_facts.get("group_by_sources") or []
                ),
                "source_files": design_facts.get("source_files") or [],
                "reason_codes": reason_codes,
            },
            message=(
                "DIM INFO表应只保留来自ODS的实体基础属性、状态属性和标准描述信息"
                if reason_codes
                else ""
            ),
        )


class ModelDwdFactNoDerivedMetricsRule(_ModelDesignRule):
    rule_id = "MODEL_DWD_FACT_NO_DERIVED_METRICS"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWD" or not target["is_fact_table"]:
            return None
        non_atomic_metric_groups = {
            key: value
            for key, value in target["metric_groups"].items()
            if key in {"derived_metrics", "calculated_metrics"}
        }
        return self.check(
            target_table=target["table_name"],
            passed=not non_atomic_metric_groups,
            expected="DWD事实表只配置原子指标",
            actual=(
                "存在派生/计算指标"
                if non_atomic_metric_groups
                else "未发现派生/计算指标"
            ),
            evidence={"metric_groups": non_atomic_metric_groups},
            message=(
                "DWD事实表包含派生或计算指标，应上移到DWS或修正指标分组"
                if non_atomic_metric_groups
                else ""
            ),
        )


class ModelDwdFactSingleBusinessProcessRule(_ModelDesignRule):
    rule_id = "MODEL_DWD_FACT_SINGLE_BUSINESS_PROCESS"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWD" or not target["is_fact_table"]:
            return None
        business_processes = _business_processes_for_dwd_fact(
            target["metadata"]
        )
        return self.check(
            target_table=target["table_name"],
            passed=len(business_processes) <= 1,
            expected="DWD事实表只承载一个业务过程",
            actual=(
                "业务过程单一"
                if len(business_processes) <= 1
                else f"多个业务过程={business_processes}"
            ),
            evidence={"business_processes": business_processes},
            message=(
                "DWD事实表包含多个业务过程，应按业务过程拆分"
                if len(business_processes) > 1
                else ""
            ),
        )


class ModelDwdFactHasPrimaryEntityOrGrainRule(_ModelDesignRule):
    rule_id = "MODEL_DWD_FACT_HAS_PRIMARY_ENTITY_OR_GRAIN"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWD" or not target["is_fact_table"]:
            return None
        metadata = target["metadata"]
        primary_entity_keys = _primary_entity_key_columns(metadata)
        grain_keys = grain_key_columns(metadata)
        has_primary_or_grain = bool(primary_entity_keys or grain_keys)
        return self.check(
            target_table=target["table_name"],
            passed=has_primary_or_grain,
            expected="DWD事实表声明primary entity key或grain key",
            actual=(
                "已声明业务主键或粒度"
                if has_primary_or_grain
                else "未声明业务主键或粒度"
            ),
            evidence={
                "primary_entity_key_columns": primary_entity_keys,
                "grain_keys": grain_keys,
                "entities": metadata.get("entities") or [],
                "grain": metadata.get("grain") or {},
            },
            message=(
                "DWD事实表缺少primary entity key或grain声明，业务粒度不清晰"
                if not has_primary_or_grain
                else ""
            ),
        )


class ModelDatePartitionUsesDataDtRule(_ModelDesignRule):
    rule_id = "MODEL_DATE_PARTITION_USES_DATA_DT"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] not in {"DWD", "DWS", "DIM"}:
            return None
        partition_column = target["partition_column"]
        if not partition_column:
            return None
        return self.check(
            target_table=target["table_name"],
            passed=partition_column == DATE_PARTITION_COLUMN,
            expected="日期分区字段为data_dt",
            actual=f"日期分区字段={partition_column}",
            evidence={
                "partition_column": partition_column,
                "expected_partition_column": DATE_PARTITION_COLUMN,
            },
            message=(
                "日期分区字段未统一使用data_dt"
                if partition_column != DATE_PARTITION_COLUMN
                else ""
            ),
        )


class ModelDerivedMetricBaseAtomicRule(_ModelDesignRule):
    rule_id = "MODEL_DERIVED_METRIC_BASE_ATOMIC"
    domain = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or not target["is_fact_table"]:
            return None
        metadata = target["metadata"]
        if not metadata.get("derived_metrics"):
            return None
        upstream_tables = _upstream_tables_from_context(
            rule_context,
            target["table_name"],
        )
        relationship_issues = _derived_metric_base_issues(
            metadata,
            _atomic_metric_names_by_table(
                rule_context["model_metadata"] or {},
                upstream_tables,
            ),
        )
        invalid_relationships = (
            relationship_issues["missing_base_metrics"]
            or relationship_issues["missing_base_metric_tables"]
            or relationship_issues["invalid_base_metrics"]
            or relationship_issues["invalid_base_metric_tables"]
            or relationship_issues["ambiguous_base_metrics"]
            or relationship_issues["missing_aggregations"]
        )
        return self.check(
            target_table=target["table_name"],
            passed=not invalid_relationships,
            expected=(
                "DWS派生指标配置base_metric、aggregation，并引用上游atomic_metrics"
            ),
            actual=(
                "派生指标关系不完整"
                if invalid_relationships
                else "派生指标关系完整"
            ),
            evidence={
                **relationship_issues,
                "upstream_tables": upstream_tables,
            },
            message=(
                "DWS派生指标应显式关联上游原子指标，并配置聚合方式"
                if invalid_relationships
                else ""
            ),
        )


MODEL_DESIGN_RULE_CLASSES = [
    ArchReverseDependencyRule,
    ArchSameLayerDependencyRule,
    ArchSkipLayerDependencyRule,
    ArchDeclaredLayerMatchesLlmRule,
    ArchDwdDimensionPositionRule,
    ArchTableTypeMatchesLlmRule,
    ArchDataDomainMatchesLlmRule,
    ArchBusinessAreaMatchesLlmRule,
    ModelDwdFactNoAggregationRule,
    ModelDwsGrainPresentRule,
    ModelDwsGrainMatchesGroupByRule,
    ModelDwdFactHasEventKeyRule,
    ModelDwsFactHasAggregationRule,
    ModelDwsSelectFieldsMatchGrainRule,
    ModelDimNoMetricGroupsRule,
    ModelDimInfoDirectOdsOnlyRule,
    ModelDwdFactNoDerivedMetricsRule,
    ModelDwdFactSingleBusinessProcessRule,
    ModelDwdFactHasPrimaryEntityOrGrainRule,
    ModelDatePartitionUsesDataDtRule,
    ModelDerivedMetricBaseAtomicRule,
]

MODEL_DESIGN_RULE_CLASSES_BY_ID = {
    rule_class.rule_id: rule_class for rule_class in MODEL_DESIGN_RULE_CLASSES
}


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
        if not isinstance(expression, exp.Alias):
            continue
        if list(expression.find_all(exp.Window)):
            continue
        if not list(expression.find_all(exp.AggFunc)):
            continue
        alias = expression.alias_or_name
        if alias:
            aliases.append(_short_column_name(alias))
    return sorted({alias for alias in aliases if alias})


def _select_has_non_window_aggregate(select: exp.Select) -> bool:
    for expression in select.expressions:
        if list(expression.find_all(exp.Window)):
            continue
        if list(expression.find_all(exp.AggFunc)):
            return True
    return False


def _select_window_metric_aliases(select: exp.Select) -> list[str]:
    aliases = []
    for expression in select.expressions:
        windows = list(expression.find_all(exp.Window))
        if not windows:
            continue
        if not any(list(window.find_all(exp.AggFunc)) for window in windows):
            continue
        alias = expression.alias_or_name
        if alias:
            aliases.append(_short_column_name(alias))
    return sorted({alias for alias in aliases if alias})


def _select_group_output_columns(
    select: exp.Select, group_by_columns: list[str]
) -> list[str]:
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
    window_metric_aliases = []
    has_aggregate = False
    has_window_metric = False
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
            window_aliases = _select_window_metric_aliases(select)
            for alias in window_aliases:
                if alias not in window_metric_aliases:
                    window_metric_aliases.append(alias)
            if _select_has_non_window_aggregate(select):
                has_aggregate = True
            if window_aliases:
                has_window_metric = True

    return {
        "has_group_by": bool(group_by_columns),
        "has_aggregate": has_aggregate,
        "has_window_metric": has_window_metric,
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_output_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
        "window_metric_aliases": sorted(window_metric_aliases),
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
    window_metric_aliases = []
    for match in re.finditer(
        r"\b(?:SUM|COUNT|AVG|MIN|MAX)\s*\([^)]*\)\s+AS\s+`?(\w+)`?",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    ):
        alias = _short_column_name(match.group(1))
        if alias and alias not in aggregate_aliases:
            aggregate_aliases.append(alias)
    for match in re.finditer(
        r"\b(?:SUM|COUNT|AVG|MIN|MAX)\s*\([^)]*\)\s+OVER\s*\([^)]*\)"
        r"\s+AS\s+`?(\w+)`?",
        str(sql_text or ""),
        flags=re.IGNORECASE | re.DOTALL,
    ):
        alias = _short_column_name(match.group(1))
        if alias and alias not in window_metric_aliases:
            window_metric_aliases.append(alias)

    window_metric_pattern = re.compile(
        r"\b(?:SUM|COUNT|AVG|MIN|MAX)\s*\([^)]*\)\s+OVER\s*\([^)]*\)"
        r"\s+AS\s+`?\w+`?",
        flags=re.IGNORECASE | re.DOTALL,
    )
    windowless_sql = window_metric_pattern.sub("", str(sql_text or ""))

    return {
        "has_group_by": bool(group_by_columns),
        "has_aggregate": bool(AGGREGATE_PATTERN.search(windowless_sql)),
        "has_window_metric": bool(window_metric_aliases),
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_by_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
        "window_metric_aliases": sorted(window_metric_aliases),
    }


def extract_model_design_sql_facts(sql_text: str) -> dict:
    """Extract SQL rule_context needed by model design checks."""
    parsed = _extract_sql_facts_with_sqlglot(sql_text)
    if parsed is not None:
        return parsed
    return _extract_sql_facts_with_regex(sql_text)


def _transformation_type_for_expression(expression: str) -> str:
    if AGGREGATE_PATTERN.search(str(expression or "")):
        return "aggregation"
    return "passthrough"


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


def _task_sql_text(task: TaskAsset) -> str:
    sql_text = task.sql
    if sql_text:
        return sql_text
    path = task.path
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding=TEXT_ENCODING)
    except (OSError, TypeError):
        return ""


def _task_source_file(task: TaskAsset) -> str:
    return task.source_file or task.file or str(task.path or "")


def _table_tasks(
    asset_catalog: AssetCatalog | None, table_name: str
) -> list[TaskAsset]:
    if not asset_catalog:
        return []
    table_asset = asset_catalog.tables.get(table_name)
    return list(table_asset.tasks) if table_asset else []


def _table_sql_facts(
    asset_catalog: AssetCatalog | None, table_name: str
) -> dict:
    group_by_columns = set()
    group_output_columns = set()
    aggregate_aliases = set()
    window_metric_aliases = set()
    source_files = []
    has_group_by = False
    has_aggregate = False
    has_window_metric = False
    for task in _table_tasks(asset_catalog, table_name):
        sql_text = _task_sql_text(task)
        if not sql_text:
            continue
        sql_facts = extract_model_design_sql_facts(sql_text)
        has_group_by = has_group_by or sql_facts["has_group_by"]
        has_aggregate = has_aggregate or sql_facts["has_aggregate"]
        has_window_metric = has_window_metric or sql_facts["has_window_metric"]
        group_by_columns.update(sql_facts.get("group_by_columns") or [])
        group_output_columns.update(
            sql_facts.get("group_output_columns") or []
        )
        aggregate_aliases.update(sql_facts.get("aggregate_aliases") or [])
        window_metric_aliases.update(
            sql_facts.get("window_metric_aliases") or []
        )
        source_file = _task_source_file(task)
        if source_file and source_file not in source_files:
            source_files.append(source_file)
    return {
        "has_group_by": has_group_by,
        "has_aggregate": has_aggregate,
        "has_window_metric": has_window_metric,
        "group_by_columns": sorted(group_by_columns),
        "group_output_columns": sorted(group_output_columns),
        "aggregate_aliases": sorted(aggregate_aliases),
        "window_metric_aliases": sorted(window_metric_aliases),
        "source_files": sorted(source_files),
    }


def _lineage_facts_from_edges(edges: list | None, table_name: str) -> dict:
    return LineageView.from_parts(
        "",
        [],
        edges or [],
    ).lineage_facts_for_table(table_name)


def _combined_design_facts(
    asset_catalog: AssetCatalog | None,
    lineage_view: LineageView,
    table_name: str,
) -> dict:
    sql_facts = _table_sql_facts(asset_catalog, table_name)
    edge_facts = lineage_view.lineage_facts_for_table(table_name)
    return {
        **sql_facts,
        "has_group_by": sql_facts["has_group_by"]
        or edge_facts["has_group_by"],
        "has_aggregate": (
            sql_facts["has_aggregate"] or edge_facts["has_aggregate"]
        ),
        "has_window_metric": sql_facts["has_window_metric"],
        "source_files": sorted(
            set(sql_facts.get("source_files") or [])
            | set(edge_facts.get("source_files") or [])
        ),
        "lineage": edge_facts,
    }


def _metric_group_names(metadata: dict) -> dict[str, list[str]]:
    groups = {}
    for key in ("atomic_metrics", "derived_metrics", "calculated_metrics"):
        names = []
        for item in metadata.get(key) or []:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(item or "").strip()
            if name:
                names.append(name)
        if names:
            groups[key] = names
    return groups


def _metric_items(raw_metrics) -> list[dict]:
    if not isinstance(raw_metrics, list):
        return []
    items = []
    for metric in raw_metrics:
        if isinstance(metric, dict):
            item = dict(metric)
            item["name"] = str(item.get("name") or "").strip()
        else:
            item = {"name": str(metric or "").strip()}
        if item["name"]:
            items.append(item)
    return items


def _string_values(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _business_processes_for_dwd_fact(metadata: dict) -> list[str]:
    processes = []

    def add(value) -> None:
        for process in _string_values(value):
            if process and process not in processes:
                processes.append(process)

    add(metadata.get("business_process"))
    for group in ("atomic_metrics", "derived_metrics", "calculated_metrics"):
        for metric in _metric_items(metadata.get(group)):
            add(metric.get("business_process"))
    return sorted(processes)


def _primary_entity_key_columns(metadata: dict) -> list[str]:
    keys = []
    for entity in model_entities(metadata):
        if not isinstance(entity, dict):
            continue
        if str(entity.get("type") or "").strip().lower() != "primary":
            continue
        for key in _string_values(entity.get("key_columns")):
            if key not in keys:
                keys.append(key)
    return sorted(keys)


def _upstream_tables_for(table_name: str, table_edges: dict) -> list[str]:
    upstream = [src for (src, tgt) in table_edges if tgt == table_name]
    return sorted(set(upstream))


def _atomic_metric_names_by_table(
    model_metadata: dict, table_names: list[str]
) -> dict[str, set[str]]:
    metrics_by_table = {}
    for table_name in table_names:
        metadata = (model_metadata or {}).get(table_name) or {}
        names = set(_metric_group_names(metadata).get("atomic_metrics") or [])
        if names:
            metrics_by_table[table_name] = names
    return metrics_by_table


def _candidate_base_metric_tables(
    base_metric: str, upstream_atomic_metrics: dict[str, set[str]]
) -> list[str]:
    return sorted(
        table_name
        for table_name, metric_names in upstream_atomic_metrics.items()
        if base_metric in metric_names
    )


def _derived_metric_base_issues(
    metadata: dict, upstream_atomic_metrics: dict[str, set[str]]
) -> dict[str, list[str]]:
    missing_base_metrics = []
    missing_base_metric_tables = []
    invalid_base_metrics = []
    invalid_base_metric_tables = []
    ambiguous_base_metrics = []
    missing_aggregations = []
    for metric in _metric_items(metadata.get("derived_metrics")):
        metric_name = str(metric.get("name") or "").strip()
        base_metric = str(metric.get("base_metric") or "").strip()
        base_metric_table = str(metric.get("base_metric_table") or "").strip()
        aggregation = str(metric.get("aggregation") or "").strip()
        if not base_metric:
            missing_base_metrics.append(metric_name)
        elif base_metric_table:
            table_metrics = upstream_atomic_metrics.get(base_metric_table)
            if table_metrics is None:
                invalid_base_metric_tables.append(
                    f"{metric_name}:{base_metric_table}"
                )
            elif base_metric not in table_metrics:
                invalid_base_metrics.append(
                    f"{metric_name}:{base_metric_table}.{base_metric}"
                )
        else:
            candidates = _candidate_base_metric_tables(
                base_metric,
                upstream_atomic_metrics,
            )
            if len(candidates) > 1:
                ambiguous_base_metrics.append(f"{metric_name}:{base_metric}")
            elif not candidates:
                invalid_base_metrics.append(f"{metric_name}:{base_metric}")
            else:
                missing_base_metric_tables.append(metric_name)
        if not aggregation:
            missing_aggregations.append(metric_name)
    return {
        "missing_base_metrics": sorted(missing_base_metrics),
        "missing_base_metric_tables": sorted(missing_base_metric_tables),
        "invalid_base_metrics": sorted(invalid_base_metrics),
        "invalid_base_metric_tables": sorted(invalid_base_metric_tables),
        "ambiguous_base_metrics": sorted(ambiguous_base_metrics),
        "missing_aggregations": sorted(missing_aggregations),
        "upstream_atomic_metrics": {
            table_name: sorted(metric_names)
            for table_name, metric_names in sorted(
                upstream_atomic_metrics.items()
            )
        },
    }


def _dws_plain_field_leakage(metadata: dict, design_facts: dict) -> dict:
    lineage = design_facts.get("lineage") or {}
    plain_sources = lineage.get("plain_column_sources") or {}
    group_sources = set(lineage.get("group_by_sources") or [])
    group_source_keys = {
        _lineage_source_match_key(source) for source in group_sources if source
    }
    grain_keys = grain_key_columns(metadata)
    grain_key_match_keys = {
        identifier_match_key(key) for key in grain_keys if key
    }
    leaked = []
    for target_column, source_id in plain_sources.items():
        if identifier_match_key(target_column) in grain_key_match_keys:
            continue
        if _lineage_source_match_key(source_id) in group_source_keys:
            continue
        leaked.append(target_column)
    return {
        "leaked_columns": sorted(leaked),
        "plain_column_sources": plain_sources,
        "group_by_sources": sorted(group_sources),
        "grain_keys": sorted(grain_keys),
        "constant_columns": lineage.get("constant_columns") or [],
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


def _lineage_source_match_key(source_id: str) -> tuple[str, ...]:
    table_key, column_key = column_ref_match_key(source_id)
    if table_key or column_key:
        return ("column", table_key, column_key)
    return ("identifier", identifier_match_key(source_id))


def _has_event_key(table: dict, metadata: dict) -> bool:
    candidates = _table_column_names(table)
    for entity in metadata.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        candidates.extend(
            str(key or "").strip() for key in entity.get("key_columns") or []
        )
    for candidate in candidates:
        name = candidate.lower()
        if not name.endswith(("_id", "_no", "_key")):
            continue
        if any(token in name for token in EVENT_KEY_TOKENS):
            return True
    return False


def _table_partition_column(
    asset_catalog: AssetCatalog | None,
    table_name: str,
) -> str:
    if not asset_catalog:
        return ""
    table_asset = asset_catalog.tables.get(table_name)
    ddl = table_asset.ddl if table_asset else None
    partition_column = ddl.partition_column.strip() if ddl else ""
    if partition_column:
        return partition_column

    path = ddl.path if ddl else None
    if not path:
        return ""
    try:
        return extract_doris_partition_column(
            Path(path).read_text(encoding=TEXT_ENCODING)
        )
    except (OSError, TypeError):
        return ""


def _grain_group_by_mismatch(metadata: dict, sql_facts: dict) -> dict:
    grain_keys = grain_key_columns(metadata)
    group_outputs = sorted(set(sql_facts.get("group_output_columns") or []))
    missing_in_group_by = missing_identifier_names(grain_keys, group_outputs)
    extra_group_by = missing_identifier_names(group_outputs, grain_keys)
    return {
        "grain_keys": sorted(grain_keys),
        "group_by_columns": sql_facts.get("group_by_columns") or [],
        "group_output_columns": group_outputs,
        "missing_in_group_by": missing_in_group_by,
        "extra_group_by": extra_group_by,
        "matched": not missing_in_group_by and not extra_group_by,
    }
