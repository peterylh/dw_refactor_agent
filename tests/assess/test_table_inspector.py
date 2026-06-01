import json
import threading
import time
import pytest
from unittest.mock import patch

from assess.table_inspector import (
    TableInspector,
    TableContext,
    build_prompt,
    parse_response,
    result_to_dict,
    validate_columns,
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
    assert "is_violating_declared_layer" in prompt
    assert "不要返回 is_violating_declared_layer" in prompt
    assert "atomic_metrics" in prompt
    assert "derived_metrics" in prompt
    assert "dimensions" in prompt
    assert "others" in prompt


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
    assert result.derived_metrics[0]["name"] == "gross_profit"
    assert result.derived_metrics[0]["derived_from"] == [
        "subtotal",
        "cost_price",
        "quantity",
    ]
    assert result.dimensions[0]["dimension_type"] == "primary_key"
    assert result.others[0]["role"] == "audit"


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
    assert "is_violating_declared_layer" in saved["t1"]["result"]
    assert "is_violating_current_name" not in saved["t1"]["result"]


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
