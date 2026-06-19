"""Model metadata health dimension execution."""

from __future__ import annotations

from assess.assessment_context import AssessmentContext
from assess.project_facts.entity_metadata import model_entities
from assess.result_model import finalize_dimension
from assess.rules.definitions.metadata_health import (
    _as_string_list,
    _model_entity_codes,
    _table_column_names,
)
from assess.rules.engine.filtering import selected_rules
from assess.rules.engine.runner import RuleRunner
from assess.rules.engine.selection import RuleSelection
from assess.scoring.config import METADATA_HEALTH_RULES


def score_metadata_health(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
) -> dict:
    """检查 models/*.yaml 的结构自洽性与业务元数据有效性。"""
    rules = selected_rules(METADATA_HEALTH_RULES, rule_selection)
    tables = context.tables
    nc = context.naming_config
    model_metadata = context.models
    business_domain_config = context.business_domain_config
    asset_catalog = context.assets
    if not model_metadata:
        return finalize_dimension(
            dimension="metadata_health",
            score=100.0,
            checks=[],
            rules=rules,
        )

    if asset_catalog and asset_catalog.get("tables"):
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

    targets = []
    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        table = tables_by_name.get(table_name)
        columns = _table_column_names(table) if table else set()
        entities = model_entities(metadata)
        entity_codes = _model_entity_codes(metadata)
        grain = metadata.get("grain")
        layer = str(
            metadata.get("layer") or (table or {}).get("layer") or "OTHER"
        ).upper()
        targets.append(
            {
                "table_name": table_name,
                "metadata": metadata,
                "table": table,
                "columns": columns,
                "entities": entities,
                "entity_codes": entity_codes,
                "primary_code": entity_codes[0] if entity_codes else "",
                "grain": grain,
                "grain_entities": (
                    _as_string_list(grain.get("entities"))
                    if isinstance(grain, dict)
                    else []
                ),
                "layer": layer,
            }
        )

    runner = RuleRunner(rule_selection)
    rule_context = {
        "business_domain_config": business_domain_config,
        "naming_config": nc,
    }
    checks = []
    for target in targets:
        if target["layer"] == "DIM":
            checks.extend(
                runner.run_rules(
                    [
                        "METADATA_DIM_HAS_PRIMARY_ENTITY",
                        "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY",
                    ],
                    [target],
                    rule_context,
                )
            )
        if target["table"]:
            for entity in target["entities"]:
                entity_target = dict(target)
                entity_target["entity"] = entity
                checks.extend(
                    runner.run_rules(
                        [
                            "METADATA_ENTITY_KEYS_EXIST",
                            "METADATA_RELATIONSHIP_FROM_PRIMARY",
                            "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY",
                        ],
                        [entity_target],
                        rule_context,
                    )
                )
        checks.extend(
            runner.run_rules(
                ["METADATA_GRAIN_KEYS_EXIST"],
                [target],
                rule_context,
            )
        )
        checks.extend(
            runner.run_rules(
                [
                    "METADATA_GRAIN_ENTITIES_DEFINED",
                    "METADATA_GRAIN_ENTITIES_PRESENT",
                    "METADATA_DATA_DOMAIN_VALID",
                    "METADATA_BUSINESS_AREA_VALID",
                ],
                [target],
                rule_context,
            )
        )
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="metadata_health",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=rules,
    )
