"""Incremental lineage artifact builder for refactor runs."""

from __future__ import annotations

import json
from pathlib import Path

import config
from config import TEXT_ENCODING
from lineage import lineage_extractor as extractor
from lineage.task_cache import (
    cache_entry_from_result,
    load_task_cache,
    stable_json_hash,
    task_cache_key,
)


def _task_files(project: str) -> tuple[Path, list[Path]]:
    cfg = config.PROJECT_CONFIG[project]
    tasks_dir = config.PROJECT_ROOT / cfg["dir"] / "tasks"
    task_files = []
    if tasks_dir.exists():
        task_files.extend(sorted(tasks_dir.glob("*.sql")))
        full_refresh_dir = tasks_dir / "full_refresh"
        if full_refresh_dir.exists():
            task_files.extend(sorted(full_refresh_dir.glob("*.sql")))
    return tasks_dir, task_files


def _write_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )


def build_lineage_artifacts(
    project: str,
    output_path: Path,
    cache_path: Path,
    *,
    previous_cache_path: Path | None = None,
) -> dict:
    """Build lineage output and task cache for a project."""
    extractor.configure_project(project)
    schema = extractor.build_schema_from_project_ddl(project)
    tasks_dir, task_files = _task_files(project)
    previous_cache = load_task_cache(previous_cache_path)

    task_cache_entries = []
    task_results = []
    reused = 0
    computed = 0

    for index, task_file in enumerate(task_files):
        source_file = task_file.relative_to(tasks_dir).as_posix()
        sql_text = task_file.read_text(encoding=TEXT_ENCODING)
        cache_key = task_cache_key(
            project=project,
            source_file=source_file,
            sql_text=sql_text,
            schema=schema,
            project_config=config.PROJECT_CONFIG[project],
        )
        cached = previous_cache.get(source_file)
        if cached and cached.get("cache_key") == cache_key:
            reused += 1
            result = {
                "index": index,
                "source_file": source_file,
                "entries": cached.get("entries") or [],
                "transient_tables": cached.get("transient_tables") or [],
                "missing_ddl_tables": cached.get("missing_ddl_tables") or [],
                "stats": cached.get("stats") or {},
                "errors": cached.get("errors") or [],
            }
        else:
            computed += 1
            work_item = {
                "index": index,
                "source_file": source_file,
                "sql_text": sql_text,
            }
            result = extractor._extract_task_work_item(work_item, schema)
        task_results.append(result)
        task_cache_entries.append(cache_entry_from_result(result, cache_key))

    all_lineage = []
    transient_tables = []
    missing_ddl_tables = set()
    diagnostics = []
    for result in task_results:
        all_lineage.extend(result.get("entries") or [])
        transient_tables.extend(result.get("transient_tables") or [])
        missing_ddl_tables.update(result.get("missing_ddl_tables") or [])
        diagnostics.extend(result.get("errors") or [])

    output = extractor.build_lineage_output(
        all_lineage,
        schema,
        transient_tables=transient_tables,
    )
    cache = {
        "project": project,
        "schema_hash": stable_json_hash(schema),
        "tasks": sorted(
            task_cache_entries,
            key=lambda item: item.get("source_file", ""),
        ),
    }

    _write_json(output_path, output)
    _write_json(cache_path, cache)

    return {
        "lineage": output,
        "cache": cache,
        "summary": {
            "task_count": len(task_files),
            "computed_task_count": computed,
            "reused_task_count": reused,
            "missing_ddl_tables": sorted(missing_ddl_tables),
            "diagnostic_count": len(diagnostics),
        },
    }
