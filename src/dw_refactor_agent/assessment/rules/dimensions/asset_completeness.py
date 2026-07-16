"""Asset completeness dimension execution."""

from __future__ import annotations

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    TableAsset,
    TaskAsset,
)
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.engine.filtering import selected_rules
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.assessment.scoring.config import (
    ASSET_COMPLETENESS_RULES,
)


def _logical_task_key(task: TaskAsset) -> str:
    return task.expected_table or task.file


def score_asset_completeness(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    """Score DDL/model/task closure and task-lineage consistency."""
    asset_catalog = context.assets
    rules = selected_rules(ASSET_COMPLETENESS_RULES, rule_selection)
    table_scope = scoped_names(scope, "tables")
    task_scope = scoped_names(scope, "tasks")

    assets = asset_catalog.tables
    table_targets = []
    for name, asset in sorted(assets.items()):
        if table_scope is not None and name not in table_scope:
            continue
        has_ddl = bool(asset.ddl)
        has_model = bool(asset.model)
        tasks = asset.tasks
        has_output_task = any(name in task.output_tables for task in tasks)
        table_targets.append(
            {
                "kind": "table",
                "name": name,
                "asset": asset,
                "has_ddl": has_ddl,
                "has_model": has_model,
                "has_output_task": has_output_task,
            }
        )

    task_outputs = sorted(
        {
            output
            for task in asset_catalog.tasks
            for output in task.output_tables
        }
    )
    task_targets = [
        {"kind": "task", "task": task}
        for task in asset_catalog.tasks
        if task_scope is None or _logical_task_key(task) in task_scope
    ]

    for output in task_outputs:
        if table_scope is not None and output not in table_scope:
            continue
        task_targets.append(
            {
                "kind": "output",
                "output": output,
                "asset": assets.get(output, TableAsset(name=output)),
            }
        )

    writers_by_output = {}
    for task in asset_catalog.tasks:
        for output in task.output_tables:
            writers_by_output.setdefault(output, {}).setdefault(
                _logical_task_key(task),
                set(),
            ).add(task.file)

    for output, writers_by_key in sorted(writers_by_output.items()):
        if table_scope is not None and output not in table_scope:
            continue
        task_targets.append(
            {
                "kind": "writer",
                "output": output,
                "writers_by_key": writers_by_key,
            }
        )

    runner = RuleRunner(rule_selection)
    checks = runner.run_rules(
        [
            "ASSET_DDL_HAS_MODEL",
            "ASSET_EXECUTABLE_DDL_HAS_TASK",
            "ASSET_MODEL_HAS_DDL",
        ],
        table_targets,
        {},
    )

    task_only_targets = [
        target for target in task_targets if target["kind"] == "task"
    ]
    output_targets = [
        target for target in task_targets if target["kind"] == "output"
    ]
    writer_targets = [
        target for target in task_targets if target["kind"] == "writer"
    ]

    checks.extend(
        runner.run_rules(
            ["ASSET_TASK_SINGLE_OUTPUT"],
            task_only_targets,
            {},
        )
    )
    checks.extend(
        runner.run_rules(
            ["ASSET_TASK_OUTPUT_HAS_DDL", "ASSET_TASK_OUTPUT_HAS_MODEL"],
            output_targets,
            {},
        )
    )
    checks.extend(
        runner.run_rules(
            ["ASSET_TABLE_SINGLE_WRITER"],
            writer_targets,
            {},
        )
    )
    checks.extend(
        runner.run_rules(
            ["ASSET_TASK_LINEAGE_MATCHES_OUTPUT"],
            task_only_targets,
            {},
        )
    )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="asset_completeness",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=rules,
    )
