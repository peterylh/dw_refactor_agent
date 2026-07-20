from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    _aggregate_metric_sources,
    _inject_upstream_metric_groups,
    run_inspection_pipeline,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    TableInspectResult,
)
from tests.case_matrix import case_matrix


def _fact_result(
    table_name,
    *,
    process="",
    atomic=(),
    derived=(),
    dimensions=(),
    entities=(),
    grain=None,
    validation=None,
    inferred_layer="DWD",
):
    return TableInspectResult(
        table_name=table_name,
        declared_layer="DWD",
        inferred_layer=inferred_layer,
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        business_process=process,
        columns={
            "atomic_metrics": list(atomic),
            "derived_metrics": list(derived),
            "calculated_metrics": [],
            "dimensions": list(dimensions),
            "others": [],
        },
        entities=list(entities),
        grain=grain or {},
        validation=validation or {},
    )


@case_matrix(
    ("upstream_tables", "detected_tables", "expected_tables"),
    [
        (
            ["analytics.order_detail"],
            ["order_detail"],
            ["analytics.order_detail"],
        ),
        (["cat1.db.orders", "cat2.db.orders"], ["orders"], []),
    ],
    ids=("unique-short", "ambiguous-short"),
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


@case_matrix(
    ("sql", "consumer_identity", "expected"),
    [
        (
            """
            SELECT SUM(amount) AS total_amount,
                   AVG(rating) AS avg_rating,
                   COUNT(order_id) AS order_count,
                   SUM(CASE WHEN status = 'PAID' THEN amount ELSE 0 END)
                       AS paid_amount
            FROM orders
            """,
            None,
            {"total_amount": {"amount"}, "avg_rating": {"rating"}},
        ),
        (
            "WITH unused AS (SELECT SUM(amount) AS total_amount FROM source) "
            "INSERT INTO target SELECT amount AS total_amount FROM source",
            None,
            {},
        ),
        ('SELECT "unterminated', None, {}),
        (
            "INSERT INTO staging SELECT SUM(amount) AS total_amount FROM source;"
            "INSERT INTO target SELECT amount AS total_amount FROM source",
            "analytics.target",
            {},
        ),
        (
            "SELECT SUM(amount) AS total_amount FROM source;"
            "INSERT INTO target SELECT amount AS total_amount FROM source",
            "analytics.target",
            {},
        ),
    ],
    ids=("direct", "unused-cte", "malformed", "multi-target", "auxiliary"),
)
def test_aggregate_metric_sources_requires_direct_non_key_sum_or_avg(
    sql,
    consumer_identity,
    expected,
):
    assert (
        _aggregate_metric_sources(
            sql,
            consumer_identity=consumer_identity,
        )
        == expected
    )


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
        for index in (1, 2, 3)
    ]
    monkeypatch.setattr(
        flow_module,
        "build_contexts",
        lambda *args, **kwargs: dwd_contexts + dws_contexts,
    )
    batch_sizes = []

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
                failed_reinspection = (
                    context.table_name == "summary_2"
                    and context.upstream_metric_groups
                )
                results.append(
                    TableInspectResult(
                        table_name=context.table_name,
                        declared_layer=context.layer,
                        inferred_layer=(
                            "OTHER"
                            if failed_reinspection
                            else (
                                "DWS"
                                if context.upstream_metric_groups
                                else "DWD"
                            )
                        ),
                        table_type=(
                            "other" if failed_reinspection else "fact"
                        ),
                        confidence=0.0 if failed_reinspection else 0.9,
                        reasoning_steps=(
                            ["分类异常: transient failure"]
                            if failed_reinspection
                            else []
                        ),
                        first_attempt_inferred_layer=(
                            "DWS" if context.upstream_metric_groups else "DWD"
                        ),
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

    assert batch_sizes == [6, 2]
    assert [context.table_name for context in bundle.dws_contexts] == [
        "summary_1"
    ]
    assert {"summary_2", "summary_3"}.issubset(
        {context.table_name for context in bundle.dwd_contexts}
    )
    assert dws_contexts[0].upstream_metric_groups["cat1.db.orders"][
        "atomic_metrics"
    ] == ["metric_1"]
    summary_result = next(
        result for result in bundle.results if result.table_name == "summary_1"
    )
    assert summary_result.inferred_layer == "DWS"
    assert summary_result.first_attempt_inferred_layer == "DWD"
    failed_result = next(
        result for result in bundle.results if result.table_name == "summary_2"
    )
    assert failed_result.inferred_layer == "DWD"
    assert failed_result.first_attempt_inferred_layer == "DWD"
    assert failed_result.status == "blocked"
    assert failed_result.validation[METRIC_CONTEXT_REINSPECTION_ERROR_KEY] == [
        "upstream metric context reinspection failed"
    ]


def test_inspection_pipeline_repairs_upstream_metric_and_merges_reinspection(
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.metadata_flow as flow_module

    source_context = TableContext(
        table_name="customer_interactions",
        table_identity="analytics.customer_interactions",
        layer="DWD",
        ddl=(
            "CREATE TABLE customer_interactions "
            "(interaction_id BIGINT, satisfaction_rating STRING);"
        ),
        etl_sql="",
        upstream_tables=[],
        downstream_tables=["analytics.agent"],
    )
    consumer_context = TableContext(
        table_name="agent",
        table_identity="analytics.agent",
        layer="DWD",
        ddl=(
            "CREATE TABLE agent "
            "(agent_id BIGINT, avg_satisfaction_rating DOUBLE);"
        ),
        etl_sql=(
            "INSERT INTO agent "
            "SELECT agent_id, "
            "AVG(satisfaction_rating) AS avg_satisfaction_rating "
            "FROM customer_interactions GROUP BY agent_id"
        ),
        upstream_tables=["analytics.customer_interactions"],
        downstream_tables=[],
        column_lineage=[
            {
                "source": (
                    "analytics.customer_interactions.satisfaction_rating"
                ),
                "target": "analytics.agent.avg_satisfaction_rating",
            }
        ],
    )
    monkeypatch.setattr(
        flow_module,
        "build_contexts",
        lambda *args, **kwargs: [source_context, consumer_context],
    )
    batch_sizes = []

    class FakeInspector:
        def inspect_batch(self, contexts):
            batch_sizes.append(len(contexts))
            if len(batch_sizes) == 1:
                return [
                    _fact_result(
                        "customer_interactions",
                        process="CUSTOMER_INTERACTION",
                        dimensions=[
                            {"name": "interaction_id", "data_type": "BIGINT"},
                            {
                                "name": "satisfaction_rating",
                                "data_type": "STRING",
                            },
                        ],
                        entities=[
                            {
                                "code": "INTERACTION",
                                "type": "primary",
                                "key_columns": ["interaction_id"],
                            }
                        ],
                    ),
                    _fact_result(
                        "agent",
                        process="CUSTOMER_INTERACTION",
                        derived=[
                            {
                                "name": "avg_satisfaction_rating",
                                "base_metric": "satisfaction_rating",
                                "base_metric_table": (
                                    "analytics.customer_interactions"
                                ),
                                "business_process": "CUSTOMER_INTERACTION",
                            }
                        ],
                        dimensions=[{"name": "agent_id"}],
                        entities=[
                            {
                                "code": "AGENT",
                                "type": "primary",
                                "key_columns": ["agent_id"],
                            }
                        ],
                        grain={"entities": ["AGENT"]},
                        validation={
                            "invalid_base_metrics": [
                                (
                                    "avg_satisfaction_rating:"
                                    "customer_interactions."
                                    "satisfaction_rating"
                                )
                            ]
                        },
                    ),
                ]
            assert contexts == [consumer_context]
            assert consumer_context.upstream_metric_groups[
                "analytics.customer_interactions"
            ]["atomic_metrics"] == ["satisfaction_rating"]
            return [
                _fact_result(
                    "agent",
                    process="AGENT_PERFORMANCE",
                    derived=[
                        {
                            "name": "avg_satisfaction_rating",
                            "base_metric": "satisfaction_rating",
                            "base_metric_table": (
                                "analytics.customer_interactions"
                            ),
                            "business_process": "AGENT_PERFORMANCE",
                        }
                    ],
                    dimensions=[{"name": "agent_id"}],
                    entities=[
                        {
                            "code": "EMPLOYEE",
                            "type": "foreign",
                            "key_columns": ["agent_id"],
                        }
                    ],
                    grain={"entities": ["EMPLOYEE"]},
                    validation={
                        "inconsistent_upstream_metric_layers": [
                            "avg_satisfaction_rating"
                        ]
                    },
                )
            ]

    def metric_groups(result):
        return {
            group: [
                item["name"]
                for item in result.columns.get(group) or []
                if isinstance(item, dict) and item.get("name")
            ]
            for group in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            )
        }

    bundle = run_inspection_pipeline(
        "demo",
        {},
        FakeInspector(),
        metric_group_builder=metric_groups,
        result_enricher=lambda results, contexts: None,
    )

    assert batch_sizes == [2, 1]
    source_result = next(
        result
        for result in bundle.results
        if result.table_name == "customer_interactions"
    )
    consumer_result = next(
        result for result in bundle.results if result.table_name == "agent"
    )
    assert [item["name"] for item in source_result.atomic_metrics] == [
        "satisfaction_rating"
    ]
    assert source_result.atomic_metrics[0]["inference_source"] == (
        "consumer_aggregate_evidence"
    )
    assert source_result.resume_eligible is False
    assert [item["name"] for item in source_result.dimensions] == [
        "interaction_id"
    ]
    assert consumer_result.inferred_layer == "DWS"
    assert consumer_result.status == "passed"
    assert consumer_result.business_process == "CUSTOMER_INTERACTION"
    assert consumer_result.entities[0]["code"] == "AGENT"
    assert consumer_result.grain == {"entities": ["AGENT"]}
    assert consumer_result.derived_metrics[0]["business_process"] == (
        "CUSTOMER_INTERACTION"
    )


def test_inspection_pipeline_propagates_until_stable_and_persists_final(
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.metadata_flow as flow_module

    names = ["a", "b", "c", "d"]
    contexts = []
    for index, name in enumerate(names):
        contexts.append(
            TableContext(
                table_name=name,
                table_identity=f"analytics.{name}",
                layer="DWD",
                ddl=(
                    f"CREATE TABLE {name} "
                    f"({name}_id BIGINT, metric_{name} BIGINT);"
                ),
                etl_sql=(
                    ""
                    if index == 0
                    else (
                        f"INSERT INTO {name} "
                        f"SELECT {name}_id, metric_{name} "
                        f"FROM {names[index - 1]}"
                    )
                ),
                upstream_tables=(
                    [] if index == 0 else [f"analytics.{names[index - 1]}"]
                ),
                downstream_tables=(
                    []
                    if index == len(names) - 1
                    else [f"analytics.{names[index + 1]}"]
                ),
            )
        )
    monkeypatch.setattr(
        flow_module,
        "build_contexts",
        lambda *args, **kwargs: contexts,
    )
    batch_sizes = []
    finalized = []

    class FakeInspector:
        validate_publication_contract = False

        def inspect_batch(self, batch_contexts):
            batch_sizes.append(len(batch_contexts))
            results = []
            for context in batch_contexts:
                has_metric_evidence = context.table_name == "a" or bool(
                    context.upstream_metric_groups
                )
                metric = {"name": f"metric_{context.table_name}"}
                results.append(
                    _fact_result(
                        context.table_name,
                        process="DEMO",
                        atomic=[metric] if has_metric_evidence else [],
                        dimensions=[{"name": f"{context.table_name}_id"}]
                        + ([] if has_metric_evidence else [metric]),
                        entities=[
                            {
                                "code": context.table_name.upper(),
                                "type": "primary",
                                "key_columns": [f"{context.table_name}_id"],
                            }
                        ],
                        grain={"entities": [context.table_name.upper()]},
                    )
                )
            return results

        def persist_finalized_results(self, pairs):
            finalized.extend(pairs)

    def metric_groups(result):
        return {
            "atomic_metrics": [item["name"] for item in result.atomic_metrics],
            "derived_metrics": [],
            "calculated_metrics": [],
        }

    bundle = run_inspection_pipeline(
        "demo",
        {},
        FakeInspector(),
        metric_group_builder=metric_groups,
        result_enricher=lambda results, contexts_by_name: [
            result.reasoning_steps.append("finalized") for result in results
        ],
    )

    assert batch_sizes == [4, 1, 1, 1]
    assert all(result.status == "passed" for result in bundle.results)
    assert [ctx.table_name for ctx, _result in finalized] == names
    assert all(
        result.reasoning_steps[-1] == "finalized" for _ctx, result in finalized
    )
