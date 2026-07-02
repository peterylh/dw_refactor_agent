import json

import pytest

from lineage.job_dag import JobDAG, asset_job_dag_from_lineage


def _edges(*pairs):
    return [
        {"source": f"{source}.x", "target": f"{target}.x"}
        for source, target in pairs
    ]


def _positions(order):
    return {job: index for index, job in enumerate(order)}


def _assert_before(order, *pairs):
    positions = _positions(order)
    for source, target in pairs:
        assert positions[source] < positions[target]


def test_downstream_traversal_scenarios():
    dag = JobDAG(
        _edges(
            ("a", "b"),
            ("a", "c"),
            ("b", "d"),
            ("c", "d"),
            ("d", "a"),
            ("x", "y"),
        )
    )

    assert dag.bfs_downstream({"a"}) == {"b", "c", "d"}
    assert dag.bfs_downstream({"b", "c"}) == {"a", "d"}
    assert dag.bfs_downstream({"missing"}) == set()
    assert dag.bfs_downstream(set()) == set()

    dag = JobDAG(_edges(("DWD_Order_Detail", "DWS_Store_Sales_Daily")))

    assert dag.bfs_downstream({"dwd_order_detail"}) == {
        "DWS_Store_Sales_Daily"
    }


def test_topological_sort_scenarios():
    dag = JobDAG(
        _edges(
            ("ods_order", "dwd_order_detail"),
            ("dwd_order_detail", "dws_store_sales_daily"),
            ("dwd_order_detail", "dws_product_sales_daily"),
            ("dws_store_sales_daily", "ads_sales_dashboard"),
            ("dws_product_sales_daily", "ads_sales_dashboard"),
        )
    )

    order = dag.topological_sort(
        {
            "ods_order",
            "dwd_order_detail",
            "dws_store_sales_daily",
            "dws_product_sales_daily",
            "ads_sales_dashboard",
            "unrelated_task",
        }
    )

    assert set(order) == {
        "ods_order",
        "dwd_order_detail",
        "dws_store_sales_daily",
        "dws_product_sales_daily",
        "ads_sales_dashboard",
        "unrelated_task",
    }
    _assert_before(
        order,
        ("ods_order", "dwd_order_detail"),
        ("dwd_order_detail", "dws_store_sales_daily"),
        ("dwd_order_detail", "dws_product_sales_daily"),
        ("dws_store_sales_daily", "ads_sales_dashboard"),
        ("dws_product_sales_daily", "ads_sales_dashboard"),
    )

    dag = JobDAG(
        _edges(
            ("DWD_Order_Detail", "DWS_Store_Sales_Daily"),
            ("DWS_Store_Sales_Daily", "ADS_Sales_Dashboard"),
        )
    )

    order = dag.topological_sort(
        {
            "dwd_order_detail",
            "dws_store_sales_daily",
            "ads_sales_dashboard",
        }
    )

    assert order == [
        "dwd_order_detail",
        "dws_store_sales_daily",
        "ads_sales_dashboard",
    ]

    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("external", "sink")))

    order = dag.topological_sort({"a", "b", "c"})

    assert order == ["a", "b", "c"]

    dag = JobDAG(_edges(("a", "b"), ("b", "a")))

    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort({"a", "b", "c"})

    dag = JobDAG(_edges(("a", "a"), ("a", "b")))

    assert dag.bfs_downstream({"a"}) == {"b"}
    assert dag.topological_sort({"a", "b"}) == ["a", "b"]
    assert dag.self_edges == [
        {
            "table": "a",
            "source_table": "a",
            "target_table": "a",
            "source": "a.x",
            "target": "a.x",
        }
    ]

    dag = JobDAG(_edges(("a", "c"), ("b", "c"), ("c", "d")))

    layers = dag.topological_layers({"a", "b", "c", "d"})

    assert [set(layer) for layer in layers] == [{"a", "b"}, {"c"}, {"d"}]


def test_structured_lineage_edges_are_accepted():
    dag = JobDAG(
        [
            {
                "source": {
                    "type": "column",
                    "id": "shop_dm.dwd_order.order_id",
                },
                "target": {
                    "type": "column",
                    "id": "shop_dm.dws_order.order_id",
                },
            },
            {
                "source": {"type": "table", "id": "shop_dm.dws_order"},
                "target": {"type": "table", "id": "shop_dm.ads_order"},
            },
        ]
    )

    assert dag.bfs_downstream({"shop_dm.dwd_order"}) == {
        "shop_dm.dws_order",
        "shop_dm.ads_order",
    }


def test_asset_job_dag_preserves_asset_self_edges_as_metadata():
    dag = asset_job_dag_from_lineage(
        {
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
                {
                    "source": "dwd_orders.id",
                    "target": "dws_orders.id",
                    "source_file": "dws_orders.sql",
                },
            ],
            "tables": [{"name": "tmp_orders", "is_transient": True}],
        }
    )

    assert dag.bfs_downstream({"dwd_orders"}) == {"dws_orders"}
    assert dag.self_edges == [
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


def test_serialization_roundtrip_preserves_behavior(tmp_path):
    dag = JobDAG(_edges(("a", "a"), ("a", "b"), ("b", "c")))
    path = tmp_path / "dag.json"

    dag.save(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = JobDAG.load(path)

    assert raw["deps"] == {"a": ["b"], "b": ["c"]}
    assert raw["self_edges"] == [
        {
            "table": "a",
            "source_table": "a",
            "target_table": "a",
            "source": "a.x",
            "target": "a.x",
        }
    ]
    assert loaded.self_edges == raw["self_edges"]
    assert loaded.bfs_downstream({"a"}) == {"b", "c"}
    assert loaded.topological_sort({"a", "b", "c"}) == ["a", "b", "c"]

    loaded.add_edge("x", "y")

    assert loaded.bfs_downstream({"x"}) == {"y"}
