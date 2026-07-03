import json
import sys

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    build_dwd_contexts,
    build_inspection_contexts,
    build_metric_contexts,
    business_metadata_for_result,
    metric_groups_for_model,
    metric_names_for_model,
    metric_violations,
    result_for_report,
    run_catalog_discovery,
    run_catalog_metadata_write,
    run_direct_model_generation,
    run_metadata_write,
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
)


def _business_domain_config():
    return BusinessDomainConfig(
        domains={
            "04": DomainDef(id="04", code="TRAN", name="交易域"),
            "06": DomainDef(id="06", code="ORGN", name="机构域"),
        },
        business_areas={
            "CHNL": BusinessAreaDef(id="09", code="CHNL", name="渠道业务"),
            "PAYM": BusinessAreaDef(id="04", code="PAYM", name="支付结算"),
        },
    )


def _configure_project_root(monkeypatch, project_root):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    monkeypatch.setattr(config.core, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


@pytest.fixture
def isolated_writer_project(tmp_path, monkeypatch):
    project = "unit_writer"
    project_dir = tmp_path / project
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir(parents=True)
    for table_name, layer in [
        ("dwd_customer", "DWD"),
        ("dwd_order_detail", "DWD"),
        ("dws_store_sales_daily", "DWS"),
        ("ads_sales_dashboard", "ADS"),
        ("dim_store", "DIM"),
    ]:
        (models_dir / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    yield project
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


def _sample_fact_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["订单明细事实表"],
        columns={
            "atomic_metrics": [
                {
                    "name": "pay_amt",
                    "data_type": "DECIMAL(12,2)",
                    "business_process": "订单支付",
                    "action": "pay",
                    "measure": "amt",
                    "description": "支付金额",
                    "reason": "基础支付金额",
                    "confidence": 0.95,
                }
            ],
            "derived_metrics": [
                {
                    "name": "pay_amt_1d",
                    "data_type": "DECIMAL(12,2)",
                    "base_metric": "pay_amt",
                    "base_metric_table": "dwd_order_detail",
                    "modifiers": [],
                    "time_period": "1d",
                    "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
                    "description": "近 1 日支付金额",
                    "reason": "原子指标加时间周期限定",
                    "confidence": 0.86,
                }
            ],
            "calculated_metrics": [
                {
                    "name": "gross_profit",
                    "data_type": "DECIMAL(12,2)",
                    "expression": "subtotal - cost_price * quantity",
                    "derived_from": ["subtotal", "cost_price", "quantity"],
                    "description": "毛利",
                    "reason": "多字段计算得到",
                    "confidence": 0.88,
                }
            ],
            "dimensions": [
                {
                    "name": "order_id",
                    "dimension_type": "primary_key",
                    "data_type": "BIGINT",
                    "confidence": 0.9,
                }
            ],
            "others": [
                {
                    "name": "etl_time",
                    "role": "audit",
                    "data_type": "DATETIME",
                    "confidence": 0.9,
                }
            ],
        },
    )


def _sample_dws_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="dws_store_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["门店日销售汇总事实表"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "data_type": "DECIMAL(14,2)",
                    "base_metric": "subtotal",
                    "base_metric_table": "dwd_order_detail",
                    "modifiers": ["store"],
                    "time_period": "1d",
                    "expression": "SUM(subtotal) GROUP BY store_id, order_date",
                    "description": "门店日销售金额",
                    "reason": "原子指标按门店和日期汇总",
                    "confidence": 0.9,
                }
            ],
            "calculated_metrics": [],
            "dimensions": [
                {
                    "name": "store_id",
                    "dimension_type": "foreign_key",
                    "data_type": "BIGINT",
                    "confidence": 0.9,
                }
            ],
            "others": [],
        },
    )


def _sample_dimension_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="M_SHOP_06_STORE_DF",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.93,
        reasoning_steps=["门店实体属性快照，适合作为公共维度"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [
                {
                    "name": "STORE_ID",
                    "dimension_type": "primary_key",
                    "data_type": "BIGINT",
                    "confidence": 0.95,
                }
            ],
            "others": [],
        },
    )


def _sample_dimension_conflict_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="M_SHOP_06_STORE_DF",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="dimension",
        confidence=0.88,
        reasoning_steps=["表类型是维度表，但分层判断仍返回 DWD"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )


def _expected_pay_amt_1d_metric() -> dict:
    return {
        "name": "pay_amt_1d",
        "base_metric": "pay_amt",
        "base_metric_table": "dwd_order_detail",
        "aggregation": "SUM",
        "time_period": "D",
        "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
    }


def _run_isolated_writer_helper(tmp_path_factory, monkeypatch, helper):
    with monkeypatch.context() as isolated_monkeypatch:
        tmp_path = tmp_path_factory.mktemp(
            helper.__name__.replace("_assert_", "")
        )
        helper(tmp_path, isolated_monkeypatch)


def test_update_model_yaml_table_metadata_scenarios(
    tmp_path_factory, monkeypatch
):
    helpers = [
        _assert_update_model_yaml_preserves_existing_metadata,
        _assert_update_model_yaml_defaults_to_declared_layer,
        _assert_update_model_yaml_writes_llm_table_metadata,
        _assert_update_model_yaml_writes_dimension_classification_metadata,
        _assert_update_model_yaml_removes_stale_dimension_classification_for_fact,
        _assert_update_model_yaml_keeps_existing_applicable_business_metadata,
        _assert_update_model_yaml_forces_dimension_layer_and_warns,
        _assert_update_model_yaml_dry_run_reports_metadata_change,
    ]

    for helper in helpers:
        _run_isolated_writer_helper(tmp_path_factory, monkeypatch, helper)


def test_update_model_yaml_write_scope_and_metric_scenarios(
    tmp_path_factory, monkeypatch
):
    helpers = [
        _assert_update_model_yaml_table_scope_preserves_metrics,
        _assert_update_model_yaml_metrics_scope_preserves_table_info,
        _assert_update_model_yaml_metrics_scope_does_not_create_empty_model,
        _assert_update_model_yaml_replaces_existing_metrics,
        _assert_update_model_yaml_replaces_legacy_metric_fields,
        _assert_update_model_yaml_removes_metrics_when_none_detected,
        _assert_update_model_yaml_preserves_metrics_when_dws_metrics_missing,
        _assert_update_model_yaml_skips_blocked_results,
    ]

    for helper in helpers:
        _run_isolated_writer_helper(tmp_path_factory, monkeypatch, helper)


def test_update_model_yaml_grain_entity_scenarios(
    tmp_path_factory, monkeypatch
):
    helpers = [
        _assert_update_model_yaml_grain_scope_writes_dws_grain_only,
        _assert_update_model_yaml_normalizes_time_period_aliases,
        _assert_update_model_yaml_grain_scope_keeps_full_dws_grain_entities,
        _assert_update_model_yaml_grain_scope_writes_dimension_entity_only,
        _assert_update_model_yaml_grain_scope_removes_placeholder_empty_grain,
        _assert_update_model_yaml_grain_scope_writes_dimension_related_entities,
        _assert_update_model_yaml_grain_scope_migrates_legacy_entity_fields,
        _assert_update_model_yaml_grain_scope_migrates_existing_legacy_without_result,
        _assert_update_model_yaml_grain_scope_canonicalizes_llm_entities,
        _assert_update_model_yaml_preserves_dwd_fact_primary_entity,
        _assert_update_model_yaml_grain_scope_treats_declared_dim_as_primary,
        _assert_update_model_yaml_grain_scope_migrates_blocked_existing_metadata,
        _assert_update_models_for_results_allows_blocked_schema_migration,
        _assert_blocked_schema_migration_keeps_grain_entities_consistent,
    ]

    for helper in helpers:
        _run_isolated_writer_helper(tmp_path_factory, monkeypatch, helper)


def test_build_inspection_context_scope_scenarios(
    sample_lineage_data, isolated_writer_project
):
    dwd_contexts = build_dwd_contexts(
        isolated_writer_project, sample_lineage_data
    )

    assert {ctx.table_name for ctx in dwd_contexts} == {
        "dwd_customer",
        "dwd_order_detail",
    }

    metric_contexts = build_metric_contexts(
        isolated_writer_project, sample_lineage_data
    )
    assert {ctx.table_name for ctx in metric_contexts} == {
        "dwd_customer",
        "dwd_order_detail",
        "dws_store_sales_daily",
    }

    data = dict(sample_lineage_data)
    data["tables"] = sample_lineage_data["tables"] + [
        {
            "name": "dim_store",
            "full_name": "shop_dm.dim_store",
            "layer": "DIM",
            "columns": [{"name": "store_id", "type": "BIGINT"}],
        }
    ]

    contexts = build_inspection_contexts(isolated_writer_project, data)

    assert {ctx.table_name for ctx in contexts} == {
        "dwd_customer",
        "dwd_order_detail",
        "dws_store_sales_daily",
        "dim_store",
    }


def test_metric_helper_scenarios():
    metrics = metric_names_for_model(_sample_fact_result())

    assert metrics == ["pay_amt", "pay_amt_1d", "gross_profit"]

    metric_groups = metric_groups_for_model(_sample_fact_result())

    assert metric_groups == {
        "atomic_metrics": ["pay_amt"],
        "derived_metrics": [_expected_pay_amt_1d_metric()],
        "calculated_metrics": ["gross_profit"],
    }

    violations = metric_violations(_sample_fact_result())

    assert violations == [
        {
            "table": "dwd_order_detail",
            "column": "pay_amt_1d",
            "metric_type": "derived",
            "reason": "原子指标加时间周期限定",
            "confidence": 0.86,
        },
        {
            "table": "dwd_order_detail",
            "column": "gross_profit",
            "metric_type": "calculated",
            "reason": "多字段计算得到",
            "confidence": 0.88,
        },
    ]

    result = TableInspectResult(
        table_name="dwd_customer",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [{"name": "age_group"}],
            "dimensions": [],
            "others": [],
        },
    )

    assert metric_violations(result) == []
    assert metric_violations(_sample_dws_result()) == []


