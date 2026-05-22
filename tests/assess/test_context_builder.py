import pytest
from pathlib import Path
from assess.context_builder import build_contexts, extract_dependencies


def test_extract_dependencies(sample_lineage_data):
    upstream, downstream = extract_dependencies(sample_lineage_data)
    
    assert "dwd_customer" in downstream["ods_customer"]
    assert "dwd_customer" in upstream
    assert upstream["dwd_customer"] == {"ods_customer"}
    
    assert "dws_store_sales_daily" in downstream["dwd_order_detail"]
    assert upstream["dws_store_sales_daily"] == {"dwd_order_detail"}
    
    assert "ads_sales_dashboard" in downstream["dwd_customer"]
    assert "ods_customer" not in downstream["dwd_customer"]


def test_build_contexts_filters_middle_layer(sample_lineage_data, tmp_path):
    # Setup mock files
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    
    (ddl_dir / "dwd_customer.sql").write_text("DDL dwd_customer")
    (tasks_dir / "dwd_customer.sql").write_text("ETL dwd_customer")
    (ddl_dir / "dwd_order_detail.sql").write_text("DDL dwd_order_detail")
    
    contexts = build_contexts("test_proj", sample_lineage_data, ddl_dir, tasks_dir)
    
    # 验证只有 DWD/DWS 层的表被返回
    assert len(contexts) == 3
    table_names = [ctx.table_name for ctx in contexts]
    assert "dwd_customer" in table_names
    assert "dwd_order_detail" in table_names
    assert "dws_store_sales_daily" in table_names
    assert "ods_customer" not in table_names
    assert "ads_sales_dashboard" not in table_names


def test_build_context_with_ddl_and_task(sample_lineage_data, tmp_path):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    
    (ddl_dir / "dwd_customer.sql").write_text("CREATE dwd_customer;")
    (tasks_dir / "dwd_customer.sql").write_text("INSERT dwd_customer;")
    
    contexts = build_contexts("test_proj", sample_lineage_data, ddl_dir, tasks_dir)
    ctx = next(c for c in contexts if c.table_name == "dwd_customer")
    
    assert ctx.ddl == "CREATE dwd_customer;"
    assert ctx.etl_sql == "INSERT dwd_customer;"
    assert ctx.upstream_tables == ["ods_customer"]
    assert ctx.downstream_tables == ["ads_sales_dashboard"]


def test_build_context_without_task(sample_lineage_data, tmp_path):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    
    (ddl_dir / "dwd_order_detail.sql").write_text("CREATE dwd_order_detail;")
    # No task file
    
    contexts = build_contexts("test_proj", sample_lineage_data, ddl_dir, tasks_dir)
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")
    
    assert ctx.ddl == "CREATE dwd_order_detail;"
    assert ctx.etl_sql == ""
    assert ctx.downstream_tables == ["dws_store_sales_daily"]
