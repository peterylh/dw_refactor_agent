"""Lineage version 2 output assembly and CLI summaries.

SQL parsing stays in ``lineage_extractor``; this module owns conversion from
raw extraction entries to the validated, Job-aware output contract.
"""

from functools import lru_cache
from typing import Sequence

from dw_refactor_agent.lineage.contract import (
    FORMAT_VERSION,
    LineageContractError,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.job_lineage import (
    build_job_records,
    find_jobs_with_multiple_non_process_outputs,
    find_multiple_producer_datasets,
    resolve_job_dependencies,
)
from dw_refactor_agent.lineage.runtime_binding import RuntimeBindings

_BINDINGS = RuntimeBindings(
    __name__,
    "dw_refactor_agent.lineage.lineage_extractor",
)


def _delegate(name, *args, **kwargs):
    return getattr(_BINDINGS.runtime(), name)(*args, **kwargs)


def _canonical_column(*args, **kwargs):
    return _delegate("_canonical_column", *args, **kwargs)


def _canonical_lineage_entry(*args, **kwargs):
    return _delegate("_canonical_lineage_entry", *args, **kwargs)


def _column_source(*args, **kwargs):
    return _delegate("_column_source", *args, **kwargs)


def _column_target(*args, **kwargs):
    return _delegate("_column_target", *args, **kwargs)


def _display_table_name(*args, **kwargs):
    return _delegate("_display_table_name", *args, **kwargs)


def _expression_source(*args, **kwargs):
    return _delegate("_expression_source", *args, **kwargs)


def _identifier_match_key(*args, **kwargs):
    return _delegate("_identifier_match_key", *args, **kwargs)


def _literal_source(*args, **kwargs):
    return _delegate("_literal_source", *args, **kwargs)


def _qualified_table_name(*args, **kwargs):
    return _delegate("_qualified_table_name", *args, **kwargs)


def _relation_type_for_condition(*args, **kwargs):
    return _delegate("_relation_type_for_condition", *args, **kwargs)


def _schema_lookup(*args, **kwargs):
    return _delegate("_schema_lookup", *args, **kwargs)


def _source_sort_key(*args, **kwargs):
    return _delegate("_source_sort_key", *args, **kwargs)


def _strip_db(*args, **kwargs):
    return _delegate("_strip_db", *args, **kwargs)


def _table_identity(*args, **kwargs):
    return _delegate("_table_identity", *args, **kwargs)


def _table_identity_match_key(*args, **kwargs):
    return _delegate("_table_identity_match_key", *args, **kwargs)


def _table_target(*args, **kwargs):
    return _delegate("_table_target", *args, **kwargs)


def _target_sort_key(*args, **kwargs):
    return _delegate("_target_sort_key", *args, **kwargs)


def _transformation_type_for_expression(*args, **kwargs):
    return _delegate("_transformation_type_for_expression", *args, **kwargs)


def determine_layer(*args, **kwargs):
    return _delegate("determine_layer", *args, **kwargs)


def _source_file_match_key(source_file):
    return str(source_file or "").replace("\\", "/")


def _task_fact_table_names(values):
    names = []
    for value in values or []:
        name = value.get("name") if isinstance(value, dict) else value
        if name:
            names.append(str(name))
    return names


def _legacy_task_results(all_lineage, transient_tables=None):
    """Reconstruct explicit Job facts for legacy direct writer callers."""
    results_by_source = {}

    def result_for(source_file):
        source_key = _source_file_match_key(source_file)
        if not source_key:
            return None
        return results_by_source.setdefault(
            source_key,
            {
                "source_file": str(source_file),
                "input_tables": set(),
                "output_tables": set(),
                "created_tables": set(),
                "temporary_tables": set(),
                "local_lifecycle_tables": [],
            },
        )

    for entry in all_lineage or []:
        result = result_for(entry.get("source_file"))
        if result is None:
            continue
        source_table = entry.get("source_table")
        if source_table and source_table != "UNKNOWN":
            result["input_tables"].add(source_table)
        target_table = entry.get("target_table")
        if target_table:
            result["output_tables"].add(target_table)

    for table in transient_tables or []:
        result = result_for(table.get("source_file"))
        table_name = table.get("name")
        if result is None or not table_name:
            continue
        result["created_tables"].add(table_name)
        is_local = bool(
            table.get("is_temporary") or table.get("dropped_in_same_task")
        )
        if table.get("is_temporary"):
            result["temporary_tables"].add(table_name)
        if is_local:
            result["local_lifecycle_tables"].append(dict(table))
            local_table_key = _table_identity_match_key(table_name)
            result["output_tables"] = {
                output
                for output in result["output_tables"]
                if _table_identity_match_key(output) != local_table_key
            }

    return [results_by_source[key] for key in sorted(results_by_source)]


def _job_for_lineage_entry(entry, jobs_by_source_file):
    source_file = entry.get("source_file")
    source_key = _source_file_match_key(source_file)
    if source_key in jobs_by_source_file:
        return jobs_by_source_file[source_key]
    if source_key:
        message = f"cannot map edge source_file {source_file!r} to a Job"
    else:
        message = "cannot map edge without source_file to a Job"
    raise LineageContractError(f"lineage edge source_file: {message}")


def _normalize_producer_diagnostics(diagnostics, jobs, tables):
    jobs_by_name = {
        _identifier_match_key(job["name"]): job["name"] for job in jobs
    }
    jobs_by_source = {
        _source_file_match_key(job["source_file"]): job["name"] for job in jobs
    }
    tables_by_key = {
        _table_identity_match_key(table["full_name"]): table["full_name"]
        for table in tables
    }

    def job_name(value):
        text = str(value or "")
        return jobs_by_name.get(
            _identifier_match_key(text),
            jobs_by_source.get(_source_file_match_key(text), text),
        )

    def job_names(values):
        by_key = {}
        for value in values or []:
            name = job_name(value)
            by_key.setdefault(_identifier_match_key(name), name)
        return [by_key[key] for key in sorted(by_key)]

    normalized = []
    for diagnostic in diagnostics or []:
        dataset = str(diagnostic.get("dataset") or "")
        dataset = tables_by_key.get(
            _table_identity_match_key(dataset),
            _display_table_name(dataset),
        )
        normalized.append(
            {
                "code": diagnostic.get("code"),
                "dataset": dataset,
                "reason": diagnostic.get("reason"),
                "consumer_jobs": job_names(
                    diagnostic.get("consumer_jobs")
                    or diagnostic.get("consumer_source_files")
                ),
                "candidate_producer_jobs": job_names(
                    diagnostic.get("candidate_producer_jobs")
                    or diagnostic.get("candidate_producer_source_files")
                ),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (
            _table_identity_match_key(item["dataset"]),
            item["reason"] or "",
            tuple(_identifier_match_key(job) for job in item["consumer_jobs"]),
            tuple(
                _identifier_match_key(job)
                for job in item["candidate_producer_jobs"]
            ),
        ),
    )


def build_lineage_output(
    all_lineage,
    schema,
    *,
    task_results=None,
    diagnostics=None,
    transient_tables=None,
):
    """Build and validate one strict, Job-aware lineage version 2 artifact.

    ``transient_tables`` remains an input-only compatibility bridge for legacy
    direct callers. Version 2 output never serializes that global metadata.
    """
    schema_lookup = _schema_lookup(schema)
    all_lineage = [
        _canonical_lineage_entry(entry, schema_lookup) for entry in all_lineage
    ]

    @lru_cache(maxsize=None)
    def cached_identifier_match_key(value):
        return _identifier_match_key(value)

    @lru_cache(maxsize=None)
    def cached_table_identity_match_key(value):
        return _table_identity_match_key(value)

    @lru_cache(maxsize=None)
    def cached_display_table_name(value):
        return _display_table_name(value)

    @lru_cache(maxsize=None)
    def cached_short_table_name(value):
        return _strip_db(value)

    @lru_cache(maxsize=None)
    def cached_column_name(value):
        return _canonical_column(value)

    def _direct_source_type(entry):
        source_type = cached_identifier_match_key(
            entry.get("source_type") or "column"
        )
        if source_type in {"literal", "expression"}:
            return source_type
        return "column"

    def _literal_source_value_key(entry):
        value = entry.get("source_value", "")
        return type(value).__name__, repr(value)

    def _direct_transformation(entry):
        if entry.get("transformation_type"):
            return str(entry["transformation_type"])
        return _transformation_type_for_expression(entry.get("expression", ""))

    edge_table_displays = {}
    edge_column_displays = {}

    def remember_edge_ref(table_name, column_name=""):
        table_display = cached_short_table_name(table_name)
        if not table_display or table_display == "UNKNOWN":
            return
        table_key = cached_table_identity_match_key(table_display)
        edge_table_displays.setdefault(table_key, table_display)
        column_display = cached_column_name(column_name)
        if column_display:
            column_key = cached_identifier_match_key(column_display)
            edge_column_displays.setdefault(
                (table_key, column_key),
                (table_display, column_display),
            )

    for entry in all_lineage:
        source_type = _direct_source_type(entry)
        if source_type == "column":
            remember_edge_ref(
                entry.get("source_table", ""),
                entry.get("source_column", ""),
            )
        remember_edge_ref(
            entry.get("target_table", ""),
            entry.get("target_column", ""),
        )

    if task_results is None:
        task_results = _legacy_task_results(
            all_lineage,
            transient_tables=transient_tables,
        )
    else:
        task_results = list(task_results)
    jobs = build_job_records(task_results, cached_display_table_name)
    jobs_by_source_file = {
        _source_file_match_key(job["source_file"]): job["name"] for job in jobs
    }

    def entry_job_key(entry):
        return cached_identifier_match_key(
            _job_for_lineage_entry(entry, jobs_by_source_file)
        )

    def direct_source_key(entry):
        source_type = _direct_source_type(entry)
        if source_type == "literal":
            return (source_type, *_literal_source_value_key(entry))
        if source_type == "expression":
            return (source_type, entry.get("source_expression", ""))
        return (
            source_type,
            cached_table_identity_match_key(entry.get("source_table", "")),
            cached_identifier_match_key(entry.get("source_column", "")),
        )

    def direct_semantic_key(entry):
        return (
            "direct",
            entry_job_key(entry),
            direct_source_key(entry),
            cached_table_identity_match_key(entry.get("target_table", "")),
            cached_identifier_match_key(entry.get("target_column", "")),
            _direct_transformation(entry),
            entry.get("expression", ""),
        )

    unique = []
    seen = set()
    for e in all_lineage:
        is_indirect = e.get("lineage_type") == "indirect"
        if is_indirect:
            key = (
                "indirect",
                entry_job_key(e),
                cached_table_identity_match_key(e.get("source_table", "")),
                cached_identifier_match_key(e.get("source_column", "")),
                cached_table_identity_match_key(e.get("target_table", "")),
                _relation_type_for_condition(e.get("condition_type", "")),
                e.get("condition_expression", ""),
            )
        else:
            key = direct_semantic_key(e)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    all_lineage = sorted(
        unique,
        key=lambda e: (
            e.get("source_file", ""),
            e.get("lineage_type", "direct"),
            e.get("source_type", ""),
            e.get("source_table", ""),
            e.get("source_column", ""),
            _literal_source_value_key(e),
            e.get("source_expression", ""),
            e.get("target_table", ""),
            e.get("target_column", ""),
            e.get("condition_type", ""),
            e.get("condition_expression", ""),
            e.get("expression", ""),
        ),
    )
    # Avoid retaining large build-only indexes through edge serialization and
    # strict contract validation, where peak memory is otherwise highest.
    del seen, unique

    direct_entries = [
        e for e in all_lineage if e.get("lineage_type") != "indirect"
    ]
    indirect_entries = [
        e for e in all_lineage if e.get("lineage_type") == "indirect"
    ]

    tables = {}
    edges = []

    schema_columns_by_table = schema_lookup.schema_columns_by_table
    schema_type_by_table_col = schema_lookup.schema_type_by_table_col

    column_names_by_table = {}
    column_objects_by_table = {}

    def _schema_column_type(tbl, col):
        tbl = cached_short_table_name(tbl)
        col = cached_column_name(col)
        return schema_type_by_table_col.get((tbl, col), "UNKNOWN")

    @lru_cache(maxsize=None)
    def _table_storage_key(tbl):
        return cached_table_identity_match_key(cached_display_table_name(tbl))

    managed_table_keys = {
        _table_storage_key(table_name)
        for table_name in schema_columns_by_table
    }
    process_table_keys = set()
    temporary_table_keys = set()
    table_names_by_key = {}

    def _remember_table_name(table_name):
        displayed = cached_display_table_name(table_name)
        if not displayed:
            return None
        table_key = cached_table_identity_match_key(displayed)
        table_names_by_key.setdefault(table_key, displayed)
        return table_key

    for task_result in task_results:
        task_temporary_keys = {
            key
            for key in (
                _remember_table_name(table_name)
                for table_name in _task_fact_table_names(
                    task_result.get("temporary_tables")
                )
            )
            if key is not None
        }
        temporary_table_keys.update(task_temporary_keys)
        for fact_field in (
            "input_tables",
            "output_tables",
            "created_tables",
        ):
            for table_name in _task_fact_table_names(
                task_result.get(fact_field)
            ):
                table_key = _remember_table_name(table_name)
                if table_key is None:
                    continue
                if fact_field == "output_tables" or (
                    fact_field == "created_tables"
                    and table_key not in task_temporary_keys
                ):
                    process_table_keys.add(table_key)
        for table_name in _task_fact_table_names(
            task_result.get("local_lifecycle_tables")
        ):
            _remember_table_name(table_name)

    for entry in all_lineage:
        source_table = entry.get("source_table")
        if source_table and source_table != "UNKNOWN":
            _remember_table_name(source_table)
        target_key = _remember_table_name(entry.get("target_table"))
        if target_key is not None and target_key not in temporary_table_keys:
            process_table_keys.add(target_key)
    table_keys_by_short_name = {}
    table_keys_by_database_name = {}
    for table_key in table_names_by_key:
        table_keys_by_short_name.setdefault(table_key[2], set()).add(table_key)
        table_keys_by_database_name.setdefault(table_key[1:], set()).add(
            table_key
        )

    def _unique_table_reference(table_name, preferred_reference):
        table_key = _table_storage_key(table_name)
        if len(table_keys_by_short_name[table_key[2]]) == 1:
            return preferred_reference
        if len(table_keys_by_database_name[table_key[1:]]) == 1:
            return cached_display_table_name(table_name)
        catalog, database, name = _table_identity(table_name)
        return _qualified_table_name(catalog, database, name)

    for job in jobs:
        for io_field in ("inputs", "outputs"):
            references_by_key = {
                _table_storage_key(table_name): _unique_table_reference(
                    table_name,
                    cached_display_table_name(table_name),
                )
                for table_name in job[io_field]
            }
            job[io_field] = [
                references_by_key[key] for key in sorted(references_by_key)
            ]
    del all_lineage, task_results

    def _dataset_type(tbl):
        table_key = _table_storage_key(tbl)
        if table_key in managed_table_keys:
            return "managed"
        if table_key in process_table_keys:
            return "process"
        if table_key in temporary_table_keys:
            return "temporary"
        return "external"

    def _ensure_column_index(tbl):
        table_key = _table_storage_key(tbl)
        if table_key not in column_objects_by_table:
            column_objects_by_table[table_key] = {
                cached_identifier_match_key(c["name"]): c
                for c in tables[table_key]["columns"]
            }
            column_names_by_table[table_key] = set(
                column_objects_by_table[table_key]
            )
        return (
            column_names_by_table[table_key],
            column_objects_by_table[table_key],
        )

    def _ensure_table(tbl):
        tbl = cached_short_table_name(tbl)
        if not tbl:
            return
        table_key = _table_storage_key(tbl)
        if table_key not in tables:
            tables[table_key] = {
                "name": tbl,
                "full_name": cached_display_table_name(tbl),
                "dataset_type": _dataset_type(tbl),
                "columns": [],
            }
            column_names_by_table[table_key] = set()
            column_objects_by_table[table_key] = {}

    def _ensure_column(tbl, col):
        tbl = cached_short_table_name(tbl)
        col = cached_column_name(col)
        if not tbl or not col:
            return
        _ensure_table(tbl)
        column_names, column_objects = _ensure_column_index(tbl)
        column_key = cached_identifier_match_key(col)
        if column_key not in column_names:
            column = {"name": col, "type": _schema_column_type(tbl, col)}
            tables[_table_storage_key(tbl)]["columns"].append(column)
            column_names.add(column_key)
            column_objects[column_key] = column

    def _stored_table_reference(tbl):
        table_key = _table_storage_key(tbl)
        table = tables[table_key]
        return _unique_table_reference(tbl, table["name"])

    def _stored_column_name(tbl, col):
        return column_objects_by_table[_table_storage_key(tbl)][
            cached_identifier_match_key(col)
        ]["name"]

    for table_display in edge_table_displays.values():
        _ensure_table(table_display)
    for table_display, column_display in edge_column_displays.values():
        _ensure_column(table_display, column_display)

    def _direct_source(entry, source_table="", source_column=""):
        source_type = _direct_source_type(entry)
        if source_type == "literal":
            return _literal_source(entry.get("source_value", ""))
        if source_type == "expression":
            return _expression_source(entry.get("source_expression", ""))
        return _column_source(source_table, source_column)

    for entry in direct_entries:
        tgt_tbl = cached_short_table_name(entry.get("target_table", ""))
        tgt_col = cached_column_name(entry.get("target_column", ""))
        source_type = _direct_source_type(entry)
        displayed_src_tbl = ""
        displayed_src_col = ""
        if source_type == "column":
            src_tbl = cached_short_table_name(entry.get("source_table", ""))
            src_col = cached_column_name(entry.get("source_column", ""))
            if src_tbl == "UNKNOWN":
                continue
            _ensure_column(src_tbl, src_col)
            displayed_src_tbl = _stored_table_reference(src_tbl)
            displayed_src_col = _stored_column_name(src_tbl, src_col)
        if not tgt_tbl or not tgt_col:
            continue
        _ensure_column(tgt_tbl, tgt_col)
        displayed_tgt_tbl = _stored_table_reference(tgt_tbl)
        displayed_tgt_col = _stored_column_name(tgt_tbl, tgt_col)
        edges.append(
            {
                "source": _direct_source(
                    entry,
                    displayed_src_tbl,
                    displayed_src_col,
                ),
                "target": _column_target(
                    displayed_tgt_tbl,
                    displayed_tgt_col,
                ),
                "relation_type": "direct",
                "transformation_type": _direct_transformation(entry),
                "expression": entry.get("expression", ""),
                "job": _job_for_lineage_entry(
                    entry,
                    jobs_by_source_file,
                ),
            }
        )

    for entry in indirect_entries:
        src_tbl = cached_short_table_name(entry.get("source_table", ""))
        src_col = cached_column_name(entry.get("source_column", ""))
        tgt_tbl = cached_short_table_name(entry.get("target_table", ""))
        if src_tbl == "UNKNOWN":
            continue
        _ensure_column(src_tbl, src_col)
        _ensure_table(tgt_tbl)
        displayed_src_tbl = _stored_table_reference(src_tbl)
        displayed_src_col = _stored_column_name(src_tbl, src_col)
        displayed_tgt_tbl = _stored_table_reference(tgt_tbl)
        relation_type = _relation_type_for_condition(
            entry.get("condition_type", "")
        )
        edges.append(
            {
                "source": _column_source(
                    displayed_src_tbl,
                    displayed_src_col,
                ),
                "target": _table_target(displayed_tgt_tbl),
                "relation_type": relation_type,
                "transformation_type": relation_type,
                "expression": entry.get("condition_expression", ""),
                "job": _job_for_lineage_entry(
                    entry,
                    jobs_by_source_file,
                ),
            }
        )
    del direct_entries, indirect_entries

    for table_name in table_names_by_key.values():
        _ensure_table(table_name)

    for job in jobs:
        for table_name in (*job["inputs"], *job["outputs"]):
            _ensure_table(table_name)

    for tbl_name, cols in schema_columns_by_table.items():
        if _table_storage_key(tbl_name) in tables:
            column_names, column_objects = _ensure_column_index(tbl_name)
            for col_name, col_type in cols:
                column_key = cached_identifier_match_key(col_name)
                if column_key not in column_names:
                    column = {"name": col_name, "type": col_type}
                    tables[_table_storage_key(tbl_name)]["columns"].append(
                        column
                    )
                    column_names.add(column_key)
                    column_objects[column_key] = column
                elif column_objects[column_key].get("type") == "UNKNOWN":
                    column_objects[column_key]["type"] = col_type

    serialized_tables = sorted(
        tables.values(),
        key=lambda table: cached_table_identity_match_key(table["full_name"]),
    )
    for table in serialized_tables:
        table["columns"].sort(
            key=lambda column: cached_identifier_match_key(column["name"])
        )

    if diagnostics is None:
        _dependencies, diagnostics = resolve_job_dependencies(
            jobs,
            serialized_tables,
        )
    public_diagnostics = _normalize_producer_diagnostics(
        diagnostics,
        jobs,
        serialized_tables,
    )
    output = {
        "format_version": FORMAT_VERSION,
        "tables": serialized_tables,
        "jobs": jobs,
        "edges": sorted(
            edges,
            key=lambda e: (
                cached_identifier_match_key(e["job"]),
                e.get("relation_type", ""),
                _target_sort_key(e.get("target")),
                _source_sort_key(e.get("source")),
                e.get("expression", ""),
            ),
        ),
        "diagnostics": public_diagnostics,
    }
    validate_lineage_v2(output)
    return output


def format_lineage_output_statistics(output):
    """Return structural and version 2 dataset counts for CLI output."""
    edges = output.get("edges") or []
    tables = output.get("tables") or []
    jobs = output.get("jobs") or []
    multiple_producer_count = len(find_multiple_producer_datasets(jobs))
    multiple_non_process_output_count = len(
        find_jobs_with_multiple_non_process_outputs(jobs, tables)
    )
    other_producer_diagnostic_count = sum(
        1
        for diagnostic in output.get("diagnostics") or []
        if diagnostic.get("reason") != "multiple_candidates"
    )
    producer_warning_count = (
        multiple_producer_count + other_producer_diagnostic_count
    )
    direct_count = sum(
        1 for edge in edges if edge.get("relation_type") == "direct"
    )
    dataset_types = ("managed", "process", "temporary", "external")
    dataset_counts = {
        dataset_type: sum(
            1 for table in tables if table.get("dataset_type") == dataset_type
        )
        for dataset_type in dataset_types
    }
    return [
        f"  直接血缘: {direct_count} 条边",
        f"  间接血缘: {len(edges) - direct_count} 条边",
        "  节点数: "
        f"{sum(len(table.get('columns') or []) for table in tables)}",
        f"  表数: {len(tables)}",
        "  数据集类型: "
        + ", ".join(
            f"{dataset_type}={dataset_counts[dataset_type]}"
            for dataset_type in dataset_types
        ),
        f"  生产者警告: {producer_warning_count}",
        f"  多输出作业警告: {multiple_non_process_output_count}",
    ]


def warn_multiple_producer_datasets(jobs: Sequence[dict]) -> None:
    """Log one warning for every dataset written by multiple Jobs."""
    for warning in find_multiple_producer_datasets(jobs):
        _BINDINGS.runtime().LOGGER.warning(
            "数据集 %s 由多个作业生产: %s",
            warning["dataset"],
            ", ".join(warning["producer_jobs"]),
        )


def warn_jobs_with_multiple_non_process_outputs(
    jobs: Sequence[dict],
    tables: Sequence[dict],
) -> None:
    """Log Jobs writing multiple non-temporary, non-process datasets."""
    for warning in find_jobs_with_multiple_non_process_outputs(jobs, tables):
        _BINDINGS.runtime().LOGGER.warning(
            "作业 %s 写入多个非临时、非过程数据集: %s",
            warning["job"],
            ", ".join(warning["output_datasets"]),
        )


def format_layer_statistics(tables):
    """Return compact layer-level table and column counts for CLI output."""
    ordered_layers = ("ODS", "DWD", "DWS", "DIM", "ADS")
    stats = {
        layer: {"tables": 0, "columns": 0}
        for layer in (*ordered_layers, "OTHER")
    }

    for table in tables or []:
        layer = determine_layer(table.get("name") or "")
        if layer not in stats:
            layer = "OTHER"
        stats[layer]["tables"] += 1
        stats[layer]["columns"] += len(table.get("columns") or [])

    lines = ["分层统计:"]
    for layer in ordered_layers:
        layer_stats = stats[layer]
        lines.append(
            f"  {layer}: {layer_stats['tables']} 个表, "
            f"{layer_stats['columns']} 个字段"
        )
    if stats["OTHER"]["tables"]:
        other_stats = stats["OTHER"]
        lines.append(
            f"  OTHER: {other_stats['tables']} 个表, "
            f"{other_stats['columns']} 个字段"
        )
    return lines


_EXPORTED_FUNCTIONS = (
    "_source_file_match_key",
    "_task_fact_table_names",
    "_legacy_task_results",
    "_job_for_lineage_entry",
    "_normalize_producer_diagnostics",
    "build_lineage_output",
    "format_lineage_output_statistics",
    "warn_multiple_producer_datasets",
    "warn_jobs_with_multiple_non_process_outputs",
    "format_layer_statistics",
)
_BINDINGS.install(globals(), _EXPORTED_FUNCTIONS)


def call(name, runtime, *args, **kwargs):
    """Call one output helper through an explicit facade."""
    return _BINDINGS.call(name, runtime, *args, **kwargs)


def preserve_facade_metadata(namespace):
    """Restore output signatures and docs on extractor wrappers."""
    _BINDINGS.preserve_metadata(namespace, _EXPORTED_FUNCTIONS)


def install_facade(namespace):
    """Install output compatibility exports on the extractor facade."""
    _BINDINGS.install_facade(namespace, _EXPORTED_FUNCTIONS)