def _assert_update_model_yaml_preserves_existing_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "description": "订单明细事实表",
                "config": {
                    "materialized": "incremental",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 3
    assert update["new_metric_count"] == 3
    assert saved["description"] == "订单明细事实表"
    assert saved["config"]["materialized"] == "incremental"
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == [_expected_pay_amt_1d_metric()]
    assert saved["calculated_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def _assert_update_model_yaml_defaults_to_declared_layer(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    (project_root / "demo" / "mid" / "models").mkdir(parents=True)
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_dws_result())
    model_path = (
        project_root / "demo" / "mid" / "models" / "dws_store_sales_daily.yaml"
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 1
    assert saved["layer"] == "DWS"
    assert saved["table_type"] == "fact"
    assert saved["derived_metrics"] == [
        {
            "name": "sale_amount",
            "base_metric": "subtotal",
            "base_metric_table": "dwd_order_detail",
            "aggregation": "SUM",
            "time_period": "D",
            "expression": "SUM(subtotal) GROUP BY store_id, order_date",
        }
    ]
    assert "atomic_metrics" not in saved


def _assert_update_model_yaml_writes_llm_table_metadata(tmp_path, monkeypatch):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "M_SHOP_06_STORE_DF.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "M_SHOP_06_STORE_DF",
                "layer": "DWD",
                "data_domain": "06",
                "business_area": "CHNL",
                "description": "门店每日快照",
                "config": {
                    "materialized": "snapshot",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    monkeypatch.setattr(
        writer_module,
        "get_business_domain_config",
        lambda project: _business_domain_config(),
    )

    update = update_model_yaml("demo", _sample_dimension_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["changed"] is True
    assert update["updated"] is True
    assert update["metadata_changed"] is True
    assert update["previous_layer"] == "DWD"
    assert update["layer"] == "DIM"
    assert update["previous_table_type"] is None
    assert update["table_type"] == "dimension"
    assert saved["layer"] == "DIM"
    assert saved["table_type"] == "dimension"
    assert "data_domain" not in saved
    assert "business_area" not in saved
    assert saved["description"] == "门店每日快照"
    assert saved["config"]["materialized"] == "snapshot"
    assert "atomic_metrics" not in saved


def _assert_update_model_yaml_writes_dimension_classification_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "DIM_BASE_STORE_INFO.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "DIM_BASE_STORE_INFO",
                "layer": "DIM",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="DIM_BASE_STORE_INFO",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        dimension_role="BASE",
        dimension_content_type="INFO",
        confidence=0.92,
        reasoning_steps=["门店主维度属性信息"],
    )

    update = update_model_yaml("demo", result)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["dimension_role"] == "BASE"
    assert update["dimension_content_type"] == "INFO"
    assert update["metadata_changed"] is True
    assert saved["dimension_role"] == "BASE"
    assert saved["dimension_content_type"] == "INFO"


def _assert_update_model_yaml_removes_stale_dimension_classification_for_fact(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "M_SHOP_04_ORDER_DI.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "M_SHOP_04_ORDER_DI",
                "layer": "DIM",
                "table_type": "dimension",
                "dimension_role": "BASE",
                "dimension_content_type": "INFO",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="M_SHOP_04_ORDER_DI",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["订单明细事实表"],
    )

    update = update_model_yaml("demo", result)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["layer"] == "DWD"
    assert update["dimension_role"] is None
    assert update["dimension_content_type"] is None
    assert "dimension_role" not in saved
    assert "dimension_content_type" not in saved


def test_business_metadata_for_result_limits_fields_by_layer(monkeypatch):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    monkeypatch.setattr(
        writer_module,
        "get_business_domain_config",
        lambda project: _business_domain_config(),
    )
    dws_result = TableInspectResult(
        table_name="dws_transactions",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="04",
        inferred_business_area="PAYM",
    )
    dim_result = TableInspectResult(
        table_name="dim_location",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="06",
        inferred_business_area="CHNL",
    )

    assert business_metadata_for_result("demo", dws_result) == {
        "business_area": "PAYM",
    }
    assert business_metadata_for_result("demo", dim_result) == {}


def _assert_update_model_yaml_keeps_existing_applicable_business_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "PAYM",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    monkeypatch.setattr(
        writer_module,
        "get_business_domain_config",
        lambda project: _business_domain_config(),
    )
    result = TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
    )

    update = update_model_yaml("demo", result)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["data_domain"] == "04"
    assert update["business_area"] == "PAYM"
    assert saved["data_domain"] == "04"
    assert saved["business_area"] == "PAYM"


def _assert_update_model_yaml_forces_dimension_layer_and_warns(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "M_SHOP_06_STORE_DF.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "M_SHOP_06_STORE_DF",
                "layer": "DWD",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_dimension_conflict_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["layer"] == "DIM"
    assert saved["layer"] == "DIM"
    assert update["warnings"] == [
        {
            "type": "dimension_layer_override",
            "severity": "warning",
            "message": (
                "LLM 表类型为 dimension，但 inferred_layer 不是 DIM；"
                "表信息回写时 layer 会按 dimension 规则强制写为 DIM"
            ),
            "inferred_layer": "DWD",
            "applied_layer": "DIM",
        }
    ]


def test_result_for_report_includes_dimension_layer_warning():
    report = result_for_report(_sample_dimension_conflict_result())

    assert report["metadata_warnings"][0]["type"] == "dimension_layer_override"
    assert report["metadata_warnings"][0]["inferred_layer"] == "DWD"


def _assert_update_model_yaml_dry_run_reports_metadata_change(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "M_SHOP_06_STORE_DF.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "M_SHOP_06_STORE_DF",
                "layer": "DWD",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo", _sample_dimension_result(), dry_run=True
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["changed"] is True
    assert update["updated"] is False
    assert update["metadata_changed"] is True
    assert saved["layer"] == "DWD"
    assert "table_type" not in saved


def _assert_update_model_yaml_table_scope_preserves_metrics(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "metrics": ["legacy_metric"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo", _sample_fact_result(), write_scope="table"
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["write_scope"] == "table"
    assert update["metadata_changed"] is True
    assert update["metric_changed"] is False
    assert update["metric_count"] == 0
    assert update["new_metric_count"] == 0
    assert update["removed_metric_count"] == 0
    assert saved["layer"] == "DWD"
    assert saved["table_type"] == "fact"
    assert saved["metrics"] == ["legacy_metric"]
    assert "atomic_metrics" not in saved


def _assert_update_model_yaml_metrics_scope_preserves_table_info(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "OLD_LAYER",
                "table_type": "dimension",
                "metrics": ["legacy_metric"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo", _sample_fact_result(), write_scope="metrics"
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["write_scope"] == "metrics"
    assert update["metadata_changed"] is False
    assert update["metric_changed"] is True
    assert update["metric_count"] == 3
    assert update["new_metric_count"] == 3
    assert update["removed_metric_count"] == 1
    assert saved["layer"] == "OLD_LAYER"
    assert saved["table_type"] == "dimension"
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == [_expected_pay_amt_1d_metric()]
    assert saved["calculated_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def _assert_update_model_yaml_metrics_scope_does_not_create_empty_model(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    (project_root / "demo" / "mid" / "models").mkdir(parents=True)
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo", _sample_dimension_result(), write_scope="metrics"
    )
    model_path = (
        project_root / "demo" / "mid" / "models" / "M_SHOP_06_STORE_DF.yaml"
    )

    assert update["changed"] is False
    assert update["updated"] is False
    assert update["metric_count"] == 0
    assert not model_path.exists()


def _assert_update_model_yaml_grain_scope_writes_dws_grain_only(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_product_sales_daily.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_product_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "derived_metrics": ["sale_quantity"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dws_product_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "PROD",
                "type": "foreign",
                "key_columns": ["product_id"],
            }
        ],
        grain={
            "entities": ["PROD"],
            "time_column": "stat_date",
            "time_period": "D",
        },
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["write_scope"] == "grain"
    assert update["grain_changed"] is True
    assert update["metadata_changed"] is False
    assert update["metric_changed"] is False
    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "foreign",
            "key_columns": ["product_id"],
        }
    ]
    assert saved["grain"] == {
        "entities": ["PROD"],
        "time_column": "stat_date",
        "time_period": "D",
    }
    assert saved["layer"] == "DWS"
    assert saved["table_type"] == "fact"
    assert saved["derived_metrics"] == ["sale_quantity"]


def _assert_update_model_yaml_normalizes_time_period_aliases(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_category_sales_monthly.yaml"
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dws_category_sales_monthly",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "base_metric": "subtotal",
                    "base_metric_table": "dwd_order_detail",
                    "time_period": "月",
                    "expression": "SUM(subtotal)",
                }
            ],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
        entities=[
            {
                "code": "PROD",
                "type": "foreign",
                "key_columns": ["category_id"],
            }
        ],
        grain={
            "entities": ["PROD"],
            "time_column": "stat_month_date",
            "time_period": "月",
        },
    )

    update_model_yaml("demo", result, write_scope="all")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["derived_metrics"][0]["time_period"] == "M"
    assert saved["grain"]["time_period"] == "M"


def _assert_update_model_yaml_grain_scope_keeps_full_dws_grain_entities(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_product_store_sales_daily.yaml"
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dws_product_store_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        grain={
            "keys": ["product_id", "store_id", "customer_id", "stat_date"],
            "entities": ["prod", "STORE", "CUST", "STORE"],
            "time_column": "stat_date",
            "time_period": "D",
        },
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["grain_changed"] is True
    assert saved["entities"] == [
        {
            "code": "prod",
            "type": "foreign",
            "key_columns": ["product_id"],
        },
        {
            "code": "STORE",
            "type": "foreign",
            "key_columns": ["store_id"],
        },
        {
            "code": "CUST",
            "type": "foreign",
            "key_columns": ["customer_id"],
        },
    ]
    assert saved["grain"] == {
        "entities": ["prod", "STORE", "CUST", "STORE"],
        "time_column": "stat_date",
        "time_period": "D",
    }


def _assert_update_model_yaml_grain_scope_writes_dimension_entity_only(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_product.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_product",
                "layer": "DWD",
                "table_type": "dimension",
                "data_domain": "02",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dwd_product",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entity={
            "code": "PROD",
            "key_columns": ["product_id"],
        },
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["write_scope"] == "grain"
    assert update["grain_changed"] is True
    assert update["metadata_changed"] is False
    assert update["metric_changed"] is False
    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "primary",
            "key_columns": ["product_id"],
        }
    ]
    assert "entity" not in saved
    assert saved["layer"] == "DWD"
    assert saved["table_type"] == "dimension"
    assert saved["data_domain"] == "02"


def _assert_update_model_yaml_grain_scope_removes_placeholder_empty_grain(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_customers.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_customers",
                "layer": "DWD",
                "table_type": "dimension",
                "entity": {
                    "code": "CUST",
                    "key_columns": ["customer_id"],
                },
                "grain": {
                    "keys": [],
                    "entities": [],
                    "time_column": "",
                    "time_period": "",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dwd_customers",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entity={
            "code": "CUST",
            "key_columns": ["customer_id"],
        },
        grain={
            "keys": [],
            "entities": [],
            "time_column": "",
            "time_period": "",
        },
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["grain_changed"] is True
    assert "grain" not in saved


def _assert_update_model_yaml_grain_scope_writes_dimension_related_entities(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_product.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_product",
                "layer": "DWD",
                "table_type": "dimension",
                "entity": {
                    "code": "PROD",
                    "key_columns": ["product_id"],
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dwd_product",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entity={
            "code": "PROD",
            "key_columns": ["product_id"],
        },
        related_entities=[
            {
                "code": "CAT",
                "name": "品类",
                "key_columns": ["category_id"],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": "PROD",
                },
            }
        ],
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["grain_changed"] is True
    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "primary",
            "key_columns": ["product_id"],
        },
        {
            "code": "CAT",
            "type": "foreign",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PROD",
            },
        },
    ]
    assert "entity" not in saved
    assert "related_entities" not in saved
    assert saved["layer"] == "DWD"
    assert saved["table_type"] == "dimension"


def _assert_update_model_yaml_grain_scope_migrates_legacy_entity_fields(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_product.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_product",
                "layer": "DWD",
                "table_type": "dimension",
                "entity": {
                    "code": "PROD",
                    "key_columns": ["product_id"],
                },
                "related_entities": [
                    {
                        "code": "CAT",
                        "name": "品类",
                        "key_columns": ["category_id"],
                        "relationship": {
                            "type": "many_to_one",
                            "from_entity": "PROD",
                        },
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dwd_product",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entity={
            "code": "PROD",
            "key_columns": ["product_id"],
        },
        related_entities=[
            {
                "code": "CAT",
                "name": "品类",
                "key_columns": ["category_id"],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": "PROD",
                },
            }
        ],
    )

    update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "primary",
            "key_columns": ["product_id"],
        },
        {
            "code": "CAT",
            "type": "foreign",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PROD",
            },
        },
    ]
    assert "entity" not in saved
    assert "related_entities" not in saved


