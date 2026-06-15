import json
import threading
import time
import pytest
from unittest.mock import patch

from assess.llm.table_inspector import (
    TableInspector,
    TableContext,
    build_prompt,
    parse_response,
    result_to_cache_dict,
    result_to_dict,
    validate_columns,
    validate_metric_relationships,
)


# ============================================================
# 1. Prompt 组装测试
# ============================================================

def test_build_prompt_includes_all_info():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        ddl="CREATE TABLE dwd_customer (id BIGINT);",
        etl_sql="INSERT INTO dwd_customer SELECT id FROM ods_customer;",
        upstream_tables=["ods_customer"],
        downstream_tables=["ads_rfm"]
    )
    prompt = build_prompt(ctx)
    assert "dwd_customer" in prompt
    assert "DWD" in prompt
    assert "CREATE TABLE dwd_customer" in prompt
    assert "INSERT INTO" in prompt
    assert "ods_customer" in prompt
    assert "ads_rfm" in prompt
    assert "只允许返回下方 JSON schema 中列出的顶层字段" in prompt
    assert "不要新增任何字段" in prompt
    assert "is_violating_declared_layer" not in prompt
    assert "atomic_metrics" in prompt
    assert "derived_metrics" in prompt
    assert "calculated_metrics" in prompt
    assert "dimensions" in prompt
    assert "others" in prompt


def test_build_prompt_requests_entity_and_grain_metadata():
    ctx = TableContext(
        table_name="dws_product_sales_daily",
        layer="DWS",
        ddl="CREATE TABLE dws_product_sales_daily (product_id BIGINT, stat_date DATE);",
        etl_sql="INSERT INTO dws_product_sales_daily SELECT product_id, order_date FROM dwd_order_detail GROUP BY product_id, order_date;",
        upstream_tables=["dwd_order_detail"],
        downstream_tables=[],
    )

    prompt = build_prompt(ctx)

    assert "entities、grain" in prompt
    assert "grain.entities" in prompt
    assert "返回完整的粒度实体集合" in prompt
    assert '"entities": [' in prompt
    assert '"type": "primary|unique|foreign|natural"' in prompt
    assert '"grain": {' in prompt


def test_build_prompt_requests_dimension_classification_metadata():
    ctx = TableContext(
        table_name="DIM_BASE_CUST_INFO",
        layer="DIM",
        ddl="CREATE TABLE DIM_BASE_CUST_INFO (CUST_ID BIGINT);",
        etl_sql="",
        upstream_tables=["dwd_customer"],
        downstream_tables=["dwd_order_detail"],
    )

    prompt = build_prompt(ctx)

    assert "维表内容形态" in prompt
    assert "维表建设角色" in prompt
    assert "dimension_role" in prompt
    assert "dimension_content_type" in prompt
    assert '"dimension_role": "BASE|ADDT"' in prompt
    assert '"dimension_content_type": "INFO|TAG|TREE"' in prompt


def test_build_prompt_clarifies_metric_group_boundaries():
    ctx = TableContext(
        table_name="dwd_fact_table",
        layer="DWD",
        ddl="CREATE TABLE dwd_fact_table (metric_a DECIMAL(12,2));",
        etl_sql="",
        upstream_tables=["ods_source_table"],
        downstream_tables=["dws_summary_table"],
    )

    prompt = build_prompt(ctx)

    assert "事件标识或实体标识字段做 COUNT/COUNT DISTINCT" in prompt
    assert "对上游已存在的 atomic_metrics 做 SUM/AVG/MIN/MAX" in prompt
    assert "对上游 calculated_metrics 再聚合" in prompt
    assert "不要套用字段名示例" in prompt
    assert "非加性属性" in prompt
    assert "补值、回填、估算" in prompt
    assert "不会让字段变成 calculated_metrics" in prompt

    hardcoded_examples = [
        "订单ID",
        "客户ID",
        "交易ID",
        "订单明细小计金额",
        "行金额",
        "含税金额",
        "净额",
        "毛利",
    ]
    for example in hardcoded_examples:
        assert example not in prompt


