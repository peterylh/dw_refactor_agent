import sqlglot

from lineage.lineage_extractor import (
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

    def test_lineage_simple_select(self, schema_ods_order):
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

    def test_lineage_with_alias(self, schema_ods_order):
        sql = "SELECT o.customer_id AS cid FROM shop_dm.ods_order o"
        nodes = _lineage_nodes_for_select(
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
        )
        assert "cid" in nodes


class TestTraceLineage:
    def test_simple_select(self, schema_ods_order):
        sql = "SELECT order_id, customer_id FROM shop_dm.ods_order"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "target_tbl", "order_id"),
            ("ods_order", "customer_id", "target_tbl", "customer_id"),
        }

    def test_select_with_expression(self, schema_ods_order):
        sql = "SELECT total_amount * 0.1 AS tax FROM shop_dm.ods_order"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert _direct_edges(entries) == {
            ("ods_order", "total_amount", "target_tbl", "tax"),
        }

    def test_select_with_where(self, schema_ods_order):
        sql = "SELECT order_id, total_amount FROM shop_dm.ods_order WHERE store_id = 100"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "target_tbl", "order_id"),
            ("ods_order", "total_amount", "target_tbl", "total_amount"),
        }
        assert _indirect_edges(entries) == {
            ("ods_order", "store_id", "target_tbl", "WHERE"),
        }

    def test_select_constant_no_lineage(self, schema_ods_order):
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

    def test_select_constant_emits_typed_literal_lineage(
        self, schema_ods_order
    ):
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

    def test_nonexistent_table(self, schema_ods_order):
        sql = "SELECT x FROM nonexistent_table"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert entries == []


class TestHandleInsert:
    def test_insert_select_simple(self, schema_ods_order):
        stmt = sqlglot.parse_one(
            "INSERT INTO shop_dm.dwd_order SELECT order_id, customer_id FROM shop_dm.ods_order",
            dialect="doris",
        )
        entries = _handle_insert(stmt, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
        }

    def test_insert_values(self, schema_ods_order):
        stmt = sqlglot.parse_one(
            "INSERT INTO shop_dm.ods_order VALUES (1, 2, 3, '2025-01-01', 100.00, 0.00, 100.00, '微信', '已完成', NULL, NOW())",
            dialect="doris",
        )
        entries = _handle_insert(stmt, "test.sql", schema_ods_order)
        assert entries == []


class TestExtractLineageFromSql:
    def test_insert_select(self, schema_ods_order):
        sql = "INSERT INTO shop_dm.dwd_order SELECT order_id, customer_id, total_amount FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "total_amount", "dwd_order", "total_amount"),
        }

    def test_insert_select_with_func(self, schema_ods_order):
        sql = "INSERT INTO shop_dm.dwd_order SELECT order_id, NOW() AS etl_time FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            (None, None, "dwd_order", "etl_time"),
        }
        etl_entry = next(
            e for e in entries if e["target_column"] == "etl_time"
        )
        assert etl_entry["source_type"] == "expression"
        assert etl_entry["source_expression"] == "NOW() AS etl_time"

    def test_update(self, schema_dwd_customer):
        sql = "UPDATE shop_dm.dwd_customer SET member_level = '金卡' WHERE customer_id = 100"
        entries = extract_lineage_from_sql(
            sql, "test.sql", schema_dwd_customer
        )
        assert _direct_edges(entries) == {
            (None, None, "dwd_customer", "member_level"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_customer", "customer_id", "dwd_customer", "WHERE"),
        }

    def test_ctas(self, schema_ods_order):
        sql = "CREATE TABLE shop_dm.ads_test AS SELECT order_id, total_amount FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "ads_test", "order_id"),
            ("ods_order", "total_amount", "ads_test", "total_amount"),
        }

    def test_multiple_statements(self, schema_ods_order):
        sql = """
        INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order;
        INSERT INTO t2 SELECT customer_id FROM shop_dm.ods_order;
        """
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "t1", "order_id"),
            ("ods_order", "customer_id", "t2", "customer_id"),
        }

    def test_malformed_sql(self, schema_ods_order):
        entries = extract_lineage_from_sql(
            "THIS IS NOT SQL $$$", "bad.sql", schema_ods_order
        )
        assert entries == []

    def test_empty_sql(self, schema_ods_order):
        entries = extract_lineage_from_sql("", "empty.sql", schema_ods_order)
        assert entries == []

    def test_comment_only(self, schema_ods_order):
        entries = extract_lineage_from_sql(
            "-- just a comment", "comment.sql", schema_ods_order
        )
        assert entries == []

    def test_source_file_in_entries(self, schema_ods_order):
        sql = "INSERT INTO t SELECT order_id FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(
            sql, "my_task.sql", schema_ods_order
        )
        for e in entries:
            assert e["source_file"] == "my_task.sql"

    def test_entry_keys(self, schema_ods_order):
        sql = "INSERT INTO t SELECT order_id FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        for e in entries:
            assert "source_table" in e
            assert "source_column" in e
            assert "target_table" in e
            assert "target_column" in e
            assert "expression" in e
            assert "source_file" in e
