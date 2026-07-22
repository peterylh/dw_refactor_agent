"""Task parsing, caching, and parallel lineage extraction."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sqlglot
from sqlglot import exp

from dw_refactor_agent.lineage.runtime_binding import RuntimeBindings

_BINDINGS = RuntimeBindings(
    __name__,
    "dw_refactor_agent.lineage.lineage_extractor",
)

_apply_alter_table_to_task_schema = _BINDINGS.delegate(
    "_apply_alter_table_to_task_schema"
)
_canonical_column = _BINDINGS.delegate("_canonical_column")
_canonical_lineage_entry = _BINDINGS.delegate("_canonical_lineage_entry")
_copy_schema = _BINDINGS.delegate("_copy_schema")
_created_table_columns_from_schema = _BINDINGS.delegate(
    "_created_table_columns_from_schema"
)
_default_catalog = _BINDINGS.delegate("_default_catalog")
_default_db = _BINDINGS.delegate("_default_db")
_diagnostic_error = _BINDINGS.delegate("_diagnostic_error")
_diagnostic_severity = _BINDINGS.delegate("_diagnostic_severity")
_drop_task_table_schema = _BINDINGS.delegate("_drop_task_table_schema")
_handle_create = _BINDINGS.delegate("_handle_create")
_handle_delete = _BINDINGS.delegate("_handle_delete")
_handle_insert = _BINDINGS.delegate("_handle_insert")
_handle_merge = _BINDINGS.delegate("_handle_merge")
_handle_select_into = _BINDINGS.delegate("_handle_select_into")
_handle_update = _BINDINGS.delegate("_handle_update")
_identifier_match_key = _BINDINGS.delegate("_identifier_match_key")
_is_table_drop_statement = _BINDINGS.delegate("_is_table_drop_statement")
_iter_matching_schema_tables = _BINDINGS.delegate(
    "_iter_matching_schema_tables"
)
_iter_schema_tables = _BINDINGS.delegate("_iter_schema_tables")
_qualified_table_name = _BINDINGS.delegate("_qualified_table_name")
_record_diagnostic = _BINDINGS.delegate("_record_diagnostic")
_register_task_table_schema = _BINDINGS.delegate("_register_task_table_schema")
_schema_has_table = _BINDINGS.delegate("_schema_has_table")
_schema_lookup = _BINDINGS.delegate("_schema_lookup")
_schema_table_match_key = _BINDINGS.delegate("_schema_table_match_key")
_sqlglot_task_sql = _BINDINGS.delegate("_sqlglot_task_sql")
_statement_existing_target_table_names = _BINDINGS.delegate(
    "_statement_existing_target_table_names"
)
_statement_source_table_names = _BINDINGS.delegate(
    "_statement_source_table_names"
)
_strip_db = _BINDINGS.delegate("_strip_db")
_table_identity_match_key = _BINDINGS.delegate("_table_identity_match_key")
_target_table_sql = _BINDINGS.delegate("_target_table_sql")
_task_schema_for_table_names = _BINDINGS.delegate(
    "_task_schema_for_table_names"
)
collect_statement_cte_names = _BINDINGS.delegate("collect_statement_cte_names")
collect_statement_table_names = _BINDINGS.delegate(
    "collect_statement_table_names"
)
configure_project = _BINDINGS.delegate("configure_project")
extract_task_table_facts = _BINDINGS.delegate("extract_task_table_facts")
extract_task_table_facts_from_statements = _BINDINGS.delegate(
    "extract_task_table_facts_from_statements"
)
slice_schema = _BINDINGS.delegate("slice_schema")


def _runtime_stats():
    return _BINDINGS.runtime().STATS


def _reset_stats():
    stats = _runtime_stats()
    stats["parse_failures"] = 0
    stats["lineage_failures"] = 0


def _add_stats(stats):
    runtime_stats = _runtime_stats()
    for key in runtime_stats:
        runtime_stats[key] += int((stats or {}).get(key, 0))


@dataclass
class TaskWorkItem:
    index: int
    source_file: str
    sql_text: str
    sql_hash: str = ""
    cache_key: str = ""
    analysis_identity: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTaskContext:
    work_item: TaskWorkItem
    statements: List[Any]
    task_facts: Dict[str, Any]
    referenced_tables: Tuple[str, ...]
    cte_names: Tuple[str, ...]
    task_schema: Dict[str, Any]
    missing_ddl_tables: List[str]
    missing_source_ddl: List[str]
    missing_target_ddl: List[str]
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def index(self):
        return self.work_item.index

    @property
    def source_file(self):
        return self.work_item.source_file

    @property
    def sql_hash(self):
        return self.work_item.sql_hash


def _task_context_from_statements(
    work_item,
    statements,
    schema,
    diagnostics=None,
):
    diagnostics = diagnostics if diagnostics is not None else []
    referenced_tables = tuple(
        sorted(collect_statement_table_names(statements))
    )
    cte_names = tuple(sorted(collect_statement_cte_names(statements)))
    task_facts = extract_task_table_facts_from_statements(
        statements,
        work_item.source_file,
        default_catalog=_default_catalog(),
        default_db=_default_db(),
    )
    task_schema = _task_schema_for_table_names(schema, referenced_tables)
    if not work_item.sql_hash:
        work_item.sql_hash = _task_sql_hash(work_item)
    return _BINDINGS.runtime().ParsedTaskContext(
        work_item=work_item,
        statements=statements,
        task_facts=task_facts,
        referenced_tables=referenced_tables,
        cte_names=cte_names,
        task_schema=task_schema,
        missing_ddl_tables=[],
        missing_source_ddl=[],
        missing_target_ddl=[],
        diagnostics=diagnostics,
    )


def _parse_task_context(work_item, schema, diagnostics=None):
    statements = sqlglot.parse(
        _sqlglot_task_sql(work_item.sql_text), dialect="doris"
    )
    return _task_context_from_statements(
        work_item,
        statements,
        schema,
        diagnostics=diagnostics,
    )


def _task_fact_result_fields(task_facts):
    def sorted_tables(field):
        return sorted(
            task_facts.get(field) or [],
            key=_identifier_match_key,
        )

    return {
        "input_tables": sorted_tables("input_tables"),
        "output_tables": sorted_tables("output_tables"),
        "created_tables": sorted_tables("created_tables"),
        "temporary_tables": sorted_tables("temporary_tables"),
        "local_lifecycle_tables": task_facts.get("local_lifecycle_tables")
        or [],
    }


def _persistent_created_table_schemas(context):
    """Return schemas for CTAS/create outputs that survive this task."""
    output_keys = {
        _table_identity_match_key(table_name)
        for table_name in context.task_facts.get("output_tables") or []
    }
    records = {}
    for table_name in context.task_facts.get("created_tables") or []:
        table_key = _table_identity_match_key(table_name)
        if table_key not in output_keys:
            continue
        for catalog, database, table, columns in _iter_matching_schema_tables(
            context.task_schema,
            table_name,
        ):
            clean_columns = {
                _canonical_column(column_name): str(column_type or "UNKNOWN")
                for column_name, column_type in (columns or {}).items()
                if _canonical_column(column_name)
            }
            if not clean_columns:
                continue
            records[table_key] = {
                "name": _qualified_table_name(catalog, database, table),
                "columns": clean_columns,
            }
    return [records[key] for key in sorted(records)]


def _task_result_from_context(context, entries):
    result = {
        "index": context.index,
        "source_file": context.source_file,
        "entries": entries,
        "transient_tables": context.task_facts["transient_tables"],
        "missing_ddl_tables": context.missing_ddl_tables,
        "missing_source_ddl": context.missing_source_ddl,
        "missing_target_ddl": context.missing_target_ddl,
        "referenced_tables": list(context.referenced_tables),
        "sql_hash": context.sql_hash,
        "stats": dict(_runtime_stats()),
        "errors": context.diagnostics,
        "process_table_schemas": _persistent_created_table_schemas(context),
    }
    result.update(_task_fact_result_fields(context.task_facts))
    return result


def extract_lineage_from_statements(
    statements,
    file_path,
    schema,
    diagnostics=None,
):
    work_item = _BINDINGS.runtime().TaskWorkItem(
        index=-1,
        source_file=file_path,
        sql_text="",
    )
    context = _task_context_from_statements(
        work_item,
        statements,
        schema,
        diagnostics=diagnostics,
    )
    return extract_lineage_from_context(context)


def _add_context_missing_ddl(context, category, table_name):
    display_name = _strip_db(table_name)
    if not display_name:
        return
    missing_tables = getattr(context, category)
    if display_name not in missing_tables:
        missing_tables.append(display_name)
        missing_tables.sort()
    context.missing_ddl_tables = sorted(
        set(context.missing_source_ddl) | set(context.missing_target_ddl)
    )


def _record_statement_missing_ddl(context, stmt):
    for table_name in _statement_source_table_names(stmt):
        if not _schema_has_table(context.task_schema, table_name):
            _add_context_missing_ddl(
                context,
                "missing_source_ddl",
                table_name,
            )
    for table_name in _statement_existing_target_table_names(stmt):
        if not _schema_has_table(context.task_schema, table_name):
            _add_context_missing_ddl(
                context,
                "missing_target_ddl",
                table_name,
            )


def extract_lineage_from_context(context):
    entries = []
    for stmt in context.statements:
        if stmt is None:
            continue
        _record_statement_missing_ddl(context, stmt)
        if isinstance(stmt, exp.Insert):
            entries.extend(
                _handle_insert(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Update):
            entries.extend(
                _handle_update(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Create):
            entries.extend(
                _handle_create(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
            _register_task_table_schema(
                context.task_schema,
                _target_table_sql(stmt.this),
                _created_table_columns_from_schema(
                    stmt,
                    context.task_schema,
                    file_path=context.source_file,
                    diagnostics=None,
                ),
            )
        elif isinstance(stmt, exp.Alter):
            _apply_alter_table_to_task_schema(context.task_schema, stmt)
        elif _is_table_drop_statement(stmt):
            _drop_task_table_schema(
                context.task_schema,
                _target_table_sql(stmt.this),
            )
        elif isinstance(stmt, exp.Merge):
            entries.extend(
                _handle_merge(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
        elif isinstance(stmt, exp.Delete):
            entries.extend(_handle_delete(stmt, context.source_file))
        elif isinstance(stmt, exp.Select) and stmt.args.get("into"):
            entries.extend(
                _handle_select_into(
                    stmt,
                    context.source_file,
                    context.task_schema,
                    context.diagnostics,
                )
            )
    task_schema_lookup = _schema_lookup(context.task_schema)
    return [
        _canonical_lineage_entry(entry, task_schema_lookup)
        for entry in entries
    ]


def extract_lineage_from_sql(sql_text, file_path, schema, diagnostics=None):
    try:
        statements = sqlglot.parse(
            _sqlglot_task_sql(sql_text), dialect="doris"
        )
    except Exception as e:
        print(f"  解析失败 {file_path}: {e}")
        _record_diagnostic(diagnostics, file_path, "parse", e)
        _runtime_stats()["parse_failures"] += 1
        return []

    return extract_lineage_from_statements(
        statements,
        file_path,
        schema,
        diagnostics=diagnostics,
    )


def _extract_task_work_item(work_item, schema):
    stats = _runtime_stats()
    previous_stats = dict(stats)
    _reset_stats()
    try:
        diagnostics = []
        try:
            statements = sqlglot.parse(
                _sqlglot_task_sql(work_item.sql_text),
                dialect="doris",
            )
        except Exception as e:
            print(f"  解析失败 {work_item.source_file}: {e}")
            _record_diagnostic(diagnostics, work_item.source_file, "parse", e)
            stats["parse_failures"] += 1
            if not work_item.sql_hash:
                work_item.sql_hash = _task_sql_hash(work_item)
            task_facts = extract_task_table_facts(
                work_item.sql_text,
                work_item.source_file,
                default_catalog=_default_catalog(),
                default_db=_default_db(),
            )
            result = {
                "index": work_item.index,
                "source_file": work_item.source_file,
                "entries": [],
                "transient_tables": task_facts["transient_tables"],
                "missing_ddl_tables": [],
                "missing_source_ddl": [],
                "missing_target_ddl": [],
                "referenced_tables": [],
                "sql_hash": work_item.sql_hash,
                "stats": dict(stats),
                "errors": diagnostics,
                "process_table_schemas": [],
            }
            result.update(_task_fact_result_fields(task_facts))
            result["schema_slice_hash"] = _schema_slice_hash_for_tables(
                schema,
                result["referenced_tables"],
            )
            result["analysis_identity"] = dict(work_item.analysis_identity)
            return result

        context = _task_context_from_statements(
            work_item,
            statements,
            schema,
            diagnostics=diagnostics,
        )
        entries = extract_lineage_from_context(context)
        result = _task_result_from_context(context, entries)
        result["schema_slice_hash"] = _schema_slice_hash_for_tables(
            schema,
            result["referenced_tables"],
        )
        result["analysis_identity"] = dict(work_item.analysis_identity)
        return result
    finally:
        stats.update(previous_stats)


_PARALLEL_SCHEMA = None


def _init_parallel_worker(project_name, schema):
    global _PARALLEL_SCHEMA
    configure_project(project_name)
    _PARALLEL_SCHEMA = schema


def _extract_task_work_item_parallel(work_item):
    if _PARALLEL_SCHEMA is None:
        raise RuntimeError("parallel lineage worker schema is not initialized")
    return _extract_task_work_item(work_item, _PARALLEL_SCHEMA)


def _task_failure_result(work_item, error, stage="worker"):
    return {
        "index": work_item.index,
        "source_file": work_item.source_file,
        "entries": [],
        "transient_tables": [],
        "input_tables": [],
        "output_tables": [],
        "created_tables": [],
        "temporary_tables": [],
        "local_lifecycle_tables": [],
        "missing_ddl_tables": [],
        "missing_source_ddl": [],
        "missing_target_ddl": [],
        "referenced_tables": [],
        "stats": {},
        "errors": [
            {
                "source_file": work_item.source_file,
                "stage": stage,
                "severity": _diagnostic_severity(stage),
                "error": _diagnostic_error(error),
            }
        ],
        "process_table_schemas": [],
        "analysis_identity": dict(work_item.analysis_identity),
    }


def _read_task_work_items(
    task_files,
    tasks_dir,
    source_file_for_path=None,
    task_sql_resolver=None,
):
    work_items = []
    for index, task_file in enumerate(task_files):
        task_path = Path(task_file)
        if source_file_for_path:
            source_file = source_file_for_path(task_path)
        else:
            source_file = task_path.relative_to(tasks_dir).as_posix()
        resolved = task_sql_resolver(task_path) if task_sql_resolver else None
        sql_text = (
            resolved.sql
            if resolved is not None
            else task_path.read_text(
                encoding=_BINDINGS.runtime().TEXT_ENCODING
            )
        )
        analysis_identity = (
            dict(resolved.analysis_identity) if resolved is not None else {}
        )
        work_items.append(
            _BINDINGS.runtime().TaskWorkItem(
                index=index,
                source_file=source_file,
                sql_text=sql_text,
                analysis_identity=analysis_identity,
            )
        )
    return work_items


def _task_result_from_cache(work_item, cached):
    result = {
        "index": work_item.index,
        "source_file": work_item.source_file,
        "entries": cached.get("entries") or [],
        "transient_tables": cached.get("transient_tables") or [],
        "input_tables": cached.get("input_tables") or [],
        "output_tables": cached.get("output_tables") or [],
        "created_tables": cached.get("created_tables") or [],
        "temporary_tables": cached.get("temporary_tables") or [],
        "local_lifecycle_tables": cached.get("local_lifecycle_tables") or [],
        "missing_ddl_tables": cached.get("missing_ddl_tables") or [],
        "missing_source_ddl": cached.get("missing_source_ddl") or [],
        "missing_target_ddl": cached.get("missing_target_ddl") or [],
        "referenced_tables": cached.get("referenced_tables") or [],
        "stats": cached.get("stats") or {},
        "errors": cached.get("errors") or [],
        "process_table_schemas": cached.get("process_table_schemas") or [],
        "cache_hit": True,
    }
    for key in (
        "sql_hash",
        "schema_slice_hash",
        "extractor_hash",
        "project_config",
        "analysis_identity",
    ):
        if key in cached:
            result[key] = cached[key]
    return result


def _project_config_for_cache(project):
    runtime = _BINDINGS.runtime()
    return runtime.PROJECT_CONFIG.get(
        project,
        {
            "catalog": runtime.CURRENT_CATALOG,
            "db": runtime.CURRENT_DB,
        },
    )


def _cache_project_config(project):
    from dw_refactor_agent.lineage.task_cache import cache_project_config

    return cache_project_config(_project_config_for_cache(project))


def _extractor_hash_for_cache():
    from dw_refactor_agent.lineage.task_cache import extractor_version_hash

    return extractor_version_hash(
        (
            Path(__file__).with_name("lineage_extractor.py"),
            Path(__file__).with_name("lineage_schema.py"),
            Path(__file__).with_name("lineage_trace.py"),
            __file__,
            Path(__file__).with_name("lineage_projection.py"),
            Path(__file__).with_name("runtime_binding.py"),
            Path(__file__).with_name("sql_task_facts.py"),
            Path(__file__).parents[1] / "sql" / "task_analysis.py",
        )
    )


def _task_sql_hash(work_item):
    from dw_refactor_agent.lineage.task_cache import sha256_text

    return sha256_text(work_item.sql_text)


def _schema_slice_hash_for_tables(schema, referenced_tables):
    from dw_refactor_agent.lineage.task_cache import stable_json_hash

    if referenced_tables:
        return stable_json_hash(slice_schema(schema, referenced_tables))
    return stable_json_hash(_copy_schema(schema))


def _cache_can_seed_process_table_schemas(
    work_item,
    cached,
    project,
    extractor_hash,
):
    if not cached or "process_table_schemas" not in cached:
        return False
    sql_hash = work_item.sql_hash or _task_sql_hash(work_item)
    return (
        cached.get("sql_hash") == sql_hash
        and cached.get("extractor_hash") == extractor_hash
        and cached.get("project_config") == _cache_project_config(project)
        and cached.get("analysis_identity") == work_item.analysis_identity
    )


def _process_table_schema_catalog(task_results, schema=None):
    """Return schemas supplied by one unambiguous persistent creator."""
    formal_keys = {
        _schema_table_match_key(catalog, database, table)
        for catalog, database, table, _columns in _iter_schema_tables(schema)
    }
    consumers = {}
    for result in task_results or []:
        source_file = str(result.get("source_file") or "")
        for table_name in result.get("input_tables") or []:
            consumers.setdefault(
                _table_identity_match_key(table_name),
                set(),
            ).add(source_file)

    candidates = {}
    for result in task_results or []:
        source_file = str(result.get("source_file") or "")
        output_keys = {
            _table_identity_match_key(table_name)
            for table_name in result.get("output_tables") or []
        }
        for record in result.get("process_table_schemas") or []:
            table_name = record.get("name")
            columns = record.get("columns") or {}
            table_key = _table_identity_match_key(table_name)
            external_consumers = consumers.get(table_key, set()) - {
                source_file
            }
            if (
                not table_key[2]
                or table_key in formal_keys
                or table_key not in output_keys
                or not columns
                or not external_consumers
            ):
                continue
            candidates.setdefault(table_key, {})[source_file] = {
                "name": table_name,
                "columns": dict(columns),
            }

    catalog = []
    for table_key in sorted(candidates):
        by_source = candidates[table_key]
        if len(by_source) != 1:
            continue
        catalog.append(next(iter(by_source.values())))
    return catalog


def _schema_with_process_table_catalog(schema, catalog):
    if not catalog:
        return schema
    combined = _copy_schema(schema)
    formal_keys = {
        _schema_table_match_key(catalog_name, database, table)
        for catalog_name, database, table, _columns in _iter_schema_tables(
            schema
        )
    }
    for record in catalog or []:
        table_name = record.get("name")
        if _table_identity_match_key(table_name) in formal_keys:
            continue
        _register_task_table_schema(
            combined,
            table_name,
            record.get("columns") or {},
        )
    return combined


def _cache_key_from_cached_metadata(
    work_item,
    cached,
    schema,
    project,
    extractor_hash,
):
    required_keys = (
        "sql_hash",
        "referenced_tables",
        "schema_slice_hash",
        "extractor_hash",
        "project_config",
        "analysis_identity",
    )
    if not all(key in cached for key in required_keys):
        return None

    sql_hash = work_item.sql_hash or _task_sql_hash(work_item)
    if cached.get("sql_hash") != sql_hash:
        return None
    if cached.get("extractor_hash") != extractor_hash:
        return None
    if cached.get("project_config") != _cache_project_config(project):
        return None
    if cached.get("analysis_identity") != work_item.analysis_identity:
        return None

    referenced_tables = cached.get("referenced_tables") or []
    schema_slice_hash = _schema_slice_hash_for_tables(
        schema,
        referenced_tables,
    )
    if cached.get("schema_slice_hash") != schema_slice_hash:
        return None

    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    metadata = TaskCacheMetadata(
        sql_hash=sql_hash,
        referenced_tables=tuple(referenced_tables),
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
        analysis_identity=dict(work_item.analysis_identity),
    )
    return _task_cache_key_from_metadata(
        work_item,
        project,
        metadata,
    )


def _task_cache_metadata_from_context(
    context,
    schema,
    project,
    extractor_hash,
):
    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    schema_slice_hash = _schema_slice_hash_for_tables(
        schema,
        context.referenced_tables,
    )
    return TaskCacheMetadata(
        sql_hash=context.sql_hash,
        referenced_tables=context.referenced_tables,
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
        analysis_identity=dict(context.work_item.analysis_identity),
    )


def _task_cache_metadata_from_result(
    result,
    work_item,
    schema,
    project,
    extractor_hash,
):
    from dw_refactor_agent.lineage.task_cache import TaskCacheMetadata

    referenced_tables = tuple(sorted(result.get("referenced_tables") or []))
    sql_hash = (
        result.get("sql_hash")
        or work_item.sql_hash
        or _task_sql_hash(work_item)
    )
    schema_slice_hash = result.get("schema_slice_hash")
    if not schema_slice_hash:
        schema_slice_hash = _schema_slice_hash_for_tables(
            schema,
            referenced_tables,
        )
    return TaskCacheMetadata(
        sql_hash=sql_hash,
        referenced_tables=referenced_tables,
        schema_slice_hash=schema_slice_hash,
        extractor_hash=extractor_hash,
        project_config=_cache_project_config(project),
        analysis_identity=dict(work_item.analysis_identity),
    )


def _task_cache_key_from_metadata(work_item, project, metadata):
    from dw_refactor_agent.lineage.task_cache import task_cache_key

    return task_cache_key(
        project=project,
        source_file=work_item.source_file,
        metadata=metadata,
    )


def _result_with_cache_metadata(result, metadata):
    cached_result = dict(result)
    cached_result.update(
        {
            "sql_hash": metadata.sql_hash,
            "referenced_tables": list(metadata.referenced_tables),
            "schema_slice_hash": metadata.schema_slice_hash,
            "extractor_hash": metadata.extractor_hash,
            "project_config": metadata.project_config,
            "analysis_identity": metadata.analysis_identity,
        }
    )
    return cached_result


def _cache_metadata_for_result(
    result, work_item, schema, project, extractor_hash
):
    metadata = _task_cache_metadata_from_result(
        result,
        work_item,
        schema,
        project,
        extractor_hash,
    )
    cache_key = _task_cache_key_from_metadata(
        work_item,
        project,
        metadata,
    )
    return cache_key, _result_with_cache_metadata(result, metadata)


def _load_previous_task_cache(path):
    from dw_refactor_agent.lineage.task_cache import load_task_cache

    return load_task_cache(path)


def _build_task_cache(project, schema, task_cache_entries):
    from dw_refactor_agent.lineage.task_cache import (
        TASK_CACHE_FORMAT_VERSION,
        stable_json_hash,
    )

    return {
        "format_version": TASK_CACHE_FORMAT_VERSION,
        "project": project,
        "schema_hash": stable_json_hash(schema),
        "tasks": sorted(
            task_cache_entries,
            key=lambda item: item.get("source_file", ""),
        ),
    }


def _cache_entry_from_result(result, cache_key):
    from dw_refactor_agent.lineage.task_cache import cache_entry_from_result

    return cache_entry_from_result(result, cache_key)


def _notify_progress(progress_callback, completed, total, result):
    if progress_callback is not None:
        progress_callback(completed, total, result)


def _extract_task_work_items_serial(work_items, schema, progress_callback):
    task_results = []
    total = len(work_items)
    for completed, work_item in enumerate(work_items, start=1):
        try:
            result = _extract_task_work_item(work_item, schema)
        except Exception as exc:
            result = _task_failure_result(work_item, exc)
        task_results.append(result)
        _notify_progress(progress_callback, completed, total, result)
    return task_results


def _extract_task_work_items_parallel(
    work_items,
    schema,
    parallel,
    progress_callback,
):
    max_workers = min(parallel, len(work_items))
    try:
        runtime = _BINDINGS.runtime()
        with runtime.ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_parallel_worker,
            initargs=(runtime.CURRENT_PROJECT, schema),
        ) as executor:
            future_to_item = {
                executor.submit(_extract_task_work_item_parallel, work_item): (
                    work_item
                )
                for work_item in work_items
            }
            task_results = []
            total = len(work_items)
            for completed, future in enumerate(
                runtime.as_completed(future_to_item),
                start=1,
            ):
                work_item = future_to_item[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = _task_failure_result(work_item, exc)
                task_results.append(result)
                _notify_progress(
                    progress_callback,
                    completed,
                    total,
                    result,
                )
            return sorted(
                task_results,
                key=lambda result: result["index"],
            )
    except (NotImplementedError, OSError, PermissionError):
        return _extract_task_work_items_serial(
            work_items,
            schema,
            progress_callback,
        )


def _extract_task_work_items(
    work_items,
    schema,
    parallel,
    progress_callback=None,
):
    if len(work_items) <= 1 or parallel == 1:
        return _extract_task_work_items_serial(
            work_items,
            schema,
            progress_callback,
        )
    return _extract_task_work_items_parallel(
        work_items,
        schema,
        parallel,
        progress_callback,
    )


def _propagate_process_table_schemas(
    task_results,
    work_items_by_index,
    schema,
    parallel,
    initial_schema,
    initial_catalog,
):
    """Re-extract consumers until cross-Job process schemas reach a fixpoint."""
    results_by_index = {result["index"]: result for result in task_results}
    final_schema = schema
    max_rounds = len(work_items_by_index) + 1
    for _round in range(max_rounds):
        catalog = _process_table_schema_catalog(
            results_by_index.values(),
            schema=schema,
        )
        if _round == 0 and catalog == initial_catalog:
            return (
                [
                    results_by_index[index]
                    for index in sorted(results_by_index)
                ],
                initial_schema,
            )
        final_schema = _schema_with_process_table_catalog(schema, catalog)
        stale_items = []
        for index, result in sorted(results_by_index.items()):
            if "schema_slice_hash" not in result:
                continue
            expected_hash = _schema_slice_hash_for_tables(
                final_schema,
                result.get("referenced_tables") or [],
            )
            if result.get("schema_slice_hash") != expected_hash:
                stale_items.append(work_items_by_index[index])
        if not stale_items:
            return (
                [
                    results_by_index[index]
                    for index in sorted(results_by_index)
                ],
                final_schema,
            )

        refreshed = _extract_task_work_items(
            stale_items,
            final_schema,
            parallel,
        )
        for result in refreshed:
            results_by_index[result["index"]] = result

    raise RuntimeError(
        "cross-Job process table schema propagation did not converge"
    )


def extract_lineage_from_task_files(
    task_files,
    tasks_dir,
    schema,
    parallel=1,
    progress_callback=None,
    previous_cache_file=None,
    cache_project=None,
    source_file_for_path=None,
    task_sql_resolver=None,
):
    work_items = _read_task_work_items(
        task_files,
        tasks_dir,
        source_file_for_path=source_file_for_path,
        task_sql_resolver=task_sql_resolver,
    )
    parallel = max(1, int(parallel or 1))
    cache_enabled = previous_cache_file is not None
    cache_project = cache_project or _BINDINGS.runtime().CURRENT_PROJECT
    previous_cache = (
        _load_previous_task_cache(previous_cache_file) if cache_enabled else {}
    )
    extractor_hash = _extractor_hash_for_cache() if cache_enabled else None
    work_items_by_index = {item.index: item for item in work_items}

    cached_schema_seeds = []
    if cache_enabled:
        for work_item in work_items:
            work_item.sql_hash = _task_sql_hash(work_item)
            cached = previous_cache.get(work_item.source_file)
            if _cache_can_seed_process_table_schemas(
                work_item,
                cached,
                cache_project,
                extractor_hash,
            ):
                cached_schema_seeds.append(cached)
    initial_catalog = _process_table_schema_catalog(
        cached_schema_seeds,
        schema=schema,
    )
    extraction_schema = _schema_with_process_table_catalog(
        schema,
        initial_catalog,
    )

    total = len(work_items)
    completed = 0
    cached_results = []
    uncached_work_items = []
    for work_item in work_items:
        if not cache_enabled:
            uncached_work_items.append(work_item)
            continue
        cached = previous_cache.get(work_item.source_file)
        if cached:
            cache_key = _cache_key_from_cached_metadata(
                work_item,
                cached,
                extraction_schema,
                cache_project,
                extractor_hash,
            )
            work_item.cache_key = cache_key or ""

        if cached and cached.get("cache_key") == work_item.cache_key:
            result = _task_result_from_cache(work_item, cached)
            cached_results.append(result)
            completed += 1
            _notify_progress(progress_callback, completed, total, result)
        else:
            uncached_work_items.append(work_item)

    def notify_uncached_progress(_completed, _total, result):
        nonlocal completed
        completed += 1
        _notify_progress(progress_callback, completed, total, result)

    computed_results = _extract_task_work_items(
        uncached_work_items,
        extraction_schema,
        parallel,
        notify_uncached_progress,
    )
    task_results = sorted(
        [*cached_results, *computed_results],
        key=lambda result: result["index"],
    )
    task_results, extraction_schema = _propagate_process_table_schemas(
        task_results,
        work_items_by_index,
        schema,
        parallel,
        extraction_schema,
        initial_catalog,
    )

    task_cache_entries = []
    if cache_enabled:
        for result in task_results:
            work_item = work_items_by_index[result["index"]]
            cache_key, cache_result = _cache_metadata_for_result(
                result,
                work_item,
                extraction_schema,
                cache_project,
                extractor_hash,
            )
            task_cache_entries.append(
                _cache_entry_from_result(cache_result, cache_key)
            )

    all_lineage = []
    transient_tables = []
    missing_ddl_tables = set()
    missing_source_ddl = set()
    missing_target_ddl = set()
    errors = []
    for result in task_results:
        all_lineage.extend(result["entries"])
        transient_tables.extend(result["transient_tables"])
        missing_ddl_tables.update(result.get("missing_ddl_tables") or [])
        missing_source_ddl.update(result.get("missing_source_ddl") or [])
        missing_target_ddl.update(result.get("missing_target_ddl") or [])
        _add_stats(result["stats"])
        errors.extend(result.get("errors") or [])

    return {
        "lineage": all_lineage,
        "transient_tables": transient_tables,
        "missing_ddl_tables": sorted(missing_ddl_tables),
        "missing_source_ddl": sorted(missing_source_ddl),
        "missing_target_ddl": sorted(missing_target_ddl),
        "task_results": task_results,
        "task_cache": (
            _build_task_cache(
                cache_project,
                extraction_schema,
                task_cache_entries,
            )
            if cache_enabled
            else None
        ),
        "errors": errors,
    }


_EXPORTED_FUNCTIONS = (
    "_reset_stats",
    "_add_stats",
    "_task_context_from_statements",
    "_parse_task_context",
    "_task_fact_result_fields",
    "_persistent_created_table_schemas",
    "_task_result_from_context",
    "extract_lineage_from_statements",
    "_add_context_missing_ddl",
    "_record_statement_missing_ddl",
    "extract_lineage_from_context",
    "extract_lineage_from_sql",
    "_extract_task_work_item",
    "_init_parallel_worker",
    "_extract_task_work_item_parallel",
    "_task_failure_result",
    "_read_task_work_items",
    "_task_result_from_cache",
    "_project_config_for_cache",
    "_cache_project_config",
    "_extractor_hash_for_cache",
    "_task_sql_hash",
    "_schema_slice_hash_for_tables",
    "_cache_can_seed_process_table_schemas",
    "_process_table_schema_catalog",
    "_schema_with_process_table_catalog",
    "_cache_key_from_cached_metadata",
    "_task_cache_metadata_from_context",
    "_task_cache_metadata_from_result",
    "_task_cache_key_from_metadata",
    "_result_with_cache_metadata",
    "_cache_metadata_for_result",
    "_load_previous_task_cache",
    "_build_task_cache",
    "_cache_entry_from_result",
    "_notify_progress",
    "_extract_task_work_items_serial",
    "_extract_task_work_items_parallel",
    "_extract_task_work_items",
    "_propagate_process_table_schemas",
    "extract_lineage_from_task_files",
)
_BINDINGS.install(globals(), _EXPORTED_FUNCTIONS)


def install_facade(namespace):
    """Install compatibility exports on the extractor facade."""
    _BINDINGS.install_facade(namespace, _EXPORTED_FUNCTIONS)
