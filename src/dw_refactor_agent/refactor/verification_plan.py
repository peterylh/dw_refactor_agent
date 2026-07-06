"""Build validation plans for refactor run shadow execution."""

from __future__ import annotations

from datetime import date, timedelta
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
from dw_refactor_agent.lineage.job_dag import asset_job_dag_from_lineage
from dw_refactor_agent.sql.doris import extract_doris_partition_column

SUPPORTED_TIME_PERIODS = {"D", "W", "M"}
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
    repo = _project_repo_root(repo_root)
    old_tables = {}
    new_tables = {}
    for ddl_rel in _project_ddl_rels(project):
        old_tables.update(load_git_tables(repo, ddl_rel, base_ref))
        new_tables.update(load_tables_from_dir(repo / ddl_rel))
    changes = derive_ddl_changes(old_tables, new_tables)
    return changes_to_json(changes)["changes"]


def _task_path(project: str, job_name: str) -> Path | None:
    return config.task_path_for_job(project, job_name)


def _relative(path: Path) -> str:
    try:
        return path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _job_entry(project: str, job_name: str) -> dict | None:
    task_path = _task_path(project, job_name)
    if not task_path:
        return None
    return {
        "job": job_name,
        "file": _relative(task_path),
        "layer": config.determine_layer(job_name, project),
        "target": job_name,
    }


def _short_name(name: str) -> str:
    return str(name or "").split(".")[-1]


def _phase2_create_tables(ddl_changes: list[dict]) -> set[str]:
    phase2_creates = set()
    for change in ddl_changes:
        change_type = change.get("change_type")
        if change_type == "CREATE":
            phase2_creates.add(_short_name(change.get("table_name")))
        elif change_type == "RENAME":
            phase2_creates.add(_short_name(change.get("new_name")))
    return phase2_creates


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
) -> dict:
    cfg = config.PROJECT_CONFIG[project]
    metadata_errors = []
    raw_scope = (
        change_analysis.get("scope")
        or change_analysis.get("affected_scope")
        or {}
    )
    scope = _normalized_scope(raw_scope)
    assessment_tables = set(scope["assessment_tables"])
    assessment_tasks = set(scope["assessment_tasks"])
    modified_jobs = _modified_jobs(change_analysis, assessment_tasks)
    changed_ddl_tables = _changed_ddl_tables(change_analysis)
    anchors, self_anchor_tables = _verification_anchor_tables(
        scope,
        modified_jobs,
        changed_ddl_tables,
    )
    scope["anchor_tables"] = anchors
    changes = _plan_changes(change_analysis, modified_jobs)

    sorted_jobs = _sort_jobs_for_execution(
        project,
        assessment_tasks,
        lineage_data=lineage_data,
    )

    jobs_to_run = []
    for job_name in sorted_jobs:
        entry = _job_entry(project, job_name)
        if entry:
            jobs_to_run.append(entry)
            assessment_tables.add(entry["target"])

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
        needed_baseline = _baseline_needed_tables(
            ddl_changes,
            jobs_to_run,
            set(anchors),
        )
        baseline_ddl = {
            table: strip_insert_data(ddl)
            for table, ddl in all_baseline_ddl.items()
            if table in needed_baseline
        }
    else:
        ddl_changes = []
        baseline_ddl = _current_ddl_by_table(project, assessment_tables)

    compare_anchors, anchor_windows, verification_warnings = (
        _build_compare_anchors(
            project,
            anchors,
            partition,
            metadata_errors,
        )
    )
    _apply_refresh_metadata(
        project,
        jobs_to_run,
        anchor_windows,
        metadata_errors,
    )

    checks = []
    for table in anchors:
        for method in ("count", "row_compare"):
            check = {"table": table, "method": method}
            if method == "row_compare":
                exclude_columns = _row_compare_exclude_columns(project, table)
                if exclude_columns is not None:
                    check["exclude_columns"] = exclude_columns
            checks.append(check)

    verification = _verification_metadata(
        [] if metadata_errors else checks,
        scope,
        jobs_to_run,
        ddl_changes,
        _ads_schema_change_tables(project, ddl_changes),
        self_anchor_tables,
        compare_anchors,
        verification_warnings,
        metadata_errors,
    )

    return {
        "project": project,
        "project_db": cfg["db"],
        "qa_db": cfg["qa_db"],
        "changes": changes,
        "scope": scope,
        "baseline_ddl": dict(sorted(baseline_ddl.items())),
        "ddl_changes": ddl_changes,
        "jobs_to_run": jobs_to_run,
        "verification": verification,
    }


