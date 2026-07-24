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
from dw_refactor_agent.assessment.semantic_models import (
    semantic_coverage_dict,
)


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

    table_scope = scoped_names(scope, "tables")
    quarantined_names = set()
    unavailable_units = 0
    required_sections = set()
    runner = RuleRunner(rule_selection)

    def run_available(rule_ids, target, view, sections):
        nonlocal unavailable_units
        enabled = [
            rule_id for rule_id in rule_ids if runner.is_enabled(rule_id)
        ]
        if not enabled:
            return []
        required_sections.update(sections)
        unavailable = [
            section
            for section in sections
            if view.status(section) == "quarantined"
        ]
        if unavailable:
            quarantined_names.add(target["table_name"])
            unavailable_units += len(enabled)
            return []
        return runner.run_rules(enabled, [target], rule_context)

    rule_context = {
        "business_domain_config": business_domain_config,
        "naming_config": nc,
        "project_dir": asset_catalog.project_dir,
    }
    checks = []
    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        if table_scope is not None and table_name not in table_scope:
            continue
        view = context.model_view(table_name)
        if view is None:
            continue
        semantic_metadata = view.canonical_semantic_mapping()
        asset = asset_catalog.tables.get(table_name)
        table = tables_by_name.get(table_name)
        columns = _table_column_names(table) if table else set()
        entities = model_entities(semantic_metadata)
        entity_codes = _model_entity_codes(semantic_metadata)
        grain = semantic_metadata.get("grain")
        layer = view.layer or "OTHER"
        target = {
            "table_name": table_name,
            "metadata": semantic_metadata,
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
        checks.extend(
            run_available(
                ["METADATA_MODEL_LAYER_MATCHES_ASSET_PATH"],
                target,
                view,
                ("classification",),
            )
        )
        effective_layer = view.layer or view.operational_layer
        if effective_layer == "DIM":
            checks.extend(
                run_available(
                    ["METADATA_DIM_HAS_PRIMARY_ENTITY"],
                    target,
                    view,
                    ("classification", "entities"),
                )
            )
            checks.extend(
                run_available(
                    ["METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY"],
                    target,
                    view,
                    ("classification", "business_semantics", "entities"),
                )
            )
        if target["table"]:
            checks.extend(
                run_available(
                    ["METADATA_MODEL_COLUMN_SPELLING_MATCHES_DDL"],
                    target,
                    view,
                    ("entities", "grain"),
                )
            )
            if view.status("entities") == "quarantined":
                checks.extend(
                    run_available(
                        [
                            "METADATA_ENTITY_KEYS_EXIST",
                            "METADATA_RELATIONSHIP_FROM_PRIMARY",
                            "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY",
                        ],
                        target,
                        view,
                        ("entities",),
                    )
                )
            else:
                for entity in target["entities"]:
                    entity_target = dict(target)
                    entity_target["entity"] = entity
                    checks.extend(
                        run_available(
                            [
                                "METADATA_ENTITY_KEYS_EXIST",
                                "METADATA_RELATIONSHIP_FROM_PRIMARY",
                                "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY",
                            ],
                            entity_target,
                            view,
                            ("entities",),
                        )
                    )
        checks.extend(
            run_available(
                ["METADATA_GRAIN_KEYS_EXIST"],
                target,
                view,
                ("grain",),
            )
        )
        checks.extend(
            run_available(
                ["METADATA_GRAIN_ENTITIES_DEFINED"],
                target,
                view,
                ("entities", "grain"),
            )
        )
        checks.extend(
            run_available(
                ["METADATA_GRAIN_ENTITIES_PRESENT"],
                target,
                view,
                ("classification", "grain"),
            )
        )
        checks.extend(
            run_available(
                [
                    "METADATA_DATA_DOMAIN_VALID",
                    "METADATA_BUSINESS_AREA_VALID",
                ],
                target,
                view,
                ("classification", "business_semantics"),
            )
        )
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    coverage = semantic_coverage_dict(
        eligible_count=total + unavailable_units,
        assessed_count=total,
        quarantined_names=quarantined_names,
        sections=sorted(required_sections),
        unit="rule_checks",
    )
    score = round(passed / total * 100, 1) if total else 100.0
    return finalize_dimension(
        dimension="metadata_health",
        score=score,
        checks=checks,
        rules=rules,
        coverage=coverage,
        # Withheld entity/metric cardinality is unknown, so no finite
        # synthetic check count can safely bound the hidden failure rate.
        effective_score=0.0 if quarantined_names else score,
    )
