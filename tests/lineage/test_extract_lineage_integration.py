from tests.lineage.test_extract_lineage import (
    ALL_DDLS,
    _direct_edges,
    _indirect_edges,
    build_schema_from_texts,
    extract_lineage_from_sql,
)


class TestIntegrationUpdatePattern:
    """Test UPDATE statements commonly used in ETL tasks"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)

    def test_update_case_when(self):
        sql = """
        UPDATE shop_dm.dwd_customer
        SET member_level = CASE
            WHEN age < 30 THEN '青年'
            WHEN age < 45 THEN '中年'
            ELSE member_level
        END
        WHERE member_level IS NULL
        """
        entries = extract_lineage_from_sql(
            sql, "dwd_customer.sql", self.schema
        )
        assert _direct_edges(entries) == {
            ("dwd_customer", "age", "dwd_customer", "member_level"),
            ("dwd_customer", "member_level", "dwd_customer", "member_level"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_customer", "member_level", "dwd_customer", "WHERE"),
        }


class TestIntegrationMultiTable:
    """Test multi-table scenarios"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)
        # Add extra table for join tests
        cls.schema["internal"]["shop_dm"]["ods_store"] = {
            "store_id": "BIGINT",
            "store_name": "VARCHAR(64)",
            "city": "VARCHAR(32)",
        }

    def test_join_two_tables(self):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT o.order_id, o.customer_id, o.store_id, o.order_date,
               o.total_amount, o.discount_amount, o.payment_amount,
               NOW() AS etl_time
        FROM shop_dm.ods_order o
        LEFT JOIN shop_dm.ods_store s ON o.store_id = s.store_id
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "store_id", "dwd_order", "store_id"),
        }
        assert _indirect_edges(entries) == {
            ("ods_order", "store_id", "dwd_order", "JOIN_ON"),
            ("ods_store", "store_id", "dwd_order", "JOIN_ON"),
        }

    def test_union_all(self):
        sql = """
        INSERT INTO shop_dm.dws_daily_sales
        SELECT order_date, SUM(total_amount) AS total_amount,
               COUNT(DISTINCT order_id) AS order_count, NOW() AS etl_time
        FROM (
            SELECT order_date, total_amount, order_id FROM shop_dm.dwd_order
            UNION ALL
            SELECT order_date, total_amount, order_id FROM shop_dm.dwd_order
        ) t
        GROUP BY order_date
        """
        entries = extract_lineage_from_sql(
            sql, "dws_daily_sales.sql", self.schema
        )
        assert _direct_edges(entries) >= {
            ("dwd_order", "order_date", "dws_daily_sales", "order_date"),
            ("dwd_order", "total_amount", "dws_daily_sales", "total_amount"),
            ("dwd_order", "order_id", "dws_daily_sales", "order_count"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_order", "order_date", "dws_daily_sales", "GROUP_BY"),
        }
