import json

import pytest

import config
from lineage.formatters import (
    format_column_json,
    format_column_text,
    format_table_dot,
    format_table_html,
    format_table_json,
    format_table_text,
)
from lineage.query import build_column_lineage, build_table_subgraph
from tests.lineage.test_lineage_query import (
    _demo_view,
    configure_demo_project_layers,
)


@pytest.fixture(autouse=True)
def demo_project_layers(monkeypatch, tmp_path):
    configure_demo_project_layers(monkeypatch, tmp_path)
    yield
    config._model_metadata_cache.clear()


def _table_subgraph():
    return build_table_subgraph(
        _demo_view(),
        "ads_sales_dashboard",
        direction="upstream",
        depth=2,
    )


def test_format_table_text_includes_summary_graph_and_edges():
    output = format_table_text(_table_subgraph())

    assert "Lineage: demo / ads_sales_dashboard" in output
    assert "Direction: upstream   Depth: 2   Granularity: table" in output
    assert "Summary" in output
    assert "Tables: 4   Edges: 3   Jobs: 2" in output
    assert "Layers: ADS=1, DWD=2, DWS=1" in output
    assert "Boundary: reached depth limit, 1 upstream tables hidden" in output
    assert "Graph" in output
    assert "ads_sales_dashboard [ADS]" in output
    assert (
        "<- dws_product_sales_daily [DWS]  job=ads_sales_dashboard.sql"
        in output
    )
    assert "Edges" in output
    assert "dwd_order_detail" in output
    assert "dws_product_sales_daily.sql" in output


def test_format_table_json_contains_only_selected_local_subgraph():
    payload = json.loads(format_table_json(_table_subgraph()))

    assert payload["root"] == "ads_sales_dashboard"
    assert payload["direction"] == "upstream"
    assert payload["summary"]["tables"] == 4
    assert payload["summary"]["hidden_boundary_edges"] == 1
    assert payload["tables"] == [
        {
            "name": "ads_sales_dashboard",
            "layer": "ADS",
            "columns": ["sales_amount"],
        },
        {
            "name": "dwd_order_detail",
            "layer": "DWD",
            "columns": ["sale_amount"],
        },
        {
            "name": "dwd_product",
            "layer": "DWD",
            "columns": ["product_id"],
        },
        {
            "name": "dws_product_sales_daily",
            "layer": "DWS",
            "columns": ["product_id", "sales_amount"],
        },
    ]
    assert payload["edges"] == [
        {
            "source": "dws_product_sales_daily",
            "target": "ads_sales_dashboard",
            "hops": 1,
            "source_files": ["ads_sales_dashboard.sql"],
        },
        {
            "source": "dwd_order_detail",
            "target": "dws_product_sales_daily",
            "hops": 2,
            "source_files": ["dws_product_sales_daily.sql"],
        },
        {
            "source": "dwd_product",
            "target": "dws_product_sales_daily",
            "hops": 2,
            "source_files": ["dws_product_sales_daily.sql"],
        },
    ]


def test_format_table_json_includes_local_columns_and_column_lineage():
    payload = json.loads(format_table_json(_table_subgraph()))

    dws_table = next(
        table
        for table in payload["tables"]
        if table["name"] == "dws_product_sales_daily"
    )
    assert dws_table["columns"] == ["product_id", "sales_amount"]

    lineage_rows = payload["column_lineage"]
    assert {
        "source": "dwd_order_detail.sale_amount",
        "target": "dws_product_sales_daily.sales_amount",
        "expression": "SUM(sale_amount) AS sales_amount",
        "source_file": "dws_product_sales_daily.sql",
        "transformation_type": "aggregation",
        "conditions": [
            {
                "source": "dwd_order_detail.order_date",
                "condition_type": "FILTER",
                "condition_expression": "order_date = @etl_date",
                "source_file": "dws_product_sales_daily.sql",
            },
            {
                "source": "dwd_order_detail.product_id",
                "condition_type": "GROUP_BY",
                "condition_expression": "product_id",
                "source_file": "dws_product_sales_daily.sql",
            },
        ],
    } in lineage_rows


