import pytest
import yaml

import dw_refactor_agent.assessment.llm.context_builder as context_builder_module
import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.context_builder import (
    build_contexts,
    extract_column_lineage,
    extract_dependencies,
)

MODEL_METADATA = {
    "dwd_customer": {"name": "dwd_customer", "layer": "DWD"},
    "dwd_order_detail": {"name": "dwd_order_detail", "layer": "DWD"},
    "dws_store_sales_daily": {
        "name": "dws_store_sales_daily",
        "layer": "DWS",
    },
    "ads_sales_dashboard": {"name": "ads_sales_dashboard", "layer": "ADS"},
}


@pytest.fixture(autouse=True)
def model_metadata(monkeypatch):
    monkeypatch.setattr(
        context_builder_module,
        "load_model_metadata",
        lambda project: MODEL_METADATA,
    )


def _build_contexts_for_graph(
    tmp_path,
    monkeypatch,
    *,
    tables,
    upstream,
    model_metadata,
    metric_groups=None,
    ddl_files=None,
    task_files=None,
    downstream=None,
):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    for filename, content in (ddl_files or {}).items():
        (ddl_dir / filename).write_text(content, encoding="utf-8")
    for filename, content in (task_files or {}).items():
        (tasks_dir / filename).write_text(content, encoding="utf-8")

    class FakeLineageView:
        @classmethod
        def from_data(cls, project, lineage_data):
            return cls()

        def asset_table_graph(self):
            return upstream, downstream or {}

        def column_lineage_for_table(self, table_name):
            return []

    monkeypatch.setattr(context_builder_module, "LineageView", FakeLineageView)
    return build_contexts(
        "test_proj",
        {"tables": [{"name": name} for name in tables]},
        ddl_dir,
        tasks_dir,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
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
            {
                "source": "dwd_orders.order_id",
                "target": "tmp_orders_stage.order_id",
            },
            {
                "source": "tmp_orders_stage.order_id",
                "target": "dws_orders.order_id",
            },
        ],
        "indirect_edges": [],
        "tables": [{"name": "tmp_orders_stage", "is_transient": True}],
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
        "tables": [
            {
                "name": "tmp_promotion_stage",
                "is_transient": True,
            }
        ],
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

    contexts = build_contexts(
        "test_proj", sample_lineage_data, ddl_dir, tasks_dir
    )

    # 验证只有 DWD/DWS 层的表被返回
    assert len(contexts) == 3
    table_names = [ctx.table_name for ctx in contexts]
    assert "dwd_customer" in table_names
    assert "dwd_order_detail" in table_names
    assert "dws_store_sales_daily" in table_names
    assert "ods_customer" not in table_names
    assert "ads_sales_dashboard" not in table_names


def test_build_contexts_reuses_one_lineage_view(
    sample_lineage_data, tmp_path, monkeypatch
):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    calls = {"builds": 0, "column_tables": []}

    class FakeLineageView:
        @classmethod
        def from_data(cls, project, lineage_data):
            calls["builds"] += 1
            assert project == "test_proj"
            assert lineage_data is sample_lineage_data
            return cls()

        def asset_table_graph(self):
            return (
                {
                    "dwd_customer": {"ods_customer"},
                    "dws_store_sales_daily": {"dwd_order_detail"},
                    "ads_sales_dashboard": {"dwd_customer"},
                },
                {
                    "ods_customer": {"dwd_customer"},
                    "dwd_order_detail": {"dws_store_sales_daily"},
                    "dwd_customer": {"ads_sales_dashboard"},
                },
            )

        def column_lineage_for_table(self, table_name):
            calls["column_tables"].append(table_name)
            return [{"target": f"{table_name}.id"}]

    monkeypatch.setattr(context_builder_module, "LineageView", FakeLineageView)

    contexts = build_contexts(
        "test_proj", sample_lineage_data, ddl_dir, tasks_dir
    )

    assert calls["builds"] == 1
    assert calls["column_tables"] == [ctx.table_name for ctx in contexts]


def test_build_contexts_matches_dependency_layers_case_insensitively(
    tmp_path,
    monkeypatch,
):
    metric_groups = {
        "atomic_metrics": ["order_count"],
        "derived_metrics": [],
        "calculated_metrics": [],
    }

    context = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=["Internal.Demo.DWS_ORDER_DAILY"],
        upstream={
            "Internal.Demo.DWS_ORDER_DAILY": {"INTERNAL.DEMO.DWD_ORDER_DETAIL"}
        },
        model_metadata={
            "dwd_order_detail": {"layer": "DWD"},
            "dws_order_daily": {"layer": "DWS"},
        },
        metric_groups={"dwd_order_detail": metric_groups},
        ddl_files={
            "dws_order_daily.sql": (
                "CREATE TABLE dws_order_daily (order_count BIGINT);"
            )
        },
    )[0]

    assert context.table_name == "dws_order_daily"
    assert context.upstream_table_layers == {
        "INTERNAL.DEMO.DWD_ORDER_DETAIL": "DWD"
    }
    assert context.upstream_metric_groups == {
        "INTERNAL.DEMO.DWD_ORDER_DETAIL": metric_groups
    }
    assert context.ddl.endswith("order_count BIGINT);")


