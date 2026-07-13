from __future__ import annotations

from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.sql_executor import ShadowSqlExecutor
from dw_refactor_agent.refactor.shadow_rewrite import (
    RelationRoute,
    RewriteContext,
)


def test_shadow_executor_accepts_only_compiled_context_and_qa_readiness(
    tmp_path,
):
    sql_path = tmp_path / "sales.sql"
    sql_path.write_text(
        "INSERT INTO dm.result SELECT * FROM dm.sales;",
        encoding="utf-8",
    )
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        write_routes={"result": RelationRoute("dm_qa", "result")},
        data_routes={"sales": RelationRoute("dm_qa", "sales")},
        selected_tables={"result", "sales"},
        required_qa_tables={"sales"},
        current_job="result",
        strict=True,
    )
    executor = ShadowSqlExecutor(
        context=context,
        qa_ready_tables={"sales"},
        run_sql_text=lambda *_args, **_kwargs: "",
    )

    rendered = executor.render(
        TaskInvocation(
            job_name="result",
            sql_path=sql_path,
            params={},
            full_refresh=False,
            strategy="replay_slices",
        )
    )

    assert "INSERT INTO dm_qa.result" in rendered
    assert "FROM dm_qa.sales" in rendered
    assert context.qa_ready_tables == set()
