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


def cache_project_config(project_config: dict) -> dict:
    return {
        "catalog": project_config.get("catalog", "internal"),
        "db": project_config.get("db", ""),
    }


def schema_slice_for_table_names(table_names, schema: dict) -> dict:
    if table_names:
        return extractor.slice_schema(schema, table_names)
    return extractor._copy_schema(schema)


def schema_slice_hash_for_table_names(table_names, schema: dict) -> str:
    return stable_json_hash(schema_slice_for_table_names(table_names, schema))


def schema_slice_for_sql(sql_text: str, schema: dict) -> dict:
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
        table_names = extractor.collect_statement_table_names(statements)
        if table_names:
            return schema_slice_for_table_names(table_names, schema)
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
    sql_hash: str | None = None,
    referenced_tables=None,
    schema_slice_hash: str | None = None,
) -> str:
    if sql_hash is None:
        sql_hash = sha256_text(sql_text)
    if schema_slice_hash is None:
        if referenced_tables is not None:
            schema_slice_hash = schema_slice_hash_for_table_names(
                referenced_tables,
                schema,
            )
        else:
            schema_slice_hash = stable_json_hash(
                schema_slice_for_sql(sql_text, schema)
            )

    payload = {
        "project": project,
        "source_file": source_file,
        "sql_hash": sql_hash,
        "schema_slice_hash": schema_slice_hash,
        "extractor_hash": extractor_hash or extractor_version_hash(),
        "project_config": cache_project_config(project_config),
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
