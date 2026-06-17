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
