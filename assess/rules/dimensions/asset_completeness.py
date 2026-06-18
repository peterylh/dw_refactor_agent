"""Asset completeness dimension execution."""

from __future__ import annotations

from assess.assessment_context import AssessmentContext
from assess.result_model import finalize_dimension
from assess.rules.engine.filtering import selected_rules
from assess.rules.engine.runner import RuleRunner
from assess.rules.engine.selection import RuleSelection
from assess.scoring.config import ASSET_COMPLETENESS_RULES


def _logical_task_key(task: dict) -> str:
    return str(task.get("expected_table") or task.get("file") or "")


def score_asset_completeness(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
) -> dict:
    """Score DDL/model/task closure and task-lineage consistency."""
    asset_catalog = context.assets
    rules = selected_rules(ASSET_COMPLETENESS_RULES, rule_selection)

    assets = asset_catalog.get("tables") or {}
    table_targets = []
    for name, asset in sorted(assets.items()):
        has_ddl = bool(asset.get("ddl"))
        has_model = bool(asset.get("model"))
        tasks = asset.get("tasks") or []
        has_output_task = any(
            name in task.get("output_tables", set()) for task in tasks
        )
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
            for task in asset_catalog.get("tasks") or []
            for output in task.get("output_tables", set())
        }
    )
    task_targets = [
        {"kind": "task", "task": task}
        for task in asset_catalog.get("tasks") or []
    ]

    for output in task_outputs:
        task_targets.append(
            {
                "kind": "output",
                "output": output,
                "asset": assets.get(output, {}),
            }
        )

    writers_by_output = {}
    for task in asset_catalog.get("tasks") or []:
        for output in task.get("output_tables") or set():
            writers_by_output.setdefault(output, {}).setdefault(
                _logical_task_key(task),
                set(),
            ).add(task["file"])

    for output, writers_by_key in sorted(writers_by_output.items()):
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
