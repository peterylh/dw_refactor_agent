import pytest

from dw_refactor_agent.lineage.asset_graph import (
    build_asset_column_lineage,
    build_asset_self_edges,
    build_asset_table_graph,
)
from dw_refactor_agent.lineage.table_graph import (
    build_table_edge_source_files,
    build_table_graph,
    collect_table_self_edges,
)


def _column_edge(source, target, job):
    return {
        "source": {"type": "column", "id": f"{source}.id"},
        "target": {"type": "column", "id": f"{target}.id"},
        "relation_type": "direct",
        "transformation_type": "passthrough",
        "expression": "id",
        "job": job,
    }


def _v2_tables(*names):
    return [
        {
            "name": name,
            "full_name": name,
            "dataset_type": "process" if name == "t" else "managed",
            "columns": [{"name": "id", "type": "BIGINT"}],
        }
        for name in names
    ]


def two_local_t_jobs_v2():
    return {
        "format_version": 2,
        "tables": _v2_tables("src_a", "src_b", "t", "out_a", "out_b"),
        "jobs": [
            {
                "name": "job_a",
                "source_file": "mid/tasks/job_a.sql",
                "inputs": ["src_a", "t"],
                "outputs": ["t", "out_a"],
            },
            {
                "name": "job_b",
                "source_file": "mid/tasks/job_b.sql",
                "inputs": ["src_b", "t"],
                "outputs": ["t", "out_b"],
            },
        ],
        "edges": [
            _column_edge("src_a", "t", "job_a"),
            _column_edge("t", "out_a", "job_a"),
            _column_edge("src_b", "t", "job_b"),
            _column_edge("t", "out_b", "job_b"),
        ],
        "diagnostics": [],
    }


def test_same_name_local_process_tables_do_not_cross_jobs():
    upstream, downstream = build_asset_table_graph(two_local_t_jobs_v2())

    assert downstream["src_a"] == {"out_a"}
    assert downstream["src_b"] == {"out_b"}
    assert upstream["out_a"] == {"src_a"}
    assert upstream["out_b"] == {"src_b"}
    assert "out_b" not in downstream["src_a"]
    assert "out_a" not in downstream["src_b"]


