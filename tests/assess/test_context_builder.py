import pytest
import yaml

import dw_refactor_agent.assessment.llm.context_builder as context_builder_module
import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.context_builder import (
    InspectionContextSetError,
    build_contexts,
    extract_column_lineage,
    extract_dependencies,
)

MODEL_METADATA = {
    "dwd_customer": {"version": 2, "name": "dwd_customer", "layer": "DWD"},
    "dwd_order_detail": {
        "version": 2,
        "name": "dwd_order_detail",
        "layer": "DWD",
    },
    "dws_store_sales_daily": {
        "version": 2,
        "name": "dws_store_sales_daily",
        "layer": "DWS",
    },
    "ads_sales_dashboard": {
        "version": 2,
        "name": "ads_sales_dashboard",
        "layer": "ADS",
    },
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
    inspection_targets=None,
    asset_content=None,
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
    model_metadata = {
        name: {
            "version": 2,
            "name": name,
            **metadata,
        }
        for name, metadata in model_metadata.items()
    }
    return build_contexts(
        "test_proj",
        {"tables": [{"name": name} for name in tables]},
        ddl_dir,
        tasks_dir,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
        inspection_targets=inspection_targets,
        asset_content=asset_content,
    )


def test_build_contexts_uses_explicit_target_without_lineage(
    tmp_path,
    monkeypatch,
):
    contexts = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=[],
        upstream={},
        model_metadata={"dim_currency": {"layer": "DIM"}},
        inspection_targets=["internal.demo.dim_currency"],
        asset_content={
            "dim_currency": {
                "ddl": "CREATE TABLE demo.dim_currency (code VARCHAR(3));",
                "etl_sql": "",
            }
        },
    )

    assert len(contexts) == 1
    assert contexts[0].table_name == "dim_currency"
    assert contexts[0].table_identity == "internal.demo.dim_currency"
    assert contexts[0].ddl.startswith("CREATE TABLE")
    assert contexts[0].etl_sql == ""


def test_build_contexts_explicit_targets_are_exact_and_keep_short_lineage(
    tmp_path,
    monkeypatch,
):
    contexts = _build_contexts_for_graph(
        tmp_path,
        monkeypatch,
        tables=["dwd_orders", "dws_order_daily", "dws_unrelated"],
        upstream={"dws_order_daily": {"dwd_orders"}},
        model_metadata={
            "dwd_orders": {"layer": "DWD"},
            "dws_order_daily": {"layer": "DWS"},
            "dws_unrelated": {"layer": "DWS"},
        },
        inspection_targets=["internal.demo.dws_order_daily"],
    )

    assert [context.table_identity for context in contexts] == [
        "internal.demo.dws_order_daily"
    ]
    assert contexts[0].upstream_tables == ["dwd_orders"]


def test_build_contexts_blocks_ambiguous_lineage_for_explicit_target(
    tmp_path,
    monkeypatch,
):
    with pytest.raises(
        InspectionContextSetError,
        match="ambiguous qualified lineage candidates",
    ):
        _build_contexts_for_graph(
            tmp_path,
            monkeypatch,
            tables=[],
            upstream={
                "catalog_a.db_a.dim_currency": set(),
                "catalog_b.db_b.dim_currency": set(),
            },
            model_metadata={"dim_currency": {"layer": "DIM"}},
            inspection_targets=["internal.demo.dim_currency"],
        )


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
        model_metadata={
            "dwd_order_clean": {
                "version": 2,
                "name": "dwd_order_clean",
                "layer": "DWD",
            }
        },
    )[0]

    assert context.upstream_tables == []
    assert context.downstream_tables == []
    assert "lineage graph is empty" in caplog.text.lower()


def test_build_contexts_clears_stale_metadata_cache_inside_snapshot(
    tmp_path, monkeypatch
):
    project = "context_consistent_snapshot"
    project_dir = tmp_path / project
    models_dir = project_dir / "mid" / "models"
    ddl_dir = tmp_path / "ddl"
    tasks_dir = tmp_path / "tasks"
    for directory in (models_dir, ddl_dir, tasks_dir):
        directory.mkdir(parents=True)
    model_path = models_dir / "fact.yaml"
    model_path.write_text(
        yaml.safe_dump(
            {"version": 2, "name": "fact", "layer": "DWD"},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "fact.sql").write_text(
        "CREATE TABLE fact (id BIGINT);",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "catalog": "internal", "db": "demo"},
    )
    monkeypatch.setattr(
        context_builder_module,
        "load_model_metadata",
        config.load_model_metadata,
    )
    config.clear_model_metadata_cache()
    assert config.load_model_metadata(project)["fact"]["layer"] == "DWD"
    model_path.write_text(
        yaml.safe_dump(
            {"version": 2, "name": "fact", "layer": "DWS"},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    context = build_contexts(
        project,
        {"tables": [{"name": "fact"}], "edges": []},
        ddl_dir,
        tasks_dir,
    )[0]

    assert context.layer == "DWS"


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


def test_build_contexts_excludes_fixed_boundaries_with_wrong_declared_layer(
    tmp_path,
    monkeypatch,
    caplog,
):
    project = "context_fixed_boundaries"
    project_dir = tmp_path / project
    ods_models = project_dir / "ods" / "models" / "internal" / "demo"
    mid_models = project_dir / "mid" / "models"
    ads_models = project_dir / "ads" / "models"
    for directory in (ods_models, mid_models, ads_models):
        directory.mkdir(parents=True)
    for path, metadata in (
        (ods_models / "orders.yaml", {"name": "orders", "layer": "DWD"}),
        (
            mid_models / "order_summary.yaml",
            {"name": "order_summary", "layer": "DWS"},
        ),
        (
            ads_models / "dashboard.yaml",
            {"name": "dashboard", "layer": "DWD"},
        ),
    ):
        path.write_text(
            yaml.safe_dump(metadata, sort_keys=False),
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "catalog": "internal", "db": "demo"},
    )
    metadata = {
        "orders": {"version": 2, "name": "orders", "layer": "DWD"},
        "order_summary": {
            "version": 2,
            "name": "order_summary",
            "layer": "DWS",
        },
        "dashboard": {
            "version": 2,
            "name": "dashboard",
            "layer": "DWD",
        },
    }

    contexts = build_contexts(
        project,
        {
            "tables": [
                {"name": "orders"},
                {"name": "order_summary"},
                {"name": "dashboard"},
            ],
            "edges": [],
        },
        model_metadata=metadata,
    )

    assert [context.table_name for context in contexts] == ["order_summary"]
    assert "Skipping fixed-boundary model orders" in caplog.text
    assert "Skipping fixed-boundary model dashboard" in caplog.text


def test_generate_context_roles_ignore_stale_model_directories(
    tmp_path,
    monkeypatch,
):
    project = "context_generate_roles"
    stale_model_dir = (
        tmp_path / project / "ods" / "models" / "internal" / "demo"
    )
    stale_model_dir.mkdir(parents=True)
    (stale_model_dir / "orders.yaml").write_text(
        yaml.safe_dump({"name": "orders", "layer": "DWD"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "catalog": "internal", "db": "demo"},
    )

    contexts = build_contexts(
        project,
        {"tables": [{"name": "orders"}], "edges": []},
        model_metadata={
            "orders": {"version": 2, "name": "orders", "layer": "DWD"}
        },
        use_model_metadata_asset_roles=True,
    )

    assert [context.table_name for context in contexts] == ["orders"]


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
