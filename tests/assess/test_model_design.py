from assess.scoring.architecture import score_architecture_health
from assess.scoring.model_design import (
    extract_model_design_sql_facts,
    score_model_design_health,
)


def _rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def test_architecture_wrapper_uses_model_design_dimension():
    tables = [
        {"name": "ods_order", "layer": "ODS", "columns": []},
        {"name": "ads_sales", "layer": "ADS", "columns": []},
    ]
    edges = [{
        "source": "ods_order.order_id",
        "target": "ads_sales.order_id",
        "source_file": "ads_sales.sql",
    }]

    wrapped = score_architecture_health(tables, edges, [])
    direct = score_model_design_health(tables, edges, [])

    assert wrapped["score"] == direct["score"]
    assert _rule_ids(wrapped) == {"ARCH_SKIP_LAYER_DEPENDENCY"}
    assert _rule_ids(direct) == {"ARCH_SKIP_LAYER_DEPENDENCY"}


def test_extract_model_design_sql_facts_detects_group_by_and_aggregates():
    sql = """
    INSERT INTO shop_dm.dws_store_sales_daily
    SELECT store_id, order_date AS stat_date, SUM(subtotal) AS total_amount
    FROM shop_dm.dwd_order_detail
    GROUP BY store_id, order_date;
    """

    facts = extract_model_design_sql_facts(sql)

    assert facts["has_group_by"] is True
    assert facts["has_aggregate"] is True
    assert facts["group_by_columns"] == ["order_date", "store_id"]
    assert "total_amount" in facts["aggregate_aliases"]


def test_extract_model_design_sql_facts_detects_plain_detail_select():
    sql = """
    INSERT INTO shop_dm.dwd_order_detail
    SELECT order_item_id, order_id, subtotal
    FROM shop_dm.ods_order_item;
    """

    facts = extract_model_design_sql_facts(sql)

    assert facts["has_group_by"] is False
    assert facts["has_aggregate"] is False
    assert facts["group_by_columns"] == []
    assert facts["aggregate_aliases"] == []


def test_model_design_flags_dwd_fact_with_group_by():
    asset_catalog = {
        "tables": {
            "dwd_order_summary": {
                "tasks": [{
                    "source_file": "dwd_order_summary.sql",
                    "sql": """
                    INSERT INTO shop_dm.dwd_order_summary
                    SELECT order_id, SUM(subtotal) AS subtotal
                    FROM shop_dm.ods_order_item
                    GROUP BY order_id;
                    """,
                }],
            },
        },
    }
    tables = [{
        "name": "dwd_order_summary",
        "layer": "DWD",
        "columns": [
            {"name": "order_id", "type": "BIGINT"},
            {"name": "subtotal", "type": "DECIMAL(12,2)"},
        ],
    }]
    model_metadata = {"dwd_order_summary": {"table_type": "fact"}}

    result = score_model_design_health(
        tables,
        [],
        [],
        model_metadata=model_metadata,
        asset_catalog=asset_catalog,
    )

    assert _rule_ids(result) == {"MODEL_DWD_FACT_NO_AGGREGATION"}


def test_model_design_flags_dws_grain_mismatch_with_group_by():
    asset_catalog = {
        "tables": {
            "dws_store_sales_daily": {
                "tasks": [{
                    "source_file": "dws_store_sales_daily.sql",
                    "sql": """
                    INSERT INTO shop_dm.dws_store_sales_daily
                    SELECT store_id, order_date AS stat_date,
                           SUM(subtotal) AS total_amount
                    FROM shop_dm.dwd_order_detail
                    GROUP BY store_id, order_date;
                    """,
                }],
            },
        },
    }
    tables = [{"name": "dws_store_sales_daily", "layer": "DWS", "columns": []}]
    model_metadata = {
        "dws_store_sales_daily": {
            "table_type": "fact",
            "grain": {
                "entities": ["CUSTOMER"],
                "time_column": "stat_date",
            },
            "entities": [{
                "code": "CUSTOMER",
                "type": "foreign",
                "key_columns": ["customer_id"],
            }],
        }
    }

    result = score_model_design_health(
        tables,
        [],
        [],
        model_metadata=model_metadata,
        asset_catalog=asset_catalog,
    )

    assert "MODEL_DWS_GRAIN_MATCHES_GROUP_BY" in _rule_ids(result)


