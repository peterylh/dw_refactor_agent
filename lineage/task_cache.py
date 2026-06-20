"""Task-level lineage cache helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sqlglot

from config import TEXT_ENCODING
from lineage import lineage_extractor as extractor


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode(TEXT_ENCODING)).hexdigest()


def stable_json_hash(value) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def extractor_version_hash() -> str:
    return sha256_text(
        Path(extractor.__file__).read_text(encoding=TEXT_ENCODING)
    )


def schema_slice_for_sql(sql_text: str, schema: dict) -> dict:
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
        table_names = extractor.collect_statement_table_names(statements)
        if table_names:
            return extractor.slice_schema(schema, table_names)
    except Exception:
        pass
    return extractor._copy_schema(schema)


def task_cache_key(
    *,
    project: str,
    source_file: str,
    sql_text: str,
    schema: dict,
    project_config: dict,
    extractor_hash: str | None = None,
) -> str:
    payload = {
        "project": project,
        "source_file": source_file,
        "sql_hash": sha256_text(sql_text),
        "schema_slice_hash": stable_json_hash(
            schema_slice_for_sql(sql_text, schema)
        ),
        "extractor_hash": extractor_hash or extractor_version_hash(),
        "project_config": {
            "catalog": project_config.get("catalog", "internal"),
            "db": project_config.get("db", ""),
        },
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
    return {
        "cache_key": cache_key,
        "source_file": result["source_file"],
        "entries": result.get("entries") or [],
        "transient_tables": result.get("transient_tables") or [],
        "missing_ddl_tables": result.get("missing_ddl_tables") or [],
        "stats": result.get("stats") or {},
        "errors": result.get("errors") or [],
    }