def test_format_table_html_includes_column_lineage_details():
    output = format_table_html(_table_subgraph())

    assert "Column Lineage" in output
    assert "Tables And Columns" in output
    assert "dws_product_sales_daily.sales_amount" in output
    assert "SUM(sale_amount) AS sales_amount" in output
    assert '"condition_type": "GROUP_BY"' in output
    assert '"source": "dwd_order_detail.product_id"' in output


def test_format_table_dot_contains_selected_edges():
    output = format_table_dot(_table_subgraph())

    assert output.startswith("digraph lineage {")
    assert '"dws_product_sales_daily" -> "ads_sales_dashboard";' in output
    assert '"dwd_order_detail" -> "dws_product_sales_daily";' in output
    assert "ads_unrelated" not in output
    assert "ods_order" not in output


def test_format_column_text_includes_paths_expressions_and_jobs():
    lineage = build_column_lineage(
        _demo_view(),
        "dws_product_sales_daily",
        "sales_amount",
        direction="upstream",
        depth=2,
    )

    output = format_column_text(lineage)

    assert (
        "Column Lineage: demo / dws_product_sales_daily.sales_amount" in output
    )
    assert "Direction: upstream   Depth: 2" in output
    assert "Summary" in output
    assert "Paths: 1   Source Columns: 1" in output
    assert "Transformations: aggregation=1, passthrough=1" in output
    assert (
        "Source Files: dwd_order_detail.sql, dws_product_sales_daily.sql"
        in output
    )
    assert "Paths" in output
    assert "ods_order.sale_amount" in output
    assert "-> dwd_order_detail.sale_amount" in output
    assert "expr: sale_amount" in output
    assert "job:  dwd_order_detail.sql" in output
    assert "-> dws_product_sales_daily.sales_amount" in output
    assert "expr: SUM(sale_amount) AS sales_amount" in output
    assert "conditions:" not in output


def test_format_column_text_verbose_includes_conditions():
    lineage = build_column_lineage(
        _demo_view(),
        "dws_product_sales_daily",
        "sales_amount",
        direction="upstream",
        depth=2,
    )

    output = format_column_text(lineage, verbose=True)

    assert "conditions:" in output
    assert (
        "FILTER dwd_order_detail.order_date: order_date = @etl_date" in output
    )
    assert "GROUP_BY dwd_order_detail.product_id: product_id" in output


def test_format_column_json_contains_paths():
    lineage = build_column_lineage(
        _demo_view(),
        "dws_product_sales_daily",
        "sales_amount",
        direction="upstream",
        depth=2,
    )

    payload = json.loads(format_column_json(lineage))

    assert payload["table"] == "dws_product_sales_daily"
    assert payload["column"] == "sales_amount"
    assert payload["summary"] == {
        "paths": 1,
        "source_columns": 1,
        "source_files": [
            "dwd_order_detail.sql",
            "dws_product_sales_daily.sql",
        ],
        "transformations": {
            "aggregation": 1,
            "passthrough": 1,
        },
    }
    assert payload["paths"][0]["nodes"] == [
        "ods_order.sale_amount",
        "dwd_order_detail.sale_amount",
        "dws_product_sales_daily.sales_amount",
    ]
    assert payload["paths"][0]["steps"][1]["conditions"] == [
        {
            "source": "dwd_order_detail.order_date",
            "condition_type": "FILTER",
            "condition_expression": "order_date = @etl_date",
            "source_file": "dws_product_sales_daily.sql",
        },
        {
            "source": "dwd_order_detail.product_id",
            "condition_type": "GROUP_BY",
            "condition_expression": "product_id",
            "source_file": "dws_product_sales_daily.sql",
        },
    ]
