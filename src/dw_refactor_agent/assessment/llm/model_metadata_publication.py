"""Shared filesystem lock for metadata publication workflows."""

from __future__ import annotations

import fcntl
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dw_refactor_agent.assessment.llm.model_metadata_runtime import (
    project_root,
)
from dw_refactor_agent.config import PROJECT_CONFIG

_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()
_LOCAL = threading.local()


def _process_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.RLock())


def metadata_publication_lock_path(project: str) -> Path:
    config = PROJECT_CONFIG.get(project)
    if not config:
        raise KeyError(f"未知项目: {project}")
    project_dir = project_root() / str(config["dir"])
    return (
        project_dir / "artifacts" / "assessment" / ".metadata_publication.lock"
    )


@contextmanager
def metadata_publication_lock(project: str) -> Iterator[None]:
    """Serialize metadata CAS validation, rendering, and installation."""
    path = metadata_publication_lock_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    depths = getattr(_LOCAL, "depths", None)
    if depths is None:
        depths = {}
        _LOCAL.depths = depths
    with _process_lock(path):
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield
            finally:
                depths[key] -= 1
            return
        with path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            depths[key] = 1
            try:
                yield
            finally:
                depths.pop(key, None)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
