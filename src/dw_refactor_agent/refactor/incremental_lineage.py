"""Incremental lineage artifact builder for refactor runs."""

from __future__ import annotations

import json
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.lineage import lineage_extractor as extractor
from dw_refactor_agent.lineage.task_cache import (
    TASK_CACHE_FORMAT_VERSION,
    cache_entry_from_result,
    load_task_cache,
    stable_json_hash,
)
from dw_refactor_agent.sql.task_analysis import resolve_project_tasks_analysis


def _task_files(project: str) -> list:
    return resolve_project_tasks_analysis(project)


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
    resolved_tasks = _task_files(project)
    previous_cache = load_task_cache(previous_cache_path)

    task_cache_entries = []
    task_results = []
    reused = 0
    computed = 0
    extractor_hash = extractor._extractor_hash_for_cache()

    for index, (asset, analysis_sql) in enumerate(resolved_tasks):
        source_file = asset.source_file
        work_item = extractor.TaskWorkItem(
            index=index,
            source_file=source_file,
            sql_text=analysis_sql.sql,
            analysis_identity=dict(analysis_sql.analysis_identity),
        )
        work_item.sql_hash = extractor._task_sql_hash(work_item)
        cached = previous_cache.get(source_file)
        cache_key = ""
        if cached:
            cache_key = (
                extractor._cache_key_from_cached_metadata(
                    work_item,
                    cached,
                    schema,
                    project,
                    extractor_hash,
                )
                or ""
            )
        if cached and cached.get("cache_key") == cache_key:
            reused += 1
            result = extractor._task_result_from_cache(work_item, cached)
        else:
            computed += 1
            result = extractor._extract_task_work_item(work_item, schema)
        task_results.append(result)
        cache_key, cache_result = extractor._cache_metadata_for_result(
            result,
            work_item,
            schema,
            project,
            extractor_hash,
        )
        task_cache_entries.append(
            cache_entry_from_result(cache_result, cache_key)
        )

    all_lineage = []
    transient_tables = []
    missing_ddl_tables = set()
    missing_source_ddl = set()
    missing_target_ddl = set()
    diagnostics = []
    for result in task_results:
        all_lineage.extend(result.get("entries") or [])
        transient_tables.extend(result.get("transient_tables") or [])
        missing_ddl_tables.update(result.get("missing_ddl_tables") or [])
        missing_source_ddl.update(result.get("missing_source_ddl") or [])
        missing_target_ddl.update(result.get("missing_target_ddl") or [])
        diagnostics.extend(result.get("errors") or [])

    output = extractor.build_lineage_output(
        all_lineage,
        schema,
        transient_tables=transient_tables,
    )
    cache = {
        "format_version": TASK_CACHE_FORMAT_VERSION,
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
            "task_count": len(resolved_tasks),
            "computed_task_count": computed,
            "reused_task_count": reused,
            "missing_ddl_tables": sorted(missing_ddl_tables),
            "missing_source_ddl": sorted(missing_source_ddl),
            "missing_target_ddl": sorted(missing_target_ddl),
            "diagnostic_count": len(diagnostics),
        },
    }
