"""Planned task execution invocations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskInvocation:
    job_name: str
    sql_path: Path
    params: dict[str, str]
    full_refresh: bool
    strategy: str


def _sql_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def render_invocation_sql(invocation: TaskInvocation, sql_text: str) -> str:
    """Return SQL text with execution parameters set explicitly."""
    statements = [
        f"SET @{param} = '{_sql_string(value)}';"
        for param, value in invocation.params.items()
    ]
    statements.append(
        f"SET @full_refresh = {1 if invocation.full_refresh else 0};"
    )
    statements.append(sql_text)
    return "\n".join(statements)
