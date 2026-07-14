import json
import threading
import time
from unittest.mock import patch

import pytest

from dw_refactor_agent.assessment.llm.table_inspector import (
    TableContext,
    TableInspector,
    TableInspectResult,
    _extract_ddl_column_names,
    build_prompt,
    normalize_chat_completions_url,
    parse_response,
    result_to_cache_dict,
    result_to_dict,
    validate_columns,
    validate_layer_sql_consistency,
    validate_layer_table_type_consistency,
    validate_metric_expressions,
    validate_metric_relationships,
    validate_primary_entities,
    validate_time_periods,
    validate_upstream_metric_layer_consistency,
)


def _inspection_result(
    *,
    table_name="candidate_table",
    declared_layer="DWD",
    inferred_layer="DWD",
    table_type="fact",
    confidence=0.9,
    **metadata,
):
    return TableInspectResult(
        table_name=table_name,
        declared_layer=declared_layer,
        inferred_layer=inferred_layer,
        table_type=table_type,
        confidence=confidence,
        reasoning_steps=[],
        **metadata,
    )


def _inspect_with_responses(inspector, context, responses, monkeypatch):
    prompts = []

    def fake_api(prompt):
        prompts.append(prompt)
        payload = responses[len(prompts) - 1]
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    monkeypatch.setattr(inspector, "_call_api", fake_api)
    return inspector.inspect(context), prompts


# ============================================================
# 1. Prompt 组装测试
# ============================================================


def test_build_prompt_scenarios():
    _assert_build_prompt_exposes_context_and_json_contract()
    _assert_build_prompt_can_hide_layer_hints()
    _assert_build_prompt_omits_empty_etl_section()
    _assert_build_prompt_keeps_metadata_contracts_without_project_examples()
    _assert_build_prompt_includes_catalog_and_project_context_as_inputs()
    _assert_build_prompt_documents_business_metadata_scope()
    _assert_build_prompt_keeps_metric_expression_separate_from_grain()
    _assert_build_prompt_weakens_empty_downstream_ads_signal()
    _assert_build_prompt_distinguishes_entity_staging_from_publication()


def test_normalize_chat_completions_url():
    assert normalize_chat_completions_url(None) == (
        "https://api.deepseek.com/chat/completions"
    )
    assert normalize_chat_completions_url("https://api.deepseek.com") == (
        "https://api.deepseek.com/chat/completions"
    )
    assert normalize_chat_completions_url("https://api.deepseek.com/v1") == (
        "https://api.deepseek.com/chat/completions"
    )
    assert (
        normalize_chat_completions_url("https://example.test/chat/completions")
        == "https://example.test/chat/completions"
    )


def test_extract_ddl_columns_normalizes_doris_table_clauses():
    ddl = """
    DROP TABLE IF EXISTS demo.sales_daily;
    CREATE TABLE IF NOT EXISTS demo.sales_daily (
        store_id BIGINT NOT NULL COMMENT '门店',
        stat_date DATE NOT NULL COMMENT '日期',
        sale_amount DECIMAL(18,2) NULL COMMENT '销售额'
    ) ENGINE=OLAP
    UNIQUE KEY(store_id, stat_date)
    PARTITION BY RANGE(stat_date) (
        PARTITION p1 VALUES LESS THAN ('2026-01-02')
    )
    DISTRIBUTED BY HASH(store_id) BUCKETS 1
    PROPERTIES ('replication_num'='1');
    """

    assert _extract_ddl_column_names(ddl) == {
        "store_id",
        "stat_date",
        "sale_amount",
    }


def test_parse_response_metadata_scenarios():
    helpers = [
        _assert_parse_dimension_response,
        _assert_parse_response_preserves_dimension_classification_metadata,
        _assert_parse_business_domain_response,
        _assert_parse_response_preserves_entity_and_grain_metadata,
        _assert_parse_response_normalizes_convertible_time_periods,
        _assert_parse_response_preserves_entities_metadata,
        _assert_parse_response_normalizes_placeholder_empty_grain,
        _assert_dict_to_result_normalizes_placeholder_empty_grain,
        _assert_parse_response_preserves_related_entities_metadata,
        _assert_parse_basic_response_shapes,
        _assert_parse_grouped_column_response,
        _assert_result_serialization_handles_system_fields,
    ]

    for helper in helpers:
        helper()


def test_validate_response_contract_scenarios():
    helpers = [
        _assert_validate_time_periods_flags_unrecognized_values,
        _assert_validate_metric_expressions_flags_grain_text,
        _assert_validate_primary_entities_requires_dwd_fact_primary,
        _assert_validate_primary_entities_uses_inferred_dwd_layer,
        _assert_validate_layer_table_type_consistency,
        _assert_validate_layer_sql_consistency,
        _assert_validate_upstream_metric_layer_consistency,
        _assert_validate_columns_flags_unknown_duplicate_and_missing_fields,
        _assert_validate_columns_matches_identifiers_case_insensitively,
        _assert_validate_columns_requires_all_dws_fact_fields,
        _assert_validate_columns_uses_inferred_metric_layer,
        _assert_validate_metric_relationships_requires_derived_base_metric_in_upstream_atomic,
        _assert_validate_metric_relationships_matches_qualified_upstream_table,
        _assert_validate_metric_relationships_isolates_same_short_name_schemas,
        _assert_validate_metric_relationships_accepts_lineage_backed_raw_source,
        _assert_validate_metric_relationships_flags_ambiguous_unqualified_base_metric,
        _assert_result_status_from_validation,
    ]

    for helper in helpers:
        helper()


def test_inspector_cache_and_progress_scenarios(tmp_path_factory, monkeypatch):
    _assert_cache_hit_skips_api(tmp_path_factory.mktemp("cache_hit"))
    _assert_cache_retains_prompt_variants(
        tmp_path_factory.mktemp("cache_variants")
    )
    _assert_failed_result_does_not_poison_cache(
        tmp_path_factory.mktemp("cache_failure")
    )
    _assert_warning_cache_preserves_status_and_retry_budget(
        tmp_path_factory.mktemp("cache_warning")
    )
    with monkeypatch.context() as mp:
        _assert_cache_miss_calls_api(tmp_path_factory.mktemp("cache_miss"), mp)
    with monkeypatch.context() as mp:
        _assert_progress_callback_reports_batch_events(
            tmp_path_factory.mktemp("progress_batch"), mp
        )
    _assert_progress_callback_reports_cache_hit(
        tmp_path_factory.mktemp("progress_cache")
    )
    _assert_cache_hash_includes_context_fields(
        tmp_path_factory.mktemp("cache_hash")
    )


def test_inspector_retry_scenarios(tmp_path_factory, monkeypatch):
    helpers = [
        _assert_inspect_retries_validation_errors,
        _assert_inspect_normalizes_convertible_time_periods_without_retry,
        _assert_inspect_retries_unrecognized_time_periods,
        _assert_inspect_retries_invalid_metric_expressions,
        _assert_inspect_retries_missing_dwd_fact_primary_entity,
    ]

    for helper in helpers:
        with monkeypatch.context() as mp:
            helper(
                tmp_path_factory.mktemp(
                    helper.__name__.replace("_assert_", "")
                ),
                mp,
            )


def _assert_build_prompt_exposes_context_and_json_contract():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        ddl="CREATE TABLE dwd_customer (id BIGINT);",
        etl_sql="INSERT INTO dwd_customer SELECT id FROM ods_customer;",
        upstream_tables=["ods_customer"],
        downstream_tables=["ads_rfm"],
    )

    prompt = build_prompt(ctx)

    assert "dwd_customer" in prompt
    assert "CREATE TABLE dwd_customer" in prompt
    assert "INSERT INTO dwd_customer" in prompt
    assert "ods_customer" in prompt
    assert "ads_rfm" in prompt
    assert "只允许返回下方 JSON schema 中列出的顶层字段" in prompt
    for field in [
        "inferred_layer",
        "table_type",
        "entities",
        "grain",
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
        "dimensions",
        "others",
    ]:
        assert field in prompt
    assert '"inferred_layer": "DWD|DWS|DIM|OTHER"' in prompt
    assert "is_violating_declared_layer" not in prompt


def _assert_build_prompt_omits_empty_etl_section():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        ddl="CREATE TABLE dwd_customer;",
        etl_sql="",
        upstream_tables=[],
        downstream_tables=[],
    )

    prompt = build_prompt(ctx)

    assert "dwd_customer" in prompt
    assert "## ETL 加工逻辑" not in prompt


def _assert_build_prompt_can_hide_layer_hints():
    ctx = TableContext(
        table_name="order_summary",
        layer="DWD",
        ddl="CREATE TABLE order_summary (order_count BIGINT);",
        etl_sql=(
            "INSERT INTO order_summary SELECT COUNT(*) FROM order_detail;"
        ),
        upstream_tables=["order_detail"],
        downstream_tables=["order_dashboard"],
        upstream_table_layers={"order_detail": "DWD"},
        downstream_table_layers={"order_dashboard": "ADS"},
        expose_layer_hints=False,
    )

    prompt = build_prompt(ctx)

    assert "原始配置层级: 未提供" in prompt
    assert "上游表: order_detail" in prompt
    assert "下游表: order_dashboard" in prompt
    assert "order_detail(DWD)" not in prompt
    assert "order_dashboard(ADS)" not in prompt
    assert "距 ODS 最小跳数" not in prompt


