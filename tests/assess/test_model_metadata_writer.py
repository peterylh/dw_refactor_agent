import json
import sys
from pathlib import Path

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.generation_contract import (
    validate_generate_candidate,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    catalog_plan_for_discovery,
    catalog_plan_for_generate,
    catalog_plan_for_refresh,
)
from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    build_dwd_contexts,
    build_inspection_contexts,
    build_metric_contexts,
    metric_groups_for_model,
    metric_names_for_model,
    metric_violations,
    result_for_report,
    run_catalog_discovery,
    run_catalog_metadata_write,
    run_generate_model_metadata,
    run_metadata_write,
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
)
from tests.case_matrix import case_matrix


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
                "business_processes": catalog.get("business_processes", []),
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
    task_dir = project_dir / "mid" / "tasks"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    for table_name in ddl_tables:
        (ddl_dir / f"{table_name}.sql").write_text(
            (f"CREATE TABLE {table_name} (id BIGINT, customer_id BIGINT);\n"),
            encoding="utf-8",
        )
        (task_dir / f"{table_name}.sql").write_text(
            f"TRUNCATE TABLE {table_name};\n"
            f"INSERT INTO {table_name} SELECT 1, 1;\n",
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
        _assert_update_model_yaml_keeps_existing_business_metadata_when_inferred_code_invalid,
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
        _assert_update_model_yaml_normalizes_time_period_values,
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


@case_matrix(
    ("factory", "kwargs", "expected"),
    [
        (
            catalog_plan_for_refresh,
            {"llm": False},
            {
                "ensure_skeleton": False,
                "merge_llm_discoveries": False,
                "write_business_assignments": True,
                "overwrite_discovered_catalog": False,
            },
        ),
        (
            catalog_plan_for_refresh,
            {"llm": True},
            {
                "ensure_skeleton": True,
                "merge_llm_discoveries": True,
                "write_business_assignments": True,
                "overwrite_discovered_catalog": False,
            },
        ),
        (
            catalog_plan_for_generate,
            {"llm": True},
            {
                "ensure_skeleton": True,
                "merge_llm_discoveries": True,
                "write_business_assignments": True,
                "overwrite_discovered_catalog": False,
            },
        ),
        (
            catalog_plan_for_discovery,
            {"overwrite": True},
            {
                "ensure_skeleton": False,
                "merge_llm_discoveries": True,
                "write_business_assignments": True,
                "overwrite_discovered_catalog": True,
            },
        ),
    ],
)
def test_catalog_plan_semantics(factory, kwargs, expected):
    plan = factory(**kwargs)

    for field, value in expected.items():
        assert getattr(plan, field) is value


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

    reclassified_dwd = TableInspectResult(
        table_name="order_activity",
        declared_layer="DIM",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [{"name": "order_count_1d"}],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )

    assert metric_violations(reclassified_dwd) == [
        {
            "table": "order_activity",
            "column": "order_count_1d",
            "metric_type": "derived",
            "reason": "",
            "confidence": 0.0,
        }
    ]
    assert (
        metric_violations(
            reclassified_dwd,
            applied_layer="DWD",
            applied_table_type="other",
        )
        == []
    )

    fallback_to_existing_type = TableInspectResult(
        table_name="dwd_order_stage",
        declared_layer="DWD",
        inferred_layer="OTHER",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [{"name": "order_count_1d"}],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )
    existing_model = {"layer": "DWD", "table_type": "other"}

    assert (
        result_for_report(
            fallback_to_existing_type,
            existing_model=existing_model,
        )["violations"]
        == []
    )

    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    assert (
        writer_module._violation_count(
            [fallback_to_existing_type],
            existing_model_metadata={
                fallback_to_existing_type.table_name: existing_model
            },
        )
        == 0
    )


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
                "execution": {
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
    assert saved["execution"]["materialized"] == "incremental"
    assert "config" not in saved
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
                "execution": {
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
    assert saved["execution"]["materialized"] == "incremental"
    assert "config" not in saved
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


def _assert_update_model_yaml_keeps_existing_business_metadata_when_inferred_code_invalid(
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
        inferred_data_domain="UNKNOWN",
        inferred_business_area="BAD",
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


def _assert_update_model_yaml_normalizes_time_period_values(
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
        grain={
            "entities": ["CAMPAIGN"],
            "time_column": "ghost_time",
        },
        validation={
            "duplicate_columns": ["campaign_id"],
        },
    )

    update_model_yaml("demo", blocked, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["grain"]["entities"] == ["CAMP"]
    assert saved["grain"]["time_column"] == "start_date"
    assert "entities" not in saved


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
    assert update["reason"] == "validation_blocked_contract_change"
    assert saved["atomic_metrics"] == ["quantity"]
    assert saved["calculated_metrics"] == ["subtotal"]


@pytest.mark.parametrize(
    (
        "existing_layer",
        "existing_type",
        "inferred_layer",
        "inferred_type",
        "confidence",
        "validation",
        "expected_reason",
        "partial_write",
    ),
    [
        (
            "DWS",
            "",
            "DWS",
            "fact",
            0.95,
            {"missing_columns": ["sale_amount"]},
            "validation_blocked_table_metadata_only",
            True,
        ),
        (
            "DWD",
            "fact",
            "DWD",
            "fact",
            0.9,
            {"ddl_columns_unavailable": ["unavailable"]},
            "validation_blocked_table_metadata_only",
            True,
        ),
        (
            "DWD",
            "fact",
            "DIM",
            "dimension",
            0.9,
            {"unknown_columns": ["ghost"]},
            "validation_blocked_contract_change",
            False,
        ),
        (
            "DWD",
            "fact",
            "DWD",
            "fact",
            0.9,
            {
                "inconsistent_upstream_metric_layers": [
                    "metric_count<-entity_metrics.metric_count"
                ]
            },
            "validation_blocked",
            False,
        ),
        (
            "DWD",
            "fact",
            "DIM",
            "dimension",
            0.01,
            {},
            "resolution_requires_reinspection",
            False,
        ),
    ],
    ids=(
        "missing-columns",
        "ddl-unavailable-fact",
        "cross-contract",
        "upstream-metric-layer",
        "low-confidence",
    ),
)
def test_update_model_yaml_blocked_contract_scenarios(
    tmp_path,
    existing_layer,
    existing_type,
    inferred_layer,
    inferred_type,
    confidence,
    validation,
    expected_reason,
    partial_write,
):
    existing = {
        "version": 2,
        "name": "sales_detail",
        "layer": existing_layer,
        "atomic_metrics": ["existing_metric"],
    }
    if existing_type:
        existing["table_type"] = existing_type
    result = TableInspectResult(
        table_name="sales_detail",
        declared_layer=existing_layer,
        inferred_layer=inferred_layer,
        table_type=inferred_type,
        confidence=confidence,
        reasoning_steps=[],
        validation=validation,
    )

    update = update_model_yaml(
        "demo",
        result,
        dry_run=True,
        existing_model=existing,
        path=tmp_path / "sales_detail.yaml",
        include_model_metadata=True,
    )

    assert result.status == "blocked"
    assert update["reason"] == expected_reason
    assert update["metric_changed"] is False
    if partial_write:
        assert update["model_metadata"]["table_type"] == "fact"
        assert update["model_metadata"]["atomic_metrics"] == [
            "existing_metric"
        ]
    else:
        assert update["model_metadata"] == existing


def test_run_metadata_write_reuses_table_inspector(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    created_cache_files = []
    seen_dws_contexts = []

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
            if contexts and contexts[0].layer == "DWS":
                seen_dws_contexts.extend(contexts)
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
    original_pipeline = writer_module.run_inspection_pipeline
    pipeline_calls = []

    def tracking_pipeline(*args, **kwargs):
        pipeline_calls.append(
            {
                "project": args[0],
                "base_model_metadata": kwargs.get("base_model_metadata"),
                "metric_groups": kwargs.get("metric_groups"),
            }
        )
        return original_pipeline(*args, **kwargs)

    monkeypatch.setattr(
        writer_module, "run_inspection_pipeline", tracking_pipeline
    )

    result = run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True
    )

    updates_by_table = {
        update["table"]: update for update in result["model_updates"]
    }

    assert result["inspected_table_count"] == 3
    assert result["write_scope"] == "all"
    assert result["metric_table_count"] == 2
    assert result["metadata_only_table_count"] == 1
    assert result["dwd_table_count"] == 1
    assert result["dws_table_count"] == 1
    assert result["dim_table_count"] == 1
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
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["project"] == isolated_writer_project
    assert (
        pipeline_calls[0]["base_model_metadata"]["dwd_customer"]["layer"]
        == "DWD"
    )
    assert pipeline_calls[0]["metric_groups"] is None
    assert created_cache_files[0] == config.assess_cache_path(
        isolated_writer_project, "inspect.json"
    )
    assert updates_by_table["dwd_customer"]["layer"] == "DIM"
    assert updates_by_table["dwd_customer"]["table_type"] == "dimension"
    assert updates_by_table["dwd_customer"]["updated"] is False
    assert updates_by_table["dws_store_sales_daily"]["table"] == (
        "dws_store_sales_daily"
    )
    assert seen_dws_contexts[0].upstream_metric_groups["dwd_order_detail"] == {
        "atomic_metrics": ["pay_amt"],
        "derived_metrics": [_expected_pay_amt_1d_metric()],
        "calculated_metrics": ["gross_profit"],
    }
    assert result["skipped_model_updates"] == []


def test_model_metadata_writer_cli_dispatches_refresh_and_generate_modes(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
        },
    )

    calls = []

    def fake_catalog_write(*args, **kwargs):
        calls.append(("refresh", args, kwargs))
        return {
            "project": project,
            "source": "catalog",
            "paths": {"taxonomy": "business_taxonomy.yaml"},
            "written_names": ["business_processes"],
            "inspected_table_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
        }

    def fake_generate(*args, **kwargs):
        calls.append(("generate", args, kwargs))
        return {
            "project": project,
            "source": "direct_model_generation",
            "planned_catalog_written_names": [],
            "catalog_init_written_names": [],
            "planned_deleted_model_files": [],
            "model_change_count": 0,
            "model_update_count": 0,
        }

    def fake_metadata_write(*args, **kwargs):
        calls.append(("refresh_llm", args, kwargs))
        return {
            "project": project,
            "write_scope": kwargs["write_scope"],
            "inspected_table_count": 0,
            "metric_table_count": 0,
            "metadata_only_table_count": 0,
            "dwd_table_count": 0,
            "dws_table_count": 0,
            "dim_table_count": 0,
            "fact_table_count": 0,
            "metric_count": 0,
            "atomic_metric_count": 0,
            "derived_metric_count": 0,
            "calculated_metric_count": 0,
            "non_atomic_metric_violation_count": 0,
            "metadata_warning_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
        }

    monkeypatch.setattr(
        writer_module,
        "run_catalog_metadata_write",
        fake_catalog_write,
    )
    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        fake_generate,
    )
    monkeypatch.setattr(
        writer_module,
        "run_metadata_write",
        fake_metadata_write,
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")

    monkeypatch.setattr(
        sys,
        "argv",
        ["model_metadata_writer.py", "--project", project],
    )

    writer_module.main()
    assert calls[-1][0] == "refresh"
    assert calls[-1][2]["write_scope"] == "business"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "refresh",
            "--llm",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "refresh_llm"
    assert calls[-1][2]["write_scope"] == "all"
    assert calls[-1][2]["update_catalog"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "generate",
            "--dry-run",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "generate"
    assert calls[-1][2]["write_scope"] == "all"
    assert calls[-1][2]["replace_existing_models"] is True
    assert calls[-1][2]["update_catalog"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "generate",
            "--llm",
            "--dry-run",
            "--base-url",
            "https://api.deepseek.com",
            "--max-retries",
            "3",
            "--parallel",
            "4",
            "--request-timeout",
            "12",
            "--no-cache",
            "--quiet",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "generate"
    assert calls[-1][2]["api_key"] == "test"
    assert calls[-1][2]["base_url"] == (
        "https://api.deepseek.com/chat/completions"
    )
    assert calls[-1][2]["max_retries"] == 3
    assert calls[-1][2]["parallelism"] == 4
    assert calls[-1][2]["request_timeout"] == 12
    assert calls[-1][2]["no_cache"] is True
    assert calls[-1][2]["show_progress"] is False

    output_path = (
        project_dir
        / "artifacts"
        / "assessment"
        / ("model_metadata_result.json")
    )
    assert output_path.exists()


def test_model_metadata_writer_cli_rejects_catalog_mode(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "catalog",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        writer_module.main()
    assert exc_info.value.code == 2


def test_model_metadata_writer_cli_fails_when_generate_publication_is_blocked(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        lambda *_args, **_kwargs: {
            "project": project,
            "source": "direct_model_generation",
            "planned_catalog_written_names": [],
            "catalog_init_written_names": [],
            "planned_deleted_model_files": [],
            "model_change_count": 1,
            "model_update_count": 0,
            "publication": {
                "status": "blocked",
                "published": False,
                "validation": {"errors": [{"type": "invalid_model"}]},
            },
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
            "generate",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        writer_module.main()

    assert "发布被阻断" in str(exc_info.value)
    output_path = (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    )
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["publication"]["status"] == "blocked"


def test_run_direct_model_generation_delegates_to_generate_entrypoint(
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    calls = []

    def fake_generate(*args, **kwargs):
        calls.append((args, kwargs))
        return {"source": "direct_model_generation"}

    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        fake_generate,
    )

    result = writer_module.run_direct_model_generation("demo", dry_run=True)

    assert result == {"source": "direct_model_generation"}
    assert calls == [(("demo",), {"dry_run": True})]


def test_run_generate_model_metadata_dry_run_missing_catalog_uses_in_memory_skeleton(
    tmp_path, monkeypatch
):
    project = "generate_metadata_dry_run"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_existing": {
                "version": 2,
                "name": "dwd_existing",
                "layer": "DWD",
            }
        },
    )
    existing_model = project_dir / "mid" / "models" / "dwd_existing.yaml"

    result = run_generate_model_metadata(project, dry_run=True)

    assert result["catalog_initialized"] is True
    assert result["catalog_init_written_names"] == []
    assert result["planned_catalog_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["model_change_count"] == 1
    assert result["model_update_count"] == 0
    assert str(existing_model) in result["planned_deleted_model_files"]
    assert existing_model.exists()
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()


def test_run_generate_model_metadata_dry_run_llm_uses_generated_model_baseline(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_metadata_dry_run_llm"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    lineage_data = {
        "tables": [
            {
                "name": "dwd_order_detail",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
        ],
        "edges": [],
        "indirect_edges": [],
    }
    seen_contexts = []

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            seen_contexts.extend(contexts)
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    columns={
                        "atomic_metrics": [],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda _: lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=True,
    )

    assert result["llm_result"]["inspected_table_count"] == 1
    assert result["llm_result"]["model_update_count"] == 0
    assert seen_contexts[0].layer == "DWD"
    assert result["llm_result"]["model_updates"][0]["previous_table_type"] == (
        "other"
    )
    assert result["llm_result"]["model_updates"][0]["table_type"] == "fact"
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert saved["layer"] == "DWS"


def test_run_generate_model_metadata_missing_catalog_writes_skeleton_and_models(
    tmp_path, monkeypatch
):
    project = "generate_metadata_write"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
    )

    result = run_generate_model_metadata(project, dry_run=False)

    assert result["catalog_initialized"] is True
    assert result["catalog_init_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["planned_catalog_written_names"] == []
    assert (project_dir / "business_taxonomy.yaml").exists()
    assert (project_dir / "business_processes.yaml").exists()
    assert (project_dir / "semantic_subjects.yaml").exists()

    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert result["model_update_count"] == 1
    assert model["name"] == "dwd_order_detail"
    assert model["layer"] == "DWD"
    assert model["execution"] == {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }
    assert "config" not in model


def test_run_generate_model_metadata_derives_execution_from_task_sql(
    tmp_path, monkeypatch
):
    project = "generate_execution_contracts"
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir = project_dir / "mid" / "tasks"
    full_refresh_dir = task_dir / "full_refresh"
    ddl_dir.mkdir(parents=True)
    full_refresh_dir.mkdir(parents=True)
    for table_name in ("dwd_full", "dwd_daily", "dwd_companion"):
        (ddl_dir / f"{table_name}.sql").write_text(
            (
                f"CREATE TABLE {table_name} "
                "(id BIGINT, date DATE, processing_status INT, "
                "business_date DATE);\n"
            ),
            encoding="utf-8",
        )
    (task_dir / "dwd_full.sql").write_text(
        "TRUNCATE TABLE demo.dwd_full;\n"
        "INSERT INTO demo.dwd_full SELECT 1, CURDATE();\n",
        encoding="utf-8",
    )
    daily_sql = (
        "SET @etl_date = COALESCE(@etl_date, CURDATE());\n"
        "TRUNCATE TABLE demo.staging_cleanup;\n"
        "DELETE FROM demo.{table} "
        "WHERE processing_status = 1 "
        "AND business_date = CAST(@etl_date AS DATE);\n"
        "INSERT INTO demo.{table} SELECT 1, @etl_date;\n"
    )
    (task_dir / "dwd_daily.sql").write_text(
        daily_sql.format(table="dwd_daily"),
        encoding="utf-8",
    )
    (task_dir / "dwd_companion.sql").write_text(
        daily_sql.format(table="dwd_companion"),
        encoding="utf-8",
    )
    (full_refresh_dir / "dwd_companion_full_refresh.sql").write_text(
        "TRUNCATE TABLE demo.dwd_companion;\n"
        "INSERT INTO demo.dwd_companion SELECT 1, CURDATE();\n",
        encoding="utf-8",
    )
    _write_split_catalog(project_dir, project, _catalog_payload())
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "naming_config": "naming_config.yaml"},
    )

    result = run_generate_model_metadata(project, dry_run=False)
    models = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (project_dir / "mid" / "models").glob("*.yaml")
    }

    assert result["publication"]["status"] == "published"
    assert models["dwd_full"]["execution"] == {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }
    assert models["dwd_daily"]["execution"] == {
        "materialized": "incremental",
        "full_refresh_strategy": "replay_slices",
        "slice": {
            "param": "etl_date",
            "column": "business_date",
            "period": "D",
        },
    }
    assert models["dwd_companion"]["execution"] == {
        "materialized": "incremental",
        "full_refresh_strategy": "companion",
        "slice": {
            "param": "etl_date",
            "column": "business_date",
            "period": "D",
        },
    }


def test_run_generate_model_metadata_blocks_unresolved_execution_contract(
    tmp_path, monkeypatch
):
    project = "generate_execution_blocked"
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
                "execution": {"materialized": "full"},
            }
        },
    )
    task_dir = project_dir / "mid" / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "dwd_order_detail.sql").write_text(
        "INSERT INTO demo.dwd_order_detail SELECT 1, 1;\n",
        encoding="utf-8",
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    result = run_generate_model_metadata(project, dry_run=False)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["validation"]["errors"] == [
        {
            "type": "execution_slice_missing",
            "table": "dwd_order_detail",
            "message": (
                "incremental replay_slices model requires execution.slice"
            ),
        }
    ]
    assert result["deleted_model_files"] == []
    assert saved["execution"] == {"materialized": "full"}


def test_run_generate_model_metadata_blocks_dwd_without_task_sql(
    tmp_path, monkeypatch
):
    project = "generate_execution_task_missing"
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
                "execution": {"materialized": "full"},
            }
        },
    )
    (project_dir / "mid" / "tasks" / "dwd_order_detail.sql").unlink()
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    result = run_generate_model_metadata(project, dry_run=False)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["validation"]["errors"] == [
        {
            "type": "execution_task_missing",
            "table": "dwd_order_detail",
            "message": "DWD execution cannot be inferred without task SQL",
        }
    ]
    assert saved["execution"] == {"materialized": "full"}


