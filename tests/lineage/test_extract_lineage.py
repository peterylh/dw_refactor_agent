import sqlglot

from lineage.lineage_extractor import (
    _created_table_columns_from_schema,
    build_lineage_output,
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

    def test_insert_select_metric_literals_are_not_source_columns(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_metric (
                    metric_value DECIMAL(18,4),
                    dt DATE
                )
                """,
                """
                CREATE TABLE shop_dm.ads_metric (
                    metric_code VARCHAR(300),
                    metric_value DECIMAL(18,4),
                    measure_index VARCHAR(300),
                    updated_at DATETIME,
                    optional_note STRING,
                    dt DATE
                )
                """,
            ]
        )
        cases = [
            (
                "ads_metric_alias.sql",
                """
                INSERT INTO shop_dm.ads_metric
                SELECT
                    'ZBJ00000093',
                    metric_value,
                    'ZBJ00000092' AS measure_index,
                    NOW() AS updated_at,
                    NULL AS optional_note,
                    dt
                FROM shop_dm.src_metric
                """,
            ),
            (
                "ads_metric_no_alias.sql",
                """
                INSERT INTO shop_dm.ads_metric
                SELECT
                    'ZBJ00000093',
                    metric_value,
                    'ZBJ00000092',
                    NOW(),
                    NULL,
                    dt
                FROM shop_dm.src_metric
                """,
            ),
            (
                "ads_metric_explicit_insert_columns.sql",
                """
                INSERT INTO shop_dm.ads_metric (
                    metric_code,
                    metric_value,
                    measure_index,
                    updated_at,
                    optional_note,
                    dt
                )
                SELECT
                    'ZBJ00000093',
                    metric_value,
                    'ZBJ00000092',
                    NOW(),
                    NULL,
                    dt
                FROM shop_dm.src_metric
                """,
            ),
        ]

        for file_path, sql in cases:
            entries = extract_lineage_from_sql(
                sql,
                file_path,
                schema,
            )
            output = build_lineage_output(entries, schema)

            assert _direct_edges(entries) == {
                (
                    "src_metric",
                    "metric_value",
                    "ads_metric",
                    "metric_value",
                ),
                ("src_metric", "dt", "ads_metric", "dt"),
                (None, None, "ads_metric", "metric_code"),
                (None, None, "ads_metric", "measure_index"),
                (None, None, "ads_metric", "updated_at"),
                (None, None, "ads_metric", "optional_note"),
            }
            constant_sources = {
                entry["target_column"]: entry["source_type"]
                for entry in entries
                if entry.get("transformation_type") == "constant"
            }
            assert constant_sources == {
                "metric_code": "literal",
                "measure_index": "literal",
                "updated_at": "expression",
                "optional_note": "expression",
            }
            column_source_ids = {
                edge["source"].get("id")
                for edge in output["edges"]
                if edge["source"].get("type") == "column"
            }
            assert column_source_ids == {
                "src_metric.dt",
                "src_metric.metric_value",
            }
            all_column_names = {
                column["name"]
                for table in output["tables"]
                for column in table["columns"]
            }
            assert not {"ZBJ00000092", "ZBJ00000093", "NOW", "NULL"} & (
                all_column_names - {"metric_code", "measure_index"}
            )

    def test_insert_union_metric_literals_are_not_lineage_columns(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_metric (
                    metric_value DECIMAL(18,4)
                )
                """,
                """
                CREATE TABLE shop_dm.ads_metric (
                    metric_code VARCHAR(300),
                    measure_index VARCHAR(300),
                    metric_value DECIMAL(18,4)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.ads_metric
        SELECT
            'ZBJ00000093',
            'ZBJ00000092' AS measure_index,
            metric_value
        FROM shop_dm.src_metric
        UNION ALL
        SELECT
            'ZBJ00000093',
            'ZBJ00000092' AS measure_index,
            metric_value
        FROM shop_dm.src_metric
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ads_metric_union.sql",
            schema,
            diagnostics=diagnostics,
        )
        output = build_lineage_output(entries, schema)

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "src_metric",
                "metric_value",
                "ads_metric",
                "metric_value",
            ),
            (None, None, "ads_metric", "metric_code"),
            (None, None, "ads_metric", "measure_index"),
        }
        constant_sources = {
            entry["target_column"]: entry["source_type"]
            for entry in entries
            if entry.get("transformation_type") == "constant"
        }
        assert constant_sources == {
            "metric_code": "literal",
            "measure_index": "literal",
        }
        column_source_ids = {
            edge["source"].get("id")
            for edge in output["edges"]
            if edge["source"].get("type") == "column"
        }
        assert column_source_ids == {"src_metric.metric_value"}
        all_column_names = {
            column["name"]
            for table in output["tables"]
            for column in table["columns"]
        }
        assert not {"ZBJ00000092", "ZBJ00000093"} & all_column_names

    def test_ctas_metric_literals_are_not_source_columns(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_metric (
                    metric_value DECIMAL(18,4),
                    dt DATE
                )
                """,
            ]
        )
        cases = [
            (
                "ctas_metric_alias.sql",
                """
                CREATE TABLE shop_dm.ads_metric AS
                SELECT
                    'ZBJ00000093' AS metric_code,
                    metric_value,
                    'ZBJ00000092' AS measure_index,
                    NOW() AS updated_at,
                    NULL AS optional_note,
                    dt
                FROM shop_dm.src_metric
                """,
            ),
            (
                "ctas_metric_column_defs.sql",
                """
                CREATE TABLE shop_dm.ads_metric (
                    metric_code VARCHAR(300),
                    metric_value DECIMAL(18,4),
                    measure_index VARCHAR(300),
                    updated_at DATETIME,
                    optional_note STRING,
                    dt DATE
                ) AS
                SELECT
                    'ZBJ00000093',
                    metric_value,
                    'ZBJ00000092' AS measure_index,
                    NOW(),
                    NULL,
                    dt
                FROM shop_dm.src_metric
                """,
            ),
        ]

        for file_path, sql in cases:
            entries = extract_lineage_from_sql(
                sql,
                file_path,
                schema,
            )
            output = build_lineage_output(entries, schema)

            assert _direct_edges(entries) == {
                (
                    "src_metric",
                    "metric_value",
                    "ads_metric",
                    "metric_value",
                ),
                ("src_metric", "dt", "ads_metric", "dt"),
                (None, None, "ads_metric", "metric_code"),
                (None, None, "ads_metric", "measure_index"),
                (None, None, "ads_metric", "updated_at"),
                (None, None, "ads_metric", "optional_note"),
            }
            constant_sources = {
                entry["target_column"]: entry["source_type"]
                for entry in entries
                if entry.get("transformation_type") == "constant"
            }
            assert constant_sources == {
                "metric_code": "literal",
                "measure_index": "literal",
                "updated_at": "expression",
                "optional_note": "expression",
            }
            column_source_ids = {
                edge["source"].get("id")
                for edge in output["edges"]
                if edge["source"].get("type") == "column"
            }
            assert column_source_ids == {
                "src_metric.dt",
                "src_metric.metric_value",
            }
            all_column_names = {
                column["name"]
                for table in output["tables"]
                for column in table["columns"]
            }
            assert not {"ZBJ00000092", "ZBJ00000093", "NOW", "NULL"} & (
                all_column_names - {"metric_code", "measure_index"}
            )

    def test_ctas_parenthesized_column_projection_keeps_lineage(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.a12_cust_tag_list_t2 (
                    cust_num STRING,
                    cust_type STRING,
                    data_dt STRING
                )
                """,
            ]
        )
        sql = """
        CREATE TABLE IF NOT EXISTS tmp_a10_cdm_corp_biz_info_t2_01
        DISTRIBUTED BY RANDOM BUCKETS 15 AS
        SELECT DISTINCT
          (
            cust_num
          ),
          cust_type AS cust_type_cd,
          CASE
            WHEN cust_type = '1' THEN '存量客户'
            WHEN cust_type = '2' THEN '沉睡客户'
            WHEN cust_type = '3' THEN '流失客户'
            WHEN cust_type = '4' THEN '空客户'
          END AS cust_type
        FROM cdm.a12_cust_tag_list_t2
        WHERE data_dt = '20260601'
        """

        entries = extract_lineage_from_sql(
            sql,
            "ctas_parenthesized_column.sql",
            schema,
        )

        assert (
            "cdm.a12_cust_tag_list_t2",
            "cust_num",
            "tmp_a10_cdm_corp_biz_info_t2_01",
            "cust_num",
        ) in _direct_edges(entries)

    def test_insert_alias_star_names_anonymous_literal_by_target_position(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.i10_bill_org_index_amt_sum (
                    id STRING,
                    data_Dt DATE,
                    org_num STRING,
                    org_num_lv STRING,
                    index_id STRING
                );
                CREATE TABLE i00_org_info_lvl_dim (
                    data_Dt DATE,
                    dept_code_lv5 STRING
                );
                CREATE TABLE index_dict (
                    index_id STRING,
                    org_num STRING
                );
                """,
            ]
        )
        sql = """
        INSERT INTO cdm.i10_bill_org_index_amt_sum (
          id,
          data_Dt,
          org_num,
          org_num_lv,
          index_id
        )
        SELECT
          NULL AS id,
          aa.*
        FROM (
          SELECT
            info.data_Dt,
            info.dept_code_lv5 AS org_num,
            '', /* dim.org_num_lv as org_num_lv */
            dict.index_id
          FROM i00_org_info_lvl_dim AS info
          JOIN index_dict AS dict
            ON info.dept_code_lv5 = dict.org_num
        ) AS aa
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "insert_alias_star_anonymous_literal.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert (
            "i00_org_info_lvl_dim",
            "dept_code_lv5",
            "cdm.i10_bill_org_index_amt_sum",
            "org_num",
        ) in _direct_edges(entries)
        literal_entries = [
            entry
            for entry in entries
            if entry.get("target_column") == "org_num_lv"
        ]
        assert literal_entries == [
            {
                "lineage_type": "direct",
                "source_type": "literal",
                "source_value": "",
                "target_table": "cdm.i10_bill_org_index_amt_sum",
                "target_column": "org_num_lv",
                "expression": "'' /* dim.org_num_lv as org_num_lv */ AS org_num_lv",
                "transformation_type": "constant",
                "source_file": "insert_alias_star_anonymous_literal.sql",
            }
        ]

    def test_insert_alias_star_aligns_expanded_columns_to_targets(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.i10_bill_org_index_amt_sum (
                    id BIGINT,
                    data_dt DATE,
                    org_num STRING,
                    org_num_lv STRING,
                    index_id STRING,
                    index_nm STRING,
                    cnt BIGINT
                );
                CREATE TABLE i00_org_info_lvl_dim (
                    data_Dt DATE,
                    dept_code_lv5 STRING
                );
                CREATE TABLE org_dim (
                    dept_code_lv STRING,
                    org_num_lv STRING
                );
                CREATE TABLE index_dict (
                    index_id STRING,
                    index_nm STRING,
                    org_num STRING
                );
                """,
            ]
        )
        sql = """
        INSERT INTO cdm.i10_bill_org_index_amt_sum (
          id,
          data_dt,
          org_num,
          org_num_lv,
          index_id,
          index_nm,
          cnt
        )
        SELECT
          NULL AS id,
          aa.*
        FROM (
          SELECT
            info.data_Dt,
            dim.dept_code_lv AS org_num,
            dim.org_num_lv AS org_num_lv,
            dict.index_id,
            dict.index_nm,
            COUNT(*) AS cnt
          FROM i00_org_info_lvl_dim AS info
          JOIN org_dim AS dim
            ON info.dept_code_lv5 = dim.dept_code_lv
          JOIN index_dict AS dict
            ON dim.dept_code_lv = dict.org_num
          GROUP BY
            info.data_Dt,
            dim.dept_code_lv,
            dim.org_num_lv,
            dict.index_id,
            dict.index_nm
        ) AS aa
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "insert_alias_star_target_alignment.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        direct_edges = _direct_edges(entries)
        assert (
            "i00_org_info_lvl_dim",
            "data_dt",
            "cdm.i10_bill_org_index_amt_sum",
            "data_dt",
        ) in direct_edges
        assert (
            "i00_org_info_lvl_dim",
            "data_dt",
            "cdm.i10_bill_org_index_amt_sum",
            "id",
        ) not in direct_edges
        assert (
            "aa",
            "cnt",
            "cdm.i10_bill_org_index_amt_sum",
            "cnt",
        ) not in direct_edges
        cnt_entries = [
            entry for entry in entries if entry.get("target_column") == "cnt"
        ]
        assert cnt_entries == [
            {
                "lineage_type": "direct",
                "source_type": "expression",
                "source_expression": "COUNT(*) AS cnt",
                "target_table": "cdm.i10_bill_org_index_amt_sum",
                "target_column": "cnt",
                "expression": "COUNT(*) AS cnt",
                "transformation_type": "constant",
                "source_file": "insert_alias_star_target_alignment.sql",
            }
        ]

    def test_ctas_parenthesized_select_registers_transient_schema(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE m10_txn_transfer_disc (
                    node_no STRING,
                    data_Dt DATE
                );
                CREATE TABLE i00_org_info_lvl_dim (
                    dept_code_lv STRING,
                    dept_code_lv5 STRING,
                    data_Dt DATE
                );
                """,
            ]
        )
        sql = """
        CREATE TABLE IF NOT EXISTS tmp_i10_bill_transfer_disc_org_sum_202606021
        DISTRIBUTED BY HASH (
          node_no
        ) AS
        (
          SELECT
            *
          FROM (
            SELECT
              a1.node_no,
              a2.dept_code_lv5,
              ROW_NUMBER() OVER (
                PARTITION BY a1.node_no
                ORDER BY a2.dept_code_lv5
              ) AS rn
            FROM (
              SELECT DISTINCT
                COALESCE(node_no, 'MGMT9999') AS node_no
              FROM m10_txn_transfer_disc
              WHERE
                data_Dt = CAST('20260602' AS DATE)
            ) AS a1
            LEFT JOIN i00_org_info_lvl_dim AS a2
              ON a1.node_no = a2.dept_code_lv
              AND a2.data_Dt = CAST('20260602' AS DATE)
          ) AS aa
          WHERE
            aa.rn = 1
        )
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ctas_parenthesized_select_transient_schema.sql",
            schema,
            diagnostics=diagnostics,
        )
        output = build_lineage_output(entries, schema)
        stmt = sqlglot.parse_one(sql, dialect="doris")

        assert diagnostics == []
        assert _created_table_columns_from_schema(stmt, schema) == [
            "node_no",
            "dept_code_lv5",
            "rn",
        ]
        assert (
            "i00_org_info_lvl_dim",
            "dept_code_lv5",
            "tmp_i10_bill_transfer_disc_org_sum_202606021",
            "dept_code_lv5",
        ) in _direct_edges(entries)
        transient_table = next(
            table
            for table in output["tables"]
            if table["name"] == "tmp_i10_bill_transfer_disc_org_sum_202606021"
        )
        assert {column["name"] for column in transient_table["columns"]} == {
            "node_no",
            "dept_code_lv5",
            "rn",
        }


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


class TestSelectStarLineage:
    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_order (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.ods_customer (
                    customer_id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2),
                    etl_time DATETIME
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order_customer (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2),
                    customer_name VARCHAR(64)
                )
                """,
            ]
        )

    def test_insert_select_star_expands_physical_table_columns(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        SELECT *
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "select_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_task_alter_add_column_updates_ctas_schema_for_later_star(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.src (
                    id BIGINT
                )
                """,
            ],
            default_db="cdm",
        )
        sql = """
        CREATE TABLE cdm.tmp AS
        SELECT id FROM cdm.src;

        ALTER TABLE cdm.tmp ADD COLUMN name STRING;

        CREATE TABLE cdm.tmp_out AS
        SELECT t.* FROM cdm.tmp AS t;
        """

        entries = extract_lineage_from_sql(
            sql,
            "alter_add_column_star.sql",
            schema,
        )

        assert _direct_edges(entries) >= {
            ("cdm.src", "id", "cdm.tmp", "id"),
            ("cdm.tmp", "id", "cdm.tmp_out", "id"),
            ("cdm.tmp", "name", "cdm.tmp_out", "name"),
        }

    def test_ctas_unaliased_complex_expression_does_not_become_column_name(
        self,
    ):
        sql = """
        CREATE TABLE cdm.tmp AS
        SELECT COALESCE(
            CASE
                WHEN t1.xd_used_amt >= 40000000 THEN 40000000
                ELSE t1.xd_used_amt
            END
        )
        FROM cdm.src AS t1;

        CREATE TABLE cdm.tmp_out AS
        SELECT t.* FROM cdm.tmp AS t;
        """

        entries = extract_lineage_from_sql(sql, "ctas_expr_star.sql", {})

        assert not any(
            "COALESCE" in str(edge_part)
            for edge in _direct_edges(entries)
            for edge_part in edge
        )

    def test_insert_select_alias_star_expands_only_alias_columns(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        SELECT o.*
        FROM shop_dm.ods_order o
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "alias_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_insert_select_star_then_expression_keeps_target_alignment(self):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT *, NOW() AS etl_time
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "star_then_expr.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
            (None, None, "dwd_order", "etl_time"),
        }
        assert [
            entry
            for entry in entries
            if entry.get("transformation_type") == "constant"
        ] == [
            {
                "lineage_type": "direct",
                "source_type": "expression",
                "source_expression": "NOW() AS etl_time",
                "target_table": "dwd_order",
                "target_column": "etl_time",
                "expression": "NOW() AS etl_time",
                "transformation_type": "constant",
                "source_file": "star_then_expr.sql",
            }
        ]

    def test_insert_select_star_expands_subquery_outputs(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        SELECT *
        FROM (
            SELECT order_id, customer_id, amount
            FROM shop_dm.ods_order
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "subquery_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_subquery_star_inlines_unaliased_constant_projection(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_bill_detail (
                    bill_no STRING
                )
                """,
                """
                CREATE TABLE shop_dm.rept_bill_detail (
                    id STRING,
                    bill_no STRING,
                    data_dt DATE
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.rept_bill_detail
        SELECT
            NULL AS id,
            t.*
        FROM (
            SELECT
                bill_no,
                TO_DATE('20260602')
            FROM shop_dm.src_bill_detail
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "a_rept_bill_dtl_d.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) >= {
            (
                "src_bill_detail",
                "bill_no",
                "rept_bill_detail",
                "bill_no",
            ),
            (None, None, "rept_bill_detail", "id"),
            (None, None, "rept_bill_detail", "data_dt"),
        }
        data_dt_entries = [
            entry
            for entry in entries
            if entry.get("target_column") == "data_dt"
        ]
        assert len(data_dt_entries) == 1
        assert data_dt_entries[0]["lineage_type"] == "direct"
        assert data_dt_entries[0]["source_type"] == "expression"
        assert data_dt_entries[0]["target_table"] == "rept_bill_detail"
        assert data_dt_entries[0]["target_column"] == "data_dt"
        assert data_dt_entries[0]["transformation_type"] == "constant"
        assert data_dt_entries[0]["source_file"] == "a_rept_bill_dtl_d.sql"
        assert "TO_DATE('20260602')" in data_dt_entries[0]["expression"]
        assert not any(
            entry.get("target_column") == "20260602" for entry in entries
        )

    def test_insert_select_star_expands_cte_outputs(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        WITH cleaned AS (
            SELECT order_id, customer_id, amount
            FROM shop_dm.ods_order
        )
        SELECT *
        FROM cleaned
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "cte_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_ctas_select_star_uses_expanded_output_columns(self):
        sql = """
        CREATE TABLE shop_dm.tmp_order AS
        SELECT *
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "ctas_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "tmp_order", "order_id"),
            ("ods_order", "customer_id", "tmp_order", "customer_id"),
            ("ods_order", "amount", "tmp_order", "amount"),
        }

    def test_alias_star_in_join_does_not_expand_other_relation_columns(self):
        sql = """
        INSERT INTO shop_dm.dwd_order_customer
        SELECT o.*, c.customer_name
        FROM shop_dm.ods_order o
        JOIN shop_dm.ods_customer c ON o.customer_id = c.customer_id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql, "join_alias_star.sql", self.schema, diagnostics=diagnostics
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order_customer", "order_id"),
            (
                "ods_order",
                "customer_id",
                "dwd_order_customer",
                "customer_id",
            ),
            ("ods_order", "amount", "dwd_order_customer", "amount"),
            (
                "ods_customer",
                "customer_name",
                "dwd_order_customer",
                "customer_name",
            ),
        }

    def test_bare_star_does_not_partially_expand_when_source_schema_missing(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order_customer
        SELECT *
        FROM shop_dm.missing_orders m
        JOIN shop_dm.ods_customer c ON m.customer_id = c.customer_id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "missing_schema_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_bare_star_join_duplicate_column_names_map_by_position(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_order_key (
                    id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.ods_customer_key (
                    id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order_customer_flat (
                    order_id BIGINT,
                    amount DECIMAL(12,2),
                    customer_id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dwd_order_customer_flat
        SELECT *
        FROM shop_dm.ods_order_key o
        JOIN shop_dm.ods_customer_key c ON o.id = c.id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "duplicate_star_join.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "ods_order_key",
                "id",
                "dwd_order_customer_flat",
                "order_id",
            ),
            (
                "ods_order_key",
                "amount",
                "dwd_order_customer_flat",
                "amount",
            ),
            (
                "ods_customer_key",
                "id",
                "dwd_order_customer_flat",
                "customer_id",
            ),
            (
                "ods_customer_key",
                "customer_name",
                "dwd_order_customer_flat",
                "customer_name",
            ),
        }

    def test_alias_star_ignores_unprojected_relation_with_missing_schema(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        SELECT o.*
        FROM shop_dm.ods_order o
        JOIN shop_dm.missing_customer c ON o.customer_id = c.customer_id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "alias_star_missing_join.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_unresolved_inner_star_does_not_leak_as_derived_column(self):
        sql = """
        INSERT INTO shop_dm.dwd_order_customer
        SELECT *
        FROM (
            SELECT *
            FROM shop_dm.missing_orders m
            JOIN shop_dm.ods_customer c ON m.customer_id = c.customer_id
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unresolved_inner_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand",
        ]

    def test_unresolved_star_suppresses_later_position_dependent_expression(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT *, NOW() AS etl_time
        FROM shop_dm.missing_orders
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unresolved_star_then_expr.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_cte_column_alias_list_exposes_star_output_names(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (customer_id, amount)
        WITH renamed(customer_id, amount) AS (
            SELECT order_id, amount
            FROM shop_dm.ods_order
        )
        SELECT *
        FROM renamed
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "cte_alias_columns.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_subquery_column_alias_list_exposes_star_output_names(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (customer_id, amount)
        SELECT *
        FROM (
            SELECT order_id, amount
            FROM shop_dm.ods_order
        ) renamed(customer_id, amount)
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "subquery_alias_columns.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_explicit_projection_from_subquery_star_expands_inner_star(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        SELECT t.order_id
        FROM (
            SELECT *
            FROM shop_dm.ods_order
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "explicit_subquery_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
        }

    def test_explicit_projection_from_unresolved_subquery_star_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        SELECT t.order_id
        FROM (
            SELECT *
            FROM shop_dm.missing_orders
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "explicit_unresolved_subquery_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_unqualified_projection_from_unresolved_subquery_star_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        SELECT order_id
        FROM (
            SELECT *
            FROM shop_dm.missing_orders
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unqualified_unresolved_subquery_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_unqualified_projection_from_unresolved_cte_star_is_blocked(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        WITH t AS (
            SELECT *
            FROM shop_dm.missing_orders
        )
        SELECT order_id
        FROM t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unqualified_unresolved_cte_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_unused_unresolved_cte_star_does_not_block_main_query(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        WITH unused_bad AS (
            SELECT *
            FROM shop_dm.missing_orders
        )
        SELECT order_id
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unused_unresolved_cte_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
        }

    def test_alias_star_with_explicit_unresolved_subquery_projection_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT o.*, missing_id AS etl_time
        FROM shop_dm.ods_order o
        JOIN (
            SELECT *
            FROM shop_dm.missing_orders
        ) t ON o.order_id = t.order_id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "alias_star_unresolved_explicit.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_nested_bare_star_join_duplicate_columns_map_by_position(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_order_key (
                    id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.ods_customer_key (
                    id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order_customer_flat (
                    order_id BIGINT,
                    amount DECIMAL(12,2),
                    customer_id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dwd_order_customer_flat
        SELECT *
        FROM (
            SELECT *
            FROM shop_dm.ods_order_key o
            JOIN shop_dm.ods_customer_key c ON o.id = c.id
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "nested_duplicate_star_join.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "ods_order_key",
                "id",
                "dwd_order_customer_flat",
                "order_id",
            ),
            (
                "ods_order_key",
                "amount",
                "dwd_order_customer_flat",
                "amount",
            ),
            (
                "ods_customer_key",
                "id",
                "dwd_order_customer_flat",
                "customer_id",
            ),
            (
                "ods_customer_key",
                "customer_name",
                "dwd_order_customer_flat",
                "customer_name",
            ),
        }

    def test_fully_qualified_star_matches_exact_relation(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_same_name (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE other_dm.ods_same_name (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_same_name (
                    id BIGINT
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dwd_same_name
        SELECT shop_dm.ods_same_name.*
        FROM shop_dm.ods_same_name
        JOIN other_dm.ods_same_name
          ON shop_dm.ods_same_name.id = other_dm.ods_same_name.id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "qualified_star.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_same_name", "id", "dwd_same_name", "id"),
        }

    def test_fully_qualified_star_matches_non_default_database_relation(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_same_name (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE other_dm.ods_same_name (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_same_name (
                    id BIGINT
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dwd_same_name
        SELECT other_dm.ods_same_name.*
        FROM shop_dm.ods_same_name
        JOIN other_dm.ods_same_name
          ON shop_dm.ods_same_name.id = other_dm.ods_same_name.id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "qualified_star_other_db.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("other_dm.ods_same_name", "id", "dwd_same_name", "id"),
        }

    def test_qualified_physical_table_star_is_not_shadowed_by_cte(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        WITH ods_order AS (
            SELECT order_id
            FROM shop_dm.ods_order
        )
        SELECT shop_dm.ods_order.*
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "qualified_physical_not_cte.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_union_right_unresolved_star_does_not_emit_star_column_edge(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id, amount)
        SELECT *
        FROM shop_dm.ods_order
        UNION ALL
        SELECT *
        FROM shop_dm.missing_orders
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "union_missing_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_union_left_unresolved_star_suppresses_later_projection(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id)
        SELECT *, c.customer_name
        FROM shop_dm.missing_orders m
        JOIN shop_dm.ods_customer c ON m.customer_id = c.customer_id
        UNION ALL
        SELECT order_id, customer_id
        FROM shop_dm.ods_order
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "union_left_missing_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) == set()

    def test_ctas_unresolved_star_records_single_diagnostic(self):
        sql = """
        CREATE TABLE shop_dm.tmp_missing AS
        SELECT *
        FROM shop_dm.missing_orders
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ctas_missing_star.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def test_ctas_known_shape_with_unresolved_source_registers_columns(self):
        sql = """
        CREATE TABLE shop_dm.tmp_order AS
        SELECT o.*, t.missing_id AS etl_time
        FROM shop_dm.ods_order o
        JOIN (
            SELECT *
            FROM shop_dm.missing_orders
        ) t ON o.order_id = t.order_id;

        INSERT INTO shop_dm.dwd_order
        SELECT *
        FROM shop_dm.tmp_order;
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ctas_known_shape_unresolved_source.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "tmp_order", "order_id"),
            ("ods_order", "customer_id", "tmp_order", "customer_id"),
            ("ods_order", "amount", "tmp_order", "amount"),
            ("tmp_order", "order_id", "dwd_order", "order_id"),
            ("tmp_order", "customer_id", "dwd_order", "customer_id"),
            ("tmp_order", "amount", "dwd_order", "amount"),
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

    def test_insert_star_expands_anonymous_derived_projections_to_targets(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dws_daily_sales (
            order_date,
            total_amount,
            order_count
        )
        SELECT aa.*
        FROM (
            SELECT
                info.order_date,
                SUM(info.total_amount),
                COUNT(info.order_id)
            FROM shop_dm.ods_order AS info
            GROUP BY info.order_date
        ) AS aa
        """
        diagnostics = []
        entries = extract_lineage_from_sql(
            sql,
            "dws_daily_sales.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) >= {
            ("ods_order", "order_date", "dws_daily_sales", "order_date"),
            ("info", "total_amount", "dws_daily_sales", "total_amount"),
            ("info", "order_id", "dws_daily_sales", "order_count"),
        }

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

    def test_lineage_extraction_matches_uppercase_sql_columns_to_lowercase_ddl(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE ndh_hive.etl_cdmtest.p03_corp_cust_info (
                    cust_no STRING
                )
                """,
                """
                CREATE TABLE ndh_hive.etl_cdmtest.p01_pub_cd_info (
                    code STRING,
                    name STRING
                )
                """,
                """
                CREATE TABLE ndh_hive.etl_cdmtest.target_t (
                    cust_num STRING,
                    gxgm01 STRING
                )
                """,
            ]
        )
        sql = """
        INSERT INTO NDH_HIVE.ETL_CDMTEST.TARGET_T
        SELECT T.CUST_NUM, T.GXGM01
        FROM (
            SELECT
                A.CUST_NO AS cust_num,
                B.NAME AS gxgm01
            FROM NDH_HIVE.ETL_CDMTEST.P03_CORP_CUST_INFO AS a
            LEFT JOIN ndh_hive.etl_cdmtest.P01_PUB_CD_INFO AS b
              ON A.CUST_NO = B.CODE
        ) AS t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "case_subquery_join.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "ndh_hive.etl_cdmtest.p03_corp_cust_info",
                "cust_no",
                "ndh_hive.etl_cdmtest.target_t",
                "cust_num",
            ),
            (
                "ndh_hive.etl_cdmtest.p01_pub_cd_info",
                "name",
                "ndh_hive.etl_cdmtest.target_t",
                "gxgm01",
            ),
        }
        assert _indirect_edges(entries) == {
            (
                "ndh_hive.etl_cdmtest.p03_corp_cust_info",
                "cust_no",
                "ndh_hive.etl_cdmtest.target_t",
                "JOIN_ON",
            ),
            (
                "ndh_hive.etl_cdmtest.p01_pub_cd_info",
                "code",
                "ndh_hive.etl_cdmtest.target_t",
                "JOIN_ON",
            ),
        }

    def test_lineage_extraction_preserves_sources_for_aliases_differing_only_by_case(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src (
                    a INT,
                    b INT
                )
                """,
                """
                CREATE TABLE shop_dm.dst (
                    c1 INT,
                    c2 INT
                )
                """,
            ]
        )
        sql = """
        INSERT INTO dst (c1, c2)
        SELECT a AS `Foo`, b AS `foo`
        FROM src
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "case_alias_collision.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("src", "a", "dst", "c1"),
            ("src", "b", "dst", "c2"),
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

    def test_lineage_extraction_matches_quoted_derived_column_case_insensitively(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_operator (
                    oper_no BIGINT,
                    `alias` VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.m05_czpt_group_cus_info (
                    operator_name VARCHAR(64)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.m05_czpt_group_cus_info (operator_name)
        SELECT t7.`ALIAS` AS operator_name
        FROM (
            SELECT oper_no, `alias`
            FROM shop_dm.ods_operator
        ) t7
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "m05_czpt_group_cus_info.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "ods_operator",
                "alias",
                "m05_czpt_group_cus_info",
                "operator_name",
            ),
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