def _assert_build_prompt_keeps_metadata_contracts_without_project_examples():
    ctx = TableContext(
        table_name="DIM_BASE_CUST_INFO",
        layer="DIM",
        ddl="CREATE TABLE DIM_BASE_CUST_INFO (CUST_ID BIGINT);",
        etl_sql="",
        upstream_tables=["dwd_customer"],
        downstream_tables=["dwd_order_detail"],
    )

    prompt = build_prompt(ctx)

    for contract in [
        '"type": "primary|unique|foreign|natural"',
        '"dimension_role": "BASE|ADDT"',
        '"dimension_content_type": "INFO|TAG|TREE"',
        "grain.entities",
        "business_process",
        "semantic_subject",
        "行粒度、键约束、聚合位置、时间字段和 JOIN 复用关系",
        "OTHER 不能作为 ODS 的替代返回值",
        "factless fact",
        "实体主数据的批次快照与周期事实要分开",
        "上游已治理公共指标作为输出指标继续发布",
        "JOIN 聚合子查询若按业务实体与时间粒度产生",
        "必须把业务参与关系与参数配置映射分开",
        "不得为了填写 base_metric 而虚构上游不存在",
    ]:
        assert contract in prompt
    for hardcoded_example in [
        "CUSTOMER_OPERATION",
        "PRODUCT_MANAGEMENT",
        "STORE_OPERATION",
        "dwd_order_detail.cost_price",
    ]:
        assert hardcoded_example not in prompt


def _assert_build_prompt_includes_catalog_and_project_context_as_inputs():
    ctx = TableContext(
        table_name="dwd_event_detail",
        layer="DWD",
        ddl="CREATE TABLE dwd_event_detail (event_id BIGINT);",
        etl_sql="INSERT INTO dwd_event_detail SELECT event_id FROM ods_event;",
        upstream_tables=["ods_event"],
        downstream_tables=["dws_event_daily"],
        project_context="事件完成是核心业务过程。",
        business_semantics_options={
            "business_processes": [
                {
                    "code": "EVENT_COMPLETION",
                    "name": "事件完成",
                }
            ],
            "semantic_subjects": [
                {
                    "code": "PARTY",
                    "name": "参与方",
                }
            ],
        },
    )

    prompt = build_prompt(ctx)

    assert "项目背景说明" in prompt
    assert "事件完成是核心业务过程" in prompt
    assert "已确认业务语义目录" in prompt
    assert "EVENT_COMPLETION" in prompt
    assert "PARTY" in prompt
    assert '"tables"' not in prompt


def _assert_build_prompt_documents_business_metadata_scope():
    scenarios = [
        ("DWD", "未提供已确认字典时"),
        ("DIM", "数据域与业务板块字典"),
    ]
    for layer, expected_section in scenarios:
        options = None
        if layer == "DIM":
            options = {
                "domains": [{"id": "06", "code": "ORGN", "name": "机构域"}],
                "business_areas": [{"code": "CHNL", "name": "渠道业务"}],
            }
        ctx = TableContext(
            table_name=(
                "dim_location" if layer == "DIM" else "dwd_event_detail"
            ),
            layer=layer,
            ddl="CREATE TABLE t (id BIGINT);",
            etl_sql="",
            upstream_tables=[],
            downstream_tables=[],
            business_domain_options=options,
        )

        prompt = build_prompt(ctx)

        assert expected_section in prompt
        assert "inferred_data_domain" in prompt
        assert "inferred_business_area" in prompt


def _assert_build_prompt_keeps_metric_expression_separate_from_grain():
    ctx = TableContext(
        table_name="dws_store_sales_daily",
        layer="DWS",
        ddl="CREATE TABLE dws_store_sales_daily (store_id BIGINT);",
        etl_sql=(
            "INSERT INTO dws_store_sales_daily "
            "SELECT store_id, order_date, SUM(subtotal) AS total_amount "
            "FROM dwd_order_detail GROUP BY store_id, order_date;"
        ),
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
    )

    prompt = build_prompt(ctx)

    assert "metric.expression 只填写指标计算公式" in prompt
    assert "不要在 metric.expression 中写 GROUP BY" in prompt
    assert "不要在 metric.expression 中写“按...分组”" in prompt
    assert "聚合粒度由表级 grain 表达" in prompt
    assert "如果 SQL 存在 GROUP BY" in prompt
    assert "输出前逐项检查所有 metric.expression" in prompt
    assert "不得包含 GROUP BY" in prompt
    assert "time_period 只允许 D/W/M/Q/Y/S" in prompt
    assert "不得返回中文" in prompt
    assert "SUM(discount) GROUP BY store_id, order_date" not in prompt


def _assert_build_prompt_weakens_empty_downstream_ads_signal():
    ctx = TableContext(
        table_name="inventory_daily",
        layer="DWD",
        ddl="CREATE TABLE inventory_daily (product_id BIGINT);",
        etl_sql=(
            "INSERT INTO inventory_daily "
            "SELECT product_id, SUM(quantity) AS quantity "
            "FROM inventory GROUP BY product_id;"
        ),
        upstream_tables=["inventory"],
        downstream_tables=[],
        upstream_table_layers={"inventory": "ODS"},
    )

    prompt = build_prompt(ctx)

    assert "inventory(ODS)" in prompt
    assert "出度为 0 只能作为弱证据" in prompt
    assert "不得仅凭下游为空判为 ADS" in prompt


def _assert_build_prompt_distinguishes_entity_staging_from_publication():
    ctx = TableContext(
        table_name="clean_entity",
        layer="DWD",
        ddl="CREATE TABLE clean_entity (entity_id BIGINT, name STRING);",
        etl_sql=(
            "INSERT INTO clean_entity "
            "SELECT entity_id, TRIM(name) AS name FROM raw_entity;"
        ),
        upstream_tables=["raw_entity"],
        downstream_tables=["published_entity"],
        downstream_entity_publication_features={
            "published_entity": {
                "generated_key_columns": ["entity_key"],
                "natural_key_aliases": ["entity_natural_key"],
                "added_version_control_columns": ["effective_date"],
                "combines_sources_with_union": False,
                "contains_aggregation": False,
            }
        },
        expose_layer_hints=False,
    )

    prompt = build_prompt(ctx)

    assert "下游实体发布结构特征" in prompt
    assert '"generated_key_columns"' in prompt
    assert '"natural_key_aliases"' in prompt
    assert "当前表应为 DWD/other" in prompt
    assert "不包含下游层级标签" in prompt
    assert "published_entity(DIM)" not in prompt


# ============================================================
# 2. 响应解析测试
# ============================================================


def _assert_parse_dimension_response():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DIM",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reasoning_steps": ["test"],
                        }
                    )
                }
            }
        ]
    }
    result = parse_response("dwd_customer", resp, declared_layer="DWD")
    assert result.table_name == "dwd_customer"
    assert result.declared_layer == "DWD"
    assert result.inferred_layer == "DIM"
    assert result.table_type == "dimension"
    assert result.confidence == 0.9
    assert result.reasoning_steps == ["test"]
    assert result.is_violating_declared_layer is True


def _assert_parse_response_preserves_dimension_classification_metadata():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DIM",
                            "table_type": "dimension",
                            "dimension_role": "base",
                            "dimension_content_type": "tag",
                            "confidence": 0.9,
                            "reasoning_steps": ["客户标签维表"],
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("DIM_BASE_CUST_TAG", resp, declared_layer="DIM")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.dimension_role == "BASE"
    assert result.dimension_content_type == "TAG"
    assert data["dimension_role"] == "BASE"
    assert data["dimension_content_type"] == "TAG"
    assert cached["dimension_role"] == "BASE"
    assert cached["dimension_content_type"] == "TAG"


def _assert_parse_business_domain_response():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DWD",
                            "table_type": "fact",
                            "inferred_data_domain": "04",
                            "inferred_business_area": "PAYM",
                            "confidence": 0.9,
                            "reasoning_steps": ["交易事实表"],
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("dwd_transactions", resp, declared_layer="DWD")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.inferred_data_domain == "04"
    assert result.inferred_business_area == "PAYM"
    assert data["inferred_data_domain"] == "04"
    assert data["inferred_business_area"] == "PAYM"
    assert cached["inferred_data_domain"] == "04"
    assert cached["inferred_business_area"] == "PAYM"


def _assert_parse_response_preserves_entity_and_grain_metadata():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DWS",
                            "table_type": "fact",
                            "confidence": 0.9,
                            "reasoning_steps": ["商品日汇总"],
                            "entity": {},
                            "grain": {
                                "keys": ["product_id", "stat_date"],
                                "entities": ["PROD"],
                                "time_column": "stat_date",
                                "time_period": "D",
                            },
                        }
                    )
                }
            }
        ]
    }

    result = parse_response(
        "dws_product_sales_daily", resp, declared_layer="DWS"
    )
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.grain == {
        "keys": ["product_id", "stat_date"],
        "entities": ["PROD"],
        "time_column": "stat_date",
        "time_period": "D",
    }
    assert data["grain"] == result.grain
    assert cached["grain"] == result.grain


def _assert_parse_response_normalizes_convertible_time_periods():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DWS",
                            "table_type": "fact",
                            "confidence": 0.9,
                            "reasoning_steps": ["商品月汇总"],
                            "grain": {
                                "entities": ["PROD"],
                                "time_column": "stat_month_date",
                                "time_period": "月",
                            },
                            "columns": {
                                "atomic_metrics": [],
                                "derived_metrics": [
                                    {
                                        "name": "sale_amount",
                                        "base_metric": "subtotal",
                                        "time_period": "月",
                                        "expression": "SUM(subtotal)",
                                        "confidence": 0.9,
                                    }
                                ],
                                "calculated_metrics": [],
                                "dimensions": [],
                                "others": [],
                            },
                        }
                    )
                }
            }
        ]
    }

    result = parse_response(
        "dws_category_sales_monthly", resp, declared_layer="DWS"
    )
    validation = validate_time_periods(result)

    assert result.grain["time_period"] == "M"
    assert result.derived_metrics[0]["time_period"] == "M"
    assert validation == {}


