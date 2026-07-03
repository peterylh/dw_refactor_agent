from dw_refactor_agent.lineage.view import LineageView


def test_lineage_view_reuses_indexed_column_lineage():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
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
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "group_by",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.raw_table_graph() == (
        {
            "tmp_orders": {"dwd_orders"},
            "dws_orders": {"tmp_orders", "dwd_orders"},
        },
        {
            "dwd_orders": {"tmp_orders", "dws_orders"},
            "tmp_orders": {"dws_orders"},
        },
    )
    assert view.asset_table_graph() == (
        {"dws_orders": {"dwd_orders"}},
        {"dwd_orders": {"dws_orders"}},
    )
    assert view.column_lineage_for_table("dws_orders") == [
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
                    "source": "dwd_orders.store_id",
                    "condition_type": "GROUP_BY",
                    "condition_expression": "store_id",
                    "source_file": "dws_orders.sql",
                }
            ],
        }
    ]


def test_lineage_view_collapses_transient_column_lineage_case_insensitively():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
            {
                "source": "DWD_Orders.amount",
                "target": "TMP_Orders.amount",
                "expression": "DWD_Orders.amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "DWS_Orders.total_amount",
                "expression": "tmp_orders.amount AS total_amount",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.asset_table_graph() == (
        {"DWS_Orders": {"DWD_Orders"}},
        {"DWD_Orders": {"DWS_Orders"}},
    )
    assert view.column_lineage_for_table("dws_orders") == [
        {
            "source": "DWD_Orders.amount",
            "target": "DWS_Orders.total_amount",
            "expression": "tmp_orders.amount AS total_amount",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.amount"],
            "expression_chain": [
                {
                    "source": "DWD_Orders.amount",
                    "target": "TMP_Orders.amount",
                    "expression": "DWD_Orders.amount",
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.amount",
                    "target": "DWS_Orders.total_amount",
                    "expression": "tmp_orders.amount AS total_amount",
                    "source_file": "dws_orders.sql",
                },
            ],
        }
    ]


def test_lineage_view_indexes_design_facts_by_table():
    lineage_data = {
        "tables": [{"name": "dws_orders", "columns": []}],
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "column", "id": "dws_orders.store_id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.amount"},
                "target": {"type": "column", "id": "dws_orders.total_amount"},
                "relation_type": "direct",
                "transformation_type": "aggregation",
                "expression": "SUM(amount) AS total_amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "literal", "value": "ALL"},
                "target": {"type": "column", "id": "dws_orders.channel_type"},
                "relation_type": "direct",
                "transformation_type": "constant",
                "expression": "'ALL' AS channel_type",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "group_by",
                "transformation_type": "group_by",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    facts = LineageView.from_data(
        "demo", lineage_data
    ).lineage_facts_for_table("dws_orders")

    assert facts == {
        "has_lineage": True,
        "has_group_by": True,
        "has_aggregate": True,
        "aggregate_columns": ["total_amount"],
        "constant_columns": ["channel_type"],
        "plain_columns": ["store_id"],
        "plain_column_sources": {"store_id": "dwd_orders.store_id"},
        "group_by_sources": ["dwd_orders.store_id"],
        "source_files": ["dws_orders.sql"],
    }


def test_lineage_view_indexes_targets_by_source_file():
    lineage_data = {
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "column", "id": "dws_orders.id"},
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "where",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_payments.id",
                "target_table": "dws_payments",
                "source_file": "dws_payments.sql",
            }
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.targets_by_source_file("dws_orders.sql") == {"dws_orders"}
    assert view.targets_by_source_file("dws_payments.sql") == {"dws_payments"}


def test_lineage_view_indexes_table_edge_source_files():
    lineage_data = {
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "column", "id": "dws_orders.id"},
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.status"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "where",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_payments.id",
                "target_table": "dws_payments",
                "source_file": "dws_payments.sql",
            }
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.table_edge_source_files() == {
        ("dwd_orders", "dws_orders"): {"dws_orders.sql"},
        ("dwd_payments", "dws_payments"): {"dws_payments.sql"},
    }


def test_lineage_view_exposes_self_edges_separately_from_table_graphs():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "DWD_Orders.amount",
                "expression": "amount + 1",
                "source_file": "dwd_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "tmp_orders.amount",
                "expression": "amount + 1",
                "source_file": "tmp_orders.sql",
            },
            {
                "source": "dwd_orders.id",
                "target": "dws_orders.id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.raw_table_graph() == (
        {"dws_orders": {"dwd_orders"}},
        {"dwd_orders": {"dws_orders"}},
    )
    assert view.raw_self_edges() == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.amount",
            "target": "DWD_Orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        },
        {
            "table": "tmp_orders",
            "source_table": "tmp_orders",
            "target_table": "tmp_orders",
            "source": "tmp_orders.amount",
            "target": "tmp_orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "tmp_orders.sql",
        },
    ]
    assert view.asset_self_edges() == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.amount",
            "target": "DWD_Orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        }
    ]
    assert view.self_edges_for_table("DWD_ORDERS") == view.asset_self_edges()
