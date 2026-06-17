from lineage.lineage_extractor import (
    _schema_columns_for_table,
    _schema_has_column,
    build_schema_from_ddl,
    build_schema_from_texts,
    schema_table_count,
)


class TestBuildSchemaFromTexts:
    def test_basic(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        assert "internal" in schema
        assert "shop_dm" in schema["internal"]
        assert "ods_customer" in schema["internal"]["shop_dm"]
        assert "ods_order" in schema["internal"]["shop_dm"]
        assert "dwd_customer" in schema["internal"]["shop_dm"]

    def test_column_count(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        assert len(schema["internal"]["shop_dm"]["ods_customer"]) == 12
        assert len(schema["internal"]["shop_dm"]["ods_order"]) == 11
        assert len(schema["internal"]["shop_dm"]["dwd_customer"]) == 13

    def test_column_types(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        cust = schema["internal"]["shop_dm"]["ods_customer"]
        assert cust["customer_id"] == "BIGINT"
        assert cust["customer_name"] == "VARCHAR(64)"
        assert cust["age"] == "INT"
        assert cust["register_date"] == "DATE"
        assert cust["create_time"] == "DATETIME"
        assert cust["member_level"] == "VARCHAR(16)"

    def test_quoted_identifiers_are_canonicalized(self):
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

    def test_schema_lookup_is_case_insensitive(self):
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

    def test_bare_table_uses_default_catalog_and_database(self):
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

    def test_three_part_table_preserves_catalog_database_and_table(self):
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

    def test_empty_list(self):
        assert build_schema_from_texts([]) == {}

    def test_no_ddl_statements(self):
        sql = "SELECT 1; INSERT INTO t VALUES (1);"
        assert build_schema_from_texts([sql]) == {}

    def test_comment_only(self):
        assert build_schema_from_texts(["-- just a comment"]) == {}

    def test_schema_table_count_counts_nested_catalog_database_tables(self):
        schema = {
            "internal": {
                "shop_dm": {
                    "ods_customer": {},
                    "dwd_customer": {},
                },
                "other_db": {
                    "ods_order": {},
                },
            },
            "hive": {
                "source_db": {
                    "source_order": {},
                },
            },
        }

        assert schema_table_count(schema) == 4


class TestBuildSchemaFromDdl:
    def test_from_directory(self, ddl_dir):
        schema = build_schema_from_ddl(str(ddl_dir))
        assert "internal" in schema
        assert "shop_dm" in schema["internal"]
        assert len(schema["internal"]["shop_dm"]) == 4
        assert "ods_customer" in schema["internal"]["shop_dm"]
        assert "ads_sales_dashboard" in schema["internal"]["shop_dm"]

    def test_empty_directory(self, tmp_path):
        d = tmp_path / "empty_ddl"
        d.mkdir()
        assert build_schema_from_ddl(str(d)) == {}

    def test_from_multiple_directories(self, tmp_path):
        root_ddl = tmp_path / "ddl"
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