def _assert_validate_time_periods_flags_unrecognized_values():
    result = parse_response(
        "dws_category_sales_monthly",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "grain": {
                                    "entities": ["PROD"],
                                    "time_column": "stat_month_date",
                                    "time_period": "月累计",
                                },
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [
                                        {
                                            "name": "sale_amount",
                                            "base_metric": "subtotal",
                                            "time_period": "月累计",
                                            "expression": "SUM(subtotal)",
                                        }
                                    ],
                                    "calculated_metrics": [],
                                    "dimensions": [],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWS",
    )

    validation = validate_time_periods(result)

    assert validation == {
        "invalid_time_periods": [
            "grain.time_period=月累计",
            "derived_metrics[0].time_period=月累计",
        ]
    }


def _assert_validate_metric_expressions_flags_grain_text():
    result = parse_response(
        "dws_store_sales_daily",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [
                                        {
                                            "name": "sale_amount",
                                            "base_metric": "subtotal",
                                            "expression": (
                                                "SUM(subtotal) GROUP BY "
                                                "store_id, order_date"
                                            ),
                                        },
                                        {
                                            "name": "discount_amount",
                                            "base_metric": "discount",
                                            "expression": (
                                                "SUM(discount) 按门店+日期分组"
                                            ),
                                        },
                                    ],
                                    "calculated_metrics": [],
                                    "dimensions": [],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWS",
    )

    validation = validate_metric_expressions(result)

    assert validation == {
        "invalid_metric_expressions": [
            (
                "derived_metrics[0].expression="
                "SUM(subtotal) GROUP BY store_id, order_date"
            ),
            "derived_metrics[1].expression=SUM(discount) 按门店+日期分组",
        ]
    }


def _assert_validate_primary_entities_requires_dwd_fact_primary():
    result = parse_response(
        "dwd_order_detail",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "code": "ORDER",
                                        "type": "foreign",
                                        "key_columns": ["order_id"],
                                    },
                                    {
                                        "code": "CUST",
                                        "type": "foreign",
                                        "key_columns": ["customer_id"],
                                    },
                                ],
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [
                                        {
                                            "name": "order_item_id",
                                            "dimension_type": "primary_key",
                                        }
                                    ],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWD",
    )

    validation = validate_primary_entities(result)

    assert validation == {
        "missing_primary_entities": [
            "DWD fact必须返回至少一个type=primary的entities项"
        ]
    }


def _assert_validate_primary_entities_uses_inferred_dwd_layer():
    for inferred_layer in ("DWS", "ADS"):
        result = _inspection_result(
            inferred_layer=inferred_layer,
            entities=[
                {
                    "code": "ENTITY",
                    "type": "foreign",
                    "key_columns": ["entity_id"],
                }
            ],
            grain={"entities": ["ENTITY"]},
        )

        assert validate_primary_entities(result) == {}


def _assert_validate_layer_table_type_consistency():
    for layer, table_type in (
        ("DWD", "dimension"),
        ("DIM", "fact"),
        ("DWS", "other"),
        ("OTHER", "fact"),
    ):
        result = _inspection_result(
            inferred_layer=layer,
            table_type=table_type,
        )

        assert validate_layer_table_type_consistency(result)[
            "inconsistent_layer_table_types"
        ]

    consistent = _inspection_result(
        inferred_layer="DIM",
        table_type="dimension",
    )
    assert validate_layer_table_type_consistency(consistent) == {}


def _assert_validate_layer_sql_consistency():
    context = TableContext(
        table_name="entity_daily_metrics",
        layer="DWD",
        ddl="",
        etl_sql="",
        upstream_tables=["event_detail"],
        downstream_tables=[],
        column_lineage=[
            {
                "source": "event_detail.entity_id",
                "target": "entity_daily_metrics.event_count",
                "condition_lineage": [
                    {
                        "source": "event_detail.entity_id",
                        "condition_type": "GROUP_BY",
                        "condition_expression": "entity_id",
                    }
                ],
            }
        ],
    )
    result = _inspection_result()

    # Bare lineage GROUP_BY evidence cannot distinguish metric aggregation
    # from valid DWD deduplication.
    assert validate_layer_sql_consistency(result, context) == {}

    result.inferred_layer = "DWS"
    assert validate_layer_sql_consistency(result, context) == {}

    grouped_dedup_context = TableContext(
        table_name="deduplicated_event",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT event_id, event_time FROM source_event "
            "GROUP BY event_id, event_time"
        ),
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    result.inferred_layer = "DWD"
    assert validate_layer_sql_consistency(result, grouped_dedup_context) == {}

    latest_record_context = TableContext(
        table_name="latest_event",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT event_id, MAX(updated_at) AS updated_at "
            "FROM source_event GROUP BY event_id"
        ),
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    expected_ambiguous_updated_at = {
        "ambiguous_min_max_aggregation": [
            "MAX(updated_at) AS updated_at: "
            "无法仅凭同名MIN/MAX确定技术选值或业务汇总"
        ]
    }
    assert (
        validate_layer_sql_consistency(result, latest_record_context)
        == expected_ambiguous_updated_at
    )

    last_modified_context = TableContext(
        table_name="latest_event",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT event_id, MAX(last_modified_date) AS last_modified_date "
            "FROM source_event GROUP BY event_id"
        ),
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    assert validate_layer_sql_consistency(result, last_modified_context) == {
        "ambiguous_min_max_aggregation": [
            "MAX(last_modified_date) AS last_modified_date: "
            "无法仅凭同名MIN/MAX确定技术选值或业务汇总"
        ]
    }

    business_max_context = TableContext(
        table_name="store_sales_metrics",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT store_id, MAX(sale_amount) AS max_sale_amount "
            "FROM store_sales GROUP BY store_id"
        ),
        upstream_tables=["store_sales"],
        downstream_tables=[],
    )
    expected_metric_aggregation_error = {
        "inconsistent_layer_sql": [
            "DWD候选的目标行驱动查询包含指标聚合；请重新判断DWS或其他合法层级"
        ]
    }
    assert (
        validate_layer_sql_consistency(result, business_max_context)
        == expected_metric_aggregation_error
    )

    same_name_business_result = _inspection_result(
        columns={
            "atomic_metrics": [{"name": "updated_at"}],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [{"name": "customer_id"}],
            "others": [],
        }
    )
    customer_activity_context = TableContext(
        table_name="customer_activity",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT customer_id, MAX(updated_at) AS updated_at "
            "FROM customer_event GROUP BY customer_id"
        ),
        upstream_tables=["customer_event"],
        downstream_tables=[],
    )
    assert (
        validate_layer_sql_consistency(
            same_name_business_result,
            customer_activity_context,
        )
        == expected_metric_aggregation_error
    )

    global_metric_context = TableContext(
        table_name="event_metrics",
        layer="DWD",
        ddl="",
        etl_sql="SELECT COUNT(*) AS event_count FROM source_event",
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    assert (
        validate_layer_sql_consistency(result, global_metric_context)
        == expected_metric_aggregation_error
    )

    global_max_context = TableContext(
        table_name="latest_update_metric",
        layer="DWD",
        ddl="",
        etl_sql="SELECT MAX(updated_at) AS updated_at FROM source_event",
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    assert (
        validate_layer_sql_consistency(result, global_max_context)
        == expected_metric_aggregation_error
    )

    lookup_aggregate_context = TableContext(
        table_name="instruction_detail",
        layer="DWD",
        ddl="",
        etl_sql=(
            "INSERT INTO instruction_detail "
            "SELECT src.id, dates.first_date FROM instruction_source src "
            "LEFT JOIN ("
            "SELECT instruction_id, MIN(event_date) AS first_date "
            "FROM instruction_event GROUP BY instruction_id"
            ") dates ON src.id = dates.instruction_id"
        ),
        upstream_tables=["instruction_source", "instruction_event"],
        downstream_tables=[],
        column_lineage=context.column_lineage,
    )
    result.inferred_layer = "DWD"
    assert (
        validate_layer_sql_consistency(result, lookup_aggregate_context) == {}
    )

    grouped_cte_context = TableContext(
        table_name="entity_daily_metrics",
        layer="DWD",
        ddl="",
        etl_sql=(
            "INSERT INTO entity_daily_metrics "
            "WITH daily AS ("
            "SELECT entity_id, metric_date, COUNT(*) AS event_count "
            "FROM event_detail GROUP BY entity_id, metric_date"
            ") SELECT * FROM daily"
        ),
        upstream_tables=["event_detail"],
        downstream_tables=[],
        column_lineage=[],
    )
    assert validate_layer_sql_consistency(result, grouped_cte_context) == {
        "inconsistent_layer_sql": [
            "DWD候选的目标行驱动查询包含指标聚合；请重新判断DWS或其他合法层级"
        ]
    }


def _assert_validate_upstream_metric_layer_consistency():
    context = TableContext(
        table_name="entity_metric_snapshot",
        layer="DWD",
        ddl="",
        etl_sql=(
            "SELECT e.entity_id, m.metric_count "
            "FROM entity e LEFT JOIN entity_metrics m "
            "ON e.entity_id = m.entity_id"
        ),
        upstream_tables=["entity", "entity_metrics"],
        downstream_tables=[],
        upstream_metric_groups={
            "analytics.entity_metrics": {
                "atomic_metrics": [{"name": "metric_count"}],
                "derived_metrics": [],
                "calculated_metrics": [],
            }
        },
        column_lineage=[
            {
                "source": "analytics.entity_metrics.metric_count",
                "target": "entity_metric_snapshot.published_metric_count",
            }
        ],
    )
    dwd_result = _inspection_result(
        columns={
            "atomic_metrics": [{"name": "published_metric_count"}],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [{"name": "entity_id"}],
            "others": [],
        }
    )

    assert validate_upstream_metric_layer_consistency(dwd_result, context) == {
        "inconsistent_upstream_metric_layers": [
            "published_metric_count<-analytics.entity_metrics.metric_count"
        ]
    }

    dwd_result.inferred_layer = "DWS"
    assert (
        validate_upstream_metric_layer_consistency(dwd_result, context) == {}
    )

    raw_metric_context = TableContext(
        table_name="entity_detail",
        layer="DWD",
        ddl="",
        etl_sql="SELECT entity_id, amount FROM raw_event",
        upstream_tables=["raw_event"],
        downstream_tables=[],
        upstream_metric_groups={},
        column_lineage=[
            {
                "source": "raw_event.amount",
                "target": "entity_detail.amount",
            }
        ],
    )
    dwd_result.inferred_layer = "DWD"
    assert (
        validate_upstream_metric_layer_consistency(
            dwd_result, raw_metric_context
        )
        == {}
    )


def _assert_parse_response_preserves_entities_metadata():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DWS",
                            "table_type": "fact",
                            "confidence": 0.9,
                            "reasoning_steps": ["商品门店日汇总"],
                            "entities": [
                                {
                                    "code": "PROD",
                                    "type": "foreign",
                                    "key_columns": ["product_id"],
                                },
                                {
                                    "code": "STOR",
                                    "type": "foreign",
                                    "key_columns": ["store_id"],
                                },
                            ],
                            "grain": {
                                "entities": ["PROD", "STOR"],
                                "time_column": "stat_date",
                                "time_period": "D",
                            },
                        }
                    )
                }
            }
        ]
    }

    result = parse_response(
        "dws_product_store_sales_daily", resp, declared_layer="DWS"
    )
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.entities == [
        {
            "code": "PROD",
            "type": "foreign",
            "key_columns": ["product_id"],
        },
        {
            "code": "STOR",
            "type": "foreign",
            "key_columns": ["store_id"],
        },
    ]
    assert result.grain == {
        "entities": ["PROD", "STOR"],
        "time_column": "stat_date",
        "time_period": "D",
    }
    assert data["entities"] == result.entities
    assert cached["entities"] == result.entities


