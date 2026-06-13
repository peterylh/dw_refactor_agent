import pytest
from pathlib import Path
import yaml

import config
from assess.context_builder import (
    build_contexts,
    extract_column_lineage,
    extract_dependencies,
)


def test_extract_dependencies(sample_lineage_data):
    upstream, downstream = extract_dependencies(sample_lineage_data)
    
    assert "dwd_customer" in downstream["ods_customer"]
    assert "dwd_customer" in upstream
    assert upstream["dwd_customer"] == {"ods_customer"}
    
    assert "dws_store_sales_daily" in downstream["dwd_order_detail"]
    assert upstream["dws_store_sales_daily"] == {"dwd_order_detail"}
    
    assert "ads_sales_dashboard" in downstream["dwd_customer"]
    assert "ods_customer" not in downstream["dwd_customer"]


def test_extract_dependencies_collapses_transient_tables():
    lineage_data = {
        "edges": [
            {"source": "dwd_orders.order_id", "target": "tmp_orders_stage.order_id"},
            {"source": "tmp_orders_stage.order_id", "target": "dws_orders.order_id"},
        ],
        "indirect_edges": [],
        "transient_tables": [{"name": "tmp_orders_stage", "is_transient": True}],
    }

    upstream, downstream = extract_dependencies(lineage_data)

    assert upstream == {"dws_orders": {"dwd_orders"}}
    assert downstream == {"dwd_orders": {"dws_orders"}}


def test_extract_column_lineage_collapses_transient_fields():
    lineage_data = {
        "edges": [
            {
                "source": "dwd_order_detail.sale_amount",
                "target": "tmp_promotion_stage.sale_amount",
                "expression": "SUM(dwd_order_detail.sale_amount) AS sale_amount",
                "source_file": "dws_promotion_effect_daily.sql",
            },
            {
                "source": "tmp_promotion_stage.sale_amount",
                "target": "dws_promotion_effect_daily.sale_amount",
                "expression": "tmp_promotion_stage.sale_amount AS sale_amount",
                "source_file": "dws_promotion_effect_daily.sql",
            },
        ],
        "transient_tables": [{
            "name": "tmp_promotion_stage",
            "is_transient": True,
        }],
    }

    lineage = extract_column_lineage(
        lineage_data,
        "dws_promotion_effect_daily",
    )

    assert lineage[0]["source"] == "dwd_order_detail.sale_amount"
    assert lineage[0]["target"] == "dws_promotion_effect_daily.sale_amount"
    assert lineage[0]["transient_path"] == ["tmp_promotion_stage.sale_amount"]
    assert len(lineage[0]["expression_chain"]) == 2


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


def test_build_contexts_includes_business_semantics_catalog_options(
        sample_lineage_data, tmp_path, monkeypatch):
    project = "context_catalog"
    project_dir = tmp_path / project
    ddl_dir = project_dir / "ddl"
    tasks_dir = project_dir / "tasks"
    ddl_dir.mkdir(parents=True)
    tasks_dir.mkdir()
    (ddl_dir / "dwd_order_detail.sql").write_text(
        "CREATE TABLE dwd_order_detail (order_id BIGINT);",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    (project_dir / "business_semantics.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [],
                "business_areas": [],
                "business_processes": [{
                    "code": "ORDER_TRANSACTION",
                    "name": "订单交易",
                    "tables": ["dwd_order_detail"],
                }],
                "semantic_subjects": [{
                    "code": "CUSTOMER",
                    "name": "客户",
                    "tables": ["dwd_customer"],
                }],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {
        "dir": project,
        "naming_config": "naming_config.yaml",
    })
    config._business_semantics_cache.clear()

    contexts = build_contexts(project, sample_lineage_data)
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")

    assert ctx.business_semantics_options == {
        "business_processes": [{
            "code": "ORDER_TRANSACTION",
            "name": "订单交易",
        }],
        "semantic_subjects": [{
            "code": "CUSTOMER",
            "name": "客户",
        }],
    }
