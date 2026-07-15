import dw_refactor_agent.config as config
from dw_refactor_agent.lineage.lineage_extractor import (
    _schema_columns_for_table,
    _schema_has_column,
    build_schema_from_ddl,
    build_schema_from_project_ddl,
    build_schema_from_texts,
)


class TestBuildSchemaFromTexts:
    def test_schema_from_texts_extracts_hive_partition_columns(self):
        ddl = """
        CREATE TABLE `tran_data_menu`(
          `id` decimal(38,0) COMMENT 'identifier',
          `menu_name` string COMMENT 'menu name',
          `channel_type` string COMMENT 'channel')
        COMMENT 'ods hive table'
        PARTITIONED BY (
          `row_date` string COMMENT 'partition date')
        ROW FORMAT SERDE
          'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
        WITH SERDEPROPERTIES (
          'serialization.format' = '1')
        STORED AS INPUTFORMAT
          'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
        OUTPUTFORMAT
          'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
        LOCATION
          'hdfs://easyops-cluster/user/hive/warehouse/etl.db/tran_data_menu'
        TBLPROPERTIES (
          'transient_lastDdlTime'='1776664703');
        """

        schema = build_schema_from_texts(
            [ddl],
            dialect="hive",
            default_catalog="internal",
            default_db="shop_dm",
        )

        assert schema["internal"]["shop_dm"]["tran_data_menu"] == {
            "id": "DECIMAL(38, 0)",
            "menu_name": "STRING",
            "channel_type": "STRING",
            "row_date": "STRING",
        }
        assert (
            _schema_has_column(
                schema, "internal.shop_dm.tran_data_menu", "row_date"
            )
            is True
        )
        assert _schema_columns_for_table(
            schema, "internal.shop_dm.tran_data_menu"
        ) == [
            "id",
            "menu_name",
            "channel_type",
            "row_date",
        ]

    def test_table_identifier_shape_scenarios(self):
        self._assert_quoted_identifiers_are_canonicalized()
        self._assert_schema_lookup_is_case_insensitive()
        self._assert_bare_table_uses_default_catalog_and_database()
        self._assert_three_part_table_preserves_catalog_database_and_table()

    def _assert_quoted_identifiers_are_canonicalized(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS "shop_dm"."M_SHOP_01_CUST_DF" (
            "CUSTOMER_ID" BIGINT,
            `CUSTOMER_NAME` VARCHAR(64)
        ) ENGINE=OLAP
        DUPLICATE KEY("CUSTOMER_ID")
        DISTRIBUTED BY HASH("CUSTOMER_ID") BUCKETS 1
        PROPERTIES ("replication_num" = "1");
        """
        schema = build_schema_from_texts([ddl])

        assert "M_SHOP_01_CUST_DF" in schema["internal"]["shop_dm"]
        assert set(schema["internal"]["shop_dm"]["M_SHOP_01_CUST_DF"]) == {
            "CUSTOMER_ID",
            "CUSTOMER_NAME",
        }

    def _assert_schema_lookup_is_case_insensitive(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.M_SHOP_01_CUST_DF (
                    CUSTOMER_ID BIGINT,
                    Customer_Name VARCHAR(64)
                )
                """
            ]
        )

        assert _schema_columns_for_table(
            schema, "SHOP_DM.m_shop_01_cust_df"
        ) == [
            "CUSTOMER_ID",
            "Customer_Name",
        ]
        assert (
            _schema_has_column(
                schema, "shop_dm.m_shop_01_cust_df", "customer_id"
            )
            is True
        )
        assert (
            _schema_has_column(
                schema, "SHOP_DM.M_SHOP_01_CUST_DF", "customer_name"
            )
            is True
        )

    def _assert_bare_table_uses_default_catalog_and_database(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE dwd_order (
                    id BIGINT,
                    name VARCHAR(10)
                )
                """
            ]
        )

        assert schema == {
            "internal": {
                "shop_dm": {
                    "dwd_order": {
                        "id": "BIGINT",
                        "name": "VARCHAR(10)",
                    }
                }
            }
        }
        assert _schema_columns_for_table(schema, "dwd_order") == ["id", "name"]
        assert _schema_has_column(schema, "dwd_order", "id") is True

    def _assert_three_part_table_preserves_catalog_database_and_table(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE hive.shop_dm.dwd_order (
                    id BIGINT
                )
                """
            ]
        )

        assert schema == {
            "hive": {
                "shop_dm": {
                    "dwd_order": {
                        "id": "BIGINT",
                    }
                }
            }
        }
        assert _schema_columns_for_table(schema, "hive.shop_dm.dwd_order") == [
            "id"
        ]
        assert (
            _schema_has_column(schema, "hive.shop_dm.dwd_order", "id") is True
        )