def test_build_prompt_separates_business_process_and_semantic_subject():
    ctx = TableContext(
        table_name="dwd_entity_profile",
        layer="DWD",
        ddl=(
            "CREATE TABLE dwd_entity_profile "
            "(entity_id BIGINT, entity_name VARCHAR(64));"
        ),
        etl_sql=(
            "INSERT INTO dwd_entity_profile "
            "SELECT entity_id, entity_name FROM ods_entity_profile;"
        ),
        upstream_tables=["ods_entity_profile"],
        downstream_tables=["dws_entity_activity_daily"],
    )

    prompt = build_prompt(ctx)

    assert "business_process 只适用于事实表或汇总事实表" in prompt
    assert "dimension 表不得为了填充业务过程而生成" in prompt
    assert "semantic_subject" in prompt
    assert "管理/运营/主数据/资料维护" in prompt
    assert "实体主语 + 管理/运营" in prompt
    assert "大写下划线短语" in prompt
    assert "不能仅由实体主语" in prompt
    assert "语义主题" in prompt
    hardcoded_project_examples = [
        "客户、商品、门店",
        "CUSTOMER_OPERATION",
        "PRODUCT_MANAGEMENT",
        "STORE_OPERATION",
        "CUSTOMER、PRODUCT",
        "STORE、PROMOTION",
    ]
    for example in hardcoded_project_examples:
        assert example not in prompt


def test_build_prompt_uses_confirmed_catalog_options_without_hardcoded_domain():
    ctx = TableContext(
        table_name="dwd_event_detail",
        layer="DWD",
        ddl="CREATE TABLE dwd_event_detail (event_id BIGINT, amount DECIMAL(12,2));",
        etl_sql="INSERT INTO dwd_event_detail SELECT event_id, amount FROM ods_event;",
        upstream_tables=["ods_event"],
        downstream_tables=["dws_event_daily"],
        business_semantics_options={
            "business_processes": [{
                "code": "EVENT_COMPLETION",
                "name": "事件完成",
            }],
            "semantic_subjects": [{
                "code": "PARTY",
                "name": "参与方",
            }],
        },
    )

    prompt = build_prompt(ctx)

    assert "已确认业务语义目录" in prompt
    assert "EVENT_COMPLETION" in prompt
    assert "PARTY" in prompt
    assert '"tables"' not in prompt
    assert "优先复用目录中的 code" in prompt
    assert "若没有合适 code" in prompt
    assert "CUSTOMER_OPERATION" not in prompt
    assert "PRODUCT_MANAGEMENT" not in prompt
    assert "STORE_OPERATION" not in prompt


def test_build_prompt_includes_project_context_as_auxiliary_evidence():
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        ddl="CREATE TABLE dwd_order_detail (order_id BIGINT, sale_amt DECIMAL(12,2));",
        etl_sql="INSERT INTO dwd_order_detail SELECT order_id, sale_amt FROM ods_order;",
        upstream_tables=["ods_order"],
        downstream_tables=["dws_order_daily"],
        project_context=(
            "这是一个门店零售数据集市，订单交易是核心业务过程，"
            "销售额和订单数是基础指标。"
        ),
    )

    prompt = build_prompt(ctx)

    assert "项目背景说明" in prompt
    assert "门店零售数据集市" in prompt
    assert "销售额和订单数是基础指标" in prompt
    assert "辅助语义" in prompt
    assert "不能覆盖 DDL、ETL、血缘" in prompt


def test_build_prompt_allows_domain_area_candidates_without_dictionary():
    ctx = TableContext(
        table_name="dwd_event_detail",
        layer="DWD",
        ddl="CREATE TABLE dwd_event_detail (event_id BIGINT);",
        etl_sql="INSERT INTO dwd_event_detail SELECT event_id FROM ods_event;",
        upstream_tables=["ods_event"],
        downstream_tables=[],
    )

    prompt = build_prompt(ctx)

    assert "未提供数据域与业务板块字典" in prompt
    assert "可以返回新的大写下划线候选 code" in prompt
    assert "不确定时返回空字符串" in prompt


def test_build_prompt_treats_imputed_non_additive_inputs_as_dimensions():
    ctx = TableContext(
        table_name="dwd_fact_table",
        layer="DWD",
        ddl="CREATE TABLE dwd_fact_table (amount DECIMAL(12,2));",
        etl_sql="",
        upstream_tables=["ods_source_table"],
        downstream_tables=["dws_summary_table"],
    )

    prompt = build_prompt(ctx)

    assert "价格、成本、费率、汇率、系数、阈值" in prompt
    assert "缺失值兜底" in prompt
    assert "应继续归 dimensions" in prompt
    assert "dwd_order_detail.cost_price" not in prompt


def test_build_prompt_without_etl():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        ddl="CREATE TABLE dwd_customer;",
        etl_sql="",
        upstream_tables=[],
        downstream_tables=[]
    )
    prompt = build_prompt(ctx)
    assert "dwd_customer" in prompt
    assert "## ETL 加工逻辑" not in prompt


