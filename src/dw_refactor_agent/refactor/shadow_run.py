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
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from datetime import datetime, timezone
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import dw_refactor_agent.config as config
from dw_refactor_agent.config import PROJECT_ROOT, get_mysql_cmd
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.execution.sql_executor import ShadowSqlExecutor
from dw_refactor_agent.execution.thread_pool import shutdown_executor
from dw_refactor_agent.lineage.job_dag import JobDAG
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
)
from dw_refactor_agent.refactor.execution_provenance import (
    execution_marker_sql,
    project_execution_lock,
)
from dw_refactor_agent.refactor.plan_artifact import (
    load_persisted_verification_plan,
    require_fresh_plan,
    require_fresh_plan_bundle,
)
from dw_refactor_agent.refactor.shadow_manifest import (
    PrefillMode,
    compile_shadow_manifest,
    manifest_summary,
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


def _execute_ddl_statement(statement: str, qa_db: str) -> None:
    before_refs, after_refs = _alter_table_wait_refs(statement, qa_db)
    known_job_ids_by_ref = {}

    for db_name, table_name in before_refs:
        jobs = _wait_for_table_alter_jobs(db_name, table_name, qa=True)
        known_job_ids_by_ref[(db_name, table_name)] = _job_ids(jobs)

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


def _check_with_compare_anchor(check: dict, verification: dict) -> dict:
    if check.get("partition_col") or check.get("partition_value") is not None:
        return dict(check)
    anchor = (verification.get("compare_anchors") or {}).get(
        check.get("table")
    ) or {}
    time_column = anchor.get("time_column")
    anchor_value = anchor.get("anchor_time_value")
    if not time_column or anchor_value is None:
        return dict(check)
    resolved = dict(check)
    resolved["partition_col"] = time_column
    resolved["partition_value"] = anchor_value
    return resolved


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


def _job_dag_artifact_path(project: str, root: Path) -> Path:
    cfg = config.core.PROJECT_CONFIG.get(project)
    if cfg and cfg.get("dir"):
        project_dir = Path(cfg["dir"])
        if not project_dir.is_absolute():
            project_dir = Path(root) / project_dir
    else:
        project_dir = Path(root) / "warehouses" / project
    return project_dir / "artifacts" / "lineage" / "job_dag.json"


def _serial_job_dependencies(
    jobs_to_run: list[dict],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    job_names = [job["job"] for job in jobs_to_run]
    in_degree = dict.fromkeys(job_names, 0)
    adj = {job_name: [] for job_name in job_names}
    for upstream, downstream in zip(job_names, job_names[1:]):
        adj[upstream].append(downstream)
        in_degree[downstream] += 1
    return in_degree, adj


def _job_dependencies_from_plan(
    plan: dict,
    root: Path,
) -> tuple[dict[str, int], dict[str, list[str]], str, list[str]]:
    jobs_to_run = plan.get("jobs_to_run", [])
    job_names = [job["job"] for job in jobs_to_run]
    job_set = set(job_names)
    if len(job_names) <= 1:
        return (
            dict.fromkeys(job_names, 0),
            {job_name: [] for job_name in job_names},
            "trivial",
            [],
        )

    job_dependencies = plan.get("job_dependencies")
    if isinstance(job_dependencies, dict):
        in_degree = dict.fromkeys(job_names, 0)
        adj = {job_name: [] for job_name in job_names}
        for downstream, upstreams in job_dependencies.items():
            if downstream not in job_set:
                continue
            for upstream in upstreams or []:
                if upstream not in job_set:
                    continue
                adj[upstream].append(downstream)
                in_degree[downstream] += 1
        return in_degree, adj, "plan", []

    dag_path = _job_dag_artifact_path(str(plan.get("project") or ""), root)
    if dag_path.exists():
        dag = JobDAG.load(dag_path)
        in_degree, adj = dag.compute_in_degree(job_set)
        return in_degree, adj, "lineage_dag", []

    in_degree, adj = _serial_job_dependencies(jobs_to_run)
    warning = (
        f"job DAG artifact not found: {dag_path}; "
        "falling back to serial jobs_to_run order"
    )
    return in_degree, adj, "serial_fallback", [warning]


def _augment_manifest_dependencies(
    in_degree: dict[str, int],
    adj: dict[str, list[str]],
    manifest: dict,
) -> bool:
    augmented = False
    producers = manifest.get("producers") or {}
    for consumer, job_manifest in (manifest.get("jobs") or {}).items():
        if consumer not in in_degree:
            continue
        for table in job_manifest.get("required_qa_tables") or []:
            producer = producers.get(table)
            if (
                not producer
                or producer == consumer
                or producer not in adj
                or consumer in adj[producer]
            ):
                continue
            adj[producer].append(consumer)
            in_degree[consumer] += 1
            augmented = True
    return augmented


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
    job_manifest: dict,
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
    invocation_parallel = 1 if job_manifest.get("self_read") else parallel

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
                context=job_manifest["context"],
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
        qa_ready_tables.update(job_manifest.get("outputs") or {job_name})

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
    manifest: dict,
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
    in_degree, adj, scheduler, warnings = _job_dependencies_from_plan(
        plan,
        root,
    )
    if _augment_manifest_dependencies(in_degree, adj, manifest):
        scheduler = f"{scheduler}+manifest"
    job_by_name = {job["job"]: job for job in jobs_to_run}
    index_by_name = {
        job["job"]: index for index, job in enumerate(jobs_to_run, 1)
    }
    remaining = set(job_by_name)
    ready = sorted(
        [
            job_name
            for job_name in remaining
            if in_degree.get(job_name, 0) == 0
        ],
        key=lambda job_name: index_by_name[job_name],
    )
    running = {}
    failed = False

    phase["scheduler"] = scheduler
    if warnings:
        phase["warnings"] = list(warnings)
        for warning in warnings:
            _log(f"  警告: {warning}")

    def submit_job(executor_pool, job_name: str) -> None:
        remaining.remove(job_name)
        future = executor_pool.submit(
            _execute_shadow_job,
            job_by_name[job_name],
            job_manifest=(manifest.get("jobs") or {}).get(job_name, {}),
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
        running[future] = job_name

    executor_pool = ThreadPoolExecutor(max_workers=min(parallel, job_count))
    try:
        while ready or running:
            while ready and not failed:
                submit_job(executor_pool, ready.pop(0))
            if not running:
                break
            done, _pending = wait(
                list(running),
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                job_name = running.pop(future)
                try:
                    job_result = future.result()
                except Exception as exc:
                    job_result = _finish_timing(
                        _job_result(
                            job_by_name[job_name],
                            "failed",
                            str(exc),
                            invocation_count=0,
                            **_job_batch_kwargs(0, parallel, batch_size),
                        ),
                        _start_timing(),
                    )
                job_results_by_name[job_name] = job_result
                if job_result.get("status") != "success":
                    failed = True
                    phase["status"] = "failed"
                    continue
                if failed:
                    continue
                for downstream in sorted(
                    adj.get(job_name, []),
                    key=lambda item: index_by_name.get(item, 0),
                ):
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0 and downstream in remaining:
                        ready.append(downstream)
                ready.sort(key=lambda item: index_by_name[item])
    finally:
        shutdown_executor(executor_pool)

    if remaining and not failed:
        failed = True
        phase["status"] = "failed"
        skip_reason = "job dependency cycle or unsatisfied dependency"
        for job_name in sorted(
            remaining, key=lambda item: index_by_name[item]
        ):
            job_results_by_name[job_name] = _skipped_shadow_job_result(
                job_by_name[job_name],
                skip_reason,
                parallel=parallel,
                batch_size=batch_size,
                timing_detail=timing_detail,
            )

    if failed:
        skip_reason = "upstream job failed"
        for job_name in sorted(
            remaining, key=lambda item: index_by_name[item]
        ):
            if job_name in job_results_by_name:
                continue
            job_results_by_name[job_name] = _skipped_shadow_job_result(
                job_by_name[job_name],
                skip_reason,
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
        "project_db": plan.get("project_db"),
        "qa_db": plan["qa_db"],
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
) -> tuple[dict | None, dict]:
    timer = _start_timing()
    try:
        manifest = compile_shadow_manifest(plan, root, planner)
        blockers = list(manifest.get("blockers") or [])
        phase = {
            "name": "compile_shadow_manifest",
            "status": "failed"
            if blockers
            else ("dry_run" if dry_run else "success"),
            "blockers": blockers,
            "warnings": list(manifest.get("warnings") or []),
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
    manifest: dict,
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
    for action in manifest.get("prefill_actions") or []:
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
    manifest: dict,
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

    reset_timer = _start_timing()
    reset_phase = _finish_timing(
        {
            "name": "reset_qa_db",
            "status": "dry_run",
            "actions": [
                f"DROP DATABASE IF EXISTS {qa_db}",
                f"CREATE DATABASE {qa_db}",
            ],
        },
        reset_timer,
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

    return [reset_phase, create_phase, prefill_phase, ddl_phase, job_phase]


def execute_shadow_plan(
    plan: dict,
    *,
    root: Path,
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

    checks = plan.get("verification", {}).get("checks", [])
    if not _plan_anchor_tables(plan) and not checks:
        _log("  警告: 无锚点表且无校验配置")
        _log("    作业会正常执行，但后续 compare 命令没有表可对比校验")
        _log("    如果只是想确认作业不报错，可继续执行\n")

    _log("=" * 60)
    _log(f"Phase 0: 重置验证数据库 {qa_db}")
    reset_timer = _start_timing()
    reset_phase = {
        "name": "reset_qa_db",
        "status": "success",
        "actions": [
            f"DROP DATABASE IF EXISTS {qa_db}",
            f"CREATE DATABASE {qa_db}",
        ],
    }
    try:
        run_sql(
            f"DROP DATABASE IF EXISTS {qa_db}",
            "information_schema",
            qa=True,
        )
        run_sql(f"CREATE DATABASE {qa_db}", "information_schema", qa=True)
    except Exception as exc:
        _log(f"  [FAIL] 重置验证数据库失败: {exc}")
        reset_phase["status"] = "failed"
        reset_phase["error"] = str(exc)
        _finish_timing(reset_phase, reset_timer)
        phases.append(reset_phase)
        return finish_result(_failed_shadow_result(plan, phases))
    _finish_timing(reset_phase, reset_timer)
    _log(f"  {qa_db} 已重建 duration={reset_phase['duration_ms']}ms")
    phases.append(reset_phase)

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
            try:
                for statement in statements:
                    try:
                        _execute_ddl_statement(statement, qa_db)
                    except Exception as exc:
                        statement_results.append(
                            _ddl_statement_result(
                                statement,
                                "failed",
                                str(exc),
                            )
                        )
                        raise
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
        "execution_id": execution_id,
        "workspace_fingerprint": workspace_digest,
        "plan_fingerprint": plan_digest,
    }
    with project_execution_lock(plan_path):
        atomic_write_json(
            output_path,
            {
                **common_result,
                "status": "running",
                "started_at": wrapper_timer["started_at"],
            },
        )
        result = execute_shadow_plan(
            plan,
            root=bundle.root,
            dry_run=dry_run,
            timing_detail=timing_detail,
            parallel=parallel,
            batch_size=batch_size,
        )
        if result.get("status") == "completed" and not dry_run:
            marker_timer = _start_timing()
            try:
                run_sql_text(
                    execution_marker_sql(
                        plan["qa_db"],
                        execution_id=execution_id,
                        plan_fingerprint=plan_digest,
                        workspace_fingerprint=workspace_digest,
                    ),
                    db=plan["qa_db"],
                    qa=True,
                )
                marker_phase = {
                    "name": "publish_execution_marker",
                    "status": "success",
                }
            except Exception as exc:
                result["status"] = "failed"
                result["error"] = (
                    f"failed to publish QA execution marker: {exc}"
                )
                marker_phase = {
                    "name": "publish_execution_marker",
                    "status": "failed",
                    "error": str(exc),
                }
            result.setdefault("phases", []).append(
                _finish_timing(marker_phase, marker_timer)
            )
        result.update(common_result)
        _finish_timing(result, wrapper_timer)
        atomic_write_json(output_path, result)
    return result


def _dry_run(plan: dict, manifest: dict, *, root: Path) -> None:
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
    verification = plan.get("verification", {})
    compare_anchors = verification.get("compare_anchors") or {}
    if compare_anchors:
        for table in sorted(compare_anchors):
            anchor = compare_anchors[table] or {}
            time_column = anchor.get("time_column")
            anchor_value = anchor.get("anchor_time_value")
            time_period = anchor.get("time_period")
            if time_column and anchor_value:
                print(
                    f"  对比范围: {table} "
                    f"WHERE {time_column} = '{anchor_value}' ({time_period})"
                )
            else:
                print(f"  对比范围: {table} 全表")
    checks = plan.get("verification", {}).get("checks", [])
    if not _plan_anchor_tables(plan) and not checks:
        print()
        print(
            "  警告: 无锚点表且无校验配置，后续 compare 命令没有表可对比校验"
        )

    print("\n--- Phase 0: 重置验证库 ---")
    print(f"  DROP DATABASE IF EXISTS {qa_db}")
    print(f"  CREATE DATABASE {qa_db}")

    print(f"\n--- Phase 1: 基线建表 ({len(baseline_ddl)} 张) ---")
    for table_name in sorted(baseline_ddl):
        print(f"  [CREATE] {qa_db}.{table_name}")

    actions = manifest.get("prefill_actions") or []
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
                job_manifest = (manifest.get("jobs") or {}).get(job_name, {})
                executor = ShadowSqlExecutor(
                    context=job_manifest["context"],
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
                (manifest.get("jobs") or {}).get(job_name, {}).get("outputs")
                or {job_name}
            )

    if checks:
        print(f"\n--- 校验检查 ({len(checks)} 项) ---")
        verification = plan.get("verification", {})
        for raw_check in checks:
            check = _check_with_compare_anchor(raw_check, verification)
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
