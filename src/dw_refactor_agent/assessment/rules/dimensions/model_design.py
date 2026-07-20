"""Model design health dimension execution."""

from __future__ import annotations

from collections import defaultdict

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.model_design import (
    _combined_design_facts,
    _is_fact_table,
    _metric_group_names,
    _table_metadata,
    _table_partition_column,
    _upstream_tables_for,
)
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import (
    MODEL_DESIGN_RULES,
    PER_TABLE_CAP,
    SEVERITY_WEIGHT,
)
from dw_refactor_agent.assessment.semantic_models import (
    semantic_coverage_dict,
)
from dw_refactor_agent.config import layer_rank


def score_model_design_health(
    context: AssessmentContext,
    llm_results: list | None = None,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    """Score model design health."""
    tables = context.tables
    table_layers = context.table_layers
    lineage_view = context.lineage
    table_edges = context.table_edges
    raw_model_metadata = context.models or {}
    business_domain_config = context.business_domain_config
    asset_catalog = context.assets
    rules = selected_rules(MODEL_DESIGN_RULES, rule_selection)

    runner = RuleRunner(rule_selection)
    checks = []
    design_facts_cache = {}
    upstream_tables_cache = {}
    table_scope = scoped_names(scope, "tables")
    eligible_names = [
        str(table.get("name"))
        for table in tables
        if table.get("name")
        and (table_scope is None or table.get("name") in table_scope)
    ]
    incomplete_names = set()
    unavailable_penalty_tables = set()
    assessed_rule_tables = set()
    required_sections = set()

    def unavailable_sections(table_name: str, sections) -> tuple[str, ...]:
        view = context.model_view(table_name)
        if view is None:
            return ()
        return tuple(
            section
            for section in sections
            if view.status(section) == "quarantined"
        )

    def run_available(
        rule_ids,
        target,
        rule_context,
        *,
        target_table,
        dependencies,
    ):
        enabled = [
            rule_id for rule_id in rule_ids if runner.is_enabled(rule_id)
        ]
        if not enabled:
            return []
        unavailable_by_table = {
            name: unavailable_sections(name, sections)
            for name, sections in dependencies.items()
        }
        unavailable_by_table = {
            name: sections
            for name, sections in unavailable_by_table.items()
            if sections
        }
        for sections in dependencies.values():
            required_sections.update(sections)
        if unavailable_by_table:
            incomplete_names.add(target_table)
            incomplete_names.update(unavailable_by_table)
            unavailable_penalty_tables.add(target_table)
            return []
        assessed_rule_tables.add(target_table)
        return runner.run_rules(enabled, [target], rule_context)

    model_metadata = {
        name: view.canonical_semantic_mapping()
        for name in raw_model_metadata
        for view in [context.model_view(name)]
        if view is not None
    }
    edge_pairs = None
    if scope and scope.get("mode") == "scoped" and "edges" in scope:
        edge_pairs = {
            (edge.get("source"), edge.get("target"))
            for edge in scope.get("edges", [])
        }

    def design_facts_for(table_name: str) -> dict:
        if table_name not in design_facts_cache:
            design_facts_cache[table_name] = _combined_design_facts(
                asset_catalog,
                lineage_view,
                table_name,
            )
        return design_facts_cache[table_name]

    def upstream_tables_for(table_name: str) -> list[str]:
        if table_name not in upstream_tables_cache:
            upstream_tables_cache[table_name] = _upstream_tables_for(
                table_name,
                table_edges,
            )
        return upstream_tables_cache[table_name]

    dependency_targets = []
    for (src, tgt), files in table_edges.items():
        if edge_pairs is not None and (src, tgt) not in edge_pairs:
            continue
        dependency_rule_ids = [
            "ARCH_REVERSE_DEPENDENCY",
            "ARCH_SAME_LAYER_DEPENDENCY",
            "ARCH_SKIP_LAYER_DEPENDENCY",
        ]
        if not any(
            runner.is_enabled(rule_id) for rule_id in dependency_rule_ids
        ):
            continue
        unavailable = {
            name: unavailable_sections(name, ("classification",))
            for name in (src, tgt)
        }
        unavailable = {
            name: sections
            for name, sections in unavailable.items()
            if sections
        }
        required_sections.add("classification")
        if unavailable:
            incomplete_names.add(tgt)
            incomplete_names.update(unavailable)
            unavailable_penalty_tables.add(tgt)
            continue
        src_layer = table_layers.get(src, "OTHER")
        tgt_layer = table_layers.get(tgt, "OTHER")
        src_rank = layer_rank(src_layer)
        tgt_rank = layer_rank(tgt_layer)
        if src_rank < 0 or tgt_rank < 0:
            continue
        rank_diff = src_rank - tgt_rank
        dependency_targets.append(
            {
                "kind": "dependency",
                "source": src,
                "source_layer": src_layer,
                "target_table": tgt,
                "target_layer": tgt_layer,
                "rank_diff": rank_diff,
                "evidence": {
                    "source": src,
                    "source_layer": src_layer,
                    "target": tgt,
                    "target_layer": tgt_layer,
                    "source_files": sorted(files),
                    "rank_diff": rank_diff,
                },
            }
        )
    for target in dependency_targets:
        checks.extend(
            run_available(
                dependency_rule_ids,
                target,
                {},
                target_table=target["target_table"],
                dependencies={
                    target["source"]: ("classification",),
                    target["target_table"]: ("classification",),
                },
            )
        )

    if llm_results:
        table_map = {table["name"]: table for table in tables}
        llm_targets = [
            {
                "kind": "llm",
                "table_name": name,
                "llm_result": result,
                "layer": (
                    table_map[name]["layer"] if name in table_map else "OTHER"
                ),
            }
            for name, result in {
                result.table_name: result for result in llm_results
            }.items()
            if table_scope is None or name in table_scope
        ]
        llm_rule_context = {
            "model_metadata": model_metadata,
            "business_domain_config": business_domain_config,
        }
        llm_rule_sections = {
            "ARCH_DECLARED_LAYER_MATCHES_LLM": ("classification",),
            "ARCH_DWD_DIMENSION_POSITION": ("classification",),
            "ARCH_TABLE_TYPE_MATCHES_LLM": ("classification",),
            "ARCH_DATA_DOMAIN_MATCHES_LLM": (
                "classification",
                "business_semantics",
            ),
            "ARCH_BUSINESS_AREA_MATCHES_LLM": (
                "classification",
                "business_semantics",
            ),
        }
        for target in llm_targets:
            table_name = target["table_name"]
            for rule_id, sections in llm_rule_sections.items():
                checks.extend(
                    run_available(
                        [rule_id],
                        target,
                        llm_rule_context,
                        target_table=table_name,
                        dependencies={table_name: sections},
                    )
                )

    table_targets = []
    for table in tables:
        table_name = str(table.get("name") or "").strip()
        if not table_name:
            continue
        if table_scope is not None and table_name not in table_scope:
            continue
        if unavailable_sections(table_name, ("classification",)):
            incomplete_names.add(table_name)
            unavailable_penalty_tables.add(table_name)
            required_sections.add("classification")
            continue
        layer = str(table.get("layer") or "OTHER").upper()
        metadata = _table_metadata(model_metadata, table_name)
        is_fact = _is_fact_table(model_metadata, table_name)
        table_targets.append(
            {
                "kind": "table",
                "table": table,
                "table_name": table_name,
                "layer": layer,
                "metadata": metadata,
                "metric_groups": _metric_group_names(metadata),
                "is_fact_table": is_fact,
                "partition_column": _table_partition_column(
                    asset_catalog,
                    table_name,
                ),
            }
        )
    table_count = len(eligible_names)

    table_rule_context = {
        "model_metadata": model_metadata,
        "table_edges": table_edges,
        "table_layers": table_layers,
        "design_facts_for": design_facts_for,
        "upstream_tables_for": upstream_tables_for,
    }

    def run_table_rule(
        target,
        rule_id,
        sections,
        extra_dependencies=None,
    ):
        table_name = target["table_name"]
        dependencies = {table_name: tuple(sections)}
        dependencies.update(extra_dependencies or {})
        checks.extend(
            run_available(
                [rule_id],
                target,
                table_rule_context,
                target_table=table_name,
                dependencies=dependencies,
            )
        )

    for target in table_targets:
        table_name = target["table_name"]
        semantic_metadata = target["metadata"]
        table_type = str(semantic_metadata.get("table_type") or "").lower()

        if target["layer"] == "DIM" or table_type == "dimension":
            run_table_rule(
                target,
                "MODEL_DIM_NO_METRIC_GROUPS",
                ("classification", "metrics"),
            )
        if (
            target["layer"] == "DIM"
            and table_type == "dimension"
            and str(
                semantic_metadata.get("dimension_content_type") or ""
            ).upper()
            == "INFO"
        ):
            run_table_rule(
                target,
                "MODEL_DIM_INFO_DIRECT_ODS_ONLY",
                ("classification",),
                {
                    upstream: ("classification",)
                    for upstream in upstream_tables_for(table_name)
                },
            )
        if (
            target["layer"] in {"DWD", "DWS", "DIM"}
            and target["partition_column"]
        ):
            run_table_rule(
                target,
                "MODEL_DATE_PARTITION_USES_DATA_DT",
                ("classification",),
            )
        if not target["is_fact_table"]:
            continue
        if target["layer"] == "DWD":
            run_table_rule(
                target,
                "MODEL_DWD_FACT_NO_AGGREGATION",
                ("classification",),
            )
            run_table_rule(
                target,
                "MODEL_DWD_FACT_SINGLE_BUSINESS_PROCESS",
                ("classification", "business_semantics", "metrics"),
            )
            run_table_rule(
                target,
                "MODEL_DWD_FACT_HAS_PRIMARY_ENTITY_OR_GRAIN",
                ("classification", "entities", "grain"),
            )
            run_table_rule(
                target,
                "MODEL_DWD_FACT_NO_DERIVED_METRICS",
                ("classification", "metrics"),
            )
            run_table_rule(
                target,
                "MODEL_DWD_FACT_HAS_EVENT_KEY",
                ("classification", "entities"),
            )
        if target["layer"] == "DWS":
            run_table_rule(
                target,
                "MODEL_DWS_GRAIN_PRESENT",
                ("classification", "grain"),
            )
            run_table_rule(
                target,
                "MODEL_DWS_FACT_HAS_AGGREGATION",
                ("classification",),
            )
            derived_metric_dependencies = {}
            if not unavailable_sections(
                table_name, ("metrics",)
            ) and semantic_metadata.get("derived_metrics"):
                derived_metric_dependencies = {
                    upstream: ("metrics",)
                    for upstream in upstream_tables_for(table_name)
                }
            run_table_rule(
                target,
                "MODEL_DERIVED_METRIC_BASE_ATOMIC",
                ("classification", "metrics"),
                derived_metric_dependencies,
            )
            run_table_rule(
                target,
                "MODEL_DWS_GRAIN_MATCHES_GROUP_BY",
                ("classification", "grain"),
            )
            run_table_rule(
                target,
                "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN",
                ("classification", "grain"),
            )

    table_weight = defaultdict(int)
    for check in checks:
        if check["passed"]:
            continue
        rule_id = check["rule_id"]
        issue = check.get("_issue") or {}
        effective_severity = (
            issue.get("severity") or MODEL_DESIGN_RULES[rule_id]["severity"]
        )
        table_weight[check["target"]["name"]] += SEVERITY_WEIGHT[
            effective_severity
        ]

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
    eligible_set = set(eligible_names)
    eligible_by_short = defaultdict(set)
    for name in eligible_names:
        eligible_by_short[name.split(".")[-1]].add(name)

    def eligible_identity(name):
        if name in eligible_set:
            return name
        matches = eligible_by_short.get(name.split(".")[-1]) or set()
        return next(iter(matches)) if len(matches) == 1 else None

    incomplete_eligible = {
        resolved
        for name in incomplete_names
        for resolved in [eligible_identity(name)]
        if resolved is not None
    }
    penalty_eligible = {
        resolved
        for name in unavailable_penalty_tables
        for resolved in [eligible_identity(name)]
        if resolved is not None
    }
    effective_table_capped = dict(table_capped)
    for table_name in penalty_eligible:
        effective_table_capped[table_name] = PER_TABLE_CAP
    effective_capped_total = sum(effective_table_capped.values())
    effective_score = (
        max(
            0,
            round(100 * (1 - effective_capped_total / table_count), 1),
        )
        if table_count
        else score
    )
    partial_names = {
        resolved
        for name in assessed_rule_tables
        for resolved in [eligible_identity(name)]
        if resolved is not None
    } & incomplete_eligible
    coverage = semantic_coverage_dict(
        eligible_count=table_count,
        assessed_count=table_count - len(incomplete_eligible),
        partially_assessed_count=len(partial_names),
        quarantined_names=incomplete_eligible,
        sections=sorted(required_sections),
        unit="tables",
    )

    return finalize_dimension(
        dimension="model_design",
        score=score,
        checks=checks,
        rules=rules,
        summary={
            "table_count": table_count,
            "capped_total": capped_total,
            "table_capped": table_capped,
            "effective_capped_total": effective_capped_total,
            "effective_table_capped": effective_table_capped,
        },
        coverage=coverage,
        effective_score=effective_score,
    )
