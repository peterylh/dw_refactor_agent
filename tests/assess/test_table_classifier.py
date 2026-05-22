import json
import pytest
from unittest.mock import patch, mock_open, MagicMock

from assess.table_classifier import (
    TableClassifier,
    TableContext,
    ClassifyResult,
    build_prompt,
    parse_response
)


# ============================================================
# 1. Prompt 组装测试
# ============================================================

def test_build_prompt_includes_all_info():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        columns=[{"name": "id", "type": "BIGINT"}],
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


def test_build_prompt_without_etl():
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        columns=[],
        ddl="CREATE TABLE dwd_customer;",
        etl_sql="",
        upstream_tables=[],
        downstream_tables=[]
    )
    prompt = build_prompt(ctx)
    assert "dwd_customer" in prompt
    assert "ETL 加工逻辑" not in prompt


# ============================================================
# 2. 响应解析测试
# ============================================================

def test_parse_dimension_response():
    resp = {
        "choices": [{
            "message": {
                "content": '{"table_type": "dimension", "confidence": 0.9, "reason": "test"}'
            }
        }]
    }
    result = parse_response("dwd_customer", resp)
    assert result.table_name == "dwd_customer"
    assert result.table_type == "dimension"
    assert result.confidence == 0.9
    assert result.reason == "test"


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
    assert "JSON 解析失败" in result.reason


# ============================================================
# 3. 缓存测试
# ============================================================

def test_cache_hit_skips_api(tmp_path):
    cache_file = tmp_path / "cache.json"
    classifier = TableClassifier(api_key="test", cache_file=cache_file)
    
    ctx = TableContext(
        table_name="t1", layer="DWD", columns=[],
        ddl="ddl1", etl_sql="etl1", upstream_tables=[], downstream_tables=[]
    )
    
    # 模拟缓存文件已存在
    cache_data = {
        "t1": {
            "hash": classifier._compute_hash(ctx),
            "result": {"table_name": "t1", "table_type": "dimension", "confidence": 0.9, "reason": "cached"}
        }
    }
    cache_file.write_text(json.dumps(cache_data))
    
    # 重新加载缓存
    classifier._load_cache()
    
    with patch.object(classifier, '_call_api') as mock_api:
        res = classifier.classify(ctx)
        mock_api.assert_not_called()
        assert res.table_type == "dimension"
        assert res.reason == "cached"


def test_cache_miss_calls_api(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    classifier = TableClassifier(api_key="test", cache_file=cache_file)
    
    ctx = TableContext(
        table_name="t1", layer="DWD", columns=[],
        ddl="ddl_new", etl_sql="etl1", upstream_tables=[], downstream_tables=[]
    )
    
    # mock _call_api
    mock_resp = {"table_type": "fact", "confidence": 0.8, "reason": "api"}
    monkeypatch.setattr(classifier, '_call_api', lambda p: '{"table_type": "fact", "confidence": 0.8, "reason": "api"}')
    
    res = classifier.classify(ctx)
    assert res.table_type == "fact"
    
    # 验证缓存被更新
    saved = json.loads(cache_file.read_text())
    assert "t1" in saved
    assert saved["t1"]["result"]["table_type"] == "fact"


# ============================================================
# 4. 集成测试 (标记 api)
# ============================================================

@pytest.mark.api
def test_classify_dimension_table(monkeypatch):
    import os
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")
        
    from tests.assess.conftest import DDL_DWD_CUSTOMER, ETL_DWD_CUSTOMER
    
    classifier = TableClassifier(api_key=api_key, cache_file=None)
    ctx = TableContext(
        table_name="dwd_customer",
        layer="DWD",
        columns=[],
        ddl=DDL_DWD_CUSTOMER,
        etl_sql=ETL_DWD_CUSTOMER,
        upstream_tables=["ods_customer"],
        downstream_tables=["ads_rfm"]
    )
    
    res = classifier.classify(ctx)
    assert res.table_name == "dwd_customer"
    assert res.table_type == "dimension"
    assert res.confidence > 0.5


@pytest.mark.api
def test_classify_fact_table(monkeypatch):
    import os
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")
        
    from tests.assess.conftest import DDL_DWD_ORDER_DETAIL, ETL_DWD_ORDER_DETAIL
    
    classifier = TableClassifier(api_key=api_key, cache_file=None)
    ctx = TableContext(
        table_name="dwd_order_detail",
        layer="DWD",
        columns=[],
        ddl=DDL_DWD_ORDER_DETAIL,
        etl_sql=ETL_DWD_ORDER_DETAIL,
        upstream_tables=["ods_order", "ods_order_item", "ods_product"],
        downstream_tables=["dws_store_sales_daily"]
    )
    
    res = classifier.classify(ctx)
    assert res.table_name == "dwd_order_detail"
    assert res.table_type == "fact"
    assert res.confidence > 0.5
