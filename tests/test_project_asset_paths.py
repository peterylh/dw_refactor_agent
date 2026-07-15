from pathlib import Path

import pytest

import dw_refactor_agent.config as config


def test_project_config_is_loaded_from_warehouse_yaml():
    shop = config.PROJECT_CONFIG["shop"]

    assert shop["dir"] == "warehouses/shop"
    assert shop["db"] == "shop_dm"
    assert shop["qa_db"] == "shop_dm_qa"
    assert shop["lineage_db"] == "shop_lineage"
    assert shop["naming_config"] == "warehouses/shop/naming_config.yaml"
    assert shop["ods_source_catalog_dialects"] == {"internal": "doris"}
    assert shop["schema_identity"] == {"required": True}
    assert config.PROJECT_CONFIG["finance_analytics"]["schema_identity"] == {
        "required": True
    }
    assert config.PROJECT_CONFIG["shop_layering_fix"]["fixture"] == {
        "source_project": "shop",
        "purpose": "table_inspector_layer_benchmark_gold_labels",
        "execution": "disabled",
        "warning": ("Do not execute this project; metadata fixture only."),
    }


def test_shop_uses_precreated_qa_database_pool():
    assert config.PROJECT_CONFIG["shop"]["verification"][
        "qa_database_pool"
    ] == ["shop_dm_qa", "shop_dm_qa_02"]


def test_load_project_config_maps_warehouse_yaml_to_runtime_shape(tmp_path):
    warehouse_dir = tmp_path / "warehouses" / "demo"
    warehouse_dir.mkdir(parents=True)
    (warehouse_dir / "warehouse.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "catalog: internal",
                "database: demo_dm",
                "qa_database: demo_dm_qa",
                "lineage_database: demo_lineage",
                "naming_config: config/naming.yaml",
                "default_dialect: doris",
                "ods_source_catalog_dialects:",
                "  internal: doris",
                "  hive: hive",
                "schema_identity:",
                "  required: true",
            ]
        ),
        encoding="utf-8",
    )

    project_config = config.load_project_config(tmp_path)

    assert project_config == {
        "demo": {
            "dir": "warehouses/demo",
            "catalog": "internal",
            "db": "demo_dm",
            "qa_db": "demo_dm_qa",
            "lineage_db": "demo_lineage",
            "naming_config": "warehouses/demo/config/naming.yaml",
            "ods_source_catalog_dialects": {
                "internal": "doris",
                "hive": "hive",
            },
            "schema_identity": {"required": True},
        }
    }


def test_load_warehouse_config_preserves_qa_database_pool(tmp_path):
    warehouse_dir = tmp_path / "warehouses" / "demo"
    warehouse_dir.mkdir(parents=True)
    warehouse_file = warehouse_dir / "warehouse.yaml"
    warehouse_file.write_text(
        "\n".join(
            [
                "name: demo",
                "database: demo_dm",
                "qa_database: demo_dm_qa",
                "lineage_database: demo_lineage",
                "verification:",
                "  qa_database_pool:",
                "    - demo_dm_qa",
                "    - demo_dm_qa_02",
            ]
        ),
        encoding="utf-8",
    )

    loaded = config.load_warehouse_config(warehouse_file, tmp_path)

    assert loaded["verification"]["qa_database_pool"] == [
        "demo_dm_qa",
        "demo_dm_qa_02",
    ]