def _assert_parse_response_normalizes_placeholder_empty_grain():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DIM",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reasoning_steps": ["客户维度表"],
                            "grain": {
                                "keys": [],
                                "entities": [],
                                "time_column": "",
                                "time_period": "",
                            },
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("dwd_customers", resp, declared_layer="DWD")

    assert result.grain == {}


def _assert_dict_to_result_normalizes_placeholder_empty_grain():
    payload = {
        "table_name": "dwd_customers",
        "declared_layer": "DWD",
        "inferred_layer": "DIM",
        "table_type": "dimension",
        "confidence": 0.9,
        "reasoning_steps": ["客户维度表"],
        "grain": {
            "keys": [],
            "entities": [],
            "time_column": "",
            "time_period": "",
        },
    }

    from dw_refactor_agent.assessment.llm.table_inspector import dict_to_result

    result = dict_to_result(payload)

    assert result.grain == {}


def _assert_parse_response_preserves_related_entities_metadata():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DIM",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reasoning_steps": ["商品维度包含品类层级"],
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
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("dwd_product", resp, declared_layer="DWD")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.entities == [
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
    assert result.related_entities == [
        {
            "code": "CAT",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PROD",
            },
        }
    ]
    assert data["related_entities"] == result.related_entities
    assert cached["related_entities"] == result.related_entities


def _assert_parse_basic_response_shapes():
    scenarios = [
        (
            "dwd_order",
            '{"table_type": "fact", "confidence": 0.8, "reason": "test fact"}',
            "fact",
            0.8,
            None,
        ),
        (
            "t1",
            '```json\n{"table_type": "dimension", "confidence": 0.9, "reason": "test"}\n```',
            "dimension",
            0.9,
            None,
        ),
        ("t1", "This is a dimension table", "other", 0.0, "JSON 解析失败"),
    ]

    for table_name, content, table_type, confidence, reason in scenarios:
        resp = {"choices": [{"message": {"content": content}}]}
        result = parse_response(table_name, resp)
        assert result.table_type == table_type
        assert result.confidence == confidence
        if reason:
            assert reason in result.reasoning_steps[0]


def _assert_parse_grouped_column_response():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DWD",
                            "table_type": "fact",
                            "confidence": 0.92,
                            "reasoning_steps": ["订单明细事实表"],
                            "columns": {
                                "atomic_metrics": [
                                    {
                                        "name": "pay_amt",
                                        "data_type": "DECIMAL(12,2)",
                                        "business_process": "订单支付",
                                        "action": "pay",
                                        "measure": "amt",
                                        "description": "支付金额",
                                        "reason": "基础支付金额",
                                        "confidence": 0.93,
                                    }
                                ],
                                "derived_metrics": [
                                    {
                                        "name": "pay_amt_1d",
                                        "data_type": "DECIMAL(12,2)",
                                        "base_metric": "pay_amt",
                                        "modifiers": [],
                                        "time_period": "1d",
                                        "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
                                        "description": "近 1 日支付金额",
                                        "reason": "时间周期限定",
                                        "confidence": 0.86,
                                    }
                                ],
                                "calculated_metrics": [
                                    {
                                        "name": "gross_profit",
                                        "data_type": "DECIMAL(12,2)",
                                        "expression": "subtotal - cost_price * quantity",
                                        "derived_from": [
                                            "subtotal",
                                            "cost_price",
                                            "quantity",
                                        ],
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
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("dwd_order_detail", resp, declared_layer="DWD")

    assert result.is_fact_table is True
    assert result.is_violating_declared_layer is False
    assert result.atomic_metrics[0]["name"] == "pay_amt"
    assert result.atomic_metrics[0]["measure"] == "amt"
    assert result.derived_metrics[0]["name"] == "pay_amt_1d"
    assert result.derived_metrics[0]["base_metric"] == "pay_amt"
    assert result.derived_metrics[0]["time_period"] == "D"
    assert result.calculated_metrics[0]["name"] == "gross_profit"
    assert result.calculated_metrics[0]["derived_from"] == [
        "subtotal",
        "cost_price",
        "quantity",
    ]
    assert result.dimensions[0]["dimension_type"] == "primary_key"
    assert result.others[0]["role"] == "audit"


def _assert_result_serialization_handles_system_fields():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "inferred_layer": "DIM",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reasoning_steps": ["dimension table"],
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("dwd_customer", resp, declared_layer="DWD")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert data["is_violating_declared_layer"] is True
    assert "is_violating_declared_layer" not in cached
    assert "status" not in cached


def _assert_validate_columns_flags_unknown_duplicate_and_missing_fields():
    result = parse_response(
        "dwd_order_detail",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [
                                        {"name": "pay_amt"},
                                        {"name": "pay_amt"},
                                        {"name": "ghost_amt"},
                                    ],
                                    "derived_metrics": [],
                                    "dimensions": [{"name": "order_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWD",
    )

    validation = validate_columns(result, {"order_id", "pay_amt", "etl_time"})

    assert validation["unknown_columns"] == ["ghost_amt"]
    assert validation["duplicate_columns"] == ["pay_amt"]
    assert validation["missing_columns"] == ["etl_time"]


def _assert_validate_columns_matches_identifiers_case_insensitively():
    result = _inspection_result(inferred_layer="DWD", table_type="fact")
    result.columns = {
        "atomic_metrics": [{"name": "pay_amt"}],
        "derived_metrics": [],
        "calculated_metrics": [],
        "dimensions": [{"name": "order_id"}],
        "others": [{"name": "etl_time"}],
    }

    validation = validate_columns(
        result,
        {"ORDER_ID", "PAY_AMT", "ETL_TIME"},
    )

    assert validation == {
        "unknown_columns": [],
        "duplicate_columns": [],
        "missing_columns": [],
    }


def _assert_validate_columns_requires_all_dws_fact_fields():
    result = parse_response(
        "dws_store_sales_daily",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [
                                        {"name": "sale_amount"}
                                    ],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "store_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWS",
    )

    validation = validate_columns(
        result,
        {"store_id", "stat_date", "sale_amount", "etl_time"},
    )

    assert validation["missing_columns"] == ["etl_time", "stat_date"]


def _assert_validate_columns_uses_inferred_metric_layer():
    result = _inspection_result(
        declared_layer="DIM",
        inferred_layer="DWS",
    )

    validation = validate_columns(
        result,
        {"customer_id", "stat_date", "order_count"},
    )

    assert validation["missing_columns"] == [
        "customer_id",
        "order_count",
        "stat_date",
    ]


def _assert_validate_metric_relationships_requires_derived_base_metric_in_upstream_atomic():
    result = parse_response(
        "dws_store_sales_daily",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [
                                        {
                                            "name": "sale_amount",
                                            "base_metric": "subtotal",
                                            "base_metric_table": "dwd_order_detail",
                                            "expression": "SUM(subtotal)",
                                        },
                                        {
                                            "name": "sale_quantity",
                                            "base_metric": "quantity",
                                            "base_metric_table": "dwd_order_detail",
                                            "expression": "SUM(quantity)",
                                        },
                                        {
                                            "name": "mystery_amount",
                                            "base_metric": "ghost_amount",
                                            "base_metric_table": "dwd_order_detail",
                                            "expression": "SUM(ghost_amount)",
                                        },
                                        {
                                            "name": "unknown_amount",
                                            "base_metric": "",
                                            "base_metric_table": "",
                                            "expression": "SUM(amount)",
                                        },
                                        {
                                            "name": "bad_table_amount",
                                            "base_metric": "subtotal",
                                            "base_metric_table": "dwd_refund_detail",
                                            "expression": "SUM(subtotal)",
                                        },
                                    ],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "store_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWS",
    )
    ctx = TableContext(
        table_name="dws_store_sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "dwd_order_detail": {
                "atomic_metrics": ["subtotal", "quantity"],
                "derived_metrics": [],
                "calculated_metrics": [],
            },
        },
    )

    validation = validate_metric_relationships(result, ctx)

    assert validation.get("missing_base_metrics") == ["unknown_amount"]
    assert validation.get("invalid_base_metrics") == [
        "mystery_amount:dwd_order_detail.ghost_amount"
    ]
    assert validation.get("invalid_base_metric_tables") == [
        "bad_table_amount:dwd_refund_detail"
    ]


def _assert_validate_metric_relationships_matches_qualified_upstream_table():
    result = _inspection_result(
        inferred_layer="DWS",
        columns={
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "base_metric": "SUBTOTAL",
                    "base_metric_table": "order_detail",
                    "expression": "SUM(subtotal)",
                }
            ]
        },
    )
    context = TableContext(
        table_name="sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=["analytics.order_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "analytics.order_detail": {"atomic_metrics": ["subtotal"]}
        },
    )

    assert validate_metric_relationships(result, context) == {}

    result.derived_metrics[0]["base_metric_table"] = (
        "warehouse.analytics.order_detail"
    )
    context.upstream_tables = ["order_detail"]
    context.upstream_metric_groups = {
        "order_detail": {"atomic_metrics": ["subtotal"]}
    }
    assert validate_metric_relationships(result, context) == {}