def test_v1_same_name_transient_tables_safely_stay_in_source_file_jobs():
    lineage_data = {
        "tables": [{"name": "t", "is_transient": True}],
        "edges": [
            {
                "source": f"{source}.id",
                "target": f"{target}.id",
                "expression": "id",
                "source_file": f"mid/tasks/{job}.sql",
            }
            for source, target, job in (
                ("src_a", "t", "job_a"),
                ("t", "out_a", "job_a"),
                ("src_b", "t", "job_b"),
                ("t", "out_b", "job_b"),
            )
        ],
        "indirect_edges": [],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert downstream == {
        "src_a": {"out_a"},
        "src_b": {"out_b"},
    }
    assert upstream == {
        "out_a": {"src_a"},
        "out_b": {"src_b"},
    }
    assert {
        record["source"]
        for record in build_asset_column_lineage(lineage_data, "out_a")
    } == {"src_a.id"}
    assert {
        record["source"]
        for record in build_asset_column_lineage(lineage_data, "out_b")
    } == {"src_b.id"}


def test_v1_same_basename_source_files_use_full_path_process_scopes():
    lineage_data = {
        "tables": [{"name": "t", "is_transient": True}],
        "edges": [
            {
                "source": f"{source}.id",
                "target": f"{target}.id",
                "expression": "id",
                "source_file": source_file,
            }
            for source, target, source_file in (
                ("src_mid", "t", "mid/tasks/load.sql"),
                ("t", "out_mid", "mid/tasks/load.sql"),
                ("src_ads", "t", "ads/tasks/load.sql"),
                ("t", "out_ads", "ads/tasks/load.sql"),
            )
        ],
        "indirect_edges": [],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert downstream == {
        "src_ads": {"out_ads"},
        "src_mid": {"out_mid"},
    }
    assert upstream == {
        "out_ads": {"src_ads"},
        "out_mid": {"src_mid"},
    }
    assert {
        record["source"]
        for record in build_asset_column_lineage(lineage_data, "out_mid")
    } == {"src_mid.id"}
    assert {
        record["source"]
        for record in build_asset_column_lineage(lineage_data, "out_ads")
    } == {"src_ads.id"}


def test_unique_shared_process_producer_composes_across_jobs():
    lineage_data = {
        "format_version": 2,
        "tables": _v2_tables("src", "t", "out"),
        "jobs": [
            {
                "name": "prepare",
                "source_file": "mid/tasks/prepare.sql",
                "inputs": ["src"],
                "outputs": ["t"],
            },
            {
                "name": "publish",
                "source_file": "mid/tasks/publish.sql",
                "inputs": ["t"],
                "outputs": ["out"],
            },
        ],
        "edges": [
            _column_edge("src", "t", "prepare"),
            _column_edge("t", "out", "publish"),
        ],
        "diagnostics": [],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream == {"out": {"src"}}
    assert downstream == {"src": {"out"}}


def test_multiple_shared_process_producers_do_not_compose_a_path():
    lineage_data = {
        "format_version": 2,
        "tables": _v2_tables("src_a", "src_b", "t", "out"),
        "jobs": [
            {
                "name": "producer_a",
                "source_file": "mid/tasks/producer_a.sql",
                "inputs": ["src_a"],
                "outputs": ["t"],
            },
            {
                "name": "producer_b",
                "source_file": "mid/tasks/producer_b.sql",
                "inputs": ["src_b"],
                "outputs": ["t"],
            },
            {
                "name": "consumer",
                "source_file": "mid/tasks/consumer.sql",
                "inputs": ["t"],
                "outputs": ["out"],
            },
        ],
        "edges": [
            _column_edge("src_a", "t", "producer_a"),
            _column_edge("src_b", "t", "producer_b"),
            _column_edge("t", "out", "consumer"),
        ],
        "diagnostics": [],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert "out" not in downstream.get("src_a", set())
    assert "out" not in downstream.get("src_b", set())
    assert "src_a" not in upstream.get("out", set())
    assert "src_b" not in upstream.get("out", set())


def test_missing_shared_process_producer_does_not_compose_a_path():
    lineage_data = {
        "format_version": 2,
        "tables": _v2_tables("t", "out"),
        "jobs": [
            {
                "name": "consumer",
                "source_file": "mid/tasks/consumer.sql",
                "inputs": ["t"],
                "outputs": ["out"],
            }
        ],
        "edges": [_column_edge("t", "out", "consumer")],
        "diagnostics": [
            {
                "code": "UNRESOLVED_DATASET_PRODUCER",
                "dataset": "t",
                "reason": "not_found",
                "consumer_jobs": ["consumer"],
                "candidate_producer_jobs": [],
            }
        ],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream.get("out", set()) == set()
    assert "out" not in downstream.get("t", set())


def test_same_name_local_process_conditions_stay_in_their_jobs():
    lineage_data = two_local_t_jobs_v2()
    lineage_data["edges"].extend(
        [
            {
                "source": {"type": "column", "id": f"{source}.status"},
                "target": {"type": "column", "id": "t.status"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "status",
                "job": job,
            }
            for source, job in (("src_a", "job_a"), ("src_b", "job_b"))
        ]
    )
    lineage_data["edges"].extend(
        [
            {
                "source": {"type": "column", "id": "t.status"},
                "target": {"type": "table", "id": output},
                "relation_type": "filter",
                "transformation_type": "filter",
                "expression": "status = 'READY'",
                "job": job,
            }
            for output, job in (("out_a", "job_a"), ("out_b", "job_b"))
        ]
    )

    out_a = build_asset_column_lineage(lineage_data, "out_a")
    out_b = build_asset_column_lineage(lineage_data, "out_b")

    assert {
        condition["source"]
        for record in out_a
        for condition in record["condition_lineage"]
    } == {"src_a.status"}
    assert {
        condition["source"]
        for record in out_b
        for condition in record["condition_lineage"]
    } == {"src_b.status"}


def test_v2_conditions_attach_only_to_column_edges_from_the_same_job():
    lineage_data = {
        "format_version": 2,
        "tables": _v2_tables("src_a", "src_b", "out"),
        "jobs": [
            {
                "name": job,
                "source_file": f"mid/tasks/{job}.sql",
                "inputs": [source],
                "outputs": ["out"],
            }
            for source, job in (("src_a", "job_a"), ("src_b", "job_b"))
        ],
        "edges": [
            _column_edge(source, "out", job)
            for source, job in (("src_a", "job_a"), ("src_b", "job_b"))
        ]
        + [
            {
                "source": {"type": "column", "id": f"{source}.status"},
                "target": {"type": "table", "id": "out"},
                "relation_type": "filter",
                "transformation_type": "filter",
                "expression": "status = 'READY'",
                "job": job,
            }
            for source, job in (("src_a", "job_a"), ("src_b", "job_b"))
        ],
        "diagnostics": [],
    }

    lineage = build_asset_column_lineage(lineage_data, "out")

    assert {
        record["job"]: {
            condition["source"] for condition in record["condition_lineage"]
        }
        for record in lineage
    } == {
        "job_a": {"src_a.status"},
        "job_b": {"src_b.status"},
    }


def test_build_table_graph_keeps_transient_tables_raw():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.order_id",
                "target": "tmp_orders_stage.order_id",
            },
            {
                "source": "tmp_orders_stage.order_id",
                "target": "dws_orders.order_id",
            },
        ],
        "indirect_edges": [],
    }

    upstream, downstream = build_table_graph(
        lineage_data["edges"],
        lineage_data["indirect_edges"],
    )

    assert upstream["tmp_orders_stage"] == {"dwd_orders"}
    assert upstream["dws_orders"] == {"tmp_orders_stage"}
    assert downstream["dwd_orders"] == {"tmp_orders_stage"}


def test_build_table_graph_merges_table_nodes_case_insensitively():
    lineage_data = {
        "edges": [
            {
                "source": "DWD_Orders.order_id",
                "target": "TMP_Orders_Stage.order_id",
                "source_file": "stage.sql",
            },
            {
                "source": "tmp_orders_stage.order_id",
                "target": "DWS_Orders.order_id",
                "source_file": "dws.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_orders.store_id",
                "target_table": "dws_orders",
                "source_file": "dws.sql",
            }
        ],
    }

    upstream, downstream = build_table_graph(
        lineage_data["edges"],
        lineage_data["indirect_edges"],
    )

    assert upstream == {
        "TMP_Orders_Stage": {"DWD_Orders"},
        "DWS_Orders": {"DWD_Orders", "TMP_Orders_Stage"},
    }
    assert downstream == {
        "DWD_Orders": {"DWS_Orders", "TMP_Orders_Stage"},
        "TMP_Orders_Stage": {"DWS_Orders"},
    }
    assert build_table_edge_source_files(
        lineage_data["edges"],
        lineage_data["indirect_edges"],
    ) == {
        ("DWD_Orders", "TMP_Orders_Stage"): {"stage.sql"},
        ("TMP_Orders_Stage", "DWS_Orders"): {"dws.sql"},
        ("DWD_Orders", "DWS_Orders"): {"dws.sql"},
    }


def test_table_edge_source_files_resolve_v2_jobs():
    assert build_table_edge_source_files(
        [
            {
                "source": {"type": "column", "id": "src.id"},
                "target": {"type": "column", "id": "out.id"},
                "job": "publish",
            }
        ],
        [],
        jobs=[
            {
                "name": "publish",
                "source_file": "mid/tasks/publish.sql",
            }
        ],
    ) == {("src", "out"): {"mid/tasks/publish.sql"}}


def test_table_graph_exposes_self_edges_without_dependency_noise():
    lineage_data = {
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.amount"},
                "target": {"type": "column", "id": "DWD_Orders.amount"},
                "relation_type": "direct",
                "expression": "amount + 1",
                "source_file": "dwd_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.dt"},
                "target": {"type": "table", "id": "dwd_orders"},
                "relation_type": "filter",
                "expression": "dt = @etl_date",
                "source_file": "dwd_orders.sql",
            },
            {
                "source": "dwd_orders.id",
                "target": "dws_orders.id",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_orders.status",
                "target_table": "DWD_Orders",
                "condition_type": "WHERE",
                "condition_expression": "status = 'ACTIVE'",
                "source_file": "dwd_orders.sql",
            }
        ],
    }

    upstream, downstream = build_table_graph(
        lineage_data["edges"],
        lineage_data["indirect_edges"],
    )

    assert upstream == {"dws_orders": {"dwd_orders"}}
    assert downstream == {"dwd_orders": {"dws_orders"}}
    assert collect_table_self_edges(
        lineage_data["edges"],
        lineage_data["indirect_edges"],
    ) == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": {"type": "column", "id": "dwd_orders.amount"},
            "target": {"type": "column", "id": "DWD_Orders.amount"},
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        },
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": {"type": "column", "id": "dwd_orders.dt"},
            "target": {"type": "table", "id": "dwd_orders"},
            "relation_type": "filter",
            "expression": "dt = @etl_date",
            "source_file": "dwd_orders.sql",
        },
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.status",
            "target": "DWD_Orders",
            "relation_type": "WHERE",
            "expression": "status = 'ACTIVE'",
            "source_file": "dwd_orders.sql",
        },
    ]