@pytest.mark.parametrize(
    "value",
    ["[]", "[demo_dm_qa, '']", "demo_dm_qa"],
)
def test_load_warehouse_config_rejects_invalid_qa_database_pool(
    tmp_path, value
):
    warehouse_dir = tmp_path / "warehouses" / "demo"
    warehouse_dir.mkdir(parents=True)
    warehouse_file = warehouse_dir / "warehouse.yaml"
    warehouse_file.write_text(
        "\n".join(
            [
                "name: demo",
                "database: demo_dm",
                "qa_database: demo_dm_qa",
                "lineage_database: demo_lineage",
                "verification:",
                f"  qa_database_pool: {value}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="qa_database_pool.*non-empty"):
        config.load_warehouse_config(warehouse_file, tmp_path)


def test_resolve_project_root_prefers_env_then_warehouse_cwd(tmp_path):
    env_root = tmp_path / "env_root"
    cwd_root = tmp_path / "cwd_root"
    env_root.mkdir()
    (cwd_root / "warehouses").mkdir(parents=True)

    assert (
        config.resolve_project_root(
            default_root=tmp_path / "site_packages",
            cwd=cwd_root,
            env={},
        )
        == cwd_root
    )
    assert (
        config.resolve_project_root(
            default_root=tmp_path / "site_packages",
            cwd=cwd_root,
            env={config.PROJECT_ROOT_ENV: str(env_root)},
        )
        == env_root.resolve()
    )


def test_iter_project_asset_files_ignores_root_and_includes_ods_dir(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "ddl" / "legacy_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_customer.sql"
    ).write_text("", encoding="utf-8")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    files = list(config.iter_project_asset_files("demo", "ddl", "*.sql"))

    assert [path.name for path in files] == ["ods_customer.sql"]


def test_iter_project_asset_files_includes_configured_ods_source_catalogs(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "hive" / "source_db").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "hive" / "ods_source").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "external" / "source_dm").mkdir(
        parents=True
    )
    (project_dir / "ddl" / "legacy_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_customer.sql"
    ).write_text("", encoding="utf-8")
    (
        project_dir
        / "ods"
        / "ddl"
        / "hive"
        / "source_db"
        / "tran_data_menu.sql"
    ).write_text("", encoding="utf-8")
    (
        project_dir
        / "ods"
        / "ddl"
        / "hive"
        / "ods_source"
        / "tran_data_account.sql"
    ).write_text("", encoding="utf-8")
    (
        project_dir
        / "ods"
        / "ddl"
        / "external"
        / "source_dm"
        / "source_customer.sql"
    ).write_text("", encoding="utf-8")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
            "ods_source_catalog_dialects": {
                "hive": "hive",
            },
        },
    )

    files = list(config.iter_project_asset_files("demo", "ddl", "*.sql"))

    assert [path.name for path in files] == [
        "ods_customer.sql",
        "source_customer.sql",
        "tran_data_account.sql",
        "tran_data_menu.sql",
        "dwd_customer.sql",
    ]
    assert config.project_ods_source_catalog_dialects("demo") == {
        "internal": "doris",
        "hive": "hive",
    }
    assert config.ods_source_catalog_ddl_dialect("demo", "external") == "doris"
    assert config.ods_source_catalog_ddl_dialect("demo", "internal") == "doris"
    assert config.ods_source_catalog_ddl_dialect("demo", "hive") == "hive"


