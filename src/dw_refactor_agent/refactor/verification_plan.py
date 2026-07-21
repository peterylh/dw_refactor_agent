"""Build validation plans for refactor run shadow execution."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta
from pathlib import Path

import dw_refactor_agent.config as config
from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.ddl_deriver.ddl_deriver import (
    changes_to_json,
    derive_ddl_changes,
    load_git_ddl_texts,
    load_git_tables,
    load_tables_from_dir,
)
from dw_refactor_agent.ddl_deriver.schema_ids import (
    SchemaIdentityError,
    require_valid_project,
    validate_table_defs,
)
from dw_refactor_agent.execution.model_config import (
    ExecutionConfigError,
    execution_config_for_model,
    normalize_execution_mode,
    require_runnable_execution,
    slice_config_from_mapping,
)
from dw_refactor_agent.execution.schedule_graph import ScheduleGraph
from dw_refactor_agent.lineage.asset_graph import build_asset_table_graph
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.job_dag import job_dag_from_lineage
from dw_refactor_agent.lineage.schedule_inference import (
    validate_schedule_against_lineage,
    writers_by_table,
)
from dw_refactor_agent.refactor.qa_pool import configured_qa_pool
from dw_refactor_agent.refactor.verification_checks import (
    FULL_TABLE_SCOPE,
    TIME_SLICE_SCOPE,
)
from dw_refactor_agent.sql.doris import extract_doris_partition_column

SUPPORTED_TIME_PERIODS = {"D", "W", "M", "H"}
WEEKDAY_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


def strip_insert_data(sql_text: str) -> str:
    lines = []
    for line in str(sql_text or "").splitlines():
        if line.strip().upper().startswith("INSERT"):
            break
        lines.append(line)
    return "\n".join(lines)


def parse_partition_col_from_ddl(ddl_text: str) -> str:
    if not ddl_text:
        return ""
    return extract_doris_partition_column(ddl_text)


def get_partition_col(
    table_name: str, baseline_ddl: dict | None = None
) -> str:
    if not baseline_ddl:
        return ""
    ddl_text = baseline_ddl.get(table_name)
    if not ddl_text:
        return ""
    return parse_partition_col_from_ddl(ddl_text)


def _current_ddl_by_table(project: str, table_names: set[str]) -> dict:
    ddl = {}
    for path in config.iter_project_asset_files(project, "ddl", "*.sql"):
        table_name = path.stem
        if table_name in table_names:
            ddl[table_name] = strip_insert_data(
                path.read_text(encoding=TEXT_ENCODING)
            )
    return dict(sorted(ddl.items()))


def _project_repo_root(repo_root: Path | None = None) -> Path:
    return Path(repo_root) if repo_root else config.PROJECT_ROOT


def _project_ddl_rels(project: str) -> list[str]:
    project_dir = config.PROJECT_CONFIG[project]["dir"]
    return [
        f"{project_dir}/mid/ddl",
        f"{project_dir}/ads/ddl",
    ]


def load_baseline_ddl(
    project: str,
    base_ref: str,
    *,
    repo_root: Path | None = None,
) -> dict:
    """Load project DDL text from a git base ref."""
    repo = _project_repo_root(repo_root)
    baseline_ddl = {}
    for ddl_rel in _project_ddl_rels(project):
        baseline_ddl.update(
            {
                table_name: strip_insert_data(content)
                for table_name, content in load_git_ddl_texts(
                    repo, ddl_rel, base_ref
                ).items()
            }
        )
    return dict(sorted(baseline_ddl.items()))


def derive_project_ddl_changes(
    project: str,
    base_ref: str,
    *,
    repo_root: Path | None = None,
) -> list[dict]:
    """Derive DDL changes between a git base ref and the working tree."""
    require_valid_project(project)
    repo = _project_repo_root(repo_root)
    old_tables = {}
    new_tables = {}
    for ddl_rel in _project_ddl_rels(project):
        old_tables.update(load_git_tables(repo, ddl_rel, base_ref))
        new_tables.update(load_tables_from_dir(repo / ddl_rel))
    baseline_issues = validate_table_defs(
        old_tables, f"git-baseline-{base_ref}"
    )
    if baseline_issues:
        raise SchemaIdentityError(baseline_issues)
    changes = derive_ddl_changes(old_tables, new_tables, legacy_identity=False)
    return changes_to_json(changes)["changes"]


def _task_path(project: str, job_name: str) -> Path | None:
    return config.task_path_for_job(project, job_name)


def _relative(path: Path) -> str:
    try:
        return path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _job_entry(
    project: str,
    job_name: str,
    *,
    target: str | None = None,
) -> dict | None:
    task_path = _task_path(project, job_name)
    if not task_path:
        return None
    target_table = target or job_name
    return {
        "job": job_name,
        "file": _relative(task_path),
        "layer": config.determine_operational_layer(target_table, project),
        "target": target_table,
    }


def _short_name(name: str) -> str:
    return str(name or "").split(".")[-1]


def _table_key(name: str) -> str:
    return _short_name(name).casefold()


def _dataset_key(project: str, name: str) -> tuple:
    cfg = config.PROJECT_CONFIG[project]
    return table_identity_match_key(
        name,
        default_catalog=cfg.get("catalog") or "internal",
        default_db=cfg.get("db") or "",
    )


def _phase2_create_tables(ddl_changes: list[dict]) -> set[str]:
    phase2_creates = set()
    for change in ddl_changes:
        change_type = change.get("change_type")
        if change_type == "CREATE":
            phase2_creates.add(_short_name(change.get("table_name")))
        elif change_type == "RENAME":
            phase2_creates.add(_short_name(change.get("new_name")))
    return phase2_creates


def _job_target(
    project: str,
    job: dict,
    target_hints: set[str],
    dataset_type_by_key: dict[tuple, str],
) -> str:
    job_name = str(job.get("name") or "")
    outputs = [str(output) for output in job.get("outputs") or [] if output]
    managed_outputs = [
        output
        for output in outputs
        if dataset_type_by_key.get(_dataset_key(project, output)) == "managed"
    ]
    if len(managed_outputs) > 1:
        raise ValueError(
            f"Job {job_name!r} has multiple managed outputs; "
            f"execution target is ambiguous: {sorted(managed_outputs)!r}"
        )
    if len(target_hints) > 1:
        raise ValueError(
            f"Job {job_name!r} maps to multiple affected outputs: "
            f"{sorted(target_hints)!r}"
        )
    if target_hints:
        return _short_name(next(iter(target_hints)))
    if len(managed_outputs) == 1:
        return _short_name(managed_outputs[0])
    if len(outputs) == 1:
        return _short_name(outputs[0])
    return job_name


def _explicit_job_entries(
    project: str,
    execution_tasks: set[str],
    lineage_data: dict,
) -> dict[str, dict]:
    jobs = list(lineage_data.get("jobs") or [])
    job_by_key = {
        identifier_match_key(job.get("name")): job
        for job in jobs
        if job.get("name")
    }
    jobs_by_output_key: dict[tuple, list[dict]] = defaultdict(list)
    for job in jobs:
        for output in job.get("outputs") or []:
            jobs_by_output_key[_dataset_key(project, output)].append(job)
    dataset_type_by_key = {
        _dataset_key(project, table.get("full_name")): str(
            table.get("dataset_type") or ""
        )
        for table in lineage_data.get("tables") or []
        if table.get("full_name")
    }

    selected: dict[str, dict] = {}
    target_hints: dict[str, set[str]] = defaultdict(set)
    for task_or_table in execution_tasks:
        job = job_by_key.get(identifier_match_key(task_or_table))
        if job is not None:
            selected[identifier_match_key(job["name"])] = job
            continue
        producers = jobs_by_output_key.get(
            _dataset_key(project, task_or_table), []
        )
        for producer in producers:
            producer_key = identifier_match_key(producer["name"])
            selected[producer_key] = producer
            matched_output = next(
                output
                for output in producer.get("outputs") or []
                if _dataset_key(project, output)
                == _dataset_key(project, task_or_table)
            )
            target_hints[producer_key].add(str(matched_output))

    entries = {}
    for job_key, job in selected.items():
        job_name = str(job["name"])
        target = _job_target(
            project,
            job,
            target_hints.get(job_key, set()),
            dataset_type_by_key,
        )
        entry = _job_entry(project, job_name, target=target)
        if entry:
            entries[job_name] = entry
    return entries


def _execution_job_entries(
    project: str,
    execution_tasks: set[str],
    lineage_data: dict | None,
) -> dict[str, dict]:
    if lineage_data and lineage_data.get("format_version") == 2:
        return _explicit_job_entries(project, execution_tasks, lineage_data)
    entries = {}
    for job_name in execution_tasks:
        entry = _job_entry(project, job_name)
        if entry:
            entries[job_name] = entry
    return entries


def _baseline_needed_tables(
    ddl_changes: list[dict],
    jobs_to_run: list[dict],
    anchors: set[str],
) -> set[str]:
    phase2_creates = _phase2_create_tables(ddl_changes)
    needed = set(anchors)
    for change in ddl_changes:
        change_type = change.get("change_type")
        if change_type == "ALTER":
            needed.add(_short_name(change.get("table_name")))
        elif change_type == "RENAME":
            needed.add(_short_name(change.get("old_name")))
    for job in jobs_to_run:
        target = job.get("target")
        if target and target not in phase2_creates:
            needed.add(target)
    return needed


def build_verification_plan(
    project: str,
    change_analysis: dict,
    *,
    base_ref: str | None = None,
    repo_root: Path | None = None,
    lineage_data: dict | None = None,
    partition: str | None = None,
    semantic_resolution=None,
    schedule_graph: ScheduleGraph | None = None,
    baseline_schedule_graph: ScheduleGraph | None = None,
    baseline_lineage_data: dict | None = None,
    strict_schedule: bool = False,
) -> dict:
    cfg = config.PROJECT_CONFIG[project]
    metadata_errors = []
    if not isinstance(change_analysis.get("changed_assets"), dict):
        raise ValueError("change_analysis.changed_assets is required")
    raw_scope = change_analysis.get("affected_scope")
    if not isinstance(raw_scope, dict):
        raise ValueError("change_analysis.affected_scope is required")
    scope = _normalized_scope(raw_scope)
    modified_jobs = _modified_jobs(change_analysis)
    changed_ddl_tables = _changed_ddl_tables(change_analysis)
    if semantic_resolution is None:
        execution_tasks = set(scope["direct_tables"]) | set(
            scope["downstream_tables"]
        )
        anchors, self_anchor_tables = _verification_anchor_tables(
            scope,
            modified_jobs,
            changed_ddl_tables,
        )
    else:
        execution_tasks = set(semantic_resolution.selected_tables)
        boundaries = semantic_resolution.boundaries
        anchors = sorted(
            set(boundaries.get("authority") or [])
            | set(boundaries.get("observational") or [])
        )
        self_anchor_tables = []
    scope["anchor_tables"] = anchors
    changes = _plan_changes(change_analysis, modified_jobs)

    if schedule_graph is None:
        execution_config = cfg.get("execution") or {}
        if execution_config.get("schedule"):
            schedule_graph = ScheduleGraph.load_for_project(
                project, root=repo_root
            )
        elif strict_schedule:
            raise ValueError(
                f"[{project}] execution.schedule is required for refactor "
                "planning"
            )

    execution_tasks.update(modified_jobs)
    execution_tasks.update(anchors)
    job_entries = _execution_job_entries(
        project,
        execution_tasks,
        lineage_data,
    )
    schedule_changed_edges = _changed_schedule_edges(
        baseline_schedule_graph, schedule_graph
    )
    if schedule_graph is not None:
        scheduled_initial_jobs = {
            resolved
            for job_name in job_entries
            for resolved in [schedule_graph.resolve_job(job_name)]
            if resolved is not None
        }
        selected_jobs = _selected_schedule_jobs(
            project,
            schedule_graph,
            lineage_data or {},
            initial_jobs=scheduled_initial_jobs,
            changed_jobs=modified_jobs,
            changed_tables=changed_ddl_tables,
            final_tables=set(anchors),
            changed_schedule_edges=schedule_changed_edges,
        )
        job_entries = _execution_job_entries(
            project,
            selected_jobs,
            lineage_data,
        )
        missing_entries = sorted(
            selected_jobs - set(job_entries), key=identifier_match_key
        )
        if missing_entries:
            raise ValueError(
                "selected schedule Jobs cannot be resolved to runnable task "
                f"SQL: {missing_entries!r}"
            )
        sorted_jobs = schedule_graph.topological_sort(selected_jobs)
        execution_graph = {
            "format_version": 1,
            "project": project,
            "jobs": sorted_jobs,
            "dependencies": schedule_graph.selected_dependencies(
                selected_jobs
            ),
        }
    else:
        sorted_jobs = _sort_jobs_for_execution(
            project,
            set(job_entries),
            lineage_data=lineage_data,
        )
        execution_graph = {
            "format_version": 1,
            "project": project,
            "jobs": sorted_jobs,
            "dependencies": _job_dependencies_for_plan(
                sorted_jobs,
                lineage_data=lineage_data,
            ),
        }
    jobs_to_run = [job_entries[job_name] for job_name in sorted_jobs]
    _validate_runnable_job_models(project, jobs_to_run, metadata_errors)

    schedule_diagnostics = []
    if schedule_graph is not None and lineage_data:
        schedule_diagnostics = validate_schedule_against_lineage(
            schedule_graph,
            lineage_data,
            baseline_lineage=baseline_lineage_data,
        )
        _validate_selected_schedule_diagnostics(
            schedule_diagnostics, set(sorted_jobs)
        )

    if base_ref:
        all_baseline_ddl = load_baseline_ddl(
            project,
            base_ref,
            repo_root=repo_root,
        )
        ddl_changes = derive_project_ddl_changes(
            project,
            base_ref,
            repo_root=repo_root,
        )
    else:
        all_baseline_ddl = None
        ddl_changes = []

    needed_baseline = _baseline_needed_tables(
        ddl_changes,
        jobs_to_run,
        set(anchors),
    )
    if all_baseline_ddl is not None:
        baseline_ddl = {
            table: strip_insert_data(ddl)
            for table, ddl in all_baseline_ddl.items()
            if table in needed_baseline
        }
    else:
        baseline_ddl = _current_ddl_by_table(project, needed_baseline)

    compare_scopes, anchor_windows, verification_warnings = (
        _build_compare_scopes(project, anchors, partition, metadata_errors)
    )
    if semantic_resolution is not None:
        verification_warnings.extend(semantic_resolution.warnings)
        _validate_semantic_anchor_mappings(
            anchors,
            semantic_resolution.target_semantics,
            metadata_errors,
        )
    verification_warnings.extend(
        _schedule_warnings(schedule_diagnostics, schedule_changed_edges)
    )
    if not partition:
        partition_required_jobs = _partition_required_jobs(
            project,
            jobs_to_run,
            metadata_errors,
        )
        if partition_required_jobs:
            job_list = ", ".join(partition_required_jobs)
            raise ValueError(
                "refactor analyze requires --partition for incremental jobs "
                f"with execution slices: {job_list}. Pass an explicit "
                "partition value so shadow-run can inject deterministic "
                "execution parameters."
            )
    _apply_execution_values(
        project,
        jobs_to_run,
        anchor_windows,
        metadata_errors,
        lineage_data,
    )

    checks = _verification_checks(
        project,
        anchors,
        semantic_resolution,
        compare_scopes,
    )

    verification = _verification_metadata(
        [] if metadata_errors else checks,
        scope,
        jobs_to_run,
        ddl_changes,
        _ads_schema_change_tables(project, ddl_changes),
        anchors,
        self_anchor_tables,
        verification_warnings,
        metadata_errors,
        target_semantics=(
            semantic_resolution.target_semantics
            if semantic_resolution is not None
            else None
        ),
        semantic_boundaries=(
            semantic_resolution.boundaries
            if semantic_resolution is not None
            else None
        ),
    )

    if semantic_resolution is not None:
        _validate_semantic_check_invariants(verification)

    verification["schedule_validation"] = schedule_diagnostics
    if any(
        diagnostic.get("code") == "NEW_LINEAGE_DEPENDENCY_NOT_SCHEDULED"
        and identifier_match_key(diagnostic.get("downstream_job"))
        in {identifier_match_key(job) for job in sorted_jobs}
        for diagnostic in schedule_diagnostics
    ):
        verification["result_cap"] = "inconclusive"
        verification["result_cap_reason"] = (
            "new lineage dependency is not ordered by the trusted schedule"
        )

    return {
        "project": project,
        "project_db": cfg["db"],
        "qa_db": cfg["qa_db"],
        "qa_database_pool": list(configured_qa_pool(project, cfg)),
        "changes": changes,
        "baseline_ddl": dict(sorted(baseline_ddl.items())),
        "ddl_changes": ddl_changes,
        "jobs_to_run": jobs_to_run,
        "execution_graph": execution_graph,
        "verification": verification,
    }


def _changed_schedule_edges(
    baseline: ScheduleGraph | None,
    current: ScheduleGraph | None,
) -> set[tuple[str, str]]:
    if baseline is None or current is None:
        return set()
    baseline_edges = {
        (identifier_match_key(upstream), identifier_match_key(downstream))
        for upstream, downstream in baseline.edges
    }
    current_by_key = {
        (identifier_match_key(upstream), identifier_match_key(downstream)): (
            upstream,
            downstream,
        )
        for upstream, downstream in current.edges
    }
    baseline_display = {
        (identifier_match_key(upstream), identifier_match_key(downstream)): (
            upstream,
            downstream,
        )
        for upstream, downstream in baseline.edges
    }
    changed_keys = baseline_edges.symmetric_difference(set(current_by_key))
    return {
        current_by_key.get(key) or baseline_display[key]
        for key in changed_keys
    }


def _lineage_writer_jobs_for_tables(
    project: str,
    lineage_data: dict,
    tables: set[str],
    schedule: ScheduleGraph,
) -> set[str]:
    writers = writers_by_table(lineage_data)
    selected = set()
    for table in tables:
        for writer in writers.get(_dataset_key(project, table), []):
            scheduled_writer = schedule.resolve_job(writer)
            if scheduled_writer is not None:
                selected.add(scheduled_writer)
    return selected


def _selected_schedule_jobs(
    project: str,
    schedule: ScheduleGraph,
    lineage_data: dict,
    *,
    initial_jobs: set[str],
    changed_jobs: set[str],
    changed_tables: set[str],
    final_tables: set[str],
    changed_schedule_edges: set[tuple[str, str]],
) -> set[str]:
    jobs_by_key = {
        identifier_match_key(job.get("name")): job
        for job in lineage_data.get("jobs") or []
    }
    no_output_changed_jobs = sorted(
        job
        for job in changed_jobs
        if not (
            jobs_by_key.get(identifier_match_key(job), {}).get("outputs") or []
        )
    )
    if no_output_changed_jobs:
        raise ValueError(
            "changed Jobs must resolve at least one persistent output for "
            f"shadow verification: {no_output_changed_jobs!r}"
        )
    changed_table_writers = _lineage_writer_jobs_for_tables(
        project, lineage_data, changed_tables, schedule
    )
    final_writers = _lineage_writer_jobs_for_tables(
        project, lineage_data, final_tables, schedule
    )
    direct_jobs = set(changed_jobs) | changed_table_writers
    direct_jobs.update(job for edge in changed_schedule_edges for job in edge)
    selected = set(initial_jobs) | direct_jobs | final_writers
    missing = sorted(
        job for job in selected if schedule.resolve_job(job) is None
    )
    if missing:
        raise ValueError(
            f"changed or selected Jobs are absent from schedule DAG: {missing!r}"
        )
    resolved = {schedule.resolve_job(job) for job in selected}
    direct_resolved = {
        schedule.resolve_job(job) for job in direct_jobs if job in selected
    }
    boundary_resolved = {
        schedule.resolve_job(job) for job in final_writers if job in selected
    }
    downstream = schedule.bfs_downstream(direct_resolved)
    boundary_ancestors = schedule.bfs_upstream(boundary_resolved)
    resolved.update(downstream.intersection(boundary_ancestors))
    return {job for job in resolved if job is not None}


def _validate_selected_schedule_diagnostics(
    diagnostics: list[dict], selected_jobs: set[str]
) -> None:
    selected_keys = {identifier_match_key(job) for job in selected_jobs}
    blocking = []
    for diagnostic in diagnostics:
        if diagnostic.get("severity") != "ERROR":
            continue
        consumers = diagnostic.get("consumer_jobs") or [
            diagnostic.get("consumer_job")
        ]
        if not any(
            identifier_match_key(consumer) in selected_keys
            for consumer in consumers
            if consumer
        ):
            continue
        blocking.append(diagnostic)
    if blocking:
        raise ValueError(
            "selected execution graph has unsafe process/temporary lineage: "
            f"{blocking!r}"
        )


def _schedule_warnings(
    diagnostics: list[dict],
    changed_edges: set[tuple[str, str]],
) -> list[dict]:
    warnings = [
        {
            "type": diagnostic.get("code", "schedule_validation").lower(),
            "message": diagnostic.get(
                "message", "schedule validation warning"
            ),
            "diagnostic": diagnostic,
        }
        for diagnostic in diagnostics
        if diagnostic.get("severity") == "WARNING"
    ]
    if changed_edges:
        warnings.append(
            {
                "type": "schedule_dag_changed",
                "message": "trusted schedule DAG changed since refactor start",
                "edges": [
                    {
                        "upstream_job": upstream,
                        "downstream_job": downstream,
                    }
                    for upstream, downstream in sorted(changed_edges)
                ],
            }
        )
    return warnings


def _validate_semantic_anchor_mappings(
    anchors: list[str],
    target_semantics: dict,
    metadata_errors: list[dict],
) -> None:
    for table in anchors:
        semantics = target_semantics.get(table)
        if semantics is None:
            _add_validation_error(
                metadata_errors,
                table,
                "target_semantics",
                "verification anchor has no target semantics",
            )
            continue
        blocker = semantics.get("compare_blocker")
        if blocker:
            _add_validation_error(
                metadata_errors,
                table,
                "schema_identity",
                blocker,
            )


def _check_table_mapping(check: dict, semantics: dict) -> None:
    prod_table = semantics.get("prod_table")
    qa_table = semantics.get("qa_table")
    if prod_table and qa_table and prod_table != qa_table:
        check["prod_table"] = prod_table
        check["qa_table"] = qa_table


def _verification_checks(
    project: str,
    anchors: list[str],
    semantic_resolution,
    compare_scopes: dict[str, dict],
) -> list[dict]:
    checks = []
    for table in anchors:
        semantics = (
            semantic_resolution.target_semantics.get(table)
            if semantic_resolution is not None
            else None
        )
        check_group = {
            "table": table,
            "scope": dict(
                compare_scopes.get(table) or {"mode": FULL_TABLE_SCOPE}
            ),
            "methods": [],
        }
        if semantics is not None:
            _check_table_mapping(check_group, semantics)
            if semantics.get("column_mapping"):
                check_group["column_mapping"] = list(
                    semantics["column_mapping"]
                )
        for method in ("count", "row_compare"):
            method_config = {"method": method}
            if method == "row_compare":
                exclude_columns = _row_compare_exclude_columns(project, table)
                if exclude_columns is not None:
                    method_config["exclude_columns"] = exclude_columns
            check_group["methods"].append(method_config)
        checks.append(check_group)
    return checks


def _validate_semantic_check_invariants(verification: dict) -> None:
    target_semantics = verification.get("target_semantics") or {}
    for check_group in verification.get("checks") or []:
        table = check_group.get("table")
        semantics = target_semantics.get(table)
        if semantics is None:
            raise ValueError(
                f"verification check has no target semantics: {table}"
            )
        if semantics.get("resolved_mode") == "changed":
            raise ValueError(
                f"changed table cannot have a direct verification check: "
                f"{table}"
            )


def _normalized_scope(scope: dict) -> dict:
    return {
        "direct_tables": sorted(set(scope.get("direct_tables") or [])),
        "downstream_tables": sorted(set(scope.get("downstream_tables") or [])),
        "anchor_tables": sorted(set(scope.get("anchor_tables") or [])),
        "assessment_tables": sorted(set(scope.get("assessment_tables") or [])),
        "assessment_tasks": sorted(set(scope.get("assessment_tasks") or [])),
        "global_dimensions": sorted(set(scope.get("global_dimensions") or [])),
    }


def _modified_jobs(change_analysis: dict) -> list[str]:
    changed_assets = change_analysis["changed_assets"]
    return sorted(set(changed_assets.get("task_jobs") or []))


def _changed_asset_list(change_analysis: dict, key: str) -> list[str]:
    changed_assets = change_analysis.get("changed_assets")
    if not isinstance(changed_assets, dict):
        return []
    return sorted(set(changed_assets.get(key) or []))


def _plan_changes(change_analysis: dict, modified_jobs: list[str]) -> dict:
    return {
        "modified_jobs": sorted(set(modified_jobs or [])),
        "ddl_tables": _changed_asset_list(change_analysis, "ddl_tables"),
        "model_tables": _changed_asset_list(change_analysis, "model_tables"),
        "config_files": _changed_asset_list(change_analysis, "config_files"),
    }


def _changed_ddl_tables(change_analysis: dict) -> set[str]:
    changed_assets = change_analysis.get("changed_assets")
    if not isinstance(changed_assets, dict):
        return set()
    return set(changed_assets.get("ddl_tables") or [])


def _verification_anchor_tables(
    affected_scope: dict,
    modified_jobs: list[str],
    changed_ddl_tables: set[str],
) -> tuple[list[str], list[str]]:
    anchors = set(affected_scope["anchor_tables"])
    if anchors:
        return sorted(anchors), []
    direct_tables = set(affected_scope["direct_tables"])
    modified_job_set = set(modified_jobs)
    for table in direct_tables & modified_job_set:
        if table not in changed_ddl_tables:
            anchors.add(table)
    sorted_anchors = sorted(anchors)
    return sorted_anchors, sorted_anchors


def _has_verification_work(
    affected_scope: dict,
    jobs_to_run: list[dict],
    ddl_changes: list[dict],
) -> bool:
    return bool(
        affected_scope.get("direct_tables")
        or affected_scope.get("downstream_tables")
        or jobs_to_run
        or ddl_changes
    )


def _validation_error(table: str, field: str, message: str) -> dict:
    return {"table": table, "field": field, "message": message}


def _add_validation_error(
    metadata_errors: list[dict], table: str, field: str, message: str
) -> None:
    error = _validation_error(table, field, message)
    if error not in metadata_errors:
        metadata_errors.append(error)


def _project_verification_config(project: str) -> dict:
    return dict(
        config.PROJECT_CONFIG.get(project, {}).get("verification") or {}
    )


def _column_list(value, field_path: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_path} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _row_compare_exclude_columns(project: str, table: str) -> list[str] | None:
    verification = _project_verification_config(project)
    row_compare = verification.get("row_compare")
    if row_compare is None:
        return None
    if not isinstance(row_compare, dict):
        raise ValueError("verification.row_compare must be a mapping")

    tables = row_compare.get("tables", {})
    if tables is None:
        tables = {}
    if not isinstance(tables, dict):
        raise ValueError("verification.row_compare.tables must be a mapping")

    table_key = None
    table_config = None
    table_lookup = str(table).casefold()
    for raw_key, raw_value in tables.items():
        if str(raw_key).casefold() == table_lookup:
            table_key = raw_key
            table_config = raw_value
            break

    if table_config is not None:
        if not isinstance(table_config, dict):
            raise ValueError(
                f"verification.row_compare.tables.{table_key} "
                "must be a mapping"
            )
        if "exclude_columns" in table_config:
            return _column_list(
                table_config.get("exclude_columns"),
                (
                    "verification.row_compare.tables."
                    f"{table_key}.exclude_columns"
                ),
            )

    if "exclude_columns" in row_compare:
        return _column_list(
            row_compare.get("exclude_columns"),
            "verification.row_compare.exclude_columns",
        )
    return None


def _time_period(value) -> str:
    return str(value or "").strip().upper()


def _table_execution_slice_metadata(
    project: str,
    table: str,
    metadata_errors: list[dict],
) -> dict | None:
    metadata = config.get_model_metadata(table, project)
    if metadata is None:
        return None
    try:
        raw_execution = execution_config_for_model(table, metadata)
        execution_mode = normalize_execution_mode(
            table,
            raw_execution.get("mode"),
        )
    except ExecutionConfigError as exc:
        _add_validation_error(
            metadata_errors,
            table,
            "execution",
            str(exc),
        )
        return None
    if execution_mode == "taskless":
        return None
    project_execution = (config.PROJECT_CONFIG.get(project) or {}).get(
        "execution"
    ) or {}
    if not isinstance(project_execution, dict):
        project_execution = {}

    try:
        slice_config = slice_config_from_mapping(
            table,
            raw_execution.get("slice"),
            label="execution.slice",
        )
        if slice_config is None:
            slice_config = slice_config_from_mapping(
                table,
                project_execution.get("default_slice"),
                label="execution.default_slice",
            )
    except ExecutionConfigError as exc:
        _add_validation_error(
            metadata_errors,
            table,
            "execution.slice",
            str(exc),
        )
        return None

    if slice_config is None:
        return None

    period = _time_period(slice_config.period)
    if period not in SUPPORTED_TIME_PERIODS:
        _add_validation_error(
            metadata_errors,
            table,
            "execution.slice.period",
            "execution.slice.period must be one of D, W, M, H",
        )
        return None
    if (
        period == "W"
        and _week_start_index(
            project,
            table,
            metadata_errors,
        )
        is None
    ):
        return None
    return {
        "param": slice_config.param,
        "time_column": slice_config.column,
        "time_period": period,
    }


def _is_incremental_model(project: str, table: str) -> bool:
    metadata = config.get_model_metadata(table, project)
    if metadata is None:
        return True
    raw_execution = execution_config_for_model(table, metadata)
    if (
        normalize_execution_mode(table, raw_execution.get("mode"))
        == "taskless"
    ):
        return False
    materialized = str(
        raw_execution.get("materialized") or "incremental"
    ).strip()
    return materialized.lower() != "full"


def _validate_runnable_job_models(
    project: str,
    jobs_to_run: list[dict],
    metadata_errors: list[dict],
) -> None:
    for job in jobs_to_run:
        table = str(job.get("target") or job.get("job") or "")
        if not table:
            continue
        metadata = config.get_model_metadata(table, project)
        if metadata is None:
            continue
        try:
            raw_execution = execution_config_for_model(table, metadata)
            require_runnable_execution(table, raw_execution)
        except ExecutionConfigError as exc:
            _add_validation_error(
                metadata_errors,
                table,
                "execution.mode",
                str(exc),
            )


def _partition_required_jobs(
    project: str,
    jobs_to_run: list[dict],
    metadata_errors: list[dict],
) -> list[str]:
    jobs = []
    for job in jobs_to_run:
        table = job.get("target") or job.get("job")
        if not table:
            continue
        try:
            is_incremental = _is_incremental_model(project, table)
        except ExecutionConfigError as exc:
            _add_validation_error(
                metadata_errors,
                table,
                "execution.mode",
                str(exc),
            )
            continue
        if not is_incremental:
            continue
        before_error_count = len(metadata_errors)
        slice_metadata = _table_execution_slice_metadata(
            project,
            table,
            metadata_errors,
        )
        if len(metadata_errors) > before_error_count or not slice_metadata:
            continue
        jobs.append(str(job.get("job") or table))
    return sorted(set(jobs))


def _parse_anchor_date(value: str, table: str, metadata_errors: list[dict]):
    try:
        text = str(value).strip()
        if " " in text or "T" in text:
            return datetime.fromisoformat(text)
        return date.fromisoformat(text)
    except ValueError:
        _add_validation_error(
            metadata_errors,
            table,
            "anchor_time_value",
            "anchor time value must be an ISO date",
        )
        return None


def _week_start_index(
    project: str,
    table: str,
    metadata_errors: list[dict],
) -> int | None:
    week_start = str(
        _project_verification_config(project).get("week_start") or ""
    ).upper()
    if week_start not in WEEKDAY_INDEX:
        _add_validation_error(
            metadata_errors,
            table,
            "week_start",
            "project verification.week_start is required for W periods",
        )
        return None
    return WEEKDAY_INDEX[week_start]


def _period_start(
    value,
    period: str,
    project: str,
    table: str,
    metadata_errors: list[dict],
) -> date | datetime | None:
    if period == "H":
        if isinstance(value, datetime):
            return value.replace(minute=0, second=0, microsecond=0)
        return datetime.combine(value, time.min)
    if isinstance(value, datetime):
        value = value.date()
    if period == "D":
        return value
    if period == "M":
        return value.replace(day=1)
    if period == "W":
        week_start = _week_start_index(project, table, metadata_errors)
        if week_start is None:
            return None
        delta = (value.weekday() - week_start) % 7
        return value - timedelta(days=delta)
    return None


def _add_month(value: date) -> date:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def _period_end_exclusive(start, period: str):
    if period == "H":
        return start + timedelta(hours=1)
    if period == "D":
        return start + timedelta(days=1)
    if period == "W":
        return start + timedelta(days=7)
    return _add_month(start)


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _date_floor(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _date_ceiling(value) -> date:
    if not isinstance(value, datetime):
        return value
    value_date = value.date()
    if value.time() == time.min:
        return value_date
    return value_date + timedelta(days=1)


def _format_period_value(value, period: str) -> str:
    if period == "H":
        return _as_datetime(value).strftime("%Y-%m-%d %H:00:00")
    return _date_floor(value).isoformat()


def _period_values_for_window(
    window: dict,
    period: str,
    project: str,
) -> list[str]:
    start = window["start"]
    end = window["end_exclusive"]
    values = []
    if period == "H":
        current = _as_datetime(start)
        end = _as_datetime(end)
    else:
        current = _date_floor(start)
        end = _date_ceiling(end)

    if period == "W":
        errors = []
        current = _period_start(start, "W", project, "", errors) or start
    elif period == "M":
        current = _date_floor(start).replace(day=1)

    while current < end:
        values.append(_format_period_value(current, period))
        if period == "D":
            current += timedelta(days=1)
        elif period == "W":
            current += timedelta(days=7)
        elif period == "H":
            current += timedelta(hours=1)
        else:
            current = _add_month(current)
    return values


def _execution_values(
    windows: list[dict],
    refresh_period: str,
    project: str,
) -> list[str]:
    values = set()
    for window in windows:
        values.update(
            _period_values_for_window(window, refresh_period, project)
        )
    return sorted(values)


def _window_for_period_value(
    project: str,
    table: str,
    period: str,
    value: str,
    metadata_errors: list[dict],
) -> dict | None:
    parsed = _parse_anchor_date(value, table, metadata_errors)
    if parsed is None:
        return None
    start = _period_start(parsed, period, project, table, metadata_errors)
    if start is None:
        return None
    return {
        "table": table,
        "time_period": period,
        "start": start,
        "end_exclusive": _period_end_exclusive(start, period),
    }


def _windows_for_execution_values(
    project: str,
    table: str,
    period: str,
    values: list[str],
    metadata_errors: list[dict],
) -> list[dict]:
    windows = []
    for value in values:
        window = _window_for_period_value(
            project,
            table,
            period,
            value,
            metadata_errors,
        )
        if window is not None:
            windows.append(window)
    return windows


def _build_compare_scopes(
    project: str,
    anchors: list[str],
    anchor_value: str | None,
    metadata_errors: list[dict],
) -> tuple[dict, list[dict], list[dict]]:
    compare_scopes = {}
    windows = []
    full_table_tables = []
    no_anchor_value_tables = []

    for table in anchors:
        before_error_count = len(metadata_errors)
        slice_metadata = _table_execution_slice_metadata(
            project,
            table,
            metadata_errors,
        )
        if len(metadata_errors) > before_error_count:
            continue
        if not slice_metadata:
            compare_scopes[table] = {"mode": FULL_TABLE_SCOPE}
            full_table_tables.append(table)
            continue

        if not anchor_value:
            compare_scopes[table] = {"mode": FULL_TABLE_SCOPE}
            no_anchor_value_tables.append(table)
        else:
            parsed = _parse_anchor_date(anchor_value, table, metadata_errors)
            if parsed:
                start = _period_start(
                    parsed,
                    slice_metadata["time_period"],
                    project,
                    table,
                    metadata_errors,
                )
                if start:
                    formatted_value = _format_period_value(
                        start, slice_metadata["time_period"]
                    )
                    compare_scopes[table] = {
                        "mode": TIME_SLICE_SCOPE,
                        "column": slice_metadata["time_column"],
                        "period": slice_metadata["time_period"],
                        "value": formatted_value,
                    }
                    windows.append(
                        {
                            "table": table,
                            "time_period": slice_metadata["time_period"],
                            "start": start,
                            "end_exclusive": _period_end_exclusive(
                                start,
                                slice_metadata["time_period"],
                            ),
                        }
                    )

    warnings = []
    if full_table_tables:
        warnings.append(
            {
                "type": "full_table_compare",
                "tables": sorted(full_table_tables),
                "message": (
                    "No execution slice metadata is configured; "
                    "full-table compare will be used."
                ),
            }
        )
    if no_anchor_value_tables:
        warnings.append(
            {
                "type": "full_table_compare",
                "tables": sorted(no_anchor_value_tables),
                "message": (
                    "No anchor time value is provided; full-table compare "
                    "will be used."
                ),
            }
        )
    return compare_scopes, windows, warnings


def _apply_execution_values_globally(
    project: str,
    jobs_to_run: list[dict],
    anchor_windows: list[dict],
    metadata_errors: list[dict],
) -> None:
    for job in jobs_to_run:
        table = job.get("target") or job.get("job")
        before_error_count = len(metadata_errors)
        slice_metadata = _table_execution_slice_metadata(
            project,
            table,
            metadata_errors,
        )
        if len(metadata_errors) > before_error_count or not slice_metadata:
            continue
        values = _execution_values(
            anchor_windows,
            slice_metadata["time_period"],
            project,
        )
        if values:
            job["execution_values"] = values


def _lineage_upstream_by_key(
    lineage_data: dict | None,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    upstream, downstream = build_asset_table_graph(lineage_data or {})
    upstream_by_key: dict[str, set[str]] = defaultdict(set)
    table_name_by_key = {}
    for table in set(upstream) | set(downstream):
        table_name_by_key.setdefault(_table_key(table), _short_name(table))
    for table, sources in upstream.items():
        target_key = _table_key(table)
        table_name_by_key.setdefault(target_key, _short_name(table))
        for source in sources:
            source_key = _table_key(source)
            if source_key:
                upstream_by_key[target_key].add(source_key)
                table_name_by_key.setdefault(source_key, _short_name(source))
    return dict(upstream_by_key), table_name_by_key


def _job_table(job: dict) -> str:
    return str(job.get("target") or job.get("job") or "")


def _apply_execution_values_by_lineage(
    project: str,
    jobs_to_run: list[dict],
    anchor_windows: list[dict],
    metadata_errors: list[dict],
    lineage_data: dict | None,
) -> None:
    upstream_by_key, table_name_by_key = _lineage_upstream_by_key(lineage_data)
    jobs_by_key: dict[str, list[dict]] = defaultdict(list)
    assigned_values: dict[str, set[str]] = defaultdict(set)

    for job in jobs_to_run:
        table = _job_table(job)
        key = _table_key(table)
        if key:
            jobs_by_key[key].append(job)
            table_name_by_key.setdefault(key, table)

    queue = deque()
    for window in anchor_windows:
        table = str(window.get("table") or "")
        key = _table_key(table)
        if key:
            table_name_by_key.setdefault(key, _short_name(table))
            queue.append((key, window))

    visited = set()
    while queue:
        table_key, window = queue.popleft()
        visit_key = (
            table_key,
            window.get("start"),
            window.get("end_exclusive"),
        )
        if visit_key in visited:
            continue
        visited.add(visit_key)

        jobs = jobs_by_key.get(table_key) or []
        table = (
            _job_table(jobs[0]) if jobs else table_name_by_key.get(table_key)
        )
        if not table:
            continue

        before_error_count = len(metadata_errors)
        slice_metadata = _table_execution_slice_metadata(
            project,
            table,
            metadata_errors,
        )
        if len(metadata_errors) > before_error_count:
            continue

        upstream_windows = [window]
        if slice_metadata:
            period = slice_metadata["time_period"]
            values = _execution_values([window], period, project)
            if jobs and values:
                assigned_values[table_key].update(values)
            upstream_windows = _windows_for_execution_values(
                project,
                table,
                period,
                values,
                metadata_errors,
            )
            if len(metadata_errors) > before_error_count:
                continue

        for upstream_key in sorted(upstream_by_key.get(table_key, set())):
            for upstream_window in upstream_windows:
                queue.append((upstream_key, upstream_window))

    for table_key, values in assigned_values.items():
        for job in jobs_by_key.get(table_key) or []:
            if values:
                job["execution_values"] = sorted(values)


def _apply_execution_values(
    project: str,
    jobs_to_run: list[dict],
    anchor_windows: list[dict],
    metadata_errors: list[dict],
    lineage_data: dict | None = None,
) -> None:
    if not anchor_windows:
        return
    if not lineage_data or not (
        lineage_data.get("edges") or lineage_data.get("indirect_edges")
    ):
        _apply_execution_values_globally(
            project,
            jobs_to_run,
            anchor_windows,
            metadata_errors,
        )
        return
    _apply_execution_values_by_lineage(
        project,
        jobs_to_run,
        anchor_windows,
        metadata_errors,
        lineage_data,
    )


def _verification_metadata(
    checks: list[dict],
    affected_scope: dict,
    jobs_to_run: list[dict],
    ddl_changes: list[dict],
    blocked_schema_tables: list[str],
    anchor_tables: list[str],
    self_anchor_tables: list[str],
    warnings: list[dict] | None = None,
    metadata_errors: list[dict] | None = None,
    target_semantics: dict | None = None,
    semantic_boundaries: dict | None = None,
) -> dict:
    verification = {
        "anchor_tables": sorted(set(anchor_tables)),
        "checks": checks,
    }
    if target_semantics is not None:
        verification["target_semantics"] = target_semantics
    if semantic_boundaries is not None:
        verification["semantic_boundaries"] = semantic_boundaries
    combined_warnings = list(warnings or [])
    if blocked_schema_tables:
        verification["schema_anchor_status"] = "blocked"
        verification["schema_anchor_reason"] = (
            "ADS table definitions must remain unchanged during refactor "
            "verification"
        )
        verification["blocked_schema_tables"] = blocked_schema_tables
    if metadata_errors:
        verification["data_anchor_status"] = "blocked"
        verification["data_anchor_reason"] = (
            "verification time metadata is incomplete or invalid"
        )
        verification["metadata_errors"] = metadata_errors
        if combined_warnings:
            verification["warnings"] = combined_warnings
        return verification
    if checks:
        if self_anchor_tables:
            verification["data_anchor_status"] = "self_anchor_warning"
            verification["data_anchor_reason"] = (
                "fallback self-anchor tables are used because no downstream "
                "data anchor is available; compare can detect observed data "
                "differences but does not prove SQL semantic equivalence"
            )
            verification["self_anchor_tables"] = self_anchor_tables
            combined_warnings.append(
                {
                    "type": "fallback_self_anchor",
                    "tables": self_anchor_tables,
                    "message": (
                        "No downstream data anchor is available; using "
                        "SQL-only changed terminal tables as fallback anchors. "
                        "Passing compare does not prove SQL semantic "
                        "equivalence."
                    ),
                }
            )
            verification["warnings"] = combined_warnings
            return verification
        verification["data_anchor_status"] = "ready"
        if combined_warnings:
            verification["warnings"] = combined_warnings
        return verification
    if _has_verification_work(affected_scope, jobs_to_run, ddl_changes):
        verification["data_anchor_status"] = "none"
        verification["data_anchor_reason"] = (
            "no invariant downstream anchor tables; "
            "terminal tables with schema changes or no declared invariant "
            "require explicit manual verification"
        )
        if combined_warnings:
            verification["warnings"] = combined_warnings
        return verification
    verification["data_anchor_status"] = "not_required"
    if combined_warnings:
        verification["warnings"] = combined_warnings
    return verification


def _ads_schema_change_tables(
    project: str, ddl_changes: list[dict]
) -> list[str]:
    tables = set()
    for change in ddl_changes:
        for key in ("table_name", "old_name", "new_name"):
            table = _short_name(change.get(key))
            if (
                table
                and config.determine_operational_layer(table, project) == "ADS"
            ):
                tables.add(table)
    return sorted(tables)


def _sort_jobs_for_execution(
    project: str,
    jobs: set[str],
    *,
    lineage_data: dict | None = None,
) -> list[str]:
    if not jobs:
        return []
    has_explicit_jobs = bool(
        lineage_data
        and lineage_data.get("format_version") == 2
        and lineage_data.get("jobs")
    )
    if not lineage_data or (
        not has_explicit_jobs and not lineage_data.get("edges")
    ):
        raise ValueError("lineage data is required to sort jobs_to_run")
    return job_dag_from_lineage(lineage_data).topological_sort(set(jobs))


def _job_dependencies_for_plan(
    jobs: list[str],
    *,
    lineage_data: dict | None,
) -> dict[str, list[str]]:
    if not jobs:
        return {}

    _in_degree, adjacency = job_dag_from_lineage(
        lineage_data
    ).compute_in_degree(set(jobs))
    upstream_by_job = {job: set() for job in jobs}
    for upstream, downstream_jobs in adjacency.items():
        for downstream in downstream_jobs:
            upstream_by_job[downstream].add(upstream)

    return {
        job: sorted(upstream_by_job[job], key=identifier_match_key)
        for job in jobs
    }
