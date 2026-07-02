"""Build validation plans for refactor run shadow execution."""

from __future__ import annotations

from pathlib import Path

import config
from config import TEXT_ENCODING
from ddl_deriver.ddl_deriver import (
    changes_to_json,
    derive_ddl_changes,
    load_git_ddl_texts,
    load_git_tables,
    load_tables_from_dir,
)
from doris_sql import extract_doris_partition_column
from lineage.job_dag import asset_job_dag_from_lineage


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


def _project_ddl_rel(project: str) -> str:
    return f"{config.PROJECT_CONFIG[project]['dir']}/ddl"


def load_baseline_ddl(
    project: str,
    base_ref: str,
    *,
    repo_root: Path | None = None,
) -> dict:
    """Load project DDL text from a git base ref."""
    repo = _project_repo_root(repo_root)
    ddl_rel = _project_ddl_rel(project)
    baseline_ddl = {
        table_name: strip_insert_data(content)
        for table_name, content in load_git_ddl_texts(
            repo, ddl_rel, base_ref
        ).items()
    }
    return dict(sorted(baseline_ddl.items()))


def derive_project_ddl_changes(
    project: str,
    base_ref: str,
    *,
    repo_root: Path | None = None,
) -> list[dict]:
    """Derive DDL changes between a git base ref and the working tree."""
    repo = _project_repo_root(repo_root)
    ddl_rel = _project_ddl_rel(project)
    old_tables = load_git_tables(repo, ddl_rel, base_ref)
    new_tables = load_tables_from_dir(repo / ddl_rel)
    changes = derive_ddl_changes(old_tables, new_tables)
    return changes_to_json(changes)["changes"]


def _task_path(project: str, job_name: str) -> Path | None:
    cfg = config.PROJECT_CONFIG[project]
    tasks_dir = config.PROJECT_ROOT / cfg["dir"] / "tasks"
    candidates = [
        tasks_dir / f"{job_name}.sql",
        tasks_dir / "full_refresh" / f"{job_name}_full_refresh.sql",
        tasks_dir / "full_refresh" / f"{job_name}.sql",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _relative(path: Path) -> str:
    try:
        return path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _job_entry(project: str, job_name: str) -> dict | None:
    task_path = _task_path(project, job_name)
    if not task_path:
        return None
    sql_text = task_path.read_text(encoding=TEXT_ENCODING)
    return {
        "job": job_name,
        "file": _relative(task_path),
        "layer": config.determine_layer(job_name, project),
        "target": job_name,
        "needs_etl_date": "@etl_date" in sql_text,
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
    scope = change_analysis.get("affected_scope") or {}
    affected_scope = _normalized_affected_scope(scope)
    assessment_tables = set(affected_scope["assessment_tables"])
    assessment_tasks = set(affected_scope["assessment_tasks"])
    modified_jobs = _modified_jobs(change_analysis, assessment_tasks)
    changed_ddl_tables = _changed_ddl_tables(change_analysis)
    anchors, self_anchor_tables = _verification_anchor_tables(
        affected_scope,
        modified_jobs,
        changed_ddl_tables,
    )
    affected_scope["anchor_tables"] = anchors
    downstream_tables = affected_scope["downstream_tables"]

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

    partition_info = _build_partition_info(
        partition,
        anchors,
        baseline_ddl,
    )

    checks = []
    for table in anchors:
        table_partition = partition_info.get("per_table", {}).get(table)
        for method in ("count", "row_compare"):
            check = {"table": table, "method": method}
            if table_partition:
                check["partition_col"] = table_partition["partition_col"]
                check["partition_value"] = table_partition["value"]
            checks.append(check)

    verification = _verification_metadata(
        checks,
        affected_scope,
        jobs_to_run,
        ddl_changes,
        _ads_schema_change_tables(project, ddl_changes),
        self_anchor_tables,
    )

    return {
        "project": project,
        "project_db": cfg["db"],
        "qa_db": cfg["qa_db"],
        "affected_scope": affected_scope,
        "modified_jobs": modified_jobs,
        "downstream_tables": downstream_tables,
        "anchors": anchors,
        "baseline_ddl": dict(sorted(baseline_ddl.items())),
        "ddl_changes": ddl_changes,
        "partition_info": partition_info,
        "jobs_to_run": jobs_to_run,
        "verification": verification,
    }


def _normalized_affected_scope(scope: dict) -> dict:
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


def _verification_metadata(
    checks: list[dict],
    affected_scope: dict,
    jobs_to_run: list[dict],
    ddl_changes: list[dict],
    blocked_schema_tables: list[str],
    self_anchor_tables: list[str],
) -> dict:
    verification = {"checks": checks}
    if blocked_schema_tables:
        verification["schema_anchor_status"] = "blocked"
        verification["schema_anchor_reason"] = (
            "ADS table definitions must remain unchanged during refactor "
            "verification"
        )
        verification["blocked_schema_tables"] = blocked_schema_tables
    if checks:
        if self_anchor_tables:
            verification["data_anchor_status"] = "self_anchor_warning"
            verification["data_anchor_reason"] = (
                "fallback self-anchor tables are used because no downstream "
                "data anchor is available; compare can detect observed data "
                "differences but does not prove SQL semantic equivalence"
            )
            verification["self_anchor_tables"] = self_anchor_tables
            verification["warnings"] = [
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
            ]
            return verification
        verification["data_anchor_status"] = "ready"
        return verification
    if _has_verification_work(affected_scope, jobs_to_run, ddl_changes):
        verification["data_anchor_status"] = "none"
        verification["data_anchor_reason"] = (
            "no invariant downstream anchor tables; "
            "terminal tables with schema changes or no declared invariant "
            "require explicit manual verification"
        )
        return verification
    verification["data_anchor_status"] = "not_required"
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


def _build_partition_info(
    partition: str | None,
    anchors: list[str],
    baseline_ddl: dict,
) -> dict:
    if not partition:
        return {}
    per_table = {}
    for table in anchors:
        partition_col = get_partition_col(table, baseline_ddl)
        if partition_col:
            per_table[table] = {
                "partition_col": partition_col,
                "value": partition,
            }
    return {
        "partition": partition,
        "etl_date": partition,
        "per_table": per_table,
    }
