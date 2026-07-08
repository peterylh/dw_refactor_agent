"""ThreadPoolExecutor compatibility helpers."""

from __future__ import annotations


def shutdown_executor(executor) -> None:
    """Shutdown an executor without relying on Python 3.9-only arguments."""
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        executor.shutdown(wait=False)
