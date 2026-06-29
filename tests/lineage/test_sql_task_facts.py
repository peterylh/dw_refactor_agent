import lineage.sql_task_facts as sql_task_facts
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
            "pre_drop_statement_indexes": [],
            "reason": "created_then_dropped_in_same_task",
        }
    ]


def test_extract_task_table_facts_keeps_pre_drop_metadata_when_later_dropped():
    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;

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
            "created_statement_index": 1,
            "dropped_statement_index": 3,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": True,
            "pre_drop_statement_indexes": [0],
            "reason": "created_then_dropped_in_same_task",
        }
    ]


def test_extract_task_table_facts_marks_pre_dropped_tmp_ctas_transient_without_drop():
    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;

CREATE TABLE shop_dm.tmp_orders_stage AS
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
            "created_statement_index": 1,
            "dropped_statement_index": None,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": False,
            "pre_drop_statement_indexes": [0],
            "reason": "pre_drop_create_without_post_drop",
        }
    ]


def test_extract_task_table_facts_strips_comment_after_create_target():
    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base FORCE;

CREATE TABLE IF NOT EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base
/* 算收入 */ AS
SELECT order_id
FROM cdm.dwd_orders;
""",
        "a_ibank.sql",
    )

    assert facts["transient_tables"] == [
        {
            "name": "tmp_A_IBANK_CUST_IND_D__20260601_5_base",
            "source_file": "a_ibank.sql",
            "created_statement_index": 1,
            "dropped_statement_index": None,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": False,
            "pre_drop_statement_indexes": [0],
            "reason": "pre_drop_create_without_post_drop",
        }
    ]


def test_extract_task_table_facts_keeps_repeated_same_name_lifecycles():
    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;

CREATE TABLE shop_dm.tmp_orders_stage AS
SELECT order_id, amount
FROM shop_dm.dwd_orders;

INSERT INTO shop_dm.dws_orders
SELECT order_id, amount
FROM shop_dm.tmp_orders_stage;

DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;

CREATE TABLE shop_dm.tmp_orders_stage AS
SELECT order_id, amount
FROM shop_dm.dwd_orders_retry;

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
            "created_statement_index": 1,
            "dropped_statement_index": 3,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": True,
            "pre_drop_statement_indexes": [0],
            "reason": "created_then_dropped_in_same_task",
        },
        {
            "name": "tmp_orders_stage",
            "source_file": "dws_orders.sql",
            "created_statement_index": 4,
            "dropped_statement_index": None,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": False,
            "pre_drop_statement_indexes": [3],
            "reason": "pre_drop_create_without_post_drop",
        },
    ]


def test_extract_task_table_facts_regex_fallback_handles_qualified_pre_drop(
    monkeypatch,
):
    monkeypatch.setattr(
        sql_task_facts,
        "_parse_with_sqlglot",
        lambda sql_text, source_file: None,
    )

    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS internal.shop_dm.tmp_orders_stage;

CREATE TABLE internal.shop_dm.tmp_orders_stage AS
SELECT order_id, amount
FROM internal.shop_dm.dwd_orders;

INSERT INTO internal.shop_dm.dws_orders
SELECT order_id, amount
FROM internal.shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["output_tables"] == {"dws_orders"}
    assert facts["transient_tables"][0]["name"] == "tmp_orders_stage"
    assert facts["transient_tables"][0]["reason"] == (
        "pre_drop_create_without_post_drop"
    )


def test_extract_task_table_facts_pairs_mixed_case_qualified_temp_table():
    facts = extract_task_table_facts(
        """
CREATE TABLE Shop_Dm.Tmp_Orders_Stage AS
SELECT 1 AS order_id;

DROP TABLE shop_dm.tmp_orders_stage;

INSERT INTO DWS_ORDERS
SELECT order_id FROM shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["output_tables"] == {"DWS_ORDERS"}
    assert facts["transient_tables"] == [
        {
            "name": "Tmp_Orders_Stage",
            "source_file": "dws_orders.sql",
            "created_statement_index": 0,
            "dropped_statement_index": 1,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": True,
            "pre_drop_statement_indexes": [],
            "reason": "created_then_dropped_in_same_task",
        }
    ]
