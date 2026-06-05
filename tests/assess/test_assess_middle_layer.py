from config import (
    get_business_domain_config,
    get_naming_config,
    load_naming_config,
    PROJECT_ROOT,
)
from assess.assess_middle_layer import (
    ATOMIC_METRIC_RULE_NAME,
    DERIVED_METRIC_RULE_NAME,
    assess,
    generate_report,
    score_architecture_health,
    score_naming_conventions,
)
from assess.table_inspector import TableInspectResult


def test_assess_returns_raw_and_display_scores(monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")

    assert "architecture" in result
    assert result["weights"]["architecture"] == 0.25

    # 展示分 = 原始分 (取消展示分映射后)
    assert result["reuse"]["raw"] == result["reuse"]["display"]
    assert result["depth"]["raw"] == result["depth"]["display"]
    assert result["architecture"]["raw"] == result["architecture"]["display"]
    assert result["naming"]["raw"] == result["naming"]["display"]
    assert result["overall_display"] == result["overall_raw"]

    # sample: 4 张表, 1 条违规 (低权重=1), cap 后 = 1, 合规率 = (1 - 1/4) × 100 = 75
    assert result["architecture"]["raw"] == 75.0


def test_generate_report_contains_raw_and_display_scores(
        monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")
    report = generate_report(result, result["weights"], "shop")

    assert "总体评分(展示)" in report
    assert "总体评分(原始)" in report
    assert "【架构合理性】评分: 75.0" in report
    assert "Σ(每表 cap 后权重) = 1" in report


def test_assess_includes_atomic_metric_naming_summary(
        monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    monkeypatch.setattr(
        "config.load_model_metadata",
        lambda project: {
            "dwd_order_detail": {
                "atomic_metrics": ["PAY_AMT", "PAY_UNKNOWN"]
            }
        },
    )

    result = assess(project="shop")

    assert result["naming"]["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }


def test_score_architecture_health_penalizes_declared_table_type_mismatch(
        sample_lineage_data):
    result = score_architecture_health(
        sample_lineage_data["tables"],
        sample_lineage_data["edges"],
        sample_lineage_data["indirect_edges"],
        llm_results=[
            TableInspectResult(
                table_name="dws_store_sales_daily",
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="dimension",
                confidence=0.9,
                reasoning_steps=[],
            )
        ],
        model_metadata={
            "dws_store_sales_daily": {
                "table_type": "fact",
            }
        },
    )

    type_violations = [
        v for v in result["violations"]
        if v["description"].startswith("表类型配置疑似错误")
    ]
    assert type_violations == [{
        "source": "dws_store_sales_daily(fact)",
        "target": "dws_store_sales_daily(dimension)",
        "severity": "中",
        "weight": 2,
        "description": "表类型配置疑似错误(LLM): 配置类型=fact, 推断类型=dimension",
        "source_file": "",
        "source_type": "llm",
        "belongs_to": "dws_store_sales_daily",
    }]


def test_score_architecture_health_allows_ads_to_read_dim():
    tables = [
        {"name": "dim_customer", "layer": "DIM", "columns": []},
        {"name": "ads_customer_by_segment", "layer": "ADS", "columns": []},
    ]
    edges = [{
        "source": "dim_customer.customer_id",
        "target": "ads_customer_by_segment.customer_id",
        "source_file": "ads_customer_by_segment.sql",
    }]

    result = score_architecture_health(tables, edges, [])

    assert result["score"] == 100.0
    assert result["violations"] == []


def test_score_architecture_health_penalizes_llm_business_metadata_mismatch():
    business_config = get_business_domain_config("finance_analytics")
    tables = [{"name": "dwd_transactions", "layer": "DWD", "columns": []}]

    result = score_architecture_health(
        tables,
        [],
        [],
        llm_results=[
            TableInspectResult(
                table_name="dwd_transactions",
                declared_layer="DWD",
                inferred_layer="DWD",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                inferred_data_domain="04",
                inferred_business_area="PAYM",
            )
        ],
        model_metadata={
            "dwd_transactions": {
                "data_domain": "10",
                "business_area": "CLNT",
            }
        },
        business_domain_config=business_config,
    )

    descriptions = [v["description"] for v in result["violations"]]
    assert any(desc.startswith("数据域配置疑似错误") for desc in descriptions)
    assert any(desc.startswith("业务板块配置疑似错误") for desc in descriptions)


def test_score_architecture_health_limits_business_checks_by_layer():
    business_config = get_business_domain_config("finance_analytics")
    tables = [{"name": "dws_transactions", "layer": "DWS", "columns": []}]

    result = score_architecture_health(
        tables,
        [],
        [],
        llm_results=[
            TableInspectResult(
                table_name="dws_transactions",
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                inferred_data_domain="04",
                inferred_business_area="PAYM",
            )
        ],
        model_metadata={
            "dws_transactions": {
                "business_area": "CLNT",
            }
        },
        business_domain_config=business_config,
    )

    descriptions = [v["description"] for v in result["violations"]]
    assert not any(desc.startswith("数据域配置疑似错误") for desc in descriptions)
    assert any(desc.startswith("业务板块配置疑似错误") for desc in descriptions)


def test_score_naming_conventions_checks_table_name_length():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {"name": "M_WEMG_04_CHREM_DI", "layer": "DWD", "columns": []},
        {"name": "M_WEMG_04_CHREMEXTRALONGNAME_DI", "layer": "DWD", "columns": []},
    ]

    result = score_naming_conventions(tables, nc)

    assert result["rule_summary"]["表名长度 <= 30"] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["details"][1]["table_checks"]["violations"] == ["违反: 表名长度 <= 30"]


def test_score_naming_conventions_checks_business_dictionary_metadata():
    nc = get_naming_config("finance_analytics")
    business_config = get_business_domain_config("finance_analytics")
    tables = [
        {"name": "M_PAYM_04_CHREM_DI", "layer": "DWD", "columns": []},
        {"name": "M_BAD_98_CHREM_DI", "layer": "DWD", "columns": []},
    ]
    model_metadata = {
        "M_PAYM_04_CHREM_DI": {
            "data_domain": "04",
            "business_area": "PAYM",
        },
        "M_BAD_98_CHREM_DI": {
            "data_domain": "98",
            "business_area": "BAD",
        },
    }

    result = score_naming_conventions(
        tables,
        nc,
        model_metadata,
        business_config,
    )

    assert result["rule_summary"]["数据域属于字典"] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["rule_summary"]["业务板块属于字典"] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["details"][1]["business_metadata_checks"]["violations"] == [
        "数据域不在字典: 98",
        "业务板块不在字典: BAD",
    ]


def test_score_naming_conventions_limits_business_metadata_by_layer():
    nc = get_naming_config("finance_analytics")
    business_config = get_business_domain_config("finance_analytics")
    tables = [
        {"name": "M_PAYM_04_CHREM_DI", "layer": "DWD", "columns": []},
        {"name": "I_CLNT_CUST_SUM_DS", "layer": "DWS", "columns": []},
        {"name": "D_CUST", "layer": "DIM", "columns": []},
    ]
    model_metadata = {
        "M_PAYM_04_CHREM_DI": {
            "data_domain": "98",
            "business_area": "PAYM",
        },
        "I_CLNT_CUST_SUM_DS": {
            "business_area": "CLNT",
        },
        "D_CUST": {
            "data_domain": "99",
            "business_area": "BAD",
        },
    }

    result = score_naming_conventions(
        tables,
        nc,
        model_metadata,
        business_config,
    )

    assert result["rule_summary"]["数据域属于字典"] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"]["业务板块属于字典"] == {
        "pass_count": 2,
        "total": 2,
        "pct": 100.0,
    }
    dws_detail = next(
        item for item in result["details"]
        if item["table"] == "I_CLNT_CUST_SUM_DS"
    )
    dim_detail = next(
        item for item in result["details"]
        if item["table"] == "D_CUST"
    )
    assert dws_detail["business_metadata_checks"]["violations"] == []
    assert dim_detail["business_metadata_checks"]["total"] == 0


def test_score_naming_conventions_checks_atomic_metrics_from_models():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT", "pay_amt", "PAY_UNKNOWN"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 3,
        "pct": 33.3,
    }
    assert result["details"][0]["atomic_metric_checks"] == {
        "passed": 1,
        "total": 3,
        "violations": ["PAY_UNKNOWN", "pay_amt"],
    }


def test_score_naming_conventions_checks_derived_metrics_from_models():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": [
                "7D_OLD_CHREM_PAY_AMT",
                "30D_HIGH_NET_PAY_CNT",
                "OLD_7D_PAY_AMT",
                "7D_OL_PAY_AMT",
                "7D_OLD_PAY_UNKNOWN",
            ]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 2,
        "total": 5,
        "pct": 40.0,
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 2,
        "total": 5,
        "violations": [
            "7D_OLD_PAY_UNKNOWN",
            "7D_OL_PAY_AMT",
            "OLD_7D_PAY_AMT",
        ],
    }


def test_score_naming_conventions_checks_default_enterprise_metric_bindings():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT", "pay_amt"],
            "derived_metrics": ["7D_OLD_PAY_AMT", "transaction_count"],
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }


def test_score_naming_conventions_derived_metrics_follow_rule_config():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    nc.metric_rules["derived"][0]["nodes"][1]["repeat"]["min"] = 2
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": [
                "7D_OLD_CHREM_PAY_AMT",
                "7D_OLD_PAY_AMT",
            ]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 1,
        "total": 2,
        "violations": ["7D_OLD_PAY_AMT"],
    }


def test_score_naming_conventions_does_not_double_check_derived_metric_columns():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [{"name": "7D_OLD_PAY_AMT"}],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": ["7D_OLD_PAY_AMT"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["details"][0]["column_checks"] == {
        "passed": 0,
        "total": 0,
        "violations": [],
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }
    assert result["details"][0]["score"] == 100.0


def test_score_naming_conventions_does_not_double_check_atomic_metric_columns():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [{"name": "PAY_AMT"}],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["details"][0]["column_checks"] == {
        "passed": 0,
        "total": 0,
        "violations": [],
    }
    assert result["details"][0]["atomic_metric_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }
    assert result["details"][0]["score"] == 100.0