def _normalized_scope(scope: dict) -> dict:
    return {
        "direct_tables": sorted(set(scope.get("direct_tables") or [])),
        "downstream_tables": sorted(set(scope.get("downstream_tables") or [])),
        "anchor_tables": sorted(set(scope.get("anchor_tables") or [])),
        "assessment_tables": sorted(set(scope.get("assessment_tables") or [])),
        "assessment_tasks": sorted(set(scope.get("assessment_tasks") or [])),
        "global_dimensions": sorted(set(scope.get("global_dimensions") or [])),
    }


def _modified_jobs(
    change_analysis: dict, assessment_tasks: set[str]
) -> list[str]:
    changed_assets = change_analysis.get("changed_assets")
    if isinstance(changed_assets, dict) and "task_jobs" in changed_assets:
        return sorted(set(changed_assets.get("task_jobs") or []))
    return sorted(assessment_tasks)


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
        or affected_scope.get("assessment_tasks")
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


def _table_grain_metadata(
    project: str,
    table: str,
    metadata_errors: list[dict],
) -> dict | None:
    metadata = config.get_model_metadata(table, project) or {}
    grain = metadata.get("grain")
    if not isinstance(grain, dict) or not grain:
        return None

    time_column = grain.get("time_column")
    period = _time_period(grain.get("time_period"))
    if not time_column and not period:
        return None
    if bool(time_column) != bool(period):
        _add_validation_error(
            metadata_errors,
            table,
            "grain",
            (
                "grain.time_column and grain.time_period must be "
                "configured together"
            ),
        )
        return None
    if period and period not in SUPPORTED_TIME_PERIODS:
        _add_validation_error(
            metadata_errors,
            table,
            "grain.time_period",
            "grain.time_period must be one of D, W, M",
        )
        return None
    if (
        period == "W"
        and _week_start_index(project, table, metadata_errors) is None
    ):
        return None
    return {"time_column": str(time_column), "time_period": period}


def _table_refresh_metadata(
    project: str,
    table: str,
    grain: dict,
    metadata_errors: list[dict],
) -> dict | None:
    metadata = config.get_model_metadata(table, project) or {}
    refresh = metadata.get("refresh")
    if isinstance(refresh, dict) and refresh:
        parameter = refresh.get("parameter")
        period = _time_period(refresh.get("time_period"))
        if bool(parameter) != bool(period):
            _add_validation_error(
                metadata_errors,
                table,
                "refresh",
                (
                    "refresh.parameter and refresh.time_period must be "
                    "configured together"
                ),
            )
            return None
        if period not in SUPPORTED_TIME_PERIODS:
            _add_validation_error(
                metadata_errors,
                table,
                "refresh.time_period",
                "refresh.time_period must be one of D, W, M",
            )
            return None
        if (
            period == "W"
            and _week_start_index(project, table, metadata_errors) is None
        ):
            return None
        return {"parameter": str(parameter), "time_period": period}

    parameter = _project_verification_config(project).get(
        "default_refresh_parameter"
    )
    if not parameter:
        _add_validation_error(
            metadata_errors,
            table,
            "refresh.parameter",
            (
                "refresh.parameter is missing and project "
                "verification.default_refresh_parameter is not configured"
            ),
        )
        return None
    return {
        "parameter": str(parameter),
        "time_period": grain["time_period"],
    }