@pytest.mark.parametrize(
    ("source_table", "first_transient", "second_transient", "target_table"),
    [
        (
            "dwd_orders",
            "tmp_orders_stage",
            "tmp_orders_stage",
            "dws_orders",
        ),
        (
            "DWD_Orders",
            "TMP_Orders_Stage",
            "tmp_orders_stage",
            "DWS_Orders",
        ),
    ],
    ids=("matching-case", "mixed-case"),
)
def test_build_asset_table_graph_collapses_transient_tables(
    source_table, first_transient, second_transient, target_table
):
    lineage_data = {
        "edges": [
            {
                "source": f"{source_table}.order_id",
                "target": f"{first_transient}.order_id",
            },
            {
                "source": f"{second_transient}.order_id",
                "target": f"{target_table}.order_id",
            },
        ],
        "indirect_edges": [],
        "tables": [{"name": "tmp_orders_stage", "is_transient": True}],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream == {target_table: {source_table}}
    assert downstream == {source_table: {target_table}}


def test_build_asset_table_graph_uses_table_transient_flags():
    lineage_data = {
        "edges": [
            {"source": "ods_events.event_id", "target": "tmp_events.event_id"},
            {"source": "tmp_events.event_id", "target": "dwd_events.event_id"},
            {"source": "dwd_events.event_id", "target": "dws_events.event_id"},
        ],
        "indirect_edges": [
            {
                "source": "tmp_events.event_date",
                "target_table": "dwd_events",
            }
        ],
        "tables": [{"name": "tmp_events", "is_transient": True}],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream["dwd_events"] == {"ods_events"}
    assert upstream["dws_events"] == {"dwd_events"}
    assert downstream["ods_events"] == {"dwd_events"}
    assert downstream["dwd_events"] == {"dws_events"}
    assert "tmp_events" not in upstream
    assert "tmp_events" not in downstream


def test_build_asset_self_edges_excludes_transient_table_loops():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "dwd_orders.amount",
                "expression": "amount + 1",
                "source_file": "dwd_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "tmp_orders.amount",
                "expression": "amount + 1",
                "source_file": "tmp_orders.sql",
            },
        ],
        "tables": [{"name": "tmp_orders", "is_transient": True}],
    }

    assert build_asset_self_edges(lineage_data) == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.amount",
            "target": "dwd_orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        }
    ]


