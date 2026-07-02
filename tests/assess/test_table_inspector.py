import json
import threading
import time
import urllib.error
from unittest.mock import patch

import pytest

from assess.llm.table_inspector import (
    TableContext,
    TableInspector,
    TableInspectResult,
    build_prompt,
    parse_response,
    result_to_cache_dict,
    result_to_dict,
    validate_candidate_layer,
    validate_columns,
    validate_metadata_quality,
    validate_metric_expressions,
    validate_metric_relationships,
    validate_primary_entities,
    validate_time_periods,
)

# ============================================================
# 1. Prompt 组装测试
# ============================================================


def test_build_prompt_scenarios():
    _assert_build_prompt_exposes_context_and_json_contract()
    _assert_build_prompt_omits_empty_etl_section()
    _assert_build_prompt_keeps_metadata_contracts_without_project_examples()
    _assert_build_prompt_includes_catalog_and_project_context_as_inputs()
    _assert_build_prompt_documents_business_metadata_scope()
    _assert_build_prompt_keeps_metric_expression_separate_from_grain()
    _assert_build_prompt_groups_metrics_from_inferred_layer()
    _assert_build_prompt_limits_candidate_layers()


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
        _assert_parse_response_repairs_unescaped_quotes_inside_string_values,
        _assert_parse_response_ignores_legacy_layer_reason_fields,
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
        _assert_validate_primary_entities_uses_inferred_dwd_for_cold_start,
        _assert_validate_candidate_layer_rejects_non_middle_layer,
        _assert_validate_metadata_quality_requires_dws_and_dim_semantics,
        _assert_base_metric_relationship_validation_blocks_invalid_references,
        _assert_validate_columns_flags_unknown_duplicate_and_missing_fields,
        _assert_validate_columns_requires_all_dws_fact_fields,
        _assert_validate_metric_relationships_requires_derived_base_metric_in_upstream_atomic,
        _assert_validate_metric_relationships_flags_ambiguous_unqualified_base_metric,
        _assert_result_status_from_validation,
    ]

    for helper in helpers:
        helper()


def test_inspector_cache_and_progress_scenarios(tmp_path_factory, monkeypatch):
    _assert_cache_hit_skips_api(tmp_path_factory.mktemp("cache_hit"))
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


def _assert_build_prompt_groups_metrics_from_inferred_layer():
    ctx = TableContext(
        table_name="sales_daily",
        layer="OTHER",
        ddl="CREATE TABLE sales_daily (store_id BIGINT, total_amt DECIMAL);",
        etl_sql=(
            "INSERT INTO sales_daily SELECT store_id, SUM(pay_amt) total_amt "
            "FROM order_detail GROUP BY store_id;"
        ),
        upstream_tables=["order_detail"],
        downstream_tables=[],
    )

    prompt = build_prompt(ctx)

    assert "冷启动时原始配置可能是 OTHER" in prompt
    assert "inferred_layer 是 DWD 或 DWS" in prompt
    assert "不要因为原始配置层级是 OTHER 而跳过指标字段分组" in prompt

    result = parse_response(
        "sales_daily",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWS",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "reasoning_steps": ["公共汇总事实"],
                                "columns": {
                                    "atomic_metrics": [
                                        {"name": "total_amt"}
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
        },
        "OTHER",
    )

    validation = validate_columns(result, {"store_id", "total_amt"})

    assert validation["missing_columns"] == ["store_id"]


def _assert_build_prompt_limits_candidate_layers():
    ctx = TableContext(
        table_name="customer_monthly_summary",
        layer="OTHER",
        ddl=(
            "CREATE TABLE customer_monthly_summary "
            "(customer_id BIGINT, stat_month DATE, total_amount DECIMAL);"
        ),
        etl_sql=(
            "INSERT INTO customer_monthly_summary "
            "SELECT customer_id, stat_month, SUM(pay_amount) total_amount "
            "FROM order_detail GROUP BY customer_id, stat_month;"
        ),
        upstream_tables=["order_detail"],
        downstream_tables=[],
        candidate_layers=("DWD", "DWS", "DIM"),
    )

    prompt = build_prompt(ctx)

    assert "本轮候选层约束" in prompt
    assert "只允许在 DWD, DWS, DIM 中选择 inferred_layer" in prompt
    assert '"inferred_layer": "DWD|DWS|DIM"' in prompt
    assert "不能把公共汇总表单独推到 ADS" in prompt


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
        ("DWD", "数据域与业务板块候选"),
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


def _assert_validate_primary_entities_uses_inferred_dwd_for_cold_start():
    result = parse_response(
        "order_detail",
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
                                        "code": "CUSTOMER",
                                        "type": "foreign",
                                        "key_columns": ["customer_id"],
                                    }
                                ],
                                "columns": {
                                    "atomic_metrics": [],
                                    "derived_metrics": [],
                                    "calculated_metrics": [],
                                    "dimensions": [{"name": "order_id"}],
                                    "others": [],
                                },
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="OTHER",
    )

    validation = validate_primary_entities(result)

    assert validation == {
        "missing_primary_entities": [
            "DWD fact必须返回至少一个type=primary的entities项"
        ]
    }


def _assert_validate_candidate_layer_rejects_non_middle_layer():
    result = parse_response(
        "customer_monthly_summary",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "ADS",
                                "table_type": "fact",
                                "confidence": 0.9,
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="OTHER",
    )

    validation = validate_candidate_layer(result, ("DWD", "DWS", "DIM"))

    assert validation == {
        "invalid_candidate_layers": [
            "inferred_layer=ADS 不在候选层 DIM,DWD,DWS 中"
        ]
    }


