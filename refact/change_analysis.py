"""Changed asset and affected scope analysis for refactor runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

from lineage.asset_graph import build_asset_table_graph


def _normalize_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


def _task_job_name(path: str) -> str:
    stem = Path(path).stem
    if stem.endswith("_full_refresh"):
        return stem[: -len("_full_refresh")]
    return stem


def classify_changed_assets(files: list[str], project_dir: str) -> dict:
    project_prefix = _normalize_path(project_dir).rstrip("/") + "/"
    ddl_tables = set()
    task_jobs = set()
    model_tables = set()
    config_files = set()

    for raw_file in files:
        path = _normalize_path(raw_file)
        if not path:
            continue
        if path == "naming_config.yaml":
            config_files.add(path)
            continue
        if path == f"{project_prefix}business_semantics.yaml":
            config_files.add(path)
            continue
        if not path.startswith(project_prefix):
            continue
        rel_path = path[len(project_prefix) :]
        parts = rel_path.split("/")
        if path.endswith(".sql") and (
            (len(parts) >= 2 and parts[0] == "ddl")
            or (len(parts) >= 5 and parts[0] == "ods" and parts[1] == "ddl")
        ):
            ddl_tables.add(Path(path).stem)
        elif len(parts) >= 2 and parts[0] == "tasks" and path.endswith(".sql"):
            task_jobs.add(_task_job_name(path))
        elif path.endswith((".yaml", ".yml")) and (
            (len(parts) >= 2 and parts[0] == "models")
            or (len(parts) >= 5 and parts[0] == "ods" and parts[1] == "models")
        ):
            model_tables.add(Path(path).stem)

    return {
        "ddl_tables": sorted(ddl_tables),
        "task_jobs": sorted(task_jobs),
        "model_tables": sorted(model_tables),
        "config_files": sorted(config_files),
    }


def _edge_set(lineage_data: dict) -> set[tuple[str, str]]:
    _upstream, downstream = build_asset_table_graph(lineage_data or {})
    edges = set()
    for source, targets in downstream.items():
        for target in targets:
            if source and target and source != target:
                edges.add((source, target))
    return edges


def _downstream_map(lineage_data: dict) -> dict[str, set[str]]:
    _upstream, downstream = build_asset_table_graph(lineage_data or {})
    return {key: set(value) for key, value in downstream.items()}


def _bfs_downstream(
    seeds: set[str], downstream: dict[str, set[str]]
) -> set[str]:
    visited = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop(0)
        for child in downstream.get(current, set()):
            if child in visited:
                continue
            visited.add(child)
            queue.append(child)
    return visited - seeds


def _edge_records(edges: set[tuple[str, str]]) -> list[dict]:
    return [
        {"source": source, "target": target}
        for source, target in sorted(edges)
    ]


def build_change_analysis(
    project: str,
    baseline_lineage: dict,
    current_lineage: dict,
    changed_files: list[str],
) -> dict:
    changed_assets = classify_changed_assets(changed_files, project)
    direct_tables = set(changed_assets["ddl_tables"])
    direct_tables.update(changed_assets["model_tables"])
    direct_tables.update(changed_assets["task_jobs"])

    baseline_downstream = _downstream_map(baseline_lineage)
    current_downstream = _downstream_map(current_lineage)

    downstream_tables = set()
    downstream_tables.update(
        _bfs_downstream(direct_tables, baseline_downstream)
    )
    downstream_tables.update(
        _bfs_downstream(direct_tables, current_downstream)
    )

    anchor_tables = set()
    for table in direct_tables:
        anchor_tables.update(baseline_downstream.get(table, set()))
        anchor_tables.update(current_downstream.get(table, set()))

    baseline_edges = _edge_set(baseline_lineage)
    current_edges = _edge_set(current_lineage)
    added_edges = current_edges - baseline_edges
    removed_edges = baseline_edges - current_edges
    changed_edge_tables = {
        table for edge in added_edges | removed_edges for table in edge
    }

    global_dimensions = []
    config_files = set(changed_assets["config_files"])
    if "naming_config.yaml" in config_files:
        global_dimensions.append("naming")
    if f"{project}/business_semantics.yaml" in config_files:
        global_dimensions.extend(["metadata_health", "naming"])
    global_dimensions = sorted(set(global_dimensions))

    assessment_tables = (
        direct_tables | downstream_tables | anchor_tables | changed_edge_tables
    )

    return {
        "project": project,
        "changed_files": sorted(
            _normalize_path(path) for path in changed_files
        ),
        "changed_assets": changed_assets,
        "affected_scope": {
            "direct_tables": sorted(direct_tables),
            "downstream_tables": sorted(downstream_tables),
            "anchor_tables": sorted(anchor_tables),
            "assessment_tables": sorted(assessment_tables),
            "assessment_tasks": sorted(
                set(changed_assets["task_jobs"]) | assessment_tables
            ),
            "global_dimensions": global_dimensions,
        },
        "lineage_diff": {
            "added_edges": _edge_records(added_edges),
            "removed_edges": _edge_records(removed_edges),
            "changed_tables": sorted(changed_edge_tables),
        },
    }


def changed_files_since_head(
    repo: Path, head: str, project_dir: str
) -> list[str]:
    repo = Path(repo)
    diff = subprocess.run(
        ["git", "diff", "--name-only", head],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    files = set(
        line.strip() for line in diff.stdout.splitlines() if line.strip()
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    files.update(
        line.strip() for line in untracked.stdout.splitlines() if line.strip()
    )
    relevant_prefix = _normalize_path(project_dir).rstrip("/") + "/"
    return sorted(
        file
        for file in files
        if file == "naming_config.yaml" or file.startswith(relevant_prefix)
    )