def _assert_update_model_yaml_grain_scope_migrates_existing_legacy_without_result(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dim_indicator.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dim_indicator",
                "layer": "DIM",
                "table_type": "dimension",
                "entity": {
                    "code": "ECON",
                    "key_columns": ["date"],
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dim_indicator",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["grain_changed"] is True
    assert saved["entities"] == [
        {
            "code": "ECON",
            "type": "primary",
            "key_columns": ["date"],
        }
    ]
    assert "entity" not in saved


def _assert_update_model_yaml_grain_scope_canonicalizes_llm_entities(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_product_sales_daily.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_product_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dws_product_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "PROD",
                "type": "natural",
                "name": "商品",
                "key_columns": ["product_id"],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": "PROD",
                },
            },
            {
                "code": "PROD",
                "type": "foreign",
                "name": "商品",
                "key_columns": ["product_id"],
            },
        ],
        grain={
            "entities": ["PROD"],
            "time_column": "stat_date",
            "time_period": "D",
        },
    )

    update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "foreign",
            "name": "商品",
            "key_columns": ["product_id"],
        }
    ]


def _assert_update_model_yaml_preserves_dwd_fact_primary_entity(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "ORDER_ITEM",
                "type": "primary",
                "name": "订单明细",
                "key_columns": ["order_id", "order_item_id", "order_date"],
            },
            {
                "code": "CUST",
                "type": "foreign",
                "name": "客户",
                "key_columns": ["customer_id"],
            },
        ],
    )

    update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["entities"] == [
        {
            "code": "ORDER_ITEM",
            "type": "primary",
            "name": "订单明细",
            "key_columns": ["order_id", "order_item_id", "order_date"],
        },
        {
            "code": "CUST",
            "type": "foreign",
            "name": "客户",
            "key_columns": ["customer_id"],
        },
    ]


def _assert_update_model_yaml_grain_scope_treats_declared_dim_as_primary(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dim_agent.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dim_agent",
                "layer": "DIM",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dim_agent",
        declared_layer="DIM",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "AGENT",
                "type": "foreign",
                "key_columns": ["agent_natural_key"],
            }
        ],
    )

    update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["entities"] == [
        {
            "code": "AGENT",
            "type": "primary",
            "key_columns": ["agent_natural_key"],
        }
    ]