# ============================================================
# 2. 响应解析测试
# ============================================================

def test_parse_dimension_response():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "confidence": 0.9,
                    "reasoning_steps": ["test"],
                })
            }
        }]
    }
    result = parse_response("dwd_customer", resp, declared_layer="DWD")
    assert result.table_name == "dwd_customer"
    assert result.declared_layer == "DWD"
    assert result.inferred_layer == "DIM"
    assert result.table_type == "dimension"
    assert result.confidence == 0.9
    assert result.reasoning_steps == ["test"]
    assert result.is_violating_declared_layer is True


def test_parse_response_preserves_dimension_classification_metadata():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "dimension_role": "base",
                    "dimension_content_type": "tag",
                    "confidence": 0.9,
                    "reasoning_steps": ["客户标签维表"],
                })
            }
        }]
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


def test_parse_business_domain_response():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "inferred_data_domain": "04",
                    "inferred_business_area": "PAYM",
                    "confidence": 0.9,
                    "reasoning_steps": ["交易事实表"],
                })
            }
        }]
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


def test_parse_response_preserves_entity_and_grain_metadata():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
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
                })
            }
        }]
    }

    result = parse_response("dws_product_sales_daily",
                            resp,
                            declared_layer="DWS")
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


def test_parse_response_preserves_entities_metadata():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWS",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "reasoning_steps": ["商品门店日汇总"],
                    "entities": [{
                        "code": "PROD",
                        "type": "foreign",
                        "key_columns": ["product_id"],
                    }, {
                        "code": "STOR",
                        "type": "foreign",
                        "key_columns": ["store_id"],
                    }],
                    "grain": {
                        "entities": ["PROD", "STOR"],
                        "time_column": "stat_date",
                        "time_period": "D",
                    },
                })
            }
        }]
    }

    result = parse_response("dws_product_store_sales_daily",
                            resp,
                            declared_layer="DWS")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.entities == [{
        "code": "PROD",
        "type": "foreign",
        "key_columns": ["product_id"],
    }, {
        "code": "STOR",
        "type": "foreign",
        "key_columns": ["store_id"],
    }]
    assert result.grain == {
        "entities": ["PROD", "STOR"],
        "time_column": "stat_date",
        "time_period": "D",
    }
    assert data["entities"] == result.entities
    assert cached["entities"] == result.entities


def test_parse_response_normalizes_placeholder_empty_grain():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
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
                })
            }
        }]
    }

    result = parse_response("dwd_customers", resp, declared_layer="DWD")

    assert result.grain == {}


def test_dict_to_result_normalizes_placeholder_empty_grain():
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


def test_parse_response_preserves_related_entities_metadata():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "confidence": 0.9,
                    "reasoning_steps": ["商品维度包含品类层级"],
                    "entity": {
                        "code": "PROD",
                        "key_columns": ["product_id"],
                    },
                    "related_entities": [{
                        "code": "CAT",
                        "name": "品类",
                        "key_columns": ["category_id"],
                        "relationship": {
                            "type": "many_to_one",
                            "from_entity": "PROD",
                        },
                    }],
                })
            }
        }]
    }

    result = parse_response("dwd_product", resp, declared_layer="DWD")
    data = result_to_dict(result)
    cached = result_to_cache_dict(result)

    assert result.entities == [{
        "code": "PROD",
        "type": "primary",
        "key_columns": ["product_id"],
    }, {
        "code": "CAT",
        "type": "foreign",
        "name": "品类",
        "key_columns": ["category_id"],
        "relationship": {
            "type": "many_to_one",
            "from_entity": "PROD",
        },
    }]
    assert result.related_entities == [{
        "code": "CAT",
        "name": "品类",
        "key_columns": ["category_id"],
        "relationship": {
            "type": "many_to_one",
            "from_entity": "PROD",
        },
    }]
    assert data["related_entities"] == result.related_entities
    assert cached["related_entities"] == result.related_entities