def _assert_validate_metadata_quality_requires_dws_and_dim_semantics():
    dws_result = parse_response(
        "agent_summary",
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
                                    "dimensions": [],
                                    "others": [],
                                },
                                "grain": {},
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="OTHER",
    )
    dim_result = parse_response(
        "economic_indicators_profile",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DIM",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "entities": [],
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="OTHER",
    )
    sparse_dim_result = parse_response(
        "economic_indicators_profile",
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DIM",
                                "table_type": "dimension",
                                "confidence": 0.9,
                                "entities": [],
                            }
                        )
                    }
                }
            ]
        },
        declared_layer="OTHER",
    )

    dws_validation = validate_metadata_quality(dws_result)
    dim_validation = validate_metadata_quality(dim_result)
    sparse_dim_validation = validate_metadata_quality(sparse_dim_result)
    assert dws_validation == {
        "missing_metric_metadata": ["DWS fact必须至少返回一个指标字段"],
        "missing_grain_metadata": ["DWS fact必须尽量返回表级grain"],
    }
    assert dim_validation == {
        "invalid_dimension_table_type": ["DIM层模型的table_type必须为dimension"],
        "missing_dimension_entities": [
            "DIM/dimension模型必须尽量返回一个type=primary的entities项"
        ],
    }
    assert sparse_dim_validation == {
        "missing_dimension_entities": [
            "DIM/dimension模型必须尽量返回一个type=primary的entities项"
        ]
    }
    dws_result.validation = dws_validation
    dim_result.validation = dim_validation
    sparse_dim_result.validation = sparse_dim_validation
    assert dws_result.status == "warning"
    assert dim_result.status == "blocked"
    assert sparse_dim_result.status == "warning"


def _assert_base_metric_relationship_validation_blocks_invalid_references():
    invalid_result = TableInspectResult(
        table_name="customer_monthly_summary",
        declared_layer="OTHER",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["公共汇总表"],
        validation={
            "invalid_base_metrics": ["total_amount:transaction_amount"]
        },
    )
    missing_result = TableInspectResult(
        table_name="customer_monthly_summary",
        declared_layer="OTHER",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["公共汇总表"],
        validation={"missing_base_metrics": ["total_amount"]},
    )
    candidate_layer_result = TableInspectResult(
        table_name="customer_monthly_summary",
        declared_layer="OTHER",
        inferred_layer="ADS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["越界层"],
        validation={"invalid_candidate_layers": ["ADS"]},
    )

    assert invalid_result.status == "blocked"
    assert missing_result.status == "blocked"
    assert candidate_layer_result.status == "blocked"


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

    from assess.llm.table_inspector import dict_to_result

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
            json.dumps(
                {
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "confidence": 0.8,
                    "reasoning_steps": ["test fact"],
                }
            ),
            "fact",
            0.8,
            None,
        ),
        (
            "t1",
            "```json\n"
            + json.dumps(
                {
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "confidence": 0.9,
                    "reasoning_steps": ["test"],
                }
            )
            + "\n```",
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


def _assert_parse_response_repairs_unescaped_quotes_inside_string_values():
    content = (
        '{"inferred_layer":"DIM","table_type":"dimension","confidence":0.91,'
        '"reasoning_steps":["表名包含 "profile" 且是实体属性表"],'
        '"dimension_role":"BASE","dimension_content_type":"INFO",'
        '"entities":[{"code":"ECONOMIC_INDICATOR","type":"primary",'
        '"key_columns":["economic_indicator_key"]}]}'
    )
    resp = {"choices": [{"message": {"content": content}}]}

    result = parse_response("economic_indicators_profile", resp)

    assert result.inferred_layer == "DIM"
    assert result.table_type == "dimension"
    assert result.confidence == 0.91
    assert result.reasoning_steps == ['表名包含 "profile" 且是实体属性表']
    assert result.dimension_role == "BASE"
    assert result.dimension_content_type == "INFO"
    assert result.entities == [
        {
            "code": "ECONOMIC_INDICATOR",
            "type": "primary",
            "key_columns": ["economic_indicator_key"],
        }
    ]


def _assert_parse_response_ignores_legacy_layer_reason_fields():
    resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "layer": "DIM",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reason": "legacy response",
                        }
                    )
                }
            }
        ]
    }

    result = parse_response("t1", resp)

    assert result.inferred_layer == "OTHER"
    assert result.reasoning_steps == []


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
    assert result.status == "warning"

    result.validation["unknown_columns"] = ["ghost_amt"]
    assert result.status == "blocked"

    result.validation = {
        "unknown_columns": [],
        "duplicate_columns": [],
        "missing_columns": [],
    }
    assert result.status == "passed"


def test_call_api_falls_back_to_v1_for_custom_base_url(monkeypatch):
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices": []}'

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                req.full_url,
                404,
                "not found",
                {},
                None,
            )
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    inspector = TableInspector(
        api_key="test",
        cache_file=None,
        base_url="https://api.example.com",
    )

    assert inspector._call_api("hello") == '{"choices": []}'
    assert calls == [
        "https://api.example.com/chat/completions",
        "https://api.example.com/v1/chat/completions",
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


def _assert_cache_miss_calls_api(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)

    ctx = TableContext(
        table_name="t1",
        layer="DWD",
        ddl="ddl_new",
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
    calls = []

    def fake_api(prompt):
        calls.append(prompt)
        data = responses[len(calls) - 1]
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(data)}}]}
        )

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    result = inspector.inspect(ctx)

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
