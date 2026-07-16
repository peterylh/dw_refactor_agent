"""Model metadata health dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    model_entities,
)
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.metadata_health import (
    _as_string_list,
    _model_entity_codes,
    _table_column_names,
)
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import METADATA_HEALTH_RULES


def score_metadata_health(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
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

    if asset_catalog.tables:
        tables_by_name = {
            name: dict(
                name=name,
                layer=asset.layer,
                columns=asset.columns,
            )
            for name, asset in asset_catalog.tables.items()
            if asset.ddl or asset.lineage_table
        }
    else:
        tables_by_name = {table["name"]: table for table in tables}

    targets = []
    table_scope = scoped_names(scope, "tables")
    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        if table_scope is not None and table_name not in table_scope:
            continue
        asset = asset_catalog.tables.get(table_name)
        table = tables_by_name.get(table_name)
        columns = _table_column_names(table) if table else set()
        entities = model_entities(metadata)
        entity_codes = _model_entity_codes(metadata)
        grain = metadata.get("grain")
        layer = str(metadata.get("layer") or "OTHER").upper()
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
                "model": asset.model if asset and asset.model else {},
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
        "project_dir": asset_catalog.project_dir,
    }
    checks = []
    for target in targets:
        checks.extend(
            runner.run_rules(
                ["METADATA_MODEL_LAYER_MATCHES_ASSET_PATH"],
                [target],
                rule_context,
            )
        )
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
            checks.extend(
                runner.run_rules(
                    ["METADATA_MODEL_COLUMN_SPELLING_MATCHES_DDL"],
                    [target],
                    rule_context,
                )
            )
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
