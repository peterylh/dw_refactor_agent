"""Scoped assessment planning helpers.

This module intentionally keeps the scope logic imperative and local.  The
planner translates refactor change analysis into per-dimension target sets;
scorers consume those target sets without inspecting changed files.
"""

from __future__ import annotations

from pathlib import Path

import dw_refactor_agent.config as config

DEFAULT_DIMENSIONS = [
    "reuse",
    "depth",
    "model_design",
    "naming",
    "asset_completeness",
    "metadata_health",
    "code_quality",
]

FULL_CHANGE_TYPES_BY_DIMENSION = {
    "reuse": {"warehouse_config"},
    "depth": {"warehouse_config"},
    "model_design": {"warehouse_config"},
    "naming": {"business_semantics", "naming_config", "warehouse_config"},
    "asset_completeness": {"warehouse_config"},
    "metadata_health": {
        "business_semantics",
        "naming_config",
        "warehouse_config",
    },
    "code_quality": {"warehouse_config"},
}

def _sorted(values) -> list[str]:
    return sorted(str(value) for value in values if str(value or "").strip())


def _short_task_name(task: dict) -> str:
    name = str(task.get("expected_table") or "").strip()
    if name:
        return name
    file_name = Path(str(task.get("file") or "")).stem
    if file_name.endswith("_full_refresh"):
        return file_name[: -len("_full_refresh")]
    return file_name


def _project_business_semantics_paths(project: str) -> set[str]:
    project_cfg = config.PROJECT_CONFIG.get(project) or {}
    project_dir = str(project_cfg.get("dir") or f"warehouses/{project}")
    project_dir = project_dir.rstrip("/")
    return {
        f"{project_dir}/{file_name}"
        for file_name in config.BUSINESS_SEMANTICS_FILE_NAMES.values()
    }


def changed_types_for_analysis(
    project: str, change_analysis: dict
) -> set[str]:
    """Return normalized change categories for a refactor analysis."""
    changed_assets = change_analysis.get("changed_assets") or {}
    changed_types = set()
    if changed_assets.get("ddl_tables"):
        changed_types.add("ddl")
    if changed_assets.get("task_jobs"):
        changed_types.add("task")
    if changed_assets.get("model_tables"):
        changed_types.add("model")

    project_business_semantics = _project_business_semantics_paths(project)
    for file_name in changed_assets.get("config_files") or []:
        normalized = str(file_name or "").replace("\\", "/")
        if normalized == "naming_config.yaml":
            continue
        if normalized.endswith("/naming_config.yaml"):
            changed_types.add("naming_config")
        elif normalized in project_business_semantics:
            changed_types.add("business_semantics")
        elif normalized.endswith("/warehouse.yaml"):
            changed_types.add("warehouse_config")
        elif normalized:
            changed_types.add("config")
    return changed_types


def dimension_scope(scope_plan: dict | None, dimension: str) -> dict | None:
    if not scope_plan:
        return None
    return (scope_plan.get("dimensions") or {}).get(dimension)


def scoped_names(dimension_scope: dict | None, key: str) -> set[str] | None:
    """Return scoped names for key, or None when the dimension is full."""
    if not dimension_scope or dimension_scope.get("mode") != "scoped":
        return None
    return set(dimension_scope.get(key) or [])


def _full_dimension(dimension: str, changed_types: set[str]) -> dict:
    triggers = sorted(
        changed_types & FULL_CHANGE_TYPES_BY_DIMENSION.get(dimension, set())
    )
    return {
        "mode": "full",
        "reason": [f"changed:{item}" for item in triggers],
        "score_semantics": "global",
    }


def _scoped_dimension(
    *,
    scope_name: str,
    tables: set[str] | list[str] | None = None,
    tasks: set[str] | list[str] | None = None,
    edges: set[tuple[str, str]] | list[dict] | None = None,
    reason: str = "changed_scope",
) -> dict:
    result = {
        "mode": "scoped",
        "scope": scope_name,
        "reason": [reason],
        "score_semantics": "scope_local",
    }
    if tables is not None:
        result["tables"] = _sorted(tables)
    if tasks is not None:
        result["tasks"] = _sorted(tasks)
    if edges is not None:
        result["edges"] = _edge_records(edges)
    return result


def _edge_records(edges) -> list[dict]:
    records = []
    for edge in edges or []:
        if isinstance(edge, dict):
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
        else:
            source, target = edge
            source = str(source or "").strip()
            target = str(target or "").strip()
        if source and target:
            records.append({"source": source, "target": target})
    return sorted(records, key=lambda item: (item["source"], item["target"]))


def _base_tables(base_scope: dict) -> set[str]:
    return set(base_scope.get("assessment_tables") or [])


def _base_tasks(base_scope: dict) -> set[str]:
    return set(base_scope.get("assessment_tasks") or [])


def _current_table_names(context) -> set[str]:
    return {
        str(table.get("name") or "").strip()
        for table in context.tables
        if str(table.get("name") or "").strip()
    }


