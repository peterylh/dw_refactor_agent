#!/usr/bin/env python3
"""Execute refactor shadow-run plans against the QA database."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.config import PROJECT_ROOT, get_mysql_cmd
from dw_refactor_agent.execution.dag_executor import execute_dag
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
)
from dw_refactor_agent.execution.sql_executor import ShadowSqlExecutor
from dw_refactor_agent.execution.thread_pool import shutdown_executor
from dw_refactor_agent.lineage.identifiers import identifier_match_key
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
)
from dw_refactor_agent.refactor.execution_provenance import run_execution_lock
from dw_refactor_agent.refactor.plan_artifact import (
    load_persisted_verification_plan,
    require_fresh_plan,
    require_fresh_plan_bundle,
)
from dw_refactor_agent.refactor.qa_pool import (
    QaSlotOwnership,
    claim_qa_slot,
    require_slot_ownership,
)
from dw_refactor_agent.refactor.shadow_manifest import (
    CompiledShadowManifest,
    PrefillMode,
    ShadowJob,
    compile_shadow_manifest,
    ensure_compiled_shadow_manifest,
    manifest_summary,
)
from dw_refactor_agent.refactor.verification_checks import (
    flatten_verification_checks,
)

FINAL_ALTER_JOB_STATES = {"FINISHED", "CANCELLED"}
DEFAULT_ALTER_JOB_TIMEOUT_SECONDS = 300
DEFAULT_ALTER_JOB_POLL_INTERVAL_SECONDS = 2
ALTER_TABLE_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+"
    r"(?P<table>(?:`[^`]+`|[^\s]+)(?:\s*\.\s*(?:`[^`]+`|[^\s]+))?)"
    r"\s+(?P<body>.*?)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
TABLE_RENAME_RE = re.compile(
    r"^\s*RENAME\s+"
    r"(?!COLUMN\b|ROLLUP\b|PARTITION\b)"
    r"(?P<target>(?:`[^`]+`|[^\s;]+)"
    r"(?:\s*\.\s*(?:`[^`]+`|[^\s;]+))?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


class ShadowRunSqlError(RuntimeError):
    """Raised when a SQL command fails during shadow-run execution."""


class ShadowRunBatchError(ShadowRunSqlError):
    """Raised when a batch fails after collecting invocation details."""

    def __init__(self, message: str, invocations: list[dict]):
        super().__init__(message)
        self.invocations = invocations


class _ShadowJobFailure(RuntimeError):
    def __init__(self, result: dict):
        super().__init__(str(result.get("error") or "shadow Job failed"))
        self.result = result


def _project_root() -> Path:
    return PROJECT_ROOT


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    )


def _log(message: str = "") -> None:
    print(message, flush=True)


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _start_timing() -> dict:
    return {
        "started_at": _now_iso(),
        "monotonic_start": time.monotonic(),
    }


def _finish_timing(result: dict, timing: dict) -> dict:
    result["started_at"] = timing["started_at"]
    result["finished_at"] = _now_iso()
    elapsed_ms = int(
        round((time.monotonic() - timing["monotonic_start"]) * 1000)
    )
    result["duration_ms"] = max(0, elapsed_ms)
    return result


def _sql_error_message(result: subprocess.CompletedProcess) -> str:
    return (
        result.stderr.strip()
        or result.stdout.strip()
        or f"mysql exited with status {result.returncode}"
    )


def run_sql(sql: str, db: str = "", qa: bool = False) -> str:
    """Execute one SQL statement and return stdout."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    cmd.extend(["-e", sql])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise ShadowRunSqlError(_sql_error_message(result))
    return result.stdout