def test_build_contexts_keeps_qualified_same_name_tables_isolated(
    tmp_path,
    monkeypatch,
):
    catalog_a_metrics = {
        "atomic_metrics": ["gross_amount"],
        "derived_metrics": [],
        "calculated_metrics": [],
    }
    catalog_b_metrics = {
        "atomic_metrics": ["balance_amount"],
        "derived_metrics": [],
        "calculated_metrics": [],
    }

    context = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=["catalog_a.db_a.order_summary"],
        upstream={
            "catalog_a.db_a.order_summary": {"catalog_a.db_a.orders"},
            "catalog_b.db_b.other_summary": {"catalog_b.db_b.orders"},
        },
        model_metadata={
            "catalog_a.db_a.order_summary": {
                "name": "order_summary",
                "layer": "DWS",
            },
            "catalog_a.db_a.orders": {"layer": "DWD"},
            "catalog_b.db_b.orders": {"layer": "DIM"},
        },
        metric_groups={
            "catalog_a.db_a.orders": catalog_a_metrics,
            "catalog_b.db_b.orders": catalog_b_metrics,
        },
    )[0]

    assert context.upstream_tables == ["catalog_a.db_a.orders"]
    assert context.upstream_table_layers == {"catalog_a.db_a.orders": "DWD"}
    assert context.upstream_metric_groups == {
        "catalog_a.db_a.orders": catalog_a_metrics
    }


def test_build_contexts_rejects_ambiguous_unqualified_exact_match(
    tmp_path,
    monkeypatch,
    caplog,
):
    contexts = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=["orders"],
        upstream={
            "summary_a": {"catalog_a.db_a.orders"},
            "summary_b": {"catalog_b.db_b.orders"},
        },
        model_metadata={"orders": {"name": "orders", "layer": "DWD"}},
    )

    assert contexts == []
    assert "Ambiguous short table name orders" in caplog.text


def test_canonical_lookup_does_not_fallback_wrong_qualified_identity():
    lookup = context_builder_module._canonical_table_lookup(
        {"catalog_a.db_a.orders": {"layer": "DWD"}}
    )
    short_lookup = context_builder_module._canonical_table_lookup(
        {"orders": {"layer": "DWD"}}
    )

    assert lookup.get("wrong.db.orders") is None
    assert lookup.get("orders") == {"layer": "DWD"}
    assert short_lookup.get("wrong.db.orders") is None


def test_build_context_with_ddl_and_task(sample_lineage_data, tmp_path):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()

    (ddl_dir / "dwd_customer.sql").write_text("CREATE dwd_customer;")
    (tasks_dir / "dwd_customer.sql").write_text("INSERT dwd_customer;")

    contexts = build_contexts(
        "test_proj", sample_lineage_data, ddl_dir, tasks_dir
    )
    ctx = next(c for c in contexts if c.table_name == "dwd_customer")

    assert ctx.ddl == "CREATE dwd_customer;"
    assert ctx.etl_sql == "INSERT dwd_customer;"
    assert ctx.upstream_tables == ["ods_customer"]
    assert ctx.downstream_tables == ["ads_sales_dashboard"]


def test_build_contexts_extracts_downstream_entity_publication_features(
    tmp_path,
    monkeypatch,
):
    contexts = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=["clean_entity", "published_entity", "entity_summary"],
        upstream={
            "clean_entity": {"raw_entity"},
            "published_entity": {"clean_entity"},
            "entity_summary": {"clean_entity"},
        },
        downstream={
            "clean_entity": {"published_entity", "entity_summary"},
        },
        model_metadata={
            "clean_entity": {"name": "clean_entity", "layer": "DWD"},
            "published_entity": {
                "name": "published_entity",
                "layer": "DIM",
            },
            "entity_summary": {
                "name": "entity_summary",
                "layer": "DWS",
            },
        },
        task_files={
            "published_entity.sql": (
                "INSERT INTO published_entity "
                "SELECT MD5(CAST(entity_id AS STRING)) AS entity_key, "
                "entity_id AS entity_natural_key, "
                "CURRENT_TIMESTAMP AS effective_date, "
                "CAST('9999-12-31' AS DATETIME) AS expiration_date, "
                "TRUE AS is_current FROM clean_entity;"
            ),
            "entity_summary.sql": (
                "INSERT INTO entity_summary "
                "SELECT MD5(CAST(entity_id AS STRING)) AS entity_key, "
                "SUM(amount) AS total_amount FROM clean_entity "
                "GROUP BY entity_id;"
            ),
        },
    )
    context = next(ctx for ctx in contexts if ctx.table_name == "clean_entity")

    assert context.downstream_entity_publication_features == {
        "published_entity": {
            "generated_key_columns": ["entity_key"],
            "natural_key_aliases": ["entity_natural_key"],
            "added_version_control_columns": [
                "effective_date",
                "expiration_date",
                "is_current",
            ],
            "combines_sources_with_union": False,
            "contains_aggregation": False,
        }
    }


