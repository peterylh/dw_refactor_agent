"""SQL executors for planned task invocations."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Callable

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.execution.invocation import (
    TaskInvocation,
    render_invocation_sql,
)
from dw_refactor_agent.refactor.shadow_rewrite import (
    RewriteContext,
    rewrite_shadow_sql,
)


class SqlExecutionError(RuntimeError):
    """Raised when a planned SQL invocation fails."""


class DirectSqlExecutor:
    """Execute planned invocations against a configured database."""

    def __init__(
        self,
        mysql_cmd: list[str],
        db_name: str,
        *,
        before_execute: Callable[[TaskInvocation], None] | None = None,
        timeout: int = 600,
    ):
        self.mysql_cmd = list(mysql_cmd)
        self.db_name = db_name
        self.before_execute = before_execute
        self.timeout = timeout

    def execute(self, invocation: TaskInvocation) -> None:
        if self.before_execute is not None:
            self.before_execute(invocation)
        sql_text = invocation.resolved_sql
        if sql_text is None:
            sql_text = Path(invocation.sql_path).read_text(
                encoding=TEXT_ENCODING
            )
        full_sql = render_invocation_sql(invocation, sql_text)
        result = subprocess.run(
            self.mysql_cmd + [self.db_name],
            input=full_sql,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise SqlExecutionError(
                f"[{invocation.job_name}] [FAIL]\n  {result.stderr.strip()}"
            )


class ShadowSqlExecutor:
    """Rewrite and execute planned invocations against a QA database."""

    def __init__(
        self,
        *,
        context: RewriteContext,
        qa_ready_tables: set[str],
        run_sql_text: Callable[..., str],
    ):
        self.context = context
        self.qa_db = context.qa_db
        self.qa_ready_tables = qa_ready_tables
        self.run_sql_text = run_sql_text

    def render(self, invocation: TaskInvocation) -> str:
        sql_text = invocation.resolved_sql
        if sql_text is None:
            sql_text = Path(invocation.sql_path).read_text(
                encoding=TEXT_ENCODING
            )
        context = replace(
            self.context,
            qa_ready_tables=set(self.qa_ready_tables),
        )
        rewritten = rewrite_shadow_sql(sql_text, context)
        return render_invocation_sql(invocation, rewritten)

    def execute(self, invocation: TaskInvocation) -> None:
        self.run_sql_text(self.render(invocation), self.qa_db, qa=True)

    def execute_batch(self, invocations: list[TaskInvocation]) -> None:
        rendered_sql = []
        for invocation in invocations:
            sql = self.render(invocation).rstrip()
            if sql and not sql.endswith(";"):
                sql = f"{sql};"
            rendered_sql.append(sql)
        full_sql = "\n".join(rendered_sql)
        if full_sql.strip():
            self.run_sql_text(full_sql, self.qa_db, qa=True)
