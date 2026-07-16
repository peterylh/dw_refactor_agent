from tests.lineage.test_extract_lineage import (
    ALL_DDLS,
    _direct_edges,
    _indirect_edges,
    build_schema_from_texts,
    extract_lineage_from_sql,
)


class TestEdgeCases:
    """Edge cases that should not crash"""

    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(ALL_DDLS)

    def test_lateral_view_named_struct_fields_are_lineage_sources(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE a_ibank_cust_ind_d (
                    data_dt DATE,
                    cust_no STRING,
                    valid_cust_mark STRING,
                    basic_cust_org_mark STRING
                );
                CREATE TABLE cdm.a10_corp_cust_bool_label_t2 (
                    data_dt DATE,
                    cust_num STRING,
                    label_name STRING,
                    label_index INT
                );
                """,
            ]
        )
        sql = """
        INSERT INTO cdm.a10_corp_cust_bool_label_t2 (
            data_dt,
            cust_num,
            label_name,
            label_index
        )
        SELECT DISTINCT
            data_dt,
            customer_no,
            title,
            CAST(flag AS INT) AS flag
        FROM (
            SELECT
                CAST('20260601' AS DATE) AS data_dt,
                t.cust_no AS customer_no,
                f.flag AS flag,
                f.title AS title
            FROM (
                SELECT *
                FROM a_ibank_cust_ind_d
                WHERE data_dt = CAST('20260601' AS DATE)
            ) AS t
            LATERAL VIEW EXPLODE(ARRAY(
                NAMED_STRUCT('flag', valid_cust_mark, 'title', 'tyyxkh01'),
                NAMED_STRUCT('flag', basic_cust_org_mark, 'title', 'jgtyxzjckh01')
            )) f AS f
        ) AS g
        WHERE g.flag = '1'
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "a10_corp_cust_bool_label_t2.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) >= {
            (
                "a_ibank_cust_ind_d",
                "valid_cust_mark",
                "cdm.a10_corp_cust_bool_label_t2",
                "label_index",
            ),
            (
                "a_ibank_cust_ind_d",
                "basic_cust_org_mark",
                "cdm.a10_corp_cust_bool_label_t2",
                "label_index",
            ),
        }
        assert _indirect_edges(entries) >= {
            (
                "a_ibank_cust_ind_d",
                "valid_cust_mark",
                "cdm.a10_corp_cust_bool_label_t2",
                "WHERE",
            ),
            (
                "a_ibank_cust_ind_d",
                "basic_cust_org_mark",
                "cdm.a10_corp_cust_bool_label_t2",
                "WHERE",
            ),
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

    def test_create_table_like_registers_schema_for_later_star(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.a11_unite_busi_oppor_info (
                    busi_oppor_id BIGINT,
                    cust_id STRING,
                    update_time DATETIME
                )
                """,
            ]
        )
        sql = """
        DROP TABLE IF EXISTS tmp_a11_unite_busi_oppor_info_12_20260601 FORCE;

        CREATE TABLE IF NOT EXISTS tmp_a11_unite_busi_oppor_info_12_20260601
        LIKE cdm.a11_unite_busi_oppor_info;

        CREATE TABLE tmp_like_out AS
        SELECT *
        FROM tmp_a11_unite_busi_oppor_info_12_20260601;
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "tmp_like_star.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert not [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.get("stage") == "lineage_star_expand"
        ]
        assert _direct_edges(entries) == {
            (
                "tmp_a11_unite_busi_oppor_info_12_20260601",
                "busi_oppor_id",
                "tmp_like_out",
                "busi_oppor_id",
            ),
            (
                "tmp_a11_unite_busi_oppor_info_12_20260601",
                "cust_id",
                "tmp_like_out",
                "cust_id",
            ),
            (
                "tmp_a11_unite_busi_oppor_info_12_20260601",
                "update_time",
                "tmp_like_out",
                "update_time",
            ),
        }

    def test_unqualified_filter_column_ignores_derived_table_without_column(
        self,
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE bs_epbp_trans_total (
                    batch_jnls_no STRING,
                    row_date DATE,
                    send_date DATE,
                    pay_acc_no STRING
                )
                """,
                """
                CREATE TABLE tmp_a10_channel_cust_day_dtl_df (
                    batch_jnls_no STRING
                )
                """,
                """
                CREATE TABLE target_t (
                    batch_jnls_no STRING,
                    row_date DATE,
                    pay_acc_no STRING
                )
                """,
            ]
        )
        sql = """
        INSERT INTO target_t (batch_jnls_no, row_date, pay_acc_no)
        SELECT
            t.batch_jnls_no,
            row_date,
            pay_acc_no
        FROM bs_epbp_trans_total AS t
        LEFT JOIN (
            SELECT DISTINCT
                batch_jnls_no
            FROM tmp_a10_channel_cust_day_dtl_df
        ) AS t2
            ON t.batch_jnls_no = t2.batch_jnls_no
        WHERE
            row_date = CAST('20260602' AS DATE)
            AND send_date = '20260602'
            AND t2.batch_jnls_no IS NULL
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "unqualified_filter_derived_join.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert not [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.get("stage") == "derived_lineage_column"
        ]
        assert _indirect_edges(entries) >= {
            ("bs_epbp_trans_total", "row_date", "target_t", "WHERE"),
            ("bs_epbp_trans_total", "send_date", "target_t", "WHERE"),
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
