from lineage.asset_graph import (
    build_asset_column_lineage,
    build_asset_table_graph,
)
from lineage.table_graph import (
    build_table_edge_source_files,
    build_table_graph,
)


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


def test_build_asset_table_graph_collapses_transient_tables():
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
        "tables": [{"name": "tmp_orders_stage", "is_transient": True}],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream == {"dws_orders": {"dwd_orders"}}
    assert downstream == {"dwd_orders": {"dws_orders"}}


def test_build_asset_table_graph_collapses_transient_tables_case_insensitively():
    lineage_data = {
        "edges": [
            {
                "source": "DWD_Orders.order_id",
                "target": "TMP_Orders_Stage.order_id",
            },
            {
                "source": "tmp_orders_stage.order_id",
                "target": "DWS_Orders.order_id",
            },
        ],
        "indirect_edges": [],
        "tables": [{"name": "tmp_orders_stage", "is_transient": True}],
    }

    upstream, downstream = build_asset_table_graph(lineage_data)

    assert upstream == {"DWS_Orders": {"DWD_Orders"}}
    assert downstream == {"DWD_Orders": {"DWS_Orders"}}


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
