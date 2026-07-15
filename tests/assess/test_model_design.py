from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.rules.dimensions.model_design import (
    score_model_design_health,
)
from tests.case_matrix import case_matrix


def _models_from_tables(tables):
    return {
        table["name"]: {"name": table["name"], "layer": table["layer"]}
        for table in tables
        if table.get("name") and table.get("layer")
    }


def _merge_model_layers(tables, models):
    merged = {
        name: dict(metadata) for name, metadata in (models or {}).items()
    }
    for table in tables:
        name = table.get("name")
        layer = table.get("layer")
        if not name or not layer:
            continue
        metadata = merged.setdefault(name, {})
        metadata.setdefault("name", name)
        metadata.setdefault("layer", layer)
    return merged


def _context(
    tables,
    edges=None,
    indirect_edges=None,
    *,
    models=None,
    business_domain_config=None,
    assets=None,
):
    models = (
        _merge_model_layers(tables, models)
        if models is not None
        else _models_from_tables(tables)
    )
    return AssessmentContext.from_facts(
        tables=tables,
        edges=edges or [],
        indirect_edges=indirect_edges or [],
        models=models,
        business_domain_config=business_domain_config,
        assets=assets,
    )


def _rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def test_model_design_flags_dwd_fact_with_group_by():
    asset_catalog = {
        "tables": {
            "dwd_order_summary": {
                "tasks": [
                    {
                        "source_file": "dwd_order_summary.sql",
                        "sql": """
                    INSERT INTO shop_dm.dwd_order_summary
                    SELECT order_id, SUM(subtotal) AS subtotal
                    FROM shop_dm.ods_order_item
                    GROUP BY order_id;
                    """,
                    }
                ],
            },
        },
    }
    tables = [
        {
            "name": "dwd_order_summary",
            "layer": "DWD",
            "columns": [
                {"name": "order_id", "type": "BIGINT"},
                {"name": "subtotal", "type": "DECIMAL(12,2)"},
            ],
        }
    ]
    model_metadata = {
        "dwd_order_summary": {
            "table_type": "fact",
            "entities": [
                {
                    "code": "ORDER",
                    "type": "primary",
                    "key_columns": ["order_id"],
                }
            ],
        }
    }

    context = _context(
        tables,
        [],
        [],
        models=model_metadata,
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    assert _rule_ids(result) == {"MODEL_DWD_FACT_NO_AGGREGATION"}


def test_model_design_matches_dws_grain_columns_case_insensitively():
    asset_catalog = {
        "tables": {
            "dws_customer_sales_daily": {
                "tasks": [
                    {
                        "source_file": "dws_customer_sales_daily.sql",
                        "sql": """
                    INSERT INTO shop_dm.dws_customer_sales_daily
                    SELECT Customer_ID, STAT_DATE, SUM(pay_amt) AS pay_amt
                    FROM shop_dm.dwd_payment_detail
                    GROUP BY Customer_ID, STAT_DATE;
                    """,
                    }
                ],
            },
        },
    }
    tables = [
        {"name": "dws_customer_sales_daily", "layer": "DWS", "columns": []}
    ]
    edges = [
        {
            "source": {
                "type": "column",
                "id": "dwd_payment_detail.customer_id",
            },
            "target": {
                "type": "column",
                "id": "dws_customer_sales_daily.Customer_ID",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "customer_id AS Customer_ID",
            "source_file": "dws_customer_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_payment_detail.pay_amt"},
            "target": {
                "type": "column",
                "id": "dws_customer_sales_daily.pay_amt",
            },
            "relation_type": "direct",
            "transformation_type": "aggregation",
            "expression": "SUM(pay_amt) AS pay_amt",
            "source_file": "dws_customer_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_payment_detail.stat_date"},
            "target": {"type": "table", "id": "dws_customer_sales_daily"},
            "relation_type": "group_by",
            "transformation_type": "group_by",
            "expression": "STAT_DATE",
            "source_file": "dws_customer_sales_daily.sql",
        },
    ]
    model_metadata = {
        "dws_customer_sales_daily": {
            "table_type": "fact",
            "entities": [
                {
                    "code": "CUSTOMER",
                    "type": "foreign",
                    "key_columns": ["CUSTOMER_ID"],
                }
            ],
            "grain": {
                "entities": ["CUSTOMER"],
                "time_column": "stat_date",
            },
        }
    }

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    assert "MODEL_DWS_GRAIN_MATCHES_GROUP_BY" not in _rule_ids(result)
    assert "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN" not in _rule_ids(result)


