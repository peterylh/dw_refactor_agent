import pytest
import sqlglot
from sqlglot import exp

import config
import lineage.lineage_extractor as lineage_extractor
from lineage.lineage_extractor import (
    _table_name,
    configure_project,
    determine_layer,
)


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
        monkeypatch.setitem(
            config.PROJECT_CONFIG,
            project_name,
            {
                "dir": project_name,
                "db": f"{project_name}_dm",
            },
        )

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    config._model_metadata_cache.clear()
    configure_project(default_project)
    yield
    lineage_extractor.CURRENT_PROJECT = original_project
    lineage_extractor.CURRENT_DB = original_db
    config._model_metadata_cache.clear()


class TestDetermineLayer:
    def test_determine_layer_scenarios(self):
        scenarios = [
            ("ods_customer", "ODS"),
            ("shop_dm.ods_order", "ODS"),
            ("dwd_customer", "DWD"),
            ("shop_dm.dwd_product", "DWD"),
            ("dws_store_sales_daily", "DWS"),
            ("shop_dm.dws_product_sales_daily", "DWS"),
            ("ads_customer_rfm", "ADS"),
            ("shop_dm.ads_sales_dashboard", "ADS"),
            ("unknown_table", "OTHER"),
            ("ods_", "OTHER"),
        ]
        for table_name, expected in scenarios:
            assert determine_layer(table_name) == expected

        configure_project("unit_lineage_dim")
        assert determine_layer("dim_date") == "DIM"
        assert determine_layer("finance_analytics_dm.dim_customer") == "DIM"
        assert determine_layer("") == "OTHER"


class TestTableName:
    def _from_table(self, stmt):
        return (stmt.args.get("from_") or stmt.args.get("from")).this

    def test_table_name_from_parsed_sql(self):
        scenarios = [
            ("SELECT * FROM shop_dm.ods_customer", "shop_dm.ods_customer"),
            ("SELECT * FROM ods_customer", "ods_customer"),
            ("SELECT * FROM shop_dm.`order`", "shop_dm.order"),
        ]
        for sql, expected in scenarios:
            stmt = sqlglot.parse_one(sql, dialect="doris")
            t = self._from_table(stmt)
            assert isinstance(t, exp.Table)
            assert _table_name(t) == expected
