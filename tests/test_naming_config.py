"""config NamingConfig 的单元测试"""

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.config import (
    LayerDef,
    NamingConfig,
    TypeDef,
    get_business_domain_config,
    layer_rank,
    load_naming_config,
)
from dw_refactor_agent.config.naming import (
    _parse_rule_expression,
    _parse_segments,
    _parse_template,
)


def _write_dictionary_naming_config(tmp_path, filename, *, domains, areas):
    raw = yaml.safe_load(
        config.naming_config_path().read_text(encoding="utf-8")
    )
    raw["dictionaries"] = {
        "data_domains": {
            "values": [
                {"id": domain_id, "code": code, "name": code}
                for domain_id, code in domains
            ]
        },
        "business_areas": {
            "values": [
                {"id": f"{index:02d}", "code": code, "name": code}
                for index, code in enumerate(areas, start=1)
            ]
        },
    }
    raw["types"]["BUSINESS_AREA_CODE"]["allow"] = {
        "dictionary": "business_areas",
        "value_field": "code",
    }
    raw["types"]["BUSINESS_AREA_CODE"].pop("patterns", None)
    raw["types"]["DATA_DOMAIN_ID"]["allow"] = {
        "dictionary": "data_domains",
        "value_field": "id",
    }
    raw["types"]["DATA_DOMAIN_ID"].pop("patterns", None)

    cfg_path = tmp_path / filename
    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return cfg_path


@pytest.fixture
def isolated_project_naming_configs(tmp_path, monkeypatch):
    shop_cfg = _write_dictionary_naming_config(
        tmp_path,
        "unit_shop_naming.yaml",
        domains=[
            ("01", "CUST"),
            ("02", "PROD"),
            ("03", "STOR"),
            ("04", "ORDR"),
            ("05", "INVT"),
            ("06", "PROM"),
            ("99", "OTHR"),
        ],
        areas=["SHOP"],
    )
    finance_cfg = _write_dictionary_naming_config(
        tmp_path,
        "unit_finance_naming.yaml",
        domains=[
            ("01", "CUST"),
            ("04", "TRAN"),
            ("10", "MKTG"),
            ("99", "OTHR"),
        ],
        areas=["LOAN", "PAYM", "CLNT", "OTHR"],
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "unit_shop",
        {
            "dir": "unit_shop",
            "naming_config": shop_cfg.name,
        },
    )
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "unit_finance",
        {
            "dir": "unit_finance",
            "naming_config": finance_cfg.name,
        },
    )
    config.clear_naming_config_cache()
    yield {
        "shop": "unit_shop",
        "finance": "unit_finance",
    }
    config.clear_naming_config_cache()


# ============================================================
# TypeDef.validate
# ============================================================


class TestTypeDef:
    def test_validate_scenarios(self):
        scenarios = [
            (
                TypeDef(label="load_type", allow=["full", "inc"]),
                ["full", "inc"],
                ["daily", ""],
            ),
            (
                TypeDef(label="source", patterns=["^[a-z0-9]+$"]),
                ["mysql", "erp01"],
                ["MySql", ""],
            ),
            (
                TypeDef(
                    label="period", patterns=["^[0-9]+D$"], allow=["D", "MTD"]
                ),
                ["D", "MTD", "7D"],
                ["0M"],
            ),
        ]
        for typedef, valid_values, invalid_values in scenarios:
            for value in valid_values:
                assert typedef.validate(value) is True
            for value in invalid_values:
                assert typedef.validate(value) is False

        self._assert_without_validator_accepts_freeform_values()

    def _assert_without_validator_accepts_freeform_values(self):
        assert TypeDef(label="freeform").validate("anything") is True


# ============================================================
# _parse_segments
# ============================================================


