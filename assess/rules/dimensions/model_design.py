"""Model design health dimension execution."""

from __future__ import annotations

from collections import defaultdict

from assess.assessment_context import AssessmentContext
from assess.result_model import finalize_dimension
from assess.rules.definitions.model_design import (
    _combined_design_facts,
    _is_fact_table,
    _metric_group_names,
    _table_metadata,
    _table_partition_column,
    _upstream_tables_for,
)
from assess.rules.engine.filtering import selected_rules
from assess.rules.engine.runner import RuleRunner
from assess.rules.engine.selection import RuleSelection
from assess.scoped_plan import scoped_names
from assess.scoring.config import (
    MODEL_DESIGN_RULES,
    PER_TABLE_CAP,
    SEVERITY_WEIGHT,
)
from config import layer_rank


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
    model_metadata = context.models
    business_domain_config = context.business_domain_config
    asset_catalog = context.assets
    rules = selected_rules(MODEL_DESIGN_RULES, rule_selection)

    runner = RuleRunner(rule_selection)
    checks = []
    design_facts_cache = {}
    upstream_tables_cache = {}
    table_scope = scoped_names(scope, "tables")
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
    checks.extend(
        runner.run_rules(
            [
                "ARCH_REVERSE_DEPENDENCY",
                "ARCH_SAME_LAYER_DEPENDENCY",
                "ARCH_SKIP_LAYER_DEPENDENCY",
            ],
            dependency_targets,
            {},
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
        checks.extend(
            runner.run_rules(
                [
                    "ARCH_DECLARED_LAYER_MATCHES_LLM",
                    "ARCH_DWD_DIMENSION_POSITION",
                    "ARCH_TABLE_TYPE_MATCHES_LLM",
                    "ARCH_DATA_DOMAIN_MATCHES_LLM",
                    "ARCH_BUSINESS_AREA_MATCHES_LLM",
                ],
                llm_targets,
                {
                    "model_metadata": model_metadata,
                    "business_domain_config": business_domain_config,
                },
            )
        )

    table_targets = []
    for table in tables:
        table_name = str(table.get("name") or "").strip()
        if not table_name:
            continue
        if table_scope is not None and table_name not in table_scope:
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
    table_count = len(table_targets)

    table_rule_context = {
        "model_metadata": model_metadata,
        "table_edges": table_edges,
        "table_layers": table_layers,
        "design_facts_for": design_facts_for,
        "upstream_tables_for": upstream_tables_for,
    }

    for target in table_targets:
        checks.extend(
            runner.run_rules(
                [
                    "MODEL_DIM_NO_METRIC_GROUPS",
                    "MODEL_DIM_INFO_DIRECT_ODS_ONLY",
                    "MODEL_DATE_PARTITION_USES_DATA_DT",
                ],
                [target],
                table_rule_context,
            )
        )
        if not target["is_fact_table"]:
            continue
        if target["layer"] == "DWD":
            checks.extend(
                runner.run_rules(
                    [
                        "MODEL_DWD_FACT_NO_AGGREGATION",
                        "MODEL_DWD_FACT_SINGLE_BUSINESS_PROCESS",
                        "MODEL_DWD_FACT_HAS_PRIMARY_ENTITY_OR_GRAIN",
                        "MODEL_DWD_FACT_NO_DERIVED_METRICS",
                        "MODEL_DWD_FACT_HAS_EVENT_KEY",
                    ],
                    [target],
                    table_rule_context,
                )
            )
        if target["layer"] == "DWS":
            checks.extend(
                runner.run_rules(
                    [
                        "MODEL_DWS_GRAIN_PRESENT",
                        "MODEL_DWS_FACT_HAS_AGGREGATION",
                        "MODEL_DERIVED_METRIC_BASE_ATOMIC",
                        "MODEL_DWS_GRAIN_MATCHES_GROUP_BY",
                        "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN",
                    ],
                    [target],
                    table_rule_context,
                )
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

    return finalize_dimension(
        dimension="model_design",
        score=score,
        checks=checks,
        rules=rules,
        summary={
            "table_count": table_count,
            "capped_total": capped_total,
            "table_capped": table_capped,
        },
    )
