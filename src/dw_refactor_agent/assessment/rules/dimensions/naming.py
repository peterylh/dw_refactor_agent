"""Naming convention dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    AssetCatalog,
    TaskAsset,
)
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.naming import (
    _metric_rule_label,
    _metric_rule_name,
)
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import (
    ATOMIC_METRIC_RULE_NAME,
    DERIVED_METRIC_RULE_NAME,
    NAMING_RULES,
)
from dw_refactor_agent.assessment.semantic_models import (
    semantic_coverage_dict,
)


def _empty_file_score() -> dict:
    return dict(
        passed=0,
        total=0,
        checks=[],
    )


def _task_name(task: TaskAsset) -> str:
    return task.expected_table or task.file


def _score_file_naming_conventions(
    asset_catalog: AssetCatalog,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    project_dir = asset_catalog.project_dir
    if not project_dir:
        return _empty_file_score()

    table_scope = scoped_names(scope, "tables")
    task_scope = scoped_names(scope, "tasks")
    table_targets = list(asset_catalog.tables.values())
    if table_scope is not None:
        table_targets = [
            target for target in table_targets if target.name in table_scope
        ]
    task_targets = [
        {"task": task}
        for task in asset_catalog.tasks
        if task_scope is None or _task_name(task) in task_scope
    ]
    runner = RuleRunner(rule_selection)
    checks = []
    checks.extend(
        runner.run_rules(
            ["NAMING_DDL_FILE_NAME", "NAMING_MODEL_FILE_NAME"],
            table_targets,
            {"project_dir": project_dir},
        )
    )
    checks.extend(
        runner.run_rules(
            ["NAMING_TASK_OUTPUT_NAME"],
            task_targets,
            {"project_dir": project_dir},
        )
    )
    return {
        "passed": sum(
            check.get("_score_passed", int(check["passed"]))
            for check in checks
        ),
        "total": sum(check.get("_score_total", 1) for check in checks),
        "checks": checks,
    }


def _prepare_naming_context(
    assessment_context: AssessmentContext,
) -> dict:
    catalog = assessment_context.assets
    tables = assessment_context.tables
    nc = assessment_context.naming_config
    model_metadata = assessment_context.models
    business_domain_config = assessment_context.business_domain_config
    if catalog.project_dir:
        naming_tables = [
            dict(
                name=name,
                layer=(
                    assessment_context.model_view(name).layer
                    if assessment_context.model_view(name) is not None
                    else asset.layer
                ),
                columns=asset.columns,
            )
            for name, asset in catalog.tables.items()
            if asset.ddl
        ]
    else:
        naming_tables = [
            {
                **dict(table),
                "layer": (
                    assessment_context.model_view(table.get("name")).layer
                    if assessment_context.model_view(table.get("name"))
                    is not None
                    else table.get("layer")
                ),
            }
            for table in tables
        ]

    eligible_names = [
        table["name"]
        for table in naming_tables
        if (
            assessment_context.operational_layer(table["name"])
            or table.get("layer")
        )
        in {"DWD", "DWS", "DIM"}
    ]
    semantic_models = {
        name: view.canonical_semantic_mapping()
        for name in (model_metadata or {})
        for view in [assessment_context.model_view(name)]
        if view is not None
    }

    atomic_rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    derived_rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    return dict(
        nc=nc,
        models=semantic_models,
        assessment_context=assessment_context,
        business_domain_config=business_domain_config,
        assets=catalog,
        middle=[
            table
            for table in naming_tables
            if table["name"] in set(eligible_names)
        ],
        eligible_names=eligible_names,
        atomic_rule_name=atomic_rule_name,
        derived_rule_name=derived_rule_name,
        atomic_rule_label=_metric_rule_label(
            nc,
            ATOMIC_METRIC_RULE_NAME,
            atomic_rule_name,
        ),
        derived_rule_label=_metric_rule_label(
            nc,
            DERIVED_METRIC_RULE_NAME,
            derived_rule_name,
        ),
    )


def score_naming_conventions(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    context = _prepare_naming_context(context)
    runner = RuleRunner(rule_selection)
    checks = []
    table_scope = scoped_names(scope, "tables")
    middle = context["middle"]
    if table_scope is not None:
        middle = [
            table for table in middle if table.get("name") in table_scope
        ]
    assessment_context = context["assessment_context"]
    quarantined_names = set()
    unavailable_units = 0
    required_sections = set()

    def run_available(rule_id, table, sections, *, units=1):
        nonlocal unavailable_units
        if not runner.is_enabled(rule_id):
            return
        required_sections.update(sections)
        view = assessment_context.model_view(table["name"])
        unavailable = [
            section
            for section in sections
            if view is not None and view.status(section) == "quarantined"
        ]
        if unavailable:
            quarantined_names.add(table["name"])
            unavailable_units += max(1, int(units))
            return
        checks.extend(runner.run_rules([rule_id], [table], context))

    for table in middle:
        view = assessment_context.model_view(table["name"])
        layer = (
            (view.layer or view.operational_layer)
            if view is not None
            else table.get("layer")
        )
        table_type = view.table_type if view is not None else None
        run_available("NAMING_TABLE_TEMPLATE", table, ("classification",))
        run_available("NAMING_TABLE_MAX_LENGTH", table, ("classification",))
        run_available(
            "NAMING_COLUMN_NAME",
            table,
            ("classification", "metrics"),
            units=max(1, len(table.get("columns") or [])),
        )
        if layer in {"DWD", "DWS"} and table_type in {None, "fact"}:
            run_available(
                "NAMING_ATOMIC_METRIC",
                table,
                ("classification", "metrics"),
            )
            run_available(
                "NAMING_DERIVED_METRIC",
                table,
                ("classification", "metrics"),
            )
        if layer == "DWS":
            run_available(
                "NAMING_DWS_ENTITY_ALIGNMENT",
                table,
                ("classification", "grain"),
            )
        if layer == "DIM":
            run_available(
                "NAMING_DIM_ENTITY_ALIGNMENT",
                table,
                ("classification", "entities"),
            )
            run_available(
                "NAMING_DIM_CLASSIFICATION_ALIGNMENT",
                table,
                ("classification",),
            )
        if layer in {"DWD", "DWS"}:
            run_available(
                "NAMING_SEMANTIC_METADATA_ALIGNMENT",
                table,
                ("classification", "business_semantics"),
            )
    file_result = _score_file_naming_conventions(
        context["assets"],
        rule_selection,
        scope=scope,
    )
    checks.extend(file_result.get("checks") or [])
    total_passed = sum(
        check.get("_score_passed", int(check["passed"])) for check in checks
    )
    total_checks = sum(check.get("_score_total", 1) for check in checks)
    coverage = semantic_coverage_dict(
        eligible_count=total_checks + unavailable_units,
        assessed_count=total_checks,
        quarantined_names=quarantined_names,
        sections=sorted(required_sections),
        unit="rule_checks",
    )
    score = (
        round(total_passed / total_checks * 100, 1) if total_checks else 100.0
    )
    return finalize_dimension(
        dimension="naming",
        score=score,
        checks=checks,
        rules=selected_rules(NAMING_RULES, rule_selection),
        summary={
            "file_checks": dict(
                passed=file_result["passed"],
                total=file_result["total"],
            ),
        },
        coverage=coverage,
        # Metric cardinality is withheld, so the only safe lower bound for
        # a partially assessed naming dimension is zero.
        effective_score=0.0 if quarantined_names else score,
    )
