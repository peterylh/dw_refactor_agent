import sqlglot

from dw_refactor_agent.lineage.lineage_extractor import (
    _extract_leaf_edges,
    _handle_insert,
    _lineage_nodes_for_select,
    _trace_lineage,
    extract_lineage_from_sql,
)


def _direct_edges(entries):
    return {
        (
            e.get("source_table"),
            e.get("source_column"),
            e.get("target_table"),
            e.get("target_column"),
        )
        for e in entries
        if e.get("lineage_type") != "indirect"
    }


def _indirect_edges(entries):
    return {
        (
            e.get("source_table"),
            e.get("source_column"),
            e.get("target_table"),
            e.get("condition_type"),
        )
        for e in entries
        if e.get("lineage_type") == "indirect"
    }


class TestExtractLeafEdges:
    """_extract_leaf_edges 依赖 sqlglot lineage() 输出的 Node 对象"""

    def test_lineage_node_extraction_scenarios(self, schema_ods_order):
        sql = "SELECT customer_id FROM shop_dm.ods_order"
        nodes = _lineage_nodes_for_select(
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
        )
        edges = []
        for col_name, node in nodes.items():
            e = _extract_leaf_edges(node, "target_tbl", col_name)
            edges.extend(e)
        assert _direct_edges(edges) == {
            ("ods_order", "customer_id", "target_tbl", "customer_id"),
        }

        sql = "SELECT o.customer_id AS cid FROM shop_dm.ods_order o"
        nodes = _lineage_nodes_for_select(
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
        )
        assert "cid" in nodes


class TestTraceLineage:
    def test_select_source_lineage_scenarios(self, schema_ods_order):
        scenarios = [
            (
                "simple_select",
                "SELECT order_id, customer_id FROM shop_dm.ods_order",
                {
                    ("ods_order", "order_id", "target_tbl", "order_id"),
                    (
                        "ods_order",
                        "customer_id",
                        "target_tbl",
                        "customer_id",
                    ),
                },
                set(),
            ),
            (
                "expression",
                "SELECT total_amount * 0.1 AS tax FROM shop_dm.ods_order",
                {("ods_order", "total_amount", "target_tbl", "tax")},
                set(),
            ),
            (
                "where",
                (
                    "SELECT order_id, total_amount FROM shop_dm.ods_order "
                    "WHERE store_id = 100"
                ),
                {
                    ("ods_order", "order_id", "target_tbl", "order_id"),
                    (
                        "ods_order",
                        "total_amount",
                        "target_tbl",
                        "total_amount",
                    ),
                },
                {("ods_order", "store_id", "target_tbl", "WHERE")},
            ),
        ]

        for (
            scenario_name,
            sql,
            expected_direct,
            expected_indirect,
        ) in scenarios:
            entries = _trace_lineage(
                "target_tbl",
                sqlglot.parse_one(sql, dialect="doris"),
                schema_ods_order,
                "test.sql",
            )

            assert _direct_edges(entries) == expected_direct, scenario_name
            assert _indirect_edges(entries) == expected_indirect, scenario_name

    def test_select_constant_and_missing_source_scenarios(
        self, schema_ods_order
    ):
        sql = "SELECT 1 AS col, 'abc' AS col2"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        # constants should produce source-free lineage, not UNKNOWN columns.
        assert entries == [
            {
                "lineage_type": "direct",
                "source_type": "literal",
                "source_value": "1",
                "target_table": "target_tbl",
                "target_column": "col",
                "expression": "1 AS col",
                "transformation_type": "constant",
                "source_file": "test.sql",
            },
            {
                "lineage_type": "direct",
                "source_type": "literal",
                "source_value": "abc",
                "target_table": "target_tbl",
                "target_column": "col2",
                "expression": "'abc' AS col2",
                "transformation_type": "constant",
                "source_file": "test.sql",
            },
        ]

        sql = "SELECT 'ALL' AS channel_type"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
            ["channel_type"],
        )

        assert entries == [
            {
                "lineage_type": "direct",
                "source_type": "literal",
                "source_value": "ALL",
                "target_table": "target_tbl",
                "target_column": "channel_type",
                "expression": "'ALL' AS channel_type",
                "transformation_type": "constant",
                "source_file": "test.sql",
            }
        ]

        sql = "SELECT x FROM nonexistent_table"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert entries == []


