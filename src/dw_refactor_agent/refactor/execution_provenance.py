"""Run-scoped local artifact locking for shadow execution and compare."""

from __future__ import annotations

import fcntl
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError


def _lock_path(plan_path: Path) -> Path:
    plan_path = Path(plan_path).resolve()
    for parent in plan_path.parents:
        if parent.name == "refactor_runs":
            project_name = parent.parent.parent.name
            relative = plan_path.relative_to(parent)
            run_id = relative.parts[0] if relative.parts else "unknown-run"
            safe_project = re.sub(r"[^A-Za-z0-9_.-]", "_", project_name)
            safe_run_id = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)
            return (
                Path(tempfile.gettempdir())
                / "dw_refactor_agent_locks"
                / f"{safe_project}.{safe_run_id}.shadow_execution.lock"
            )
    return plan_path.parent / ".shadow_execution.lock"


@contextmanager
def run_execution_lock(plan_path: Path):
    """Prevent concurrent artifact mutation for one logical refactor run."""
    lock_path = _lock_path(plan_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding=TEXT_ENCODING) as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ArtifactFormatError(
                "another shadow-run or compare is active for this run"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
