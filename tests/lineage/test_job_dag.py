import json

import pytest

from lineage.job_dag import JobDAG


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


def test_downstream_traversal_handles_branches_cycles_and_missing_seeds():
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


def test_topological_sort_keeps_dependencies_before_dependents():
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


def test_topological_sort_matches_requested_jobs_case_insensitively():
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


def test_downstream_traversal_matches_seeds_case_insensitively():
    dag = JobDAG(_edges(("DWD_Order_Detail", "DWS_Store_Sales_Daily")))

    assert dag.bfs_downstream({"dwd_order_detail"}) == {
        "DWS_Store_Sales_Daily"
    }


def test_topological_sort_ignores_edges_outside_requested_jobs():
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("external", "sink")))

    order = dag.topological_sort({"a", "b", "c"})

    assert order == ["a", "b", "c"]


@pytest.mark.parametrize(
    "edges",
    [
        _edges(("a", "b"), ("b", "a")),
    ],
)
def test_topological_sort_rejects_cycles(edges):
    dag = JobDAG(edges)

    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort({"a", "b", "c"})


def test_self_references_are_not_dependencies():
    dag = JobDAG(_edges(("a", "a"), ("a", "b")))

    assert dag.bfs_downstream({"a"}) == {"b"}
    assert dag.topological_sort({"a", "b"}) == ["a", "b"]


def test_topological_layers_group_parallel_jobs():
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


def test_serialization_roundtrip_preserves_behavior(tmp_path):
    dag = JobDAG(_edges(("a", "b"), ("b", "c")))
    path = tmp_path / "dag.json"

    dag.save(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = JobDAG.load(path)

    assert raw["deps"] == {"a": ["b"], "b": ["c"]}
    assert loaded.bfs_downstream({"a"}) == {"b", "c"}
    assert loaded.topological_sort({"a", "b", "c"}) == ["a", "b", "c"]

    loaded.add_edge("x", "y")

    assert loaded.bfs_downstream({"x"}) == {"y"}