def test_model_design_flags_dws_fact_without_aggregation_from_typed_edges():
    tables = [
        {
            "name": "dws_store_sales_daily",
            "layer": "DWS",
            "columns": [
                {"name": "store_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
                {"name": "sale_amount", "type": "DECIMAL(12,2)"},
            ],
        }
    ]
    edges = [
        {
            "source": {"type": "column", "id": "dwd_order_detail.store_id"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.store_id",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "store_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.order_date"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.stat_date",
            },
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

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
    )
    result = score_model_design_health(context)

    assert "MODEL_DWS_FACT_HAS_AGGREGATION" in _rule_ids(result)


def test_model_design_flags_dws_plain_field_not_in_group_by_from_typed_edges():
    tables = [{"name": "dws_store_sales_daily", "layer": "DWS", "columns": []}]
    edges = [
        {
            "source": {"type": "column", "id": "dwd_order_detail.store_id"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.store_id",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "store_id",
            "source_file": "dws_store_sales_daily.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_order_detail.order_date"},
            "target": {
                "type": "column",
                "id": "dws_store_sales_daily.stat_date",
            },
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

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
    )
    result = score_model_design_health(context)

    assert "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN" in _rule_ids(result)
    check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN"
        and not check["passed"]
    )
    assert check["evidence"]["leaked_columns"] == ["customer_id"]
    assert "channel_type" not in check["evidence"]["leaked_columns"]


@case_matrix(
    ("sql", "evidence_field", "reason_code"),
    [
        (
            """
            INSERT INTO shop_dm.dim_base_customer_info
            SELECT customer_id, COUNT(*) AS order_count
            FROM shop_dm.ods_order
            GROUP BY customer_id;
            """,
            "aggregate_columns",
            "aggregate_output",
        ),
        (
            """
            INSERT INTO shop_dm.dim_base_customer_info
            SELECT customer_id,
                   COUNT(*) OVER (
                       PARTITION BY customer_id
                   ) AS order_count
            FROM shop_dm.ods_order;
            """,
            "window_metric_columns",
            "window_metric",
        ),
    ],
    ids=("aggregate", "window-metric"),
)
def test_model_design_flags_dim_info_with_metric_output(
    sql, evidence_field, reason_code
):
    asset_catalog = {
        "tables": {
            "dim_base_customer_info": {
                "tasks": [
                    {
                        "source_file": "dim_base_customer_info.sql",
                        "sql": sql,
                    }
                ],
            },
        },
    }
    tables = [
        {"name": "ods_order", "layer": "ODS", "columns": []},
        {"name": "dim_base_customer_info", "layer": "DIM", "columns": []},
    ]
    model_metadata = {
        "dim_base_customer_info": {
            "table_type": "dimension",
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
        }
    }

    context = _context(
        tables,
        [],
        [],
        models=model_metadata,
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    assert "MODEL_DIM_INFO_DIRECT_ODS_ONLY" in _rule_ids(result)
    check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "MODEL_DIM_INFO_DIRECT_ODS_ONLY"
    )
    assert check["evidence"][evidence_field] == ["order_count"]
    assert check["evidence"]["reason_codes"] == [reason_code]


def test_model_design_allows_dim_info_from_ods_with_cleaning_and_dedup():
    asset_catalog = {
        "tables": {
            "dim_base_customer_info": {
                "tasks": [
                    {
                        "source_file": "dim_base_customer_info.sql",
                        "sql": """
                        INSERT INTO shop_dm.dim_base_customer_info
                        SELECT customer_id,
                               TRIM(customer_name) AS customer_name,
                               CASE gender_code
                                   WHEN 'M' THEN 'male'
                                   WHEN 'F' THEN 'female'
                                   ELSE 'unknown'
                               END AS gender_name
                        FROM (
                            SELECT customer_id,
                                   customer_name,
                                   gender_code,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY customer_id
                                       ORDER BY updated_at DESC
                                   ) AS rn
                            FROM shop_dm.ods_customer
                        ) t
                        WHERE rn = 1;
                        """,
                    }
                ],
            },
        },
    }
    tables = [
        {"name": "ods_customer", "layer": "ODS", "columns": []},
        {"name": "dim_base_customer_info", "layer": "DIM", "columns": []},
    ]
    edges = [
        {
            "source": {
                "type": "column",
                "id": "ods_customer.customer_name",
            },
            "target": {
                "type": "column",
                "id": "dim_base_customer_info.customer_name",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": "TRIM(customer_name) AS customer_name",
            "source_file": "dim_base_customer_info.sql",
        }
    ]
    model_metadata = {
        "dim_base_customer_info": {
            "table_type": "dimension",
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
        }
    }

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    assert "MODEL_DIM_INFO_DIRECT_ODS_ONLY" not in _rule_ids(result)


def test_score_model_design_uses_context_lineage_view():
    calls = {"fact_tables": []}

    class FakeLineageView:
        def __init__(self, base):
            self.base = base

        def tables(self):
            return self.base.tables()

        def asset_table_graph(self):
            return self.base.asset_table_graph()

        def table_edge_source_files(self):
            return self.base.table_edge_source_files()

        def lineage_facts_for_table(self, table_name):
            calls["fact_tables"].append(table_name)
            return {
                "has_lineage": False,
                "has_group_by": False,
                "has_aggregate": False,
                "aggregate_columns": [],
                "constant_columns": [],
                "plain_columns": [],
                "plain_column_sources": {},
                "group_by_sources": [],
                "source_files": [],
            }

    context = _context(
        [
            {"name": "dws_orders", "layer": "DWS", "columns": []},
            {"name": "dws_payments", "layer": "DWS", "columns": []},
        ],
        [],
        [],
        models={
            "dws_orders": {
                "table_type": "fact",
                "grain": {"keys": ["id"]},
            },
            "dws_payments": {
                "table_type": "fact",
                "grain": {"keys": ["id"]},
            },
        },
    )
    context.lineage = FakeLineageView(context.lineage)

    score_model_design_health(context)

    assert calls == {
        "fact_tables": ["dws_orders", "dws_payments"],
    }


def test_model_design_flags_partition_column_not_data_dt(tmp_path):
    ddl_path = tmp_path / "dwd_order_detail.sql"
    ddl_path.write_text(
        """
        CREATE TABLE shop_dm.dwd_order_detail (
            order_id BIGINT NOT NULL,
            order_date DATE NOT NULL,
            subtotal DECIMAL(12,2) NULL
        )
        UNIQUE KEY(order_id, order_date)
        PARTITION BY RANGE(order_date) (
            PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
        )
        DISTRIBUTED BY HASH(order_id) BUCKETS 1;
        """,
        encoding="utf-8",
    )
    tables = [
        {
            "name": "dwd_order_detail",
            "layer": "DWD",
            "columns": [
                {"name": "order_id", "type": "BIGINT"},
                {"name": "order_date", "type": "DATE"},
                {"name": "subtotal", "type": "DECIMAL(12,2)"},
            ],
        }
    ]
    model_metadata = {
        "dwd_order_detail": {
            "table_type": "fact",
            "business_process": "ORDER_TRANSACTION",
            "entities": [
                {
                    "code": "ORDER",
                    "type": "primary",
                    "key_columns": ["order_id"],
                }
            ],
        }
    }
    asset_catalog = {
        "tables": {
            "dwd_order_detail": {
                "ddl": {"path": ddl_path},
                "tasks": [],
            }
        }
    }

    context = _context(
        tables,
        [],
        [],
        models=model_metadata,
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    assert "MODEL_DATE_PARTITION_USES_DATA_DT" in _rule_ids(result)


def test_model_design_flags_derived_metric_without_upstream_atomic_base():
    tables = [
        {"name": "dwd_order_detail", "layer": "DWD", "columns": []},
        {"name": "dws_store_sales_daily", "layer": "DWS", "columns": []},
    ]
    edges = [
        {
            "source": "dwd_order_detail.subtotal",
            "target": "dws_store_sales_daily.sale_amount",
            "source_file": "dws_store_sales_daily.sql",
        }
    ]
    model_metadata = {
        "dwd_order_detail": {
            "table_type": "fact",
            "atomic_metrics": ["quantity"],
        },
        "dws_store_sales_daily": {
            "table_type": "fact",
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "base_metric": "subtotal",
                    "base_metric_table": "dwd_order_detail",
                    "aggregation": "SUM",
                },
                {
                    "name": "unknown_amount",
                    "aggregation": "SUM",
                },
            ],
        },
    }

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
    )
    result = score_model_design_health(context)

    assert "MODEL_DERIVED_METRIC_BASE_ATOMIC" in _rule_ids(result)
    check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "MODEL_DERIVED_METRIC_BASE_ATOMIC"
    )
    assert check["evidence"]["missing_base_metrics"] == ["unknown_amount"]
    assert check["evidence"]["invalid_base_metrics"] == [
        "sale_amount:dwd_order_detail.subtotal"
    ]


