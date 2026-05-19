from lineage.lineage_extractor import build_schema_from_texts, build_schema_from_ddl


class TestBuildSchemaFromTexts:
    def test_basic(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        assert "shop_dm" in schema
        assert "ods_customer" in schema["shop_dm"]
        assert "ods_order" in schema["shop_dm"]
        assert "dwd_customer" in schema["shop_dm"]

    def test_column_count(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        assert len(schema["shop_dm"]["ods_customer"]) == 12
        assert len(schema["shop_dm"]["ods_order"]) == 11
        assert len(schema["shop_dm"]["dwd_customer"]) == 13

    def test_column_types(self, ddl_texts):
        schema = build_schema_from_texts(ddl_texts)
        cust = schema["shop_dm"]["ods_customer"]
        assert cust["customer_id"] == "BIGINT"
        assert cust["customer_name"] == "VARCHAR(64)"
        assert cust["age"] == "INT"
        assert cust["register_date"] == "DATE"
        assert cust["create_time"] == "DATETIME"
        assert cust["member_level"] == "VARCHAR(16)"

    def test_empty_list(self):
        assert build_schema_from_texts([]) == {}

    def test_no_ddl_statements(self):
        sql = "SELECT 1; INSERT INTO t VALUES (1);"
        assert build_schema_from_texts([sql]) == {}

    def test_comment_only(self):
        assert build_schema_from_texts(["-- just a comment"]) == {}


class TestBuildSchemaFromDdl:
    def test_from_directory(self, ddl_dir):
        schema = build_schema_from_ddl(str(ddl_dir))
        assert "shop_dm" in schema
        assert len(schema["shop_dm"]) == 4
        assert "ods_customer" in schema["shop_dm"]
        assert "ads_sales_dashboard" in schema["shop_dm"]

    def test_empty_directory(self, tmp_path):
        d = tmp_path / "empty_ddl"
        d.mkdir()
        assert build_schema_from_ddl(str(d)) == {}
