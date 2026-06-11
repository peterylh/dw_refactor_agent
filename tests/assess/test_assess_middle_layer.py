import pytest
import yaml

import config
from config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
    load_naming_config,
    PROJECT_ROOT,
)
from assess.assess_middle_layer import (
    ATOMIC_METRIC_RULE_NAME,
    DIM_ENTITY_RULE_NAME,
    DERIVED_METRIC_RULE_NAME,
    FILE_RULE_DDL,
    FILE_RULE_MODEL_NAME,
    FILE_RULE_MODEL_TABLE,
    FILE_RULE_TASK_LINEAGE,
    FILE_RULE_TASK_SQL,
    assess,
    generate_report,
    normalize_score_weights,
    score_architecture_health,
    score_metadata_health,
    score_naming_conventions,
)
from assess.table_inspector import TableInspectResult


def _business_domain_config():
    return BusinessDomainConfig(
        domains={
            "04": DomainDef(id="04", code="TRAN", name="交易域"),
            "10": DomainDef(id="10", code="MKTG", name="营销域"),
            "99": DomainDef(id="99", code="OTHR", name="其它"),
        },
        business_areas={
            "PAYM": BusinessAreaDef(id="04", code="PAYM", name="支付结算"),
            "CLNT": BusinessAreaDef(id="13", code="CLNT", name="客户经营"),
            "OTHR": BusinessAreaDef(id="99", code="OTHR", name="其它"),
        },
    )


