import pytest
import yaml

import config
from config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
    PROJECT_ROOT,
    load_naming_config,
)
from assess.assess_middle_layer import (
    assess,
    build_asset_catalog,
    generate_report,
    normalize_score_weights,
    score_architecture_health,
    score_asset_completeness,
    score_metadata_health,
    score_naming_conventions,
)
from assess.llm.table_inspector import TableInspectResult


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


def _issue_rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def _checks_by_rule(result, rule_id):
    return [
        check for check in result["checks"]
        if check["rule_id"] == rule_id
    ]


def test_assess_returns_dimension_check_issue_model(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)

    assert result["project"] == isolated_assess_project
    assert "overall_score" in result
    assert set(result["dimensions"]) == {
        "reuse",
        "depth",
        "model_design",
        "naming",
        "asset_completeness",
        "metadata_health",
        "code_quality",
    }
    for dimension in result["dimensions"].values():
        assert set(dimension) >= {
            "score",
            "rule_summary",
            "checks",
            "issues",
        }
    assert result["dimensions"]["model_design"]["score"] == 50.0
    assert result["dimensions"]["model_design"]["issues"][0]["severity"] == "中"
    assert result["dimensions"]["asset_completeness"]["issues"] == []
    assert result["dimensions"]["asset_completeness"]["checks"] == []
    assert all(
        not check["passed"]
        for dimension in result["dimensions"].values()
        for check in dimension["checks"]
    )


def test_assess_can_include_passed_checks(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(
        project=isolated_assess_project,
        include_passed_checks=True,
    )

    assert any(
        check["passed"]
        for check in result["dimensions"]["model_design"]["checks"]
    )
    assert any(
        not check["passed"]
        for check in result["dimensions"]["model_design"]["checks"]
    )


def test_assess_can_run_selected_model_design_only(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(
        project=isolated_assess_project,
        selected_dimensions={"model_design"},
    )

    assert set(result["dimensions"]) == {"model_design"}
    assert result["dimensions"]["model_design"]["score"] == 50.0


def test_assess_accepts_architecture_dimension_alias(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(
        project=isolated_assess_project,
        selected_dimensions={"architecture"},
    )

    assert set(result["dimensions"]) == {"model_design"}


def test_generate_report_reads_dimension_issues(
        monkeypatch, sample_lineage_data, isolated_assess_project):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)
    report = generate_report(result, result["weights"], isolated_assess_project)

    assert "总体评分" in report
    assert "ARCH_SKIP_LAYER_DEPENDENCY" in report
    assert "问题项" in report
    assert "总体评分(展示)" not in report


def test_normalize_score_weights_supports_partial_override():
    weights = normalize_score_weights({"reuse": 0.3})

    assert weights["reuse"] == pytest.approx(0.267857, rel=0, abs=1e-6)
    assert weights["depth"] == pytest.approx(0.160714, rel=0, abs=1e-6)
    assert weights["model_design"] == pytest.approx(0.160714,
                                                    rel=0,
                                                    abs=1e-6)
    assert weights["asset_completeness"] == pytest.approx(0.080357,
                                                          rel=0,
                                                          abs=1e-6)
    assert weights["metadata_health"] == pytest.approx(0.080357,
                                                       rel=0,
                                                       abs=1e-6)
    assert weights["naming"] == pytest.approx(0.160714, rel=0, abs=1e-6)
    assert weights["code_quality"] == pytest.approx(0.089286,
                                                    rel=0,
                                                    abs=1e-6)


def test_normalize_score_weights_accepts_architecture_alias():
    weights = normalize_score_weights({"architecture": 0.3})

    assert weights["model_design"] == pytest.approx(0.267857,
                                                    rel=0,
                                                    abs=1e-6)
    assert "architecture" not in weights


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
            "semantic_subject": "CUST",
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

    assert result["score"] == 80.0
    assert result["rule_summary"]["METADATA_GRAIN_ENTITIES_DEFINED"] == {
        "name": "grain.entities有实体定义",
        "severity": "中",
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["checks"][-1] == {
        "id": "metadata_health.chk_005",
        "rule_id": "METADATA_GRAIN_ENTITIES_DEFINED",
        "target": {
            "type": "table",
            "name": "I_SHOP_CAT_SALE_DS",
        },
        "passed": False,
        "expected": "grain.entities引用已定义实体",
        "actual": "未定义实体: ['CAT']",
        "evidence": {
            "grain_entities": ["CAT"],
            "defined_entities": ["CUST"],
        },
        "message": "grain.entities未定义=['CAT']",
    }
    assert result["issues"][0]["severity"] == "中"
    assert result["issues"][0]["remediation"]["strategy"] == (
        "update_model_grain_entities"
    )


def test_score_metadata_health_passes_valid_entities_schema():
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
            "semantic_subject": "PROD",
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
    assert result["issues"] == []
    assert all(check["passed"] for check in result["checks"])


def test_score_metadata_health_validates_dim_semantic_subject():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "dim_product",
        "layer": "DIM",
        "columns": [{"name": "product_id", "type": "BIGINT"}],
    }]
    model_metadata = {
        "dim_product": {
            "name": "dim_product",
            "layer": "DIM",
            "table_type": "dimension",
            "semantic_subject": "STORE",
            "entities": [{
                "code": "PRODUCT",
                "type": "primary",
                "key_columns": ["product_id"],
            }],
        }
    }

    result = score_metadata_health(tables, nc, model_metadata)

    assert "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY" in _issue_rule_ids(
        result)


def test_score_metadata_health_requires_dim_semantic_subject():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "dim_customer",
        "layer": "DIM",
        "columns": [{"name": "customer_id", "type": "BIGINT"}],
    }]
    model_metadata = {
        "dim_customer": {
            "name": "dim_customer",
            "layer": "DIM",
            "table_type": "dimension",
            "entities": [{
                "code": "CUSTOMER",
                "type": "primary",
                "key_columns": ["customer_id"],
            }],
        }
    }

    result = score_metadata_health(tables, nc, model_metadata)

    assert "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY" in _issue_rule_ids(
        result)