def run_sql_text(sql_text: str, db: str = "", qa: bool = False) -> str:
    """Execute multi-statement SQL text through stdin."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    result = subprocess.run(
        cmd,
        input=sql_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise ShadowRunSqlError(_sql_error_message(result))
    return result.stdout


def _with_semicolon(sql: str) -> str:
    sql = sql.strip()
    return sql if sql.endswith(";") else f"{sql};"


def _split_outside_quotes(text: str, delimiter: str) -> list[str]:
    parts = []
    current = []
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if quote:
            current.append(ch)
            if ch == "\\" and nxt:
                current.append(nxt)
                i += 2
                continue
            if ch == quote:
                if nxt == quote:
                    current.append(nxt)
                    i += 2
                    continue
                quote = ""
            i += 1
            continue

        if ch in {"'", '"', "`"}:
            quote = ch
            current.append(ch)
            i += 1
            continue

        if ch == "-" and nxt == "-":
            line_end = text.find("\n", i + 2)
            if line_end == -1:
                current.append(text[i:])
                break
            current.append(text[i : line_end + 1])
            i = line_end + 1
            continue

        if ch == "/" and nxt == "*":
            block_end = text.find("*/", i + 2)
            if block_end == -1:
                current.append(text[i:])
                break
            current.append(text[i : block_end + 2])
            i = block_end + 2
            continue

        if ch == delimiter:
            parts.append("".join(current))
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    parts.append("".join(current))
    return parts


def _split_sql_statements(sql_text: str) -> list[str]:
    return [
        _with_semicolon(part)
        for part in _split_outside_quotes(sql_text, ";")
        if part.strip()
    ]


def _ddl_change_statements(sql_text: str) -> list[str]:
    """Return the DDL statements provided by the plan without rewriting them."""
    return _split_sql_statements(sql_text)


def _is_session_setting(statement: str) -> bool:
    return bool(re.match(r"^\s*SET\b", statement, re.IGNORECASE))


def _split_identifier_path(identifier: str) -> list[str]:
    parts = []
    current = []
    in_backticks = False
    for ch in identifier.strip():
        if ch == "`":
            in_backticks = not in_backticks
            current.append(ch)
        elif ch == "." and not in_backticks:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _unquote_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith("`") and identifier.endswith("`"):
        return identifier[1:-1].replace("``", "`")
    return identifier


def _quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def _quote_string_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _resolve_table_ref(
    table_ref: str, default_db: str
) -> tuple[str, str] | None:
    parts = [
        _unquote_identifier(part) for part in _split_identifier_path(table_ref)
    ]
    if len(parts) == 1:
        return default_db, parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


def _dedupe_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    seen = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
    return result


def _alter_table_wait_refs(
    statement: str, default_db: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    match = ALTER_TABLE_RE.match(statement)
    if not match:
        return [], []

    current_ref = _resolve_table_ref(match.group("table"), default_db)
    if current_ref is None:
        return [], []

    before_refs = [current_ref]
    after_refs = [current_ref]
    rename_match = TABLE_RENAME_RE.match(match.group("body").strip())
    if rename_match:
        target_ref = _resolve_table_ref(
            rename_match.group("target"), current_ref[0] or default_db
        )
        if target_ref is not None:
            after_refs = [target_ref]

    return _dedupe_refs(before_refs), _dedupe_refs(after_refs)


def _parse_mysql_table(output: str) -> list[dict]:
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return []

    headers = [header.strip() for header in lines[0].split("\t")]
    if "State" not in headers:
        return []

    rows = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        rows.append(
            {headers[idx]: values[idx].strip() for idx in range(len(headers))}
        )
    return rows


def _show_table_alter_jobs(
    db_name: str, table_name: str, qa: bool
) -> list[dict]:
    sql = (
        f"SHOW ALTER TABLE COLUMN FROM {_quote_identifier(db_name)} "
        f'WHERE TableName = "{_quote_string_value(table_name)}" '
        "ORDER BY CreateTime DESC LIMIT 10"
    )
    return _parse_mysql_table(run_sql(sql, qa=qa))


def _job_ids(jobs: list[dict]) -> set[str]:
    return {job.get("JobId", "") for job in jobs if job.get("JobId")}


def _active_alter_jobs(jobs: list[dict]) -> list[dict]:
    return [
        job
        for job in jobs
        if job.get("State", "").strip().upper() not in FINAL_ALTER_JOB_STATES
    ]


def _new_cancelled_jobs(
    jobs: list[dict], known_job_ids: set[str] | None
) -> list[dict]:
    if known_job_ids is None:
        return []
    return [
        job
        for job in jobs
        if job.get("JobId")
        and job.get("JobId") not in known_job_ids
        and job.get("State", "").strip().upper() == "CANCELLED"
    ]


def _wait_for_table_alter_jobs(
    db_name: str,
    table_name: str,
    *,
    qa: bool,
    known_job_ids: set[str] | None = None,
    poll_interval_seconds: float = DEFAULT_ALTER_JOB_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_ALTER_JOB_TIMEOUT_SECONDS,
) -> list[dict]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        jobs = _show_table_alter_jobs(db_name, table_name, qa)
        cancelled = _new_cancelled_jobs(jobs, known_job_ids)
        if cancelled:
            msg = cancelled[0].get("Msg", "")
            raise RuntimeError(
                f"ALTER job cancelled for {db_name}.{table_name}: {msg}"
            )

        active_jobs = _active_alter_jobs(jobs)
        if not active_jobs:
            return jobs

        if time.monotonic() >= deadline:
            states = ", ".join(
                f"{job.get('JobId')}:{job.get('State')}" for job in active_jobs
            )
            raise TimeoutError(
                f"Timed out waiting for ALTER jobs on "
                f"{db_name}.{table_name}: {states}"
            )
        time.sleep(poll_interval_seconds)


def _execute_ddl_statement(
    statement: str,
    qa_db: str,
    *,
    session_settings: tuple[str, ...] = (),
) -> None:
    before_refs, after_refs = _alter_table_wait_refs(statement, qa_db)
    known_job_ids_by_ref = {}

    for db_name, table_name in before_refs:
        jobs = _wait_for_table_alter_jobs(db_name, table_name, qa=True)
        known_job_ids_by_ref[(db_name, table_name)] = _job_ids(jobs)

    if session_settings:
        run_sql_text("\n".join((*session_settings, statement)), qa_db, qa=True)
    else:
        run_sql(statement, qa_db, qa=True)

    for db_name, table_name in after_refs:
        known_job_ids = known_job_ids_by_ref.get((db_name, table_name))
        jobs = _wait_for_table_alter_jobs(
            db_name,
            table_name,
            qa=True,
            known_job_ids=known_job_ids,
        )
        known_job_ids_by_ref[(db_name, table_name)] = _job_ids(jobs)


def _plan_anchor_tables(plan: dict) -> list:
    verification = plan.get("verification") or {}
    return list(verification.get("anchor_tables") or [])


def _rewrite_db_prefix(value: str, prod_db: str, qa_db: str) -> str:
    return value.replace(f"{prod_db}.", f"{qa_db}.")


def _qa_ddl_change(change: dict, prod_db: str, qa_db: str) -> dict:
    result = dict(change)
    if "sql" in result:
        original_sql = result.get("original_sql", result.get("sql", ""))
        result["sql"] = _rewrite_db_prefix(
            result.get("sql", ""),
            prod_db,
            qa_db,
        )
        result["original_sql"] = original_sql

    for key in ("table_name", "old_name", "new_name"):
        if key in result and isinstance(result[key], str):
            result[key] = _rewrite_db_prefix(result[key], prod_db, qa_db)

    return result


def _ddl_change_display_name(change: dict) -> str:
    change_type = str(change.get("change_type") or "").upper()
    table_name = str(change.get("table_name") or "").strip()
    old_name = str(change.get("old_name") or "").strip()
    new_name = str(change.get("new_name") or "").strip()
    if change_type == "RENAME" and old_name and new_name:
        return f"{old_name} -> {new_name}"
    return table_name or old_name or new_name or "?"


def _ddl_change_result(
    change: dict,
    status: str,
    error: str | None = None,
    *,
    statement_results: list[dict] | None = None,
) -> dict:
    result = {
        "change_type": change.get("change_type"),
        "sql": change.get("sql", ""),
        "status": status,
        "error": error,
    }
    if "original_sql" in change:
        result["original_sql"] = change.get("original_sql")
    for key in ("table_name", "old_name", "new_name"):
        if key in change:
            result[key] = change.get(key)
    for key in ("renames", "case_only_renames"):
        if key in change:
            result[key] = change.get(key)
    if statement_results is not None:
        result["statements"] = statement_results
    return result


def _ddl_statement_result(
    sql: str,
    status: str,
    error: str | None = None,
) -> dict:
    return {"sql": sql, "status": status, "error": error}


def _job_result(
    job: dict,
    status: str,
    error: str | None = None,
    *,
    invocation_count: int | None = None,
    batch_count: int | None = None,
    parallelism: int | None = None,
    batch_size: int | None = None,
    invocations: list[dict] | None = None,
) -> dict:
    job_name = job.get("job")
    result = {
        "job": job_name,
        "file": job.get("file"),
        "layer": job.get("layer", "?"),
        "target": job.get("target") or job_name,
        "status": status,
        "error": error,
    }
    for key in ("execution_values",):
        if key in job:
            result[key] = job.get(key)
    if invocation_count is not None:
        result["invocation_count"] = invocation_count
    if batch_count is not None:
        result["batch_count"] = batch_count
    if parallelism is not None:
        result["parallelism"] = parallelism
    if batch_size is not None:
        result["batch_size"] = batch_size
    if invocations is not None:
        result["invocations"] = invocations
    if "needs_etl_date" in job:
        result["needs_etl_date"] = bool(job.get("needs_etl_date", False))
    return result


def _invocation_result(
    driver_value: str | None,
    status: str,
    error: str | None = None,
) -> dict:
    return {
        "execution_value": driver_value,
        "status": status,
        "error": error,
    }


def _execution_value_strings(values) -> list[str]:
    result = []
    seen = set()
    for value in values or []:
        item = str(value)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return sorted(result)


def _job_driver_values(job: dict, spec) -> list[str | None]:
    if spec.materialized == "full" or not spec.slice_param:
        return [None]
    values = _execution_value_strings(job.get("execution_values"))
    if values:
        return values
    job_name = job.get("job") or spec.job_name
    raise ExecutionConfigError(
        f"[{job_name}] shadow-run requires execution_values "
        "for sliced incremental jobs"
    )


def _job_for_driver_value(job: dict, driver_value: str | None) -> dict:
    if driver_value is None:
        return dict(job)
    planned = dict(job)
    planned["execution_values"] = [driver_value]
    return planned


def _chunked(items: list, size: int) -> list[list]:
    return [
        items[index : index + size] for index in range(0, len(items), size)
    ]


def _include_batch_fields(parallel: int, batch_size: int) -> bool:
    return parallel > 1 or batch_size > 1


def _job_batch_kwargs(
    invocation_count: int,
    parallel: int,
    batch_size: int,
) -> dict:
    if not _include_batch_fields(parallel, batch_size):
        return {}
    batch_count = (
        (invocation_count + batch_size - 1) // batch_size
        if invocation_count
        else 0
    )
    return {
        "batch_count": batch_count,
        "parallelism": parallel,
        "batch_size": batch_size,
    }


def _effective_parallel(parallel: int) -> int:
    return max(1, int(parallel or 1))


def _effective_batch_size(batch_size: int) -> int:
    return max(1, int(batch_size or 1))


def _batch_driver_values(
    batch: list[tuple[str | None, object]],
) -> list[str | None]:
    values = []
    for driver_value, _invocation in batch:
        if driver_value is None or driver_value in values:
            continue
        values.append(driver_value)
    return values


def _execute_invocation_batch(
    executor: ShadowSqlExecutor,
    batch: list[tuple[str | None, object]],
) -> None:
    executor.execute_batch([invocation for _driver_value, invocation in batch])


def _job_dependencies_from_plan(
    plan: dict,
    root: Path,
) -> tuple[dict[str, int], dict[str, list[str]], str, list[str]]:
    jobs_to_run = plan.get("jobs_to_run", [])
    job_names = [job["job"] for job in jobs_to_run]
    jobs_by_key = {
        identifier_match_key(job_name): job_name for job_name in job_names
    }
    execution_graph = plan.get("execution_graph")
    if not isinstance(execution_graph, dict):
        raise ArtifactFormatError(
            "verification plan execution_graph snapshot is required; "
            "run analyze again"
        )
    try:
        graph = ScheduleGraph.from_dict(
            execution_graph, expected_project=plan.get("project")
        )
    except ScheduleContractError as exc:
        raise ArtifactFormatError(
            f"verification plan execution_graph is invalid: {exc}"
        ) from exc
    if len(job_names) <= 1:
        return (
            dict.fromkeys(job_names, 0),
            {job_name: [] for job_name in job_names},
            "trivial",
            [],
        )

    in_degree = dict.fromkeys(job_names, 0)
    adj = {job_name: [] for job_name in job_names}
    for downstream, upstreams in graph.selected_dependencies(
        job_names
    ).items():
        resolved_downstream = jobs_by_key.get(identifier_match_key(downstream))
        if resolved_downstream is None:
            continue
        for upstream in upstreams or []:
            resolved_upstream = jobs_by_key.get(identifier_match_key(upstream))
            if resolved_upstream is None:
                continue
            adj[resolved_upstream].append(resolved_downstream)
            in_degree[resolved_downstream] += 1
    return in_degree, adj, "trusted_schedule", []


def _skipped_shadow_job_result(
    job: dict,
    reason: str,
    *,
    parallel: int,
    batch_size: int,
    timing_detail: bool,
) -> dict:
    timer = _start_timing()
    invocation_results = [] if timing_detail else None
    return _finish_timing(
        _job_result(
            job,
            "skipped",
            reason,
            invocation_count=0,
            invocations=invocation_results,
            **_job_batch_kwargs(0, parallel, batch_size),
        ),
        timer,
    )


def _execute_shadow_job(
    job: dict,
    *,
    job_manifest: ShadowJob,
    job_index: int,
    job_count: int,
    root: Path,
    planner: ExecutionPlanner,
    qa_db: str,
    qa_ready_tables: set[str],
    qa_ready_lock: threading.Lock,
    batch_semaphore: threading.Semaphore,
    parallel: int,
    batch_size: int,
    timing_detail: bool,
) -> dict:
    job_name = job["job"]
    job_file = job["file"]
    layer = job.get("layer", "?")
    invocation_count = 0
    invocation_results = [] if timing_detail else None
    job_timer = _start_timing()
    invocation_parallel = (
        1
        if job_manifest.self_read or job_manifest.requires_serial_slices
        else parallel
    )

    _log(f"\n  --- {job_index}/{job_count}: [{layer}] {job_name} ---")
    file_path = root / job_file
    if not file_path.exists():
        error = f"文件不存在: {file_path}"
        _log(f"  [FAIL] {error}")
        return _finish_timing(
            _job_result(
                job,
                "failed",
                error,
                invocation_count=invocation_count,
                invocations=invocation_results,
                **_job_batch_kwargs(
                    invocation_count, invocation_parallel, batch_size
                ),
            ),
            job_timer,
        )

    try:
        spec = planner.task_spec(
            job_name,
            file_path,
            model_name=job.get("target") or job_name,
        )
        driver_values = _job_driver_values(job, spec)
    except ExecutionConfigError as exc:
        _log(f"  [FAIL] {job_name}: {exc}")
        return _finish_timing(
            _job_result(
                job,
                "failed",
                str(exc),
                invocation_count=invocation_count,
                invocations=invocation_results,
                **_job_batch_kwargs(
                    invocation_count, invocation_parallel, batch_size
                ),
            ),
            job_timer,
        )

    planned_invocations = []
    for driver_idx, driver_value in enumerate(driver_values, 1):
        if driver_value is not None:
            _log(
                f"\n  === replay slice "
                f"{driver_idx}/{len(driver_values)}: "
                f"{driver_value} ==="
            )
            _log(
                f"  slice {driver_idx}/{len(driver_values)}: "
                f"{spec.slice_param or 'execution_value'}={driver_value}"
            )
        planned_job = _job_for_driver_value(job, driver_value)

        try:
            invocations = planner.plan_shadow_job(
                planned_job,
                project_root=root,
            )
        except ExecutionConfigError as exc:
            _log(f"  [FAIL] {job_name}: {exc}")
            return _finish_timing(
                _job_result(
                    job,
                    "failed",
                    str(exc),
                    invocation_count=invocation_count,
                    invocations=invocation_results,
                    **_job_batch_kwargs(
                        invocation_count,
                        invocation_parallel,
                        batch_size,
                    ),
                ),
                job_timer,
            )

        for invocation in invocations:
            planned_invocations.append((driver_value, invocation))

    batches = _chunked(planned_invocations, batch_size)
    invocation_count = len(planned_invocations)
    batch_count = len(batches)

    def execute_batch(batch):
        batch_timer = _start_timing()
        for _batch_driver_value, batch_invocation in batch:
            sql_path = _display_path(batch_invocation.sql_path, root)
            _log(f"    SQL start: {sql_path}")
        batch_semaphore.acquire()
        try:
            with qa_ready_lock:
                qa_ready_snapshot = set(qa_ready_tables)
            executor = ShadowSqlExecutor(
                context=job_manifest.context,
                qa_ready_tables=qa_ready_snapshot,
                run_sql_text=run_sql_text,
            )
            _execute_invocation_batch(executor, batch)
        except Exception as exc:
            failed_invocations = []
            for batch_driver_value, batch_invocation in batch:
                sql_path = _display_path(batch_invocation.sql_path, root)
                failed_invocation = _finish_timing(
                    _invocation_result(
                        batch_driver_value,
                        "failed",
                        str(exc),
                    ),
                    dict(batch_timer),
                )
                _log(
                    f"    SQL fail: {sql_path} "
                    f"duration={failed_invocation['duration_ms']}ms "
                    f"error={exc}"
                )
                failed_invocations.append(failed_invocation)
            raise ShadowRunBatchError(
                str(exc),
                failed_invocations,
            ) from exc
        finally:
            batch_semaphore.release()
        success_invocations = []
        for batch_driver_value, batch_invocation in batch:
            sql_path = _display_path(batch_invocation.sql_path, root)
            success_invocation = _finish_timing(
                _invocation_result(batch_driver_value, "success"),
                dict(batch_timer),
            )
            _log(
                f"    SQL done: {sql_path} "
                f"duration={success_invocation['duration_ms']}ms"
            )
            success_invocations.append(success_invocation)
        return {
            "driver_values": _batch_driver_values(batch),
            "invocations": success_invocations,
        }

    try:
        if invocation_parallel == 1 or batch_count <= 1:
            batch_results = [execute_batch(batch) for batch in batches]
        else:
            executor_pool = ThreadPoolExecutor(
                max_workers=min(invocation_parallel, batch_count)
            )
            try:
                future_to_index = {
                    executor_pool.submit(execute_batch, batch): index
                    for index, batch in enumerate(batches)
                }
                indexed_results = []
                for future in as_completed(future_to_index):
                    indexed_results.append(
                        (future_to_index[future], future.result())
                    )
                batch_results = [
                    result for _index, result in sorted(indexed_results)
                ]
            finally:
                shutdown_executor(executor_pool)

        for batch_result in batch_results:
            if invocation_results is not None:
                invocation_results.extend(batch_result["invocations"])
        _log(f"  + {qa_db}.{job_name}")
    except Exception as exc:
        _log(f"  [FAIL] {job_name}: {exc}")
        if invocation_results is not None and isinstance(
            exc,
            ShadowRunBatchError,
        ):
            invocation_results.extend(exc.invocations)
        return _finish_timing(
            _job_result(
                job,
                "failed",
                str(exc),
                invocation_count=invocation_count,
                invocations=invocation_results,
                **_job_batch_kwargs(
                    invocation_count, invocation_parallel, batch_size
                ),
            ),
            job_timer,
        )

    with qa_ready_lock:
        qa_ready_tables.update(job_manifest.outputs or {job_name})

    return _finish_timing(
        _job_result(
            job,
            "success",
            invocation_count=invocation_count,
            invocations=invocation_results,
            **_job_batch_kwargs(
                invocation_count, invocation_parallel, batch_size
            ),
        ),
        job_timer,
    )


def _run_shadow_jobs(
    plan: dict,
    *,
    manifest: CompiledShadowManifest,
    root: Path,
    qa_db: str,
    planner: ExecutionPlanner,
    parallel: int,
    batch_size: int,
    timing_detail: bool,
) -> dict:
    jobs_to_run = plan.get("jobs_to_run", [])
    job_phase_timer = _start_timing()
    job_count = len(jobs_to_run)
    job_results_by_name = {}
    phase = {
        "name": "run_jobs",
        "status": "success",
        "jobs": [],
        "parallelism": parallel,
    }
    if job_count == 0:
        phase["scheduler"] = "empty"
        _finish_timing(phase, job_phase_timer)
        return phase

    qa_ready_tables: set[str] = set()
    qa_ready_lock = threading.Lock()
    batch_semaphore = threading.Semaphore(parallel)
    _in_degree, adj, scheduler, warnings = _job_dependencies_from_plan(
        plan,
        root,
    )
    job_by_name = {job["job"]: job for job in jobs_to_run}
    index_by_name = {
        job["job"]: index for index, job in enumerate(jobs_to_run, 1)
    }
    phase["scheduler"] = scheduler
    if warnings:
        phase["warnings"] = list(warnings)
        for warning in warnings:
            _log(f"  警告: {warning}")

    def run_job(job_name: str) -> dict:
        result = _execute_shadow_job(
            job_by_name[job_name],
            job_manifest=manifest.jobs[job_name],
            job_index=index_by_name[job_name],
            job_count=job_count,
            root=root,
            planner=planner,
            qa_db=qa_db,
            qa_ready_tables=qa_ready_tables,
            qa_ready_lock=qa_ready_lock,
            batch_semaphore=batch_semaphore,
            parallel=parallel,
            batch_size=batch_size,
            timing_detail=timing_detail,
        )
        if result.get("status") != "success":
            raise _ShadowJobFailure(result)
        return result

    dependencies = {job_name: [] for job_name in job_by_name}
    for upstream, downstream_jobs in adj.items():
        for downstream in downstream_jobs:
            dependencies[downstream].append(upstream)
    dag_results = execute_dag(
        set(job_by_name),
        dependencies,
        run_job,
        parallel=parallel,
        order=[job["job"] for job in jobs_to_run],
    )
    for job_name, dag_result in dag_results.items():
        if dag_result.status == "success":
            job_results_by_name[job_name] = dag_result.value
            continue
        phase["status"] = "failed"
        if dag_result.status == "failed" and isinstance(
            dag_result.error, _ShadowJobFailure
        ):
            job_results_by_name[job_name] = dag_result.error.result
            continue
        if dag_result.status == "failed":
            job_results_by_name[job_name] = _finish_timing(
                _job_result(
                    job_by_name[job_name],
                    "failed",
                    str(dag_result.error),
                    invocation_count=0,
                    **_job_batch_kwargs(0, parallel, batch_size),
                ),
                _start_timing(),
            )
            continue
        job_results_by_name[job_name] = _skipped_shadow_job_result(
            job_by_name[job_name],
            "upstream job failed: {}".format(", ".join(dag_result.blocked_by)),
            parallel=parallel,
            batch_size=batch_size,
            timing_detail=timing_detail,
        )

    phase["jobs"] = [
        job_results_by_name[job["job"]]
        for job in jobs_to_run
        if job["job"] in job_results_by_name
    ]
    if any(job.get("status") == "failed" for job in phase["jobs"]):
        phase["status"] = "failed"
    _finish_timing(phase, job_phase_timer)
    return phase


def _result_summary(plan: dict, phases: list[dict]) -> dict:
    phase_by_name = {phase.get("name"): phase for phase in phases}
    ddl_changes = phase_by_name.get("apply_ddl_changes", {}).get(
        "ddl_changes", []
    )
    jobs = phase_by_name.get("run_jobs", {}).get("jobs", [])
    return {
        "baseline_table_count": len(plan.get("baseline_ddl", {})),
        "ddl_change_count": len(plan.get("ddl_changes", [])),
        "job_count": len(plan.get("jobs_to_run", [])),
        "failed_job_count": sum(
            1 for job in jobs if job.get("status") == "failed"
        ),
        "failed_ddl_change_count": sum(
            1
            for ddl_change in ddl_changes
            if ddl_change.get("status") == "failed"
        ),
    }


def _shadow_result(
    plan: dict, *, mode: str, status: str, phases: list
) -> dict:
    result = {
        "status": status,
        "mode": mode,
        "project": plan.get("project"),
        "run_id": plan.get("run_id"),
        "project_db": plan.get("project_db"),
        "qa_db": plan["qa_db"],
        "qa_database_pool": list(
            plan.get("qa_database_pool") or [plan["qa_db"]]
        ),
        "job_count": len(plan.get("jobs_to_run", [])),
        "summary": _result_summary(plan, phases),
        "phases": phases,
    }
    shadow_manifest = plan.get("_shadow_manifest_summary")
    if shadow_manifest is not None:
        result["shadow_manifest"] = shadow_manifest
    return result


def _failed_shadow_result(plan: dict, phases: list[dict]) -> dict:
    return _shadow_result(
        plan,
        mode="execute",
        status="failed",
        phases=phases,
    )


def _compile_shadow_manifest_phase(
    plan: dict,
    root: Path,
    planner: ExecutionPlanner,
    *,
    dry_run: bool,
) -> tuple[CompiledShadowManifest | None, dict]:
    timer = _start_timing()
    try:
        manifest = ensure_compiled_shadow_manifest(
            compile_shadow_manifest(plan, root, planner)
        )
        blockers = list(manifest.blockers)
        phase = {
            "name": "compile_shadow_manifest",
            "status": "failed"
            if blockers
            else ("dry_run" if dry_run else "success"),
            "blockers": blockers,
            "warnings": list(manifest.warnings),
        }
        plan["_shadow_manifest_summary"] = manifest_summary(manifest)
        return manifest, _finish_timing(phase, timer)
    except Exception as exc:
        phase = {
            "name": "compile_shadow_manifest",
            "status": "failed",
            "blockers": [str(exc)],
            "warnings": [],
        }
        plan["_shadow_manifest_summary"] = {
            "blockers": [str(exc)],
            "warnings": [],
        }
        return None, _finish_timing(phase, timer)


def _prefill_sql(action, prod_db: str, qa_db: str) -> str:
    partition = ""
    if action.mode is PrefillMode.PARTITIONS:
        partition = f" PARTITION ({', '.join(action.partitions)})"
    return (
        f"INSERT INTO {qa_db}.{action.baseline_table} "
        f"SELECT * FROM {prod_db}.{action.baseline_table}{partition};"
    )


def _prefill_phase(
    manifest: CompiledShadowManifest,
    prod_db: str,
    qa_db: str,
    *,
    dry_run: bool,
) -> dict:
    timer = _start_timing()
    results = []
    phase = {
        "name": "prefill_baseline_data",
        "status": "dry_run" if dry_run else "success",
        "actions": results,
    }
    for action in manifest.prefill_actions:
        sql = _prefill_sql(action, prod_db, qa_db)
        result = {
            **action.to_dict(),
            "sql": sql,
            "status": "dry_run" if dry_run else "success",
            "error": None,
        }
        if not dry_run:
            try:
                run_sql(sql, qa_db, qa=True)
            except Exception as exc:
                result["status"] = "failed"
                result["error"] = str(exc)
                results.append(result)
                phase["status"] = "failed"
                return _finish_timing(phase, timer)
        results.append(result)
    return _finish_timing(phase, timer)


def _dry_run_phases(
    plan: dict,
    manifest: CompiledShadowManifest,
    *,
    root: Path,
    timing_detail: bool = False,
    parallel: int = 1,
    batch_size: int = 1,
) -> list[dict]:
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    planner = ExecutionPlanner(plan["project"], project_root=root)
    qa_ddl_changes = [
        _qa_ddl_change(change, prod_db, qa_db) for change in ddl_changes
    ]

    selection_timer = _start_timing()
    selection_phase = _finish_timing(
        {
            "name": "select_qa_slot",
            "status": "dry_run",
            "default_qa_db": qa_db,
            "qa_database_pool": list(plan.get("qa_database_pool") or [qa_db]),
            "note": "execute mode claims one available pool slot",
        },
        selection_timer,
    )
    create_timer = _start_timing()
    create_phase = _finish_timing(
        {
            "name": "create_baseline_tables",
            "status": "dry_run",
            "tables": [
                {"table": table_name, "status": "dry_run"}
                for table_name in sorted(baseline_ddl)
            ],
        },
        create_timer,
    )
    prefill_phase = _prefill_phase(
        manifest,
        prod_db,
        qa_db,
        dry_run=True,
    )
    ddl_timer = _start_timing()
    ddl_phase = _finish_timing(
        {
            "name": "apply_ddl_changes",
            "status": "dry_run",
            "ddl_changes": [
                _ddl_change_result(change, "dry_run")
                for change in qa_ddl_changes
            ],
        },
        ddl_timer,
    )

    job_phase_timer = _start_timing()
    jobs = []
    for job in jobs_to_run:
        job_timer = _start_timing()
        file_path = root / job["file"]
        invocation_count = 0
        invocation_results = [] if timing_detail else None
        if not file_path.exists():
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "skipped",
                        "文件不存在",
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                        **_job_batch_kwargs(
                            invocation_count,
                            parallel,
                            batch_size,
                        ),
                    ),
                    job_timer,
                )
            )
            continue
        try:
            spec = planner.task_spec(
                job["job"],
                file_path,
                model_name=job.get("target") or job["job"],
            )
            driver_values = _job_driver_values(job, spec)
            for driver_value in driver_values:
                planned_job = _job_for_driver_value(job, driver_value)
                planned_invocations = planner.plan_shadow_job(
                    planned_job,
                    project_root=root,
                )
                if planned_invocations:
                    invocation_count += len(planned_invocations)
                    if invocation_results is not None:
                        for _ in planned_invocations:
                            invocation_timer = _start_timing()
                            invocation_results.append(
                                _finish_timing(
                                    _invocation_result(
                                        driver_value,
                                        "dry_run",
                                    ),
                                    invocation_timer,
                                )
                            )
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "dry_run",
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                        **_job_batch_kwargs(
                            invocation_count,
                            parallel,
                            batch_size,
                        ),
                    ),
                    job_timer,
                )
            )
        except ExecutionConfigError as exc:
            jobs.append(
                _finish_timing(
                    _job_result(
                        job,
                        "failed",
                        str(exc),
                        invocation_count=invocation_count,
                        invocations=invocation_results,
                        **_job_batch_kwargs(
                            invocation_count,
                            parallel,
                            batch_size,
                        ),
                    ),
                    job_timer,
                )
            )
    job_phase_status = (
        "failed"
        if any(job.get("status") == "failed" for job in jobs)
        else "dry_run"
    )

    job_phase = _finish_timing(
        {
            "name": "run_jobs",
            "status": job_phase_status,
            "jobs": jobs,
        },
        job_phase_timer,
    )

    return [
        selection_phase,
        create_phase,
        prefill_phase,
        ddl_phase,
        job_phase,
    ]


def execute_shadow_plan(
    plan: dict,
    *,
    root: Path,
    claimed_ownership: QaSlotOwnership | None = None,
    dry_run: bool = False,
    timing_detail: bool = False,
    parallel: int = 1,
    batch_size: int = 1,
) -> dict:
    """Execute or preview a shadow-run validation plan."""
    result_timer = _start_timing()
    parallel = _effective_parallel(parallel)
    batch_size = _effective_batch_size(batch_size)

    def finish_result(result: dict) -> dict:
        return _finish_timing(result, result_timer)

    root = Path(root).resolve()
    planner = ExecutionPlanner(plan["project"], project_root=root)
    manifest, manifest_phase = _compile_shadow_manifest_phase(
        plan,
        root,
        planner,
        dry_run=dry_run,
    )
    if manifest is None or manifest_phase["status"] == "failed":
        return finish_result(
            _shadow_result(
                plan,
                mode="dry_run" if dry_run else "execute",
                status="failed",
                phases=[manifest_phase],
            )
        )

    if dry_run:
        _dry_run(plan, manifest, root=root)
        phases = [manifest_phase] + _dry_run_phases(
            plan,
            manifest,
            root=root,
            timing_detail=timing_detail,
            parallel=parallel,
            batch_size=batch_size,
        )
        summary = _result_summary(plan, phases)
        status = "failed" if summary["failed_job_count"] else "dry_run"
        return finish_result(
            _shadow_result(plan, mode="dry_run", status=status, phases=phases)
        )

    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    phases = [manifest_phase]

    if claimed_ownership is None:
        raise ArtifactFormatError(
            "execute-mode shadow plan requires claimed QA slot ownership"
        )
    ownership_expectations = {
        "project": plan.get("project"),
        "run_id": plan.get("run_id"),
        "qa_database": plan.get("qa_db"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "workspace_fingerprint": (plan.get("analysis_snapshot") or {}).get(
            "workspace_fingerprint"
        ),
    }
    for field, expected in ownership_expectations.items():
        if (
            expected is not None
            and getattr(claimed_ownership, field) != expected
        ):
            raise ArtifactFormatError(
                f"claimed QA slot {field} does not match runtime plan"
            )
    try:
        require_slot_ownership(
            project=plan["project"],
            run_id=claimed_ownership.run_id,
            execution_id=claimed_ownership.execution_id,
            database=qa_db,
            plan_fingerprint=claimed_ownership.plan_fingerprint,
            workspace_fingerprint=claimed_ownership.workspace_fingerprint,
        )
    except Exception as exc:
        ownership_phase = _finish_timing(
            {
                "name": "validate_qa_slot_ownership",
                "status": "failed",
                "error": str(exc),
            },
            _start_timing(),
        )
        phases.append(ownership_phase)
        return finish_result(_failed_shadow_result(plan, phases))

    checks = plan.get("verification", {}).get("checks", [])
    if not _plan_anchor_tables(plan) and not checks:
        _log("  警告: 无锚点表且无校验配置")
        _log("    作业会正常执行，但后续 compare 命令没有表可对比校验")
        _log("    如果只是想确认作业不报错，可继续执行\n")

    _log("=" * 60)
    _log(f"已领取验证数据库: {qa_db}")
    _log(f"\n{'=' * 60}")
    _log(f"Phase 1: 基线建表 ({len(baseline_ddl)} 张)")
    create_timer = _start_timing()
    table_results = []
    create_phase = {
        "name": "create_baseline_tables",
        "status": "success",
        "tables": table_results,
    }
    for table_name in sorted(baseline_ddl):
        ddl_raw = baseline_ddl[table_name]
        if not ddl_raw.strip():
            table_results.append({"table": table_name, "status": "skipped"})
            continue
        ddl_qa = ddl_raw.replace(f"{prod_db}.", f"{qa_db}.")
        try:
            run_sql(ddl_qa, qa_db, qa=True)
            _log(f"  [CREATE] {qa_db}.{table_name}")
            table_results.append({"table": table_name, "status": "success"})
        except Exception as exc:
            _log(f"  [FAIL] {qa_db}.{table_name}: {exc}")
            table_results.append(
                {"table": table_name, "status": "failed", "error": str(exc)}
            )
            create_phase["status"] = "failed"
            _finish_timing(create_phase, create_timer)
            phases.append(create_phase)
            return finish_result(_failed_shadow_result(plan, phases))
    _finish_timing(create_phase, create_timer)
    _log(f"Phase 1 完成 duration={create_phase['duration_ms']}ms")
    phases.append(create_phase)

    prefill_phase = _prefill_phase(
        manifest,
        prod_db,
        qa_db,
        dry_run=False,
    )
    phases.append(prefill_phase)
    if prefill_phase.get("status") == "failed":
        return finish_result(_failed_shadow_result(plan, phases))

    ddl_change_results = []
    ddl_timer = _start_timing()
    ddl_phase = {
        "name": "apply_ddl_changes",
        "status": "success",
        "ddl_changes": ddl_change_results,
    }
    if ddl_changes:
        _log(f"\n{'-' * 60}")
        _log(f"Phase 2: 应用 DDL 变更 ({len(ddl_changes)} 条)")
        for change in ddl_changes:
            qa_change = _qa_ddl_change(change, prod_db, qa_db)
            sql = qa_change.get("sql", "")
            if not sql.strip():
                ddl_change_results.append(
                    _ddl_change_result(qa_change, "skipped")
                )
                continue
            statements = _ddl_change_statements(sql)
            statement_results = []
            session_settings = []
            try:
                for statement in statements:
                    try:
                        _execute_ddl_statement(
                            statement,
                            qa_db,
                            session_settings=(
                                ()
                                if _is_session_setting(statement)
                                else tuple(session_settings)
                            ),
                        )
                    except Exception as exc:
                        statement_results.append(
                            _ddl_statement_result(
                                statement,
                                "failed",
                                str(exc),
                            )
                        )
                        raise
                    if _is_session_setting(statement):
                        session_settings.append(statement)
                    statement_results.append(
                        _ddl_statement_result(statement, "success")
                    )
                _log(
                    f"  [{qa_change.get('change_type')}] "
                    f"{_ddl_change_display_name(qa_change)}"
                )
                ddl_change_results.append(
                    _ddl_change_result(
                        qa_change,
                        "success",
                        statement_results=(
                            statement_results
                            if len(statement_results) > 1
                            else None
                        ),
                    )
                )
            except Exception as exc:
                _log(f"  [FAIL] {qa_change.get('change_type')}: {exc}")
                ddl_change_results.append(
                    _ddl_change_result(
                        qa_change,
                        "failed",
                        str(exc),
                        statement_results=(
                            statement_results
                            if len(statements) > 1
                            or len(statement_results) > 1
                            else None
                        ),
                    )
                )
                ddl_phase["status"] = "failed"
                _finish_timing(ddl_phase, ddl_timer)
                phases.append(ddl_phase)
                return finish_result(_failed_shadow_result(plan, phases))
    _finish_timing(ddl_phase, ddl_timer)
    _log(f"Phase 2 完成 duration={ddl_phase['duration_ms']}ms")
    phases.append(ddl_phase)

    _log(f"\n{'=' * 60}")
    _log(f"Phase 3: 执行作业 ({len(jobs_to_run)} 个)")
    job_phase = _run_shadow_jobs(
        plan,
        manifest=manifest,
        root=root,
        qa_db=qa_db,
        planner=planner,
        parallel=parallel,
        batch_size=batch_size,
        timing_detail=timing_detail,
    )
    _log(f"Phase 3 完成 duration={job_phase['duration_ms']}ms")
    phases.append(job_phase)
    if job_phase.get("status") == "failed":
        return finish_result(_failed_shadow_result(plan, phases))

    _log(f"\n{'=' * 60}")
    _log(f"Shadow run 完成! 共执行 {len(jobs_to_run)} 个作业, 目标库: {qa_db}")
    return finish_result(
        _shadow_result(
            plan,
            mode="execute",
            status="completed",
            phases=phases,
        )
    )


def run_shadow_plan(
    plan_path: Path,
    output_path: Path,
    *,
    provenance: dict,
    dry_run: bool = False,
    timing_detail: bool = False,
    parallel: int = 1,
    batch_size: int = 1,
) -> dict:
    """Run or dry-run a validation plan and write the execution result."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    workspace_digest = provenance.get("workspace_fingerprint")
    plan_digest = provenance.get("plan_fingerprint")
    for field, value in (
        ("workspace_fingerprint", workspace_digest),
        ("plan_fingerprint", plan_digest),
    ):
        if not isinstance(value, str) or not value.startswith("sha256:"):
            raise ArtifactFormatError(
                f"shadow-run provenance {field} must be a SHA-256 digest"
            )
    bundle = require_fresh_plan_bundle(plan_path)
    plan = bundle.plan
    expected_workspace = (plan.get("analysis_snapshot") or {}).get(
        "workspace_fingerprint"
    )
    expected_plan = plan.get("plan_fingerprint")
    if workspace_digest != expected_workspace:
        raise ArtifactFormatError(
            "shadow-run provenance workspace_fingerprint does not match "
            "the verification plan"
        )
    if plan_digest != expected_plan:
        raise ArtifactFormatError(
            "shadow-run provenance plan_fingerprint does not match the "
            "verification plan"
        )
    execution_id = str(uuid.uuid4())
    mode = "dry_run" if dry_run else "execute"
    wrapper_timer = _start_timing()
    common_result = {
        "format_version": FORMAT_VERSION,
        "mode": mode,
        "plan": str(plan_path),
        "project": plan.get("project"),
        "run_id": plan.get("run_id"),
        "execution_id": execution_id,
        "qa_db": plan.get("qa_db"),
        "qa_database_pool": list(plan.get("qa_database_pool") or []),
        "workspace_fingerprint": workspace_digest,
        "plan_fingerprint": plan_digest,
    }
    with run_execution_lock(plan_path):
        atomic_write_json(
            output_path,
            {
                **common_result,
                "status": "running",
                "started_at": wrapper_timer["started_at"],
            },
        )
        if dry_run:
            result = execute_shadow_plan(
                plan,
                root=bundle.root,
                dry_run=True,
                timing_detail=timing_detail,
                parallel=parallel,
                batch_size=batch_size,
            )
        else:
            preview_planner = ExecutionPlanner(
                plan["project"], project_root=bundle.root
            )
            _, preview_phase = _compile_shadow_manifest_phase(
                plan,
                bundle.root,
                preview_planner,
                dry_run=False,
            )
            if preview_phase.get("status") == "failed":
                result = _failed_shadow_result(plan, [preview_phase])
            else:
                claim_timer = _start_timing()
                try:
                    owner = claim_qa_slot(
                        project=plan["project"],
                        run_id=plan["run_id"],
                        execution_id=execution_id,
                        pool=tuple(plan["qa_database_pool"]),
                        plan_fingerprint=plan_digest,
                        workspace_fingerprint=workspace_digest,
                    )
                    configured_databases = {
                        database.casefold(): database
                        for database in plan["qa_database_pool"]
                    }
                    configured_database = configured_databases.get(
                        owner.qa_database.casefold()
                    )
                    if configured_database is None:
                        raise ArtifactFormatError(
                            f"claimed database {owner.qa_database} is not in "
                            "the configured QA database pool"
                        )
                    if owner.qa_database != configured_database:
                        raise ArtifactFormatError(
                            "claimed database spelling does not match the "
                            "configured QA database pool"
                        )
                    claim_phase = _finish_timing(
                        {
                            "name": "claim_qa_slot",
                            "status": "success",
                            "qa_db": owner.qa_database,
                            "claimed_at": owner.claimed_at,
                        },
                        claim_timer,
                    )
                except Exception as exc:
                    claim_phase = _finish_timing(
                        {
                            "name": "claim_qa_slot",
                            "status": "failed",
                            "error": str(exc),
                        },
                        claim_timer,
                    )
                    result = _failed_shadow_result(plan, [claim_phase])
                    result["error"] = str(exc)
                else:
                    runtime_plan = deepcopy(plan)
                    runtime_plan["qa_db"] = owner.qa_database
                    common_result["qa_db"] = owner.qa_database
                    atomic_write_json(
                        output_path,
                        {
                            **common_result,
                            "status": "running",
                            "started_at": wrapper_timer["started_at"],
                        },
                    )
                    result = execute_shadow_plan(
                        runtime_plan,
                        root=bundle.root,
                        claimed_ownership=owner,
                        dry_run=False,
                        timing_detail=timing_detail,
                        parallel=parallel,
                        batch_size=batch_size,
                    )
                    result.setdefault("phases", []).insert(0, claim_phase)
        result.update(common_result)
        _finish_timing(result, wrapper_timer)
        atomic_write_json(output_path, result)
    return result


