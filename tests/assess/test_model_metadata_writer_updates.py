import pytest
import yaml

import dw_refactor_agent.assessment.llm.model_metadata_updates as updates_module
import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.context_builder import TableContext
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
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from tests.assess.model_metadata_writer_test_support import (
    _business_domain_config,
    _configure_project_root,
    _expected_pay_amt_1d_metric,
    _run_isolated_writer_helper,
    _sample_dimension_conflict_result,
    _sample_dimension_result,
    _sample_dws_result,
    _sample_fact_result,
)
from tests.case_matrix import case_matrix


def _entity_enrichment_context(
    table_name,
    ddl,
    *,
    upstream_tables=None,
    column_lineage=None,
):
    return TableContext(
        table_name=table_name,
        layer="DWS" if table_name.startswith("dws_") else "DIM",
        ddl=ddl,
        etl_sql="",
        upstream_tables=list(upstream_tables or []),
        downstream_tables=[],
        column_lineage=list(column_lineage or []),
    )


def test_related_entity_enrichment_requires_explicit_grain_and_lineage():
    dimension = TableInspectResult(
        table_name="dim_accounting_rule",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "ACCOUNTING_RULE",
                "type": "primary",
                "key_columns": ["rule_id"],
            }
        ],
    )
    unrelated_grain = TableInspectResult(
        table_name="dws_office_activity",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "OFFICE",
                "type": "primary",
                "key_columns": ["office_id"],
            }
        ],
        grain={"entities": ["OFFICE"]},
    )
    ungrained_entity = TableInspectResult(
        table_name="dws_instruction_activity",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "TRANSFER_INSTRUCTION",
                "type": "primary",
                "key_columns": ["rule_id"],
            }
        ],
        grain={},
    )
    contexts = {
        "dim_accounting_rule": _entity_enrichment_context(
            "dim_accounting_rule",
            (
                "CREATE TABLE dim_accounting_rule (\n"
                "  rule_id BIGINT COMMENT '规则ID',\n"
                "  office_id BIGINT COMMENT '机构ID'\n"
                ");"
            ),
        ),
        "dws_office_activity": _entity_enrichment_context(
            "dws_office_activity",
            "CREATE TABLE dws_office_activity (office_id BIGINT);",
            upstream_tables=["dwd_transfer"],
            column_lineage=[
                {
                    "source": "dwd_transfer.office_id",
                    "target": "dws_office_activity.office_id",
                }
            ],
        ),
        "dws_instruction_activity": _entity_enrichment_context(
            "dws_instruction_activity",
            "CREATE TABLE dws_instruction_activity (rule_id BIGINT);",
            upstream_tables=["dim_accounting_rule"],
            column_lineage=[
                {
                    "source": "dim_accounting_rule.rule_id",
                    "target": "dws_instruction_activity.rule_id",
                }
            ],
        ),
    }

    updates_module.enrich_results_with_related_entities(
        [dimension, unrelated_grain, ungrained_entity],
        contexts,
    )

    assert dimension.related_entities == []
    assert [entity["code"] for entity in dimension.entities] == [
        "ACCOUNTING_RULE"
    ]


def test_related_entity_enrichment_uses_direct_renamed_column_lineage():
    dimension = TableInspectResult(
        table_name="dim_product",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "PRODUCT",
                "type": "primary",
                "key_columns": ["product_id"],
            }
        ],
    )
    grain_result = TableInspectResult(
        table_name="dws_category_sales",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "CATEGORY",
                "type": "primary",
                "key_columns": ["category_key"],
            }
        ],
        grain={"entities": ["CATEGORY"]},
    )
    contexts = {
        "dim_product": _entity_enrichment_context(
            "dim_product",
            (
                "CREATE TABLE dim_product (\n"
                "  product_id BIGINT COMMENT '商品ID',\n"
                "  category_id BIGINT COMMENT '品类ID'\n"
                ");"
            ),
        ),
        "dws_category_sales": _entity_enrichment_context(
            "dws_category_sales",
            "CREATE TABLE dws_category_sales (category_key BIGINT);",
            upstream_tables=["dim_product"],
            column_lineage=[
                {
                    "source": "dim_product.category_id",
                    "target": "dws_category_sales.category_key",
                }
            ],
        ),
    }

    updates_module.enrich_results_with_related_entities(
        [dimension, grain_result],
        contexts,
    )

    assert dimension.related_entities == [
        {
            "code": "CATEGORY",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PRODUCT",
            },
        }
    ]


def test_related_entity_enrichment_preserves_composite_key_order():
    dimension = TableInspectResult(
        table_name="dim_account_scope",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "ACCOUNT_SCOPE",
                "type": "primary",
                "key_columns": ["scope_id"],
            }
        ],
    )
    grain_result = TableInspectResult(
        table_name="dws_account_activity",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "ACCOUNT",
                "type": "primary",
                "key_columns": ["grain_country", "grain_account"],
            }
        ],
        grain={"entities": ["ACCOUNT"]},
    )
    contexts = {
        "dim_account_scope": _entity_enrichment_context(
            "dim_account_scope",
            (
                "CREATE TABLE dim_account_scope (\n"
                "  scope_id BIGINT COMMENT '范围ID',\n"
                "  country_id BIGINT COMMENT '国家ID',\n"
                "  account_id BIGINT COMMENT '账户ID'\n"
                ");"
            ),
        ),
        "dws_account_activity": _entity_enrichment_context(
            "dws_account_activity",
            (
                "CREATE TABLE dws_account_activity (\n"
                "  grain_country BIGINT,\n"
                "  grain_account BIGINT\n"
                ");"
            ),
            upstream_tables=["dim_account_scope"],
            column_lineage=[
                {
                    "source": "dim_account_scope.country_id",
                    "target": "dws_account_activity.grain_country",
                },
                {
                    "source": "dim_account_scope.account_id",
                    "target": "dws_account_activity.grain_account",
                },
            ],
        ),
    }

    updates_module.enrich_results_with_related_entities(
        [dimension, grain_result],
        contexts,
    )

    assert dimension.related_entities[0]["key_columns"] == [
        "country_id",
        "account_id",
    ]