def test_build_asset_column_lineage_keeps_direct_asset_edges():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "dws_orders.total_amount",
                "expression": "SUM(dwd_orders.amount) AS total_amount",
                "source_file": "dws_orders.sql",
            }
        ],
    }

    assert build_asset_column_lineage(lineage_data, "dws_orders") == [
        {
            "source": "dwd_orders.amount",
            "target": "dws_orders.total_amount",
            "expression": "SUM(dwd_orders.amount) AS total_amount",
            "source_file": "dws_orders.sql",
        }
    ]


def test_build_asset_column_lineage_collapses_transient_field_path():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_order_detail.sale_amount",
                "target": "tmp_promotion_stage.sale_amount",
                "expression": "SUM(dwd_order_detail.sale_amount) AS sale_amount",
                "source_file": "dws_promotion_effect_daily.sql",
            },
            {
                "source": "tmp_promotion_stage.sale_amount",
                "target": "dws_promotion_effect_daily.sale_amount",
                "expression": "tmp_promotion_stage.sale_amount AS sale_amount",
                "source_file": "dws_promotion_effect_daily.sql",
            },
        ],
        "tables": [
            {
                "name": "tmp_promotion_stage",
                "is_transient": True,
            }
        ],
    }

    assert build_asset_column_lineage(
        lineage_data,
        "dws_promotion_effect_daily",
    ) == [
        {
            "source": "dwd_order_detail.sale_amount",
            "target": "dws_promotion_effect_daily.sale_amount",
            "expression": "tmp_promotion_stage.sale_amount AS sale_amount",
            "source_file": "dws_promotion_effect_daily.sql",
            "transient_path": ["tmp_promotion_stage.sale_amount"],
            "expression_chain": [
                {
                    "source": "dwd_order_detail.sale_amount",
                    "target": "tmp_promotion_stage.sale_amount",
                    "expression": "SUM(dwd_order_detail.sale_amount) AS sale_amount",
                    "source_file": "dws_promotion_effect_daily.sql",
                },
                {
                    "source": "tmp_promotion_stage.sale_amount",
                    "target": "dws_promotion_effect_daily.sale_amount",
                    "expression": "tmp_promotion_stage.sale_amount AS sale_amount",
                    "source_file": "dws_promotion_effect_daily.sql",
                },
            ],
        }
    ]