def _assert_update_model_yaml_grain_scope_migrates_blocked_existing_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_marketing_campaigns.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_marketing_campaigns",
                "layer": "DWS",
                "table_type": "fact",
                "grain": {
                    "keys": ["campaign_key"],
                    "entities": ["CAMP"],
                    "time_column": "start_date",
                    "time_period": "D",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    result = TableInspectResult(
        table_name="dws_marketing_campaigns",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        validation={
            "unknown_columns": ["ghost_col"],
        },
        grain={
            "keys": ["campaign_key"],
            "entities": ["CAMP"],
            "time_column": "start_date",
            "time_period": "D",
        },
    )

    update = update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result.status == "blocked"
    assert update["updated"] is True
    assert update["reason"] == "validation_blocked_schema_migration"
    assert saved["grain"] == {
        "entities": ["CAMP"],
        "time_column": "start_date",
        "time_period": "D",
    }
    assert saved["entities"] == [
        {
            "code": "CAMP",
            "type": "foreign",
            "key_columns": ["campaign_key"],
        }
    ]


def _assert_update_models_for_results_allows_blocked_schema_migration(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_marketing_campaigns.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_marketing_campaigns",
                "layer": "DWS",
                "table_type": "fact",
                "grain": {
                    "keys": ["campaign_key"],
                    "entities": ["CAMP"],
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    blocked = TableInspectResult(
        table_name="dws_marketing_campaigns",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        validation={
            "unknown_columns": ["ghost_col"],
        },
        grain={
            "keys": ["campaign_key"],
            "entities": ["CAMP"],
        },
    )

    yaml_updates, skipped_updates = writer_module._update_models_for_results(
        "demo",
        [blocked],
        dry_run=False,
        write_scope="grain",
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert len(yaml_updates) == 1
    assert skipped_updates == []
    assert saved["grain"] == {"entities": ["CAMP"]}
    assert saved["entities"] == [
        {
            "code": "CAMP",
            "type": "foreign",
            "key_columns": ["campaign_key"],
        }
    ]


def _assert_blocked_schema_migration_keeps_grain_entities_consistent(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_marketing_campaigns.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_marketing_campaigns",
                "layer": "DWS",
                "table_type": "fact",
                "grain": {
                    "entities": ["CAMP"],
                    "time_column": "start_date",
                    "time_period": "D",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    blocked = TableInspectResult(
        table_name="dws_marketing_campaigns",
        declared_layer="DWS",
        inferred_layer="ADS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "CAMPAIGN",
                "type": "natural",
                "key_columns": ["campaign_key"],
            }
        ],
        validation={
            "duplicate_columns": ["campaign_id"],
        },
    )

    update_model_yaml("demo", blocked, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["grain"]["entities"] == ["CAMPAIGN"]
    assert saved["entities"] == [
        {
            "code": "CAMPAIGN",
            "type": "foreign",
            "key_columns": ["campaign_key"],
        }
    ]


def _assert_update_model_yaml_replaces_existing_metrics(tmp_path, monkeypatch):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "metrics": ["existing_metric", "pay_amt"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 3
    assert update["new_metric_count"] == 2
    assert update["removed_metric_count"] == 1
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == [_expected_pay_amt_1d_metric()]
    assert saved["calculated_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def _assert_update_model_yaml_replaces_legacy_metric_fields(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "atomic_metrics": [{"name": "legacy_atomic"}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 3
    assert update["new_metric_count"] == 3
    assert update["removed_metric_count"] == 1
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == [_expected_pay_amt_1d_metric()]
    assert saved["calculated_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def _assert_update_model_yaml_removes_metrics_when_none_detected(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_accounts.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_accounts",
                "layer": "DWD",
                "metrics": ["current_balance"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo",
        TableInspectResult(
            table_name="dwd_accounts",
            declared_layer="DWD",
            inferred_layer="DWD",
            table_type="dimension",
            confidence=0.9,
            reasoning_steps=[],
        ),
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 0
    assert update["removed_metric_count"] == 1
    assert update["updated"] is True
    assert update["layer"] == "DIM"
    assert update["warnings"][0]["type"] == "dimension_layer_override"
    assert saved["layer"] == "DIM"
    assert "metrics" not in saved
    assert "calculated_metrics" not in saved


def _assert_update_model_yaml_preserves_metrics_when_dws_metrics_missing(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dws_sales_daily.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "atomic_metrics": ["sales_amt"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    sparse_result = TableInspectResult(
        table_name="dws_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["公共汇总事实表"],
        validation={
            "missing_metric_metadata": ["DWS fact必须至少返回一个指标字段"]
        },
    )
    update = update_model_yaml("demo", sparse_result)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 0
    assert update["removed_metric_count"] == 0
    assert update["metric_changed"] is False
    assert saved["atomic_metrics"] == ["sales_amt"]


def _assert_update_model_yaml_skips_blocked_results(tmp_path, monkeypatch):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "atomic_metrics": ["quantity"],
                "calculated_metrics": ["subtotal"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    blocked = TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="OTHER",
        table_type="other",
        confidence=0.0,
        reasoning_steps=["JSON 解析失败"],
    )
    update = update_model_yaml("demo", blocked)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["updated"] is False
    assert update["reason"] == "validation_blocked"
    assert saved["atomic_metrics"] == ["quantity"]
    assert saved["calculated_metrics"] == ["subtotal"]


def test_run_metadata_write_reuses_table_inspector(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    created_cache_files = []

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.api_key = api_key
            self.model = model
            self.cache_file = cache_file
            self.max_retries = max_retries
            self.parallelism = parallelism
            created_cache_files.append(cache_file)

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_order_detail":
                    results.append(_sample_fact_result())
                elif ctx.table_name == "dws_store_sales_daily":
                    results.append(_sample_dws_result())
                else:
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                        )
                    )
            return results

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True
    )

    updates_by_table = {
        update["table"]: update for update in result["model_updates"]
    }

    assert result["inspected_table_count"] == 3
    assert result["write_scope"] == "all"
    assert result["metric_table_count"] == 3
    assert result["metadata_only_table_count"] == 0
    assert result["dwd_table_count"] == 2
    assert result["dws_table_count"] == 1
    assert result["dim_table_count"] == 0
    assert result["fact_table_count"] == 2
    assert result["atomic_metric_count"] == 1
    assert result["derived_metric_count"] == 2
    assert result["calculated_metric_count"] == 1
    assert result["metric_count"] == 4
    assert result["derived_metric_violation_count"] == 1
    assert result["calculated_metric_violation_count"] == 1
    assert result["non_atomic_metric_violation_count"] == 2
    assert result["model_update_count"] == 0
    assert result["model_change_count"] == len(result["model_updates"])
    assert created_cache_files[0] == config.assess_cache_path(
        isolated_writer_project, "inspect.json"
    )
    assert updates_by_table["dwd_customer"]["layer"] == "DIM"
    assert updates_by_table["dwd_customer"]["table_type"] == "dimension"
    assert updates_by_table["dwd_customer"]["updated"] is False
    assert updates_by_table["dws_store_sales_daily"]["table"] == (
        "dws_store_sales_daily"
    )
    assert result["skipped_model_updates"] == []


def test_model_metadata_writer_cli_defaults_output_to_project_assess_dir(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    tool_dir = tmp_path / "tool_assess" / "llm"
    tool_dir.mkdir(parents=True)
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
        },
    )
    monkeypatch.setattr(
        writer_module,
        "__file__",
        str(tool_dir / "model_metadata_writer.py"),
    )
    monkeypatch.setattr(
        writer_module,
        "run_refresh_metadata",
        lambda *args, **kwargs: {
            "project": project,
            "source": "refresh",
            "inspected_table_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
            "catalog_update": {"changed": False},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "refresh",
        ],
    )

    writer_module.main()

    output_path = (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    )
    assert output_path.exists()
    assert not (tool_dir / f"model_metadata_result_{project}.json").exists()


@pytest.mark.parametrize(
    (
        "mode",
        "llm",
        "backend_name",
        "expected_kwargs",
    ),
    [
        (
            "generate",
            False,
            "run_direct_model_generation",
            {
                "write_scope": "all",
                "llm": False,
                "replace_existing_models": True,
                "update_catalog": True,
            },
        ),
        (
            "refresh",
            False,
            "run_refresh_metadata",
            {"llm": False, "write_scope": "business"},
        ),
        (
            "catalog",
            False,
            "run_catalog_metadata",
            {"llm": False},
        ),
        (
            "catalog",
            True,
            "run_catalog_metadata",
            {"llm": True, "api_key": "test-key"},
        ),
    ],
    ids=["generate", "refresh", "catalog", "catalog-llm"],
)
def test_model_metadata_writer_cli_modes_dispatch_to_expected_backend(
    monkeypatch,
    tmp_path,
    mode,
    llm,
    backend_name,
    expected_kwargs,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
    if llm:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    seen = {}

    def fake_backend(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        if backend_name == "run_direct_model_generation":
            return {
                "project": project,
                "source": "direct_generation",
                "write_scope": kwargs["write_scope"],
                "llm": kwargs["llm"],
                "replace_existing_models": kwargs["replace_existing_models"],
                "catalog_update": None,
                "planned_deleted_model_files": [],
                "deleted_model_files": [],
                "inspected_table_count": 0,
                "model_change_count": 0,
                "model_update_count": 0,
                "assigned_business_process_count": 0,
                "assigned_semantic_subject_count": 0,
                "table_inspector_layer_inference_count": 0,
                "table_inspector_layer_inference_attempt_count": 0,
                "table_inspector_layer_inference_candidate_count": 0,
                "warning_count": 0,
            }
        if backend_name == "run_refresh_metadata":
            return {
                "project": project,
                "source": "refresh",
                "write_scope": kwargs["write_scope"],
                "llm": kwargs["llm"],
                "catalog_update": {"changed": False},
                "inspected_table_count": 0,
                "model_change_count": 0,
                "model_update_count": 0,
            }
        return {
            "project": project,
            "source": "catalog",
            "path": str(project_dir / "business_semantics.yaml"),
            "changed": llm,
            "updated": llm,
            "llm": kwargs["llm"],
            "catalog": {
                "business_processes": [{"code": "ORDER"}] if llm else [],
                "semantic_subjects": [],
            },
        }

    argv = ["model_metadata_writer.py", "--project", project, "--mode", mode]
    if llm:
        argv.append("--llm")
    monkeypatch.setattr(writer_module, backend_name, fake_backend)
    monkeypatch.setattr(sys, "argv", argv)

    writer_module.main()

    assert seen["args"] == (project,)
    for key, value in expected_kwargs.items():
        assert seen["kwargs"][key] == value
    assert (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    ).exists()


def test_run_metadata_write_passes_parallelism(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    seen = {}

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            seen["parallelism"] = parallelism

        def inspect_batch(self, contexts):
            return []

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True, parallelism=4
    )

    assert seen["parallelism"] == 4


def test_run_metadata_write_counts_dimension_layer_warnings(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                )
                if ctx.table_name == "dwd_customer"
                else TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer=ctx.layer,
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True
    )
    customer_report = next(
        table
        for table in result["tables"]
        if table["table_name"] == "dwd_customer"
    )

    assert result["metadata_warning_count"] == 1
    assert result["warning_table_count"] == 1
    assert customer_report["metadata_warnings"][0]["applied_layer"] == "DIM"


def test_run_metadata_write_passes_dwd_metric_groups_to_dws(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    seen_dws_contexts = []

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            if contexts and contexts[0].layer == "DWS":
                seen_dws_contexts.extend(contexts)
                return [_sample_dws_result()]
            return [
                _sample_fact_result()
                if ctx.table_name == "dwd_order_detail"
                else TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DIM",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(isolated_writer_project, api_key="test", dry_run=True)

    assert seen_dws_contexts[0].upstream_metric_groups["dwd_order_detail"] == {
        "atomic_metrics": ["pay_amt"],
        "derived_metrics": [_expected_pay_amt_1d_metric()],
        "calculated_metrics": ["gross_profit"],
    }


def test_run_metadata_write_discovers_related_entity_from_dws_grain(
    monkeypatch, tmp_path, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_dir = tmp_path / isolated_writer_project
    models_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    models_dir.mkdir(exist_ok=True)
    ddl_dir.mkdir()
    (models_dir / "dwd_product.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_product",
                "layer": "DWD",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (models_dir / "dws_category_sales_monthly.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_category_sales_monthly",
                "layer": "DWS",
                "table_type": "fact",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "dwd_product.sql").write_text(
        """
        CREATE TABLE dwd_product (
            product_id BIGINT COMMENT '商品ID',
            category_id BIGINT COMMENT '品类ID'
        );
        """,
        encoding="utf-8",
    )
    (ddl_dir / "dws_category_sales_monthly.sql").write_text(
        """
        CREATE TABLE dws_category_sales_monthly (
            category_id BIGINT COMMENT '品类ID',
            stat_month_date DATE COMMENT '统计月份'
        );
        """,
        encoding="utf-8",
    )
    lineage_data = {
        "tables": [
            {
                "name": "dwd_product",
                "full_name": "demo.dwd_product",
                "layer": "DWD",
                "columns": [
                    {"name": "product_id", "type": "BIGINT"},
                    {"name": "category_id", "type": "BIGINT"},
                ],
            },
            {
                "name": "dws_category_sales_monthly",
                "full_name": "demo.dws_category_sales_monthly",
                "layer": "DWS",
                "columns": [
                    {"name": "category_id", "type": "BIGINT"},
                    {"name": "stat_month_date", "type": "DATE"},
                ],
            },
        ],
        "edges": [
            {
                "source": "dwd_product.category_id",
                "target": "dws_category_sales_monthly.category_id",
                "expression": "category_id",
                "source_file": "dws_category_sales_monthly.sql",
            }
        ],
        "indirect_edges": [],
    }

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_product":
                    results.append(
                        TableInspectResult(
                            table_name="dwd_product",
                            declared_layer="DWD",
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                            entity={
                                "code": "PROD",
                                "key_columns": ["product_id"],
                            },
                        )
                    )
                elif ctx.table_name == "dws_category_sales_monthly":
                    results.append(
                        TableInspectResult(
                            table_name="dws_category_sales_monthly",
                            declared_layer="DWS",
                            inferred_layer="DWS",
                            table_type="fact",
                            confidence=0.9,
                            reasoning_steps=[],
                            grain={
                                "keys": ["category_id", "stat_month_date"],
                                "entities": ["CAT"],
                                "time_column": "stat_month_date",
                                "time_period": "M",
                            },
                        )
                    )
            return results

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(
        isolated_writer_project, api_key="test", write_scope="grain"
    )

    saved = yaml.safe_load(
        (models_dir / "dwd_product.yaml").read_text(encoding="utf-8")
    )

    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "primary",
            "key_columns": ["product_id"],
        },
        {
            "code": "CAT",
            "type": "foreign",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PROD",
            },
        },
    ]


def test_run_metadata_write_skips_blocked_model_updates(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    blocked = _sample_fact_result()
    blocked.validation = {
        "unknown_columns": ["ghost_amt"],
        "duplicate_columns": [],
        "missing_columns": [],
    }

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            return [
                blocked
                if ctx.table_name == blocked.table_name
                else TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DIM",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                )
                for ctx in contexts
                if ctx.layer == "DWD"
            ]

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True
    )

    assert result["blocked_table_count"] == 1
    assert result["model_updates"][0]["table"] == "dwd_customer"
    assert result["model_updates"][0]["layer"] == "DIM"
    assert result["model_updates"][0]["updated"] is False
    assert result["skipped_model_updates"][0]["table"] == "dwd_order_detail"
    assert result["skipped_model_updates"][0]["reason"] == "validation_blocked"


def test_run_catalog_discovery_writes_catalog_only_by_default(
    tmp_path, monkeypatch, sample_lineage_data
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "catalog_discovery"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    for table_name, layer in [
        ("dwd_customer", "DWD"),
        ("dwd_order_detail", "DWD"),
    ]:
        (models_dir / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: sample_lineage_data,
    )

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_order_detail":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DWD",
                            table_type="fact",
                            confidence=0.9,
                            reasoning_steps=[],
                            columns={
                                "atomic_metrics": [
                                    {
                                        "name": "subtotal",
                                        "business_process": "ORDER_TRANSACTION",
                                    }
                                ],
                                "derived_metrics": [],
                                "calculated_metrics": [],
                                "dimensions": [],
                                "others": [],
                            },
                        )
                    )
                elif ctx.table_name == "dwd_customer":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                            entities=[
                                {
                                    "code": "CUSTOMER",
                                    "type": "primary",
                                    "name": "客户",
                                    "key_columns": ["customer_id"],
                                }
                            ],
                        )
                    )
            return results

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=True,
    )

    catalog_path = project_dir / "business_semantics.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    assert result["source"] == "llm_catalog_discovery"
    assert result["updated"] is True
    assert catalog["business_processes"][0]["code"] == "ORDER_TRANSACTION"
    assert "tables" not in catalog["business_processes"][0]
    assert catalog["semantic_subjects"][0]["code"] == "CUSTOMER"
    assert "tables" not in catalog["semantic_subjects"][0]
    assert result["update_models"] is False
    assert result["model_update_count"] == 0

    fact_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )
    dim_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_customer.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "business_process" not in fact_model
    assert "semantic_subject" not in dim_model


def test_run_catalog_metadata_write_initializes_models_without_llm(
    tmp_path, monkeypatch
):
    project = "catalog_writer"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {
                        "id": "04",
                        "code": "TRAN",
                        "name": "交易域",
                    }
                ],
                "business_areas": [
                    {
                        "id": "SHOP",
                        "code": "SHOP",
                        "name": "零售业务",
                    }
                ],
                "business_processes": [
                    {
                        "code": "ORDER_DETAIL",
                        "name": "订单明细",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            order_item_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_catalog_metadata_write(
        project,
        dry_run=False,
        write_scope="business",
    )

    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert result["source"] == "catalog"
    assert result["model_update_count"] == 1
    assert model["layer"] == "DWD"
    assert model["table_type"] == "other"
    assert "data_domain" not in model
    assert "business_area" not in model
    assert "business_process" not in model


def test_run_catalog_metadata_write_enriches_existing_model_business_codes(
    tmp_path, monkeypatch
):
    project = "catalog_writer_existing_refs"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (models_dir / "dwd_order_detail.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_DETAIL",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
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
                        "code": "TRAN",
                        "name": "交易域",
                    }
                ],
                "business_areas": [
                    {
                        "id": "SHOP",
                        "code": "SHOP",
                        "name": "零售业务",
                    }
                ],
                "business_processes": [
                    {
                        "code": "ORDER_DETAIL",
                        "name": "订单明细",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    assert model["business_process"] == "ORDER_DETAIL"
    assert model["data_domain"] == "04"
    assert model["business_area"] == "SHOP"


def test_run_direct_model_generation_assigns_catalog_refs_from_assets(
    tmp_path, monkeypatch
):
    project = "direct_model_writer"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {"id": "03", "code": "STORE", "name": "门店域"},
                    {"id": "04", "code": "ORDER", "name": "订单域"},
                ],
                "business_areas": [
                    {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
                ],
                "business_processes": [
                    {
                        "code": "ORDER_DETAIL",
                        "name": "订单明细",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [
                    {
                        "code": "STORE",
                        "name": "门店",
                        "data_domain": "03",
                        "business_area": "SHOP",
                    },
                    {
                        "code": "PROMOTION",
                        "name": "促销活动",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    },
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        -- DWD 订单明细事实表
            CREATE TABLE dwd_order_detail (
                order_id BIGINT,
                store_id BIGINT,
                promotion_id BIGINT,
                pay_amount DECIMAL(12,2)
            );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dws_store_sales_daily.sql").write_text(
        """
        -- DWS 门店销售日汇总
        CREATE TABLE dws_store_sales_daily (
            store_id BIGINT,
            stat_date DATE,
            order_count BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dim_store.sql").write_text(
        """
        -- DIM 门店维度表
        CREATE TABLE dim_store (
            store_id BIGINT,
            store_name VARCHAR(64)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_store_sales_daily.sql").write_text(
        """
        INSERT INTO dws_store_sales_daily
        SELECT store_id, order_date AS stat_date, COUNT(*) AS order_count,
               SUM(pay_amount) AS pay_amount
        FROM dwd_order_detail
        GROUP BY store_id, order_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "dwd_order_detail", "layer": "DWD"},
                    {"name": "dws_store_sales_daily", "layer": "DWS"},
                    {"name": "dim_store", "layer": "DIM"},
                ],
                "edges": [
                    {
                        "source": "dwd_order_detail.store_id",
                        "target": "dws_store_sales_daily.store_id",
                        "expression": "store_id",
                        "source_file": "dws_store_sales_daily.sql",
                    },
                    {
                        "source": "dwd_order_detail.order_id",
                        "target": "dws_store_sales_daily.order_count",
                        "expression": "COUNT(*)",
                        "source_file": "dws_store_sales_daily.sql",
                    },
                ],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(project, dry_run=False)

    models_dir = project_dir / "mid" / "models"
    dwd_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    dws_model = yaml.safe_load(
        (models_dir / "dws_store_sales_daily.yaml").read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (models_dir / "dim_store.yaml").read_text(encoding="utf-8")
    )
    assert result["source"] == "direct_generation"
    assert result["model_update_count"] == 3
    assert result["assigned_business_process_count"] == 2
    assert result["assigned_semantic_subject_count"] == 1
    assert dwd_model["table_type"] == "fact"
    assert dwd_model["business_process"] == "ORDER_DETAIL"
    assert dwd_model["data_domain"] == "04"
    assert dwd_model["business_area"] == "SHOP"
    assert dwd_model["entities"] == [
        {
            "code": "STORE",
            "type": "foreign",
            "name": "门店",
            "key_columns": ["store_id"],
        },
        {
            "code": "PROMOTION",
            "type": "foreign",
            "name": "促销活动",
            "key_columns": ["promotion_id"],
        },
    ]
    assert dws_model["business_process"] == "ORDER_DETAIL"
    assert dws_model["grain"] == {
        "entities": ["STORE"],
        "time_column": "stat_date",
        "time_period": "D",
    }
    assert dim_model["layer"] == "DIM"
    assert dim_model["table_type"] == "dimension"
    assert dim_model["semantic_subject"] == "STORE"
    assert dim_model["entities"][0]["key_columns"] == ["store_id"]


@pytest.mark.parametrize("dry_run", [False, True], ids=["write", "dry-run"])
def test_run_direct_model_generation_replace_existing_models_handles_dry_run(
    tmp_path, monkeypatch, dry_run
):
    project = f"direct_model_writer_replace_{dry_run}"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    stale_model = models_dir / "stale_model.yaml"
    stale_model.write_text(
        "version: 2\nname: stale_model\nlayer: DWD\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=dry_run,
        replace_existing_models=True,
        update_catalog=True,
    )

    assert str(stale_model) in result["planned_deleted_model_files"]
    assert stale_model.exists() is dry_run
    if dry_run:
        assert result["deleted_model_files"] == []
        assert not (models_dir / "dwd_order_detail.yaml").exists()
    else:
        assert str(stale_model) in result["deleted_model_files"]
        assert (models_dir / "dwd_order_detail.yaml").exists()


def test_run_direct_model_generation_keeps_ods_materialized_source(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_ods"
    project_dir = tmp_path / project
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_dm"
    ods_ddl_dir.mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "project": project},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ods_ddl_dir / "ods_customer.sql").write_text(
        """
        -- ODS 客户每日快照源表
        CREATE TABLE ods_customer (
            customer_id BIGINT,
            load_time DATETIME
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(project, dry_run=False)

    model_path = (
        project_dir
        / "ods"
        / "models"
        / "internal"
        / "demo_dm"
        / "ods_customer.yaml"
    )
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert result["model_update_count"] == 1
    assert model["layer"] == "ODS"
    assert model["table_type"] == "other"
    assert model["config"]["materialized"] == "source"


def test_run_direct_model_generation_keeps_source_layer_over_table_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_ods_table_inspector_guard"
    project_dir = tmp_path / project
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_dm"
    ods_ddl_dir.mkdir(parents=True)
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "project": project},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ods_ddl_dir / "order_source.sql").write_text(
        """
        CREATE TABLE order_source (
            order_id BIGINT,
            customer_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [{"name": "order_source"}],
                "edges": [],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )
    prompts = []

    def fake_call_api(_self, prompt):
        prompts.append(prompt)
        raise AssertionError("ODS fixed layer should not call table_inspector")

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model_path = (
        project_dir
        / "ods"
        / "models"
        / "internal"
        / "demo_dm"
        / "order_source.yaml"
    )
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    update = result["model_updates"][0]
    assert prompts == []
    assert model["layer"] == "ODS"
    assert model["table_type"] == "other"
    assert model["config"]["materialized"] == "source"
    assert "atomic_metrics" not in model
    assert "derived_metrics" not in model
    assert update["metric_changed"] is False
    assert update["metric_generation_source"] == ""
    assert update["layer_assignment_source"] == "direct_rule"
    assert result["table_inspector_layer_inference_attempt_count"] == 0
    assert result["table_inspector_layer_inference_count"] == 0


def test_run_direct_model_generation_keeps_ads_placement_over_table_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_ads_placement_guard"
    project_dir = tmp_path / project
    ads_ddl_dir = project_dir / "ads" / "ddl"
    ads_ddl_dir.mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "project": project},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ads_ddl_dir / "customer_output.sql").write_text(
        """
        CREATE TABLE customer_output (
            customer_id BIGINT,
            stat_date DATE,
            display_score DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    prompts = []

    def fake_call_api(_self, prompt):
        prompts.append(prompt)
        raise AssertionError("ADS placement should not call table_inspector")

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "ads" / "models" / "customer_output.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert prompts == []
    assert model["layer"] == "ADS"
    assert model["table_type"] == "other"
    assert model["config"]["materialized"] == "full"
    assert "atomic_metrics" not in model
    assert "entities" not in model
    assert update["layer_assignment_source"] == "direct_rule"
    assert result["table_inspector_layer_inference_attempt_count"] == 0
    assert result["table_inspector_layer_inference_count"] == 0


def test_run_direct_model_generation_prefers_strong_ads_signal_over_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_ads_signal_guard"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "CUSTOMER_ANALYSIS",
                        "name": "客户分析",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_by_age_group.sql").write_text(
        """
        CREATE TABLE customer_by_age_group (
            age_group STRING,
            customer_count BIGINT,
            avg_revenue DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "customer_by_age_group.sql").write_text(
        """
        INSERT INTO customer_by_age_group
        SELECT age_group,
               COUNT(DISTINCT customer_id) AS customer_count,
               AVG(revenue) AS avg_revenue
        FROM customer_profile
        GROUP BY age_group;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_monthly_summary.sql").write_text(
        """
        CREATE TABLE customer_monthly_summary (
            customer_id BIGINT,
            stat_month DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "tasks" / "customer_monthly_summary.sql"
    ).write_text(
        """
        INSERT INTO customer_monthly_summary
        SELECT customer_id, stat_month, SUM(pay_amount) AS total_amount
        FROM order_detail
        GROUP BY customer_id, stat_month;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "customer_by_age_group"},
                    {"name": "customer_monthly_summary"},
                ],
                "edges": [],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, prompt):
        if "customer_by_age_group" in prompt:
            content = {
                "inferred_layer": "DWS",
                "table_type": "fact",
                "confidence": 0.91,
                "reasoning_steps": ["按年龄段聚合，像公共汇总"],
                "columns": {
                    "atomic_metrics": [
                        {
                            "name": "customer_count",
                            "business_process": "CUSTOMER_ANALYSIS",
                        },
                        {
                            "name": "avg_revenue",
                            "business_process": "CUSTOMER_ANALYSIS",
                        },
                    ],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                    "dimensions": [{"name": "age_group"}],
                    "others": [],
                },
                "entities": [],
                "grain": {},
            }
        else:
            content = {
                "inferred_layer": "DWS",
                "table_type": "fact",
                "confidence": 0.91,
                "reasoning_steps": ["按客户月粒度公共汇总"],
                "columns": {
                    "atomic_metrics": [
                        {
                            "name": "total_amount",
                            "business_process": "CUSTOMER_ANALYSIS",
                        }
                    ],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                    "dimensions": [
                        {"name": "customer_id"},
                        {"name": "stat_month"},
                    ],
                    "others": [],
                },
                "entities": [
                    {
                        "code": "CUSTOMER",
                        "type": "foreign",
                        "key_columns": ["customer_id"],
                    }
                ],
                "grain": {
                    "entities": ["CUSTOMER"],
                    "time_column": "stat_month",
                    "time_period": "M",
                },
            }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    models_dir = project_dir / "mid" / "models"
    ads_model = yaml.safe_load(
        (
            project_dir / "ads" / "models" / "customer_by_age_group.yaml"
        ).read_text(encoding="utf-8")
    )
    dws_model = yaml.safe_load(
        (models_dir / "customer_monthly_summary.yaml").read_text(
            encoding="utf-8"
        )
    )
    updates = {update["table"]: update for update in result["model_updates"]}
    assert ads_model["layer"] == "ADS"
    assert ads_model["table_type"] == "other"
    assert "atomic_metrics" not in ads_model
    assert "entities" not in ads_model
    assert "grain" not in ads_model
    assert updates["customer_by_age_group"]["metric_generation_source"] == ""
    assert updates["customer_by_age_group"]["layer_assignment_source"] == (
        "direct_rule"
    )
    assert dws_model["layer"] == "DWS"
    assert dws_model["atomic_metrics"] == ["total_amount"]
    assert dws_model["grain"]["time_period"] == "M"


def test_run_direct_model_generation_reports_documentation_changes(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_doc_change"
    project_dir = tmp_path / project
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_dm"
    ods_model_dir = project_dir / "ods" / "models" / "internal" / "demo_dm"
    ods_ddl_dir.mkdir(parents=True)
    ods_model_dir.mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "project": project},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ods_ddl_dir / "ods_customer.sql").write_text(
        """
        -- ODS 客户每日快照源表
        CREATE TABLE ods_customer (
            customer_id BIGINT,
            load_time DATETIME
        );
        """,
        encoding="utf-8",
    )
    (ods_model_dir / "ods_customer.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "ods_customer",
                "layer": "ODS",
                "table_type": "other",
                "config": {"materialized": "source"},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(project, dry_run=True)

    update = result["model_updates"][0]
    assert update["table"] == "ods_customer"
    assert update["changed"] is True
    assert update["documentation_changed"] is True
    assert update["config_changed"] is True
    assert update["metadata_changed"] is True
    assert update["business_changed"] is False
    assert update["grain_changed"] is False


def test_run_direct_model_generation_defaults_to_cold_start_metadata(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_cold_start"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [
                    {
                        "code": "CUST",
                        "name": "客户",
                        "data_domain": "01",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_customer.sql").write_text(
        """
        -- DWD 客户维度宽表
        CREATE TABLE dwd_customer (
            customer_id BIGINT,
            customer_name VARCHAR(64),
            snapshot_date DATE
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dwd_customer.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_customer",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_TRANSACTION",
                "config": {"materialized": "incremental"},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=True,
    )

    update = result["model_updates"][0]
    assert result["llm"] is False
    assert update["assignment_source"] == "direct_catalog_match"
    assert update["assignment_reason"].startswith("semantic_subject_match")
    assert update["previous_layer"] is None
    assert update["layer"] == "DIM"
    assert update["previous_table_type"] is None
    assert update["table_type"] == "dimension"
    assert update["business_process"] is None
    assert update["semantic_subject"] == "CUST"


def test_run_direct_model_generation_cold_start_uses_inferred_layer_path(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_cold_start_path"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "ads" / "models").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "semantic_subjects": [
                    {
                        "code": "CUST",
                        "name": "客户",
                        "data_domain": "01",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_profile.sql").write_text(
        """
        CREATE TABLE customer_profile (
            customer_id BIGINT,
            customer_name VARCHAR(64)
        );
        """,
        encoding="utf-8",
    )
    stale_ads_path = project_dir / "ads" / "models" / "customer_profile.yaml"
    stale_ads_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "customer_profile",
                "layer": "ADS",
                "table_type": "other",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
    )

    mid_model_path = project_dir / "mid" / "models" / "customer_profile.yaml"
    update = result["model_updates"][0]
    model = yaml.safe_load(mid_model_path.read_text(encoding="utf-8"))
    assert update["path"] == str(mid_model_path)
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert not stale_ads_path.exists()


def test_run_direct_model_generation_keeps_layer_table_type_consistent(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_layer_type_consistency"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "semantic_subjects": [
                    {
                        "code": "CUST",
                        "name": "客户",
                        "data_domain": "01",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_profile.sql").write_text(
        """
        CREATE TABLE customer_profile (
            customer_id BIGINT,
            customer_name VARCHAR(64)
        );
        """,
        encoding="utf-8",
    )
    model_path = project_dir / "mid" / "models" / "customer_profile.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "customer_profile",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "OLD_PROCESS",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    run_direct_model_generation(project, dry_run=False)

    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert model["semantic_subject"] == "CUST"
    assert "business_process" not in model


def test_run_direct_model_generation_rejects_business_scope(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_preserve_governance"
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    models_dir = project_dir / "mid" / "models"
    ddl_dir.mkdir(parents=True)
    models_dir.mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "dwd_transactions.sql").write_text(
        """
        CREATE TABLE dwd_transactions (
            transaction_id BIGINT,
            amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (ddl_dir / "dws_transactions_daily.sql").write_text(
        """
        CREATE TABLE dws_transactions_daily (
            stat_date DATE,
            amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (models_dir / "dwd_transactions.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_transactions",
                "layer": "DWD",
                "table_type": "fact",
                "config": {"materialized": "incremental"},
                "data_domain": "04",
                "business_area": "PAYM",
                "business_process": "PAYMENT_TRANSACTION",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (models_dir / "dws_transactions_daily.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_transactions_daily",
                "layer": "DWS",
                "table_type": "fact",
                "config": {"materialized": "incremental"},
                "business_area": "PAYM",
                "business_process": "PAYMENT_TRANSACTION",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    with pytest.raises(
        ValueError,
        match="generate mode 仅支持 write_scope=all/table",
    ):
        run_direct_model_generation(
            project,
            dry_run=True,
            write_scope="business",
        )


def test_run_direct_model_generation_does_not_use_downstream_for_process_match(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_downstream_process"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    },
                    {
                        "code": "PROMOTION_EFFECT",
                        "name": "促销效果",
                        "data_domain": "06",
                        "business_area": "SHOP",
                    },
                ],
                "semantic_subjects": [
                    {
                        "code": "PROMOTION",
                        "name": "促销活动",
                        "data_domain": "06",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        -- DWD 订单明细事实表
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            promotion_id BIGINT,
            quantity INT,
            subtotal DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "ddl" / "dws_promotion_effect_daily.sql"
    ).write_text(
        """
        -- DWS 促销效果日汇总表
        CREATE TABLE dws_promotion_effect_daily (
            promotion_id BIGINT,
            stat_date DATE,
            sale_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "tasks" / "dws_promotion_effect_daily.sql"
    ).write_text(
        """
        INSERT INTO dws_promotion_effect_daily
        SELECT promotion_id, order_date AS stat_date, SUM(subtotal)
        FROM dwd_order_detail
        GROUP BY promotion_id, order_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "dwd_order_detail", "layer": "DWD"},
                    {"name": "dws_promotion_effect_daily", "layer": "DWS"},
                ],
                "edges": [
                    {
                        "source": "dwd_order_detail.promotion_id",
                        "target": "dws_promotion_effect_daily.promotion_id",
                        "expression": "promotion_id",
                        "source_file": "dws_promotion_effect_daily.sql",
                    },
                    {
                        "source": "dwd_order_detail.subtotal",
                        "target": "dws_promotion_effect_daily.sale_amount",
                        "expression": "SUM(subtotal)",
                        "source_file": "dws_promotion_effect_daily.sql",
                    },
                ],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=True,
    )

    updates = {update["table"]: update for update in result["model_updates"]}
    assert (
        updates["dwd_order_detail"]["business_process"] == "ORDER_TRANSACTION"
    )
    assert updates["dwd_order_detail"]["data_domain"] == "04"
    assert updates["dws_promotion_effect_daily"]["business_process"] == (
        "PROMOTION_EFFECT"
    )


def test_run_direct_model_generation_materialized_uses_target_task_pattern(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_materialized"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "INVENTORY_MANAGEMENT",
                        "name": "库存管理",
                        "data_domain": "05",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dws_inventory_daily.sql").write_text(
        """
        -- DWS 库存日汇总表
        CREATE TABLE dws_inventory_daily (
            product_id BIGINT,
            store_id BIGINT,
            stat_date DATE,
            quantity INT
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_inventory_daily.sql").write_text(
        """
        DELETE FROM dws_inventory_daily WHERE stat_date = CURRENT_DATE;
        INSERT INTO dws_inventory_daily
        SELECT product_id, store_id, snapshot_date AS stat_date, SUM(quantity)
        FROM dwd_inventory
        GROUP BY product_id, store_id, snapshot_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "ads_sales_dashboard.sql").write_text(
        """
        -- ADS 销售驾驶舱
        CREATE TABLE ads_sales_dashboard (
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "ads_sales_dashboard.sql").write_text(
        """
        TRUNCATE TABLE ads_sales_dashboard;
        INSERT INTO ads_sales_dashboard
        SELECT stat_date, SUM(total_amount)
        FROM dws_store_sales_daily
        GROUP BY stat_date;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
    )

    models_dir = project_dir / "mid" / "models"
    dws_model = yaml.safe_load(
        (models_dir / "dws_inventory_daily.yaml").read_text(encoding="utf-8")
    )
    ads_model = yaml.safe_load(
        (
            project_dir / "ads" / "models" / "ads_sales_dashboard.yaml"
        ).read_text(encoding="utf-8")
    )
    assert result["llm"] is False
    assert dws_model["config"]["materialized"] == "incremental"
    assert ads_model["config"]["materialized"] == "full"


def test_run_direct_model_generation_infers_ads_fact_from_task(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_ads_task"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dws_order_sales_daily.sql").write_text(
        """
        CREATE TABLE dws_order_sales_daily (
            store_id BIGINT,
            stat_date DATE,
            sale_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "ads_sales_dashboard.sql").write_text(
        """
        CREATE TABLE ads_sales_dashboard (
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "ads_sales_dashboard.sql").write_text(
        """
        DELETE FROM ads_sales_dashboard WHERE stat_date = CURRENT_DATE;
        INSERT INTO ads_sales_dashboard
        SELECT stat_date, SUM(sale_amount) AS total_amount
        FROM dws_order_sales_daily
        GROUP BY stat_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "dws_order_sales_daily", "layer": "DWS"},
                    {"name": "ads_sales_dashboard", "layer": "ADS"},
                ],
                "edges": [
                    {
                        "source": "dws_order_sales_daily.sale_amount",
                        "target": "ads_sales_dashboard.total_amount",
                        "expression": "SUM(sale_amount)",
                        "source_file": "ads_sales_dashboard.sql",
                    }
                ],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
    )

    models_dir = project_dir / "mid" / "models"
    dws_model = yaml.safe_load(
        (models_dir / "dws_order_sales_daily.yaml").read_text(encoding="utf-8")
    )
    ads_model = yaml.safe_load(
        (
            project_dir / "ads" / "models" / "ads_sales_dashboard.yaml"
        ).read_text(encoding="utf-8")
    )
    assert result["assigned_business_process_count"] == 1
    assert dws_model["table_type"] == "fact"
    assert dws_model["business_process"] == "ORDER_TRANSACTION"
    assert ads_model["layer"] == "ADS"
    assert ads_model["table_type"] == "other"
    assert "business_process" not in ads_model
    assert ads_model["config"]["materialized"] == "incremental"


def test_run_direct_model_generation_infers_layers_without_model_or_prefix_metadata(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_no_layer_metadata"
    project_dir = tmp_path / project
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_dm"
    ods_ddl_dir.mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [
                    {
                        "code": "CUSTOMER",
                        "name": "客户",
                        "data_domain": "01",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ods_ddl_dir / "source_orders.sql").write_text(
        """
        -- 订单源表
        CREATE TABLE source_orders (
            order_id BIGINT,
            customer_id BIGINT,
            order_date DATE,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "order_detail.sql").write_text(
        """
        -- 订单交易明细事实表
        CREATE TABLE order_detail (
            order_id BIGINT,
            customer_id BIGINT,
            order_date DATE,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "store_sales_daily.sql").write_text(
        """
        -- 订单交易门店销售日汇总表
        CREATE TABLE store_sales_daily (
            customer_id BIGINT,
            stat_date DATE,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "sales_dashboard.sql").write_text(
        """
        -- 订单交易销售驾驶舱
        CREATE TABLE sales_dashboard (
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_profile.sql").write_text(
        """
        -- 客户维度属性档案
        CREATE TABLE customer_profile (
            customer_id BIGINT,
            customer_name VARCHAR(64)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "order_detail.sql").write_text(
        """
        INSERT INTO order_detail
        SELECT order_id, customer_id, order_date, pay_amount
        FROM source_orders;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "store_sales_daily.sql").write_text(
        """
        INSERT INTO store_sales_daily
        SELECT customer_id, order_date AS stat_date, SUM(pay_amount)
        FROM order_detail
        GROUP BY customer_id, order_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "sales_dashboard.sql").write_text(
        """
        INSERT INTO sales_dashboard
        SELECT stat_date, SUM(pay_amount) AS total_amount
        FROM store_sales_daily
        GROUP BY stat_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "source_orders", "layer": "OTHER"},
                    {"name": "order_detail", "layer": "OTHER"},
                    {"name": "store_sales_daily", "layer": "OTHER"},
                    {"name": "sales_dashboard", "layer": "OTHER"},
                    {"name": "customer_profile", "layer": "OTHER"},
                ],
                "edges": [
                    {
                        "source": "source_orders.order_id",
                        "target": "order_detail.order_id",
                        "expression": "order_id",
                        "source_file": "order_detail.sql",
                    },
                    {
                        "source": "order_detail.pay_amount",
                        "target": "store_sales_daily.pay_amount",
                        "expression": "SUM(pay_amount)",
                        "source_file": "store_sales_daily.sql",
                    },
                    {
                        "source": "store_sales_daily.pay_amount",
                        "target": "sales_dashboard.total_amount",
                        "expression": "SUM(pay_amount)",
                        "source_file": "sales_dashboard.sql",
                    },
                ],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
    )

    models_dir = project_dir / "mid" / "models"
    ods_model = yaml.safe_load(
        (
            project_dir
            / "ods"
            / "models"
            / "internal"
            / "demo_dm"
            / "source_orders.yaml"
        ).read_text(encoding="utf-8")
    )
    order_model = yaml.safe_load(
        (models_dir / "order_detail.yaml").read_text(encoding="utf-8")
    )
    dws_model = yaml.safe_load(
        (models_dir / "store_sales_daily.yaml").read_text(encoding="utf-8")
    )
    ads_model = yaml.safe_load(
        (project_dir / "ads" / "models" / "sales_dashboard.yaml").read_text(
            encoding="utf-8"
        )
    )
    dim_model = yaml.safe_load(
        (models_dir / "customer_profile.yaml").read_text(encoding="utf-8")
    )
    assert result["model_update_count"] == 5
    assert ods_model["layer"] == "ODS"
    assert ods_model["table_type"] == "other"
    assert ods_model["config"]["materialized"] == "source"
    assert order_model["layer"] == "DWD"
    assert order_model["table_type"] == "fact"
    assert order_model["business_process"] == "ORDER_TRANSACTION"
    assert dws_model["layer"] == "DWS"
    assert dws_model["table_type"] == "fact"
    assert ads_model["layer"] == "ADS"
    assert ads_model["table_type"] == "other"
    assert dim_model["layer"] == "DIM"
    assert dim_model["table_type"] == "dimension"
    assert dim_model["semantic_subject"] == "CUSTOMER"


def test_run_direct_model_generation_propagates_business_process_fixpoint(
    tmp_path, monkeypatch
):
    project = "direct_model_writer_lineage_fixpoint"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            stat_date DATE,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dws_store_daily.sql").write_text(
        """
        CREATE TABLE dws_store_daily (
            store_id BIGINT,
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "ads_store_dashboard.sql").write_text(
        """
        CREATE TABLE ads_store_dashboard (
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_store_daily.sql").write_text(
        """
        INSERT INTO dws_store_daily
        SELECT store_id, stat_date, SUM(pay_amount) AS total_amount
        FROM dwd_order_detail
        GROUP BY store_id, stat_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "ads_store_dashboard.sql").write_text(
        """
        INSERT INTO ads_store_dashboard
        SELECT stat_date, SUM(total_amount) AS total_amount
        FROM dws_store_daily
        GROUP BY stat_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "dwd_order_detail"},
                    {"name": "dws_store_daily"},
                    {"name": "ads_store_dashboard"},
                ],
                "edges": [
                    {
                        "source": "dwd_order_detail.pay_amount",
                        "target": "dws_store_daily.total_amount",
                        "expression": "SUM(pay_amount)",
                        "source_file": "dws_store_daily.sql",
                    },
                    {
                        "source": "dws_store_daily.total_amount",
                        "target": "ads_store_dashboard.total_amount",
                        "expression": "SUM(total_amount)",
                        "source_file": "ads_store_dashboard.sql",
                    },
                ],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
    )

    models_dir = project_dir / "mid" / "models"
    dws_model = yaml.safe_load(
        (models_dir / "dws_store_daily.yaml").read_text(encoding="utf-8")
    )
    ads_model = yaml.safe_load(
        (
            project_dir / "ads" / "models" / "ads_store_dashboard.yaml"
        ).read_text(encoding="utf-8")
    )
    updates = {update["table"]: update for update in result["model_updates"]}
    assert dws_model["business_process"] == "ORDER_TRANSACTION"
    assert ads_model["table_type"] == "other"
    assert "business_process" not in ads_model
    assert updates["dws_store_daily"]["assignment_source"] == (
        "direct_lineage_propagation"
    )
    assert updates["ads_store_dashboard"]["assignment_source"] == "fallback"


def test_run_direct_model_generation_cold_start_inspects_prefixed_table_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_table_inspector_cold_start"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "data_domain": "04",
                        "business_area": "SHOP",
                    }
                ],
                "semantic_subjects": [
                    {
                        "code": "CUSTOMER",
                        "name": "客户",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            customer_id BIGINT,
            order_date DATE,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [{"name": "dwd_order_detail"}],
                "edges": [],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    calls = []
    timeouts = []

    def fake_call_api(_self, prompt):
        calls.append(prompt)
        timeouts.append(_self.request_timeout)
        content = {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.93,
            "reasoning_steps": ["订单明细事实表"],
            "inferred_data_domain": "04",
            "inferred_business_area": "SHOP",
            "columns": {
                "atomic_metrics": [
                    {
                        "name": "pay_amount",
                        "business_process": "ORDER_TRANSACTION",
                        "reason": "明细支付金额",
                        "confidence": 0.91,
                    }
                ],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "order_id"},
                    {"name": "customer_id"},
                    {"name": "order_date"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "ORDER",
                    "type": "primary",
                    "key_columns": ["order_id"],
                },
                {
                    "code": "CUSTOMER",
                    "type": "foreign",
                    "key_columns": ["customer_id"],
                },
            ],
            "grain": {},
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        request_timeout=240,
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert len(calls) == 1
    assert timeouts == [240]
    assert "原始配置层级: DWD" in calls[0]
    assert result["table_inspector_layer_inference_candidate_count"] == 1
    assert result["table_inspector_layer_inference_candidates"] == [
        {"table": "dwd_order_detail", "reason": "cold_start_full_metadata"}
    ]
    assert result["table_inspector_layer_inference_attempt_count"] == 1
    assert result["table_inspector_layer_inference_count"] == 1
    assert model["atomic_metrics"] == ["pay_amount"]
    assert model["entities"] == [
        {
            "code": "ORDER",
            "type": "primary",
            "key_columns": ["order_id"],
        },
        {
            "code": "CUSTOMER",
            "type": "foreign",
            "key_columns": ["customer_id"],
        },
    ]
    assert model["business_process"] == "ORDER_TRANSACTION"
    assert update["metric_changed"] is True
    assert update["metric_generation_source"] == "table_inspector"


def test_run_direct_model_generation_ignores_existing_metrics_when_inspector_sparse(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_sparse_inspector_metrics"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "SALES_SUMMARY",
                        "name": "Sales Summary",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "sales_daily.sql").write_text(
        """
        CREATE TABLE sales_daily (
            store_id BIGINT,
            stat_date DATE,
            sales_amt DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "sales_daily.sql").write_text(
        """
        INSERT INTO sales_daily
        SELECT store_id, stat_date, SUM(pay_amt) AS sales_amt
        FROM order_detail
        GROUP BY store_id, stat_date;
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "sales_daily.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "business_area": "SHOP",
                "business_process": "SALES_SUMMARY",
                "atomic_metrics": ["sales_amt"],
                "grain": {
                    "entities": ["STORE"],
                    "time_column": "stat_date",
                    "time_period": "D",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "artifacts" / "lineage" / "lineage_data.json").write_text(
        json.dumps(
            {
                "tables": [{"name": "sales_daily"}],
                "edges": [],
                "indirect_edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "reasoning_steps": ["公共汇总事实表，但未识别指标分组"],
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [],
                "others": [],
            },
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "sales_daily.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert "atomic_metrics" not in model
    assert update["removed_metric_count"] == 0
    assert update["metric_generation_source"] == ""


def test_run_direct_model_generation_prefers_inspector_over_application_token(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_application_token"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "CUSTOMER_EVENT",
                        "name": "客户事件",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_rfm_events.sql").write_text(
        """
        CREATE TABLE customer_rfm_events (
            event_id BIGINT,
            customer_id BIGINT,
            event_date DATE,
            event_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "customer_rfm_events.sql").write_text(
        """
        INSERT INTO customer_rfm_events
        SELECT event_id, customer_id, event_date, event_amount
        FROM raw_customer_events;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.91,
            "reasoning_steps": ["事件明细粒度，无聚合输出"],
            "columns": {
                "atomic_metrics": [
                    {
                        "name": "event_amount",
                        "business_process": "CUSTOMER_EVENT",
                    }
                ],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "event_id"},
                    {"name": "customer_id"},
                    {"name": "event_date"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "CUSTOMER_EVENT",
                    "type": "primary",
                    "key_columns": ["event_id"],
                }
            ],
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "customer_rfm_events.yaml"
        ).read_text(encoding="utf-8")
    )
    assert model["layer"] == "DWD"
    assert model["atomic_metrics"] == ["event_amount"]


def test_run_direct_model_generation_matches_catalog_governance_with_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_existing_governance"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "models").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "SALES_ANALYSIS",
                        "name": "销售分析",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "sales_result.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "sales_result",
                "table_type": "fact",
                "business_process": "SALES_ANALYSIS",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "sales_result.sql").write_text(
        """
        CREATE TABLE sales_result (
            stat_date DATE,
            total_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "sales_result.sql").write_text(
        """
        INSERT INTO sales_result
        SELECT stat_date, SUM(pay_amount) AS total_amount
        FROM order_detail
        GROUP BY stat_date;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "reasoning_steps": ["按日期聚合的公共汇总事实"],
            "columns": {
                "atomic_metrics": [
                    {
                        "name": "total_amount",
                        "business_process": "SALES_ANALYSIS",
                    }
                ],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [{"name": "stat_date"}],
                "others": [],
            },
            "entities": [],
            "grain": {"time_column": "stat_date", "time_period": "D"},
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "sales_result.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert model["layer"] == "DWS"
    assert model["table_type"] == "fact"
    assert model["business_process"] == "SALES_ANALYSIS"
    assert model["atomic_metrics"] == ["total_amount"]
    assert update["assignment_source"] == "direct_catalog_match"
    assert update["metric_generation_source"] == "table_inspector"


def test_run_direct_model_generation_keeps_summary_dws_from_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_summary_dws"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_summary_dws\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "agent_summary.sql").write_text(
        """
        CREATE TABLE agent_summary (
            agent_id BIGINT,
            interaction_count BIGINT
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "agent_summary.sql").write_text(
        """
        INSERT INTO agent_summary
        SELECT agent_id, COUNT(*) AS interaction_count
        FROM customer_interactions
        GROUP BY agent_id;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "reasoning_steps": ["按客户经理汇总的公共指标"],
            "columns": {
                "atomic_metrics": [{"name": "interaction_count"}],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [{"name": "agent_id"}],
                "others": [],
            },
            "entities": [
                {
                    "code": "AGENT",
                    "type": "foreign",
                    "key_columns": ["agent_id"],
                }
            ],
            "grain": {"entities": ["AGENT"]},
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "agent_summary.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert model["layer"] == "DWS"
    assert model["table_type"] == "fact"
    assert model["atomic_metrics"] == ["interaction_count"]


def test_run_direct_model_generation_keeps_aggregate_summary_dws_over_dim_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_summary_dim_guard"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_summary_dim_guard\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "agent_summary.sql").write_text(
        """
        CREATE TABLE agent_summary (
            agent_id BIGINT,
            interaction_count BIGINT,
            avg_satisfaction DECIMAL(8,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "agent_summary.sql").write_text(
        """
        INSERT INTO agent_summary
        SELECT agent_id,
               COUNT(*) AS interaction_count,
               AVG(satisfaction_rating) AS avg_satisfaction
        FROM customer_interactions
        GROUP BY agent_id;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DIM",
            "table_type": "dimension",
            "confidence": 0.85,
            "reasoning_steps": ["误把聚合绩效汇总表当成坐席维度"],
            "columns": {
                "atomic_metrics": [
                    {"name": "interaction_count"},
                    {"name": "avg_satisfaction"},
                ],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [{"name": "agent_id"}],
                "others": [],
            },
            "entities": [
                {
                    "code": "AGENT",
                    "type": "primary",
                    "key_columns": ["agent_id"],
                }
            ],
            "grain": {"entities": ["AGENT"]},
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "agent_summary.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert model["layer"] == "DWS"
    assert model["table_type"] == "fact"
    assert model["atomic_metrics"] == [
        "interaction_count",
        "avg_satisfaction",
    ]
    assert model["entities"] == [
        {
            "code": "AGENT",
            "type": "foreign",
            "key_columns": ["agent_id"],
        }
    ]
    assert model["grain"] == {"entities": ["AGENT"]}
    assert "semantic_subject" not in model
    assert update["layer_assignment_source"] == "direct_rule"


def test_run_direct_model_generation_keeps_grouped_dedup_profile_dim(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_grouped_profile_dim"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_grouped_profile_dim\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_profile.sql").write_text(
        """
        CREATE TABLE customer_profile (
            customer_id BIGINT,
            last_seen_time DATETIME,
            customer_name STRING,
            member_level STRING
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "customer_profile.sql").write_text(
        """
        INSERT INTO customer_profile
        SELECT customer_id,
               MAX(load_time) AS last_seen_time,
               MAX(customer_name) AS customer_name,
               MAX(member_level) AS member_level
        FROM customer_source
        GROUP BY customer_id;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DIM",
            "table_type": "dimension",
            "confidence": 0.92,
            "reasoning_steps": [
                "GROUP BY用于按客户去重取最新属性，不是公共指标汇总"
            ],
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "customer_id"},
                    {"name": "last_seen_time"},
                    {"name": "customer_name"},
                    {"name": "member_level"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "CUST",
                    "type": "primary",
                    "key_columns": ["customer_id"],
                }
            ],
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "customer_profile.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert model["semantic_subject"] == "CUST"
    assert model["dimension_role"] == "BASE"
    assert model["dimension_content_type"] == "INFO"
    assert "atomic_metrics" not in model
    assert "grain" not in model
    assert (
        update["layer_assignment_source"] == "table_inspector_layer_inference"
    )


def test_run_direct_model_generation_keeps_aggregate_snapshot_dws_over_dwd_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_snapshot_dwd_guard"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_snapshot_dwd_guard\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "account_daily_snapshot.sql").write_text(
        """
        CREATE TABLE account_daily_snapshot (
            account_key CHAR(32),
            snapshot_date DATE,
            daily_transaction_count BIGINT,
            daily_transaction_amount DECIMAL(18,2),
            account_count BIGINT
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "account_daily_snapshot.sql").write_text(
        """
        INSERT INTO account_daily_snapshot
        SELECT a.account_key,
               CURRENT_DATE AS snapshot_date,
               COALESCE(t.daily_transaction_count, 0),
               COALESCE(t.daily_transaction_amount, 0),
               1 AS account_count
        FROM accounts a
        LEFT JOIN (
            SELECT account_id,
                   COUNT(*) AS daily_transaction_count,
                   SUM(amount) AS daily_transaction_amount
            FROM transactions
            WHERE CAST(transaction_date AS DATE) = CURRENT_DATE
            GROUP BY account_id
        ) t ON a.account_id = t.account_id;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.86,
            "reasoning_steps": [
                "目标表本身没有GROUP BY，因此误判为账户日快照明细DWD"
            ],
            "columns": {
                "atomic_metrics": [
                    {"name": "daily_transaction_count"},
                    {"name": "daily_transaction_amount"},
                    {"name": "account_count"},
                ],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "account_key"},
                    {"name": "snapshot_date"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "ACCT",
                    "type": "primary",
                    "key_columns": ["account_key"],
                }
            ],
            "grain": {
                "entities": ["ACCT"],
                "time_column": "snapshot_date",
                "time_period": "D",
            },
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "account_daily_snapshot.yaml"
        ).read_text(encoding="utf-8")
    )
    update = result["model_updates"][0]
    assert model["layer"] == "DWS"
    assert model["table_type"] == "fact"
    assert model["atomic_metrics"] == [
        "daily_transaction_count",
        "daily_transaction_amount",
        "account_count",
    ]
    assert model["entities"] == [
        {
            "code": "ACCT",
            "type": "foreign",
            "key_columns": ["account_key"],
        }
    ]
    assert model["grain"] == {
        "entities": ["ACCT"],
        "time_column": "snapshot_date",
        "time_period": "D",
    }
    assert update["layer_assignment_source"] == "direct_rule"


def test_run_direct_model_generation_keeps_window_profile_dim_from_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_window_profile_dim"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_window_profile_dim\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "customer_profile.sql").write_text(
        """
        CREATE TABLE customer_profile (
            customer_id BIGINT,
            snapshot_date DATE,
            customer_name STRING,
            member_level STRING
        )
        DUPLICATE KEY(customer_id, snapshot_date);
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "customer_profile.sql").write_text(
        """
        INSERT INTO customer_profile
        SELECT customer_id, CAST(@etl_date AS DATE), customer_name, member_level
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY customer_id ORDER BY load_time DESC
                   ) AS rn
            FROM customer_source
        ) t
        WHERE rn = 1;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DIM",
            "table_type": "dimension",
            "confidence": 0.93,
            "reasoning_steps": [
                "使用ROW_NUMBER去重，无GROUP BY聚合，是客户属性快照维表"
            ],
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "customer_id"},
                    {"name": "snapshot_date"},
                    {"name": "customer_name"},
                    {"name": "member_level"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "CUST",
                    "type": "primary",
                    "key_columns": ["customer_id"],
                }
            ],
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "customer_profile.yaml").read_text(
            encoding="utf-8"
        )
    )
    update = result["model_updates"][0]
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert model["semantic_subject"] == "CUST"
    assert model["dimension_role"] == "BASE"
    assert model["dimension_content_type"] == "INFO"
    assert model["entities"] == [
        {
            "code": "CUST",
            "type": "primary",
            "key_columns": ["customer_id"],
        }
    ]
    assert "grain" not in model
    assert "atomic_metrics" not in model
    assert (
        update["layer_assignment_source"] == "table_inspector_layer_inference"
    )


def test_run_direct_model_generation_fills_sparse_dim_fallback_metadata(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_dim_fallback"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_dim_fallback\n",
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "ddl" / "economic_indicators_profile.sql"
    ).write_text(
        """
        CREATE TABLE economic_indicators_profile (
            economic_indicator_key CHAR(32),
            indicator_date DATE,
            gdp_growth_rate DECIMAL(18,4),
            inflation_rate DECIMAL(18,4)
        )
        DUPLICATE KEY(economic_indicator_key);
        """,
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "tasks" / "economic_indicators_profile.sql"
    ).write_text(
        """
        INSERT INTO economic_indicators_profile
        SELECT economic_indicator_key, indicator_date, gdp_growth_rate,
               inflation_rate
        FROM economic_indicators_source;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        return json.dumps(
            {
                "choices": [
                    {"message": {"content": "DIM dimension, but not JSON"}}
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "economic_indicators_profile.yaml"
        ).read_text(encoding="utf-8")
    )
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert model["semantic_subject"] == "ECONOMIC_INDICATOR"
    assert model["dimension_role"] == "BASE"
    assert model["dimension_content_type"] == "INFO"
    assert model["entities"] == [
        {
            "code": "ECONOMIC_INDICATOR",
            "type": "primary",
            "name": "Economic Indicator",
            "key_columns": ["economic_indicator_key"],
        }
    ]
    assert "grain" not in model


def test_run_direct_model_generation_keeps_event_detail_dwd_over_ads_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_event_detail_guard"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_event_detail_guard\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "credit_applications.sql").write_text(
        """
        CREATE TABLE credit_applications (
            application_id BIGINT,
            customer_id BIGINT,
            requested_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "credit_applications.sql").write_text(
        """
        INSERT INTO credit_applications
        SELECT application_id, customer_id, requested_amount
        FROM credit_applications_source;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "ADS",
            "table_type": "fact",
            "confidence": 0.88,
            "reasoning_steps": ["误认为无下游的申请分析输出"],
            "columns": {
                "atomic_metrics": [{"name": "requested_amount"}],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "application_id"},
                    {"name": "customer_id"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "APPLICATION",
                    "type": "primary",
                    "key_columns": ["application_id"],
                },
                {
                    "code": "CUSTOMER",
                    "type": "foreign",
                    "key_columns": ["customer_id"],
                },
            ],
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "credit_applications.yaml"
        ).read_text(encoding="utf-8")
    )
    assert model["layer"] == "DWD"
    assert model["table_type"] == "fact"
    assert "atomic_metrics" not in model


def test_run_direct_model_generation_syncs_dim_shape_after_layer_fix(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_dim_shape_guard"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_dim_shape_guard\n",
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "ddl" / "customer_segments_history_profile.sql"
    ).write_text(
        """
        CREATE TABLE customer_segments_history_profile (
            segment_history_id BIGINT,
            customer_id BIGINT,
            segment_name STRING,
            effective_date DATE
        );
        """,
        encoding="utf-8",
    )
    (
        project_dir / "mid" / "tasks" / "customer_segments_history_profile.sql"
    ).write_text(
        """
        INSERT INTO customer_segments_history_profile
        SELECT segment_history_id, customer_id, segment_name, effective_date
        FROM customer_segments_history_source;
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.86,
            "reasoning_steps": ["误认为分层历史明细事实"],
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "segment_history_id"},
                    {"name": "customer_id"},
                    {"name": "segment_name"},
                    {"name": "effective_date"},
                ],
                "others": [],
            },
            "entities": [
                {
                    "code": "CUSTOMER",
                    "type": "primary",
                    "key_columns": ["customer_id"],
                }
            ],
            "grain": {
                "entities": ["CUSTOMER"],
                "time_column": "effective_date",
                "time_period": "D",
            },
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir
            / "mid"
            / "models"
            / "customer_segments_history_profile.yaml"
        ).read_text(encoding="utf-8")
    )
    assert model["layer"] == "DIM"
    assert model["table_type"] == "dimension"
    assert model["semantic_subject"] == "CUSTOMER"
    assert model["entities"] == [
        {
            "code": "CUSTOMER",
            "type": "primary",
            "key_columns": ["customer_id"],
        }
    ]
    assert "grain" not in model


def test_run_direct_model_generation_omits_ods_entities_from_inspector(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_ods_entities"
    project_dir = tmp_path / project
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        "version: 1\nproject: direct_model_writer_ods_entities\n",
        encoding="utf-8",
    )
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "customers_source.sql"
    ).write_text(
        """
        CREATE TABLE customers_source (
            customer_id BIGINT,
            customer_name STRING
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    def fake_call_api(_self, _prompt):
        content = {
            "inferred_layer": "DIM",
            "table_type": "dimension",
            "confidence": 0.9,
            "reasoning_steps": ["客户属性表"],
            "entities": [
                {
                    "code": "CUSTOMER",
                    "type": "primary",
                    "key_columns": ["customer_id"],
                }
            ],
        }
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fake_call_api
    )

    run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (
            project_dir
            / "ods"
            / "models"
            / "internal"
            / "demo_dm"
            / "customers_source.yaml"
        ).read_text(encoding="utf-8")
    )
    assert model["layer"] == "ODS"
    assert model["table_type"] == "other"
    assert "entities" not in model
    assert "grain" not in model


def test_run_direct_model_generation_inspects_prefixed_table_in_cold_start(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "direct_model_writer_table_inspector_layer_skip"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "project": project},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    def fail_call_api(_self, _prompt):
        raise AssertionError(
            "Table inspector should not be called for prefixed tables"
        )

    monkeypatch.setattr(
        writer_module.TableInspector, "_call_api", fail_call_api
    )

    result = run_direct_model_generation(
        project,
        dry_run=False,
        llm=True,
        api_key="test",
        model="fake-layer-model",
        no_cache=True,
        show_progress=False,
    )

    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert result["table_inspector_layer_inference_attempt_count"] == 1
    assert result["table_inspector_layer_inference_count"] == 0
    assert model["layer"] == "DWD"


def test_run_catalog_metadata_write_can_dry_run_with_init_catalog(
    tmp_path, monkeypatch
):
    project = "catalog_writer_dry_run"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_catalog_metadata_write(
        project,
        dry_run=True,
        write_scope="business",
        init_catalog=True,
    )

    assert result["source"] == "catalog"
    assert result["model_change_count"] == 1
    assert not (project_dir / "business_semantics.yaml").exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()


def test_run_catalog_metadata_write_respects_business_metadata_layers(
    tmp_path, monkeypatch
):
    project = "catalog_writer_layers"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "ddl" / "dws_store_sales_daily.sql").write_text(
        """
        CREATE TABLE dws_store_sales_daily (
            store_id BIGINT,
            stat_date DATE,
            sale_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dim_store.sql").write_text(
        """
        CREATE TABLE dim_store (
            store_id BIGINT,
            store_name VARCHAR(64)
        );
        """,
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {
                        "id": "03",
                        "code": "STOR",
                        "name": "门店域",
                    }
                ],
                "business_areas": [
                    {
                        "id": "SHOP",
                        "code": "SHOP",
                        "name": "零售业务",
                    }
                ],
                "business_processes": [
                    {
                        "code": "STORE_SALES",
                        "name": "门店销售",
                        "data_domain": "03",
                        "business_area": "SHOP",
                    },
                    {
                        "code": "IGNORED_DIM_PROCESS",
                        "name": "错误维表过程",
                        "data_domain": "03",
                        "business_area": "SHOP",
                    },
                ],
                "semantic_subjects": [
                    {
                        "code": "STORE",
                        "name": "门店",
                        "data_domain": "03",
                        "business_area": "SHOP",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "models" / "dws_store_sales_daily.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_store_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "business_process": "STORE_SALES",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dim_store.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dim_store",
                "layer": "DIM",
                "table_type": "dimension",
                "semantic_subject": "STORE",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    dws_model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "dws_store_sales_daily.yaml"
        ).read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dim_store.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "data_domain" not in dws_model
    assert dws_model["business_area"] == "SHOP"
    assert dws_model["business_process"] == "STORE_SALES"
    assert "data_domain" not in dim_model
    assert "business_area" not in dim_model
    assert "business_process" not in dim_model
    assert dim_model["semantic_subject"] == "STORE"
