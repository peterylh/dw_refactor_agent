"""Changed asset and affected scope analysis for refactor runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dw_refactor_agent.config import (
    BUSINESS_SEMANTICS_FILE_NAMES,
    PROJECT_CONFIG,
)
from dw_refactor_agent.lineage.asset_graph import build_asset_table_graph
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    table_identity_match_key,
)

PROJECT_CONFIG_GLOBAL_DIMENSIONS = [
    "asset_completeness",
    "code_quality",
    "depth",
    "metadata_health",
    "model_design",
    "naming",
    "reuse",
]


def _normalize_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


def _task_job_name(path: str) -> str:
    stem = Path(path).stem
    if stem.endswith("_full_refresh"):
        return stem[: -len("_full_refresh")]
    return stem


def _is_asset_path(parts: list[str], asset_kind: str) -> bool:
    if len(parts) >= 5 and parts[0] == "ods" and parts[1] == asset_kind:
        return True
    return (
        len(parts) >= 3
        and parts[0] in {"mid", "ads"}
        and (parts[1] == asset_kind)
    )


def _project_dir_candidates(project_or_dir: str) -> list[str]:
    raw_value = _normalize_path(project_or_dir).rstrip("/")
    candidates = []
    project_cfg = _project_config(project_or_dir)
    if project_cfg:
        candidates.append(project_cfg["dir"])
        naming_config = project_cfg.get("naming_config")
        if naming_config:
            candidates.append(str(Path(naming_config).parent))
    if raw_value:
        candidates.append(raw_value)

    normalized = []
    for candidate in candidates:
        path = _normalize_path(candidate).rstrip("/")
        if path and path not in normalized:
            normalized.append(path)
    return normalized


def _project_config(project_or_dir: str):
    raw_value = _normalize_path(project_or_dir).rstrip("/")
    project_cfg = PROJECT_CONFIG.get(raw_value)
    if project_cfg:
        return project_cfg

    for cfg in PROJECT_CONFIG.values():
        if _normalize_path(cfg.get("dir", "")).rstrip("/") == raw_value:
            return cfg
    return None


def _project_config_files(project_or_dir: str) -> set[str]:
    files = set()
    project_cfg = _project_config(project_or_dir)
    if project_cfg and project_cfg.get("naming_config"):
        files.add(_normalize_path(project_cfg["naming_config"]))
    for project_dir in _project_dir_candidates(project_or_dir):
        files.add(f"{project_dir}/warehouse.yaml")
        files.add(f"{project_dir}/naming_config.yaml")
        for file_name in BUSINESS_SEMANTICS_FILE_NAMES.values():
            files.add(f"{project_dir}/{file_name}")
    return files


def classify_changed_assets(files: list[str], project_dir: str) -> dict:
    project_prefixes = [
        f"{project_path}/"
        for project_path in _project_dir_candidates(project_dir)
    ]
    config_candidates = _project_config_files(project_dir)
    ddl_tables = set()
    task_jobs = set()
    model_tables = set()
    config_files = set()

    for raw_file in files:
        path = _normalize_path(raw_file)
        if not path:
            continue
        if path in config_candidates:
            config_files.add(path)
            continue
        project_prefix = next(
            (prefix for prefix in project_prefixes if path.startswith(prefix)),
            None,
        )
        if project_prefix is None:
            continue
        rel_path = path[len(project_prefix) :]
        parts = rel_path.split("/")
        if path.endswith(".sql") and _is_asset_path(parts, "ddl"):
            ddl_tables.add(Path(path).stem)
        elif path.endswith(".sql") and _is_asset_path(parts, "tasks"):
            task_jobs.add(_task_job_name(path))
        elif path.endswith((".yaml", ".yml")) and (
            _is_asset_path(parts, "models")
        ):
            model_tables.add(Path(path).stem)

    return {
        "ddl_tables": sorted(ddl_tables),
        "task_jobs": sorted(task_jobs),
        "model_tables": sorted(model_tables),
        "config_files": sorted(config_files),
    }


def _downstream_map(
    project: str, lineage_data: dict
) -> tuple[dict[tuple, set[tuple]], dict[tuple, str]]:
    _upstream, downstream = build_asset_table_graph(lineage_data or {})
    canonical_downstream = {}
    display_by_key = {}
    for source, targets in downstream.items():
        source_key = _project_table_key(project, source)
        display_by_key.setdefault(source_key, source)
        canonical_targets = canonical_downstream.setdefault(source_key, set())
        for target in targets:
            target_key = _project_table_key(project, target)
            if source_key == target_key:
                continue
            display_by_key.setdefault(target_key, target)
            canonical_targets.add(target_key)
    return canonical_downstream, display_by_key


def _edge_map(
    downstream: dict[tuple, set[tuple]],
    display_by_key: dict[tuple, str],
) -> dict[tuple[tuple, tuple], tuple[str, str]]:
    return {
        (source_key, target_key): (
            display_by_key[source_key],
            display_by_key[target_key],
        )
        for source_key, targets in downstream.items()
        for target_key in targets
    }


def _bfs_downstream(
    seeds: set[tuple], downstream: dict[tuple, set[tuple]]
) -> set[tuple]:
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


def _project_table_key(project: str, table_name: str) -> tuple:
    project_cfg = PROJECT_CONFIG.get(project) or {}
    return table_identity_match_key(
        table_name,
        default_catalog=project_cfg.get("catalog") or "internal",
        default_db=project_cfg.get("db") or "",
    )


def _changed_job_output_tables(
    project: str,
    changed_jobs: set[str],
    lineage_snapshots: tuple[dict, dict],
) -> set[str]:
    explicit_snapshots = [
        snapshot
        for snapshot in lineage_snapshots
        if snapshot.get("format_version") == 2
    ]
    if not explicit_snapshots:
        return set(changed_jobs)

    changed_by_key = {
        identifier_match_key(job_name): job_name for job_name in changed_jobs
    }
    matched_jobs = set()
    output_tables = {}
    for snapshot in explicit_snapshots:
        tables_by_key = {
            _project_table_key(project, table.get("full_name")): table
            for table in snapshot.get("tables") or []
            if table.get("full_name")
        }
        for job in snapshot.get("jobs") or []:
            job_key = identifier_match_key(job.get("name"))
            if job_key not in changed_by_key:
                continue
            matched_jobs.add(job_key)
            managed_outputs = {}
            for output in job.get("outputs") or []:
                output_key = _project_table_key(project, output)
                table = tables_by_key.get(output_key)
                if table and table.get("dataset_type") == "managed":
                    managed_outputs.setdefault(
                        output_key,
                        str(table.get("full_name") or output),
                    )
            if len(managed_outputs) != 1:
                job_name = changed_by_key[job_key]
                raise ValueError(
                    f"changed Job {job_name!r} must resolve to exactly one "
                    "managed output in each lineage v2 snapshot; found "
                    f"{len(managed_outputs)}: "
                    f"{sorted(managed_outputs.values())!r}"
                )
            for output_key, output_name in managed_outputs.items():
                output_tables[output_key] = output_name

    missing_jobs = set(changed_by_key).difference(matched_jobs)
    if missing_jobs:
        missing_names = sorted(changed_by_key[key] for key in missing_jobs)
        raise ValueError(
            "changed Job must resolve to a managed output in lineage v2; "
            f"missing Job records: {missing_names!r}"
        )
    return set(output_tables.values())


def _display_values(
    project: str,
    table_keys: set[tuple],
    *display_maps: dict[tuple, str],
) -> set[str]:
    selected = {}
    for display_map in display_maps:
        for table_key in table_keys:
            if table_key in display_map:
                selected[table_key] = display_map[table_key]
    if set(selected) != table_keys:
        missing = sorted(table_keys.difference(selected))
        raise ValueError(f"missing table display names for keys: {missing!r}")
    return set(selected.values())


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
    direct_table_names = set(changed_assets["ddl_tables"])
    direct_table_names.update(changed_assets["model_tables"])

    baseline_downstream, baseline_display = _downstream_map(
        project, baseline_lineage
    )
    current_downstream, current_display = _downstream_map(
        project, current_lineage
    )
    direct_table_names.update(
        _changed_job_output_tables(
            project,
            set(changed_assets["task_jobs"]),
            (baseline_lineage, current_lineage),
        )
    )
    direct_display = {
        _project_table_key(project, table_name): table_name
        for table_name in direct_table_names
    }
    direct_keys = set(direct_display)
    direct_tables = _display_values(
        project,
        direct_keys,
        direct_display,
        baseline_display,
        current_display,
    )

    downstream_keys = _bfs_downstream(
        direct_keys, baseline_downstream
    ) | _bfs_downstream(direct_keys, current_downstream)
    downstream_tables = _display_values(
        project,
        downstream_keys,
        baseline_display,
        current_display,
    )

    anchor_keys = set()
    for table_key in direct_keys:
        anchor_keys.update(baseline_downstream.get(table_key, set()))
        anchor_keys.update(current_downstream.get(table_key, set()))
    anchor_tables = _display_values(
        project,
        anchor_keys,
        baseline_display,
        current_display,
    )

    baseline_edges = _edge_map(baseline_downstream, baseline_display)
    current_edges = _edge_map(current_downstream, current_display)
    added_edge_keys = set(current_edges).difference(baseline_edges)
    removed_edge_keys = set(baseline_edges).difference(current_edges)
    added_edges = {current_edges[key] for key in added_edge_keys}
    removed_edges = {baseline_edges[key] for key in removed_edge_keys}
    changed_edge_keys = {
        table_key
        for edge_key in added_edge_keys | removed_edge_keys
        for table_key in edge_key
    }
    changed_edge_tables = _display_values(
        project,
        changed_edge_keys,
        baseline_display,
        current_display,
    )

    global_dimensions = []
    config_files = set(changed_assets["config_files"])
    if any(path.endswith("warehouse.yaml") for path in config_files):
        global_dimensions.extend(PROJECT_CONFIG_GLOBAL_DIMENSIONS)
    if any(path.endswith("naming_config.yaml") for path in config_files):
        global_dimensions.append("naming")
    business_semantics_names = set(BUSINESS_SEMANTICS_FILE_NAMES.values())
    if any(
        Path(path).name in business_semantics_names for path in config_files
    ):
        global_dimensions.extend(["metadata_health", "naming"])
    global_dimensions = sorted(set(global_dimensions))

    assessment_keys = (
        direct_keys | downstream_keys | anchor_keys | changed_edge_keys
    )
    assessment_tables = _display_values(
        project,
        assessment_keys,
        direct_display,
        baseline_display,
        current_display,
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
    config_candidates = _project_config_files(project_dir)
    return sorted(
        file
        for file in files
        if file in config_candidates or file.startswith(relevant_prefix)
    )
