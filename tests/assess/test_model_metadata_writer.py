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
    run_metadata_write,
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
)


def _business_domain_config(*, domains=None, business_areas=None):
    return BusinessDomainConfig(
        domains=(
            {
                "04": DomainDef(id="04", code="TRAN", name="交易域"),
                "06": DomainDef(id="06", code="ORGN", name="机构域"),
            }
            if domains is None
            else domains
        ),
        business_areas=(
            {
                "CHNL": BusinessAreaDef(id="09", code="CHNL", name="渠道业务"),
                "PAYM": BusinessAreaDef(id="04", code="PAYM", name="支付结算"),
            }
            if business_areas is None
            else business_areas
        ),
    )


def _configure_project_root(monkeypatch, project_root):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    monkeypatch.setattr(config.core, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


def _write_split_catalog(project_dir, project, catalog):
    taxonomy = {
        "version": catalog.get("version", 1),
        "project": project,
        "data_domains": catalog.get("data_domains", []),
        "business_areas": catalog.get("business_areas", []),
    }
    if catalog.get("project_context"):
        taxonomy["project_context"] = catalog["project_context"]
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(taxonomy, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (project_dir / "business_processes.yaml").write_text(
        yaml.safe_dump(
            {
                "version": catalog.get("version", 1),
                "project": project,
                "business_processes": catalog.get(
                    "business_processes", []
                ),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "semantic_subjects.yaml").write_text(
        yaml.safe_dump(
            {
                "version": catalog.get("version", 1),
                "project": project,
                "semantic_subjects": catalog.get("semantic_subjects", []),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _catalog_payload(
    *,
    domains=None,
    areas=None,
    processes=None,
    subjects=None,
):
    return {
        "version": 1,
        "data_domains": (
            domains
            if domains is not None
            else [{"id": "04", "code": "TRAN", "name": "交易域"}]
        ),
        "business_areas": (
            areas
            if areas is not None
            else [{"id": "SHOP", "code": "SHOP", "name": "零售业务"}]
        ),
        "business_processes": processes or [],
        "semantic_subjects": subjects or [],
    }


def _order_detail_process(code="ORDER_DETAIL"):
    return {
        "code": code,
        "name": "订单明细",
        "data_domain": "04",
        "business_area": "SHOP",
    }


def _customer_subject(code="CUSTOMER"):
    return {
        "code": code,
        "name": "客户",
        "data_domain": "04",
        "business_area": "SHOP",
    }


def _write_catalog_project(
    tmp_path,
    monkeypatch,
    project,
    *,
    catalog=None,
    ddl_tables=(),
    models=None,
):
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    for table_name in ddl_tables:
        (ddl_dir / f"{table_name}.sql").write_text(
            f"CREATE TABLE {table_name} (id BIGINT);\n",
            encoding="utf-8",
        )
    if models:
        models_dir = project_dir / "mid" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        for table_name, payload in models.items():
            (models_dir / f"{table_name}.yaml").write_text(
                yaml.safe_dump(
                    payload,
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
    if catalog is not None:
        _write_split_catalog(project_dir, project, catalog)
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
    return project_dir


def _setup_catalog_discovery_model(
    tmp_path,
    monkeypatch,
    sample_lineage_data,
    project,
    *,
    model_text,
    inferred_data_domain,
    inferred_business_area,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (models_dir / "dwd_order_detail.yaml").write_text(
        model_text,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _write_split_catalog(project_dir, project, _catalog_payload())
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    data = dict(sample_lineage_data)
    data["tables"] = [
        table
        for table in sample_lineage_data["tables"]
        if table["name"] == "dwd_order_detail"
    ]
    monkeypatch.setattr(writer_module, "load_lineage_data", lambda _: data)

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    inferred_data_domain=inferred_data_domain,
                    inferred_business_area=inferred_business_area,
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
                for ctx in contexts
            ]

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    return models_dir


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
        _assert_update_model_yaml_removes_existing_business_metadata_not_in_taxonomy,
        _assert_update_model_yaml_removes_business_metadata_without_taxonomy,
        _assert_update_model_yaml_removes_invalid_business_metadata,
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

    monkeypatch.setattr(
        writer_module,
        "get_business_domain_config",
        lambda project: _business_domain_config(business_areas={}),
    )
    partial_taxonomy_result = TableInspectResult(
        table_name="dwd_transactions",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="TRAN",
        inferred_business_area="PAYM",
    )
    assert business_metadata_for_result("demo", partial_taxonomy_result) == {
        "data_domain": "04",
    }


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


def _assert_update_model_yaml_removes_business_metadata(
    tmp_path,
    monkeypatch,
    existing_business_metadata,
    *,
    with_taxonomy=True,
    result_overrides=None,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model = {
        "version": 2,
        "name": "dwd_order_detail",
        "layer": "DWD",
        "table_type": "fact",
    }
    model.update(existing_business_metadata)
    model_path.write_text(
        yaml.safe_dump(
            model,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    if with_taxonomy:
        monkeypatch.setattr(
            writer_module,
            "get_business_domain_config",
            lambda project: _business_domain_config(),
        )
    else:
        monkeypatch.setattr(config.core, "PROJECT_ROOT", project_root)
        config.clear_business_semantics_cache()
    result_kwargs = {
        "table_name": "dwd_order_detail",
        "declared_layer": "DWD",
        "inferred_layer": "DWD",
        "table_type": "fact",
        "confidence": 0.9,
        "reasoning_steps": [],
    }
    result_kwargs.update(result_overrides or {})
    result = TableInspectResult(**result_kwargs)

    update = update_model_yaml("demo", result)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["data_domain"] is None
    assert update["business_area"] is None
    assert "data_domain" not in saved
    assert "business_area" not in saved


def _assert_update_model_yaml_removes_existing_business_metadata_not_in_taxonomy(
    tmp_path, monkeypatch
):
    _assert_update_model_yaml_removes_business_metadata(
        tmp_path,
        monkeypatch,
        {"data_domain": "99", "business_area": "SHOP"},
    )


def _assert_update_model_yaml_removes_business_metadata_without_taxonomy(
    tmp_path, monkeypatch
):
    _assert_update_model_yaml_removes_business_metadata(
        tmp_path,
        monkeypatch,
        {"data_domain": "04", "business_area": "PAYM"},
        with_taxonomy=False,
    )


def _assert_update_model_yaml_removes_invalid_business_metadata(
    tmp_path, monkeypatch
):
    _assert_update_model_yaml_removes_business_metadata(
        tmp_path,
        monkeypatch,
        {"data_domain": "04", "business_area": "PAYM"},
        result_overrides={
            "inferred_data_domain": "UNKNOWN",
            "inferred_business_area": "BAD",
        },
    )


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
                "data_domain": "04",
                "business_area": "STALE",
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
    assert "data_domain" not in saved
    assert "business_area" not in saved


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
    assert "data_domain" not in saved


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
                "data_domain": "04",
                "business_area": "STALE",
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
    assert "data_domain" not in saved
    assert "business_area" not in saved


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
        "run_catalog_metadata_write",
        lambda *args, **kwargs: {
            "project": project,
            "source": "catalog",
            "paths": {"taxonomy": "business_taxonomy.yaml"},
            "written_names": ["business_processes"],
            "inspected_table_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["model_metadata_writer.py", "--project", project, "--from-catalog"],
    )

    writer_module.main()

    output_path = (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    )
    assert output_path.exists()
    assert not (tool_dir / f"model_metadata_result_{project}.json").exists()


def test_model_metadata_writer_cli_catalog_discovery_prints_paths_without_conflict(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr(
        writer_module,
        "run_catalog_discovery",
        lambda *args, **kwargs: {
            "project": project,
            "source": "llm_catalog_discovery",
            "path": str(project_dir),
            "paths": {"taxonomy": "business_taxonomy.yaml"},
            "written_names": ["business_processes"],
            "inspected_table_count": 0,
            "business_process_count": 0,
            "semantic_subject_count": 0,
            "updated": False,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--catalog-from-llm",
        ],
    )

    writer_module.main()

    assert (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    ).exists()


def test_catalog_discovery_keeps_existing_assignment_when_llm_incomplete():
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    fact_result = TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [
                {"name": "pay_amount", "business_process": "ORDER_DETAIL"},
                {"name": "refund_amount", "business_process": "REFUND"},
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )

    mapping = writer_module.catalog_discovery_model_mapping(
        "demo",
        fact_result,
        _catalog_payload(processes=[_order_detail_process()]),
        {
            "layer": "DWD",
            "table_type": "fact",
            "business_process": "ORDER_DETAIL",
        },
    )

    assert mapping["business_process"] == "ORDER_DETAIL"
    assert mapping["data_domain"] == "04"
    assert mapping["business_area"] == "SHOP"

    dimension_result = TableInspectResult(
        table_name="dwd_customer",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
    )

    mapping = writer_module.catalog_discovery_model_mapping(
        "demo",
        dimension_result,
        _catalog_payload(subjects=[_customer_subject()]),
        {
            "layer": "DWD",
            "table_type": "dimension",
            "semantic_subject": "CUSTOMER",
        },
    )

    assert mapping["semantic_subject"] == "CUSTOMER"
    assert mapping["data_domain"] == "04"
    assert mapping["business_area"] == "SHOP"


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


def test_run_catalog_discovery_writes_catalog_from_llm_results(
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

    catalog = config.load_business_semantics_catalog(project)
    assert result["source"] == "llm_catalog_discovery"
    assert result["updated"] is True
    assert (project_dir / "business_taxonomy.yaml").exists()
    assert (project_dir / "business_processes.yaml").exists()
    assert (project_dir / "semantic_subjects.yaml").exists()
    assert catalog["business_processes"][0]["code"] == "ORDER_TRANSACTION"
    assert "tables" not in catalog["business_processes"][0]
    assert catalog["semantic_subjects"][0]["code"] == "CUSTOMER"
    assert "tables" not in catalog["semantic_subjects"][0]
    assert result["model_update_count"] == 2

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
    assert fact_model["business_process"] == "ORDER_TRANSACTION"
    assert dim_model["semantic_subject"] == "CUSTOMER"
    assert result["paths"]["taxonomy"].endswith("business_taxonomy.yaml")


def test_run_catalog_discovery_does_not_write_unknown_domain_or_area(
    tmp_path, monkeypatch, sample_lineage_data
):
    project = "catalog_discovery_unknown_domain"
    models_dir = _setup_catalog_discovery_model(
        tmp_path,
        monkeypatch,
        sample_lineage_data,
        project,
        model_text="\n".join(
            [
                "version: 2",
                "name: dwd_order_detail",
                "layer: DWD",
                "table_type: fact",
                "business_process: LEGACY_PROCESS",
                "",
            ]
        ),
        inferred_data_domain="UNKNOWN_DOMAIN",
        inferred_business_area="UNKNOWN_AREA",
    )

    run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=True,
    )

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    assert "data_domain" not in model
    assert "business_area" not in model
    assert model["business_process"] == "ORDER_TRANSACTION"


def test_run_catalog_discovery_no_overwrite_does_not_write_new_catalog_codes(
    tmp_path, monkeypatch, sample_lineage_data
):
    project = "catalog_discovery_no_overwrite"
    models_dir = _setup_catalog_discovery_model(
        tmp_path,
        monkeypatch,
        sample_lineage_data,
        project,
        model_text="version: 2\nname: dwd_order_detail\nlayer: DWD\n",
        inferred_data_domain="04",
        inferred_business_area="SHOP",
    )

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=False,
    )

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    catalog = config.load_business_semantics_catalog(project)
    assert result["changed"] is False
    assert catalog["business_processes"] == []
    assert "business_process" not in model


def test_run_catalog_metadata_write_initializes_models_without_llm(
    tmp_path, monkeypatch
):
    project = "catalog_writer"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(processes=[_order_detail_process()]),
        ddl_tables=["dwd_order_detail"],
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
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(processes=[_order_detail_process()]),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_DETAIL",
            }
        },
    )
    models_dir = project_dir / "mid" / "models"

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    assert model["business_process"] == "ORDER_DETAIL"
    assert model["data_domain"] == "04"
    assert model["business_area"] == "SHOP"


def test_run_catalog_metadata_write_removes_stale_business_codes(
    tmp_path, monkeypatch
):
    project = "catalog_writer_stale_refs"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
                "business_process": "STALE_PROCESS",
            },
            "dim_customer": {
                "version": 2,
                "name": "dim_customer",
                "layer": "DIM",
                "table_type": "dimension",
                "semantic_subject": "STALE_SUBJECT",
                "business_process": "STALE_PROCESS",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    result = run_catalog_metadata_write(
        project, dry_run=False, write_scope="business"
    )

    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (models_dir / "dim_customer.yaml").read_text(encoding="utf-8")
    )
    assert result["model_update_count"] == 2
    assert "data_domain" not in fact_model
    assert "business_area" not in fact_model
    assert "business_process" not in fact_model
    assert "semantic_subject" not in fact_model
    assert "business_process" not in dim_model
    assert "semantic_subject" not in dim_model


def test_run_catalog_metadata_write_removes_subject_from_fact_models(
    tmp_path, monkeypatch
):
    project = "catalog_writer_fact_subject"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            processes=[_order_detail_process()],
            subjects=[_customer_subject("STORE")],
        ),
        ddl_tables=[
            "ads_store_metric_snapshot",
            "dwd_order_detail",
            "dwd_transactions",
        ],
        models={
            "ads_store_metric_snapshot": {
                "version": 2,
                "name": "ads_store_metric_snapshot",
                "layer": "ADS",
                "table_type": "fact",
                "semantic_subject": "STORE",
            },
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_DETAIL",
                "semantic_subject": "STORE",
            },
            "dwd_transactions": {
                "version": 2,
                "name": "dwd_transactions",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    ads_model = yaml.safe_load(
        (models_dir / "ads_store_metric_snapshot.yaml").read_text(
            encoding="utf-8"
        )
    )
    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    taxonomy_model = yaml.safe_load(
        (models_dir / "dwd_transactions.yaml").read_text(encoding="utf-8")
    )
    assert "semantic_subject" not in ads_model
    assert "semantic_subject" not in fact_model
    assert fact_model["business_process"] == "ORDER_DETAIL"
    assert taxonomy_model["data_domain"] == "04"
    assert taxonomy_model["business_area"] == "SHOP"
    assert "business_process" not in taxonomy_model
    assert "semantic_subject" not in taxonomy_model


def test_run_catalog_metadata_write_table_scope_removes_stale_business_codes(
    tmp_path, monkeypatch
):
    project = "catalog_writer_table_scope_stale_refs"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "STALE_PROCESS",
            }
        },
    )
    models_dir = project_dir / "mid" / "models"

    result = run_catalog_metadata_write(
        project, dry_run=False, write_scope="table"
    )

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    assert result["model_update_count"] == 1
    assert "business_process" not in model
    assert "semantic_subject" not in model


def test_run_catalog_metadata_write_filters_process_subject_metadata_by_taxonomy(
    tmp_path, monkeypatch
):
    project = "catalog_writer_taxonomy_filter"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            domains=[],
            areas=[],
            processes=[_order_detail_process()],
            subjects=[_customer_subject()],
        ),
        ddl_tables=["dwd_order_detail", "dwd_customer"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
                "business_process": "ORDER_DETAIL",
            },
            "dwd_customer": {
                "version": 2,
                "name": "dwd_customer",
                "layer": "DWD",
                "table_type": "dimension",
                "data_domain": "04",
                "business_area": "SHOP",
                "semantic_subject": "CUSTOMER",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (models_dir / "dwd_customer.yaml").read_text(encoding="utf-8")
    )
    assert fact_model["business_process"] == "ORDER_DETAIL"
    assert dim_model["semantic_subject"] == "CUSTOMER"
    assert "data_domain" not in fact_model
    assert "business_area" not in fact_model
    assert "data_domain" not in dim_model
    assert "business_area" not in dim_model


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
    assert result["paths"]["taxonomy"].endswith("business_taxonomy.yaml")
    assert "catalog_paths" not in result
    assert result["model_change_count"] == 1
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()


def test_run_catalog_metadata_write_respects_business_metadata_layers(
    tmp_path, monkeypatch
):
    project = "catalog_writer_layers"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            domains=[{"id": "03", "code": "STOR", "name": "门店域"}],
            areas=[{"id": "SHOP", "code": "SHOP", "name": "零售业务"}],
            processes=[
                _order_detail_process("STORE_SALES"),
                _order_detail_process("IGNORED_DIM_PROCESS"),
            ],
            subjects=[
                {
                    "code": "STORE",
                    "name": "门店",
                    "data_domain": "03",
                    "business_area": "SHOP",
                }
            ],
        ),
        ddl_tables=["dws_store_sales_daily", "dim_store"],
        models={
            "dws_store_sales_daily": {
                "version": 2,
                "name": "dws_store_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "business_process": "STORE_SALES",
            },
            "dim_store": {
                "version": 2,
                "name": "dim_store",
                "layer": "DIM",
                "table_type": "dimension",
                "semantic_subject": "STORE",
            },
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
