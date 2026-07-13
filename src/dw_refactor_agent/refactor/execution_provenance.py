"""Lock and database marker contracts for one shadow execution."""

from __future__ import annotations

import fcntl
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError

EXECUTION_MARKER_TABLE = "__dw_refactor_execution_marker"


def _lock_path(plan_path: Path) -> Path:
    plan_path = Path(plan_path).resolve()
    for parent in plan_path.parents:
        if parent.name == "refactor_runs":
            project_name = parent.parent.parent.name
            safe_project = re.sub(r"[^A-Za-z0-9_.-]", "_", project_name)
            return (
                Path(tempfile.gettempdir())
                / "dw_refactor_agent_locks"
                / f"{safe_project}.shadow_execution.lock"
            )
    return plan_path.parent / ".shadow_execution.lock"


@contextmanager
def project_execution_lock(plan_path: Path):
    """Prevent concurrent shadow mutation or compare for one QA project."""
    lock_path = _lock_path(plan_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ArtifactFormatError(
                "another shadow-run or compare is active for this project"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def execution_marker_sql(
    qa_db: str,
    *,
    execution_id: str,
    plan_fingerprint: str,
    workspace_fingerprint: str,
) -> str:
    """Return SQL that publishes the only valid execution in the QA DB."""
    return f"""\
CREATE TABLE IF NOT EXISTS {qa_db}.{EXECUTION_MARKER_TABLE} (
    marker_key VARCHAR(32) NOT NULL,
    execution_id VARCHAR(64) NOT NULL,
    plan_fingerprint VARCHAR(80) NOT NULL,
    workspace_fingerprint VARCHAR(80) NOT NULL,
    completed_at DATETIME NOT NULL
) ENGINE=OLAP
UNIQUE KEY(marker_key)
DISTRIBUTED BY HASH(marker_key) BUCKETS 1
PROPERTIES ("replication_num" = "1");
INSERT INTO {qa_db}.{EXECUTION_MARKER_TABLE}
    (marker_key, execution_id, plan_fingerprint,
     workspace_fingerprint, completed_at)
VALUES
    ('current', '{execution_id}', '{plan_fingerprint}',
     '{workspace_fingerprint}', NOW());
"""


def execution_marker_select_sql() -> str:
    return (
        "SELECT execution_id, plan_fingerprint, workspace_fingerprint "
        f"FROM {EXECUTION_MARKER_TABLE} "
        "WHERE marker_key = 'current' LIMIT 1"
    )
