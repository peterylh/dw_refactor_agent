"""config.py NamingConfig 的单元测试"""
import re
import pytest
import config
from config import (
    TypeDef, LayerDef, NamingConfig,
    _parse_rule_expression, _parse_segments, _parse_template, load_naming_config,
    layer_rank,
)


# ============================================================
# TypeDef.validate
# ============================================================

class TestTypeDef:
    def test_allow_match(self):
        td = TypeDef(label="load_type", allow=["full", "inc"])
        assert td.validate("full") is True
        assert td.validate("inc") is True

    def test_allow_no_match(self):
        td = TypeDef(label="load_type", allow=["full", "inc"])
        assert td.validate("daily") is False
        assert td.validate("") is False

    def test_patterns_match(self):
        td = TypeDef(label="source", patterns=["^[a-z0-9]+$"])
        assert td.validate("mysql") is True
        assert td.validate("erp01") is True

    def test_patterns_no_match(self):
        td = TypeDef(label="source", patterns=["^[a-z0-9]+$"])
        assert td.validate("MySql") is False
        assert td.validate("") is False

    def test_neither_allow_nor_patterns(self):
        td = TypeDef(label="freeform")
        assert td.validate("anything") is True

    def test_allow_and_patterns_are_or_validators(self):
        td = TypeDef(
            label="period",
            patterns=["^[0-9]+D$"],
            allow=["D", "MTD"],
        )
        assert td.validate("D") is True
        assert td.validate("7D") is True
        assert td.validate("0M") is False


# ============================================================
# _parse_segments
# ============================================================

class TestParseSegments:
    def test_basic_list(self):
        """[ods, $source, $entity] → 3 段 + 2 个 _"""
        result = _parse_segments(["ods", "$source", "$entity"], {})
        assert len(result) == 5
        assert result[0] == {"name": "ods", "kind": "literal", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}
        assert result[1] == {"name": "_", "kind": "literal", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}
        assert result[2] == {"name": "source", "kind": "type", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}
        assert result[3] == {"name": "_", "kind": "literal", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}
        assert result[4] == {"name": "entity", "kind": "type", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}

    def test_optional_right_gets_sep_before(self):
        """[$entity, "$time_granularity?"] → 右侧可选段获得 sep_before，不插入独立 _"""
        result = _parse_segments(["$entity", "$time_granularity?"], {})
        assert len(result) == 2
        assert result[0] == {"name": "entity", "kind": "type", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}
        assert result[1] == {"name": "time_granularity", "kind": "type", "optional": True,
                             "sep_before": "_", "sep_after": "", "concat_left": False}

    def test_optional_left_gets_sep_after(self):
        """["$prefix_field?", $entity] → 左侧可选段获得 sep_after"""
        result = _parse_segments(["$prefix_field?", "$entity"], {})
        assert len(result) == 2
        assert result[0] == {"name": "prefix_field", "kind": "type", "optional": True,
                             "sep_before": "", "sep_after": "_", "concat_left": False}
        assert result[1] == {"name": "entity", "kind": "type", "optional": False,
                             "sep_before": "", "sep_after": "", "concat_left": False}

    def test_double_optional(self):
        """["$prefix_field?", "$entity", "$suffix_field?"] → 混合可选绑定"""
        result = _parse_segments(["$prefix_field?", "$entity", "$suffix_field?"], {})
        assert len(result) == 3
        assert result[0]["name"] == "prefix_field" and result[0]["optional"] is True
        assert result[0]["sep_after"] == "_"
        assert result[1]["name"] == "entity" and result[1]["optional"] is False
        assert result[1]["sep_before"] == ""
        assert result[1]["sep_after"] == ""
        assert result[2]["name"] == "suffix_field" and result[2]["optional"] is True
        assert result[2]["sep_before"] == "_"

    def test_empty_list(self):
        assert _parse_segments([], {}) == []

    def test_single_literal(self):
        result = _parse_segments(["dim"], {})
        assert len(result) == 1
        assert result[0]["kind"] == "literal"
        assert result[0]["name"] == "dim"

    def test_single_type(self):
        result = _parse_segments(["$entity"], {})
        assert len(result) == 1
        assert result[0]["kind"] == "type"
        assert result[0]["name"] == "entity"

    def test_optional_marker_without_dollar(self):
        """无 $ 前缀的 ? 被识别为字面量"""
        result = _parse_segments(["time_granularity?"], {})
        # '?' 在名称中是字面量的一部分
        assert result[0]["name"] == "time_granularity" and result[0]["optional"] is True
        assert result[0]["kind"] == "literal"

    def test_all_required_separator(self):
        """[a, b, c] 全 required → 段间插入 _"""
        result = _parse_segments(["a", "b", "c"], {})
        assert len(result) == 5
        assert [s["name"] for s in result] == ["a", "_", "b", "_", "c"]