class TestParseSegments:
    def test_parse_segment_scenarios(self):
        self._assert_basic_list()
        self._assert_optional_right_gets_sep_before()
        self._assert_optional_left_gets_sep_after()
        self._assert_double_optional()
        self._assert_empty_list()
        self._assert_single_literal()
        self._assert_single_type()
        self._assert_plus_prefixed_type_syntax_is_rejected()
        self._assert_optional_marker_without_dollar()
        self._assert_all_required_separator()

    def _assert_basic_list(self):
        """[ods, $source, $entity] → 3 段 + 2 个 _"""
        result = _parse_segments(["ods", "$source", "$entity"], {})
        assert len(result) == 5
        assert result[0] == {
            "name": "ods",
            "kind": "literal",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }
        assert result[1] == {
            "name": "_",
            "kind": "literal",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }
        assert result[2] == {
            "name": "source",
            "kind": "type",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }
        assert result[3] == {
            "name": "_",
            "kind": "literal",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }
        assert result[4] == {
            "name": "entity",
            "kind": "type",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }

    def _assert_optional_right_gets_sep_before(self):
        """[$entity, "$time_granularity?"] → 右侧可选段获得 sep_before，不插入独立 _"""
        result = _parse_segments(["$entity", "$time_granularity?"], {})
        assert len(result) == 2
        assert result[0] == {
            "name": "entity",
            "kind": "type",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }
        assert result[1] == {
            "name": "time_granularity",
            "kind": "type",
            "optional": True,
            "sep_before": "_",
            "sep_after": "",
            "concat_left": False,
        }

    def _assert_optional_left_gets_sep_after(self):
        """["$prefix_field?", $entity] → 左侧可选段获得 sep_after"""
        result = _parse_segments(["$prefix_field?", "$entity"], {})
        assert len(result) == 2
        assert result[0] == {
            "name": "prefix_field",
            "kind": "type",
            "optional": True,
            "sep_before": "",
            "sep_after": "_",
            "concat_left": False,
        }
        assert result[1] == {
            "name": "entity",
            "kind": "type",
            "optional": False,
            "sep_before": "",
            "sep_after": "",
            "concat_left": False,
        }

    def _assert_double_optional(self):
        """["$prefix_field?", "$entity", "$suffix_field?"] → 混合可选绑定"""
        result = _parse_segments(
            ["$prefix_field?", "$entity", "$suffix_field?"], {}
        )
        assert len(result) == 3
        assert (
            result[0]["name"] == "prefix_field"
            and result[0]["optional"] is True
        )
        assert result[0]["sep_after"] == "_"
        assert result[1]["name"] == "entity" and result[1]["optional"] is False
        assert result[1]["sep_before"] == ""
        assert result[1]["sep_after"] == ""
        assert (
            result[2]["name"] == "suffix_field"
            and result[2]["optional"] is True
        )
        assert result[2]["sep_before"] == "_"

    def _assert_empty_list(self):
        assert _parse_segments([], {}) == []

    def _assert_single_literal(self):
        result = _parse_segments(["dim"], {})
        assert len(result) == 1
        assert result[0]["kind"] == "literal"
        assert result[0]["name"] == "dim"

    def _assert_single_type(self):
        result = _parse_segments(["$entity"], {})
        assert len(result) == 1
        assert result[0]["kind"] == "type"
        assert result[0]["name"] == "entity"

    def _assert_plus_prefixed_type_syntax_is_rejected(self):
        with pytest.raises(
            ValueError, match=r"\$\+TYPE syntax is not supported"
        ):
            _parse_segments(["$+entity"], {})

    def _assert_optional_marker_without_dollar(self):
        """无 $ 前缀的 ? 被识别为字面量"""
        result = _parse_segments(["time_granularity?"], {})
        # '?' 在名称中是字面量的一部分
        assert (
            result[0]["name"] == "time_granularity"
            and result[0]["optional"] is True
        )
        assert result[0]["kind"] == "literal"

    def _assert_all_required_separator(self):
        """[a, b, c] 全 required → 段间插入 _"""
        result = _parse_segments(["a", "b", "c"], {})
        assert len(result) == 5
        assert [s["name"] for s in result] == ["a", "_", "b", "_", "c"]


# ============================================================
# _parse_template
# ============================================================


class TestParseTemplate:
    def test_parse_template_scenarios(self):
        self._assert_list_format_passthrough()
        self._assert_string_format_conversion()
        self._assert_string_format_with_optional()
        self._assert_empty_string()

    def test_unclosed_placeholder_raises_value_error(self):
        with pytest.raises(ValueError, match="Unclosed type placeholder"):
            _parse_template("ods_{source", {})

    def _assert_list_format_passthrough(self):
        """列表格式直接委托给 _parse_segments"""
        result = _parse_template(["$entity"], {})
        assert result[0]["kind"] == "type"
        assert result[0]["name"] == "entity"

    def _assert_string_format_conversion(self):
        """ "ods_{source}_{entity}_{load_type}" → 添加 $ 前缀"""
        result = _parse_template("ods_{source}_{entity}_{load_type}", {})
        type_names = [s["name"] for s in result if s["kind"] == "type"]
        assert "source" in type_names
        assert "entity" in type_names
        assert "load_type" in type_names
        assert result[0]["kind"] == "literal" and result[0]["name"] == "ods_"

    def _assert_string_format_with_optional(self):
        """ "_{type?}" 转换"""
        result = _parse_template("_{type?}", {})
        types = [s for s in result if s["kind"] == "type"]
        assert types[0]["name"] == "type"
        assert types[0]["optional"] is True

    def _assert_empty_string(self):
        result = _parse_template("", {})
        assert result == []


# ============================================================
# NamingConfig 辅助构建
# ============================================================


def _make_types():
    return {
        "source": TypeDef(label="source", patterns=["^[a-z0-9]+$"]),
        "entity": TypeDef(label="entity", patterns=["^[a-z][a-z0-9_]*$"]),
        "load_type": TypeDef(label="load_type", allow=["full", "inc"]),
        "time_granularity": TypeDef(
            label="time_granularity",
            allow=["daily", "monthly", "weekly", "yearly"],
        ),
        "business_view": TypeDef(
            label="business_view",
            patterns=["^[a-z][a-z0-9_]*$"],
        ),
        "prefix_field": TypeDef(
            label="prefix_field",
            allow=["min", "max", "avg", "sum", "first", "last", "is", "has"],
        ),
        "suffix_field": TypeDef(
            label="suffix_field",
            allow=[
                "id",
                "name",
                "code",
                "date",
                "time",
                "amount",
                "price",
                "cost",
                "count",
                "quantity",
                "status",
                "type",
                "level",
                "score",
                "segment",
                "method",
                "num",
                "rate",
                "ratio",
                "flag",
                "desc",
                "note",
            ],
        ),
    }


def _build_nc(table_cfg=None, col_segments=None, common_cols=None):
    types = _make_types()
    layers = {}
    for name, segs in (table_cfg or {}).items():
        parsed = _parse_template(segs, types)
        layers[name] = LayerDef(templates=[parsed])
    return NamingConfig(
        types=types,
        layers=layers,
        column_segments=_parse_template(col_segments or [], types),
        common_columns=set(common_cols or []),
    )