def _assert_validate_metric_relationships_isolates_same_short_name_schemas():
    context = TableContext(
        table_name="sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=[
            "catalog_a.db_a.orders",
            "catalog_b.db_b.orders",
        ],
        downstream_tables=[],
        upstream_metric_groups={
            "catalog_a.db_a.orders": {"atomic_metrics": ["amount"]},
            "catalog_b.db_b.orders": {"atomic_metrics": ["quantity"]},
        },
    )
    qualified = _inspection_result(
        inferred_layer="DWS",
        columns={
            "derived_metrics": [
                {
                    "name": "total_amount",
                    "base_metric": "amount",
                    "base_metric_table": "catalog_a.db_a.orders",
                }
            ]
        },
    )
    ambiguous = _inspection_result(
        inferred_layer="DWS",
        columns={
            "derived_metrics": [
                {
                    "name": "total_amount",
                    "base_metric": "amount",
                    "base_metric_table": "orders",
                }
            ]
        },
    )
    wrong_qualified = _inspection_result(
        inferred_layer="DWS",
        columns={
            "derived_metrics": [
                {
                    "name": "total_amount",
                    "base_metric": "amount",
                    "base_metric_table": "wrong.db.orders",
                }
            ]
        },
    )

    assert validate_metric_relationships(qualified, context) == {}
    assert validate_metric_relationships(ambiguous, context) == {
        "invalid_base_metric_tables": ["total_amount:orders"]
    }
    assert validate_metric_relationships(wrong_qualified, context) == {
        "invalid_base_metric_tables": ["total_amount:wrong.db.orders"]
    }


def _assert_validate_metric_relationships_accepts_lineage_backed_raw_source():
    result = _inspection_result(
        inferred_layer="DWS",
        columns={
            "derived_metrics": [
                {
                    "name": "total_amount",
                    "base_metric": "subtotal",
                    "base_metric_table": "order_item",
                    "expression": "SUM(subtotal)",
                }
            ]
        },
    )
    context = TableContext(
        table_name="order_summary",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=["warehouse.order_item"],
        downstream_tables=[],
        column_lineage=[
            {
                "source": "warehouse.order_item.subtotal",
                "target": "warehouse.order_summary.total_amount",
                "expression": "SUM(subtotal)",
            }
        ],
    )

    assert validate_metric_relationships(result, context) == {}


def _assert_validate_metric_relationships_flags_ambiguous_unqualified_base_metric():
    result = parse_response(
        "dws_sales_daily",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [
                                        {
                                            "name": "sale_amount",
                                            "base_metric": "subtotal",
                                            "expression": "SUM(subtotal)",
                                        }
                                    ],
                                    "calculated_metrics": [],
                                    "dimensions": [],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWS",
    )
    ctx = TableContext(
        table_name="dws_sales_daily",
        layer="DWS",
        ddl="",
        etl_sql="",
        upstream_tables=["dwd_order_detail", "dwd_refund_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "dwd_order_detail": {"atomic_metrics": ["subtotal"]},
            "dwd_refund_detail": {"atomic_metrics": ["subtotal"]},
        },
    )

    validation = validate_metric_relationships(result, ctx)

    assert validation.get("ambiguous_base_metrics") == ["sale_amount:subtotal"]


def _assert_result_status_from_validation():
    result = parse_response(
        "dwd_order_detail",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [{"name": "pay_amt"}],
                                    "derived_metrics": [],
                                    "dimensions": [],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWD",
    )

    result.validation = {
        "unknown_columns": [],
        "duplicate_columns": [],
        "missing_columns": ["etl_time"],
    }
    assert result.status == "blocked"

    result.validation["unknown_columns"] = ["ghost_amt"]
    assert result.status == "blocked"

    result.validation = {
        "unknown_columns": [],
        "duplicate_columns": [],
        "missing_columns": [],
    }
    assert result.status == "passed"

    result.validation = {
        "ambiguous_min_max_aggregation": ["MAX(updated_at) AS updated_at"]
    }
    assert result.status == "warning"


@pytest.mark.parametrize(
    "confidence",
    [float("nan"), float("inf"), float("-inf"), -0.1, 1.1],
)
def test_inspect_result_rejects_non_finite_or_out_of_range_confidence(
    confidence,
):
    result = _inspection_result(confidence=confidence)

    assert result.confidence == 0.0
    assert result.status == "blocked"


def test_inspect_blocks_metric_write_when_ddl_columns_unavailable(
    tmp_path,
    monkeypatch,
):
    inspector = TableInspector(
        api_key="test",
        cache_file=tmp_path / "cache.json",
        max_retries=1,
    )
    context = TableContext(
        table_name="sales_detail",
        layer="DWD",
        ddl="",
        etl_sql="SELECT * FROM source_detail",
        upstream_tables=["source_detail"],
        downstream_tables=[],
    )
    response = {
        "inferred_layer": "DWD",
        "table_type": "fact",
        "confidence": 0.9,
        "reasoning_steps": [],
        "entities": [
            {
                "code": "SALE",
                "type": "primary",
                "key_columns": ["sale_id"],
            }
        ],
        "columns": {
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    }

    result, prompts = _inspect_with_responses(
        inspector,
        context,
        [response],
        monkeypatch,
    )

    assert len(prompts) == 1
    assert result.status == "blocked"
    assert result.validation["ddl_columns_unavailable"] == [
        "无法从DDL建立字段集合，禁止覆盖指标分组"
    ]


def test_inspect_preserves_llm_metric_groups(tmp_path, monkeypatch):
    inspector = TableInspector(
        api_key="test", cache_file=tmp_path / "cache.json"
    )
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        ddl="""CREATE TABLE shop_dm.dwd_order_detail (
            order_id BIGINT,
            quantity INT,
            unit_price DECIMAL(12,2),
            discount DECIMAL(12,2),
            subtotal DECIMAL(12,2),
            etl_time DATETIME
        );""",
        etl_sql="""INSERT INTO shop_dm.dwd_order_detail
        SELECT order_id, quantity, unit_price, discount, subtotal, NOW()
        FROM shop_dm.ods_order_item;""",
        upstream_tables=["ods_order_item"],
        downstream_tables=["dws_store_sales_daily"],
    )
    response = {
        "inferred_layer": "DWD",
        "table_type": "fact",
        "confidence": 0.95,
        "entities": [
            {
                "code": "ORDER",
                "type": "primary",
                "key_columns": ["order_id"],
            }
        ],
        "columns": {
            "atomic_metrics": [
                {"name": "quantity", "data_type": "INT"},
                {"name": "unit_price", "data_type": "DECIMAL(12,2)"},
                {"name": "discount", "data_type": "DECIMAL(12,2)"},
                {"name": "subtotal", "data_type": "DECIMAL(12,2)"},
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [
                {
                    "name": "order_id",
                    "dimension_type": "primary_key",
                }
            ],
            "others": [{"name": "etl_time", "role": "audit"}],
        },
    }
    monkeypatch.setattr(
        inspector,
        "_call_api",
        lambda _prompt: json.dumps(
            {"choices": [{"message": {"content": json.dumps(response)}}]}
        ),
    )

    result = inspector.inspect(ctx)

    assert [item["name"] for item in result.atomic_metrics] == [
        "quantity",
        "unit_price",
        "discount",
        "subtotal",
    ]
    assert result.calculated_metrics == []
    assert [item["name"] for item in result.dimensions] == ["order_id"]
    assert result.validation == {
        "unknown_columns": [],
        "duplicate_columns": [],
        "missing_columns": [],
    }
    assert result.status == "passed"


# ============================================================
# 3. 缓存测试
# ============================================================


def _assert_cache_hit_skips_api(tmp_path):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)

    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="ddl1",
        etl_sql="etl1",
        upstream_tables=[],
        downstream_tables=[],
    )

    # 模拟缓存文件已存在
    cached = parse_response(
        "t1",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "dimension",
                                "confidence": 0.9,
                                "reasoning_steps": ["cached"],
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "dimensions": [],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWD",
    )
    cache_data = {
        "t1": {
            "hash": inspector._compute_hash(ctx),
            # 旧缓存可能包含派生字段，读取时应忽略并重新计算。
            "result": result_to_dict(cached),
        }
    }
    cache_file.write_text(json.dumps(cache_data))

    # 重新加载缓存
    inspector._load_cache()

    with patch.object(inspector, "_call_api") as mock_api:
        res = inspector.inspect(ctx)
        mock_api.assert_not_called()
        assert res.table_type == "dimension"
        assert res.reasoning_steps == ["cached"]


