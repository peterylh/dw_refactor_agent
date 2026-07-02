import pytest

import config
from lineage.query import (
    build_column_lineage,
    build_project_stats,
    build_table_subgraph,
)
from lineage.view import LineageView


def configure_demo_project_layers(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    models_dir = project_dir / "models"
    models_dir.mkdir(parents=True)
    for table_name, layer in [
        ("ods_order", "ODS"),
        ("dwd_order_detail", "DWD"),
        ("dwd_product", "DWD"),
        ("dws_product_sales_daily", "DWS"),
        ("ads_sales_dashboard", "ADS"),
        ("ads_unrelated", "ADS"),
    ]:
        (models_dir / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, "demo", {"dir": "demo_project"})
    config.clear_model_metadata_cache()


@pytest.fixture(autouse=True)
def demo_project_layers(monkeypatch, tmp_path):
    configure_demo_project_layers(monkeypatch, tmp_path)
    yield
    config.clear_model_metadata_cache()


def _demo_view():
    return LineageView.from_data(
        "demo",
        {
            "tables": [
                {
                    "name": "ods_order",
                    "columns": [{"name": "sale_amount"}],
                },
                {
                    "name": "dwd_order_detail",
                    "columns": [{"name": "sale_amount"}],
                },
                {
                    "name": "dwd_product",
                    "columns": [{"name": "product_id"}],
                },
                {
                    "name": "dws_product_sales_daily",
                    "columns": [
                        {"name": "product_id"},
                        {"name": "sales_amount"},
                    ],
                },
                {
                    "name": "ads_sales_dashboard",
                    "columns": [{"name": "sales_amount"}],
                },
                {
                    "name": "ads_unrelated",
                    "columns": [{"name": "sales_amount"}],
                },
            ],
            "edges": [
                {
                    "source": {
                        "type": "column",
                        "id": "ods_order.sale_amount",
                    },
                    "target": {
                        "type": "column",
                        "id": "dwd_order_detail.sale_amount",
                    },
                    "transformation_type": "passthrough",
                    "expression": "sale_amount",
                    "source_file": "dwd_order_detail.sql",
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dwd_order_detail.sale_amount",
                    },
                    "target": {
                        "type": "column",
                        "id": "dws_product_sales_daily.sales_amount",
                    },
                    "transformation_type": "aggregation",
                    "expression": "SUM(sale_amount) AS sales_amount",
                    "source_file": "dws_product_sales_daily.sql",
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dwd_product.product_id",
                    },
                    "target": {
                        "type": "column",
                        "id": "dws_product_sales_daily.product_id",
                    },
                    "source_file": "dws_product_sales_daily.sql",
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dwd_order_detail.product_id",
                    },
                    "target": {
                        "type": "table",
                        "id": "dws_product_sales_daily",
                    },
                    "relation_type": "group_by",
                    "expression": "product_id",
                    "source_file": "dws_product_sales_daily.sql",
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dwd_order_detail.order_date",
                    },
                    "target": {
                        "type": "table",
                        "id": "dws_product_sales_daily",
                    },
                    "relation_type": "filter",
                    "expression": "order_date = @etl_date",
                    "source_file": "dws_product_sales_daily.sql",
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dws_product_sales_daily.sales_amount",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_sales_dashboard.sales_amount",
                    },
                    "source_file": "ads_sales_dashboard.sql",
                },
            ],
        },
    )


def test_project_stats_ignores_legacy_snapshot_layer():
    view = LineageView.from_data(
        "demo",
        {
            "tables": [
                {
                    "name": "dwd_order_detail",
                    "layer": "ADS",
                    "columns": [],
                }
            ],
            "edges": [],
        },
    )

    stats = build_project_stats(view)

    assert "layer" not in view.snapshot.to_dict()["tables"][0]
    assert stats.layer_counts == {"DWD": 1}