def test_build_asset_column_lineage_preserves_multi_source_calculation_chain():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.paid_amount",
                "target": "tmp_orders.payment_rate",
                "expression": (
                    "SUM(dwd_orders.paid_amount) / "
                    "SUM(dwd_orders.order_amount) AS payment_rate"
                ),
                "source_file": "dws_orders.sql",
            },
            {
                "source": "dwd_orders.order_amount",
                "target": "tmp_orders.payment_rate",
                "expression": (
                    "SUM(dwd_orders.paid_amount) / "
                    "SUM(dwd_orders.order_amount) AS payment_rate"
                ),
                "source_file": "dws_orders.sql",
            },
            {
                "source": "tmp_orders.payment_rate",
                "target": "dws_orders.payment_rate",
                "expression": "tmp_orders.payment_rate AS payment_rate",
                "source_file": "dws_orders.sql",
            },
        ],
        "tables": [{"name": "tmp_orders", "is_transient": True}],
    }

    result = build_asset_column_lineage(lineage_data, "dws_orders")

    assert result == [
        {
            "source": "dwd_orders.order_amount",
            "target": "dws_orders.payment_rate",
            "expression": "tmp_orders.payment_rate AS payment_rate",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.payment_rate"],
            "expression_chain": [
                {
                    "source": "dwd_orders.order_amount",
                    "target": "tmp_orders.payment_rate",
                    "expression": (
                        "SUM(dwd_orders.paid_amount) / "
                        "SUM(dwd_orders.order_amount) AS payment_rate"
                    ),
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.payment_rate",
                    "target": "dws_orders.payment_rate",
                    "expression": "tmp_orders.payment_rate AS payment_rate",
                    "source_file": "dws_orders.sql",
                },
            ],
        },
        {
            "source": "dwd_orders.paid_amount",
            "target": "dws_orders.payment_rate",
            "expression": "tmp_orders.payment_rate AS payment_rate",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.payment_rate"],
            "expression_chain": [
                {
                    "source": "dwd_orders.paid_amount",
                    "target": "tmp_orders.payment_rate",
                    "expression": (
                        "SUM(dwd_orders.paid_amount) / "
                        "SUM(dwd_orders.order_amount) AS payment_rate"
                    ),
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.payment_rate",
                    "target": "dws_orders.payment_rate",
                    "expression": "tmp_orders.payment_rate AS payment_rate",
                    "source_file": "dws_orders.sql",
                },
            ],
        },
    ]