def _assert_cache_retains_prompt_variants(tmp_path):
    cache_file = tmp_path / "cache.json"
    first_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
    )
    base_context = dict(
        table_name="store_summary",
        layer="DWS",
        ddl="CREATE TABLE store_summary (store_id BIGINT);",
        etl_sql="SELECT store_id FROM order_detail;",
        upstream_tables=["order_detail"],
        downstream_tables=[],
    )
    classification_context = TableContext(**base_context)
    metric_context = TableContext(
        upstream_metric_groups={
            "order_detail": {
                "atomic_metrics": ["subtotal"],
                "derived_metrics": [],
                "calculated_metrics": [],
            }
        },
        **base_context,
    )
    response = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "store_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        }
    )

    with patch.object(
        first_inspector,
        "_call_api",
        return_value=response,
    ) as first_api:
        first_inspector.inspect(classification_context)
        first_inspector.inspect(metric_context)
        assert first_api.call_count == 2

    saved = json.loads(cache_file.read_text())
    assert len(saved["store_summary"]["variants"]) == 2

    second_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
    )
    with patch.object(second_inspector, "_call_api") as second_api:
        second_inspector.inspect(classification_context)
        second_inspector.inspect(metric_context)
        second_api.assert_not_called()


def _assert_failed_result_does_not_poison_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    context = TableContext(
        table_name="customer",
        layer="DWD",
        ddl="CREATE TABLE customer (customer_id BIGINT);",
        etl_sql="SELECT customer_id FROM source_customer;",
        upstream_tables=["source_customer"],
        downstream_tables=[],
    )
    failed_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
    )
    with patch.object(
        failed_inspector,
        "_call_api",
        side_effect=RuntimeError("temporary outage"),
    ) as failed_api:
        failed_result = failed_inspector.inspect(context)
        assert failed_api.call_count == 1
    assert failed_result.status == "blocked"
    assert not cache_file.exists()

    recovered_response = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DIM",
                                "table_type": "dimension",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "customer_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        }
    )
    recovered_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=2,
    )
    with patch.object(
        recovered_inspector,
        "_call_api",
        return_value=recovered_response,
    ) as recovered_api:
        recovered_result = recovered_inspector.inspect(context)
        assert recovered_api.call_count == 1
    assert recovered_result.status == "passed"


def _assert_warning_cache_preserves_status_and_retry_budget(tmp_path):
    cache_file = tmp_path / "cache.json"
    context = TableContext(
        table_name="latest_event",
        layer="DWD",
        ddl=(
            "CREATE TABLE latest_event (event_id BIGINT, updated_at DATETIME);"
        ),
        etl_sql=(
            "SELECT event_id, MAX(updated_at) AS updated_at "
            "FROM source_event GROUP BY event_id"
        ),
        upstream_tables=["source_event"],
        downstream_tables=[],
    )
    dwd_response = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "code": "EVENT",
                                        "type": "primary",
                                        "key_columns": ["event_id"],
                                    }
                                ],
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "event_id"}],
                                    "others": [{"name": "updated_at"}],
                                },
                            }
                        )
                    }
                }
            ]
        }
    )
    first_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
    )
    with patch.object(
        first_inspector,
        "_call_api",
        return_value=dwd_response,
    ) as first_api:
        first_result = first_inspector.inspect(context)
        assert first_api.call_count == 1
    assert first_result.status == "warning"

    cached_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
    )
    with patch.object(cached_inspector, "_call_api") as cached_api:
        cached_result = cached_inspector.inspect(context)
        cached_api.assert_not_called()
    assert cached_result.status == "warning"
    assert (
        cached_result.validation["ambiguous_min_max_aggregation"]
        == (first_result.validation["ambiguous_min_max_aggregation"])
    )

    dws_response = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "event_id"}],
                                    "others": [{"name": "updated_at"}],
                                },
                            }
                        )
                    }
                }
            ]
        }
    )
    higher_retry_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=2,
    )
    with patch.object(
        higher_retry_inspector,
        "_call_api",
        return_value=dws_response,
    ) as higher_retry_api:
        higher_retry_result = higher_retry_inspector.inspect(context)
        assert higher_retry_api.call_count == 1
    assert higher_retry_result.status == "passed"


def _assert_cache_miss_calls_api(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)

    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="CREATE TABLE t1 (pay_amt DECIMAL(12,2));",
        etl_sql="etl1",
        upstream_tables=[],
        downstream_tables=[],
    )

    # mock _call_api
    monkeypatch.setattr(
        inspector,
        "_call_api",
        lambda p: json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "inferred_layer": "DWD",
                                    "table_type": "fact",
                                    "confidence": 0.8,
                                    "reasoning_steps": ["api"],
                                    "entities": [
                                        {
                                            "code": "PAYMENT",
                                            "type": "primary",
                                            "key_columns": ["pay_amt"],
                                        }
                                    ],
                                    "columns": {
                                        "atomic_metrics": [
                                            {
                                                "name": "pay_amt",
                                                "data_type": "DECIMAL(12,2)",
                                                "business_process": "订单支付",
                                                "action": "pay",
                                                "measure": "amt",
                                                "confidence": 0.9,
                                            }
                                        ],
                                        "derived_metrics": [],
                                        "dimensions": [],
                                        "others": [],
                                    },
                                }
                            )
                        }
                    }
                ]
            }
        ),
    )

    res = inspector.inspect(ctx)
    assert res.table_type == "fact"
    assert res.atomic_metrics[0]["name"] == "pay_amt"

    # 验证缓存被更新
    saved = json.loads(cache_file.read_text())
    assert "t1" in saved
    assert saved["t1"]["result"]["table_type"] == "fact"
    assert (
        saved["t1"]["result"]["columns"]["atomic_metrics"][0]["name"]
        == "pay_amt"
    )
    assert "is_violating_declared_layer" not in saved["t1"]["result"]
    assert "status" not in saved["t1"]["result"]
    assert "is_violating_current_name" not in saved["t1"]["result"]


def _assert_progress_callback_reports_batch_events(tmp_path, monkeypatch):
    inspector = TableInspector(
        api_key="test",
        cache_file=tmp_path / "cache.json",
        parallelism=1,
    )
    events = []
    inspector.progress_callback = events.append

    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="CREATE TABLE t1 (pay_amt DECIMAL(12,2));",
        etl_sql="INSERT INTO t1 SELECT 1;",
        upstream_tables=[],
        downstream_tables=[],
    )
    monkeypatch.setattr(
        inspector,
        "_call_api",
        lambda _prompt: json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "inferred_layer": "DWD",
                                    "table_type": "fact",
                                    "confidence": 0.9,
                                    "entities": [
                                        {
                                            "code": "PAY",
                                            "type": "primary",
                                            "key_columns": ["pay_amt"],
                                        }
                                    ],
                                    "columns": {
                                        "atomic_metrics": [
                                            {"name": "pay_amt"}
                                        ],
                                        "derived_metrics": [],
                                        "calculated_metrics": [],
                                        "dimensions": [],
                                        "others": [],
                                    },
                                }
                            )
                        }
                    }
                ]
            }
        ),
    )

    result = inspector.inspect_batch([ctx])[0]

    assert result.status == "passed"
    assert [event["event"] for event in events] == [
        "start",
        "api_call",
        "finish",
    ]
    assert events[0]["index"] == 1
    assert events[0]["total"] == 1
    assert events[-1]["status"] == "passed"
    assert events[-1]["atomic_metric_count"] == 1


def _assert_progress_callback_reports_cache_hit(tmp_path):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)
    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="CREATE TABLE t1 (id BIGINT);",
        etl_sql="",
        upstream_tables=[],
        downstream_tables=[],
    )
    cached = parse_response(
        "t1",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "dimension",
                                "confidence": 0.9,
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="DWD",
    )
    cache_file.write_text(
        json.dumps(
            {
                "t1": {
                    "hash": inspector._compute_hash(ctx),
                    "result": result_to_cache_dict(cached),
                }
            }
        )
    )
    inspector._load_cache()
    events = []
    inspector.progress_callback = events.append

    result = inspector.inspect_batch([ctx])[0]

    assert result.status == "passed"
    assert [event["event"] for event in events] == [
        "start",
        "cache_hit",
        "finish",
    ]


def _assert_inspect_retries_validation_errors(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(
        api_key="test", cache_file=cache_file, max_retries=1
    )
    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="""CREATE TABLE shop_dm.t1 (
            order_id BIGINT,
            pay_amt DECIMAL(12,2),
            etl_time DATETIME
        );""",
        etl_sql="INSERT INTO shop_dm.t1 SELECT 1, 2, NOW();",
        upstream_tables=[],
        downstream_tables=[],
    )

    responses = [
        {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.9,
            "columns": {
                "atomic_metrics": [{"name": "ghost_amt"}],
                "derived_metrics": [],
                "dimensions": [{"name": "order_id"}],
                "others": [{"name": "etl_time"}],
            },
        },
        {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.9,
            "entities": [
                {
                    "code": "ORDER",
                    "type": "primary",
                    "key_columns": ["order_id"],
                }
            ],
            "columns": {
                "atomic_metrics": [{"name": "pay_amt"}],
                "derived_metrics": [],
                "dimensions": [{"name": "order_id"}],
                "others": [{"name": "etl_time"}],
            },
        },
    ]

    result, calls = _inspect_with_responses(
        inspector, ctx, responses, monkeypatch
    )

    assert len(calls) == 2
    assert "上次返回结果校验未通过" in calls[1]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.validation["unknown_columns"] == []


