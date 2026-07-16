"""Job records and canonical dataset-producer resolution."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Callable, Sequence

from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    identifier_match_key,
    table_identity_match_key,
)


def job_name_from_source_file(source_file: str) -> str:
    """Return a stable Job name from a task SQL source path."""
    normalized = str(source_file or "").replace("\\", "/")
    return PurePosixPath(normalized).stem


def _fact_names(values) -> set:
    names = set()
    for value in values or []:
        name = value.get("name") if isinstance(value, dict) else value
        if name:
            names.add(str(name))
    return names


def _table_key(table_name: str) -> tuple:
    return table_identity_match_key(table_name)


def _table_reference_parts(table_name: str) -> tuple[str, ...]:
    return tuple(
        identifier_match_key(part)
        for part in canonical_qualified_identifier(table_name).split(".")
        if part
    )


def _dataset_reference_indexes(
    tables: Sequence[dict],
) -> tuple[dict, dict, dict]:
    dataset_types_by_key = {}
    keys_by_database_table = defaultdict(set)
    keys_by_table = defaultdict(set)
    for table in tables or []:
        full_name = table.get("full_name")
        if not full_name:
            continue
        dataset_key = _table_key(full_name)
        dataset_types_by_key.setdefault(
            dataset_key,
            table.get("dataset_type"),
        )
        keys_by_database_table[dataset_key[1:]].add(dataset_key)
        keys_by_table[dataset_key[2]].add(dataset_key)
    return (
        dataset_types_by_key,
        keys_by_database_table,
        keys_by_table,
    )


def _resolve_dataset_type(
    table_reference: str,
    dataset_types_by_key: dict,
    keys_by_database_table: dict,
    keys_by_table: dict,
) -> str | None:
    parts = _table_reference_parts(table_reference)
    if len(parts) == 1:
        candidates = keys_by_table.get(parts[0], set())
    elif len(parts) == 2:
        candidates = keys_by_database_table.get(parts, set())
    elif len(parts) == 3 and parts in dataset_types_by_key:
        candidates = {parts}
    else:
        candidates = set()
    if len(candidates) != 1:
        return None
    return dataset_types_by_key[next(iter(candidates))]


def _sorted_display_tables(values, display_table: Callable[[str], str]):
    by_key = {}
    for value in values or []:
        displayed = display_table(value)
        if displayed:
            by_key.setdefault(_table_key(displayed), displayed)
    return [by_key[key] for key in sorted(by_key)]


def build_job_records(
    task_results: Sequence[dict],
    display_table: Callable[[str], str],
) -> list[dict]:
    """Build public Job records from task-level SQL facts."""
    jobs = []
    job_names = set()
    for task_result in task_results:
        source_file = str(task_result.get("source_file") or "")
        name = job_name_from_source_file(source_file)
        name_key = identifier_match_key(name)
        if name_key in job_names:
            raise ValueError(
                f"duplicate Job name derived from source files: {name}"
            )
        job_names.add(name_key)

        local_names = _fact_names(task_result.get("temporary_tables"))
        local_names.update(
            _fact_names(task_result.get("local_lifecycle_tables"))
        )
        local_keys = {
            _table_key(display_table(table_name)) for table_name in local_names
        }
        persistent_output_keys = {
            _table_key(display_table(table_name))
            for table_name in task_result.get("output_tables") or []
        }
        inputs = [
            table_name
            for table_name in task_result.get("input_tables") or []
            if _table_key(display_table(table_name)) not in local_keys
            or _table_key(display_table(table_name)) in persistent_output_keys
        ]
        jobs.append(
            {
                "name": name,
                "source_file": source_file,
                "inputs": _sorted_display_tables(inputs, display_table),
                "outputs": _sorted_display_tables(
                    task_result.get("output_tables") or [],
                    display_table,
                ),
            }
        )
    return sorted(
        jobs,
        key=lambda job: (
            identifier_match_key(job["name"]),
            job["source_file"],
        ),
    )


def _producer_index(jobs: Sequence[dict]) -> tuple[dict, dict]:
    producers_by_key = defaultdict(set)
    display_by_key = {}
    for job in jobs or []:
        job_name = str(job.get("name") or "")
        if not job_name:
            continue
        for output in job.get("outputs") or []:
            dataset = str(output or "")
            if not dataset:
                continue
            dataset_key = _table_key(dataset)
            producers_by_key[dataset_key].add(job_name)
            display_by_key.setdefault(dataset_key, dataset)
    return producers_by_key, display_by_key


def find_multiple_producer_datasets(jobs: Sequence[dict]) -> list[dict]:
    """Return datasets written by more than one explicit Job."""
    producers_by_key, display_by_key = _producer_index(jobs)
    warnings = []
    for dataset_key in sorted(producers_by_key):
        producer_jobs = sorted(
            producers_by_key[dataset_key],
            key=identifier_match_key,
        )
        if len(producer_jobs) <= 1:
            continue
        warnings.append(
            {
                "dataset": display_by_key[dataset_key],
                "producer_jobs": producer_jobs,
            }
        )
    return warnings


def find_jobs_with_multiple_non_process_outputs(
    jobs: Sequence[dict],
    tables: Sequence[dict],
) -> list[dict]:
    """Return Jobs writing multiple managed or external datasets."""
    (
        dataset_types_by_key,
        keys_by_database_table,
        keys_by_table,
    ) = _dataset_reference_indexes(tables)
    warnings = []
    for job in jobs or []:
        outputs_by_key = {}
        for output in job.get("outputs") or []:
            dataset = str(output or "")
            if not dataset:
                continue
            dataset_key = _table_key(dataset)
            dataset_type = _resolve_dataset_type(
                dataset,
                dataset_types_by_key,
                keys_by_database_table,
                keys_by_table,
            )
            if dataset_type not in {
                "managed",
                "external",
            }:
                continue
            outputs_by_key.setdefault(dataset_key, dataset)
        if len(outputs_by_key) <= 1:
            continue
        warnings.append(
            {
                "job": str(job.get("name") or ""),
                "output_datasets": [
                    outputs_by_key[key] for key in sorted(outputs_by_key)
                ],
            }
        )
    return sorted(
        warnings,
        key=lambda warning: identifier_match_key(warning["job"]),
    )


def resolve_job_dependencies(
    jobs: Sequence[dict],
    tables: Sequence[dict],
) -> tuple[list[dict], list[dict]]:
    """Resolve unique external producers for each Job input dataset."""
    table_by_key = {}
    for table in sorted(
        tables or [],
        key=lambda item: identifier_match_key(item.get("full_name")),
    ):
        full_name = table.get("full_name")
        if full_name:
            table_by_key.setdefault(_table_key(full_name), table)

    producers_by_key, _ = _producer_index(jobs)

    dependency_datasets = defaultdict(dict)
    unresolved_consumers = defaultdict(set)
    for consumer in jobs or []:
        consumer_name = consumer["name"]
        local_output_keys = {
            _table_key(output) for output in consumer.get("outputs") or []
        }
        seen_inputs = set()
        for input_table in consumer.get("inputs") or []:
            table_key = _table_key(input_table)
            if table_key in seen_inputs or table_key in local_output_keys:
                continue
            seen_inputs.add(table_key)

            table = table_by_key.get(table_key, {})
            dataset_type = table.get("dataset_type")
            dataset = table.get("full_name") or input_table
            candidates = sorted(
                producers_by_key.get(table_key, set()) - {consumer_name},
                key=identifier_match_key,
            )
            if dataset_type == "temporary":
                candidates = []

            if len(candidates) == 1:
                pair = (candidates[0], consumer_name)
                dependency_datasets[pair].setdefault(table_key, dataset)
                continue
            if dataset_type not in {"process", "temporary"}:
                continue

            reason = "not_found" if not candidates else "multiple_candidates"
            diagnostic_key = (table_key, dataset, reason, tuple(candidates))
            unresolved_consumers[diagnostic_key].add(consumer_name)

    dependencies = []
    for (upstream_job, downstream_job), datasets in sorted(
        dependency_datasets.items(),
        key=lambda item: (
            identifier_match_key(item[0][0]),
            identifier_match_key(item[0][1]),
        ),
    ):
        dependencies.append(
            {
                "upstream_job": upstream_job,
                "downstream_job": downstream_job,
                "datasets": [datasets[key] for key in sorted(datasets)],
            }
        )

    diagnostics = []
    for diagnostic_key, consumers in sorted(
        unresolved_consumers.items(),
        key=lambda item: (
            item[0][0],
            item[0][2],
            item[0][3],
        ),
    ):
        _table_key_value, dataset, reason, candidates = diagnostic_key
        diagnostics.append(
            {
                "code": "UNRESOLVED_DATASET_PRODUCER",
                "dataset": dataset,
                "reason": reason,
                "consumer_jobs": sorted(consumers, key=identifier_match_key),
                "candidate_producer_jobs": list(candidates),
            }
        )
    return dependencies, diagnostics
