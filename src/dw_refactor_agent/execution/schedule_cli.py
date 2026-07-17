"""CLI commands for trusted schedule DAG generation and governance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import dw_refactor_agent.config as config
from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
    configured_schedule_path,
)
from dw_refactor_agent.lineage.identifiers import identifier_match_key
from dw_refactor_agent.lineage.schedule_inference import (
    infer_schedule_candidate,
    validate_schedule_against_lineage,
)


def _read_lineage(project: str, raw_path: str | None) -> dict:
    path = Path(raw_path) if raw_path else config.lineage_data_path(project)
    try:
        return json.loads(path.read_text(encoding=config.TEXT_ENCODING))
    except FileNotFoundError:
        raise ScheduleContractError(
            f"lineage file does not exist: {path}; refresh lineage first"
        ) from None
    except (OSError, json.JSONDecodeError) as exc:
        raise ScheduleContractError(
            f"cannot read lineage file {path}: {exc}"
        ) from exc


def _task_names(project: str) -> set[str]:
    return {
        path.stem
        for path in config.iter_project_task_files(
            project, include_full_refresh=False
        )
    }


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _print_report(report: dict) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _deduplicate_diagnostics(diagnostics: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for diagnostic in diagnostics:
        key = json.dumps(diagnostic, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return unique


def _generate(args) -> int:
    lineage = _read_lineage(args.project, args.lineage)
    candidate, diagnostics, evidence = infer_schedule_candidate(
        lineage,
        args.project,
        runnable_jobs=_task_names(args.project),
    )
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else configured_schedule_path(args.project)
    )
    if output.exists() and not args.force:
        raise ScheduleContractError(
            f"schedule DAG already exists: {output}; pass --force to replace it"
        )
    if any(item.get("severity") == "ERROR" for item in diagnostics):
        _print_report(
            {
                "status": "blocked",
                "output": str(output),
                "candidate": candidate.to_dict(),
                "diagnostics": diagnostics,
                "dependency_evidence": evidence,
            }
        )
        return 1
    candidate.save(output)
    _print_report(
        {
            "status": "generated",
            "output": str(output),
            "candidate": candidate.to_dict(),
            "diagnostics": diagnostics,
            "dependency_evidence": evidence,
        }
    )
    return 0


def _validate(args) -> int:
    schedule = ScheduleGraph.load_for_project(args.project)
    lineage = _read_lineage(args.project, args.lineage)
    task_names = _task_names(args.project)
    schedule_keys = {identifier_match_key(job) for job in schedule.jobs}
    task_keys = {identifier_match_key(job) for job in task_names}
    diagnostics = []
    missing_task_files = [
        job
        for job in schedule.jobs
        if identifier_match_key(job) not in task_keys
    ]
    unscheduled_tasks = sorted(
        job
        for job in task_names
        if identifier_match_key(job) not in schedule_keys
    )
    if missing_task_files:
        diagnostics.append(
            {
                "code": "SCHEDULE_JOB_WITHOUT_TASK_SQL",
                "severity": "ERROR",
                "message": "schedule Jobs must resolve to task SQL files",
                "jobs": missing_task_files,
            }
        )
    if unscheduled_tasks:
        diagnostics.append(
            {
                "code": "TASK_JOB_NOT_SCHEDULED",
                "severity": "ERROR",
                "message": "task SQL Jobs must be added to the trusted schedule",
                "jobs": unscheduled_tasks,
            }
        )
    if not missing_task_files and not unscheduled_tasks:
        diagnostics.extend(
            validate_schedule_against_lineage(schedule, lineage)
        )
    status = (
        "blocked"
        if any(item.get("severity") == "ERROR" for item in diagnostics)
        else "valid_with_warnings"
        if diagnostics
        else "valid"
    )
    _print_report(
        {
            "status": status,
            "schedule": schedule.to_dict(),
            "diagnostics": diagnostics,
        }
    )
    return 1 if status == "blocked" else 0


def _diff(args) -> int:
    trusted = ScheduleGraph.load_for_project(args.project)
    lineage = _read_lineage(args.project, args.lineage)
    candidate, diagnostics, evidence = infer_schedule_candidate(
        lineage,
        args.project,
        runnable_jobs=_task_names(args.project),
    )
    trusted_edges = trusted.edges
    candidate_edges = candidate.edges
    missing_orderings = {
        edge
        for edge in candidate_edges
        if not trusted.has_path(edge[0], edge[1])
    }
    unsupported_edges = {
        edge
        for edge in trusted_edges
        if not candidate.has_path(edge[0], edge[1])
    }
    _print_report(
        {
            "status": "different"
            if trusted.to_dict() != candidate.to_dict()
            else "identical",
            "added_jobs": sorted(
                set(candidate.jobs) - set(trusted.jobs),
                key=identifier_match_key,
            ),
            "removed_jobs": sorted(
                set(trusted.jobs) - set(candidate.jobs),
                key=identifier_match_key,
            ),
            "missing_schedule_edges": [
                {"upstream_job": upstream, "downstream_job": downstream}
                for upstream, downstream in sorted(
                    missing_orderings,
                    key=lambda edge: (
                        identifier_match_key(edge[1]),
                        identifier_match_key(edge[0]),
                    ),
                )
            ],
            "schedule_only_edges": [
                {"upstream_job": upstream, "downstream_job": downstream}
                for upstream, downstream in sorted(
                    unsupported_edges,
                    key=lambda edge: (
                        identifier_match_key(edge[1]),
                        identifier_match_key(edge[0]),
                    ),
                )
            ],
            "diagnostics": diagnostics,
            "dependency_evidence": evidence,
        }
    )
    return 0


def _reconcile(args) -> int:
    path = configured_schedule_path(args.project)
    base_sha256 = _sha256(path)
    if path.is_file():
        trusted = ScheduleGraph.load(path, expected_project=args.project)
    else:
        trusted = ScheduleGraph(args.project, [], {})
    lineage = _read_lineage(args.project, args.lineage)
    candidate, inference_diagnostics, evidence = infer_schedule_candidate(
        lineage,
        args.project,
        runnable_jobs=_task_names(args.project),
    )
    evidence_by_edge = {
        (item["upstream_job"], item["downstream_job"]): item
        for item in evidence
    }
    merged_jobs = sorted(
        set(trusted.jobs) | set(candidate.jobs), key=identifier_match_key
    )
    merged_dependencies = {
        downstream: list(upstreams)
        for downstream, upstreams in trusted.dependencies.items()
    }
    applied_edges = []
    manual_edges = []
    for edge in sorted(
        (
            edge
            for edge in candidate.edges
            if not trusted.has_path(edge[0], edge[1])
        ),
        key=lambda item: (
            identifier_match_key(item[1]),
            identifier_match_key(item[0]),
        ),
    ):
        item = evidence_by_edge[edge]
        if item.get("multiple_writer_input"):
            manual_edges.append(item)
            continue
        upstream, downstream = edge
        current_proposal = ScheduleGraph(
            args.project, merged_jobs, merged_dependencies
        )
        if current_proposal.has_path(upstream, downstream):
            continue
        merged_dependencies.setdefault(downstream, []).append(upstream)
        applied_edges.append(item)

    diagnostics = list(inference_diagnostics)
    new_jobs = sorted(
        set(candidate.jobs) - set(trusted.jobs), key=identifier_match_key
    )
    removed_jobs = sorted(
        set(trusted.jobs) - set(candidate.jobs), key=identifier_match_key
    )
    for job in new_jobs:
        connected = any(job in edge for edge in candidate.edges)
        if not connected:
            diagnostics.append(
                {
                    "code": "NEW_ISOLATED_JOB",
                    "severity": "WARNING",
                    "message": "new Job has no inferred schedule dependencies",
                    "job": job,
                }
            )
    if removed_jobs:
        diagnostics.append(
            {
                "code": "REMOVED_JOB_REQUIRES_REVIEW",
                "severity": "ERROR",
                "message": "trusted Jobs missing from current task SQL are "
                "never deleted automatically",
                "jobs": removed_jobs,
            }
        )
    proposed = ScheduleGraph(
        args.project,
        merged_jobs,
        {
            downstream: sorted(set(upstreams), key=identifier_match_key)
            for downstream, upstreams in merged_dependencies.items()
        },
    )
    candidate_keys = {identifier_match_key(job) for job in candidate.jobs}
    validation_schedule = ScheduleGraph(
        args.project,
        candidate.jobs,
        {
            downstream: [
                upstream
                for upstream in upstreams
                if identifier_match_key(upstream) in candidate_keys
            ]
            for downstream, upstreams in proposed.dependencies.items()
            if identifier_match_key(downstream) in candidate_keys
        },
    )
    validation = validate_schedule_against_lineage(
        validation_schedule, lineage
    )
    combined_diagnostics = _deduplicate_diagnostics(diagnostics + validation)
    blocking = [
        item
        for item in combined_diagnostics
        if item.get("severity") == "ERROR"
    ]
    applied = False
    if args.apply_safe:
        if blocking:
            raise ScheduleContractError(
                "reconcile proposal has blocking diagnostics; no file was changed"
            )
        if _sha256(path) != base_sha256:
            raise ScheduleContractError(
                "trusted schedule changed during reconcile; retry from the new base"
            )
        proposed.save(path)
        applied = True
    _print_report(
        {
            "status": "applied" if applied else "proposal",
            "path": str(path),
            "base_sha256": base_sha256,
            "new_jobs": new_jobs,
            "removed_jobs_manual_review": removed_jobs,
            "safe_edges": applied_edges,
            "manual_review_edges": manual_edges,
            "proposed_schedule": proposed.to_dict(),
            "diagnostics": combined_diagnostics,
        }
    )
    return 0


def add_schedule_parser(subparsers) -> argparse.ArgumentParser:
    """Add ``dw-refactor schedule`` commands to the root parser."""
    schedule = subparsers.add_parser(
        "schedule", help="generate and govern trusted schedule DAGs"
    )
    commands = schedule.add_subparsers(dest="schedule_command", required=True)
    for name, handler, help_text in (
        ("generate", _generate, "generate the initial DAG from lineage"),
        ("validate", _validate, "validate DAG reachability against lineage"),
        ("diff", _diff, "compare trusted DAG with lineage candidate"),
        ("reconcile", _reconcile, "propose conservative DAG updates"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--project", required=True, choices=sorted(config.PROJECT_CONFIG)
        )
        command.add_argument("--lineage")
        if name == "generate":
            command.add_argument("--output")
            command.add_argument("--force", action="store_true")
        if name == "reconcile":
            command.add_argument("--apply-safe", action="store_true")
        command.set_defaults(func=handler)
    return schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="trusted schedule DAG tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_schedule_parser(subparsers)
    args = parser.parse_args(["schedule", *(argv or [])])
    try:
        return args.func(args)
    except ScheduleContractError as exc:
        parser.error(str(exc))
    return 2