@pytest.mark.parametrize(
    ("process_codes", "expected_error", "expected_message"),
    [
        (
            [],
            "business_process_missing",
            "fact inspection did not identify a business process",
        ),
        (
            ["ORDER", "REFUND"],
            "business_process_ambiguous",
            (
                "fact inspection identified multiple business processes: "
                "ORDER, REFUND"
            ),
        ),
    ],
    ids=("missing", "ambiguous"),
)
def test_generate_publication_blocks_unresolved_business_processes(
    tmp_path,
    process_codes,
    expected_error,
    expected_message,
):
    task_path = tmp_path / "dwd_order_detail.sql"
    task_path.write_text(
        "TRUNCATE TABLE dwd_order_detail;\n",
        encoding="utf-8",
    )
    validation = validate_generate_candidate(
        {
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
            }
        },
        {
            "dwd_order_detail": {
                "ddl": {"columns": [{"name": "id"}]},
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={
            "tables": [
                {
                    "table_name": "dwd_order_detail",
                    "status": "passed",
                    "table_type": "fact",
                    "columns": {
                        "atomic_metrics": [
                            {
                                "name": f"metric_{index}",
                                "business_process": code,
                            }
                            for index, code in enumerate(process_codes)
                        ]
                    },
                }
            ]
        },
        catalog={
            "business_processes": [
                {"code": "ORDER"},
                {"code": "REFUND"},
            ]
        },
    )

    assert validation["status"] == "blocked"
    assert validation["errors"] == [
        {
            "type": expected_error,
            "table": "dwd_order_detail",
            "message": expected_message,
        }
    ]


def test_generate_publication_requires_complete_llm_mid_coverage(tmp_path):
    task_path = tmp_path / "dwd_order_detail.sql"
    task_path.write_text(
        "TRUNCATE TABLE dwd_order_detail;\n",
        encoding="utf-8",
    )
    validation = validate_generate_candidate(
        {
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
            }
        },
        {
            "dwd_order_detail": {
                "ddl": {"columns": [{"name": "id"}]},
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={"tables": []},
        catalog={},
    )

    assert validation["errors"] == [
        {
            "type": "llm_inspection_missing",
            "table": "dwd_order_detail",
            "message": (
                "LLM generate requires inspection coverage for every MID model"
            ),
        }
    ]


def test_generate_publication_allows_fact_foreign_entities_without_relationship(
    tmp_path,
):
    task_path = tmp_path / "dwd_order_detail.sql"
    task_path.write_text(
        "TRUNCATE TABLE dwd_order_detail;\n",
        encoding="utf-8",
    )
    validation = validate_generate_candidate(
        {
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
                "entities": [
                    {
                        "code": "ORDER_DETAIL",
                        "type": "primary",
                        "key_columns": ["id"],
                    },
                    {
                        "code": "CUSTOMER",
                        "type": "foreign",
                        "key_columns": ["customer_id"],
                    },
                ],
                "business_process": "ORDER",
            }
        },
        {
            "dwd_order_detail": {
                "ddl": {
                    "columns": [
                        {"name": "id"},
                        {"name": "customer_id"},
                    ]
                },
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={
            "tables": [
                {
                    "table_name": "dwd_order_detail",
                    "status": "passed",
                    "table_type": "fact",
                    "columns": {
                        "atomic_metrics": [
                            {"name": "id", "business_process": "ORDER"}
                        ]
                    },
                }
            ]
        },
        catalog={"business_processes": [{"code": "ORDER"}]},
    )

    assert validation == {
        "status": "passed",
        "error_count": 0,
        "errors": [],
        "blocked_tables": [],
    }


def test_generate_publication_validates_entity_keys_and_grain_references():
    validation = validate_generate_candidate(
        {
            "dim_customer": {
                "name": "dim_customer",
                "layer": "DIM",
                "table_type": "dimension",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
                "entities": [
                    {
                        "code": "CUSTOMER",
                        "type": "primary",
                        "key_columns": [],
                    }
                ],
                "semantic_subject": "CUSTOMER",
                "grain": {
                    "entities": ["GHOST"],
                    "additional_key_columns": ["ghost_id"],
                    "time_column": "ghost_date",
                },
            }
        },
        {
            "dim_customer": {
                "ddl": {"columns": [{"name": "customer_id"}]},
                "tasks": [],
            }
        },
        llm_result={
            "tables": [
                {
                    "table_name": "dim_customer",
                    "status": "passed",
                    "table_type": "dimension",
                    "columns": {},
                }
            ]
        },
        catalog={"semantic_subjects": [{"code": "CUSTOMER"}]},
    )

    assert validation["status"] == "blocked"
    assert {error["type"] for error in validation["errors"]} == {
        "entity_key_missing",
        "grain_entity_unknown",
        "grain_column_missing",
    }


def test_generate_file_set_publication_rolls_back_on_replace_failure(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    catalog_path = tmp_path / "business_processes.yaml"
    model_path = tmp_path / "dwd_order_detail.yaml"
    catalog_path.write_text("catalog: old\n", encoding="utf-8")
    model_path.write_text("model: old\n", encoding="utf-8")
    original_replace = Path.replace
    staged_replace_count = 0

    def flaky_replace(self, target):
        nonlocal staged_replace_count
        if self.name.endswith(".staged"):
            staged_replace_count += 1
            if staged_replace_count == 2:
                raise OSError("simulated replacement failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    with pytest.raises(OSError, match="simulated replacement failure"):
        writer_module._transactional_publish_files(
            {
                catalog_path: "catalog: new\n",
                model_path: "model: new\n",
            },
            delete_paths=[],
        )

    assert catalog_path.read_text(encoding="utf-8") == "catalog: old\n"
    assert model_path.read_text(encoding="utf-8") == "model: old\n"
    assert list(tmp_path.glob(".*.staged")) == []
    assert list(tmp_path.glob(".*.backup")) == []


def test_generate_asset_collection_does_not_read_existing_model_yaml(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_ignores_existing_model_content"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "ADS",
            }
        },
    )
    original_read_text = Path.read_text

    def reject_model_read(self, *args, **kwargs):
        if "models" in self.parts and self.suffix == ".yaml":
            raise OSError("existing model content must not be read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_model_read)

    assets = writer_module._generate_model_table_assets(project)

    assert assets["dwd_order_detail"]["ddl"]["exists"] is True
    assert assets["dwd_order_detail"]["model"] is None
    assert (project_dir / "mid" / "models" / "dwd_order_detail.yaml").exists()


def test_run_generate_model_metadata_uses_asset_role_for_prefixless_base(
    tmp_path, monkeypatch
):
    project = "generate_metadata_asset_role"
    project_dir = tmp_path / project
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "ads" / "ddl").mkdir(parents=True)
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "order_event.sql"
    ).write_text(
        "CREATE TABLE order_event (id BIGINT);\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "order_detail.sql").write_text(
        "CREATE TABLE order_detail (id BIGINT);\n",
        encoding="utf-8",
    )
    (project_dir / "ads" / "ddl" / "order_dashboard.sql").write_text(
        "CREATE TABLE order_dashboard (id BIGINT);\n",
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
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_generate_model_metadata(project, dry_run=True)
    updates = {update["table"]: update for update in result["model_updates"]}

    assert updates["order_event"]["layer"] == "ODS"
    assert updates["order_detail"]["layer"] == "DWD"
    assert updates["order_dashboard"]["layer"] == "ADS"
    assert (
        "/ods/models/internal/demo_dm/order_event.yaml"
        in updates["order_event"]["path"]
    )
    assert "/mid/models/order_detail.yaml" in updates["order_detail"]["path"]
    assert (
        "/ads/models/order_dashboard.yaml"
        in updates["order_dashboard"]["path"]
    )


def _write_taxonomy_only(project_dir, project):
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {"id": "04", "code": "TRAN", "name": "交易域"}
                ],
                "business_areas": [
                    {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _install_generate_catalog_fake_inspector(
    monkeypatch,
    writer_module,
    *,
    table_names,
    result_factory,
):
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables(*table_names),
    )

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                result = result_factory(ctx)
                if result is not None:
                    results.append(result)
            return results

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)


def _generate_catalog_fact_result(ctx, *, validation=None):
    return TableInspectResult(
        table_name=ctx.table_name,
        declared_layer=ctx.layer,
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        validation=validation or {},
        inferred_data_domain="04",
        inferred_business_area="SHOP",
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


def _generate_catalog_dimension_result(ctx):
    return TableInspectResult(
        table_name=ctx.table_name,
        declared_layer=ctx.layer,
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="04",
        inferred_business_area="SHOP",
        entities=[
            {
                "code": "CUSTOMER",
                "type": "primary",
                "name": "客户",
                "key_columns": ["customer_id"],
            }
        ],
    )


def _generate_catalog_result_for_context(ctx):
    if ctx.table_name == "dwd_order_detail":
        return _generate_catalog_fact_result(ctx)
    if ctx.table_name == "dim_customer":
        return _generate_catalog_dimension_result(ctx)
    return None


def test_run_generate_model_metadata_llm_dry_run_plans_catalog_merge(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_dry_run"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=_generate_catalog_result_for_context,
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=True,
    )
    planned_codes = {
        update["code"] for update in result["planned_catalog_updates"]
    }
    processes = yaml.safe_load(
        (project_dir / "business_processes.yaml").read_text(encoding="utf-8")
    )
    subjects = yaml.safe_load(
        (project_dir / "semantic_subjects.yaml").read_text(encoding="utf-8")
    )

    assert result["catalog_change_count"] == 2
    assert result["catalog_update"]["updated"] is False
    assert result["catalog_update"]["planned_written_names"] == [
        "business_processes",
        "semantic_subjects",
    ]
    assert planned_codes == {"ORDER_TRANSACTION", "CUSTOMER"}
    assert processes["business_processes"] == []
    assert subjects["semantic_subjects"] == []


def test_run_generate_model_metadata_llm_writes_catalog_merge(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_write"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=_generate_catalog_result_for_context,
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_change_count"] == 2
    assert result["catalog_update"]["updated"] is True
    assert result["catalog_update"]["written_names"] == [
        "business_processes",
        "semantic_subjects",
    ]
    assert catalog["business_processes"] == [
        {
            "code": "ORDER_TRANSACTION",
            "name": "Order Transaction",
            "data_domain": "04",
            "business_area": "SHOP",
        }
    ]
    assert catalog["semantic_subjects"] == [
        {
            "code": "CUSTOMER",
            "name": "客户",
            "data_domain": "04",
            "business_area": "SHOP",
        }
    ]
    fact_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )
    dimension_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dim_customer.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fact_model["business_process"] == "ORDER_TRANSACTION"
    assert dimension_model["semantic_subject"] == "CUSTOMER"


def test_run_generate_model_metadata_preserves_governed_catalog_code_case(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_catalog_code_case"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            processes=[
                {
                    "code": "order_transaction",
                    "name": "订单交易",
                    "data_domain": "04",
                    "business_area": "SHOP",
                }
            ]
        ),
        ddl_tables=["dwd_order_detail"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail"],
        result_factory=lambda ctx: _generate_catalog_fact_result(ctx),
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    catalog = config.load_business_semantics_catalog(project)
    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result["publication"]["status"] == "published"
    assert result["catalog_change_count"] == 0
    assert catalog["business_processes"][0]["code"] == "order_transaction"
    assert model["business_process"] == "order_transaction"


def test_run_generate_model_metadata_update_catalog_false_skips_catalog_merge(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_disabled"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail"],
        result_factory=lambda ctx: _generate_catalog_fact_result(ctx),
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
        update_catalog=False,
    )

    assert result["catalog_initialized"] is False
    assert result["catalog_update"] is None
    assert result["catalog_change_count"] == 0
    assert result["planned_catalog_updates"] == []
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()


def test_run_generate_model_metadata_llm_catalog_merge_skips_blocked_results(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_blocked"
    _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
    )

    def result_factory(ctx):
        if ctx.table_name == "dwd_order_detail":
            return _generate_catalog_fact_result(
                ctx,
                validation={"unknown_columns": ["ghost_metric"]},
            )
        if ctx.table_name == "dim_customer":
            return _generate_catalog_dimension_result(ctx)
        return None

    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=result_factory,
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_change_count"] == 1
    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["published"] is False
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def _refresh_catalog_models(*table_names):
    return {
        table_name: {
            "version": 2,
            "name": table_name,
            "layer": "DIM" if table_name.startswith("dim_") else "DWD",
            "table_type": (
                "dimension" if table_name.startswith("dim_") else "fact"
            ),
        }
        for table_name in table_names
    }


def test_run_metadata_write_llm_dry_run_plans_catalog_merge_and_skeleton(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "refresh_llm_catalog_dry_run"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail", "dim_customer"],
        models=_refresh_catalog_models("dwd_order_detail", "dim_customer"),
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=_generate_catalog_result_for_context,
    )

    result = run_metadata_write(
        project,
        api_key="test",
        dry_run=True,
    )
    planned_codes = {
        update["code"] for update in result["planned_catalog_updates"]
    }

    assert result["catalog_initialized"] is True
    assert result["planned_catalog_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["catalog_change_count"] == 2
    assert result["catalog_update"]["updated"] is False
    assert result["catalog_update"]["planned_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert planned_codes == {"ORDER_TRANSACTION", "CUSTOMER"}
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()

    disabled = run_metadata_write(
        project,
        api_key="test",
        dry_run=False,
        update_catalog=False,
    )

    assert disabled["catalog_initialized"] is False
    assert disabled["catalog_update"] is None
    assert disabled["catalog_change_count"] == 0
    assert disabled["planned_catalog_updates"] == []
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()


def test_run_metadata_write_llm_writes_catalog_merge_without_expanding_taxonomy(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "refresh_llm_catalog_write"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dwd_event_detail", "dim_customer"],
        models=_refresh_catalog_models(
            "dwd_order_detail",
            "dwd_event_detail",
            "dim_customer",
        ),
    )

    def result_factory(ctx):
        if ctx.table_name == "dwd_order_detail":
            result = _generate_catalog_fact_result(ctx)
            result.inferred_data_domain = "LLM_DOMAIN"
            result.inferred_business_area = "LLM_AREA"
            return result
        if ctx.table_name == "dwd_event_detail":
            result = _generate_catalog_fact_result(
                ctx,
                validation={"unknown_columns": ["ghost_metric"]},
            )
            result.columns["atomic_metrics"][0]["business_process"] = (
                "EVENT_COMPLETION"
            )
            return result
        if ctx.table_name == "dim_customer":
            return _generate_catalog_dimension_result(ctx)
        return None

    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dwd_event_detail", "dim_customer"],
        result_factory=result_factory,
    )

    result = run_metadata_write(
        project,
        api_key="test",
        dry_run=False,
    )
    taxonomy = yaml.safe_load(
        (project_dir / "business_taxonomy.yaml").read_text(encoding="utf-8")
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_change_count"] == 2
    assert result["catalog_update"]["updated"] is True
    assert result["catalog_update"]["written_names"] == [
        "business_processes",
        "semantic_subjects",
    ]
    assert taxonomy["data_domains"] == [
        {"id": "04", "code": "TRAN", "name": "交易域"}
    ]
    assert taxonomy["business_areas"] == [
        {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
    ]
    assert catalog["business_processes"] == [
        {
            "code": "ORDER_TRANSACTION",
            "name": "Order Transaction",
            "data_domain": "",
            "business_area": "",
        }
    ]
    assert catalog["semantic_subjects"] == [
        {
            "code": "CUSTOMER",
            "name": "客户",
            "data_domain": "04",
            "business_area": "SHOP",
        }
    ]


def _write_single_writer_project(
    tmp_path,
    monkeypatch,
    project,
    *,
    mid_tables=("dwd_order_detail",),
    include_ods_ads=False,
    existing_models=None,
):
    project_dir = tmp_path / project
    mid_ddl_dir = project_dir / "mid" / "ddl"
    mid_task_dir = project_dir / "mid" / "tasks"
    mid_ddl_dir.mkdir(parents=True, exist_ok=True)
    mid_task_dir.mkdir(parents=True, exist_ok=True)
    for table_name in mid_tables:
        (mid_ddl_dir / f"{table_name}.sql").write_text(
            f"CREATE TABLE {table_name} (id BIGINT);\n",
            encoding="utf-8",
        )
        (mid_task_dir / f"{table_name}.sql").write_text(
            f"TRUNCATE TABLE {table_name};\n"
            f"INSERT INTO {table_name} SELECT 1;\n",
            encoding="utf-8",
        )
    if include_ods_ads:
        ods_ddl_dir = (
            project_dir / "ods" / "ddl" / "internal" / "single_writer_dm"
        )
        ods_ddl_dir.mkdir(parents=True, exist_ok=True)
        (ods_ddl_dir / "ods_customer.sql").write_text(
            "CREATE TABLE ods_customer (id BIGINT);\n",
            encoding="utf-8",
        )
        ads_ddl_dir = project_dir / "ads" / "ddl"
        ads_ddl_dir.mkdir(parents=True, exist_ok=True)
        (ads_ddl_dir / "ads_sales_dashboard.sql").write_text(
            "CREATE TABLE ads_sales_dashboard (id BIGINT);\n",
            encoding="utf-8",
        )
    for table_name, payload in (existing_models or {}).items():
        model_dir = project_dir / "mid" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / f"{table_name}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    _write_split_catalog(project_dir, project, _catalog_payload())
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
            "catalog": "internal",
            "db": "single_writer_dm",
            "naming_config": "naming_config.yaml",
        },
    )
    return project_dir


def _lineage_for_tables(*table_names):
    return {
        "tables": [
            {
                "name": table_name,
                "full_name": f"demo.{table_name}",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            for table_name in table_names
        ],
        "edges": [],
        "indirect_edges": [],
    }


@pytest.mark.parametrize(
    (
        "project",
        "existing_contract",
        "inspection",
        "expected_reason",
    ),
    [
        (
            "generate_single_writer_blocked",
            ("DWS", "fact"),
            ("OTHER", "dimension", {"unknown_columns": ["ghost_id"]}, 0.2),
            "validation_blocked",
        ),
        (
            "generate_single_writer_partial_block",
            ("DWD", "other"),
            (
                "DWS",
                "fact",
                {"invalid_base_metrics": ["sale_amount:subtotal"]},
                0.95,
            ),
            "validation_blocked_contract_change",
        ),
    ],
    ids=["invalid-columns", "invalid-metrics"],
)
def test_generate_single_writer_preserves_base_contract_when_llm_blocked(
    tmp_path,
    monkeypatch,
    project,
    existing_contract,
    inspection,
    expected_reason,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    existing_layer, existing_table_type = existing_contract
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        existing_models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": existing_layer,
                "table_type": existing_table_type,
            }
        },
    )
    inferred_layer, table_type, validation, confidence = inspection

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer=inferred_layer,
                    table_type=table_type,
                    validation=validation,
                    confidence=confidence,
                    reasoning_steps=[],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dwd_order_detail"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    saved = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result["llm_result"]["blocked_table_count"] == 1
    assert result["llm_result"]["skipped_model_updates"][0]["reason"] == (
        expected_reason
    )
    assert result["publication"]["status"] == "blocked"
    assert result["deleted_model_files"] == []
    assert saved["layer"] == existing_layer
    assert saved["table_type"] == existing_table_type
    assert "atomic_metrics" not in saved


def test_generate_single_writer_pass_keeps_ods_ads_base_models(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_boundaries"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        mid_tables=("dwd_order_detail",),
        include_ods_ads=True,
    )
    seen_contexts = []

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            seen_contexts.extend(contexts)
            return [
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
                                "name": "id",
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

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables(
            "ods_customer",
            "dwd_order_detail",
            "ads_sales_dashboard",
        ),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )

    assert {ctx.table_name for ctx in seen_contexts} == {"dwd_order_detail"}
    assert result["generated_model_count"] == 3
    assert (
        project_dir
        / "ods"
        / "models"
        / "internal"
        / "single_writer_dm"
        / "ods_customer.yaml"
    ).exists()
    assert (
        project_dir / "ads" / "models" / "ads_sales_dashboard.yaml"
    ).exists()


def test_generate_single_writer_pass_dry_run_does_not_delete_or_write(
    tmp_path, monkeypatch
):
    project = "generate_single_writer_dry_run"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        existing_models={
            "dwd_existing": {
                "version": 2,
                "name": "dwd_existing",
                "layer": "DWD",
            }
        },
    )
    existing_model = project_dir / "mid" / "models" / "dwd_existing.yaml"

    result = run_generate_model_metadata(project, dry_run=True)

    assert result["model_change_count"] == 1
    assert result["model_update_count"] == 0
    assert existing_model.exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()
    assert result["deleted_model_files"] == []
    assert result["flow"] == {
        "mode": "generate",
        "prior_source": "direct_rule",
        "llm_enabled": False,
        "base_model_count": 1,
        "final_model_count": 1,
    }


def test_generate_single_writer_pass_deletes_then_writes_final_models(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_final"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        existing_models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="dimension",
                    dimension_role="BASE",
                    confidence=0.9,
                    reasoning_steps=[],
                    entities=[
                        {
                            "code": "ORDER_DETAIL",
                            "type": "primary",
                            "key_columns": ["id"],
                        }
                    ],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dwd_order_detail"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert str(model_path) in result["deleted_model_files"]
    assert saved["layer"] == "DIM"
    assert saved["table_type"] == "dimension"
    assert saved["dimension_role"] == "BASE"
    assert result["model_updates"][0]["updated"] is True


def test_generate_single_writer_pass_reports_final_metadata_changes_for_llm_refinement(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_final_metadata_report"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        mid_tables=("dws_order_summary",),
        existing_models={
            "dws_order_summary": {
                "version": 2,
                "name": "dws_order_summary",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
    )
    model_path = project_dir / "mid" / "models" / "dws_order_summary.yaml"

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWS",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    columns={
                        "atomic_metrics": [
                            {
                                "name": "order_count",
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

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dws_order_summary"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    llm_update = result["llm_result"]["model_updates"][0]
    update = result["model_updates"][0]
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["inspection_result"] == result["llm_result"]
    assert "model_metadata" not in llm_update
    assert llm_update["metadata_changed"] is False
    assert llm_update["metric_changed"] is True
    assert update["source"] == "llm_refinement"
    assert update["metadata_changed"] is True
    assert update["metric_changed"] is True
    assert update["metric_count"] == 1
    assert update["new_metric_count"] == 1
    assert update["removed_metric_count"] == 0
    assert update["grain_changed"] is False
    assert update["updated"] is True
    assert saved["layer"] == "DWS"
    assert saved["table_type"] == "fact"
    assert saved["atomic_metrics"] == ["order_count"]


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


def test_catalog_discovery_rejects_low_confidence_semantics():
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    result = TableInspectResult(
        table_name="customer_detail",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.01,
        reasoning_steps=[],
        entities=[
            {
                "code": "LOW_CONFIDENCE_ENTITY",
                "type": "primary",
                "key_columns": ["customer_id"],
            }
        ],
    )
    existing = {"layer": "DWD", "table_type": "fact"}

    assert (
        writer_module.catalog_discovery_model_mapping(
            "demo",
            result,
            {},
            existing,
        )
        == {}
    )
    assert (
        writer_module._resolved_results_for_catalog_discovery(
            [result],
            {result.table_name: existing},
        )
        == []
    )


def test_run_metadata_write_passes_inspector_configuration(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    seen = {}

    class FakeInspector:
        def __init__(
            self,
            api_key,
            *,
            model,
            cache_file,
            max_retries,
            parallelism,
            request_timeout,
            min_cacheable_confidence,
        ):
            seen["parallelism"] = parallelism
            seen["min_cacheable_confidence"] = min_cacheable_confidence

        def inspect_batch(self, contexts):
            return []

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(
        isolated_writer_project,
        api_key="test",
        dry_run=True,
        parallelism=4,
        resolution_policy=LayerResolutionPolicy(
            mode="refresh",
            min_llm_confidence=0.8,
        ),
    )

    assert seen["parallelism"] == 4
    assert seen["min_cacheable_confidence"] == 0.8


def test_run_metadata_write_report_uses_plan_prior(
    monkeypatch,
    sample_lineage_data,
    isolated_writer_project,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    model_metadata = {
        "dwd_customer": {
            "name": "dwd_customer",
            "layer": "DWD",
            "table_type": "fact",
        },
        "dwd_order_detail": {
            "name": "dwd_order_detail",
            "layer": "DWD",
            "table_type": "fact",
        },
        "dws_store_sales_daily": {
            "name": "dws_store_sales_daily",
            "layer": "DWS",
            "table_type": "fact",
        },
    }

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_customer":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer="",
                            inferred_layer="OTHER",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                        )
                    )
                else:
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer=ctx.layer,
                            table_type="fact",
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
        isolated_writer_project,
        api_key="test",
        dry_run=True,
        model_metadata=model_metadata,
        metric_groups={},
        resolution_policy=LayerResolutionPolicy(mode="refresh"),
    )
    customer_report = next(
        table
        for table in result["tables"]
        if table["table_name"] == "dwd_customer"
    )

    assert customer_report["metadata_warnings"][0]["type"] == (
        "llm_layer_fallback"
    )
    assert customer_report["metadata_warnings"][0]["prior_layer"] == "DWD"
    assert customer_report["metadata_warnings"][0]["prior_source"] == (
        "declared"
    )


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


def test_run_catalog_discovery_uses_resolved_results_for_catalog(
    tmp_path, monkeypatch, sample_lineage_data
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "catalog_discovery_resolved_catalog"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (models_dir / "dwd_order_detail.yaml").write_text(
        "\n".join(
            [
                "version: 2",
                "name: dwd_order_detail",
                "layer: DWD",
                "table_type: fact",
                "",
            ]
        ),
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
    lineage_data = {
        "tables": [
            table
            for table in sample_lineage_data["tables"]
            if table["name"] == "dwd_order_detail"
        ],
        "edges": [],
        "indirect_edges": [],
    }
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: lineage_data,
    )

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
                    inferred_layer="OTHER",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                    entities=[
                        {
                            "code": "ORDER",
                            "type": "primary",
                            "key_columns": ["order_id"],
                        }
                    ],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    original_pipeline = writer_module.run_inspection_pipeline
    pipeline_calls = []

    def tracking_pipeline(*args, **kwargs):
        pipeline_calls.append({"project": args[0], "kwargs": kwargs})
        return original_pipeline(*args, **kwargs)

    monkeypatch.setattr(
        writer_module, "run_inspection_pipeline", tracking_pipeline
    )

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=True,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog"]["semantic_subjects"] == []
    assert catalog["semantic_subjects"] == []
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["project"] == project


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
                "layer": "DWD",
                "table_type": "dimension",
                "data_domain": "04",
                "business_area": "SHOP",
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
    assert fact_model["data_domain"] == "04"
    assert fact_model["business_area"] == "SHOP"
    assert "business_process" not in fact_model
    assert "semantic_subject" not in fact_model
    assert dim_model["data_domain"] == "04"
    assert dim_model["business_area"] == "SHOP"
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