class TestHandleInsert:
    def test_handle_insert_scenarios(self, schema_ods_order):
        stmt = sqlglot.parse_one(
            "INSERT INTO shop_dm.dwd_order SELECT order_id, customer_id FROM shop_dm.ods_order",
            dialect="doris",
        )
        entries = _handle_insert(stmt, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
        }

        stmt = sqlglot.parse_one(
            "INSERT INTO shop_dm.ods_order VALUES (1, 2, 3, '2025-01-01', 100.00, 0.00, 100.00, '微信', '已完成', NULL, NOW())",
            dialect="doris",
        )
        entries = _handle_insert(stmt, "test.sql", schema_ods_order)
        assert entries == []


class TestExtractLineageFromSql:
    def test_extract_lineage_statement_scenarios(
        self, schema_ods_order, schema_dwd_customer
    ):
        scenarios = [
            (
                "insert_select",
                (
                    "INSERT INTO shop_dm.dwd_order "
                    "SELECT order_id, customer_id, total_amount "
                    "FROM shop_dm.ods_order"
                ),
                schema_ods_order,
                {
                    ("ods_order", "order_id", "dwd_order", "order_id"),
                    ("ods_order", "customer_id", "dwd_order", "customer_id"),
                    ("ods_order", "total_amount", "dwd_order", "total_amount"),
                },
                set(),
            ),
            (
                "insert_select_with_func",
                (
                    "INSERT INTO shop_dm.dwd_order "
                    "SELECT order_id, NOW() AS etl_time "
                    "FROM shop_dm.ods_order"
                ),
                schema_ods_order,
                {
                    ("ods_order", "order_id", "dwd_order", "order_id"),
                    (None, None, "dwd_order", "etl_time"),
                },
                set(),
            ),
            (
                "update",
                (
                    "UPDATE shop_dm.dwd_customer SET member_level = '金卡' "
                    "WHERE customer_id = 100"
                ),
                schema_dwd_customer,
                {(None, None, "dwd_customer", "member_level")},
                {("dwd_customer", "customer_id", "dwd_customer", "WHERE")},
            ),
            (
                "ctas",
                (
                    "CREATE TABLE shop_dm.ads_test AS "
                    "SELECT order_id, total_amount FROM shop_dm.ods_order"
                ),
                schema_ods_order,
                {
                    ("ods_order", "order_id", "ads_test", "order_id"),
                    ("ods_order", "total_amount", "ads_test", "total_amount"),
                },
                set(),
            ),
            (
                "multiple_statements",
                """
                INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order;
                INSERT INTO t2 SELECT customer_id FROM shop_dm.ods_order;
                """,
                schema_ods_order,
                {
                    ("ods_order", "order_id", "t1", "order_id"),
                    ("ods_order", "customer_id", "t2", "customer_id"),
                },
                set(),
            ),
        ]

        for (
            scenario_name,
            sql,
            schema,
            expected_direct,
            expected_indirect,
        ) in scenarios:
            entries = extract_lineage_from_sql(sql, "test.sql", schema)

            assert _direct_edges(entries) == expected_direct, scenario_name
            assert _indirect_edges(entries) == expected_indirect, scenario_name

        sql = (
            "INSERT INTO shop_dm.dwd_order "
            "SELECT order_id, NOW() AS etl_time FROM shop_dm.ods_order"
        )
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        etl_entry = next(
            e for e in entries if e["target_column"] == "etl_time"
        )
        assert etl_entry["source_type"] == "expression"
        assert etl_entry["source_expression"] == "NOW() AS etl_time"

    def test_extract_lineage_ignores_unparseable_or_empty_sql(
        self, schema_ods_order
    ):
        scenarios = [
            ("malformed", "THIS IS NOT SQL $$$", "bad.sql"),
            ("empty", "", "empty.sql"),
            ("comment_only", "-- just a comment", "comment.sql"),
        ]

        for scenario_name, sql, source_file in scenarios:
            entries = extract_lineage_from_sql(
                sql, source_file, schema_ods_order
            )
            assert entries == [], scenario_name

    def test_extract_lineage_entry_contract(self, schema_ods_order):
        sql = "INSERT INTO t SELECT order_id FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(
            sql, "my_task.sql", schema_ods_order
        )
        for e in entries:
            assert e["source_file"] == "my_task.sql"
            assert "source_table" in e
            assert "source_column" in e
            assert "target_table" in e
            assert "target_column" in e
            assert "expression" in e