def test_score_metadata_health_requires_dws_grain_entities_from_models():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")
    result = score_metadata_health(
        [{"name": "I_SHOP_PROD_SALE_DS", "layer": "DWS", "columns": []}],
        nc,
        {"I_SHOP_PROD_SALE_DS": {"layer": "DWS", "table_type": "fact"}},
    )

    assert result["score"] == 0.0
    assert result["issues"] == [{
        "id": "metadata_health.iss_001",
        "severity": "高",
        "rule_id": "METADATA_GRAIN_ENTITIES_PRESENT",
        "target": {
            "type": "table",
            "name": "I_SHOP_PROD_SALE_DS",
        },
        "title": "DWS模型缺少grain.entities",
        "message": "缺少grain.entities",
        "remediation": {
            "summary": "在模型YAML中补齐grain.entities",
            "strategy": "update_model_grain_entities",
            "edit_scope": ["models"],
        },
        "check_ids": ["metadata_health.chk_001"],
    }]


def test_score_metadata_health_checks_business_dictionary_metadata(tmp_path):
    nc = _business_naming_config(tmp_path)
    result = score_metadata_health(
        [
            {"name": "M_PAYM_04_CHREM_DI", "layer": "DWD", "columns": []},
            {"name": "M_BAD_98_CHREM_DI", "layer": "DWD", "columns": []},
        ],
        nc,
        {
            "M_PAYM_04_CHREM_DI": {
                "data_domain": "04",
                "business_area": "PAYM",
            },
            "M_BAD_98_CHREM_DI": {
                "data_domain": "98",
                "business_area": "BAD",
            },
        },
        nc.business_domain_config,
    )

    assert result["rule_summary"]["METADATA_DATA_DOMAIN_VALID"] == {
        "name": "data_domain配置有效",
        "severity": "中",
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["rule_summary"]["METADATA_BUSINESS_AREA_VALID"][
        "pass_count"] == 1
    assert _issue_rule_ids(result) == {
        "METADATA_DATA_DOMAIN_VALID",
        "METADATA_BUSINESS_AREA_VALID",
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

    type_issue = next(
        issue for issue in result["issues"]
        if issue["rule_id"] == "ARCH_TABLE_TYPE_MATCHES_LLM"
    )
    assert type_issue["severity"] == "中"
    assert type_issue["target"]["name"] == "dws_store_sales_daily"
    check = next(
        check for check in result["checks"]
        if check["id"] == type_issue["check_ids"][0]
    )
    assert check["actual"] == "配置类型=fact, 推断类型=dimension"


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
    assert result["issues"] == []
    assert result["checks"][0]["rule_id"] == "ARCH_ALLOWED_DEPENDENCY"


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

    assert _issue_rule_ids(result) == {
        "ARCH_DATA_DOMAIN_MATCHES_LLM",
        "ARCH_BUSINESS_AREA_MATCHES_LLM",
    }


def test_score_architecture_health_limits_business_checks_by_layer():
    business_config = _business_domain_config()
    result = score_architecture_health(
        [{"name": "dws_transactions", "layer": "DWS", "columns": []}],
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

    assert _issue_rule_ids(result) == {"ARCH_BUSINESS_AREA_MATCHES_LLM"}
    assert not _checks_by_rule(result, "ARCH_DATA_DOMAIN_MATCHES_LLM")


def test_score_asset_completeness_classifies_missing_assets(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()

    (project_dir / "ddl" / "dwd_orders.sql").write_text(
        """
CREATE TABLE demo.dwd_orders (
    order_id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1;
""",
        encoding="utf-8",
    )
    (project_dir / "models" / "dws_orders.yaml").write_text(
        "name: dws_orders\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "tasks" / "dws_missing.sql").write_text(
        "INSERT INTO demo.dws_missing SELECT 1 AS order_id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    result = score_asset_completeness(catalog)

    assert result["score"] == 25.0
    assert {
        (item["target"]["name"], item["rule_id"])
        for item in result["issues"]
    } == {
        ("dwd_orders", "ASSET_DDL_HAS_MODEL"),
        ("dwd_orders", "ASSET_EXECUTABLE_DDL_HAS_TASK"),
        ("dws_orders", "ASSET_MODEL_HAS_DDL"),
        ("dws_missing", "ASSET_TASK_OUTPUT_HAS_DDL"),
        ("dws_missing", "ASSET_TASK_OUTPUT_HAS_MODEL"),
        ("tasks/dws_missing.sql", "ASSET_TASK_LINEAGE_MATCHES_OUTPUT"),
    }
    assert all(item["severity"] == "高" for item in result["issues"])
    assert all(
        check["passed"]
        for rule_id in [
            "ASSET_TASK_SINGLE_OUTPUT",
            "ASSET_TABLE_SINGLE_WRITER",
        ]
        for check in _checks_by_rule(result, rule_id)
    )
    task_lineage_check = next(
        check for check in result["checks"]
        if check["rule_id"] == "ASSET_TASK_LINEAGE_MATCHES_OUTPUT"
    )
    assert task_lineage_check["actual"] == "实际产出=['dws_missing']，血缘目标=[]"
    assert task_lineage_check["evidence"] == {
        "outputs": ["dws_missing"],
        "lineage_targets": [],
    }


def test_score_asset_completeness_ignores_dropped_ctas_temp_tables(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()

    (project_dir / "ddl" / "dws_orders.sql").write_text(
        """
CREATE TABLE demo.dws_orders (
    order_id BIGINT,
    amount DECIMAL(12, 2)
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1;
""",
        encoding="utf-8",
    )
    (project_dir / "models" / "dws_orders.yaml").write_text(
        "name: dws_orders\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "tasks" / "dws_orders.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT order_id, amount
FROM demo.dwd_orders;

INSERT INTO demo.dws_orders
SELECT order_id, amount
FROM demo.tmp_orders_stage;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {"name": "dws_orders", "layer": "DWS", "columns": []},
            {"name": "tmp_orders_stage", "layer": "OTHER", "columns": []},
        ],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {
                "source_file": "dws_orders.sql",
                "target": "demo.tmp_orders_stage.order_id",
            },
            {
                "source_file": "dws_orders.sql",
                "target": "demo.dws_orders.order_id",
            },
        ],
        indirect_edges=[],
        transient_tables=[
            {
                "name": "tmp_orders_stage",
                "source_file": "dws_orders.sql",
                "created_statement_index": 0,
                "dropped_statement_index": 2,
                "is_ctas": True,
                "is_transient": True,
                "dropped_in_same_task": True,
            }
        ],
    )
    result = score_asset_completeness(catalog)

    assert catalog["tasks"][0]["output_tables"] == {"dws_orders"}
    assert catalog["tasks"][0]["lineage_targets"] == {"dws_orders"}
    assert "tmp_orders_stage" not in catalog["tables"]
    assert result["issues"] == []


def test_asset_catalog_does_not_link_transient_only_task_as_asset(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / "tmp_orders_stage.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT order_id, amount
FROM demo.dwd_orders;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {
                "name": "tmp_orders_stage",
                "layer": "OTHER",
                "columns": [],
                "is_transient": True,
                "transient_sources": ["tmp_orders_stage.sql"],
            },
        ],
        None,
        project_dir,
        edges=[{
            "source_file": "tmp_orders_stage.sql",
            "target": "demo.tmp_orders_stage.order_id",
        }],
        indirect_edges=[],
        transient_tables=[
            {
                "name": "tmp_orders_stage",
                "source_file": "tmp_orders_stage.sql",
                "created_statement_index": 0,
                "dropped_statement_index": 1,
                "is_ctas": True,
                "is_transient": True,
                "dropped_in_same_task": True,
            }
        ],
    )

    assert catalog["tasks"][0]["output_tables"] == set()
    assert "tmp_orders_stage" not in catalog["tables"]


def _write_simple_table_assets(project_dir, table_names):
    (project_dir / "ddl").mkdir(parents=True, exist_ok=True)
    (project_dir / "models").mkdir(exist_ok=True)
    for table_name in table_names:
        (project_dir / "ddl" / f"{table_name}.sql").write_text(
            f"""
CREATE TABLE demo.{table_name} (
    id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1;
""",
            encoding="utf-8",
        )
        (project_dir / "models" / f"{table_name}.yaml").write_text(
            f"name: {table_name}\nlayer: DWS\n",
            encoding="utf-8",
        )


def test_score_asset_completeness_flags_task_with_no_persistent_output(
        tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / "tmp_orders_stage.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT id
FROM demo.dwd_orders;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    result = score_asset_completeness(catalog)

    assert "ASSET_TASK_SINGLE_OUTPUT" in _issue_rule_ids(result)
    task_output_check = _checks_by_rule(
        result,
        "ASSET_TASK_SINGLE_OUTPUT",
    )[0]
    assert task_output_check["target"]["name"] == "tasks/tmp_orders_stage.sql"
    assert task_output_check["actual"] == "实际产出=[]"


def test_score_asset_completeness_flags_task_with_multiple_outputs(tmp_path):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders", "dws_order_extra"])
    (project_dir / "tasks").mkdir(exist_ok=True)
    (project_dir / "tasks" / "dws_orders.sql").write_text(
        """
INSERT INTO demo.dws_orders SELECT 1 AS id;
INSERT INTO demo.dws_order_extra SELECT 1 AS id;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {"name": "dws_orders", "layer": "DWS", "columns": []},
            {"name": "dws_order_extra", "layer": "DWS", "columns": []},
        ],
        {
            "dws_orders": {"name": "dws_orders", "layer": "DWS"},
            "dws_order_extra": {"name": "dws_order_extra", "layer": "DWS"},
        },
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {"source_file": "dws_orders.sql", "target": "dws_order_extra.id"},
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(catalog)

    assert _issue_rule_ids(result) == {"ASSET_TASK_SINGLE_OUTPUT"}
    task_output_check = _checks_by_rule(
        result,
        "ASSET_TASK_SINGLE_OUTPUT",
    )[0]
    assert task_output_check["target"]["name"] == "tasks/dws_orders.sql"
    assert task_output_check["actual"] == (
        "实际产出=['dws_order_extra', 'dws_orders']"
    )


def test_score_asset_completeness_flags_duplicate_table_writers(tmp_path):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders"])
    (project_dir / "tasks").mkdir(exist_ok=True)
    (project_dir / "tasks" / "dws_orders.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )
    (project_dir / "tasks" / "dws_orders_patch.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 2 AS id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [{"name": "dws_orders", "layer": "DWS", "columns": []}],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {"source_file": "dws_orders_patch.sql", "target": "dws_orders.id"},
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(catalog)

    assert _issue_rule_ids(result) == {"ASSET_TABLE_SINGLE_WRITER"}
    writer_check = _checks_by_rule(
        result,
        "ASSET_TABLE_SINGLE_WRITER",
    )[0]
    assert writer_check["target"]["name"] == "dws_orders"
    assert writer_check["actual"] == (
        "产出Task=['tasks/dws_orders.sql', 'tasks/dws_orders_patch.sql']"
    )


def test_score_asset_completeness_allows_full_refresh_companion_writer(
        tmp_path):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders"])
    (project_dir / "tasks" / "full_refresh").mkdir(parents=True)
    (project_dir / "tasks" / "dws_orders.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )
    (
        project_dir / "tasks" / "full_refresh" /
        "dws_orders_full_refresh.sql"
    ).write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [{"name": "dws_orders", "layer": "DWS", "columns": []}],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {
                "source_file": "full_refresh/dws_orders_full_refresh.sql",
                "target": "dws_orders.id",
            },
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(catalog)

    assert result["issues"] == []


def test_score_naming_conventions_outputs_table_and_column_issues():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")

    result = score_naming_conventions(
        [{
            "name": "dwd_customer",
            "layer": "DWD",
            "columns": [{"name": "customer_id"}],
        }],
        nc,
    )

    assert result["score"] == 33.3
    assert _issue_rule_ids(result) == {
        "NAMING_TABLE_TEMPLATE",
        "NAMING_COLUMN_NAME",
    }
    assert result["issues"][0]["remediation"]["strategy"] == (
        "rename_table_and_rewrite_references"
    )
    column_check = _checks_by_rule(result, "NAMING_COLUMN_NAME")[0]
    assert column_check["actual"] == "不合规字段: ['customer_id']"


def test_score_naming_conventions_does_not_expose_internal_violation_text():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")

    result = score_naming_conventions(
        [{
            "name": "dwd_customer_name_that_is_too_long",
            "layer": "DWD",
            "columns": [],
        }],
        nc,
    )

    assert {
        issue["rule_id"]
        for issue in result["issues"]
    } == {
        "NAMING_TABLE_TEMPLATE",
        "NAMING_TABLE_MAX_LENGTH",
    }
    rendered_checks = yaml.safe_dump(
        result["checks"],
        allow_unicode=True,
        sort_keys=True,
    )
    assert "违反:" not in rendered_checks


def test_score_naming_conventions_issues_include_related_files(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()

    table_name = "dwd_customer"
    (project_dir / "ddl" / f"{table_name}.sql").write_text(
        f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    customer_id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )
    (project_dir / "models" / f"{table_name}.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n",
        encoding="utf-8",
    )
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS customer_id;",
        encoding="utf-8",
    )

    result = score_naming_conventions(
        [],
        nc,
        {table_name: {"layer": "DWD"}},
        project_dir=project_dir,
    )

    column_issue = next(
        issue for issue in result["issues"]
        if issue["rule_id"] == "NAMING_COLUMN_NAME"
    )
    assert column_issue["remediation"]["related_files"] == [
        "demo/ddl/dwd_customer.sql",
        "demo/tasks/dwd_customer.sql",
        "demo/models/dwd_customer.yaml",
    ]


def test_naming_checks_business_segments_against_valid_model_metadata(tmp_path):
    nc = _business_naming_config(tmp_path)
    result = score_naming_conventions(
        [{
            "name": "M_PAYM_04_CHREM_DI",
            "layer": "DWD",
            "columns": [],
        }],
        nc,
        {
            "M_PAYM_04_CHREM_DI": {
                "layer": "DWD",
                "data_domain": "10",
                "business_area": "CLNT",
            },
        },
        nc.business_domain_config,
    )

    semantic_check = _checks_by_rule(
        result,
        "NAMING_SEMANTIC_METADATA_ALIGNMENT",
    )[0]
    assert semantic_check["passed"] is False
    assert "model.data_domain=10" in semantic_check["actual"]
    assert "model.business_area=CLNT" in semantic_check["actual"]


def test_score_naming_conventions_checks_project_file_names(tmp_path):
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

    result = score_naming_conventions(
        [{"name": table_name, "layer": "DWD", "columns": []}],
        nc,
        {table_name: {"layer": "DWD"}},
        project_dir=project_dir,
        edges=[{
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": "wrong_task.sql",
        }],
        indirect_edges=[],
    )

    assert _issue_rule_ids(result) == {
        "NAMING_DDL_FILE_NAME",
        "NAMING_MODEL_FILE_NAME",
        "NAMING_TASK_OUTPUT_NAME",
    }
    assert all(issue["severity"] == "低" for issue in result["issues"])


def test_score_naming_conventions_checks_atomic_and_derived_metrics():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    result = score_naming_conventions(
        [{
            "name": "M_WEMG_04_CHREM_DI",
            "layer": "DWD",
            "columns": [],
        }],
        nc,
        {
            "M_WEMG_04_CHREM_DI": {
                "atomic_metrics": ["PAY_AMT", "pay_amt"],
                "derived_metrics": ["7D_OLD_PAY_AMT", "transaction_count"],
            }
        },
    )

    assert result["rule_summary"]["NAMING_ATOMIC_METRIC"]["pass_count"] == 1
    assert result["rule_summary"]["NAMING_DERIVED_METRIC"]["pass_count"] == 1
    assert _issue_rule_ids(result) == {
        "NAMING_ATOMIC_METRIC",
        "NAMING_DERIVED_METRIC",
    }


def test_score_naming_conventions_checks_dws_and_dim_entity_alignment():
    nc = load_naming_config(PROJECT_ROOT / "shop/naming_config.yaml")

    dws_result = score_naming_conventions(
        [{
            "name": "I_SHOP_CAT_SALE_DS",
            "layer": "DWS",
            "columns": [
                {"name": "category_id"},
                {"name": "stat_date"},
            ],
        }],
        nc,
        {
            "I_SHOP_CAT_SALE_DS": {
                "grain": {
                    "keys": ["category_id", "stat_date"],
                    "entities": ["PROD"],
                    "time_column": "stat_date",
                    "time_period": "D",
                }
            }
        },
    )
    assert "NAMING_DWS_ENTITY_ALIGNMENT" in _issue_rule_ids(dws_result)

    dim_result = score_naming_conventions(
        [{"name": "DIM_BASE_PROD_INFO_INFO", "layer": "DIM", "columns": []}],
        nc,
        {
            "DIM_BASE_PROD_INFO_INFO": {
                "entity": {
                    "code": "CUST",
                    "key_columns": ["product_id"],
                }
            }
        },
    )
    assert "NAMING_DIM_ENTITY_ALIGNMENT" in _issue_rule_ids(dim_result)


def test_score_naming_conventions_ignores_lineage_tables_when_project_dir_exists(
        tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)

    result = score_naming_conventions(
        [{
            "name": "M_WEMG_04_CHREM_DI",
            "layer": "DWD",
            "columns": [{"name": "BAD_FIELD"}],
        }],
        nc,
        project_dir=project_dir,
    )

    assert result["score"] == 100.0
    assert result["checks"] == []
    assert result["issues"] == []