def test_build_asset_column_lineage_attaches_direct_condition_lineage():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "dws_orders.total_amount",
                "expression": "SUM(dwd_orders.amount) AS total_amount",
                "source_file": "dws_orders.sql",
            }
        ],
        "indirect_edges": [
            {
                "source": "dwd_orders.order_status",
                "target_table": "dws_orders",
                "condition_type": "WHERE",
                "condition_expression": "dwd_orders.order_status = 'PAID'",
                "source_file": "dws_orders.sql",
            }
        ],
    }

    assert build_asset_column_lineage(lineage_data, "dws_orders") == [
        {
            "source": "dwd_orders.amount",
            "target": "dws_orders.total_amount",
            "expression": "SUM(dwd_orders.amount) AS total_amount",
            "source_file": "dws_orders.sql",
            "condition_lineage": [
                {
                    "source": "dwd_orders.order_status",
                    "condition_type": "WHERE",
                    "condition_expression": "dwd_orders.order_status = 'PAID'",
                    "source_file": "dws_orders.sql",
                }
            ],
        }
    ]


def test_build_asset_column_lineage_collapses_transient_condition_source():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "tmp_orders.amount",
                "expression": "SUM(dwd_orders.amount) AS amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": "dwd_orders.order_status",
                "target": "tmp_orders.order_status",
                "expression": "dwd_orders.order_status AS order_status",
                "source_file": "dws_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "dws_orders.total_amount",
                "expression": "tmp_orders.amount AS total_amount",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "tmp_orders.order_status",
                "target_table": "dws_orders",
                "condition_type": "HAVING",
                "condition_expression": "tmp_orders.order_status = 'PAID'",
                "source_file": "dws_orders.sql",
            }
        ],
        "tables": [{"name": "tmp_orders", "is_transient": True}],
    }

    result = build_asset_column_lineage(lineage_data, "dws_orders")

    assert result == [
        {
            "source": "dwd_orders.amount",
            "target": "dws_orders.total_amount",
            "expression": "tmp_orders.amount AS total_amount",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.amount"],
            "expression_chain": [
                {
                    "source": "dwd_orders.amount",
                    "target": "tmp_orders.amount",
                    "expression": "SUM(dwd_orders.amount) AS amount",
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.amount",
                    "target": "dws_orders.total_amount",
                    "expression": "tmp_orders.amount AS total_amount",
                    "source_file": "dws_orders.sql",
                },
            ],
            "condition_lineage": [
                {
                    "source": "dwd_orders.order_status",
                    "condition_type": "HAVING",
                    "condition_expression": "tmp_orders.order_status = 'PAID'",
                    "source_file": "dws_orders.sql",
                    "transient_path": ["tmp_orders.order_status"],
                    "expression_chain": [
                        {
                            "source": "dwd_orders.order_status",
                            "target": "tmp_orders.order_status",
                            "expression": "dwd_orders.order_status AS order_status",
                            "source_file": "dws_orders.sql",
                        }
                    ],
                }
            ],
        }
    ]