def test_load_model_metadata_reads_catalog_database_ods_models(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir(parents=True)
    (project_dir / "ods" / "models" / "internal" / "demo_dm").mkdir(
        parents=True
    )
    (project_dir / "models" / "legacy_customer.yaml").write_text(
        "version: 2\nname: legacy_customer\nlayer: DWD\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dwd_customer.yaml").write_text(
        "version: 2\nname: dwd_customer\nlayer: DWD\n",
        encoding="utf-8",
    )
    (
        project_dir
        / "ods"
        / "models"
        / "internal"
        / "demo_dm"
        / "ods_customer.yaml"
    ).write_text(
        "version: 2\nname: ods_customer\nlayer: ODS\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )
    config.clear_model_metadata_cache()

    metadata = config.load_model_metadata("demo")

    assert sorted(metadata) == ["dwd_customer", "ods_customer"]
    assert metadata["ods_customer"]["layer"] == "ODS"
    config.clear_model_metadata_cache()


def test_model_path_for_table_routes_ods_layer_to_catalog_database_dir(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    path = config.model_path_for_table("demo", "ods_customer", layer="ODS")

    assert path == Path(
        tmp_path,
        "demo_project",
        "ods",
        "models",
        "internal",
        "demo_dm",
        "ods_customer.yaml",
    )


def test_project_artifact_paths_are_project_scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    assert config.project_artifact_dir("demo", "lineage") == Path(
        tmp_path,
        "demo_project",
        "artifacts",
        "lineage",
    )
    assert config.lineage_data_path("demo") == Path(
        tmp_path,
        "demo_project",
        "artifacts",
        "lineage",
        "lineage_data.json",
    )
    assert config.job_dag_path("demo") == Path(
        tmp_path,
        "demo_project",
        "artifacts",
        "lineage",
        "job_dag.json",
    )
    assert config.lineage_task_cache_path("demo") == Path(
        tmp_path,
        "demo_project",
        "artifacts",
        "lineage",
        "task_lineage_cache.json",
    )
    assert config.assess_cache_path("demo", "inspect.json") == Path(
        tmp_path,
        "demo_project",
        "artifacts",
        "assessment",
        "cache",
        "inspect.json",
    )


def test_finance_analytics_ods_assets_are_under_catalog_database_dir():
    project_dir = config.project_dir("finance_analytics")
    ods_root = project_dir / "ods"
    ods_dirs = {
        "ddl": ods_root / "ddl" / "internal" / "finance_analytics_dm",
        "models": ods_root / "models" / "internal" / "finance_analytics_dm",
        "data": ods_root / "data" / "internal" / "finance_analytics_dm",
    }

    for asset_kind, ods_dir in ods_dirs.items():
        pattern = "ods_*.yaml" if asset_kind == "models" else "ods_*.sql"
        assert ods_dir.exists()
        assert list(ods_dir.glob(pattern))
        assert not list((project_dir / asset_kind).glob(pattern))

    ddl_files = config.iter_project_asset_files(
        "finance_analytics", "ddl", "*.sql"
    )
    model_files = config.iter_project_asset_files(
        "finance_analytics", "models", "*.yaml"
    )
    data_files = config.iter_project_asset_files(
        "finance_analytics", "data", "*.sql"
    )

    assert any(path.name == "ods_customers.sql" for path in ddl_files)
    assert any(path.name == "ods_customers.yaml" for path in model_files)
    assert any(path.name == "ods_customers.sql" for path in data_files)


def test_project_layer_assets_are_under_mid_and_ads_dirs():
    expectations = {
        "shop": {
            "mid": {"ddl": 15, "tasks": 20, "models": 15},
            "ads": {"ddl": 6, "tasks": 7, "models": 6},
        },
        "finance_analytics": {
            "mid": {"ddl": 38, "tasks": 38, "models": 38},
            "ads": {"ddl": 4, "tasks": 4, "models": 4},
        },
    }

    for project, role_expectations in expectations.items():
        project_dir = config.project_dir(project)
        for asset_kind in ("ddl", "tasks", "models"):
            root_files = [
                path
                for path in (project_dir / asset_kind).glob("*")
                if path.is_file()
            ]
            assert root_files == []

        for role, asset_counts in role_expectations.items():
            for asset_kind, expected_count in asset_counts.items():
                pattern = "*.yaml" if asset_kind == "models" else "*.sql"
                files = list((project_dir / role / asset_kind).rglob(pattern))
                assert len(files) == expected_count


def test_iter_project_asset_files_includes_mid_and_ads_dirs(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "ads" / "ddl").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "ddl" / "legacy_table.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "dwd_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "ads" / "ddl" / "ads_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_customer.sql"
    ).write_text("", encoding="utf-8")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    files = config.iter_project_asset_files("demo", "ddl", "*.sql")

    assert [path.relative_to(project_dir).as_posix() for path in files] == [
        "ods/ddl/internal/demo_dm/ods_customer.sql",
        "mid/ddl/dwd_customer.sql",
        "ads/ddl/ads_customer.sql",
    ]


def test_task_helpers_discover_mid_and_ads_tasks(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "full_refresh").mkdir(parents=True)
    (project_dir / "ads" / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / "legacy_job.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dwd_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dwd_customer_full_refresh.sql"
    ).write_text("", encoding="utf-8")
    (project_dir / "ads" / "tasks" / "ads_customer.sql").write_text(
        "",
        encoding="utf-8",
    )

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    files = config.iter_project_task_files("demo")
    source_files = [config.task_source_file("demo", path) for path in files]

    assert source_files == [
        "dwd_customer.sql",
        "full_refresh/dwd_customer_full_refresh.sql",
        "ads_customer.sql",
    ]
    assert config.task_path_for_job("demo", "dwd_customer") == (
        project_dir / "mid" / "tasks" / "dwd_customer.sql"
    )
    assert config.task_path_for_source_file(
        "demo",
        "full_refresh/dwd_customer_full_refresh.sql",
    ) == (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dwd_customer_full_refresh.sql"
    )


def test_model_path_for_table_routes_mid_and_ads_layers(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )

    assert config.model_path_for_table(
        "demo",
        "ads_customer",
        layer="ADS",
    ) == Path(tmp_path, "demo_project", "ads", "models", "ads_customer.yaml")
    assert config.model_path_for_table(
        "demo",
        "dwd_customer",
        layer="DWD",
    ) == Path(tmp_path, "demo_project", "mid", "models", "dwd_customer.yaml")
    assert config.model_path_for_table(
        "demo",
        "dim_customer",
        layer="DIM",
    ) == Path(tmp_path, "demo_project", "mid", "models", "dim_customer.yaml")