def test_model_design_flags_dws_fact_without_aggregation_from_typed_edges():
    tables = [{
        "name": "dws_store_sales_daily",
        "layer": "DWS",
        "columns": [
            {"name": "store_id", "type": "BIGINT"},
            {"name": "stat_date", "type": "DATE"},
            {"name": "sale_amount", "type": "DECIMAL(12,2)"},
        ],
    }]
    edges = [
        {
            "source": {"type": "column", "id": "dwd_order_detail.store_id"},
            "target": {"type": "column", "id": "dws_store_sales_daily.store_id"},
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "store_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.order_date"},
            "target": {"type": "column", "id": "dws_store_sales_daily.stat_date"},
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "order_date AS stat_date",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.subtotal"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.sale_amount",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "subtotal AS sale_amount",
            "source_file": "dws_store_sales_daily.sql",
        },
    ]
    model_metadata = {
        "dws_store_sales_daily": {
            "table_type": "fact",
            "grain": {"keys": ["store_id", "stat_date"]},
        }
    }

    result = score_model_design_health(
        tables,
        edges,
        [],
        model_metadata=model_metadata,
    )

    assert "MODEL_DWS_FACT_HAS_AGGREGATION" in _rule_ids(result)


def test_model_design_flags_dws_plain_field_not_in_group_by_from_typed_edges():
    tables = [{"name": "dws_store_sales_daily", "layer": "DWS", "columns": []}]
    edges = [
        {
            "source": {"type": "column", "id": "dwd_order_detail.store_id"},
            "target": {"type": "column", "id": "dws_store_sales_daily.store_id"},
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "store_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.order_date"},
            "target": {"type": "column", "id": "dws_store_sales_daily.stat_date"},
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "order_date AS stat_date",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "literal", "value": "ALL"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.channel_type",
            },
            "relation_type": "direct",
            "transformation_type": "constant",
            "expression": "'ALL' AS channel_type",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.customer_id"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.customer_id",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "customer_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.subtotal"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.sale_amount",
            },
            "relation_type": "direct",
            "transformation_type": "aggregation",
            "expression": "SUM(subtotal) AS sale_amount",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.store_id"},
            "target": {"type": "table", "id": "dws_store_sales_daily"},
            "relation_type": "group_by",
            "transformation_type": "group_by",
            "expression": "store_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.order_date"},
            "target": {"type": "table", "id": "dws_store_sales_daily"},
            "relation_type": "group_by",
            "transformation_type": "group_by",
            "expression": "order_date",
            "source_file": "dws_store_sales_daily.sql",
        },
    ]
    model_metadata = {
        "dws_store_sales_daily": {
            "table_type": "fact",
            "grain": {"keys": ["store_id", "stat_date"]},
        }
    }

    result = score_model_design_health(
        tables,
        edges,
        [],
        model_metadata=model_metadata,
    )

    assert "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN" in _rule_ids(result)
    check = next(
        check for check in result["checks"]
        if check["rule_id"] == "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN"
        and not check["passed"]
    )
    assert check["evidence"]["leaked_columns"] == ["customer_id"]
    assert "channel_type" not in check["evidence"]["leaked_columns"]


def test_model_design_flags_dim_metric_groups_without_llm():
    tables = [{"name": "dim_customer", "layer": "DIM", "columns": []}]
    model_metadata = {
        "dim_customer": {
            "table_type": "dimension",
            "atomic_metrics": [{"name": "customer_count"}],
        }
    }

    result = score_model_design_health(
        tables,
        [],
        [],
        model_metadata=model_metadata,
    )

    assert _rule_ids(result) == {"MODEL_DIM_NO_METRIC_GROUPS"}


def test_model_design_flags_dwd_fact_with_non_atomic_metrics():
    tables = [{"name": "dwd_order_detail", "layer": "DWD", "columns": []}]
    model_metadata = {
        "dwd_order_detail": {
            "table_type": "fact",
            "calculated_metrics": [{"name": "gross_profit"}],
        }
    }

    result = score_model_design_health(
        tables,
        [],
        [],
        model_metadata=model_metadata,
    )

    assert "MODEL_DWD_FACT_NO_DERIVED_METRICS" in _rule_ids(result)