def _parse_anchor_date(value: str, table: str, metadata_errors: list[dict]):
    try:
        return date.fromisoformat(str(value))
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
    value: date,
    period: str,
    project: str,
    table: str,
    metadata_errors: list[dict],
) -> date | None:
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


def _period_end_exclusive(start: date, period: str) -> date:
    if period == "D":
        return start + timedelta(days=1)
    if period == "W":
        return start + timedelta(days=7)
    return _add_month(start)


def _period_values_for_window(
    window: dict,
    period: str,
    project: str,
) -> list[str]:
    start = window["start"]
    end = window["end_exclusive"]
    values = []
    current = start
    if period == "W":
        errors = []
        current = _period_start(start, "W", project, "", errors) or start
    elif period == "M":
        current = start.replace(day=1)

    while current < end:
        values.append(current.isoformat())
        if period == "D":
            current += timedelta(days=1)
        elif period == "W":
            current += timedelta(days=7)
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


def _build_compare_anchors(
    project: str,
    anchors: list[str],
    anchor_value: str | None,
    metadata_errors: list[dict],
) -> tuple[dict, list[dict], list[dict]]:
    compare_anchors = {}
    windows = []
    full_table_tables = []
    no_anchor_value_tables = []

    for table in anchors:
        before_error_count = len(metadata_errors)
        grain = _table_grain_metadata(project, table, metadata_errors)
        if len(metadata_errors) > before_error_count:
            continue
        if not grain:
            compare_anchors[table] = {}
            full_table_tables.append(table)
            continue

        anchor = dict(grain)
        if not anchor_value:
            no_anchor_value_tables.append(table)
        else:
            parsed = _parse_anchor_date(anchor_value, table, metadata_errors)
            if parsed:
                start = _period_start(
                    parsed,
                    grain["time_period"],
                    project,
                    table,
                    metadata_errors,
                )
                if start:
                    anchor["anchor_time_value"] = start.isoformat()
                    windows.append(
                        {
                            "table": table,
                            "time_period": grain["time_period"],
                            "start": start,
                            "end_exclusive": _period_end_exclusive(
                                start,
                                grain["time_period"],
                            ),
                        }
                    )
        compare_anchors[table] = anchor

    warnings = []
    if full_table_tables:
        warnings.append(
            {
                "type": "full_table_compare",
                "tables": sorted(full_table_tables),
                "message": (
                    "No grain/refresh time metadata is configured; "
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
    return compare_anchors, windows, warnings


def _apply_refresh_metadata(
    project: str,
    jobs_to_run: list[dict],
    anchor_windows: list[dict],
    metadata_errors: list[dict],
) -> None:
    for job in jobs_to_run:
        table = job.get("target") or job.get("job")
        before_error_count = len(metadata_errors)
        grain = _table_grain_metadata(project, table, metadata_errors)
        if len(metadata_errors) > before_error_count or not grain:
            continue

        refresh = _table_refresh_metadata(
            project,
            table,
            grain,
            metadata_errors,
        )
        if not refresh:
            continue
        job["refresh_parameter"] = refresh["parameter"]
        job["refresh_time_period"] = refresh["time_period"]
        values = _execution_values(
            anchor_windows,
            refresh["time_period"],
            project,
        )
        if values:
            job["execution_values"] = values


def _verification_metadata(
    checks: list[dict],
    affected_scope: dict,
    jobs_to_run: list[dict],
    ddl_changes: list[dict],
    blocked_schema_tables: list[str],
    self_anchor_tables: list[str],
    compare_anchors: dict | None = None,
    warnings: list[dict] | None = None,
    metadata_errors: list[dict] | None = None,
) -> dict:
    verification = {"checks": checks}
    if compare_anchors is not None:
        verification["compare_anchors"] = compare_anchors
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
            if table and config.determine_layer(table, project) == "ADS":
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
    if not lineage_data or not lineage_data.get("edges"):
        raise ValueError("lineage data is required to sort jobs_to_run")
    return asset_job_dag_from_lineage(lineage_data).topological_sort(set(jobs))
