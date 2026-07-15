"""Host-stable advisory locks for physical SQL execution targets."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from dw_refactor_agent.lineage.identifiers import identifier_match_key

RUN_LOCK_DIR_ENV = "DW_REFACTOR_AGENT_RUN_LOCK_DIR"


class ExecutionRunLockError(RuntimeError):
    """Raised when another SQL execution owns the physical-target lock."""


def _canonical_execution_target(host, port, database) -> tuple[str, str, str]:
    canonical_host = str(host or "").strip().casefold()
    port_text = str(port or "").strip()
    canonical_database = identifier_match_key(database)
    if not canonical_host:
        raise ValueError("execution target host must not be empty")
    if not port_text:
        raise ValueError("execution target port must not be empty")
    try:
        canonical_port = str(int(port_text))
    except ValueError as exc:
        raise ValueError(
            "execution target port must be an integer: {!r}".format(port)
        ) from exc
    if not canonical_database:
        raise ValueError("execution target database must not be empty")
    return canonical_host, canonical_port, canonical_database


def _execution_run_lock_dir() -> Path:
    override = str(os.environ.get(RUN_LOCK_DIR_ENV) or "").strip()
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            raise ValueError(
                "{} must be an absolute path: {!r}".format(
                    RUN_LOCK_DIR_ENV,
                    override,
                )
            )
        return override_path
    return Path(tempfile.gettempdir()) / "dw_refactor_agent" / "run_locks"


def execution_target_run_lock_path(host, port, database) -> Path:
    """Return one stable advisory-lock path for a physical Doris target."""
    target = _canonical_execution_target(host, port, database)
    target_text = "\0".join(target)
    digest = hashlib.sha256(target_text.encode("utf-8")).hexdigest()[:24]
    database_prefix = re.sub(r"[^a-z0-9_.-]+", "-", target[2]).strip(".-_")
    database_prefix = (database_prefix or "database")[:48]
    return _execution_run_lock_dir() / "{}-{}.lock".format(
        database_prefix,
        digest,
    )


@contextmanager
def execution_target_run_lock(host, port, database):
    """Fail immediately if another run is mutating the same Doris target."""
    target = _canonical_execution_target(host, port, database)
    lock_path = execution_target_run_lock_path(*target)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            raise ExecutionRunLockError(
                "another task_run SQL execution is active for target "
                "{}:{}/{}".format(*target)
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
