from lineage.sql_task_facts import extract_task_table_facts


def test_extract_task_table_facts_marks_created_then_dropped_ctas_transient():
    facts = extract_task_table_facts(
        """
CREATE TABLE shop_dm.tmp_orders_stage AS
SELECT order_id, amount
FROM shop_dm.dwd_orders;

INSERT INTO shop_dm.dws_orders
SELECT order_id, amount
FROM shop_dm.tmp_orders_stage;

DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["output_tables"] == {"dws_orders"}
    assert facts["transient_tables"] == [
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


def test_extract_task_table_facts_marks_temporary_ctas_transient_without_drop():
    facts = extract_task_table_facts(
        """
CREATE TEMPORARY TABLE shop_dm.tmp_orders_stage AS
SELECT order_id, amount
FROM shop_dm.dwd_orders;

INSERT INTO shop_dm.dws_orders
SELECT order_id, amount
FROM shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["output_tables"] == {"dws_orders"}
    assert facts["transient_tables"] == [
        {
            "name": "tmp_orders_stage",
            "source_file": "dws_orders.sql",
            "created_statement_index": 0,
            "dropped_statement_index": None,
            "is_ctas": True,
            "is_temporary": True,
            "is_transient": True,
            "dropped_in_same_task": False,
        }
    ]
