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
    assert output["transient_tables"] == [
        {
            "name": "tmp_orders_stage",
            "source_file": "dws_orders.sql",
            "created_statement_index": 0,
            "dropped_statement_index": 2,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": True,
        }
    ]
    assert tmp_table["is_transient"] is True
    assert tmp_table["transient_sources"] == ["dws_orders.sql"]