def _current_task_names(context) -> set[str]:
    tasks = set()
    asset_catalog = context.assets or {}
    for task in asset_catalog.get("tasks") or []:
        task_name = _short_task_name(task)
        if task_name:
            tasks.add(task_name)
    return tasks


def _filter_scope_names(values, allowed_names: set[str]) -> list[str]:
    if not allowed_names:
        return _sorted(values)
    return _sorted(
        value for value in values or [] if str(value or "") in allowed_names
    )


def _current_base_scope(base_scope: dict, context) -> dict:
    table_names = _current_table_names(context)
    task_names = _current_task_names(context) | table_names
    current_scope = dict(base_scope)

    for key in (
        "direct_tables",
        "downstream_tables",
        "anchor_tables",
        "assessment_tables",
    ):
        current_scope[key] = _filter_scope_names(
            base_scope.get(key) or [],
            table_names,
        )
    current_scope["assessment_tasks"] = _filter_scope_names(
        base_scope.get("assessment_tasks") or [],
        task_names,
    )
    current_scope["global_dimensions"] = _sorted(
        base_scope.get("global_dimensions") or []
    )
    return current_scope


def _impacted_ads_tables(base_tables: set[str], context) -> set[str]:
    table_layers = context.table_layers
    return {
        table["name"]
        for table in context.tables
        if table_layers.get(table.get("name")) == "ADS"
        and table.get("name") in base_tables
    }


def _model_design_edges(
    base_tables: set[str],
    change_analysis: dict,
    context,
) -> set[tuple[str, str]]:
    edges = set()
    lineage_diff = change_analysis.get("lineage_diff") or {}
    for edge in lineage_diff.get("added_edges") or []:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source and target:
            edges.add((source, target))

    for source, target in context.table_edges:
        if source in base_tables or target in base_tables:
            edges.add((source, target))
    return edges


def _asset_closure(
    base_tables: set[str], base_tasks: set[str], context
) -> dict:
    tables = set(base_tables)
    tasks = set(base_tasks)
    asset_catalog = context.assets or {}
    assets = asset_catalog.get("tables") or {}
    all_tasks = list(asset_catalog.get("tasks") or [])

    for table_name in list(tables):
        for task in (assets.get(table_name) or {}).get("tasks") or []:
            task_name = _short_task_name(task)
            if task_name:
                tasks.add(task_name)

    changed = True
    while changed:
        changed = False
        for task in all_tasks:
            task_name = _short_task_name(task)
            outputs = set(task.get("output_tables") or [])
            if task_name in tasks:
                before = len(tables)
                tables.update(outputs)
                changed = changed or len(tables) != before
            if outputs & tables:
                before = len(tasks)
                if task_name:
                    tasks.add(task_name)
                changed = changed or len(tasks) != before

    return {"tables": tables, "tasks": tasks}


def _dimension_plan(
    dimension: str,
    changed_types: set[str],
    scoped_factory,
) -> dict:
    if changed_types & FULL_CHANGE_TYPES_BY_DIMENSION.get(dimension, set()):
        return _full_dimension(dimension, changed_types)
    return scoped_factory()


def build_scoped_assessment_plan(
    project: str,
    change_analysis: dict,
    context,
) -> dict:
    """Build per-dimension scoped assessment targets."""
    base_scope = _current_base_scope(
        change_analysis.get("affected_scope") or {},
        context,
    )
    base_tables = _base_tables(base_scope)
    base_tasks = _base_tasks(base_scope)
    changed_types = changed_types_for_analysis(project, change_analysis)
    asset_closure = _asset_closure(base_tables, base_tasks, context)

    dimensions = {
        "reuse": _dimension_plan(
            "reuse",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="tables",
                tables=base_tables,
            ),
        ),
        "depth": _dimension_plan(
            "depth",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="impacted_ads",
                tables=_impacted_ads_tables(base_tables, context),
            ),
        ),
        "model_design": _dimension_plan(
            "model_design",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="dependency_closure",
                tables=base_tables,
                edges=_model_design_edges(
                    base_tables,
                    change_analysis,
                    context,
                ),
            ),
        ),
        "naming": _dimension_plan(
            "naming",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="tables_and_tasks",
                tables=base_tables,
                tasks=base_tasks,
            ),
        ),
        "asset_completeness": _dimension_plan(
            "asset_completeness",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="asset_closure",
                tables=asset_closure["tables"],
                tasks=asset_closure["tasks"],
            ),
        ),
        "metadata_health": _dimension_plan(
            "metadata_health",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="tables",
                tables=base_tables,
            ),
        ),
        "code_quality": _dimension_plan(
            "code_quality",
            changed_types,
            lambda: _scoped_dimension(
                scope_name="tasks",
                tasks=base_tasks,
            ),
        ),
    }

    return {
        "mode": "scoped",
        "score_semantics": "scope_local",
        "changed_types": _sorted(changed_types),
        "base_scope": dict(base_scope),
        "dimensions": {
            dimension: dimensions[dimension]
            for dimension in DEFAULT_DIMENSIONS
        },
    }