def test_build_prompt_limits_business_metadata_by_layer():
    ctx = TableContext(
        table_name="dim_location",
        layer="DIM",
        ddl="CREATE TABLE dim_location (location_key STRING);",
        etl_sql="",
        upstream_tables=["dwd_branch_locations"],
        downstream_tables=[],
        business_domain_options={
            "domains": [{"id": "06", "code": "ORGN", "name": "机构域"}],
            "business_areas": [{"code": "CHNL", "name": "渠道业务"}],
        },
    )

    prompt = build_prompt(ctx)

    assert "数据域只适用于 DWD 层" in prompt
    assert "业务板块只适用于 DWD 和 DWS 层" in prompt
    assert "当前表若不是 DWD，inferred_data_domain 必须返回空字符串" in prompt
    assert "当前表若不是 DWD/DWS，inferred_business_area 必须返回空字符串" in prompt
    assert "如果无法明确判断，可返回“其它”数据域编号" in prompt
    assert "如果无法明确判断，可返回“其它”业务板块简写" in prompt


def test_parse_fact_response():
    resp = {
        "choices": [{
            "message": {
                "content": '{"table_type": "fact", "confidence": 0.8, "reason": "test fact"}'
            }
        }]
    }
    result = parse_response("dwd_order", resp)
    assert result.table_type == "fact"
    assert result.confidence == 0.8


def test_parse_other_response():
    resp = {
        "choices": [{
            "message": {
                "content": '{"table_type": "other", "confidence": 0.5, "reason": "test other"}'
            }
        }]
    }
    result = parse_response("dwd_mapping", resp)
    assert result.table_type == "other"


def test_parse_markdown_wrapped_response():
    resp = {
        "choices": [{
            "message": {
                "content": '```json\n{"table_type": "dimension", "confidence": 0.9, "reason": "test"}\n```'
            }
        }]
    }
    result = parse_response("t1", resp)
    assert result.table_type == "dimension"


def test_parse_malformed_response():
    resp = {
        "choices": [{
            "message": {
                "content": "This is a dimension table"
            }
        }]
    }
    result = parse_response("t1", resp)
    assert result.table_type == "other"
    assert result.confidence == 0.0
    assert "JSON 解析失败" in result.reasoning_steps[0]


def test_parse_grouped_column_response():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "confidence": 0.92,
                    "reasoning_steps": ["订单明细事实表"],
                    "columns": {
                        "atomic_metrics": [{
                            "name": "pay_amt",
                            "data_type": "DECIMAL(12,2)",
                            "business_process": "订单支付",
                            "action": "pay",
                            "measure": "amt",
                            "description": "支付金额",
                            "reason": "基础支付金额",
                            "confidence": 0.93,
                        }],
                        "derived_metrics": [{
                            "name": "pay_amt_1d",
                            "data_type": "DECIMAL(12,2)",
                            "base_metric": "pay_amt",
                            "modifiers": [],
                            "time_period": "1d",
                            "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
                            "description": "近 1 日支付金额",
                            "reason": "时间周期限定",
                            "confidence": 0.86,
                        }],
                        "calculated_metrics": [{
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
                        }],
                        "dimensions": [{
                            "name": "order_id",
                            "dimension_type": "primary_key",
                            "data_type": "BIGINT",
                            "confidence": 0.9,
                        }],
                        "others": [{
                            "name": "etl_time",
                            "role": "audit",
                            "data_type": "DATETIME",
                            "confidence": 0.9,
                        }],
                    },
                })
            }
        }]
    }

    result = parse_response("dwd_order_detail", resp, declared_layer="DWD")

    assert result.is_fact_table is True
    assert result.is_violating_declared_layer is False
    assert result.atomic_metrics[0]["name"] == "pay_amt"
    assert result.atomic_metrics[0]["measure"] == "amt"
    assert result.derived_metrics[0]["name"] == "pay_amt_1d"
    assert result.derived_metrics[0]["base_metric"] == "pay_amt"
    assert result.derived_metrics[0]["time_period"] == "1d"
    assert result.calculated_metrics[0]["name"] == "gross_profit"
    assert result.calculated_metrics[0]["derived_from"] == [
        "subtotal",
        "cost_price",
        "quantity",
    ]
    assert result.dimensions[0]["dimension_type"] == "primary_key"
    assert result.others[0]["role"] == "audit"


def test_result_to_dict_includes_system_layer_violation():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "confidence": 0.9,
                    "reasoning_steps": ["dimension table"],
                })
            }
        }]
    }

    result = parse_response("dwd_customer", resp, declared_layer="DWD")
    data = result_to_dict(result)

    assert data["is_violating_declared_layer"] is True


def test_result_to_cache_dict_omits_system_layer_violation():
    resp = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                    "confidence": 0.9,
                    "reasoning_steps": ["dimension table"],
                })
            }
        }]
    }

    result = parse_response("dwd_customer", resp, declared_layer="DWD")
    data = result_to_cache_dict(result)

    assert "is_violating_declared_layer" not in data
    assert "status" not in data


