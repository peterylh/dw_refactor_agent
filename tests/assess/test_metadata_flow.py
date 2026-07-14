import pytest

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    _inject_upstream_metric_groups,
    run_inspection_pipeline,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult


@pytest.mark.parametrize(
    ("upstream_tables", "detected_tables", "expected_tables"),
    [
        (
            ["analytics.order_detail"],
            ["order_detail"],
            ["analytics.order_detail"],
        ),
        (["cat1.db.orders", "cat2.db.orders"], ["orders"], []),
        (["cat1.db.orders"], ["wrong.db.orders"], []),
    ],
    ids=("unique-short", "ambiguous-short", "wrong-qualified"),
)
def test_inject_upstream_metric_groups_identity_rules(
    upstream_tables,
    detected_tables,
    expected_tables,
):
    context = TableContext(
        table_name="sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=upstream_tables,
        downstream_tables=[],
    )
    groups = {
        "atomic_metrics": ["subtotal"],
        "derived_metrics": [],
        "calculated_metrics": [],
    }

    _inject_upstream_metric_groups(
        [context],
        {table_name: groups for table_name in detected_tables},
    )

    assert context.upstream_metric_groups == {
        table_name: groups for table_name in expected_tables
    }


def test_inspection_pipeline_reclassifies_and_preserves_metric_identity(
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.metadata_flow as flow_module
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    dwd_contexts = [
        TableContext(
            table_name="orders",
            table_identity=f"cat{index}.db.orders",
            layer="DWD",
            ddl="",
            etl_sql="",
            upstream_tables=[],
            downstream_tables=[],
        )
        for index in (1, 2, 3)
    ]
    dws_contexts = [
        TableContext(
            table_name=f"summary_{index}",
            table_identity=f"cat{index}.db.summary",
            # Cold-start mid models all carry the DWD direct-rule prior.
            layer="DWD",
            ddl="",
            etl_sql="",
            upstream_tables=[f"cat{index}.db.orders"],
            downstream_tables=[],
        )
        for index in (1, 3)
    ]
    monkeypatch.setattr(
        flow_module,
        "build_contexts",
        lambda *args, **kwargs: dwd_contexts + dws_contexts,
    )
    batch_sizes = []
    seen_reinspection_groups = []

    class FakeInspector:
        def inspect_batch(self, contexts):
            batch_sizes.append(len(contexts))
            results = []
            for context in contexts:
                if context.table_name == "orders":
                    index = int(context.table_identity[3])
                    results.append(
                        TableInspectResult(
                            table_name="orders",
                            declared_layer="DWD",
                            inferred_layer="DWD",
                            table_type="fact",
                            confidence=0.01 if index == 3 else 0.9,
                            reasoning_steps=[],
                            columns={
                                "atomic_metrics": [{"name": f"metric_{index}"}]
                            },
                        )
                    )
                    continue
                if context.upstream_metric_groups:
                    seen_reinspection_groups.append(
                        context.upstream_metric_groups
                    )
                results.append(
                    TableInspectResult(
                        table_name=context.table_name,
                        declared_layer=context.layer,
                        inferred_layer="DWS",
                        table_type="fact",
                        confidence=0.9,
                        reasoning_steps=[],
                    )
                )
            return results

    policy = LayerResolutionPolicy(mode="refresh")
    existing = {"orders": {"layer": "DWD", "table_type": "fact"}}
    bundle = run_inspection_pipeline(
        "demo",
        {},
        FakeInspector(),
        metric_group_builder=writer_module.metric_groups_for_model,
        result_enricher=lambda results, contexts: None,
        metric_result_is_eligible=lambda result: (
            writer_module._metric_result_is_eligible_for_propagation(
                result,
                existing_model=existing["orders"],
                resolution_policy=policy,
            )
        ),
    )

    assert batch_sizes == [5, 1]
    assert [context.table_name for context in bundle.dws_contexts] == [
        "summary_1",
        "summary_3",
    ]
    assert seen_reinspection_groups == [
        {
            "cat1.db.orders": {
                "atomic_metrics": ["metric_1"],
                "derived_metrics": [],
                "calculated_metrics": [],
            }
        }
    ]
