from lineage.lineage_extractor import build_lineage_output


def test_build_lineage_output_marks_transient_tables():
    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "order_id",
                "target_table": "tmp_orders_stage",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            },
            {
                "source_table": "tmp_orders_stage",
                "source_column": "order_id",
                "target_table": "dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            },
        ],
        {"shop_dm": {
            "dwd_orders": {"order_id": "BIGINT"},
            "dws_orders": {"order_id": "BIGINT"},
        }},
        transient_tables=[
            {
                "name": "tmp_orders_stage",
                "source_file": "dws_orders.sql",
                "created_statement_index": 0,
                "dropped_statement_index": 2,
                "is_ctas": True,
                "is_transient": True,
                "dropped_in_same_task": True,
            }
        ],
    )

    tmp_table = next(
        table for table in output["tables"]
        if table["name"] == "tmp_orders_stage"
    )
    assert "nodes" not in output
    assert "transient_tables" not in output
    assert tmp_table["is_transient"] is True
    assert tmp_table["transient_sources"] == ["dws_orders.sql"]
    assert tmp_table["transient_occurrences"] == [
        {
            "source_file": "dws_orders.sql",
            "created_statement_index": 0,
            "dropped_statement_index": 2,
            "is_ctas": True,
            "dropped_in_same_task": True,
        }
    ]


def test_build_lineage_output_keeps_transient_table_without_edges_in_tables():
    output = build_lineage_output(
        [],
        {"shop_dm": {
            "dws_orders": {"order_id": "BIGINT"},
        }},
        transient_tables=[
            {
                "name": "tmp_orders_stage",
                "source_file": "tmp_orders_stage.sql",
                "created_statement_index": 0,
                "dropped_statement_index": 1,
                "is_ctas": True,
                "is_transient": True,
                "dropped_in_same_task": True,
            }
        ],
    )

    assert "transient_tables" not in output
    assert output["tables"] == [
        {
            "name": "tmp_orders_stage",
            "full_name": "shop_dm.tmp_orders_stage",
            "layer": "OTHER",
            "columns": [],
            "is_transient": True,
            "transient_sources": ["tmp_orders_stage.sql"],
            "transient_occurrences": [
                {
                    "source_file": "tmp_orders_stage.sql",
                    "created_statement_index": 0,
                    "dropped_statement_index": 1,
                    "is_ctas": True,
                    "dropped_in_same_task": True,
                }
            ],
        },
    ]


def test_build_lineage_output_uses_typed_edges_for_direct_and_group_by():
    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "amount",
                "target_table": "dws_orders",
                "target_column": "total_amount",
                "lineage_type": "direct",
                "expression": "SUM(amount) AS total_amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source_table": "dwd_orders",
                "source_column": "order_date",
                "target_table": "dws_orders",
                "target_column": "",
                "lineage_type": "indirect",
                "condition_type": "GROUP_BY",
                "condition_expression": "order_date",
                "source_file": "dws_orders.sql",
            },
        ],
        {"shop_dm": {
            "dwd_orders": {
                "amount": "DECIMAL(12,2)",
                "order_date": "DATE",
            },
            "dws_orders": {"total_amount": "DECIMAL(12,2)"},
        }},
    )

    assert "nodes" not in output
    assert "transient_tables" not in output
    assert output["edges"] == [
        {
            "source": {"type": "column", "id": "dwd_orders.amount"},
            "target": {"type": "column", "id": "dws_orders.total_amount"},
            "relation_type": "direct",
            "transformation_type": "aggregation",
            "expression": "SUM(amount) AS total_amount",
            "source_file": "dws_orders.sql",
        },
        {
            "source": {"type": "column", "id": "dwd_orders.order_date"},
            "target": {"type": "table", "id": "dws_orders"},
            "relation_type": "group_by",
            "transformation_type": "group_by",
            "expression": "order_date",
            "source_file": "dws_orders.sql",
        },
    ]
    assert "indirect_edges" not in output