def test_validate_columns_flags_unknown_duplicate_and_missing_fields():
    result = parse_response("dwd_order_detail", {
        "choices": [{
            "message": {
                "content": json.dumps({
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
                })
            }
        }]
    }, declared_layer="DWD")

    validation = validate_columns(result, {"order_id", "pay_amt", "etl_time"})

    assert validation["unknown_columns"] == ["ghost_amt"]
    assert validation["duplicate_columns"] == ["pay_amt"]
    assert validation["missing_columns"] == ["etl_time"]


def test_validate_columns_requires_all_dws_fact_fields():
    result = parse_response("dws_store_sales_daily", {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWS",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "columns": {
                        "atomic_metrics": [],
                        "derived_metrics": [{"name": "sale_amount"}],
                        "calculated_metrics": [],
                        "dimensions": [{"name": "store_id"}],
                        "others": [],
                    },
                })
            }
        }]
    }, declared_layer="DWS")

    validation = validate_columns(
        result,
        {"store_id", "stat_date", "sale_amount", "etl_time"},
    )

    assert validation["missing_columns"] == ["etl_time", "stat_date"]


def test_validate_metric_relationships_requires_derived_base_metric_in_upstream_atomic():
    result = parse_response("dws_store_sales_daily", {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWS",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "columns": {
                        "atomic_metrics": [],
                        "derived_metrics": [{
                            "name": "sale_amount",
                            "base_metric": "subtotal",
                            "base_metric_table": "dwd_order_detail",
                            "expression": "SUM(subtotal)",
                        }, {
                            "name": "sale_quantity",
                            "base_metric": "quantity",
                            "base_metric_table": "dwd_order_detail",
                            "expression": "SUM(quantity)",
                        }, {
                            "name": "mystery_amount",
                            "base_metric": "ghost_amount",
                            "base_metric_table": "dwd_order_detail",
                            "expression": "SUM(ghost_amount)",
                        }, {
                            "name": "unknown_amount",
                            "base_metric": "",
                            "base_metric_table": "",
                            "expression": "SUM(amount)",
                        }, {
                            "name": "bad_table_amount",
                            "base_metric": "subtotal",
                            "base_metric_table": "dwd_refund_detail",
                            "expression": "SUM(subtotal)",
                        }],
                        "calculated_metrics": [],
                        "dimensions": [{"name": "store_id"}],
                        "others": [],
                    },
                })
            }
        }]
    }, declared_layer="DWS")
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


def test_validate_metric_relationships_flags_ambiguous_unqualified_base_metric():
    result = parse_response("dws_sales_daily", {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWS",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "columns": {
                        "atomic_metrics": [],
                        "derived_metrics": [{
                            "name": "sale_amount",
                            "base_metric": "subtotal",
                            "expression": "SUM(subtotal)",
                        }],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                })
            }
        }]
    }, declared_layer="DWS")
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

    assert validation.get("ambiguous_base_metrics") == [
        "sale_amount:subtotal"
    ]


def test_result_status_from_validation():
    result = parse_response("dwd_order_detail", {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "columns": {
                        "atomic_metrics": [{"name": "pay_amt"}],
                        "derived_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                })
            }
        }]
    }, declared_layer="DWD")

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


def test_inspect_preserves_llm_metric_groups(tmp_path, monkeypatch):
    inspector = TableInspector(api_key="test",
                               cache_file=tmp_path / "cache.json")
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
        "columns": {
            "atomic_metrics": [
                {"name": "quantity", "data_type": "INT"},
                {"name": "unit_price", "data_type": "DECIMAL(12,2)"},
                {"name": "discount", "data_type": "DECIMAL(12,2)"},
                {"name": "subtotal", "data_type": "DECIMAL(12,2)"},
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [{
                "name": "order_id",
                "dimension_type": "primary_key",
            }],
            "others": [{"name": "etl_time", "role": "audit"}],
        },
    }
    monkeypatch.setattr(inspector, "_call_api", lambda _prompt: json.dumps({
        "choices": [{"message": {"content": json.dumps(response)}}]
    }))

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

