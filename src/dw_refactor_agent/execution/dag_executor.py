"""Shared dependency-aware executor for regular and shadow Job runs."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable, Collection, Generic, TypeVar

from dw_refactor_agent.execution.thread_pool import shutdown_executor
from dw_refactor_agent.lineage.identifiers import identifier_match_key

T = TypeVar("T")


@dataclass(frozen=True)
class DagJobResult(Generic[T]):
    job: str
    status: str
    value: T | None = None
    error: Exception | None = None
    blocked_by: tuple[str, ...] = ()


def execute_dag(
    jobs: Collection[str],
    dependencies: dict[str, Collection[str]],
    run_job: Callable[[str], T],
    *,
    parallel: int = 1,
    order: Collection[str] | None = None,
) -> dict[str, DagJobResult[T]]:
    """Execute a DAG while allowing independent branches after failures.

    A failed Job blocks only Jobs that transitively depend on it. Independent
    ready Jobs continue to run. The function returns one terminal result for
    every selected Job and never raises callback exceptions.
    """
    if parallel < 1:
        raise ValueError("parallel must be >= 1")
    selected = set(jobs)
    unknown_dependency_jobs = sorted(
        {
            dependency
            for job in selected
            for dependency in dependencies.get(job, [])
            if dependency not in selected
        },
        key=identifier_match_key,
    )
    if unknown_dependency_jobs:
        raise ValueError(
            "DAG dependencies reference unselected Jobs: "
            f"{unknown_dependency_jobs!r}"
        )
    upstreams = {job: set(dependencies.get(job, [])) for job in selected}

    ordered = list(order or [])
    order_index = {job: index for index, job in enumerate(ordered)}

    def sort_key(job: str):
        return (
            order_index.get(job, len(order_index)),
            identifier_match_key(job),
        )

    remaining = set(selected)
    results = {}
    running = {}
    executor = ThreadPoolExecutor(
        max_workers=min(parallel, len(selected) or 1)
    )
    try:
        while remaining or running:
            progressed = False
            for job in sorted(list(remaining), key=sort_key):
                direct_upstreams = upstreams[job]
                if not direct_upstreams.issubset(results):
                    continue
                blocked_by = tuple(
                    sorted(
                        (
                            upstream
                            for upstream in direct_upstreams
                            if results[upstream].status != "success"
                        ),
                        key=sort_key,
                    )
                )
                if blocked_by:
                    results[job] = DagJobResult(
                        job=job,
                        status="blocked",
                        blocked_by=blocked_by,
                    )
                    remaining.remove(job)
                    progressed = True

            ready = sorted(
                (
                    job
                    for job in remaining
                    if upstreams[job].issubset(results)
                    and all(
                        results[upstream].status == "success"
                        for upstream in upstreams[job]
                    )
                ),
                key=sort_key,
            )
            while ready and len(running) < parallel:
                job = ready.pop(0)
                remaining.remove(job)
                running[executor.submit(run_job, job)] = job
                progressed = True

            if running:
                done, _pending = wait(
                    list(running), return_when=FIRST_COMPLETED
                )
                for future in done:
                    job = running.pop(future)
                    try:
                        value = future.result()
                    except Exception as exc:
                        results[job] = DagJobResult(
                            job=job,
                            status="failed",
                            error=exc,
                        )
                    else:
                        results[job] = DagJobResult(
                            job=job,
                            status="success",
                            value=value,
                        )
                continue

            if remaining and not progressed:
                cycle = sorted(remaining, key=sort_key)
                raise ValueError(
                    f"DAG contains a cycle or unsatisfied dependency: {cycle!r}"
                )
    finally:
        shutdown_executor(executor)
    return results