class TestBuildSchemaFromDdl:
    def test_build_schema_from_project_ddl_uses_ods_catalog_dialect(
        self,
        monkeypatch,
        tmp_path,
    ):
        project_dir = tmp_path / "demo_project"
        mid_ddl = project_dir / "mid" / "ddl"
        hive_ods_ddl = project_dir / "ods" / "ddl" / "hive" / "source_db"
        mid_ddl.mkdir(parents=True)
        hive_ods_ddl.mkdir(parents=True)
        (mid_ddl / "dwd_customer.sql").write_text(
            """
            CREATE TABLE demo_dm.dwd_customer (
                customer_id BIGINT
            )
            ENGINE=OLAP
            DUPLICATE KEY(customer_id)
            DISTRIBUTED BY HASH(customer_id) BUCKETS 1
            PROPERTIES ("replication_num" = "1");
            """,
            encoding="utf-8",
        )
        (hive_ods_ddl / "tran_data_menu.sql").write_text(
            """
            CREATE TABLE `tran_data_menu`(
              `id` decimal(38,0),
              `menu_name` string)
            PARTITIONED BY (
              `row_date` string)
            ROW FORMAT SERDE
              'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
            STORED AS INPUTFORMAT
              'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
            OUTPUTFORMAT
              'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
            LOCATION
              'hdfs://cluster/warehouse/source_db/tran_data_menu';
            """,
            encoding="utf-8",
        )

        monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
        monkeypatch.setitem(
            config.PROJECT_CONFIG,
            "demo",
            {
                "dir": "demo_project",
                "catalog": "internal",
                "db": "demo_dm",
                "ods_source_catalog_dialects": {
                    "hive": "hive",
                },
            },
        )

        schema = build_schema_from_project_ddl("demo")

        assert _schema_columns_for_table(
            schema, "internal.demo_dm.dwd_customer"
        ) == ["customer_id"]
        assert _schema_columns_for_table(
            schema, "hive.source_db.tran_data_menu"
        ) == [
            "id",
            "menu_name",
            "row_date",
        ]
        assert (
            _schema_has_column(
                schema, "hive.source_db.tran_data_menu", "row_date"
            )
            is True
        )

    def test_build_schema_from_ddl_sources(self, ddl_dir, tmp_path):
        schema = build_schema_from_ddl(str(ddl_dir))
        assert "internal" in schema
        assert "shop_dm" in schema["internal"]
        assert len(schema["internal"]["shop_dm"]) == 4
        assert "ods_customer" in schema["internal"]["shop_dm"]
        assert "ads_sales_dashboard" in schema["internal"]["shop_dm"]

        d = tmp_path / "empty_ddl"
        d.mkdir()
        assert build_schema_from_ddl(str(d)) == {}

        root_ddl = tmp_path / "root_ddl"
        ods_ddl = tmp_path / "ods" / "ddl" / "internal" / "shop_dm"
        root_ddl.mkdir(parents=True)
        ods_ddl.mkdir(parents=True)
        (root_ddl / "dwd_customer.sql").write_text(
            "CREATE TABLE shop_dm.dwd_customer (customer_id BIGINT);",
            encoding="utf-8",
        )
        (ods_ddl / "ods_customer.sql").write_text(
            "CREATE TABLE shop_dm.ods_customer (customer_id BIGINT);",
            encoding="utf-8",
        )

        schema = build_schema_from_ddl([root_ddl, ods_ddl])

        assert set(schema["internal"]["shop_dm"]) == {
            "dwd_customer",
            "ods_customer",
        }