# ============================================================
# _parse_template
# ============================================================

class TestParseTemplate:
    def test_list_format_passthrough(self):
        """列表格式直接委托给 _parse_segments"""
        result = _parse_template(["$entity"], {})
        assert result[0]["kind"] == "type"
        assert result[0]["name"] == "entity"

    def test_string_format_conversion(self):
        """"ods_{source}_{entity}_{load_type}" → 添加 $ 前缀"""
        result = _parse_template("ods_{source}_{entity}_{load_type}", {})
        type_names = [s["name"] for s in result if s["kind"] == "type"]
        assert "source" in type_names
        assert "entity" in type_names
        assert "load_type" in type_names
        assert result[0]["kind"] == "literal" and result[0]["name"] == "ods_"

    def test_string_format_with_optional(self):
        """"_{type?}" 转换"""
        result = _parse_template("_{type?}", {})
        types = [s for s in result if s["kind"] == "type"]
        assert types[0]["name"] == "type"
        assert types[0]["optional"] is True

    def test_empty_string(self):
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
            allow=["id", "name", "code", "date", "time", "amount",
                   "price", "cost", "count", "quantity", "status",
                   "type", "level", "score", "segment", "method",
                   "num", "rate", "ratio", "flag", "desc", "note"],
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

    def test_full_match(self, nc):
        segs = nc.layers["ODS"].templates[0]
        r = nc._match_segments("ods_mysql_orders_full", segs)
        assert r == {"source": "mysql", "entity": "orders", "load_type": "full"}

    def test_inc_variant(self, nc):
        segs = nc.layers["ODS"].templates[0]
        r = nc._match_segments("ods_erp_customer_inc", segs)
        assert r == {"source": "erp", "entity": "customer", "load_type": "inc"}

    def test_missing_load_type(self, nc):
        """ODS 要求 load_type，缺失则返回 None"""
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("ods_mysql_customer", segs) is None

    def test_missing_source(self, nc):
        """ODS 要求 source，缺失则返回 None"""
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("ods_customer_full", segs) is None

    def test_no_match_prefix(self, nc):
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("xxx_customer_full", segs) is None

    def test_db_prefixed_name(self, nc):
        """_match_segments 不会自动剥离 db 前缀"""
        segs = nc.layers["ODS"].templates[0]
        assert nc._match_segments("shop_dm.ods_mysql_orders_full", segs) is None


# ============================================================
# _match_segments — DWD 模式
# ============================================================