def test_cache_hit_skips_api(tmp_path):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)
    
    ctx = TableContext(
        table_name="t1", layer="DWD",
        ddl="ddl1", etl_sql="etl1", upstream_tables=[], downstream_tables=[]
    )
    
    # 模拟缓存文件已存在
    cached = parse_response("t1", {
        "choices": [{
            "message": {
                "content": json.dumps({
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
                })
            }
        }]
    }, declared_layer="DWD")
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
    
    with patch.object(inspector, '_call_api') as mock_api:
        res = inspector.inspect(ctx)
        mock_api.assert_not_called()
        assert res.table_type == "dimension"
        assert res.reasoning_steps == ["cached"]


def test_cache_miss_calls_api(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file)
    
    ctx = TableContext(
        table_name="t1", layer="DWD",
        ddl="ddl_new", etl_sql="etl1", upstream_tables=[], downstream_tables=[]
    )
    
    # mock _call_api
    monkeypatch.setattr(inspector, '_call_api', lambda p: json.dumps({
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "confidence": 0.8,
                    "reasoning_steps": ["api"],
                    "columns": {
                        "atomic_metrics": [{
                            "name": "pay_amt",
                            "data_type": "DECIMAL(12,2)",
                            "business_process": "订单支付",
                            "action": "pay",
                            "measure": "amt",
                            "confidence": 0.9,
                        }],
                        "derived_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                })
            }
        }]
    }))
    
    res = inspector.inspect(ctx)
    assert res.table_type == "fact"
    assert res.atomic_metrics[0]["name"] == "pay_amt"
    
    # 验证缓存被更新
    saved = json.loads(cache_file.read_text())
    assert "t1" in saved
    assert saved["t1"]["result"]["table_type"] == "fact"
    assert saved["t1"]["result"]["columns"]["atomic_metrics"][0]["name"] == "pay_amt"
    assert "is_violating_declared_layer" not in saved["t1"]["result"]
    assert "status" not in saved["t1"]["result"]
    assert "is_violating_current_name" not in saved["t1"]["result"]


def test_progress_callback_reports_batch_events(tmp_path, monkeypatch):
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
    monkeypatch.setattr(inspector, "_call_api", lambda _prompt: json.dumps({
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "fact",
                    "confidence": 0.9,
                    "columns": {
                        "atomic_metrics": [{"name": "pay_amt"}],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                })
            }
        }]
    }))

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


def test_progress_callback_reports_cache_hit(tmp_path):
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
    cached = parse_response("t1", {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "inferred_layer": "DWD",
                    "table_type": "dimension",
                    "confidence": 0.9,
                })
            }
        }]
    }, declared_layer="DWD")
    cache_file.write_text(json.dumps({
        "t1": {
            "hash": inspector._compute_hash(ctx),
            "result": result_to_cache_dict(cached),
        }
    }))
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


def test_inspect_retries_validation_errors(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    inspector = TableInspector(api_key="test", cache_file=cache_file, max_retries=1)
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
        return json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]})

    monkeypatch.setattr(inspector, "_call_api", fake_api)

    result = inspector.inspect(ctx)

    assert len(calls) == 2
    assert "上次返回结果校验未通过" in calls[1]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.validation["unknown_columns"] == []


def test_cache_hash_includes_declared_layer(tmp_path):
    inspector = TableInspector(api_key="test", cache_file=tmp_path / "cache.json")

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


def test_cache_hash_includes_project_context(tmp_path):
    inspector = TableInspector(api_key="test", cache_file=tmp_path / "cache.json")

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
        finance_ctx)


def test_default_parallelism_is_two():
    inspector = TableInspector(api_key="test", cache_file=None)

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
        ) for i in range(4)
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
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "inferred_layer": "DWD",
                            "table_type": "dimension",
                            "confidence": 0.9,
                            "reasoning_steps": ["api"],
                            "columns": {
                                "atomic_metrics": [],
                                "derived_metrics": [],
                                "dimensions": [],
                                "others": [],
                            },
                        })
                    }
                }]
            })
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
        downstream_tables=["ads_rfm"]
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
        
    from tests.assess.conftest import DDL_DWD_ORDER_DETAIL, ETL_DWD_ORDER_DETAIL
    
    inspector = TableInspector(api_key=api_key, cache_file=None)
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        ddl=DDL_DWD_ORDER_DETAIL,
        etl_sql=ETL_DWD_ORDER_DETAIL,
        upstream_tables=["ods_order", "ods_order_item", "ods_product"],
        downstream_tables=["dws_store_sales_daily"]
    )
    
    res = inspector.inspect(ctx)
    assert res.table_name == "dwd_order_detail"
    assert res.table_type == "fact"
    assert res.confidence > 0.5
