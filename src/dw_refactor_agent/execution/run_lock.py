"""Project-scoped advisory lock for task-run SQL execution."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path

from dw_refactor_agent.config import project_artifact_dir


class ProjectRunLockError(RuntimeError):
    """Raised when another SQL execution owns the project lock."""


def project_run_lock_path(project: str) -> Path:
    """Return the shared advisory lock path for one warehouse project."""
    artifact_dir = project_artifact_dir(project, "execution")
    if artifact_dir is None:
        raise KeyError("unknown project: {}".format(project))
    return artifact_dir / "task_run.lock"


@contextmanager
def project_run_lock(project: str):
    """Fail immediately if another task_run is mutating this project."""
    lock_path = project_run_lock_path(project)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProjectRunLockError(
                "another task_run SQL execution is active for project "
                "{!r}".format(project)
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