def test_build_table_subgraph_limits_upstream_by_depth():
    subgraph = build_table_subgraph(
        _demo_view(),
        "ads_sales_dashboard",
        direction="upstream",
        depth=2,
    )

    assert subgraph.root == "ads_sales_dashboard"
    assert subgraph.direction == "upstream"
    assert subgraph.depth == 2
    assert subgraph.tables == {
        "ads_sales_dashboard",
        "dws_product_sales_daily",
        "dwd_order_detail",
        "dwd_product",
    }
    assert subgraph.hidden_boundary_edges == 1
    assert subgraph.layer_counts == {"ADS": 1, "DWD": 2, "DWS": 1}
    assert [
        (edge.source, edge.target, edge.hops, edge.source_files)
        for edge in subgraph.edges
    ] == [
        (
            "dws_product_sales_daily",
            "ads_sales_dashboard",
            1,
            ("ads_sales_dashboard.sql",),
        ),
        (
            "dwd_order_detail",
            "dws_product_sales_daily",
            2,
            ("dws_product_sales_daily.sql",),
        ),
        (
            "dwd_product",
            "dws_product_sales_daily",
            2,
            ("dws_product_sales_daily.sql",),
        ),
    ]


def test_build_table_subgraph_matches_root_case_insensitively():
    subgraph = build_table_subgraph(
        _demo_view(),
        "ADS_SALES_DASHBOARD",
        direction="upstream",
        depth=1,
    )

    assert subgraph.root == "ads_sales_dashboard"
    assert subgraph.tables == {
        "ads_sales_dashboard",
        "dws_product_sales_daily",
    }


def test_build_table_subgraph_rejects_unknown_table():
    with pytest.raises(ValueError, match="unknown table"):
        build_table_subgraph(
            _demo_view(),
            "missing_table",
            direction="upstream",
            depth=1,
        )


def test_build_column_lineage_traces_specific_column_upstream_by_depth():
    lineage = build_column_lineage(
        _demo_view(),
        "dws_product_sales_daily",
        "sales_amount",
        direction="upstream",
        depth=2,
    )

    assert lineage.table == "dws_product_sales_daily"
    assert lineage.column == "sales_amount"
    assert lineage.direction == "upstream"
    assert lineage.depth == 2
    assert len(lineage.paths) == 1

    path = lineage.paths[0]
    assert path.nodes == (
        "ods_order.sale_amount",
        "dwd_order_detail.sale_amount",
        "dws_product_sales_daily.sales_amount",
    )
    assert [
        (step.source, step.target, step.expression, step.source_file)
        for step in path.steps
    ] == [
        (
            "ods_order.sale_amount",
            "dwd_order_detail.sale_amount",
            "sale_amount",
            "dwd_order_detail.sql",
        ),
        (
            "dwd_order_detail.sale_amount",
            "dws_product_sales_daily.sales_amount",
            "SUM(sale_amount) AS sales_amount",
            "dws_product_sales_daily.sql",
        ),
    ]
    assert lineage.source_columns == {"ods_order.sale_amount"}
    assert lineage.transformation_counts == {
        "aggregation": 1,
        "passthrough": 1,
    }
    assert lineage.source_files == {
        "dwd_order_detail.sql",
        "dws_product_sales_daily.sql",
    }
    assert [
        (
            condition.source,
            condition.condition_type,
            condition.condition_expression,
            condition.source_file,
        )
        for condition in path.steps[-1].conditions
    ] == [
        (
            "dwd_order_detail.order_date",
            "FILTER",
            "order_date = @etl_date",
            "dws_product_sales_daily.sql",
        ),
        (
            "dwd_order_detail.product_id",
            "GROUP_BY",
            "product_id",
            "dws_product_sales_daily.sql",
        ),
    ]


def test_build_column_lineage_matches_table_and_column_case_insensitively():
    lineage = build_column_lineage(
        _demo_view(),
        "DWS_PRODUCT_SALES_DAILY",
        "SALES_AMOUNT",
        direction="upstream",
        depth=1,
    )

    assert lineage.table == "dws_product_sales_daily"
    assert lineage.column == "sales_amount"
    assert lineage.paths[0].nodes == (
        "dwd_order_detail.sale_amount",
        "dws_product_sales_daily.sales_amount",
    )


def test_build_column_lineage_rejects_empty_column():
    with pytest.raises(ValueError, match="column is required"):
        build_column_lineage(
            _demo_view(),
            "dws_product_sales_daily",
            "",
            direction="upstream",
            depth=1,
        )


def test_build_column_lineage_traces_specific_column_downstream_by_depth():
    lineage = build_column_lineage(
        _demo_view(),
        "dwd_order_detail",
        "sale_amount",
        direction="downstream",
        depth=2,
    )

    assert lineage.direction == "downstream"
    assert len(lineage.paths) == 1
    assert lineage.paths[0].nodes == (
        "dwd_order_detail.sale_amount",
        "dws_product_sales_daily.sales_amount",
        "ads_sales_dashboard.sales_amount",
    )