def test_model_design_flags_ambiguous_derived_metric_base_table():
    tables = [
        {"name": "dwd_order_detail", "layer": "DWD", "columns": []},
        {"name": "dwd_refund_detail", "layer": "DWD", "columns": []},
        {"name": "dws_sales_daily", "layer": "DWS", "columns": []},
    ]
    edges = [
        {
            "source": "dwd_order_detail.subtotal",
            "target": "dws_sales_daily.sale_amount",
            "source_file": "dws_sales_daily.sql",
        },
        {
            "source": "dwd_refund_detail.subtotal",
            "target": "dws_sales_daily.refund_amount",
            "source_file": "dws_sales_daily.sql",
        },
    ]
    model_metadata = {
        "dwd_order_detail": {
            "table_type": "fact",
            "atomic_metrics": ["subtotal"],
        },
        "dwd_refund_detail": {
            "table_type": "fact",
            "atomic_metrics": ["subtotal"],
        },
        "dws_sales_daily": {
            "table_type": "fact",
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "base_metric": "subtotal",
                    "aggregation": "SUM",
                }
            ],
        },
    }

    context = _context(
        tables,
        edges,
        [],
        models=model_metadata,
    )
    result = score_model_design_health(context)

    check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "MODEL_DERIVED_METRIC_BASE_ATOMIC"
    )
    assert check["evidence"]["ambiguous_base_metrics"] == [
        "sale_amount:subtotal"
    ]
