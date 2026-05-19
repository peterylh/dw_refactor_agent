import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage
from lineage.lineage_extractor import (
    extract_lineage_from_sql,
    _trace_lineage,
    _extract_leaf_edges,
    _handle_insert,
)


class TestExtractLeafEdges:
    """_extract_leaf_edges 依赖 sqlglot lineage() 输出的 Node 对象"""

    def test_lineage_simple_select(self, schema_ods_order):
        sql = "SELECT customer_id FROM shop_dm.ods_order"
        nodes = lineage(column=None, sql=sql, schema=schema_ods_order, dialect="doris")
        edges = []
        for col_name, node in nodes.items():
            e = _extract_leaf_edges(node, "target_tbl", col_name)
            edges.extend(e)
        for e in edges:
            assert e["source_table"] is not None
            assert e["source_column"] is not None
            assert e["target_table"] == "target_tbl"
            assert e["target_column"] is not None

    def test_lineage_with_alias(self, schema_ods_order):
        sql = "SELECT o.customer_id AS cid FROM shop_dm.ods_order o"
        nodes = lineage(column=None, sql=sql, schema=schema_ods_order, dialect="doris")
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
        assert len(entries) >= 2
        tables = {e["source_table"] for e in entries}
        assert "ods_order" in tables
        assert all(e["target_table"] == "target_tbl" for e in entries)

    def test_select_with_expression(self, schema_ods_order):
        sql = "SELECT total_amount * 0.1 AS tax FROM shop_dm.ods_order"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert len(entries) >= 1
        assert entries[0]["source_column"] == "total_amount"

    def test_select_with_where(self, schema_ods_order):
        sql = (
            "SELECT order_id, total_amount FROM shop_dm.ods_order WHERE store_id = 100"
        )
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        assert len(entries) >= 2

    def test_select_constant_no_lineage(self, schema_ods_order):
        sql = "SELECT 1 AS col, 'abc' AS col2"
        entries = _trace_lineage(
            "target_tbl",
            sqlglot.parse_one(sql, dialect="doris"),
            schema_ods_order,
            "test.sql",
        )
        # constants should produce no source column lineage
        for e in entries:
            assert e["source_table"] != "UNKNOWN"
            assert e["source_column"] != "UNKNOWN"

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
        assert len(entries) >= 2

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
        assert len(entries) == 3

    def test_insert_select_with_func(self, schema_ods_order):
        sql = "INSERT INTO shop_dm.dwd_order SELECT order_id, NOW() AS etl_time FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert len(entries) >= 1

    def test_update(self, schema_dwd_customer):
        sql = "UPDATE shop_dm.dwd_customer SET member_level = '金卡' WHERE customer_id = 100"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_dwd_customer)
        assert isinstance(entries, list)

    def test_ctas(self, schema_ods_order):
        sql = "CREATE TABLE shop_dm.ads_test AS SELECT order_id, total_amount FROM shop_dm.ods_order"
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert len(entries) >= 2

    def test_multiple_statements(self, schema_ods_order):
        sql = """
        INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order;
        INSERT INTO t2 SELECT customer_id FROM shop_dm.ods_order;
        """
        entries = extract_lineage_from_sql(sql, "test.sql", schema_ods_order)
        assert len(entries) >= 2

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
        entries = extract_lineage_from_sql(sql, "my_task.sql", schema_ods_order)
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