# ============================================================
# _match_segments — ODS 模式
# ============================================================


class TestMatchOds:
    @pytest.fixture
    def nc(self):
        return _build_nc({"ODS": ["ods", "$source", "$entity", "$load_type"]})

    def test_match_ods_scenarios(self, nc):
        self._assert_full_match(nc)
        self._assert_inc_variant(nc)
        self._assert_missing_load_type(nc)
        self._assert_missing_source(nc)
        self._assert_no_match_prefix(nc)
        self._assert_db_prefixed_name(nc)

    def _assert_full_match(self, nc):
        segs = nc.layers["ODS"].templates[0]
        r = nc._match_segments("ods_mysql_orders_full", segs)
        assert r == {
            "source": "mysql",
            "entity": "orders",
            "load_type": "full",
        }

    def _assert_inc_variant(self, nc):
        segs = nc.layers["ODS"].templates[0]
        r = nc._match_segments("ods_erp_customer_inc", segs)
        assert r == {"source": "erp", "entity": "customer", "load_type": "inc"}

    def _assert_missing_load_type(self, nc):
        """ODS 要求 load_type，缺失则返回 None"""
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("ods_mysql_customer", segs) is None

    def _assert_missing_source(self, nc):
        """ODS 要求 source，缺失则返回 None"""
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("ods_customer_full", segs) is None

    def _assert_no_match_prefix(self, nc):
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("xxx_customer_full", segs) is None

    def _assert_db_prefixed_name(self, nc):
        """_match_segments 不会自动剥离 db 前缀"""
        segs = nc.layers["ODS"].templates[0]
        assert (
            nc._match_segments("shop_dm.ods_mysql_orders_full", segs) is None
        )


# ============================================================
# _match_segments — DWD 模式
# ============================================================


