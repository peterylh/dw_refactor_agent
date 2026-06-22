from pathlib import Path

import config


def test_iter_project_asset_files_includes_catalog_database_ods_dir(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "ddl" / "dwd_customer.sql").write_text("", encoding="utf-8")
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_customer.sql"
    ).write_text("", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
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

    assert [path.name for path in files] == [
        "dwd_customer.sql",
        "ods_customer.sql",
    ]


def test_iter_project_asset_files_includes_configured_ods_source_catalogs(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "hive" / "source_db").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "hive" / "ods_source").mkdir(parents=True)
    (project_dir / "ods" / "ddl" / "external" / "source_dm").mkdir(
        parents=True
    )
    (project_dir / "ddl" / "dwd_customer.sql").write_text(
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

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
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
        "dwd_customer.sql",
        "ods_customer.sql",
        "source_customer.sql",
        "tran_data_account.sql",
        "tran_data_menu.sql",
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
    (project_dir / "ods" / "models" / "internal" / "demo_dm").mkdir(
        parents=True
    )
    (project_dir / "models" / "dwd_customer.yaml").write_text(
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

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_dm",
        },
    )
    config._model_metadata_cache.clear()

    metadata = config.load_model_metadata("demo")

    assert sorted(metadata) == ["dwd_customer", "ods_customer"]
    assert metadata["ods_customer"]["layer"] == "ODS"
    config._model_metadata_cache.clear()


def test_model_path_for_table_routes_ods_layer_to_catalog_database_dir(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
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
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
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
        "lineage",
    )
    assert config.lineage_data_path("demo") == Path(
        tmp_path,
        "demo_project",
        "lineage",
        "lineage_data.json",
    )
    assert config.job_dag_path("demo") == Path(
        tmp_path,
        "demo_project",
        "lineage",
        "job_dag.json",
    )
    assert config.lineage_task_cache_path("demo") == Path(
        tmp_path,
        "demo_project",
        "lineage",
        "task_lineage_cache.json",
    )
    assert config.assess_cache_path("demo", "inspect.json") == Path(
        tmp_path,
        "demo_project",
        "assess",
        "cache",
        "inspect.json",
    )


def test_finance_analytics_ods_assets_are_under_catalog_database_dir():
    project_dir = config.PROJECT_ROOT / "finance_analytics"
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