def _business_naming_config(tmp_path):
    raw = yaml.safe_load(
        (PROJECT_ROOT / "naming_config.yaml").read_text(encoding="utf-8"))
    raw["dictionaries"] = {
        "data_domains": {
            "values": [
                {"id": "04", "code": "TRAN", "name": "交易域"},
                {"id": "10", "code": "MKTG", "name": "营销域"},
                {"id": "99", "code": "OTHR", "name": "其它"},
            ]
        },
        "business_areas": {
            "values": [
                {"id": "04", "code": "PAYM", "name": "支付结算"},
                {"id": "13", "code": "CLNT", "name": "客户经营"},
                {"id": "99", "code": "OTHR", "name": "其它"},
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
    cfg_path = tmp_path / "business_naming.yaml"
    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return load_naming_config(cfg_path)


@pytest.fixture
def isolated_assess_project(tmp_path, monkeypatch):
    import assess.assess_middle_layer as assess_module

    project = "unit_assess"
    (tmp_path / project).mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        (PROJECT_ROOT / "naming_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(assess_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {
        "dir": project,
        "naming_config": "naming_config.yaml",
    })
    config._naming_config_cache.clear()
    config._model_metadata_cache.clear()
    yield project
    config._naming_config_cache.clear()
    config._model_metadata_cache.clear()


def test_assess_returns_raw_and_display_scores(monkeypatch, sample_lineage_data,
                                               isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)

    assert "architecture" in result
    assert "metadata_health" in result
    assert result["weights"]["architecture"] == 0.2
    assert result["weights"]["metadata_health"] == 0.2

    # 展示分 = 原始分 (取消展示分映射后)
    assert result["reuse"]["raw"] == result["reuse"]["display"]
    assert result["depth"]["raw"] == result["depth"]["display"]
    assert result["architecture"]["raw"] == result["architecture"]["display"]
    assert result["metadata_health"]["raw"] == result[
        "metadata_health"]["display"]
    assert result["naming"]["raw"] == result["naming"]["display"]
    assert result["overall_display"] == result["overall_raw"]

    # sample: 4 张表, 1 条违规 (低权重=1), cap 后 = 1, 合规率 = (1 - 1/4) × 100 = 75
    assert result["architecture"]["raw"] == 75.0


def test_normalize_score_weights_supports_partial_override():
    weights = normalize_score_weights({"reuse": 0.3})

    assert weights["reuse"] == pytest.approx(0.272727, rel=0, abs=1e-6)
    assert weights["depth"] == pytest.approx(0.181818, rel=0, abs=1e-6)
    assert weights["architecture"] == pytest.approx(0.181818, rel=0, abs=1e-6)
    assert weights["metadata_health"] == pytest.approx(0.181818,
                                                       rel=0,
                                                       abs=1e-6)
    assert weights["naming"] == pytest.approx(0.181818, rel=0, abs=1e-6)
    assert sum(weights[key] for key in [
        "reuse",
        "depth",
        "architecture",
        "metadata_health",
        "naming",
    ]) == pytest.approx(1.0, rel=0, abs=1e-6)


def test_score_metadata_health_validates_model_entity_and_grain_entity():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "DIM_BASE_PROD_INFO_INFO",
            "layer": "DIM",
            "columns": [{"name": "product_id", "type": "BIGINT"}],
        },
        {
            "name": "I_SHOP_CAT_SALE_DS",
            "layer": "DWS",
            "columns": [
                {"name": "category_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
            ],
        },
    ]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "layer": "DIM",
            "table_type": "dimension",
            "entity": {
                "code": "CUST",
                "key_columns": ["product_id"],
            },
        },
        "I_SHOP_CAT_SALE_DS": {
            "layer": "DWS",
            "table_type": "fact",
            "grain": {
                "keys": ["category_id", "stat_date"],
                "entities": ["CAT"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        },
    }

    result = score_metadata_health(tables, nc, model_metadata)

    assert result["score"] == 66.7
    assert result["passed"] == 2
    assert result["total"] == 3
    assert [
        violation["message"] for violation in result["violations"]
    ] == [
        "grain.entities未定义=['CAT']",
    ]


def test_score_metadata_health_validates_entities_schema():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "DIM_BASE_PROD_INFO_INFO",
            "layer": "DIM",
            "columns": [
                {"name": "product_id", "type": "BIGINT"},
                {"name": "category_id", "type": "BIGINT"},
            ],
        },
        {
            "name": "I_SHOP_PROD_SALE_DS",
            "layer": "DWS",
            "columns": [
                {"name": "product_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
            ],
        },
    ]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "layer": "DIM",
            "table_type": "dimension",
            "entities": [{
                "code": "PROD",
                "type": "primary",
                "key_columns": ["product_id"],
            }, {
                "code": "CAT",
                "type": "foreign",
                "key_columns": ["category_id"],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": "PROD",
                },
            }],
        },
        "I_SHOP_PROD_SALE_DS": {
            "layer": "DWS",
            "table_type": "fact",
            "entities": [{
                "code": "PROD",
                "type": "foreign",
                "key_columns": ["product_id"],
            }],
            "grain": {
                "entities": ["PROD"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        },
    }

    result = score_metadata_health(tables, nc, model_metadata)

    assert result["score"] == 100.0
    assert result["passed"] == result["total"]


def test_generate_report_contains_raw_and_display_scores(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)
    report = generate_report(result, result["weights"], isolated_assess_project)

    assert "总体评分(展示)" in report
    assert "总体评分(原始)" in report
    assert "【架构合理性】评分: 75.0" in report
    assert "【模型元数据健康度】评分" in report
    assert "Σ(每表 cap 后权重) = 1" in report


def test_assess_includes_atomic_metric_naming_summary(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    project_dir = config.PROJECT_ROOT / isolated_assess_project
    (project_dir / "ddl").mkdir()
    (project_dir / "ddl" / "dwd_order_detail.sql").write_text(
        """
CREATE TABLE IF NOT EXISTS demo.dwd_order_detail (
    ORDER_ID BIGINT,
    PAY_AMT DECIMAL(12,2)
) ENGINE=OLAP
DUPLICATE KEY(ORDER_ID)
DISTRIBUTED BY HASH(ORDER_ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    monkeypatch.setattr(
        "config.load_model_metadata",
        lambda project: {
            "dwd_order_detail": {
                "layer": "DWD",
                "atomic_metrics": ["PAY_AMT", "PAY_UNKNOWN"]
            }
        },
    )

    result = assess(project=isolated_assess_project)

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
    business_config = _business_domain_config()
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
    business_config = _business_domain_config()
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


def test_score_naming_conventions_includes_structured_diagnostics():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "dwd_customer",
            "layer": "DWD",
            "columns": [{"name": "customer_id"}],
        },
    ]

    result = score_naming_conventions(tables, nc)
    detail = result["details"][0]

    table_diag = detail["table_checks"]["diagnostics"][0]
    assert table_diag["check"] == "table_template"
    assert table_diag["attempts"][0]["rule"]["name"] == "TABLE_DWD"
    assert table_diag["attempts"][0]["failure"]["code"] == "literal_mismatch"

    column_diag = detail["column_checks"]["diagnostics"][0]
    assert column_diag["actual"] == "customer_id"
    assert column_diag["attempts"][0]["rule"]["name"] == "COLUMN_DEFAULT"
    assert column_diag["attempts"][0]["segments"][0]["type"]["patterns"] == [
        "^[A-Z][A-Z0-9_]{0,14}$"
    ]


def test_score_naming_conventions_checks_business_dictionary_metadata(tmp_path):
    nc = _business_naming_config(tmp_path)
    business_config = nc.business_domain_config
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


def test_score_naming_conventions_limits_business_metadata_by_layer(tmp_path):
    nc = _business_naming_config(tmp_path)
    business_config = nc.business_domain_config
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


def test_score_naming_conventions_checks_project_file_names(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks" / "full_refresh").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    ddl = f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    ID BIGINT
) ENGINE=OLAP
DUPLICATE KEY(ID)
DISTRIBUTED BY HASH(ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
    (project_dir / "ddl" / f"{table_name}.sql").write_text(ddl)
    (project_dir / "models" / f"{table_name}.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n"
    )
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )
    full_refresh = project_dir / "tasks" / "full_refresh" / (
        f"{table_name}_full_refresh.sql"
    )
    full_refresh.write_text(f"INSERT INTO demo.{table_name} SELECT 1 AS ID;")

    tables = []
    edges = [
        {
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        },
        {
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"full_refresh/{table_name}_full_refresh.sql",
        },
    ]

    result = score_naming_conventions(
        tables,
        nc,
        {table_name: {"layer": "DWD"}},
        project_dir=project_dir,
        edges=edges,
        indirect_edges=[],
    )

    assert result["score"] == 100.0
    assert result["file_checks"] == {"passed": 7, "total": 7}
    assert result["file_details"] == []
    assert result["rule_summary"][FILE_RULE_DDL] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_TABLE] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_NAME] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 2,
        "total": 2,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 2,
        "total": 2,
        "pct": 100.0,
    }


def test_score_naming_conventions_flags_project_file_name_mismatches(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()

    table_name = "M_WEMG_04_CHREM_DI"
    ddl = f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    ID BIGINT
) ENGINE=OLAP
DUPLICATE KEY(ID)
DISTRIBUTED BY HASH(ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
    (project_dir / "ddl" / "wrong_ddl.sql").write_text(ddl)
    (project_dir / "models" / "wrong_model.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n"
    )
    (project_dir / "tasks" / "wrong_task.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )

    tables = [{"name": table_name, "layer": "DWD", "columns": []}]
    edges = [{
        "source": "ods_source.ID",
        "target": f"{table_name}.ID",
        "source_file": "wrong_task.sql",
    }]

    result = score_naming_conventions(
        tables,
        nc,
        {table_name: {"layer": "DWD"}},
        project_dir=project_dir,
        edges=edges,
        indirect_edges=[],
    )

    assert result["score"] == 37.5
    assert result["details"][0]["column_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }
    assert result["file_checks"] == {"passed": 0, "total": 5}
    assert result["rule_summary"][FILE_RULE_DDL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_TABLE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_NAME] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert {detail["rule"] for detail in result["file_details"]} == {
        FILE_RULE_DDL,
        FILE_RULE_MODEL_TABLE,
        FILE_RULE_MODEL_NAME,
        FILE_RULE_TASK_SQL,
        FILE_RULE_TASK_LINEAGE,
    }


def test_score_naming_conventions_flags_missing_task_lineage(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[],
        indirect_edges=[],
    )

    assert result["score"] == 50.0
    assert result["file_checks"] == {"passed": 1, "total": 2}
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["file_details"] == [{
        "file": "demo/tasks/M_WEMG_04_CHREM_DI.sql",
        "rule": FILE_RULE_TASK_LINEAGE,
        "expected": table_name,
        "actual": "未解析",
    }]


def test_score_naming_conventions_does_not_reuse_basename_lineage(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks" / "archive").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )
    archived_task = project_dir / "tasks" / "archive" / f"{table_name}.sql"
    archived_task.write_text(f"INSERT INTO demo.{table_name} SELECT 1 AS ID;")

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[{
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        }],
        indirect_edges=[],
    )

    assert result["file_checks"] == {"passed": 3, "total": 4}
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["file_details"] == [{
        "file": f"demo/tasks/archive/{table_name}.sql",
        "rule": FILE_RULE_TASK_LINEAGE,
        "expected": table_name,
        "actual": "未解析",
    }]


def test_score_naming_conventions_checks_extra_write_targets(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"""
TRUNCATE TABLE demo.WRONG_TARGET;
INSERT INTO demo.{table_name} SELECT 1 AS ID;
UPDATE demo.{table_name} SET ID = 1;
DELETE FROM demo.{table_name} WHERE ID = 1;
"""
    )

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[{
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        }],
        indirect_edges=[],
    )

    assert result["score"] == 50.0
    assert result["file_checks"] == {"passed": 1, "total": 2}
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["file_details"] == [{
        "file": f"demo/tasks/{table_name}.sql",
        "rule": FILE_RULE_TASK_SQL,
        "expected": table_name,
        "actual": f"{table_name}, WRONG_TARGET",
    }]


def test_score_naming_conventions_prefers_current_ddl_columns_over_lineage_snapshot(
        tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "ddl" / f"{table_name}.sql").write_text(
        f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    bad_field VARCHAR(16)
) ENGINE=OLAP
DUPLICATE KEY(bad_field)
DISTRIBUTED BY HASH(bad_field) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )

    stale_lineage_tables = [{
        "name": table_name,
        "layer": "DWD",
        "columns": [{"name": "GOOD_COL"}],
    }]
    model_metadata = {table_name: {"layer": "DWD"}}

    result = score_naming_conventions(
        stale_lineage_tables,
        nc,
        model_metadata,
        project_dir=project_dir,
    )

    assert result["details"][0]["column_checks"]["passed"] == 0
    assert result["details"][0]["column_checks"]["total"] == 1
    assert result["details"][0]["column_checks"]["violations"] == [
        "bad_field"
    ]


def test_score_naming_conventions_does_not_fall_back_to_lineage_tables_when_project_dir_exists(
        tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)

    lineage_only_tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [{"name": "BAD_FIELD"}],
    }]

    result = score_naming_conventions(
        lineage_only_tables,
        nc,
        project_dir=project_dir,
    )

    assert result["details"] == []
    assert result["rule_summary"]["表名符合规范模板"] == {
        "pass_count": 0,
        "total": 0,
        "pct": 0,
    }
    assert result["rule_summary"]["列名总计"] == {
        "pass_count": 0,
        "total": 0,
        "pct": 0,
    }


def test_score_naming_conventions_prefers_model_layer_over_lineage_snapshot():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    table_name = "DIM_BASE_CUST_PROFILE_INFO"
    stale_lineage_tables = [{
        "name": table_name,
        "layer": "DWD",
        "columns": [{"name": "CUST_ID"}],
    }]
    model_metadata = {table_name: {"layer": "DIM"}}

    result = score_naming_conventions(
        stale_lineage_tables,
        nc,
        model_metadata,
    )

    assert result["details"][0]["layer"] == "DIM"
    assert result["details"][0]["table_checks"]["violations"] == []


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


def test_score_naming_conventions_checks_dws_entity_against_model_grain():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "I_SHOP_CAT_SALE_DS",
        "layer": "DWS",
        "columns": [],
    }]
    model_metadata = {
        "I_SHOP_CAT_SALE_DS": {
            "grain": {
                "keys": ["product_id", "stat_date"],
                "entities": ["PROD"],
                "time_column": "stat_date",
                "time_period": "D",
            }
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"]["DWS表名实体包含于grain.entities"] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["details"][0]["dws_entity_checks"] == {
        "passed": 0,
        "total": 1,
        "violations": ["表名ENTITY=['CAT']，grain.entities=['PROD']"],
    }


def test_score_naming_conventions_checks_dim_entity_against_model_entity():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "DIM_BASE_PROD_INFO_INFO",
        "layer": "DIM",
        "columns": [],
    }]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "entity": {
                "code": "CUST",
                "key_columns": ["product_id"],
            }
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DIM_ENTITY_RULE_NAME] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["details"][0]["dim_entity_checks"] == {
        "passed": 0,
        "total": 1,
        "violations": [
            "表名MODEL_ENTITY=['PROD']，entities.primary.code=['CUST']"
        ],
    }


def test_score_naming_conventions_requires_dws_grain_entities_from_models():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "I_SHOP_PROD_SALE_DS",
        "layer": "DWS",
        "columns": [],
    }]
    model_metadata = {
        "I_SHOP_PROD_SALE_DS": {
            "layer": "DWS",
            "table_type": "fact",
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"]["DWS表名实体包含于grain.entities"] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["details"][0]["dws_entity_checks"] == {
        "passed": 0,
        "total": 1,
        "violations": ["缺少grain.entities，无法检测DWS表名ENTITY"],
    }


def test_score_naming_conventions_requires_dws_grain_entity_definitions():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "I_SHOP_CAT_SALE_DS",
        "layer": "DWS",
        "columns": [],
    }]
    model_metadata = {
        "I_SHOP_CAT_SALE_DS": {
            "grain": {
                "keys": ["category_id", "stat_date"],
                "entities": ["CAT"],
                "time_column": "stat_date",
                "time_period": "D",
            }
        },
        "M_SHOP_02_PROD_DF": {
            "entity": {
                "code": "PROD",
                "key_columns": ["product_id"],
            },
        },
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["details"][0]["dws_entity_checks"] == {
        "passed": 0,
        "total": 1,
        "violations": ["grain.entities未定义=['CAT']"],
    }


def test_score_naming_conventions_uses_full_dws_grain_entities():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "I_SHOP_PROD_STORE_SALE_DS",
        "layer": "DWS",
        "columns": [],
    }]
    model_metadata = {
        "I_SHOP_PROD_STORE_SALE_DS": {
            "grain": {
                "keys": ["product_id", "store_id", "customer_id", "stat_date"],
                "entities": ["PROD", "STORE", "CUST"],
                "time_column": "stat_date",
                "time_period": "D",
            }
        },
        "DIM_BASE_PROD_INFO_INFO": {
            "entity": {
                "code": "PROD",
                "key_columns": ["product_id"],
            },
        },
        "DIM_BASE_STORE_INFO_INFO": {
            "entity": {
                "code": "STORE",
                "key_columns": ["store_id"],
            },
        },
        "DIM_BASE_CUST_INFO_INFO": {
            "entity": {
                "code": "CUST",
                "key_columns": ["customer_id"],
            },
        },
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"]["DWS表名实体包含于grain.entities"] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["details"][0]["dws_entity_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }


def test_score_naming_conventions_accepts_dim_entity_from_model():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "DIM_BASE_PROD_INFO_INFO",
        "layer": "DIM",
        "columns": [],
    }]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "entity": {
                "code": "PROD",
                "key_columns": ["product_id"],
            }
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DIM_ENTITY_RULE_NAME] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["details"][0]["dim_entity_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }


def test_score_naming_conventions_accepts_entities_schema():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    tables = [{
        "name": "DIM_BASE_PROD_INFO_INFO",
        "layer": "DIM",
        "columns": [],
    }, {
        "name": "I_SHOP_PROD_STORE_SALE_DS",
        "layer": "DWS",
        "columns": [],
    }]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "entities": [{
                "code": "PROD",
                "type": "primary",
                "key_columns": ["product_id"],
            }],
        },
        "I_SHOP_PROD_STORE_SALE_DS": {
            "entities": [{
                "code": "PROD",
                "type": "foreign",
                "key_columns": ["product_id"],
            }, {
                "code": "STORE",
                "type": "foreign",
                "key_columns": ["store_id"],
            }],
            "grain": {
                "entities": ["PROD", "STORE"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        },
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DIM_ENTITY_RULE_NAME] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"]["DWS表名实体包含于grain.entities"] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
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
