import sqlglot
from sqlglot import exp
from lineage.lineage_extractor import determine_layer, _table_name


class TestDetermineLayer:
    def test_ods(self):
        assert determine_layer("ods_customer") == "ODS"
        assert determine_layer("shop_dm.ods_order") == "ODS"

    def test_dwd(self):
        assert determine_layer("dwd_customer") == "DWD"
        assert determine_layer("shop_dm.dwd_product") == "DWD"

    def test_dws(self):
        assert determine_layer("dws_store_sales_daily") == "DWS"
        assert determine_layer("shop_dm.dws_product_sales_daily") == "DWS"

    def test_ads(self):
        assert determine_layer("ads_customer_rfm") == "ADS"
        assert determine_layer("shop_dm.ads_sales_dashboard") == "ADS"

    def test_dim(self):
        assert determine_layer("dim_date") == "DIM"
        assert determine_layer("shop_dm.dim_store") == "DIM"

    def test_other(self):
        assert determine_layer("unknown_table") == "OTHER"
        assert determine_layer("temp_data") == "OTHER"
        assert determine_layer("") == "OTHER"

    def test_exact_boundary(self):
        assert determine_layer("ods_") == "ODS"
        assert determine_layer("dwd_") == "DWD"


class TestTableName:
    def test_table_with_db(self):
        t = exp.Table(
            this=exp.Identifier(this="ods_order"), db=exp.Identifier(this="shop_dm")
        )
        assert _table_name(t) == "shop_dm.ods_order"

    def test_table_without_db(self):
        t = exp.Table(this=exp.Identifier(this="ods_order"))
        assert _table_name(t) == "ods_order"

    def test_quoted_identifier(self):
        t = exp.Table(
            this=exp.Identifier(this="order", quoted=True),
            db=exp.Identifier(this="shop_dm"),
        )
        assert _table_name(t) == "shop_dm.order"

    def test_from_parse(self):
        stmt = sqlglot.parse_one("SELECT * FROM shop_dm.ods_customer", dialect="doris")
        t = stmt.args["from_"].this
        assert isinstance(t, exp.Table)
        assert _table_name(t) == "shop_dm.ods_customer"

    def test_from_parse_no_db(self):
        stmt = sqlglot.parse_one("SELECT * FROM ods_customer", dialect="doris")
        t = stmt.args["from_"].this
        assert isinstance(t, exp.Table)
        assert _table_name(t) == "ods_customer"
