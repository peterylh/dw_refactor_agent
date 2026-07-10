from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.metadata_flow import (
    _inject_upstream_metric_groups,
)


def test_inject_upstream_metric_groups_matches_qualified_table_names():
    context = TableContext(
        table_name="sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=["analytics.order_detail"],
        downstream_tables=[],
    )
    groups = {
        "atomic_metrics": ["subtotal"],
        "derived_metrics": [],
        "calculated_metrics": [],
    }

    _inject_upstream_metric_groups(
        [context],
        {"order_detail": groups},
    )

    assert context.upstream_metric_groups == {
        "analytics.order_detail": groups,
    }
