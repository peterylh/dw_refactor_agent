"""Task-level lineage cache helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING


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


def extractor_version_hash(extractor_file: str | Path) -> str:
    return sha256_text(Path(extractor_file).read_text(encoding=TEXT_ENCODING))


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
    return {
        entry["source_file"]: entry
        for entry in data.get("tasks", [])
        if entry.get("source_file")
    }


def cache_entry_from_result(result: dict, cache_key: str) -> dict:
    entry = {
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
