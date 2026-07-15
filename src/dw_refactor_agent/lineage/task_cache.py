"""Task-level lineage cache helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING

TASK_CACHE_FORMAT_VERSION = 3
TASK_FACT_FIELDS = (
    "input_tables",
    "output_tables",
    "created_tables",
    "temporary_tables",
    "local_lifecycle_tables",
)
TASK_SCHEMA_FIELDS = ("process_table_schemas",)


@dataclass
class TaskCacheMetadata:
    sql_hash: str
    referenced_tables: tuple
    schema_slice_hash: str
    extractor_hash: str
    project_config: dict


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode(TEXT_ENCODING)).hexdigest()


def stable_json_hash(value) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def extractor_version_hash(extractor_file) -> str:
    files = (
        [extractor_file]
        if isinstance(extractor_file, (str, Path))
        else list(extractor_file)
    )
    return stable_json_hash(
        [Path(path).read_text(encoding=TEXT_ENCODING) for path in files]
    )


def cache_project_config(project_config: dict) -> dict:
    return {
        "catalog": project_config.get("catalog", "internal"),
        "db": project_config.get("db", ""),
    }


def task_cache_key(
    *,
    project: str,
    source_file: str,
    metadata: TaskCacheMetadata,
) -> str:
    payload = {
        "project": project,
        "source_file": source_file,
        "sql_hash": metadata.sql_hash,
        "schema_slice_hash": metadata.schema_slice_hash,
        "extractor_hash": metadata.extractor_hash,
        "project_config": cache_project_config(metadata.project_config),
    }
    return stable_json_hash(payload)


def load_task_cache(path: Path | None) -> dict:
    if not path:
        return {}
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding=TEXT_ENCODING))
    container_version = data.get("format_version")
    if container_version not in {None, TASK_CACHE_FORMAT_VERSION}:
        return {}
    return {
        entry["source_file"]: entry
        for entry in data.get("tasks", [])
        if entry.get("source_file")
        and (
            container_version == TASK_CACHE_FORMAT_VERSION
            or entry.get("format_version") == TASK_CACHE_FORMAT_VERSION
        )
        and all(
            field in entry
            for field in (*TASK_FACT_FIELDS, *TASK_SCHEMA_FIELDS)
        )
    }


def _json_cache_value(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def cache_entry_from_result(result: dict, cache_key: str) -> dict:
    entry = {
        "format_version": TASK_CACHE_FORMAT_VERSION,
        "cache_key": cache_key,
        "source_file": result["source_file"],
        "entries": result.get("entries") or [],
        "transient_tables": result.get("transient_tables") or [],
        "missing_ddl_tables": result.get("missing_ddl_tables") or [],
        "missing_source_ddl": result.get("missing_source_ddl") or [],
        "missing_target_ddl": result.get("missing_target_ddl") or [],
        "stats": result.get("stats") or {},
        "errors": result.get("errors") or [],
    }
    for key in TASK_FACT_FIELDS:
        if key in result:
            entry[key] = _json_cache_value(result.get(key) or [])
    for key in TASK_SCHEMA_FIELDS:
        entry[key] = result.get(key) or []
    for key in (
        "sql_hash",
        "referenced_tables",
        "schema_slice_hash",
        "extractor_hash",
        "project_config",
    ):
        if key in result:
            entry[key] = result[key]
    return entry