def _assert_inspect_normalizes_convertible_time_periods_without_retry(
    tmp_path, monkeypatch
):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(
        api_key="test", cache_file=cache_file, max_retries=1
    )
    ctx = TableContext(
        table_name="dws_category_sales_monthly",
        layer="DWS",
        ddl="""CREATE TABLE shop_dm.dws_category_sales_monthly (
            category_id BIGINT,
            stat_month_date DATE,
            sale_amount DECIMAL(18,2)
        );""",
        etl_sql=(
            "INSERT INTO shop_dm.dws_category_sales_monthly "
            "SELECT category_id, stat_month_date, SUM(subtotal) "
            "FROM dwd_order_detail GROUP BY category_id, stat_month_date;"
        ),
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "dwd_order_detail": {"atomic_metrics": ["subtotal"]}
        },
    )

    responses = [
        {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "grain": {
                "entities": ["PROD"],
                "time_column": "stat_month_date",
                "time_period": "月",
            },
            "columns": {
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
                "dimensions": [
                    {"name": "category_id"},
                    {"name": "stat_month_date"},
                ],
                "others": [],
            },
        },
    ]
    result, calls = _inspect_with_responses(
        inspector, ctx, responses, monkeypatch
    )

    assert len(calls) == 1
    assert result.status == "passed"
    assert result.retry_count == 0
    assert result.grain["time_period"] == "M"
    assert result.derived_metrics[0]["time_period"] == "M"


def _assert_inspect_retries_unrecognized_time_periods(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(
        api_key="test", cache_file=cache_file, max_retries=1
    )
    ctx = TableContext(
        table_name="dws_category_sales_monthly",
        layer="DWS",
        ddl="""CREATE TABLE shop_dm.dws_category_sales_monthly (
            category_id BIGINT,
            stat_month_date DATE,
            sale_amount DECIMAL(18,2)
        );""",
        etl_sql=(
            "INSERT INTO shop_dm.dws_category_sales_monthly "
            "SELECT category_id, stat_month_date, SUM(subtotal) "
            "FROM dwd_order_detail GROUP BY category_id, stat_month_date;"
        ),
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "dwd_order_detail": {"atomic_metrics": ["subtotal"]}
        },
    )
    responses = [
        {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "grain": {
                "entities": ["PROD"],
                "time_column": "stat_month_date",
                "time_period": "月累计",
            },
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [
                    {
                        "name": "sale_amount",
                        "base_metric": "subtotal",
                        "base_metric_table": "dwd_order_detail",
                        "time_period": "月累计",
                        "expression": "SUM(subtotal)",
                    }
                ],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "category_id"},
                    {"name": "stat_month_date"},
                ],
                "others": [],
            },
        },
        {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "grain": {
                "entities": ["PROD"],
                "time_column": "stat_month_date",
                "time_period": "M",
            },
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [
                    {
                        "name": "sale_amount",
                        "base_metric": "subtotal",
                        "base_metric_table": "dwd_order_detail",
                        "time_period": "M",
                        "expression": "SUM(subtotal)",
                    }
                ],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "category_id"},
                    {"name": "stat_month_date"},
                ],
                "others": [],
            },
        },
    ]
    calls = []

    def fake_api(prompt):
        calls.append(prompt)
        data = responses[len(calls) - 1]
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(data)}}]}
        )

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    result = inspector.inspect(ctx)

    assert len(calls) == 2
    assert "invalid_time_periods" in calls[1]
    assert "grain.time_period=月累计" in calls[1]
    assert "derived_metrics[0].time_period=月累计" in calls[1]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.grain["time_period"] == "M"
    assert result.derived_metrics[0]["time_period"] == "M"


def _assert_inspect_retries_invalid_metric_expressions(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(
        api_key="test", cache_file=cache_file, max_retries=1
    )
    ctx = TableContext(
        table_name="dws_store_sales_daily",
        layer="DWS",
        ddl="""CREATE TABLE shop_dm.dws_store_sales_daily (
            store_id BIGINT,
            stat_date DATE,
            sale_amount DECIMAL(18,2)
        );""",
        etl_sql=(
            "INSERT INTO shop_dm.dws_store_sales_daily "
            "SELECT store_id, order_date, SUM(subtotal) "
            "FROM dwd_order_detail GROUP BY store_id, order_date;"
        ),
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
        upstream_metric_groups={
            "dwd_order_detail": {"atomic_metrics": ["subtotal"]}
        },
    )
    responses = [
        {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "grain": {
                "entities": ["STORE"],
                "time_column": "stat_date",
                "time_period": "D",
            },
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [
                    {
                        "name": "sale_amount",
                        "base_metric": "subtotal",
                        "base_metric_table": "dwd_order_detail",
                        "time_period": "D",
                        "expression": (
                            "SUM(subtotal) GROUP BY store_id, order_date"
                        ),
                    }
                ],
                "calculated_metrics": [],
                "dimensions": [{"name": "store_id"}, {"name": "stat_date"}],
                "others": [],
            },
        },
        {
            "inferred_layer": "DWS",
            "table_type": "fact",
            "confidence": 0.9,
            "grain": {
                "entities": ["STORE"],
                "time_column": "stat_date",
                "time_period": "D",
            },
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [
                    {
                        "name": "sale_amount",
                        "base_metric": "subtotal",
                        "base_metric_table": "dwd_order_detail",
                        "time_period": "D",
                        "expression": "SUM(subtotal)",
                    }
                ],
                "calculated_metrics": [],
                "dimensions": [{"name": "store_id"}, {"name": "stat_date"}],
                "others": [],
            },
        },
    ]
    calls = []

    def fake_api(prompt):
        calls.append(prompt)
        data = responses[len(calls) - 1]
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(data)}}]}
        )

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    result = inspector.inspect(ctx)

    assert len(calls) == 2
    assert "invalid_metric_expressions" in calls[1]
    assert (
        "derived_metrics[0].expression="
        "SUM(subtotal) GROUP BY store_id, order_date"
    ) in calls[1]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.derived_metrics[0]["expression"] == "SUM(subtotal)"


def _assert_inspect_retries_missing_dwd_fact_primary_entity(
    tmp_path, monkeypatch
):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(
        api_key="test", cache_file=cache_file, max_retries=1
    )
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        ddl="""CREATE TABLE shop_dm.dwd_order_detail (
            order_id BIGINT,
            order_item_id BIGINT,
            customer_id BIGINT,
            quantity INT
        );""",
        etl_sql="INSERT INTO shop_dm.dwd_order_detail SELECT * FROM ods;",
        upstream_tables=["ods_order_item"],
        downstream_tables=["dws_product_sales_daily"],
    )
    responses = [
        {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.9,
            "entities": [
                {
                    "code": "ORDER",
                    "type": "foreign",
                    "key_columns": ["order_id"],
                },
                {
                    "code": "CUST",
                    "type": "foreign",
                    "key_columns": ["customer_id"],
                },
            ],
            "columns": {
                "atomic_metrics": [{"name": "quantity"}],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "order_id"},
                    {"name": "order_item_id"},
                    {"name": "customer_id"},
                ],
                "others": [],
            },
        },
        {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "confidence": 0.9,
            "entities": [
                {
                    "code": "ORDER_ITEM",
                    "type": "primary",
                    "key_columns": ["order_id", "order_item_id"],
                },
                {
                    "code": "CUST",
                    "type": "foreign",
                    "key_columns": ["customer_id"],
                },
            ],
            "columns": {
                "atomic_metrics": [{"name": "quantity"}],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [
                    {"name": "order_id"},
                    {"name": "order_item_id"},
                    {"name": "customer_id"},
                ],
                "others": [],
            },
        },
    ]
    calls = []

    def fake_api(prompt):
        calls.append(prompt)
        data = responses[len(calls) - 1]
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(data)}}]}
        )

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    result = inspector.inspect(ctx)

    assert len(calls) == 2
    assert "missing_primary_entities" in calls[1]
    assert "DWD fact必须返回至少一个type=primary" in calls[1]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.entities[0]["code"] == "ORDER_ITEM"
    assert result.entities[0]["type"] == "primary"


def _fact_retry_response(
    layer, *, entity_code, metric_names=(), dimension_names=(), other_names=()
):
    return {
        "inferred_layer": layer,
        "table_type": "fact",
        "confidence": 0.9,
        "entities": [
            {
                "code": entity_code,
                "type": "primary",
                "key_columns": [dimension_names[0]],
            }
        ],
        "columns": {
            "atomic_metrics": [{"name": name} for name in metric_names],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [{"name": name} for name in dimension_names],
            "others": [{"name": name} for name in other_names],
        },
    }


