"""SQL task code quality dimension execution."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    AssetCatalog,
    TaskAsset,
)
from dw_refactor_agent.assessment.result_model import finalize_dimension
from dw_refactor_agent.assessment.rules.definitions.task_sql_quality import (
    CODE_QUALITY_RULES,
    _display_file_path,
    _scan_task_source_tables,
    _scan_task_sql,
    _short_table_name,
)
from dw_refactor_agent.assessment.rules.engine.runner import RuleRunner
from dw_refactor_agent.assessment.rules.engine.selection import (
    RuleSelection,
    normalize_rule_selection,
)
from dw_refactor_agent.assessment.scoped_plan import scoped_names
from dw_refactor_agent.config import TEXT_ENCODING


def _governed_table_names(asset_catalog: AssetCatalog) -> set[str]:
    governed = set()
    for table_name, asset in asset_catalog.tables.items():
        if (asset.ddl and asset.ddl.exists) or (
            asset.model and asset.model.exists
        ):
            governed.add(_short_table_name(table_name).lower())
    return governed


def _normalized_path(value) -> str:
    return str(value or "").replace("\\", "/").strip()


def _task_file_matches(
    *,
    project_dir,
    task: TaskAsset,
    task_path: Path,
    scoped_task_files: set[str],
) -> bool:
    if not scoped_task_files:
        return True

    file_name = _display_file_path(project_dir, task_path)
    candidates = {
        _normalized_path(task.file),
        _normalized_path(file_name),
        _normalized_path(task_path),
    }
    if file_name:
        candidates.add(f"warehouses/{_normalized_path(file_name)}")

    for scoped_file in scoped_task_files:
        scoped_file = _normalized_path(scoped_file)
        if not scoped_file:
            continue
        if scoped_file in candidates:
            return True
        if any(
            scoped_file.endswith(f"/{candidate}") for candidate in candidates
        ):
            return True
        if any(
            candidate.endswith(f"/{scoped_file}") for candidate in candidates
        ):
            return True
    return False


def score_code_quality(
    context: AssessmentContext,
    rule_selection: RuleSelection | None = None,
    scope: dict | None = None,
) -> dict:
    """Score task SQL code quality checks."""
    rule_selection = normalize_rule_selection(rule_selection)
    asset_catalog = context.assets
    project_dir = asset_catalog.project_dir
    targets = []
    task_names = scoped_names(scope, "tasks")
    task_files = scoped_names(scope, "task_files")

    for task in asset_catalog.tasks:
        expected_table = _short_table_name(task.expected_table)
        if task_names is not None and expected_table not in task_names:
            continue
        if task.path is None:
            continue
        task_path = task.path
        if task_files is not None and not _task_file_matches(
            project_dir=project_dir,
            task=task,
            task_path=task_path,
            scoped_task_files=task_files,
        ):
            continue
        file_name = _display_file_path(project_dir, task_path)
        sql = task_path.read_text(encoding=TEXT_ENCODING)
        creates, drops, write_statements = _scan_task_sql(sql)
        source_tables = _scan_task_source_tables(sql)

        drop_indexes_by_table = defaultdict(list)
        drops_by_table = defaultdict(list)
        for drop in drops:
            table = _short_table_name(drop.get("table") or "")
            if table:
                drop_indexes_by_table[table.lower()].append(drop["index"])
                drops_by_table[table.lower()].append(drop)

        targets.append(
            {
                "task": task,
                "file_name": file_name,
                "sql": sql,
                "creates": creates,
                "drops": drops,
                "drops_by_table": drops_by_table,
                "drop_indexes_by_table": drop_indexes_by_table,
                "write_statements": write_statements,
                "source_tables": source_tables,
                "transient_tables": list(task.transient_tables),
                "expected_table": expected_table,
            }
        )

    reader_tasks_by_table = defaultdict(list)
    for target in targets:
        for table_name in target["source_tables"]:
            reader_tasks_by_table[
                _short_table_name(table_name).lower()
            ].append(target["file_name"])

    checks = RuleRunner(rule_selection).run(
        "task",
        "sql",
        targets,
        {
            "asset_catalog": asset_catalog,
            "governed_tables": _governed_table_names(asset_catalog),
            "reader_tasks_by_table": {
                table: sorted(set(tasks))
                for table, tasks in reader_tasks_by_table.items()
            },
        },
        dimension="code_quality",
    )
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="code_quality",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=CODE_QUALITY_RULES,
    )
