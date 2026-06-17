import importlib.util
from pathlib import Path

import config

MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "exec" / "reinit_project.py"
)
SPEC = importlib.util.spec_from_file_location(
    "reinit_project_module", MODULE_PATH
)
reinit_project = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reinit_project)


def test_get_etl_date_partitions_uses_model_layer(monkeypatch, tmp_path):
    models_dir = tmp_path / "demo_project" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "source_events.yaml").write_text(
        "version: 2\nname: source_events\nlayer: ODS\n",
        encoding="utf-8",
    )
    (models_dir / "ods_legacy.yaml").write_text(
        "version: 2\nname: ods_legacy\nlayer: DWD\n",
        encoding="utf-8",
    )

    calls = []

    def fake_run_sql(sql_text, db, env_cmd):
        calls.append((sql_text, db, env_cmd))
        if sql_text == "SHOW TABLES":
            return "Tables_in_demo_db\nsource_events\nods_legacy\n"
        return "d\n2025-01-02\n2025-01-01\n"

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        reinit_project.PROJECT_CONFIG,
        "demo",
        {"dir": "demo_project"},
    )
    monkeypatch.setattr(reinit_project, "run_sql", fake_run_sql)
    config._model_metadata_cache.clear()

    assert reinit_project.get_etl_date_partitions(
        "demo",
        "demo_db",
        ["mysql"],
    ) == ["2025-01-01", "2025-01-02"]
    assert calls == [
        ("SHOW TABLES", "demo_db", ["mysql"]),
        (
            "SELECT DISTINCT DATE(load_time) AS d FROM demo_db.source_events ORDER BY d",
            "demo_db",
            ["mysql"],
        ),
    ]
    config._model_metadata_cache.clear()


def test_project_sql_files_include_catalog_database_ods_assets(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    ddl_dir = project_dir / "ddl"
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_db"
    ddl_dir.mkdir(parents=True)
    ods_ddl_dir.mkdir(parents=True)
    (ddl_dir / "dwd_customer.sql").write_text("", encoding="utf-8")
    (ods_ddl_dir / "ods_customer.sql").write_text("", encoding="utf-8")

    monkeypatch.setattr(reinit_project, "_root", tmp_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        reinit_project.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
        },
    )

    files = reinit_project._project_sql_files("demo", "ddl")

    assert [path.name for path in files] == [
        "dwd_customer.sql",
        "ods_customer.sql",
    ]
