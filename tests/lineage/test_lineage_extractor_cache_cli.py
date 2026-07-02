import json
import sys

import config
import lineage.lineage_extractor as lineage_extractor


def _write_demo_project(root):
    project_dir = root / "demo"
    ddl_dir = project_dir / "ddl"
    tasks_dir = project_dir / "tasks"
    ddl_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    (ddl_dir / "ods_order.sql").write_text(
        """
        CREATE TABLE demo_dm.ods_order (
            order_id BIGINT,
            amount DECIMAL(10,2)
        );
        """,
        encoding="utf-8",
    )
    (ddl_dir / "dwd_order.sql").write_text(
        """
        CREATE TABLE demo_dm.dwd_order (
            order_id BIGINT,
            amount DECIMAL(10,2)
        );
        """,
        encoding="utf-8",
    )
    (tasks_dir / "dwd_order.sql").write_text(
        """
        INSERT INTO demo_dm.dwd_order(order_id, amount)
        SELECT order_id, amount
        FROM demo_dm.ods_order;
        """,
        encoding="utf-8",
    )
    return project_dir


def _configure_demo_project(monkeypatch, tmp_path):
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": str(tmp_path / "demo"),
            "catalog": "internal",
            "db": "demo_dm",
        },
    )
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_PROJECT",
        lineage_extractor.CURRENT_PROJECT,
    )
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_CATALOG",
        lineage_extractor.CURRENT_CATALOG,
    )
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_DB",
        lineage_extractor.CURRENT_DB,
    )


def test_full_extraction_reuses_default_task_cache(
    tmp_path, monkeypatch, capsys
):
    project_dir = _write_demo_project(tmp_path)
    _configure_demo_project(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["lineage_extractor.py", "--project", "demo"],
    )

    lineage_extractor.main()

    cache_path = project_dir / "lineage" / "task_lineage_cache.json"
    assert cache_path.exists()
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert [entry["source_file"] for entry in cache["tasks"]] == [
        "dwd_order.sql"
    ]

    def fail_task(_work_item, _schema):
        raise AssertionError("task extraction should be served from cache")

    monkeypatch.setattr(
        lineage_extractor, "_extract_task_work_item", fail_task
    )
    capsys.readouterr()

    lineage_extractor.main()

    captured = capsys.readouterr()
    assert "cache hit" in captured.out


def test_full_extraction_writes_custom_output_and_cache(tmp_path, monkeypatch):
    project_dir = _write_demo_project(tmp_path)
    _configure_demo_project(monkeypatch, tmp_path)
    output_path = tmp_path / "artifacts" / "lineage_data_demo.json"
    cache_path = tmp_path / "artifacts" / "task_lineage_cache.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lineage_extractor.py",
            "--project",
            "demo",
            "--output",
            str(output_path),
            "--cache-file",
            str(cache_path),
        ],
    )

    lineage_extractor.main()

    default_output_path = project_dir / "lineage" / "lineage_data.json"
    assert output_path.exists()
    assert cache_path.exists()
    assert not default_output_path.exists()
    output = json.loads(output_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert sorted(table["name"] for table in output["tables"]) == [
        "dwd_order",
        "ods_order",
    ]
    assert [entry["source_file"] for entry in cache["tasks"]] == [
        "dwd_order.sql"
    ]