class TestMatchDwd:
    @pytest.fixture
    def nc(self):
        return _build_nc({"DWD": ["dwd", "$entity"]})

    def test_match_dwd_scenarios(self, nc):
        self._assert_basic(nc)
        self._assert_with_underscore(nc)
        self._assert_no_match(nc)

    def _assert_basic(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("dwd_customer", segs)
        assert r == {"entity": "customer"}

    def _assert_with_underscore(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("dwd_order_detail", segs)
        assert r == {"entity": "order_detail"}

    def _assert_no_match(self, nc):
        segs = nc.layers["DWD"].templates[0]
        assert nc._match_segments("ods_customer", segs) is None


# ============================================================
# _match_segments — DWS 模式（含可选时间粒度）
# ============================================================


class TestMatchDws:
    @pytest.fixture
    def nc(self):
        return _build_nc({"DWS": ["dws", "$entity", "$time_granularity?"]})

    def test_match_dws_scenarios(self, nc):
        self._assert_with_granularity(nc)
        self._assert_with_monthly(nc)
        self._assert_without_granularity(nc)

    def _assert_with_granularity(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("dws_store_sales_daily", segs)
        assert r == {"entity": "store_sales", "time_granularity": "daily"}

    def _assert_with_monthly(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("dws_category_sales_monthly", segs)
        assert r == {"entity": "category_sales", "time_granularity": "monthly"}

    def _assert_without_granularity(self, nc):
        """可选段缺失时只返回 entity"""
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("dws_customer_order_summary", segs)
        assert r == {"entity": "customer_order_summary"}


# ============================================================
# _match_segments — ADS 模式
# ============================================================


class TestMatchAds:
    @pytest.fixture
    def nc(self):
        return _build_nc({"ADS": ["ads", "$business_view"]})

    def test_match_ads_scenarios(self, nc):
        self._assert_basic(nc)
        self._assert_with_underscore(nc)

    def _assert_basic(self, nc):
        segs = nc.layers["ADS"].templates[0]
        r = nc._match_segments("ads_customer_rfm", segs)
        assert r == {"business_view": "customer_rfm"}

    def _assert_with_underscore(self, nc):
        segs = nc.layers["ADS"].templates[0]
        r = nc._match_segments("ads_product_topn_daily", segs)
        assert r == {"business_view": "product_topn_daily"}


# ============================================================
# _match_segments — DIM 模式
# ============================================================


class TestMatchDim:
    @pytest.fixture
    def nc(self):
        return _build_nc({"DIM": ["dim", "$entity"]})

    def test_basic(self, nc):
        segs = nc.layers["DIM"].templates[0]
        r = nc._match_segments("dim_date", segs)
        assert r == {"entity": "date"}


# ============================================================
# _match_segments — 列模式
# ============================================================


class TestMatchColumn:
    @pytest.fixture
    def nc(self):
        return _build_nc(
            {},
            col_segments=["$prefix_field?", "$entity", "$suffix_field?"],
        )

    def test_column_segments_match_expected_parts(self, nc):
        scenarios = [
            ("customer_id", {"entity": "customer", "suffix_field": "id"}),
            ("order_date", {"entity": "order", "suffix_field": "date"}),
            ("quantity", {"entity": "quantity"}),
            ("avg_price", {"prefix_field": "avg", "entity": "price"}),
            (
                "avg_order_amount",
                {
                    "prefix_field": "avg",
                    "entity": "order",
                    "suffix_field": "amount",
                },
            ),
            ("is_active", {"prefix_field": "is", "entity": "active"}),
            (
                "max_score_num",
                {
                    "prefix_field": "max",
                    "entity": "score",
                    "suffix_field": "num",
                },
            ),
        ]
        for name, expected in scenarios:
            assert nc._match_segments(name, nc.column_segments) == expected


class TestNamingDiagnostics:
    def test_diagnostics_expose_configured_rules(self):
        self._assert_column_diagnostic_exposes_configured_expression()
        self._assert_table_diagnostic_exposes_segment_plan()

    def _assert_column_diagnostic_exposes_configured_expression(self):
        nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")

        diagnostic = nc.diagnose_column_name("customer_id")

        assert diagnostic["passed"] is False
        attempt = diagnostic["attempts"][0]
        assert attempt["rule"]["name"] == "COLUMN_DEFAULT"
        assert attempt["rule"]["raw_expr"] == "$COLUMN_IDENTIFIER"
        assert attempt["segments"][0]["type"]["patterns"] == [
            "^[A-Z][A-Z0-9_]{0,14}$"
        ]
        assert attempt["failure"]["code"] == "type_pattern_mismatch"

    def _assert_table_diagnostic_exposes_segment_plan(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_table_name(
            "dwd_customer",
            {"name": "dwd_customer", "layer": "DWD"},
        )

        assert diagnostic["passed"] is False
        attempt = diagnostic["attempts"][0]
        assert attempt["rule"]["name"] == "TABLE_DWD"
        assert attempt["rule"]["raw_expr"][0] == "_"
        assert attempt["expression"] == (
            "M_{BUSINESS_AREA_CODE}_{DATA_DOMAIN_ID}_"
            "{BIZ_PROCESS}_{TIME_PERIOD}{DWD_GRANULARITY}"
        )
        assert attempt["failure"]["code"] == "literal_mismatch"
        assert attempt["segments"][0]["kind"] == "literal"
        assert attempt["segments"][0]["name"] == "M"

    def test_table_diagnostic_uses_model_layer_and_model_values(self):
        nc = load_naming_config(config.naming_config_path())

        passing_diagnostic = nc.diagnose_table_name(
            "DIM_BASE_CUST_PROFILE_INFO",
            {
                "name": "dim_customer",
                "layer": "DIM",
                "entities": [
                    {
                        "code": "CUST",
                        "type": "primary",
                    },
                    {
                        "code": "PROD",
                        "type": "foreign",
                    },
                ],
            },
        )
        passing_constraint = passing_diagnostic["attempts"][0][
            "model_constraints"
        ]["MODEL_ENTITY"]
        assert passing_constraint["matched_model_value"] is True
        assert "model_value_failure" not in passing_constraint

        diagnostic = nc.diagnose_table_name(
            "DIM_BASE_PROD_PROFILE_INFO",
            {
                "name": "dim_customer",
                "layer": "DIM",
                "entities": [
                    {
                        "code": "CUST",
                        "type": "primary",
                    },
                    {
                        "code": "PROD",
                        "type": "foreign",
                    },
                ],
            },
        )

        assert diagnostic["layer"] == "DIM"
        assert diagnostic["layer_source"] == "model"
        assert diagnostic["model_name"] == "dim_customer"
        assert diagnostic["passed"] is False
        attempt = diagnostic["attempts"][0]
        assert attempt["template_passed"] is True
        assert attempt["matched_values"]["MODEL_ENTITY"] == "PROD"
        assert attempt["model_constraints"] == {
            "MODEL_ENTITY": {
                "values_from": {
                    "scope": "current_model",
                    "paths": ["entities.code", "entity.code"],
                },
                "allowed_values_from_model": ["CUST"],
                "actual_values": ["PROD"],
                "matched_model_value": False,
                "model_value_failure": {
                    "code": "model_value_mismatch",
                    "actual": ["PROD"],
                    "expected": ["CUST"],
                },
            }
        }

    def test_table_diagnostic_reports_missing_model_layer(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_table_name(
            "DIM_BASE_CUST_PROFILE_INFO",
            {"name": "dim_customer"},
        )

        assert diagnostic == {
            "actual": "DIM_BASE_CUST_PROFILE_INFO",
            "layer": None,
            "layer_source": "model",
            "model_name": "dim_customer",
            "passed": False,
            "attempts": [],
            "failure": {
                "code": "missing_model_layer",
                "message": "model.layer is required to diagnose table name",
            },
        }

    def test_table_diagnostic_reports_unknown_model_layer(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_table_name(
            "DIM_BASE_CUST_PROFILE_INFO",
            {"name": "dim_customer", "layer": "UNKNOWN"},
        )

        assert diagnostic == {
            "actual": "DIM_BASE_CUST_PROFILE_INFO",
            "layer": "UNKNOWN",
            "layer_source": "model",
            "model_name": "dim_customer",
            "passed": False,
            "attempts": [],
            "failure": {
                "code": "unknown_model_layer",
                "message": "model.layer is not defined in naming config",
            },
        }

    def test_metric_diagnostic_exposes_atomic_rule_failure(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_metric_name(
            "pay_amt",
            metric_kind="atomic",
        )

        assert diagnostic["actual"] == "pay_amt"
        assert diagnostic["metric_kind"] == "atomic"
        assert diagnostic["rule_name"] == "atomic"
        assert diagnostic["passed"] is False
        attempt = diagnostic["attempts"][0]
        assert attempt["rule"]["name"] == "atomic"
        assert attempt["rule"]["description"] == (
            "原子指标命名 {ACTION_VERB}_{MEASURE_NOUN}"
        )
        assert attempt["nodes"][0]["type"]["patterns"] == ["^[A-Z][A-Z0-9]*$"]
        assert attempt["failure"]["code"] == "metric_sequence_mismatch"

    def test_metric_diagnostic_exposes_derived_rule_match(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_metric_name(
            "7D_OLD_CHREM_PAY_AMT",
            metric_kind="derived",
        )

        assert diagnostic["actual"] == "7D_OLD_CHREM_PAY_AMT"
        assert diagnostic["metric_kind"] == "derived"
        assert diagnostic["rule_name"] == "derived"
        assert diagnostic["passed"] is True
        assert diagnostic["attempts"][0]["matched_values"] == {
            "METRIC_TIME_PERIOD": "7D",
            "METRIC_MODIFIER": ["OLD", "CHREM"],
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }

    def test_metric_diagnostic_reports_unknown_rule(self):
        nc = load_naming_config(config.naming_config_path())

        diagnostic = nc.diagnose_metric_name("PAY_AMT", rule_name="missing")

        assert diagnostic == {
            "actual": "PAY_AMT",
            "metric_kind": None,
            "rule_name": "missing",
            "passed": False,
            "attempts": [],
            "failure": {
                "code": "unknown_metric_rule",
                "actual": "missing",
            },
        }


class TestTopLevelDetermineLayer:
    def test_prefers_model_layer(self, monkeypatch, tmp_path):
        models_dir = tmp_path / "demo_project" / "ads" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "legacy_name.yaml").write_text(
            "version: 2\nname: legacy_name\nlayer: ADS\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
        monkeypatch.setitem(
            config.PROJECT_CONFIG, "demo", {"dir": "demo_project"}
        )
        config.clear_model_metadata_cache()

        assert config.determine_layer("legacy_name", "demo") == "ADS"

    def test_no_prefix_fallback(self, tmp_path, monkeypatch):
        project = "unit_empty_layers"
        (tmp_path / project / "mid" / "models").mkdir(parents=True)
        monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
        monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
        config.clear_model_metadata_cache()

        assert config.determine_layer("ods_", project) == "OTHER"
        assert config.determine_layer("dwd_", project) == "OTHER"

    def test_without_project_returns_other(self):
        assert config.determine_layer("dwd_customer") == "OTHER"


# ============================================================
# 独立层级排序
# ============================================================


class TestLayerRank:
    def test_layer_rank_scenarios(self):
        assert layer_rank("ODS") == 0
        assert layer_rank("DIM") == 1
        assert layer_rank("DWD") == 1
        assert layer_rank("DWS") == 2
        assert layer_rank("ADS") == 3
        assert layer_rank("UNKNOWN") == -1
        assert layer_rank("dwd") == 1


# ============================================================
# load_naming_config — 集成测试
# ============================================================


class TestLoadNamingConfig:
    def test_load_production_config_scenarios(self):
        """加载生产 YAML 无异常，关键层存在"""
        nc = load_naming_config()
        for layer in ("DWD", "DWS", "ADS", "DIM"):
            assert layer in nc.layers
        assert "DWD" in nc.layers
        assert len(nc.layers["DWD"].templates) == 1
        assert len(nc.column_segments) > 0
        assert "ETL_TIME" in nc.common_columns
        assert "SNAPSHOT_DATE" in nc.common_columns
        assert "etl_time" not in nc.common_columns
        assert "prefix_field" not in nc.types
        assert "suffix_field" not in nc.types
        assert nc._match_segments("CUSTOMER_ID", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID",
        }
        assert nc._match_segments("CUSTOMER_ID_123", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID_123",
        }
        assert nc._match_segments("customer_id", nc.column_segments) is None
        assert (
            nc._match_segments("CUSTOMER_ID_LONG1", nc.column_segments) is None
        )

    def test_segment_repeat_syntax_applies_to_table_and_column_rules(
        self, tmp_path
    ):
        cfg_path = tmp_path / "naming.yaml"
        cfg_path.write_text(
            """
types:
  BUSINESS_AREA_CODE:
    allow:
      - FRTN
  ENTITY:
    patterns:
      - "^[A-Z]+$"
  METRICS_DESC:
    allow:
      - BAL
rules:
  TABLE_DWS:
    expr: ["_", I, "$BUSINESS_AREA_CODE", "$ENTITY{1,2}", "$METRICS_DESC"]
  COLUMN_FLEX:
    expr: ["_", "$ENTITY{1,2}", "$METRICS_DESC"]
bindings:
  table:
    DWS:
      - "@TABLE_DWS"
  column:
    rules:
      - "@COLUMN_FLEX"
""",
            encoding="utf-8",
        )

        nc = load_naming_config(cfg_path)

        assert len(nc.layers["DWS"].templates) == 2
        assert nc._match_segments(
            "I_FRTN_CUST_PROD_BAL",
            nc.layers["DWS"].templates[0],
        ) == {
            "BUSINESS_AREA_CODE": "FRTN",
            "ENTITY": ["CUST", "PROD"],
            "METRICS_DESC": "BAL",
        }
        assert nc._match_segments(
            "I_FRTN_CUST_BAL",
            nc.layers["DWS"].templates[1],
        ) == {
            "BUSINESS_AREA_CODE": "FRTN",
            "ENTITY": "CUST",
            "METRICS_DESC": "BAL",
        }

        assert len(nc.column_templates) == 2
        assert nc._match_segments("CUST_PROD_BAL", nc.column_templates[0]) == {
            "ENTITY": ["CUST", "PROD"],
            "METRICS_DESC": "BAL",
        }
        assert nc._match_segments("CUST_BAL", nc.column_templates[1]) == {
            "ENTITY": "CUST",
            "METRICS_DESC": "BAL",
        }

    def test_yaml_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_naming_config("/nonexistent/path.yaml")

    def test_metric_pattern_uses_explicit_separators(self, tmp_path):
        cfg_path = tmp_path / "naming.yaml"
        cfg_path.write_text(
            """
types:
  ACTION_VERB:
    patterns:
      - "^[A-Z][A-Z0-9]*$"
  MEASURE_NOUN:
    allow:
      - AMT
      - CNT
metrics:
  atomic_metrics:
    pattern: "{ACTION_VERB}_{MEASURE_NOUN}"
""",
            encoding="utf-8",
        )

        nc = load_naming_config(cfg_path)
        assert nc.match_metric_rule("PAY_AMT", "atomic_metrics") == {
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("PAY__AMT", "atomic_metrics") is None

    def test_metric_rules_reject_plus_repeat_shorthand(self, tmp_path):
        cfg_path = tmp_path / "naming.yaml"
        cfg_path.write_text(
            """
types:
  METRIC_PART:
    patterns:
      - "^[A-Z]+$"
rules:
  BAD_METRIC:
    expr: ["_", "$METRIC_PART+"]
bindings:
  metric:
    atomic: "@BAD_METRIC"
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=r"\{min,max\} repeat syntax"):
            load_naming_config(cfg_path)


# ============================================================
# Enterprise V2 Naming Tests
# ============================================================

from dw_refactor_agent.config import PROJECT_ROOT, get_naming_config


class TestJoinExpressionSyntax:
    def test_join_expression_syntax_scenarios(self):
        self._assert_parse_nested_empty_join()
        self._assert_segment_match_uses_patterns_when_allow_misses()

    def _assert_parse_nested_empty_join(self):
        result = _parse_rule_expression(["_", "$a", ["", "$b", "$c"]], {})
        assert [item["name"] for item in result] == ["a", "_", "b", "c"]
        assert result[3].get("concat_left") is True

    def _assert_segment_match_uses_patterns_when_allow_misses(self):
        td = TypeDef(label="period", patterns=["^[0-9]+D$"], allow=["D"])
        types = {"period": td}
        nc = NamingConfig(
            types=types,
            layers={
                "X": LayerDef(
                    templates=[_parse_template(["x", "$period"], types)]
                )
            },
            column_segments=[],
            common_columns=set(),
        )
        assert nc._match_segments("x_D", nc.layers["X"].templates[0]) == {
            "period": "D",
        }
        assert nc._match_segments("x_30D", nc.layers["X"].templates[0]) == {
            "period": "30D",
        }


class TestEnterpriseNaming:
    @pytest.fixture
    def nc(self):
        return load_naming_config(PROJECT_ROOT / "naming_config.yaml")

    def test_enterprise_naming_scenarios(self, nc):
        self._assert_match_dwd_v2(nc)
        self._assert_match_dws_v2(nc)
        self._assert_match_dws_v2_single_entity(nc)
        self._assert_match_dws_v2_requires_entity(nc)
        self._assert_match_ads_v2(nc)
        self._assert_match_dim_v2(nc)
        self._assert_match_dim_v2_addt(nc)
        self._assert_match_dim_pm(nc)
        self._assert_table_name_max_length(nc)
        self._assert_entity_types_declare_model_sources(nc)
        self._assert_removed_legacy_column_segment_types(nc)
        self._assert_column_default_requires_uppercase_identifier_shorter_than_16(
            nc
        )
        self._assert_atomic_metric_rule(nc)
        self._assert_derived_metric_types(nc)

    def _assert_match_dwd_v2(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("M_WEMG_04_CHREM_DI", segs)
        assert r == {
            "BUSINESS_AREA_CODE": "WEMG",
            "DATA_DOMAIN_ID": "04",
            "BIZ_PROCESS": "CHREM",
            "TIME_PERIOD": "D",
            "DWD_GRANULARITY": "I",
        }

    def _assert_match_dws_v2(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("I_FRTN_CUST_PROD_BAL_DS", segs)
        assert r == {
            "BUSINESS_AREA_CODE": "FRTN",
            "GRAIN_ENTITY": ["CUST", "PROD"],
            "METRICS_DESC": "BAL",
            "TIME_PERIOD": "D",
            "DWS_GRANULARITY": "S",
        }

    def _assert_match_dws_v2_single_entity(self, nc):
        assert (
            nc._match_segments(
                "I_FRTN_CUST_BAL_DS",
                nc.layers["DWS"].templates[0],
            )
            is None
        )

        segs = nc.layers["DWS"].templates[1]
        r = nc._match_segments("I_FRTN_CUST_BAL_DS", segs)
        assert r == {
            "BUSINESS_AREA_CODE": "FRTN",
            "GRAIN_ENTITY": "CUST",
            "METRICS_DESC": "BAL",
            "TIME_PERIOD": "D",
            "DWS_GRANULARITY": "S",
        }

    def _assert_match_dws_v2_requires_entity(self, nc):
        assert all(
            nc._match_segments("I_FRTN_BAL_DS", segs) is None
            for segs in nc.layers["DWS"].templates
        )

    def _assert_match_ads_v2(self, nc):
        segs = nc.layers["ADS"].templates[0]
        r = nc._match_segments("A13_CUST_DS", segs)
        assert r == {
            "ADS_PREFIX": "A13",
            "ADS_TOPIC": "CUST",
            "TIME_PERIOD": "D",
            "ADS_GRANULARITY": "S",
        }

    def _assert_match_dim_v2(self, nc):
        segs = nc.layers["DIM"].templates[0]
        r = nc._match_segments("DIM_BASE_CUST_INFO_INFO", segs)
        assert r == {
            "DIM_ROLE": "BASE",
            "MODEL_ENTITY": "CUST",
            "DIM_DESC": "INFO",
            "DIM_CONTENT_TYPE": "INFO",
        }

    def _assert_match_dim_v2_addt(self, nc):
        segs = nc.layers["DIM"].templates[0]
        r = nc._match_segments("DIM_ADDT_CUST_SCTY_RELA_INFO", segs)
        assert r == {
            "DIM_ROLE": "ADDT",
            "MODEL_ENTITY": "CUST",
            "DIM_DESC": "SCTY_RELA",
            "DIM_CONTENT_TYPE": "INFO",
        }

    def _assert_match_dim_pm(self, nc):
        segs = nc.layers["DIM"].templates[1]
        r = nc._match_segments("DIM_PM_CD", segs)
        assert r == {"DIM_DESC": "CD"}

    def _assert_table_name_max_length(self, nc):
        assert nc.table_name_max_length == 30

    def _assert_entity_types_declare_model_sources(self, nc):
        assert nc.types["MODEL_ENTITY"].values_from == {
            "scope": "current_model",
            "paths": ["entities.code", "entity.code"],
        }
        assert nc.types["GRAIN_ENTITY"].values_from == {
            "scope": "current_model",
            "paths": ["grain.entities"],
        }

    def _assert_removed_legacy_column_segment_types(self, nc):
        assert "prefix_field" not in nc.types
        assert "suffix_field" not in nc.types

    def _assert_column_default_requires_uppercase_identifier_shorter_than_16(
        self, nc
    ):
        assert nc._match_segments("CUST_ID", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUST_ID",
        }
        assert nc._match_segments("CUSTOMER_ID_123", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID_123",
        }
        assert nc._match_segments("cust_id", nc.column_segments) is None
        assert (
            nc._match_segments("CUSTOMER_ID_LONG1", nc.column_segments) is None
        )

    def _assert_atomic_metric_rule(self, nc):
        assert nc.types["ACTION_VERB"].validate("PAY") is True
        assert nc.types["ACTION_VERB"].validate("pay") is False
        assert "AMT" in nc.types["MEASURE_NOUN"].allow

        assert nc.match_metric_rule("PAY_AMT", "atomic") == {
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("PAY_UNKNOWN", "atomic") is None
        assert nc.match_metric_rule("pay_amt", "atomic") is None

    def _assert_derived_metric_types(self, nc):
        assert "7D" not in nc.types["METRIC_TIME_PERIOD"].allow
        assert nc.types["METRIC_TIME_PERIOD"].validate("7D") is True
        assert nc.types["METRIC_TIME_PERIOD"].validate("L13M") is True
        assert nc.types["METRIC_TIME_PERIOD"].validate("0D") is False
        assert nc.types["METRIC_TIME_PERIOD"].validate("AD") is False
        assert nc.types["METRIC_MODIFIER"].validate("OLD") is True
        assert nc.types["METRIC_MODIFIER"].validate("HIGH_NET") is True
        assert nc.types["METRIC_MODIFIER"].validate("OL") is False
        assert nc.types["METRIC_MODIFIER"].validate("high_net") is False
        assert nc.metric_rules["derived"][0]["nodes"] == [
            {
                "kind": "type",
                "name": "METRIC_TIME_PERIOD",
                "repeat": {"min": 1, "max": 1},
            },
            {
                "kind": "type",
                "name": "METRIC_MODIFIER",
                "repeat": {"min": 1, "max": None},
            },
            {
                "kind": "rule",
                "name": "ATOMIC_METRIC",
                "repeat": {"min": 1, "max": 1},
            },
        ]
        assert nc.match_metric_rule(
            "7D_OLD_CHREM_PAY_AMT",
            "derived",
        ) == {
            "METRIC_TIME_PERIOD": "7D",
            "METRIC_MODIFIER": ["OLD", "CHREM"],
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("OLD_7D_PAY_AMT", "derived") is None
        assert nc.match_metric_rule("7D_OL_PAY_AMT", "derived") is None


class TestGetNamingConfigByProject:
    def test_default(self):
        nc = get_naming_config()
        assert len(nc.layers["DWD"].templates) == 1
        assert nc._match_segments(
            "M_WEMG_04_CHREM_DI",
            nc.layers["DWD"].templates[0],
        ) == {
            "BUSINESS_AREA_CODE": "WEMG",
            "DATA_DOMAIN_ID": "04",
            "BIZ_PROCESS": "CHREM",
            "TIME_PERIOD": "D",
            "DWD_GRANULARITY": "I",
        }
        assert nc.match_metric_rule("PAY_AMT", "atomic") == {
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("pay_amt", "atomic") is None

    def test_project_business_dictionary_tightens_naming_types(
        self, isolated_project_naming_configs
    ):
        shop_nc = get_naming_config(isolated_project_naming_configs["shop"])
        finance_nc = get_naming_config(
            isolated_project_naming_configs["finance"]
        )
        assert (
            shop_nc._match_segments(
                "M_WEMG_04_CHREM_DI",
                shop_nc.layers["DWD"].templates[0],
            )
            is None
        )
        assert (
            shop_nc._match_segments(
                "M_SHOP_04_ORDER_DI",
                shop_nc.layers["DWD"].templates[0],
            )
            is not None
        )
        assert (
            finance_nc._match_segments(
                "M_WEMG_04_CHREM_DI",
                finance_nc.layers["DWD"].templates[0],
            )
            is None
        )
        assert (
            finance_nc._match_segments(
                "M_LOAN_04_CHREM_DI",
                finance_nc.layers["DWD"].templates[0],
            )
            is not None
        )
        assert finance_nc.types["BUSINESS_AREA_CODE"].allow == [
            "LOAN",
            "PAYM",
            "CLNT",
            "OTHR",
        ]
        assert shop_nc.types["BUSINESS_AREA_CODE"].allow == ["SHOP"]
        assert shop_nc.types["DATA_DOMAIN_ID"].allow == [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "99",
        ]
        assert shop_nc.types["BUSINESS_AREA_CODE"].dictionary == {
            "dictionary": "business_areas",
            "value_field": "code",
        }
        assert shop_nc.types["DATA_DOMAIN_ID"].dictionary == {
            "dictionary": "data_domains",
            "value_field": "id",
        }
        assert finance_nc.types["DATA_DOMAIN_ID"].allow == [
            "01",
            "04",
            "10",
            "99",
        ]
        assert finance_nc.types["BUSINESS_AREA_CODE"].dictionary == {
            "dictionary": "business_areas",
            "value_field": "code",
        }
        assert finance_nc.types["DATA_DOMAIN_ID"].dictionary == {
            "dictionary": "data_domains",
            "value_field": "id",
        }

    def test_project_naming_dictionary_merges_business_catalog(
        self, tmp_path, monkeypatch
    ):
        project = "unit_catalog_naming"
        project_dir = tmp_path / project
        project_dir.mkdir()
        raw = yaml.safe_load(
            config.naming_config_path().read_text(encoding="utf-8")
        )
        raw.pop("dictionaries", None)
        raw["types"]["BUSINESS_AREA_CODE"]["allow"] = {
            "dictionary": "business_areas",
            "value_field": "code",
        }
        raw["types"]["BUSINESS_AREA_CODE"].pop("patterns", None)
        raw["types"]["DATA_DOMAIN_ID"]["allow"] = {
            "dictionary": "data_domains",
            "value_field": "id",
        }
        raw["types"]["DATA_DOMAIN_ID"].pop("patterns", None)
        (tmp_path / "naming_config.yaml").write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (project_dir / "business_semantics.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "project": project,
                    "data_domains": [
                        {
                            "id": "04",
                            "code": "ORDR",
                            "name": "订单域",
                        }
                    ],
                    "business_areas": [
                        {
                            "id": "SHOP",
                            "code": "SHOP",
                            "name": "零售业务",
                        }
                    ],
                    "business_processes": [],
                    "semantic_subjects": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
        monkeypatch.setitem(
            config.PROJECT_CONFIG,
            project,
            {
                "dir": project,
                "naming_config": "naming_config.yaml",
            },
        )
        config.clear_naming_config_cache()
        config.clear_business_semantics_cache()

        nc = get_naming_config(project)

        assert nc.types["BUSINESS_AREA_CODE"].allow == ["SHOP"]
        assert nc.types["DATA_DOMAIN_ID"].allow == ["04"]
        assert nc.dictionaries["business_areas"]["values"][0]["code"] == "SHOP"
        assert nc.dictionaries["data_domains"]["values"][0]["id"] == "04"
        assert (
            nc._match_segments(
                "M_SHOP_04_ORDER_DI",
                nc.layers["DWD"].templates[0],
            )
            is not None
        )
        assert (
            nc._match_segments(
                "M_PAYM_04_ORDER_DI",
                nc.layers["DWD"].templates[0],
            )
            is None
        )

    def test_load_business_domain_config_for_finance_project(
        self, isolated_project_naming_configs
    ):
        business_config = get_business_domain_config(
            isolated_project_naming_configs["finance"]
        )

        assert business_config.is_valid_domain("04") is True
        assert business_config.normalize_domain("TRAN") == "04"
        assert business_config.normalize_domain("4") == "04"
        assert business_config.is_valid_domain("99") is True
        assert business_config.is_valid_business_area("PAYM") is True
        assert business_config.is_valid_business_area("OTHR") is True
        assert "PAYM" in business_config.business_area_codes
        assert "04" in business_config.domain_ids
        assert (
            "allowed_data_domains"
            not in (business_config.prompt_options()["business_areas"][0])
        )

    def test_load_business_domain_config_for_shop_project(
        self, isolated_project_naming_configs
    ):
        business_config = get_business_domain_config(
            isolated_project_naming_configs["shop"]
        )

        assert business_config.is_valid_domain("04") is True
        assert business_config.normalize_domain("ORDR") == "04"
        assert business_config.normalize_domain("4") == "04"
        assert business_config.is_valid_domain("99") is True
        assert business_config.is_valid_business_area("SHOP") is True
        assert business_config.is_valid_business_area("PAYM") is False
        assert business_config.business_area_codes == ["SHOP"]
        assert business_config.domain_ids == [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "99",
        ]