class TestMatchDwd:
    @pytest.fixture
    def nc(self):
        return _build_nc({"DWD": ["dwd", "$entity"]})

    def test_basic(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("dwd_customer", segs)
        assert r == {"entity": "customer"}

    def test_with_underscore(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("dwd_order_detail", segs)
        assert r == {"entity": "order_detail"}

    def test_no_match(self, nc):
        segs = nc.layers["DWD"].templates[0]
        assert nc._match_segments("ods_customer", segs) is None


# ============================================================
# _match_segments — DWS 模式（含可选时间粒度）
# ============================================================

class TestMatchDws:
    @pytest.fixture
    def nc(self):
        return _build_nc({"DWS": ["dws", "$entity", "$time_granularity?"]})

    def test_with_granularity(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("dws_store_sales_daily", segs)
        assert r == {"entity": "store_sales", "time_granularity": "daily"}

    def test_with_monthly(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("dws_category_sales_monthly", segs)
        assert r == {"entity": "category_sales", "time_granularity": "monthly"}

    def test_without_granularity(self, nc):
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

    def test_basic(self, nc):
        segs = nc.layers["ADS"].templates[0]
        r = nc._match_segments("ads_customer_rfm", segs)
        assert r == {"business_view": "customer_rfm"}

    def test_with_underscore(self, nc):
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

    def test_entity_suffix(self, nc):
        r = nc._match_segments("customer_id", nc.column_segments)
        assert r == {"entity": "customer", "suffix_field": "id"}

    def test_entity_suffix_date(self, nc):
        r = nc._match_segments("order_date", nc.column_segments)
        assert r == {"entity": "order", "suffix_field": "date"}

    def test_entity_only(self, nc):
        r = nc._match_segments("quantity", nc.column_segments)
        assert r == {"entity": "quantity"}

    def test_prefix_entity(self, nc):
        r = nc._match_segments("avg_price", nc.column_segments)
        assert r == {"prefix_field": "avg", "entity": "price"}

    def test_prefix_entity_suffix(self, nc):
        r = nc._match_segments("avg_order_amount", nc.column_segments)
        assert r == {"prefix_field": "avg", "entity": "order",
                     "suffix_field": "amount"}

    def test_is_prefix(self, nc):
        r = nc._match_segments("is_active", nc.column_segments)
        assert r == {"prefix_field": "is", "entity": "active"}

    def test_full_prefix_entity_suffix(self, nc):
        r = nc._match_segments("max_score_num", nc.column_segments)
        assert r == {"prefix_field": "max", "entity": "score", "suffix_field": "num"}


class TestTopLevelDetermineLayer:
    def test_prefers_model_layer(self, monkeypatch, tmp_path):
        models_dir = tmp_path / "demo_project" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "legacy_name.yaml").write_text(
            "version: 2\n"
            "name: legacy_name\n"
            "layer: ADS\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
        monkeypatch.setitem(config.PROJECT_CONFIG, "demo", {"dir": "demo_project"})
        config._model_metadata_cache.clear()

        assert config.determine_layer("legacy_name", "demo") == "ADS"

    def test_no_prefix_fallback(self):
        assert config.determine_layer("ods_", "shop") == "OTHER"
        assert config.determine_layer("dwd_", "shop") == "OTHER"

    def test_without_project_returns_other(self):
        assert config.determine_layer("dwd_customer") == "OTHER"


# ============================================================
# 独立层级排序
# ============================================================

class TestLayerRank:
    def test_ordered(self):
        assert layer_rank("ODS") == 0
        assert layer_rank("DIM") == 1
        assert layer_rank("DWD") == 1
        assert layer_rank("DWS") == 2
        assert layer_rank("ADS") == 3

    def test_unknown(self):
        assert layer_rank("UNKNOWN") == -1

    def test_normalizes_case(self):
        assert layer_rank("dwd") == 1


# ============================================================
# load_naming_config — 集成测试
# ============================================================

class TestLoadNamingConfig:
    def test_load_production_config(self):
        """加载生产 YAML 无异常，关键层存在"""
        nc = load_naming_config()
        for layer in ("DWD", "DWS", "ADS", "DIM"):
            assert layer in nc.layers

    def test_table_templates_do_not_require_layers_block(self):
        nc = load_naming_config()
        assert "DWD" in nc.layers
        assert len(nc.layers["DWD"].templates) == 1

    def test_column_segments(self):
        nc = load_naming_config()
        assert len(nc.column_segments) > 0

    def test_common_columns(self):
        nc = load_naming_config()
        assert "ETL_TIME" in nc.common_columns
        assert "SNAPSHOT_DATE" in nc.common_columns
        assert "etl_time" not in nc.common_columns

    def test_removed_legacy_column_segment_types(self):
        nc = load_naming_config()
        assert "prefix_field" not in nc.types
        assert "suffix_field" not in nc.types

    def test_column_default_requires_uppercase_identifier_shorter_than_16(self):
        nc = load_naming_config()
        assert nc._match_segments("CUSTOMER_ID", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID",
        }
        assert nc._match_segments("CUSTOMER_ID_123", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID_123",
        }
        assert nc._match_segments("customer_id", nc.column_segments) is None
        assert nc._match_segments("CUSTOMER_ID_LONG1", nc.column_segments) is None

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

from config import get_naming_config, PROJECT_ROOT

class TestJoinExpressionSyntax:
    def test_parse_nested_empty_join(self):
        result = _parse_rule_expression(["_", "$a", ["", "$b", "$c"]], {})
        assert [item["name"] for item in result] == ["a", "_", "b", "c"]
        assert result[3].get("concat_left") is True

    def test_segment_match_uses_patterns_when_allow_misses(self):
        td = TypeDef(label="period", patterns=["^[0-9]+D$"], allow=["D"])
        types = {"period": td}
        nc = NamingConfig(
            types=types,
            layers={"X": LayerDef(templates=[_parse_template(["x", "$period"], types)])},
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

    def test_match_dwd_v2(self, nc):
        segs = nc.layers["DWD"].templates[0]
        r = nc._match_segments("M_WEMG_04_CHREM_DI", segs)
        assert r == {
            "BIZ_MODULE": "WEMG",
            "DOMAIN_CODE": "04",
            "BIZ_PROCESS": "CHREM",
            "TIME_PERIOD": "D",
            "DWD_GRANULARITY": "I",
        }

    def test_match_dws_v2(self, nc):
        segs = nc.layers["DWS"].templates[0]
        r = nc._match_segments("I_FRTN_CUST_PROD_BAL_DS", segs)
        assert r == {
            "BIZ_MODULE": "FRTN",
            "ENTITY": ["CUST", "PROD"],
            "METRICS_DESC": "BAL",
            "TIME_PERIOD": "D",
            "DWS_GRANULARITY": "S",
        }

    def test_match_ads_v2(self, nc):
        segs = nc.layers["ADS"].templates[0]
        r = nc._match_segments("A13_CUST_DS", segs)
        assert r == {
            "ADS_PREFIX": "A13",
            "ADS_TOPIC": "CUST",
            "TIME_PERIOD": "D",
            "ADS_GRANULARITY": "S",
        }

    def test_match_dim_v2(self, nc):
        segs = nc.layers["DIM"].templates[0]
        r = nc._match_segments("DIM_BASE_CUST_INFO_INFO", segs)
        assert r == {
            "DIM_SCOPE": "BASE",
            "ENTITY": "CUST",
            "DIM_DESC": "INFO",
            "DIM_TYPE": "INFO",
        }

    def test_match_dim_v2_addt(self, nc):
        segs = nc.layers["DIM"].templates[0]
        r = nc._match_segments("DIM_ADDT_CUST_SCTY_RELA_INFO", segs)
        assert r == {
            "DIM_SCOPE": "ADDT",
            "ENTITY": "CUST",
            "DIM_DESC": "SCTY_RELA",
            "DIM_TYPE": "INFO",
        }

    def test_match_dim_pm(self, nc):
        segs = nc.layers["DIM"].templates[1]
        r = nc._match_segments("DIM_PM_CD", segs)
        assert r == {"DIM_DESC": "CD"}

    def test_table_name_max_length(self, nc):
        assert nc.table_name_max_length == 30

    def test_removed_legacy_column_segment_types(self, nc):
        assert "prefix_field" not in nc.types
        assert "suffix_field" not in nc.types

    def test_column_default_requires_uppercase_identifier_shorter_than_16(self, nc):
        assert nc._match_segments("CUST_ID", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUST_ID",
        }
        assert nc._match_segments("CUSTOMER_ID_123", nc.column_segments) == {
            "COLUMN_IDENTIFIER": "CUSTOMER_ID_123",
        }
        assert nc._match_segments("cust_id", nc.column_segments) is None
        assert nc._match_segments("CUSTOMER_ID_LONG1", nc.column_segments) is None

    def test_atomic_metric_rule(self, nc):
        assert nc.types["ACTION_VERB"].validate("PAY") is True
        assert nc.types["ACTION_VERB"].validate("pay") is False
        assert "AMT" in nc.types["MEASURE_NOUN"].allow

        assert nc.match_metric_rule("PAY_AMT", "atomic") == {
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("PAY_UNKNOWN", "atomic") is None
        assert nc.match_metric_rule("pay_amt", "atomic") is None

    def test_derived_metric_types(self, nc):
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
            {"kind": "type", "name": "METRIC_TIME_PERIOD", "repeat": {"min": 1, "max": 1}},
            {"kind": "type", "name": "METRIC_MODIFIER", "repeat": {"min": 1, "max": None}},
            {"kind": "rule", "name": "ATOMIC_METRIC", "repeat": {"min": 1, "max": 1}},
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
            "BIZ_MODULE": "WEMG",
            "DOMAIN_CODE": "04",
            "BIZ_PROCESS": "CHREM",
            "TIME_PERIOD": "D",
            "DWD_GRANULARITY": "I",
        }
        assert nc.match_metric_rule("PAY_AMT", "atomic") == {
            "ACTION_VERB": "PAY",
            "MEASURE_NOUN": "AMT",
        }
        assert nc.match_metric_rule("pay_amt", "atomic") is None

    def test_projects_use_default_naming_config(self):
        shop_nc = get_naming_config("shop")
        finance_nc = get_naming_config("finance_analytics")
        assert shop_nc._match_segments(
            "M_WEMG_04_CHREM_DI",
            shop_nc.layers["DWD"].templates[0],
        ) is not None
        assert finance_nc._match_segments(
            "M_WEMG_04_CHREM_DI",
            finance_nc.layers["DWD"].templates[0],
        ) is not None
