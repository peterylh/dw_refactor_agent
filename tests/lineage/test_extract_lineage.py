from lineage.lineage_extractor import (
    build_schema_from_texts,
    extract_lineage_from_sql,
)

# DDL for the full test fixture
DDL_ODS_ORDER = """
DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id       BIGINT        NOT NULL COMMENT '订单ID',
    customer_id    BIGINT        NOT NULL COMMENT '客户ID',
    store_id       BIGINT        NOT NULL COMMENT '门店ID',
    order_date     DATE          NOT NULL COMMENT '订单日期',
    total_amount   DECIMAL(12,2) NOT NULL COMMENT '订单总额',
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    payment_amount DECIMAL(12,2) NOT NULL COMMENT '实付金额',
    payment_method VARCHAR(16)   NULL COMMENT '支付方式',
    order_status   VARCHAR(16)   NOT NULL DEFAULT '已完成' COMMENT '订单状态',
    promotion_id   BIGINT        NULL COMMENT '促销活动ID',
    create_time    DATETIME      NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_DWD_ORDER = """
DROP TABLE IF EXISTS shop_dm.dwd_order;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_order (
    order_id        BIGINT        NOT NULL COMMENT '订单ID',
    customer_id     BIGINT        NOT NULL COMMENT '客户ID',
    store_id        BIGINT        NOT NULL COMMENT '门店ID',
    order_date      DATE          NOT NULL COMMENT '订单日期',
    total_amount    DECIMAL(12,2) NOT NULL COMMENT '订单总额',
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    payment_amount  DECIMAL(12,2) NOT NULL COMMENT '实付金额',
    etl_time        DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_ODS_CUSTOMER = """
DROP TABLE IF EXISTS shop_dm.ods_customer;
CREATE TABLE IF NOT EXISTS shop_dm.ods_customer (
    customer_id   BIGINT       NOT NULL COMMENT '客户ID',
    customer_name VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender        VARCHAR(4)   NULL COMMENT '性别',
    age           INT          NULL COMMENT '年龄',
    member_level  VARCHAR(16)  NULL COMMENT '会员等级',
    register_date DATE         NULL COMMENT '注册日期',
    create_time   DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_DWD_CUSTOMER = """
DROP TABLE IF EXISTS shop_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_customer (
    customer_id   BIGINT       NOT NULL COMMENT '客户ID',
    customer_name VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender        VARCHAR(4)   NULL COMMENT '性别',
    age           INT          NULL COMMENT '年龄',
    member_level  VARCHAR(16)  NULL COMMENT '会员等级',
    register_date DATE         NULL COMMENT '注册日期',
    etl_time      DATETIME     NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_DWS_DAILY = """
DROP TABLE IF EXISTS shop_dm.dws_daily_sales;
CREATE TABLE IF NOT EXISTS shop_dm.dws_daily_sales (
    order_date   DATE          NOT NULL COMMENT '订单日期',
    total_amount DECIMAL(12,2) NULL COMMENT '总金额',
    order_count  BIGINT        NULL COMMENT '订单数',
    etl_time     DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
DUPLICATE KEY(order_date)
DISTRIBUTED BY HASH(order_date) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

ALL_DDLS = [
    DDL_ODS_ORDER,
    DDL_DWD_ORDER,
    DDL_ODS_CUSTOMER,
    DDL_DWD_CUSTOMER,
    DDL_DWS_DAILY,
]


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


class TestIntegrationEtlToDwd:
    """Test the standard ODS → DWD ETL pattern"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)

    def test_ods_to_dwd_select(self):
        """INSERT SELECT from ods_order to dwd_order"""
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT order_id, customer_id, store_id, order_date,
               total_amount, discount_amount, payment_amount,
               NOW() AS etl_time
        FROM shop_dm.ods_order
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "total_amount", "dwd_order", "total_amount"),
            (None, None, "dwd_order", "etl_time"),
        }
        etl_entries = [e for e in entries if e["target_column"] == "etl_time"]
        assert etl_entries == [
            {
                "lineage_type": "direct",
                "source_type": "expression",
                "source_expression": "NOW() AS etl_time",
                "target_table": "dwd_order",
                "target_column": "etl_time",
                "expression": "NOW() AS etl_time",
                "transformation_type": "constant",
                "source_file": "dwd_order.sql",
            }
        ]

    def test_ods_to_dwd_with_customer(self):
        """INSERT SELECT with JOIN from ods_order + ods_customer to dwd_order"""
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT o.order_id, o.customer_id, o.store_id, o.order_date,
               o.total_amount, o.discount_amount, o.payment_amount,
               NOW() AS etl_time
        FROM shop_dm.ods_order o
        LEFT JOIN shop_dm.ods_customer c ON o.customer_id = c.customer_id
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "payment_amount", "dwd_order", "payment_amount"),
        }
        assert _indirect_edges(entries) == {
            ("ods_order", "customer_id", "dwd_order", "JOIN_ON"),
            ("ods_customer", "customer_id", "dwd_order", "JOIN_ON"),
        }

    def test_ods_to_dwd_with_filter(self):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT order_id, customer_id, store_id, order_date,
               total_amount, discount_amount, payment_amount,
               NOW() AS etl_time
        FROM shop_dm.ods_order
        WHERE order_status = '已完成'
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "payment_amount", "dwd_order", "payment_amount"),
        }
        assert _indirect_edges(entries) == {
            ("ods_order", "order_status", "dwd_order", "WHERE"),
        }

    def test_dwd_to_dws_aggregation(self):
        """DWD → DWS aggregation pattern"""
        sql = """
        INSERT INTO shop_dm.dws_daily_sales
        SELECT
            order_date,
            SUM(total_amount) AS total_amount,
            COUNT(DISTINCT order_id) AS order_count,
            NOW() AS etl_time
        FROM shop_dm.dwd_order
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

    def test_dwd_to_dws_with_filter(self):
        sql = """
        INSERT INTO shop_dm.dws_daily_sales
        SELECT order_date, SUM(total_amount) AS total_amount,
               COUNT(DISTINCT order_id) AS order_count, NOW() AS etl_time
        FROM shop_dm.dwd_order
        WHERE total_amount > 0
        GROUP BY order_date
        """
        entries = extract_lineage_from_sql(
            sql, "dws_daily_sales.sql", self.schema
        )
        assert _direct_edges(entries) >= {
            ("dwd_order", "total_amount", "dws_daily_sales", "total_amount"),
            ("dwd_order", "order_id", "dws_daily_sales", "order_count"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_order", "total_amount", "dws_daily_sales", "WHERE"),
            ("dwd_order", "order_date", "dws_daily_sales", "GROUP_BY"),
        }

    def test_complex_expression_propagation(self):
        """Test that expressions like SUM() propagate to source columns"""
        sql = """
        INSERT INTO shop_dm.dws_daily_sales
        SELECT order_date, SUM(total_amount) AS total_amount,
               COUNT(DISTINCT order_id) AS order_count, NOW() AS etl_time
        FROM shop_dm.dwd_order
        GROUP BY order_date
        """
        entries = extract_lineage_from_sql(
            sql, "dws_daily_sales.sql", self.schema
        )
        assert (
            "dwd_order",
            "total_amount",
            "dws_daily_sales",
            "total_amount",
        ) in _direct_edges(entries)


class TestIntegrationUpdatePattern:
    """Test UPDATE statements commonly used in ETL tasks"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)

    def test_simple_update_default(self):
        sql = """
        UPDATE shop_dm.dwd_customer
        SET member_level = '普通'
        WHERE member_level IS NULL
        """
        entries = extract_lineage_from_sql(
            sql, "dwd_customer.sql", self.schema
        )
        assert _direct_edges(entries) == {
            (None, None, "dwd_customer", "member_level"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_customer", "member_level", "dwd_customer", "WHERE"),
        }

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


class TestEdgeCases:
    """Edge cases that should not crash"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)

    def test_ctas_with_subquery(self):
        sql = """
        CREATE TABLE shop_dm.ads_top_products AS
        SELECT order_id, total_amount
        FROM shop_dm.dwd_order
        WHERE total_amount > 100
        """
        entries = extract_lineage_from_sql(
            sql, "ads_top_products.sql", self.schema
        )
        assert _direct_edges(entries) == {
            ("dwd_order", "order_id", "ads_top_products", "order_id"),
            ("dwd_order", "total_amount", "ads_top_products", "total_amount"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_order", "total_amount", "ads_top_products", "WHERE"),
        }

    def test_insert_with_target_column_list_uses_plain_target_table(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (
            order_id,
            customer_id,
            total_amount
        )
        SELECT order_id, customer_id, total_amount
        FROM shop_dm.ods_order
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "total_amount", "dwd_order", "total_amount"),
        }

    def test_insert_with_target_column_list_maps_by_position(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (
            customer_id,
            order_id
        )
        SELECT order_id, customer_id
        FROM shop_dm.ods_order
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        direct = {
            (e["source_column"], e["target_column"])
            for e in entries
            if e.get("lineage_type") != "indirect"
        }
        assert ("order_id", "customer_id") in direct
        assert ("customer_id", "order_id") in direct

    def test_insert_without_target_column_list_maps_to_ddl_columns_by_position(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
            CREATE TABLE shop_dm.ods_customer (
                customer_id BIGINT,
                customer_name VARCHAR(64)
            )
            """,
                """
            CREATE TABLE shop_dm.M_SHOP_01_CUST_DF (
                CUSTOMER_ID BIGINT,
                CUSTOMER_NAME VARCHAR(64)
            )
            """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.M_SHOP_01_CUST_DF
        SELECT customer_id, customer_name
        FROM shop_dm.ods_customer
        """
        entries = extract_lineage_from_sql(sql, "dwd_customer.sql", schema)
        direct = {
            (e["source_column"], e["target_column"])
            for e in entries
            if e.get("lineage_type") != "indirect"
        }

        assert ("customer_id", "CUSTOMER_ID") in direct
        assert ("customer_name", "CUSTOMER_NAME") in direct
        assert {target for _, target in direct} == {
            "CUSTOMER_ID",
            "CUSTOMER_NAME",
        }

    def test_insert_without_target_column_list_with_bare_table_ddl(self):
        schema = build_schema_from_texts(
            [
                """
            CREATE TABLE ods_customer (
                customer_id BIGINT,
                customer_name VARCHAR(64)
            )
            """,
                """
            CREATE TABLE M_SHOP_01_CUST_DF (
                CUSTOMER_ID BIGINT,
                CUSTOMER_NAME VARCHAR(64)
            )
            """,
            ]
        )
        sql = """
        INSERT INTO M_SHOP_01_CUST_DF
        SELECT customer_id, customer_name
        FROM ods_customer
        """
        entries = extract_lineage_from_sql(sql, "dwd_customer.sql", schema)
        direct = {
            (e["source_column"], e["target_column"])
            for e in entries
            if e.get("lineage_type") != "indirect"
        }

        assert ("customer_id", "CUSTOMER_ID") in direct
        assert ("customer_name", "CUSTOMER_NAME") in direct
        assert {target for _, target in direct} == {
            "CUSTOMER_ID",
            "CUSTOMER_NAME",
        }

    def test_insert_lineage_preserves_three_part_table_names(self):
        schema = build_schema_from_texts(
            [
                """
            CREATE TABLE hive.shop_dm.ods_customer (
                customer_id BIGINT,
                customer_name VARCHAR(64)
            )
            """,
                """
            CREATE TABLE hive.shop_dm.M_SHOP_01_CUST_DF (
                CUSTOMER_ID BIGINT,
                CUSTOMER_NAME VARCHAR(64)
            )
            """,
            ]
        )
        sql = """
        INSERT INTO hive.shop_dm.M_SHOP_01_CUST_DF
        SELECT customer_id, customer_name
        FROM hive.shop_dm.ods_customer
        """

        entries = extract_lineage_from_sql(sql, "dwd_customer.sql", schema)

        assert _direct_edges(entries) == {
            (
                "hive.shop_dm.ods_customer",
                "customer_id",
                "hive.shop_dm.M_SHOP_01_CUST_DF",
                "CUSTOMER_ID",
            ),
            (
                "hive.shop_dm.ods_customer",
                "customer_name",
                "hive.shop_dm.M_SHOP_01_CUST_DF",
                "CUSTOMER_NAME",
            ),
        }

    def test_quoted_columns_are_canonicalized_in_lineage_entries(self):
        schema = {
            "shop_dm": {
                "M_SHOP_01_SRC_DF": {"CUSTOMER_ID": "BIGINT"},
                "M_SHOP_01_CUST_DF": {"CUSTOMER_ID": "BIGINT"},
            }
        }
        sql = """
        INSERT INTO shop_dm.M_SHOP_01_CUST_DF (`CUSTOMER_ID`)
        SELECT `CUSTOMER_ID`
        FROM shop_dm.M_SHOP_01_SRC_DF
        """
        entries = extract_lineage_from_sql(sql, "quoted.sql", schema)
        direct = [e for e in entries if e.get("lineage_type") != "indirect"]

        assert direct
        assert {e["source_column"] for e in direct} == {"CUSTOMER_ID"}
        assert {e["target_column"] for e in direct} == {"CUSTOMER_ID"}
        assert {e["source_table"] for e in direct} == {"M_SHOP_01_SRC_DF"}
        assert {e["target_table"] for e in direct} == {"M_SHOP_01_CUST_DF"}

    def test_quoted_alias_column_is_canonicalized_in_lineage_entries(self):
        schema = {
            "shop_dm": {
                "M_SHOP_01_SRC_DF": {"CUSTOMER_ID": "BIGINT"},
                "M_SHOP_01_CUST_DF": {"CUSTOMER_ID": "BIGINT"},
            }
        }
        sql = """
        INSERT INTO shop_dm.M_SHOP_01_CUST_DF (`CUSTOMER_ID`)
        SELECT s.`CUSTOMER_ID`
        FROM shop_dm.M_SHOP_01_SRC_DF s
        """
        entries = extract_lineage_from_sql(
            sql, "quoted_alias_column.sql", schema
        )

        assert _direct_edges(entries) == {
            (
                "M_SHOP_01_SRC_DF",
                "CUSTOMER_ID",
                "M_SHOP_01_CUST_DF",
                "CUSTOMER_ID",
            ),
        }

    def test_quoted_projection_alias_is_canonicalized_in_lineage_entries(self):
        schema = {
            "shop_dm": {
                "M_SHOP_01_SRC_DF": {"CUSTOMER_ID": "BIGINT"},
                "M_SHOP_01_CUST_DF": {"CUSTOMER_ID": "BIGINT"},
            }
        }
        sql = """
        INSERT INTO shop_dm.M_SHOP_01_CUST_DF (`CUSTOMER_ID`)
        SELECT s.customer_id AS `CUSTOMER_ID`
        FROM shop_dm.M_SHOP_01_SRC_DF s
        """
        entries = extract_lineage_from_sql(
            sql, "quoted_projection_alias.sql", schema
        )

        assert _direct_edges(entries) == {
            (
                "M_SHOP_01_SRC_DF",
                "CUSTOMER_ID",
                "M_SHOP_01_CUST_DF",
                "CUSTOMER_ID",
            ),
        }

    def test_lineage_extraction_is_case_insensitive(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.M_SHOP_01_SRC_DF (
                    CUSTOMER_ID BIGINT,
                    ORDER_AMOUNT DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.M_SHOP_01_CUST_DF (
                    CUSTOMER_ID BIGINT,
                    ORDER_AMOUNT DECIMAL(12,2)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.m_shop_01_cust_df (customer_id, order_amount)
        SELECT s.customer_id, s.order_amount
        FROM shop_dm.m_shop_01_src_df s
        WHERE s.customer_id > 0
        """

        entries = extract_lineage_from_sql(sql, "case.sql", schema)

        assert _direct_edges(entries) == {
            (
                "M_SHOP_01_SRC_DF",
                "CUSTOMER_ID",
                "M_SHOP_01_CUST_DF",
                "CUSTOMER_ID",
            ),
            (
                "M_SHOP_01_SRC_DF",
                "ORDER_AMOUNT",
                "M_SHOP_01_CUST_DF",
                "ORDER_AMOUNT",
            ),
        }
        assert _indirect_edges(entries) == {
            (
                "M_SHOP_01_SRC_DF",
                "CUSTOMER_ID",
                "M_SHOP_01_CUST_DF",
                "WHERE",
            )
        }

    def test_lineage_extraction_matches_lowercase_aliased_column_to_uppercase_ddl(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_a (
                    MORTAGAGE_AMT DECIMAL(18,2)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_b (
                    MORTAGAGE_AMT DECIMAL(18,2)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO dwd_b
        SELECT a.mortagage_amt
        FROM ods_a a
        """

        entries = extract_lineage_from_sql(sql, "case_aliased.sql", schema)

        assert _direct_edges(entries) == {
            ("ods_a", "MORTAGAGE_AMT", "dwd_b", "MORTAGAGE_AMT"),
        }

    def test_lineage_extraction_does_not_use_target_for_unaliased_lowercase_column(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_a (
                    MORTAGAGE_AMT DECIMAL(18,2)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_b (
                    MORTAGAGE_AMT DECIMAL(18,2)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO dwd_b
        SELECT mortagage_amt
        FROM ods_a
        """

        entries = extract_lineage_from_sql(sql, "case_unaliased.sql", schema)

        assert _direct_edges(entries) == {
            ("ods_a", "MORTAGAGE_AMT", "dwd_b", "MORTAGAGE_AMT"),
        }

    def test_ctas_with_column_definitions_uses_plain_target_table(self):
        sql = """
        CREATE TABLE shop_dm.dws_daily_sales (
            order_date DATE,
            total_amount DECIMAL(12,2)
        ) AS
        SELECT order_date, total_amount
        FROM shop_dm.dwd_order
        """
        entries = extract_lineage_from_sql(
            sql, "dws_daily_sales.sql", self.schema
        )
        assert _direct_edges(entries) == {
            ("dwd_order", "order_date", "dws_daily_sales", "order_date"),
            ("dwd_order", "total_amount", "dws_daily_sales", "total_amount"),
        }

    def test_select_into(self):
        sql = """
        SELECT order_id, total_amount
        INTO shop_dm.ads_backup
        FROM shop_dm.dwd_order
        """
        entries = extract_lineage_from_sql(sql, "backup.sql", self.schema)
        assert _direct_edges(entries) == {
            ("dwd_order", "order_id", "ads_backup", "order_id"),
            ("dwd_order", "total_amount", "ads_backup", "total_amount"),
        }

    def test_multiple_inserts_in_one_file(self):
        sql = """
        TRUNCATE TABLE shop_dm.dwd_order;

        INSERT INTO shop_dm.dwd_order
        SELECT order_id, customer_id, store_id, order_date,
               total_amount, discount_amount, payment_amount,
               NOW() AS etl_time
        FROM shop_dm.ods_order;

        UPDATE shop_dm.dwd_order
        SET payment_amount = 0
        WHERE payment_amount IS NULL;
        """
        entries = extract_lineage_from_sql(sql, "dwd_order.sql", self.schema)
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "payment_amount", "dwd_order", "payment_amount"),
            (None, None, "dwd_order", "payment_amount"),
        }
        assert _indirect_edges(entries) == {
            ("dwd_order", "payment_amount", "dwd_order", "WHERE"),
        }

    def test_all_source_files_have_name(self):
        sql = """
        INSERT INTO shop_dm.dwd_order SELECT order_id FROM shop_dm.ods_order;
        """
        entries = extract_lineage_from_sql(sql, "my_task.sql", self.schema)
        for e in entries:
            assert e["source_file"] == "my_task.sql"

    def test_no_duplicate_entries(self):
        sql = """
        INSERT INTO shop_dm.dwd_order SELECT order_id, order_id AS oid FROM shop_dm.ods_order;
        """
        entries = extract_lineage_from_sql(sql, "test.sql", self.schema)
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "order_id", "dwd_order", "customer_id"),
        }

    def test_indirect_lineage_resolves_derived_table_alias(self):
        schema = {
            "shop_dm": {
                "ods_product": {
                    "product_id": "BIGINT",
                    "category_id": "BIGINT",
                    "load_time": "DATETIME",
                },
                "ods_category": {"category_id": "BIGINT"},
                "dwd_product": {"product_id": "BIGINT"},
            }
        }
        sql = """
        INSERT INTO shop_dm.dwd_product
        SELECT p.product_id
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY product_id ORDER BY load_time DESC
                ) AS rn
            FROM shop_dm.ods_product
        ) p
        LEFT JOIN shop_dm.ods_category c ON p.category_id = c.category_id
        WHERE p.rn = 1
        """
        entries = extract_lineage_from_sql(sql, "dwd_product.sql", schema)
        indirect = [e for e in entries if e.get("lineage_type") == "indirect"]
        sources = {(e["source_table"], e["source_column"]) for e in indirect}
        assert ("p", "rn") not in sources
        assert ("p", "category_id") not in sources
        assert ("ods_product", "category_id") in sources
        assert ("ods_product", "product_id") in sources
        assert ("ods_product", "load_time") in sources
        assert ("ods_product", "rn") not in sources

    def test_indirect_lineage_resolves_cte_alias(self):
        schema = {
            "shop_dm": {
                "dws_product_sales_daily": {
                    "product_id": "BIGINT",
                    "sale_quantity": "BIGINT",
                    "stat_date": "DATE",
                },
                "dws_inventory_daily": {"product_id": "BIGINT"},
                "ads_inventory_alert": {
                    "product_id": "BIGINT",
                    "daily_sales_velocity": "DECIMAL(12,2)",
                },
            }
        }
        sql = """
        INSERT INTO shop_dm.ads_inventory_alert
        WITH sales_velocity AS (
            SELECT
                product_id,
                AVG(sale_quantity) AS daily_sales_velocity
            FROM shop_dm.dws_product_sales_daily
            GROUP BY product_id
        )
        SELECT
            inv.product_id,
            sv.daily_sales_velocity
        FROM shop_dm.dws_inventory_daily inv
        LEFT JOIN sales_velocity sv ON inv.product_id = sv.product_id
        GROUP BY inv.product_id, sv.daily_sales_velocity
        """
        entries = extract_lineage_from_sql(
            sql, "ads_inventory_alert.sql", schema
        )
        indirect = [e for e in entries if e.get("lineage_type") == "indirect"]
        sources = {(e["source_table"], e["source_column"]) for e in indirect}
        assert not any(e["source_table"] == "sales_velocity" for e in indirect)
        assert ("dws_product_sales_daily", "product_id") in sources
        assert ("dws_product_sales_daily", "sale_quantity") in sources

    def test_task_ctas_transient_table_keeps_raw_segment_edges(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.dwd_orders (
                    order_id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.dws_orders (
                    order_id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
            ]
        )
        sql = """
        CREATE TABLE shop_dm.tmp_orders_stage AS
        SELECT
            order_id,
            amount
        FROM shop_dm.dwd_orders;

        INSERT INTO shop_dm.dws_orders
        SELECT
            order_id,
            amount
        FROM shop_dm.tmp_orders_stage;

        DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;
        """

        entries = extract_lineage_from_sql(sql, "dws_orders.sql", schema)
        direct = _direct_edges(entries)

        assert direct >= {
            ("dwd_orders", "order_id", "tmp_orders_stage", "order_id"),
            ("dwd_orders", "amount", "tmp_orders_stage", "amount"),
            ("tmp_orders_stage", "order_id", "dws_orders", "order_id"),
            ("tmp_orders_stage", "amount", "dws_orders", "amount"),
        }
        assert (
            "dws_orders",
            "order_id",
            "dws_orders",
            "order_id",
        ) not in direct
        assert (
            "dwd_orders",
            "order_id",
            "dws_orders",
            "order_id",
        ) not in direct
