"""Naming convention dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    _tables_for_naming,
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


def _empty_file_score() -> dict:
    return dict(
        passed=0,
        total=0,
        checks=[],
    )


def _task_name(task: dict) -> str:
    return str(task.get("expected_table") or task.get("file") or "")


def _score_file_naming_conventions(
    asset_catalog: dict,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return _empty_file_score()

    table_scope = scoped_names(scope, "tables")
    task_scope = scoped_names(scope, "tasks")
    table_targets = list((asset_catalog.get("tables") or {}).values())
    if table_scope is not None:
        table_targets = [
            target
            for target in table_targets
            if target.get("name") in table_scope
        ]
    task_targets = [
        {"task": task}
        for task in asset_catalog.get("tasks") or []
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
    if catalog.get("project_dir"):
        naming_tables = [
            dict(
                name=name,
                layer=asset.get("layer", "OTHER"),
                columns=asset.get("columns") or [],
            )
            for name, asset in catalog.get("tables", {}).items()
            if asset.get("ddl")
        ]
    else:
        naming_tables = _tables_for_naming(tables, None, model_metadata)

    atomic_rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    derived_rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    return dict(
        nc=nc,
        models=model_metadata or {},
        business_domain_config=business_domain_config,
        assets=catalog,
        middle=[
            table
            for table in naming_tables
            if table["layer"] in {"DWD", "DWS", "DIM"}
        ],
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
    for table in middle:
        checks.extend(
            runner.run_rules(
                [
                    "NAMING_TABLE_TEMPLATE",
                    "NAMING_TABLE_MAX_LENGTH",
                    "NAMING_COLUMN_NAME",
                    "NAMING_ATOMIC_METRIC",
                    "NAMING_DERIVED_METRIC",
                    "NAMING_DWS_ENTITY_ALIGNMENT",
                    "NAMING_DIM_ENTITY_ALIGNMENT",
                    "NAMING_DIM_CLASSIFICATION_ALIGNMENT",
                    "NAMING_SEMANTIC_METADATA_ALIGNMENT",
                ],
                [table],
                context,
            )
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
    return finalize_dimension(
        dimension="naming",
        score=round(total_passed / total_checks * 100, 1)
        if total_checks
        else 100.0,
        checks=checks,
        rules=selected_rules(NAMING_RULES, rule_selection),
        summary={
            "file_checks": dict(
                passed=file_result["passed"],
                total=file_result["total"],
            ),
        },
    )