def test_related_entity_enrichment_rejects_competing_entity_codes():
    dimension = TableInspectResult(
        table_name="dim_transfer_route",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "TRANSFER_ROUTE",
                "type": "primary",
                "key_columns": ["route_id"],
            }
        ],
    )
    grain_results = []
    contexts = {
        "dim_transfer_route": _entity_enrichment_context(
            "dim_transfer_route",
            (
                "CREATE TABLE dim_transfer_route (\n"
                "  route_id BIGINT COMMENT '路径ID',\n"
                "  office_id BIGINT COMMENT '机构ID',\n"
                "  region_id BIGINT COMMENT '区域ID'\n"
                ");"
            ),
        )
    }
    for suffix in ("FROM", "TO"):
        table_name = f"dws_transfer_{suffix.casefold()}"
        grain_results.append(
            TableInspectResult(
                table_name=table_name,
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                entities=[
                    {
                        "code": f"OFFICE_{suffix}",
                        "type": "primary",
                        "key_columns": ["office_id"],
                    }
                ],
                grain={"entities": [f"OFFICE_{suffix}"]},
            )
        )
        contexts[table_name] = _entity_enrichment_context(
            table_name,
            f"CREATE TABLE {table_name} (office_id BIGINT);",
            upstream_tables=["dim_transfer_route"],
            column_lineage=[
                {
                    "source": "dim_transfer_route.office_id",
                    "target": f"{table_name}.office_id",
                }
            ],
        )

    region_table = "dws_transfer_to_region"
    grain_results.append(
        TableInspectResult(
            table_name=region_table,
            declared_layer="DWS",
            inferred_layer="DWS",
            table_type="fact",
            confidence=0.9,
            reasoning_steps=[],
            entities=[
                {
                    "code": "OFFICE_TO",
                    "type": "primary",
                    "key_columns": ["region_id"],
                }
            ],
            grain={"entities": ["OFFICE_TO"]},
        )
    )
    contexts[region_table] = _entity_enrichment_context(
        region_table,
        f"CREATE TABLE {region_table} (region_id BIGINT);",
        upstream_tables=["dim_transfer_route"],
        column_lineage=[
            {
                "source": "dim_transfer_route.region_id",
                "target": f"{region_table}.region_id",
            }
        ],
    )

    updates_module.enrich_results_with_related_entities(
        [dimension] + grain_results,
        contexts,
    )

    assert dimension.related_entities == []


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
        _assert_update_model_yaml_preserves_dimension_unique_and_natural_entities,
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


def test_writer_project_root_override_remains_compatible(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "writer_root_override"
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        writer_module.PROJECT_CONFIG,
        project,
        {"dir": project},
    )

    update = update_model_yaml(project, _sample_fact_result())

    expected_path = (
        tmp_path / project / "mid" / "models" / "dwd_order_detail.yaml"
    )
    assert update["path"] == str(expected_path)
    assert expected_path.exists()
    assert writer_module._project_dir(project) == tmp_path / project


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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    monkeypatch.setattr(
        updates_module,
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    monkeypatch.setattr(
        updates_module,
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
    _configure_project_root(monkeypatch, project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    if with_taxonomy:
        monkeypatch.setattr(
            updates_module,
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
    _configure_project_root(monkeypatch, project_root)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    monkeypatch.setattr(
        updates_module,
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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


def _assert_update_model_yaml_preserves_dimension_unique_and_natural_entities(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    models_dir = tmp_path / "demo" / "mid" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dim_merchant.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dim_merchant",
                "layer": "DIM",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(writer_module.PROJECT_CONFIG, "demo", {"dir": "demo"})
    result = TableInspectResult(
        table_name="dim_merchant",
        declared_layer="DIM",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        entities=[
            {
                "code": "MERCHANT",
                "type": "primary",
                "key_columns": ["merchant_id"],
            },
            {
                "code": "MERCHANT_NATURAL",
                "type": "unique",
                "key_columns": ["merchant_code"],
                "relationship": {},
            },
            {
                "code": "MERCHANT_VERSION",
                "type": "natural",
                "key_columns": ["merchant_number"],
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": "MERCHANT",
                },
            },
            {
                "code": "REGION",
                "type": "foreign",
                "key_columns": ["region_id"],
                "relationship": {},
            },
        ],
    )

    update_model_yaml("demo", result, write_scope="grain")
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert saved["entities"] == [
        {
            "code": "MERCHANT",
            "type": "primary",
            "key_columns": ["merchant_id"],
        },
        {
            "code": "MERCHANT_NATURAL",
            "type": "unique",
            "key_columns": ["merchant_code"],
        },
        {
            "code": "MERCHANT_VERSION",
            "type": "natural",
            "key_columns": ["merchant_number"],
        },
        {
            "code": "REGION",
            "type": "foreign",
            "key_columns": ["region_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "MERCHANT",
            },
        },
    ]


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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
    _configure_project_root(monkeypatch, project_root)
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