def _dry_run(
    plan: dict, manifest: CompiledShadowManifest, *, root: Path
) -> None:
    qa_db = plan["qa_db"]
    prod_db = plan["project_db"]
    baseline_ddl = plan.get("baseline_ddl", {})
    ddl_changes = plan.get("ddl_changes", [])
    jobs_to_run = plan.get("jobs_to_run", [])
    planner = ExecutionPlanner(plan["project"], project_root=root)

    print(f"{'=' * 60}")
    print("=== SHADOW RUN DRY RUN ===")
    print(f"  项目: {plan['project']}")
    git_info = plan.get("git") or {}
    if git_info:
        print(f"  分支: {git_info.get('branch', '')}")
        merge_base = str(git_info.get("merge_base") or "")
        print(f"  基线: {merge_base[:12]}...")
    print(f"  生产库: {prod_db} -> 验证库: {qa_db}")
    print(f"  锚点: {_plan_anchor_tables(plan)}")
    checks = flatten_verification_checks(
        (plan.get("verification") or {}).get("checks", [])
    )
    if not _plan_anchor_tables(plan) and not checks:
        print()
        print(
            "  警告: 无锚点表且无校验配置，后续 compare 命令没有表可对比校验"
        )

    qa_pool = list(plan.get("qa_database_pool") or [qa_db])
    print("\n--- Phase 0: 选择验证库 ---")
    print(f"  候选池: {', '.join(qa_pool)}")
    print("  execute 模式会原子领取一个可用槽；dry-run 不连接数据库")

    print(f"\n--- Phase 1: 基线建表 ({len(baseline_ddl)} 张) ---")
    for table_name in sorted(baseline_ddl):
        print(f"  [CREATE] {qa_db}.{table_name}")

    actions = manifest.prefill_actions
    print(f"\n--- Phase 1.5: 基线数据预填 ({len(actions)} 条) ---")
    for action in actions:
        print(f"  {_prefill_sql(action, prod_db, qa_db)}")

    print(f"\n--- Phase 2: DDL 变更 ({len(ddl_changes)} 条) ---")
    for change in ddl_changes:
        qa_change = _qa_ddl_change(change, prod_db, qa_db)
        print(
            f"  [{qa_change['change_type']}] "
            f"{_ddl_change_display_name(qa_change)}"
        )
        for statement in _ddl_change_statements(qa_change.get("sql", "")):
            print(f"    {statement}")

    print(f"\n--- Phase 3: 作业 ({len(jobs_to_run)} 个) ---")
    qa_ready_tables: set[str] = set()
    for idx, job in enumerate(jobs_to_run, 1):
        job_name = job["job"]
        layer = job.get("layer", "?")
        job_file = job["file"]
        file_path = root / job_file

        print(f"\n  {idx}/{len(jobs_to_run)}: [{layer}] {job_name}")
        if not file_path.exists():
            print("    [SKIP] 文件不存在")
            continue

        try:
            spec = planner.task_spec(
                job_name,
                file_path,
                model_name=job.get("target") or job_name,
            )
            driver_values = _job_driver_values(job, spec)
        except ExecutionConfigError as exc:
            print(f"    [FAIL] {exc}")
            continue

        for driver_idx, driver_value in enumerate(driver_values, 1):
            if driver_value is not None:
                print(
                    f"\n    === replay slice "
                    f"{driver_idx}/{len(driver_values)}: "
                    f"{driver_value} ==="
                )
            planned_job = _job_for_driver_value(job, driver_value)

            try:
                invocations = planner.plan_shadow_job(
                    planned_job,
                    project_root=root,
                )
            except ExecutionConfigError as exc:
                print(f"    [FAIL] {exc}")
                continue

            for invocation in invocations:
                job_manifest = manifest.jobs[job_name]
                executor = ShadowSqlExecutor(
                    context=job_manifest.context,
                    qa_ready_tables=set(qa_ready_tables),
                    run_sql_text=run_sql_text,
                )
                print(
                    f"    strategy={invocation.strategy}, "
                    f"full_refresh={int(invocation.full_refresh)}, "
                    f"sql={invocation.sql_path}"
                )
                rendered = executor.render(invocation)
                for line in rendered.splitlines()[:8]:
                    print(f"    {line}")
                total = len(rendered.splitlines())
                if total > 8:
                    print(f"    ... ({total} 行)")

            qa_ready_tables.update(
                manifest.jobs[job_name].outputs or {job_name}
            )

    if checks:
        print(f"\n--- 校验检查 ({len(checks)} 项) ---")
        for check in checks:
            line = f"  [{check['method']}] {qa_db}.{check['table']}"
            partition_col = check.get("partition_col")
            partition_value = check.get("partition_value")
            if partition_col and partition_value is not None:
                line = f"{line} WHERE {partition_col} = '{partition_value}'"
            print(line)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="执行 refactor shadow-run 计划"
    )
    parser.add_argument("--plan", required=True, help="验证计划 JSON 路径")
    parser.add_argument(
        "--output",
        default=None,
        help="结果 JSON 路径，默认写入 plan 同目录 shadow_run_result.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只输出执行计划，不连接数据库"
    )
    parser.add_argument(
        "--timing-detail",
        "--profile",
        action="store_true",
        dest="timing_detail",
        help="记录每次 job invocation/slice 的耗时明细",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="shadow-run 全局 mysql 并发度, 默认 1",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="每个 mysql 会话批量执行的 slice 数, 默认 1",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plan_path = Path(args.plan)
    output_path = (
        Path(args.output)
        if args.output
        else plan_path.parent / "shadow_run_result.json"
    )
    try:
        persisted_plan = load_persisted_verification_plan(plan_path)
        persisted_plan = require_fresh_plan(
            plan_path,
            root=_project_root(),
            project=persisted_plan["project"],
        )
    except ArtifactFormatError as exc:
        raise SystemExit(str(exc)) from None
    snapshot = persisted_plan.get("analysis_snapshot") or {}
    provenance = {
        "workspace_fingerprint": snapshot.get("workspace_fingerprint"),
        "plan_fingerprint": persisted_plan.get("plan_fingerprint"),
    }
    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=provenance,
        dry_run=args.dry_run,
        timing_detail=args.timing_detail,
        parallel=args.parallel,
        batch_size=args.batch_size,
    )
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
