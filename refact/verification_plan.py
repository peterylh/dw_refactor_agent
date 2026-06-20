"""Build validation plans for refactor run shadow execution."""

from __future__ import annotations

from pathlib import Path

import config
from config import TEXT_ENCODING


def _strip_insert_data(sql_text: str) -> str:
    lines = []
    for line in str(sql_text or "").splitlines():
        if line.strip().upper().startswith("INSERT"):
            break
        lines.append(line)
    return "\n".join(lines)


def _current_ddl_by_table(project: str, table_names: set[str]) -> dict:
    ddl = {}
    for path in config.iter_project_asset_files(project, "ddl", "*.sql"):
        table_name = path.stem
        if table_name in table_names:
            ddl[table_name] = _strip_insert_data(
                path.read_text(encoding=TEXT_ENCODING)
            )
    return dict(sorted(ddl.items()))


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


def build_verification_plan(project: str, change_analysis: dict) -> dict:
    cfg = config.PROJECT_CONFIG[project]
    scope = change_analysis.get("affected_scope") or {}
    assessment_tables = set(scope.get("assessment_tables") or [])
    assessment_tasks = set(scope.get("assessment_tasks") or [])
    anchors = sorted(set(scope.get("anchor_tables") or []))

    jobs_to_run = []
    for job_name in sorted(assessment_tasks):
        entry = _job_entry(project, job_name)
        if entry:
            jobs_to_run.append(entry)
            assessment_tables.add(entry["target"])

    checks = []
    for table in anchors:
        checks.append({"table": table, "method": "count"})
        checks.append({"table": table, "method": "row_compare"})

    return {
        "project": project,
        "project_db": cfg["db"],
        "qa_db": cfg["qa_db"],
        "baseline_ddl": _current_ddl_by_table(project, assessment_tables),
        "ddl_changes": [],
        "partition_info": {},
        "jobs_to_run": jobs_to_run,
        "checks": checks,
        "verification": {"checks": checks},
    }
