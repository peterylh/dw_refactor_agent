import dw_refactor_agent.lineage.sql_task_facts as sql_task_facts
from dw_refactor_agent.lineage.sql_task_facts import extract_task_table_facts


def test_pre_drop_create_without_post_drop_is_persistent():
    facts = extract_task_table_facts(
        "DROP TABLE IF EXISTS tmp_t; CREATE TABLE tmp_t AS SELECT * FROM src",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"src"}
    assert facts["output_tables"] == {"tmp_t"}
    assert facts["created_tables"] == {"tmp_t"}
    assert facts["temporary_tables"] == set()
    assert facts["local_lifecycle_tables"] == []
    assert facts["transient_tables"][0]["reason"] == (
        "pre_drop_create_without_post_drop"
    )


def test_post_create_drop_is_local_and_not_a_persistent_output():
    facts = extract_task_table_facts(
        """
CREATE TABLE shop_dm.tmp_orders_stage AS
SELECT order_id FROM shop_dm.dwd_orders;
INSERT INTO shop_dm.dws_orders
SELECT order_id FROM shop_dm.tmp_orders_stage;
DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["input_tables"] == {
        "shop_dm.dwd_orders",
        "shop_dm.tmp_orders_stage",
    }
    assert facts["output_tables"] == {"shop_dm.dws_orders"}
    assert facts["created_tables"] == {"shop_dm.tmp_orders_stage"}
    assert facts["temporary_tables"] == set()
    assert facts["local_lifecycle_tables"] == [
        {
            "name": "shop_dm.tmp_orders_stage",
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
    assert facts["transient_tables"] == facts["local_lifecycle_tables"]


def test_temporary_create_is_local_even_without_post_drop():
    facts = extract_task_table_facts(
        """
CREATE TEMPORARY TABLE tmp_t AS SELECT * FROM src;
INSERT INTO out_t SELECT * FROM tmp_t;
""",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"src", "tmp_t"}
    assert facts["output_tables"] == {"out_t"}
    assert facts["temporary_tables"] == {"tmp_t"}
    assert facts["local_lifecycle_tables"] == [
        {
            "name": "tmp_t",
            "source_file": "prepare.sql",
            "created_statement_index": 0,
            "dropped_statement_index": None,
            "is_ctas": True,
            "is_transient": True,
            "dropped_in_same_task": False,
            "pre_drop_statement_indexes": [],
            "reason": "temporary_create_without_post_drop",
            "is_temporary": True,
        }
    ]


def test_later_persistent_recreate_restores_output_eligibility():
    facts = extract_task_table_facts(
        """
CREATE TABLE tmp_t AS SELECT * FROM first_src;
DROP TABLE tmp_t;
CREATE TABLE tmp_t AS SELECT * FROM second_src;
""",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"first_src", "second_src"}
    assert facts["output_tables"] == {"tmp_t"}
    assert facts["local_lifecycle_tables"][0]["dropped_statement_index"] == 1


def test_statement_reads_skip_only_write_target_and_preserve_self_read():
    facts = extract_task_table_facts(
        """
WITH staged AS (SELECT id FROM db.src)
INSERT INTO db.target
SELECT id FROM staged;
INSERT INTO db.target
SELECT id FROM db.target;
""",
        "load.sql",
    )

    assert facts["input_tables"] == {"db.src", "db.target"}
    assert facts["output_tables"] == {"db.target"}


def test_nested_cte_does_not_hide_outer_physical_table_with_same_name():
    facts = extract_task_table_facts(
        """
SELECT *
FROM src
WHERE id IN (
    WITH src AS (SELECT id FROM nested_base)
    SELECT id FROM src
);
""",
        "scope.sql",
    )

    assert facts["input_tables"] == {"src", "nested_base"}


def test_table_aliases_are_not_part_of_task_fact_names():
    facts = extract_task_table_facts(
        """
INSERT INTO db.out
SELECT s.id
FROM db.src AS s
JOIN db.dim AS d ON s.id = d.id;
""",
        "load.sql",
    )

    assert facts["input_tables"] == {"db.src", "db.dim"}
    assert facts["output_tables"] == {"db.out"}


def test_full_table_identity_prevents_cross_database_lifecycle_collision():
    facts = extract_task_table_facts(
        """
CREATE TABLE cat_a.db.t AS SELECT * FROM cat_b.db.src;
SELECT * FROM cat_c.db.src;
DROP TABLE cat_c.db.t;
""",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"cat_b.db.src", "cat_c.db.src"}
    assert facts["output_tables"] == {"cat_a.db.t"}
    assert facts["created_tables"] == {"cat_a.db.t"}
    assert facts["local_lifecycle_tables"] == []


def test_unique_qualified_lifecycle_matches_unqualified_post_drop():
    facts = extract_task_table_facts(
        """
CREATE TABLE shop_dm.t AS SELECT * FROM shop_dm.src;
DROP TABLE t;
        """,
        "prepare.sql",
        default_db="shop_dm",
    )

    assert facts["output_tables"] == set()
    assert facts["local_lifecycle_tables"][0]["name"] == "shop_dm.t"


def test_unqualified_lifecycle_does_not_match_another_database():
    facts = extract_task_table_facts(
        """
CREATE TABLE t AS SELECT * FROM src;
DROP TABLE archive_db.t;
""",
        "prepare.sql",
        default_db="main_db",
    )

    assert facts["output_tables"] == {"t"}
    assert facts["local_lifecycle_tables"] == []


def test_update_join_uses_real_target_and_source_table_nodes():
    facts = extract_task_table_facts(
        """
UPDATE db.t
JOIN db.s ON t.id = s.id
SET t.amount = s.amount
""",
        "update.sql",
    )

    assert facts["input_tables"] == {"db.s"}
    assert facts["output_tables"] == {"db.t"}


def test_regular_create_without_query_is_a_persistent_output():
    facts = extract_task_table_facts(
        "CREATE TABLE db.process_t (id BIGINT)",
        "prepare.sql",
    )

    assert facts["input_tables"] == set()
    assert facts["output_tables"] == {"db.process_t"}


def test_alter_target_is_not_counted_as_an_input():
    facts = extract_task_table_facts(
        "ALTER TABLE db.process_t ADD COLUMN amount BIGINT",
        "alter.sql",
    )

    assert facts["input_tables"] == set()
    assert facts["output_tables"] == set()


def test_select_into_records_create_output_and_source_read():
    facts = extract_task_table_facts(
        "SELECT * INTO db.process_t FROM db.src",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"db.src"}
    assert facts["output_tables"] == {"db.process_t"}
    assert facts["created_tables"] == {"db.process_t"}


def test_lifecycle_matching_is_case_insensitive_and_preserves_display_case():
    facts = extract_task_table_facts(
        """
CREATE TABLE Shop_Dm.Tmp_Orders AS SELECT * FROM Shop_Dm.Source_Orders;
DROP TABLE shop_dm.tmp_orders;
""",
        "prepare.sql",
    )

    assert facts["input_tables"] == {"Shop_Dm.Source_Orders"}
    assert facts["output_tables"] == set()
    assert facts["local_lifecycle_tables"][0]["name"] == ("Shop_Dm.Tmp_Orders")


def test_regex_fallback_collects_reads_and_keeps_pre_drop_create_persistent(
    monkeypatch,
):
    monkeypatch.setattr(
        sql_task_facts,
        "_parse_with_sqlglot",
        lambda *args, **kwargs: None,
    )

    facts = extract_task_table_facts(
        """
DROP TABLE IF EXISTS internal.shop_dm.tmp_orders_stage;
CREATE TABLE internal.shop_dm.tmp_orders_stage AS
SELECT order_id FROM internal.shop_dm.dwd_orders;
INSERT INTO internal.shop_dm.dws_orders
SELECT order_id FROM internal.shop_dm.tmp_orders_stage;
""",
        "dws_orders.sql",
    )

    assert facts["input_tables"] == {
        "internal.shop_dm.dwd_orders",
        "internal.shop_dm.tmp_orders_stage",
    }
    assert facts["output_tables"] == {
        "internal.shop_dm.tmp_orders_stage",
        "internal.shop_dm.dws_orders",
    }
    assert facts["local_lifecycle_tables"] == []
