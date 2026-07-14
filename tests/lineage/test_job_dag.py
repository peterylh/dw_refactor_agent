import json

import pytest

import dw_refactor_agent.lineage.job_dag as job_dag_module
from dw_refactor_agent.lineage.job_dag import (
    JobDAG,
    asset_job_dag_from_lineage,
)


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


def _lineage_v2(*, tables, jobs):
    return {
        "format_version": 2,
        "tables": tables,
        "jobs": jobs,
        "edges": [],
        "diagnostics": [],
    }


def _table(full_name, dataset_type="managed"):
    return {
        "name": full_name.rsplit(".", 1)[-1],
        "full_name": full_name,
        "dataset_type": dataset_type,
        "columns": [],
    }


def _job(name, *, inputs=(), outputs=()):
    return {
        "name": name,
        "source_file": f"mid/tasks/{name}.sql",
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def test_job_dag_v2_uses_explicit_jobs_and_dataset_evidence():
    lineage = _lineage_v2(
        tables=[
            _table("internal.shop_dm.t", "process"),
            _table("internal.shop_dm.report"),
        ],
        jobs=[
            _job(
                "build_report",
                inputs=["internal.shop_dm.t"],
                outputs=["internal.shop_dm.report"],
            ),
            _job("prepare_sales", outputs=["internal.shop_dm.t"]),
        ],
    )

    dag = job_dag_module.job_dag_from_lineage(lineage)

    assert dag.to_dict() == {
        "format_version": 2,
        "jobs": ["build_report", "prepare_sales"],
        "data_dependencies": [
            {
                "upstream_job": "prepare_sales",
                "downstream_job": "build_report",
                "datasets": ["internal.shop_dm.t"],
            }
        ],
        "deps": {
            "build_report": [],
            "prepare_sales": ["build_report"],
        },
        "rev": {
            "build_report": ["prepare_sales"],
            "prepare_sales": [],
        },
    }


def test_job_dag_v2_keeps_isolated_jobs_and_aggregates_dataset_evidence():
    lineage = _lineage_v2(
        tables=[
            _table("internal.shop_dm.stage_a", "process"),
            _table("internal.shop_dm.stage_b", "process"),
            _table("internal.shop_dm.report"),
        ],
        jobs=[
            _job(
                "publish_metrics",
                inputs=[
                    "internal.shop_dm.stage_a",
                    "internal.shop_dm.stage_b",
                ],
                outputs=["internal.shop_dm.report"],
            ),
            _job(
                "prepare_metrics",
                outputs=[
                    "internal.shop_dm.stage_a",
                    "internal.shop_dm.stage_b",
                ],
            ),
            _job("vacuum_audit"),
        ],
    )

    dag = job_dag_module.job_dag_from_lineage(lineage)

    assert dag.to_dict()["data_dependencies"] == [
        {
            "upstream_job": "prepare_metrics",
            "downstream_job": "publish_metrics",
            "datasets": [
                "internal.shop_dm.stage_a",
                "internal.shop_dm.stage_b",
            ],
        }
    ]
    assert dag.to_dict()["deps"]["vacuum_audit"] == []
    assert dag.to_dict()["rev"]["vacuum_audit"] == []


def test_job_dag_v2_skips_self_reads_and_ambiguous_producers():
    shared_table = "internal.shop_dm.shared_stage"
    local_table = "internal.shop_dm.local_stage"
    lineage = _lineage_v2(
        tables=[
            _table(local_table, "process"),
            _table(shared_table, "process"),
        ],
        jobs=[
            _job("producer_a", outputs=[shared_table]),
            _job("producer_b", outputs=[shared_table]),
            _job("consumer", inputs=[shared_table]),
            _job("self_refresh", inputs=[local_table], outputs=[local_table]),
        ],
    )

    dag = job_dag_module.job_dag_from_lineage(lineage)

    assert dag.to_dict()["data_dependencies"] == []
    assert dag.to_dict()["deps"] == {
        "consumer": [],
        "producer_a": [],
        "producer_b": [],
        "self_refresh": [],
    }
    assert dag.topological_sort(
        {"CONSUMER", "PRODUCER_A", "PRODUCER_B", "SELF_REFRESH"}
    ) == ["CONSUMER", "PRODUCER_A", "PRODUCER_B", "SELF_REFRESH"]


def test_job_dag_v2_roundtrip_omits_legacy_fields(tmp_path):
    dag = job_dag_module.job_dag_from_lineage(
        _lineage_v2(
            tables=[_table("internal.shop_dm.output")],
            jobs=[
                _job(
                    "job_not_named_after_output",
                    outputs=["internal.shop_dm.output"],
                )
            ],
        )
    )
    path = tmp_path / "job_dag.json"

    dag.save(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = JobDAG.load(path)

    assert set(raw) == {
        "format_version",
        "jobs",
        "data_dependencies",
        "deps",
        "rev",
    }
    assert raw["jobs"] == ["job_not_named_after_output"]
    assert loaded.to_dict() == raw


def test_job_dag_loads_legacy_edges_and_adjacency():
    loaded = JobDAG.from_dict(
        {
            "edges": [{"source": "old_a", "target": "old_b"}],
            "self_edges": [],
            "deps": {"old_a": ["old_b"]},
            "rev": {"old_b": ["old_a"]},
        }
    )

    assert loaded.topological_sort({"OLD_A", "OLD_B"}) == [
        "OLD_A",
        "OLD_B",
    ]


@pytest.mark.parametrize("format_version", [0, 3, "2", True])
def test_job_dag_rejects_unsupported_explicit_versions(format_version):
    with pytest.raises(ValueError, match="format_version"):
        JobDAG.from_dict(
            {
                "format_version": format_version,
                "edges": [],
                "self_edges": [],
                "deps": {},
                "rev": {},
            }
        )


@pytest.mark.parametrize("format_version", [0, 3, "2", True])
def test_job_dag_from_lineage_rejects_unsupported_explicit_versions(
    format_version,
):
    with pytest.raises(ValueError, match="format_version"):
        job_dag_module.job_dag_from_lineage(
            {
                "format_version": format_version,
                "tables": [],
                "jobs": [],
                "edges": [],
                "diagnostics": [],
            }
        )


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