def test_build_context_without_task(sample_lineage_data, tmp_path):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()

    (ddl_dir / "dwd_order_detail.sql").write_text("CREATE dwd_order_detail;")
    # No task file

    contexts = build_contexts(
        "test_proj", sample_lineage_data, ddl_dir, tasks_dir
    )
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")

    assert ctx.ddl == "CREATE dwd_order_detail;"
    assert ctx.etl_sql == ""
    assert ctx.downstream_tables == ["dws_store_sales_daily"]


def test_build_contexts_warns_without_parsing_tasks_when_lineage_empty(
    tmp_path,
    caplog,
):
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    ddl_dir.mkdir()
    tasks_dir.mkdir()
    (tasks_dir / "dwd_order_clean.sql").write_text(
        "INSERT INTO dwd_order_clean SELECT * FROM ods_order;",
        encoding="utf-8",
    )

    context = build_contexts(
        "test_proj",
        {"tables": [{"name": "dwd_order_clean"}], "edges": []},
        ddl_dir,
        tasks_dir,
        model_metadata={"dwd_order_clean": {"layer": "DWD"}},
    )[0]

    assert context.upstream_tables == []
    assert context.downstream_tables == []
    assert "lineage graph is empty" in caplog.text.lower()


def test_build_contexts_reads_default_mid_asset_dirs(
    sample_lineage_data,
    tmp_path,
    monkeypatch,
):
    project = "context_mid_assets"
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    tasks_dir = project_dir / "mid" / "tasks"
    ddl_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    (ddl_dir / "dwd_order_detail.sql").write_text(
        "CREATE TABLE dwd_order_detail (order_id BIGINT);",
        encoding="utf-8",
    )
    (tasks_dir / "dwd_order_detail.sql").write_text(
        "INSERT INTO dwd_order_detail SELECT order_id FROM ods_order;",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    contexts = build_contexts(project, sample_lineage_data)
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")

    assert ctx.ddl == "CREATE TABLE dwd_order_detail (order_id BIGINT);"
    assert ctx.etl_sql == (
        "INSERT INTO dwd_order_detail SELECT order_id FROM ods_order;"
    )


def test_build_contexts_includes_business_semantics_catalog_options(
    sample_lineage_data, tmp_path, monkeypatch
):
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
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [],
                "business_areas": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "business_processes.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "business_processes": [
                    {
                        "code": "ORDER_TRANSACTION",
                        "name": "订单交易",
                        "tables": ["dwd_order_detail"],
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "semantic_subjects.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "semantic_subjects": [
                    {
                        "code": "CUSTOMER",
                        "name": "客户",
                        "tables": ["dwd_customer"],
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    config.clear_business_semantics_cache()

    contexts = build_contexts(project, sample_lineage_data)
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")

    assert ctx.business_semantics_options == {
        "business_processes": [
            {
                "code": "ORDER_TRANSACTION",
                "name": "订单交易",
            }
        ],
        "semantic_subjects": [
            {
                "code": "CUSTOMER",
                "name": "客户",
            }
        ],
    }


def test_build_contexts_includes_project_context_from_business_semantics(
    sample_lineage_data, tmp_path, monkeypatch
):
    project = "context_project_context"
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
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "project_context": (
                    "这是一个门店零售数据集市，订单交易是核心业务过程，"
                    "客户、商品和门店是核心分析实体。"
                ),
                "data_domains": [],
                "business_areas": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    config.clear_business_semantics_cache()

    contexts = build_contexts(project, sample_lineage_data)
    ctx = next(c for c in contexts if c.table_name == "dwd_order_detail")

    assert ctx.project_context == (
        "这是一个门店零售数据集市，订单交易是核心业务过程，"
        "客户、商品和门店是核心分析实体。"
    )
