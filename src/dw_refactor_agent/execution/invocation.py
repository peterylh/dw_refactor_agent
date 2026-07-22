"""Planned task execution invocations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class TaskInvocation:
    job_name: str
    sql_path: Path
    params: dict[str, str] = field(repr=False)
    full_refresh: bool
    strategy: str
    render_inputs: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
    )
    resolved_sql: Optional[str] = field(default=None, repr=False)
    public_summary: Mapping[str, object] = field(default_factory=dict)

    @property
    def session_params(self) -> dict[str, str]:
        """Legacy SQL session variables retained for compatibility."""
        return self.params

    @property
    def public_session_params(self) -> Mapping[str, object]:
        """Return values safe for logs and serialized execution summaries."""
        value = self.public_summary.get("session_params")
        return value if isinstance(value, Mapping) else self.params


def _sql_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def render_invocation_sql(invocation: TaskInvocation, sql_text: str) -> str:
    """Return SQL text with execution parameters set explicitly."""
    statements = [
        f"SET @{param} = '{_sql_string(value)}';"
        for param, value in invocation.session_params.items()
    ]
    statements.append(
        f"SET @full_refresh = {1 if invocation.full_refresh else 0};"
    )
    statements.append(sql_text)
    return "\n".join(statements)
