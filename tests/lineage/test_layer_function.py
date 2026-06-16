import pytest
import sqlglot
from sqlglot import exp

import config
import lineage.lineage_extractor as lineage_extractor
from lineage.lineage_extractor import configure_project, determine_layer, _table_name


@pytest.fixture(autouse=True)
def isolated_lineage_projects(tmp_path, monkeypatch):
    original_project = lineage_extractor.CURRENT_PROJECT
    original_db = lineage_extractor.CURRENT_DB
    default_project = "unit_lineage"
    dim_project = "unit_lineage_dim"
    layer_map = {
        default_project: {
            "ods_customer": "ODS",
            "ods_order": "ODS",
            "dwd_customer": "DWD",
            "dwd_product": "DWD",
            "dws_store_sales_daily": "DWS",
            "dws_product_sales_daily": "DWS",
            "ads_customer_rfm": "ADS",
            "ads_sales_dashboard": "ADS",
        },
        dim_project: {
            "dim_date": "DIM",
            "dim_customer": "DIM",
        },
    }
    for project_name, tables in layer_map.items():
        models_dir = tmp_path / project_name / "models"
        models_dir.mkdir(parents=True)
        for table_name, layer in tables.items():
            (models_dir / f"{table_name}.yaml").write_text(
                f"version: 2\nname: {table_name}\nlayer: {layer}\n",
                encoding="utf-8",
            )
        monkeypatch.setitem(config.PROJECT_CONFIG, project_name, {
            "dir": project_name,
            "db": f"{project_name}_dm",
        })

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    config._model_metadata_cache.clear()
    configure_project(default_project)
    yield
    lineage_extractor.CURRENT_PROJECT = original_project
    lineage_extractor.CURRENT_DB = original_db
    config._model_metadata_cache.clear()


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
        configure_project("unit_lineage_dim")
        assert determine_layer("dim_date") == "DIM"
        assert determine_layer("finance_analytics_dm.dim_customer") == "DIM"

    def test_other(self):
        assert determine_layer("unknown_table") == "OTHER"
        assert determine_layer("temp_data") == "OTHER"
        assert determine_layer("") == "OTHER"

    def test_exact_boundary(self):
        assert determine_layer("ods_") == "OTHER"
        assert determine_layer("dwd_") == "OTHER"


class TestTableName:
    def _from_table(self, stmt):
        return (stmt.args.get("from_") or stmt.args.get("from")).this

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
        t = self._from_table(stmt)
        assert isinstance(t, exp.Table)
        assert _table_name(t) == "shop_dm.ods_customer"

    def test_from_parse_no_db(self):
        stmt = sqlglot.parse_one("SELECT * FROM ods_customer", dialect="doris")
        t = self._from_table(stmt)
        assert isinstance(t, exp.Table)
        assert _table_name(t) == "ods_customer"
