"""Infer schedule candidates from lineage and validate trusted schedules."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Collection

from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
)
from dw_refactor_agent.lineage.contract import validate_lineage_v2
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    table_identity_match_key,
)


def _diagnostic(code: str, severity: str, message: str, **details) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        **details,
    }


def writers_by_table(lineage_data: dict) -> dict[tuple, list[str]]:
    """Return canonical table identity to lineage Job writers."""
    writers = defaultdict(set)
    for job in lineage_data.get("jobs") or []:
        job_name = str(job.get("name") or "")
        if not job_name:
            continue
        for output in job.get("outputs") or []:
            writers[table_identity_match_key(output)].add(job_name)
    return {
        key: sorted(values, key=identifier_match_key)
        for key, values in writers.items()
    }


def infer_schedule_candidate(
    lineage_data: dict,
    project: str,
    *,
    runnable_jobs: Collection[str] | None = None,
) -> tuple[ScheduleGraph, list[dict], list[dict]]:
    """Build a reviewable Job DAG candidate from current lineage facts.

    Returns ``(candidate, diagnostics, dependency_evidence)``. Multiple
    writers never create writer-to-writer edges. Every writer is placed before
    a consumer of the shared dataset in the candidate, and the ambiguity is
    explicitly reported for review.
    """
    validate_lineage_v2(lineage_data)
    lineage_jobs = {
        identifier_match_key(job["name"]): job
        for job in lineage_data.get("jobs") or []
    }
    if runnable_jobs is None:
        job_names = [job["name"] for job in lineage_data.get("jobs") or []]
    else:
        job_names = sorted(set(runnable_jobs), key=identifier_match_key)
        missing = [
            job
            for job in job_names
            if identifier_match_key(job) not in lineage_jobs
        ]
        if missing:
            raise ScheduleContractError(
                f"runnable Jobs missing from lineage: {missing!r}"
            )
    allowed_keys = {identifier_match_key(job) for job in job_names}
    jobs = [lineage_jobs[key] for key in sorted(allowed_keys)]

    table_types = {
        table_identity_match_key(table.get("full_name")): str(
            table.get("dataset_type") or ""
        )
        for table in lineage_data.get("tables") or []
        if table.get("full_name")
    }
    display_tables = {
        table_identity_match_key(table.get("full_name")): table.get(
            "full_name"
        )
        for table in lineage_data.get("tables") or []
        if table.get("full_name")
    }
    writers = writers_by_table({**lineage_data, "jobs": jobs})
    dependency_datasets = defaultdict(dict)
    dependency_is_multiwriter = defaultdict(bool)
    diagnostics = []

    for table_key, producer_jobs in sorted(writers.items()):
        if len(producer_jobs) > 1:
            diagnostics.append(
                _diagnostic(
                    "MULTIPLE_WRITERS",
                    "WARNING",
                    "lineage found multiple Jobs writing one dataset; no "
                    "writer-to-writer order was inferred",
                    dataset=display_tables.get(table_key)
                    or ".".join(table_key),
                    writer_jobs=producer_jobs,
                )
            )

    for consumer in jobs:
        consumer_name = consumer["name"]
        output_keys = {
            table_identity_match_key(output)
            for output in consumer.get("outputs") or []
        }
        seen = set()
        for input_table in consumer.get("inputs") or []:
            table_key = table_identity_match_key(input_table)
            if table_key in seen or table_key in output_keys:
                continue
            seen.add(table_key)
            dataset_type = table_types.get(table_key)
            dataset = display_tables.get(table_key) or input_table
            producers = [
                producer
                for producer in writers.get(table_key, [])
                if identifier_match_key(producer)
                != identifier_match_key(consumer_name)
            ]
            if dataset_type == "temporary" and producers:
                diagnostics.append(
                    _diagnostic(
                        "TEMPORARY_CROSS_JOB_DEPENDENCY",
                        "ERROR",
                        "temporary datasets cannot cross Job sessions",
                        dataset=dataset,
                        consumer_job=consumer_name,
                        producer_jobs=producers,
                    )
                )
                continue
            for producer in producers:
                pair = (producer, consumer_name)
                dependency_datasets[pair][table_key] = dataset
                if len(producers) > 1:
                    dependency_is_multiwriter[pair] = True

    for raw in lineage_data.get("diagnostics") or []:
        if raw.get("code") != "UNRESOLVED_DATASET_PRODUCER":
            continue
        table_key = table_identity_match_key(raw.get("dataset"))
        dataset_type = table_types.get(table_key)
        if dataset_type not in {"process", "temporary"}:
            continue
        diagnostics.append(
            _diagnostic(
                "UNRESOLVED_DATASET_PRODUCER",
                "ERROR",
                f"{dataset_type} dataset producer cannot be resolved",
                dataset=raw.get("dataset"),
                dataset_type=dataset_type,
                reason=raw.get("reason"),
                consumer_jobs=list(raw.get("consumer_jobs") or []),
                candidate_producer_jobs=list(
                    raw.get("candidate_producer_jobs") or []
                ),
            )
        )

    dependencies = defaultdict(list)
    evidence = []
    for (upstream, downstream), datasets in sorted(
        dependency_datasets.items(),
        key=lambda item: (
            identifier_match_key(item[0][1]),
            identifier_match_key(item[0][0]),
        ),
    ):
        dependencies[downstream].append(upstream)
        evidence.append(
            {
                "upstream_job": upstream,
                "downstream_job": downstream,
                "datasets": [datasets[key] for key in sorted(datasets)],
                "multiple_writer_input": bool(
                    dependency_is_multiwriter[(upstream, downstream)]
                ),
            }
        )

    try:
        candidate = ScheduleGraph(project, job_names, dependencies)
    except ScheduleContractError as exc:
        diagnostics.append(
            _diagnostic(
                "INFERRED_SCHEDULE_CYCLE",
                "ERROR",
                str(exc),
            )
        )
        candidate = ScheduleGraph(project, job_names, {})
    return candidate, diagnostics, evidence


def validate_schedule_against_lineage(
    schedule: ScheduleGraph,
    lineage_data: dict,
    *,
    baseline_lineage: dict | None = None,
) -> list[dict]:
    """Validate schedule reachability against lineage without changing order."""
    candidate, inference_diagnostics, evidence = infer_schedule_candidate(
        lineage_data,
        schedule.project,
        runnable_jobs=schedule.jobs,
    )
    diagnostics = [
        {
            **diagnostic,
            "severity": (
                "WARNING"
                if diagnostic.get("code") == "INFERRED_SCHEDULE_CYCLE"
                else diagnostic.get("severity")
            ),
        }
        for diagnostic in inference_diagnostics
    ]
    baseline_edges = set()
    if baseline_lineage is not None:
        baseline_jobs = {
            identifier_match_key(job.get("name"))
            for job in baseline_lineage.get("jobs") or []
        }
        shared_jobs = [
            job
            for job in schedule.jobs
            if identifier_match_key(job) in baseline_jobs
        ]
        baseline_candidate, _baseline_diagnostics, _baseline_evidence = (
            infer_schedule_candidate(
                baseline_lineage,
                schedule.project,
                runnable_jobs=shared_jobs,
            )
        )
        baseline_edges = {
            (
                identifier_match_key(upstream),
                identifier_match_key(downstream),
            )
            for upstream, downstream in baseline_candidate.edges
        }

    for item in evidence:
        upstream = item["upstream_job"]
        downstream = item["downstream_job"]
        if schedule.has_path(upstream, downstream):
            continue
        edge_key = (
            identifier_match_key(upstream),
            identifier_match_key(downstream),
        )
        code = "LINEAGE_DEPENDENCY_NOT_ORDERED"
        if baseline_lineage is not None and edge_key not in baseline_edges:
            code = "NEW_LINEAGE_DEPENDENCY_NOT_SCHEDULED"
        diagnostics.append(
            _diagnostic(
                code,
                "WARNING",
                "lineage dependency is not ordered by trusted schedule "
                "reachability",
                upstream_job=upstream,
                downstream_job=downstream,
                datasets=item["datasets"],
                multiple_writer_input=item["multiple_writer_input"],
            )
        )

    for upstream, downstream in sorted(
        schedule.edges,
        key=lambda edge: (
            identifier_match_key(edge[1]),
            identifier_match_key(edge[0]),
        ),
    ):
        if candidate.has_path(upstream, downstream):
            continue
        diagnostics.append(
            _diagnostic(
                "SCHEDULE_EDGE_WITHOUT_LINEAGE",
                "WARNING",
                "trusted schedule edge has no supporting lineage path",
                upstream_job=upstream,
                downstream_job=downstream,
            )
        )

    for diagnostic in inference_diagnostics:
        if diagnostic.get("code") != "MULTIPLE_WRITERS":
            continue
        writers = diagnostic["writer_jobs"]
        unordered_pairs = []
        for left, right in combinations(writers, 2):
            if schedule.has_path(left, right) or schedule.has_path(
                right, left
            ):
                continue
            unordered_pairs.append([left, right])
        if unordered_pairs:
            diagnostics.append(
                _diagnostic(
                    "UNORDERED_MULTIPLE_WRITERS",
                    "WARNING",
                    "multiple writers are unordered in the trusted schedule; "
                    "parallel execution is allowed and no business order is "
                    "inferred",
                    dataset=diagnostic["dataset"],
                    writer_jobs=writers,
                    unordered_pairs=unordered_pairs,
                )
            )
    return diagnostics