def _layer_contract_retry_case(scenario):
    if scenario == "layer-table-type":
        context = TableContext(
            table_name="customer_cleaned",
            layer="DWD",
            ddl=(
                "CREATE TABLE customer_cleaned ("
                "customer_id BIGINT, customer_name STRING);"
            ),
            etl_sql=(
                "INSERT INTO customer_cleaned "
                "SELECT customer_id, customer_name FROM customer_source;"
            ),
            upstream_tables=["customer_source"],
            downstream_tables=["customer"],
        )
        common = {
            "inferred_layer": "DWD",
            "confidence": 0.9,
            "columns": {
                "atomic_metrics": [],
                "derived_metrics": [],
                "calculated_metrics": [],
                "dimensions": [],
                "others": [],
            },
        }
        return (
            context,
            [
                {**common, "table_type": "dimension"},
                {**common, "table_type": "other"},
            ],
            ("inconsistent_layer_table_types",),
        )

    if scenario == "other-fact":
        context = TableContext(
            table_name="status_event",
            layer="DWD",
            ddl=(
                "CREATE TABLE status_event ("
                "event_id BIGINT, event_date DATE, etl_time DATETIME);"
            ),
            etl_sql=(
                "INSERT INTO status_event "
                "SELECT id, event_date, CURRENT_TIMESTAMP FROM source_event"
            ),
            upstream_tables=["source_event"],
            downstream_tables=[],
        )
        response_args = {
            "entity_code": "STATUS_EVENT",
            "dimension_names": ("event_id", "event_date"),
            "other_names": ("etl_time",),
        }
        return (
            context,
            [
                _fact_retry_response("OTHER", **response_args),
                _fact_retry_response("DWD", **response_args),
            ],
            ("OTHER/fact", "不要用 OTHER 代替 ODS"),
        )

    if scenario == "group-by":
        context = TableContext(
            table_name="entity_daily_metrics",
            layer="DWD",
            ddl=(
                "CREATE TABLE entity_daily_metrics ("
                "entity_id BIGINT, metric_date DATE, event_count BIGINT);"
            ),
            etl_sql=(
                "SELECT entity_id, metric_date, COUNT(*) AS event_count "
                "FROM event_detail GROUP BY entity_id, metric_date"
            ),
            upstream_tables=["event_detail"],
            downstream_tables=[],
            column_lineage=[
                {
                    "source": "event_detail.entity_id",
                    "target": "entity_daily_metrics.event_count",
                    "condition_lineage": [
                        {
                            "source": "event_detail.entity_id",
                            "condition_type": "GROUP_BY",
                            "condition_expression": "entity_id, metric_date",
                        }
                    ],
                }
            ],
        )
        response_args = {
            "entity_code": "ENTITY",
            "metric_names": ("event_count",),
            "dimension_names": ("entity_id", "metric_date"),
        }
        markers = ("inconsistent_layer_sql",)
    else:
        context = TableContext(
            table_name="entity_metric_snapshot",
            layer="DWD",
            ddl=(
                "CREATE TABLE entity_metric_snapshot ("
                "entity_id BIGINT, published_metric_count BIGINT);"
            ),
            etl_sql=(
                "SELECT e.entity_id, m.metric_count AS published_metric_count "
                "FROM entity e LEFT JOIN entity_metrics m "
                "ON e.entity_id = m.entity_id"
            ),
            upstream_tables=["entity", "entity_metrics"],
            downstream_tables=[],
            upstream_metric_groups={
                "entity_metrics": {
                    "atomic_metrics": [{"name": "metric_count"}],
                }
            },
            column_lineage=[
                {
                    "source": "entity_metrics.metric_count",
                    "target": "entity_metric_snapshot.published_metric_count",
                }
            ],
        )
        response_args = {
            "entity_code": "ENTITY",
            "metric_names": ("published_metric_count",),
            "dimension_names": ("entity_id",),
        }
        markers = (
            "inconsistent_upstream_metric_layers",
            "上游指标分组中的已治理指标",
        )

    return (
        context,
        [
            _fact_retry_response("DWD", **response_args),
            _fact_retry_response("DWS", **response_args),
        ],
        markers,
    )


@pytest.mark.parametrize(
    "scenario",
    ["layer-table-type", "other-fact", "group-by", "upstream-metric"],
)
def test_inspector_retries_layer_contracts(scenario, tmp_path, monkeypatch):
    context, responses, prompt_markers = _layer_contract_retry_case(scenario)
    inspector = TableInspector(
        api_key="test",
        cache_file=tmp_path / "cache.json",
        max_retries=1,
    )

    result, calls = _inspect_with_responses(
        inspector, context, responses, monkeypatch
    )

    assert len(calls) == 2
    assert all(marker in calls[1] for marker in prompt_markers)
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.inferred_layer == responses[1]["inferred_layer"]
    assert result.table_type == responses[1]["table_type"]


def _assert_cache_hash_includes_context_fields(tmp_path):
    inspector = TableInspector(
        api_key="test", cache_file=tmp_path / "cache.json"
    )

    base = dict(
        table_name="t1",
        ddl="ddl1",
        etl_sql="etl1",
        upstream_tables=[],
        downstream_tables=[],
    )
    dwd_ctx = TableContext(layer="DWD", **base)
    dws_ctx = TableContext(layer="DWS", **base)

    assert inspector._compute_hash(dwd_ctx) != inspector._compute_hash(dws_ctx)

    other_model = TableInspector(
        api_key="test",
        model="deepseek-v4-pro",
        cache_file=tmp_path / "cache.json",
    )
    other_backend = TableInspector(
        api_key="test",
        base_url="https://example.test/chat/completions",
        cache_file=tmp_path / "cache.json",
    )
    assert inspector._compute_hash(dwd_ctx) != other_model._compute_hash(
        dwd_ctx
    )
    assert inspector._compute_hash(dwd_ctx) != other_backend._compute_hash(
        dwd_ctx
    )

    base = dict(
        table_name="t1",
        layer="DWD",
        ddl="ddl1",
        etl_sql="etl1",
        upstream_tables=[],
        downstream_tables=[],
    )
    retail_ctx = TableContext(project_context="零售订单交易背景", **base)
    finance_ctx = TableContext(project_context="金融账户交易背景", **base)

    assert inspector._compute_hash(retail_ctx) != inspector._compute_hash(
        finance_ctx
    )

    upstream_dwd_ctx = TableContext(
        upstream_table_layers={"source": "DWD"},
        **base,
    )
    upstream_ods_ctx = TableContext(
        upstream_table_layers={"source": "ODS"},
        **base,
    )
    downstream_dws_ctx = TableContext(
        downstream_table_layers={"target": "DWS"},
        **base,
    )
    downstream_ads_ctx = TableContext(
        downstream_table_layers={"target": "ADS"},
        **base,
    )

    assert inspector._compute_hash(upstream_dwd_ctx) != (
        inspector._compute_hash(upstream_ods_ctx)
    )
    assert inspector._compute_hash(downstream_dws_ctx) != (
        inspector._compute_hash(downstream_ads_ctx)
    )

    hidden_dws_ctx = TableContext(
        downstream_table_layers={"target": "DWS"},
        expose_layer_hints=False,
        **base,
    )
    hidden_ads_ctx = TableContext(
        downstream_table_layers={"target": "ADS"},
        expose_layer_hints=False,
        **base,
    )
    assert inspector._compute_hash(hidden_dws_ctx) == (
        inspector._compute_hash(hidden_ads_ctx)
    )
    assert inspector._compute_hash(hidden_dws_ctx) != (
        inspector._compute_hash(downstream_dws_ctx)
    )
    downstream_publication_ctx = TableContext(
        downstream_entity_publication_features={
            "published_entity": {
                "generated_key_columns": ["entity_key"],
                "natural_key_aliases": ["entity_natural_key"],
                "added_version_control_columns": [],
                "combines_sources_with_union": False,
                "contains_aggregation": False,
            }
        },
        **base,
    )
    assert inspector._compute_hash(downstream_publication_ctx) != (
        inspector._compute_hash(TableContext(**base))
    )
    assert inspector.parallelism == 2


def test_inspect_batch_runs_with_configured_parallelism(monkeypatch):
    inspector = TableInspector(api_key="test", cache_file=None, parallelism=2)
    contexts = [
        TableContext(
            table_name=f"t{i}",
            layer="DWD",
            ddl="CREATE TABLE t (id BIGINT);",
            etl_sql="",
            upstream_tables=[],
            downstream_tables=[],
        )
        for i in range(4)
    ]

    active = 0
    max_active = 0
    calls = 0
    lock = threading.Lock()

    def fake_api(_prompt):
        nonlocal active, max_active, calls
        with lock:
            active += 1
            calls += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.05)
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "inferred_layer": "DWD",
                                        "table_type": "other",
                                        "confidence": 0.9,
                                        "reasoning_steps": ["api"],
                                        "columns": {
                                            "atomic_metrics": [],
                                            "derived_metrics": [],
                                            "dimensions": [],
                                            "others": [],
                                        },
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    results = inspector.inspect_batch(contexts)

    assert [res.table_name for res in results] == ["t0", "t1", "t2", "t3"]
    assert calls == 4
    assert 1 < max_active <= 2


# ============================================================
# 4. 集成测试 (标记 api)
# ============================================================


@pytest.mark.api
def test_inspect_dimension_table():
    import os

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    from tests.assess.conftest import DDL_DWD_CUSTOMER, ETL_DWD_CUSTOMER

    inspector = TableInspector(api_key=api_key, cache_file=None)
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        ddl=DDL_DWD_CUSTOMER,
        etl_sql=ETL_DWD_CUSTOMER,
        upstream_tables=["ods_customer"],
        downstream_tables=["ads_rfm"],
    )

    res = inspector.inspect(ctx)
    assert res.table_name == "dwd_customer"
    assert res.table_type in {"dimension", "other"}
    assert res.confidence > 0.5


@pytest.mark.api
def test_inspect_fact_table():
    import os

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    from tests.assess.conftest import (
        DDL_DWD_ORDER_DETAIL,
        ETL_DWD_ORDER_DETAIL,
    )

    inspector = TableInspector(api_key=api_key, cache_file=None)
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        ddl=DDL_DWD_ORDER_DETAIL,
        etl_sql=ETL_DWD_ORDER_DETAIL,
        upstream_tables=["ods_order", "ods_order_item", "ods_product"],
        downstream_tables=["dws_store_sales_daily"],
    )

    res = inspector.inspect(ctx)
    assert res.table_name == "dwd_order_detail"
    assert res.table_type == "fact"
    assert res.confidence > 0.5
