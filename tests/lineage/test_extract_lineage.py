import sqlglot

from dw_refactor_agent.lineage.lineage_extractor import (
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


def _assert_metric_literal_lineage(entries, schema):
    output = build_lineage_output(entries, schema)

    assert _direct_edges(entries) == {
        ("src_metric", "metric_value", "ads_metric", "metric_value"),
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
        "optional_note": "literal",
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
            _assert_metric_literal_lineage(entries, schema)

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

    def test_union_derived_literals_do_not_create_alias_source_table(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_org (
                    org_num VARCHAR(32)
                )
                """,
                """
                CREATE TABLE shop_dm.dst_org (
                    org_num VARCHAR(32),
                    org_num_lv INT,
                    leaf_flg VARCHAR(1)
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dst_org (org_num, org_num_lv, leaf_flg)
        SELECT t.org_num, t.org_num_lv, t.leaf_flg
        FROM (
            SELECT org_num, 1 AS org_num_lv, '0' AS leaf_flg
            FROM shop_dm.src_org
            UNION ALL
            SELECT org_num, 2 AS org_num_lv, '1' AS leaf_flg
            FROM shop_dm.src_org
        ) AS t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "union_derived_literals.sql",
            schema,
            diagnostics=diagnostics,
        )
        output = build_lineage_output(entries, schema)

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("src_org", "org_num", "dst_org", "org_num"),
            (None, None, "dst_org", "org_num_lv"),
            (None, None, "dst_org", "leaf_flg"),
        }
        assert {
            entry["target_column"]: entry["source_type"]
            for entry in entries
            if entry.get("transformation_type") == "constant"
        } == {
            "org_num_lv": "expression",
            "leaf_flg": "expression",
        }
        assert {table["name"] for table in output["tables"]} == {
            "src_org",
            "dst_org",
        }

    def test_qualified_table_is_not_shadowed_by_same_named_cte(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE shop_dm.dst (
                    id BIGINT
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dst (id)
        WITH src AS (SELECT 1 AS id)
        SELECT p.id
        FROM shop_dm.src AS p
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "qualified_table_same_named_cte.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("src", "id", "dst", "id"),
        }

    def test_derived_alias_does_not_shadow_physical_table_lineage(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src (
                    id BIGINT
                )
                """,
                """
                CREATE TABLE shop_dm.dst (
                    physical_id BIGINT,
                    literal_id BIGINT
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.dst (physical_id, literal_id)
        SELECT p.id, src.id
        FROM shop_dm.src AS p
        JOIN (SELECT 1 AS id) AS src ON 1 = 1
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "derived_alias_physical_table_collision.sql",
            schema,
            diagnostics=diagnostics,
        )
        output = build_lineage_output(entries, schema)

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("src", "id", "dst", "physical_id"),
            (None, None, "dst", "literal_id"),
        }
        assert {table["name"] for table in output["tables"]} == {
            "src",
            "dst",
        }

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
            _assert_metric_literal_lineage(entries, schema)

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

    def test_insert_alias_star_names_anonymous_literal_by_target_position(
        self,
    ):
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

    def test_ctas_parenthesized_union_has_output_columns(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE i02_confer_flow_effic_index (
                    data_dt DATE,
                    org_num STRING,
                    confer_num STRING,
                    assure_amt DECIMAL(18, 2)
                )
                """,
            ]
        )
        sql = """
        CREATE TABLE IF NOT EXISTS temp_confer_org_flow AS
        (
          SELECT
            data_dt,
            org_num,
            '00' AS flow_status,
            0 AS index_1,
            00 AS index_2
          FROM i02_confer_flow_effic_index
          GROUP BY data_dt, org_num
        )
        UNION ALL
        (
          SELECT
            data_dt,
            org_num,
            '01' AS flow_status,
            COUNT(DISTINCT confer_num) AS index_1,
            SUM(assure_amt) AS index_2
          FROM i02_confer_flow_effic_index
          GROUP BY data_dt, org_num
        )
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ctas_parenthesized_union.sql",
            schema,
            diagnostics=diagnostics,
        )
        output = build_lineage_output(entries, schema)

        assert diagnostics == []
        assert (
            "i02_confer_flow_effic_index",
            "data_dt",
            "temp_confer_org_flow",
            "data_dt",
        ) in _direct_edges(entries)
        assert (
            "i02_confer_flow_effic_index",
            "org_num",
            "temp_confer_org_flow",
            "org_num",
        ) in _direct_edges(entries)
        transient_table = next(
            table
            for table in output["tables"]
            if table["name"] == "temp_confer_org_flow"
        )
        assert {column["name"] for column in transient_table["columns"]} == {
            "data_dt",
            "org_num",
            "flow_status",
            "index_1",
            "index_2",
        }
