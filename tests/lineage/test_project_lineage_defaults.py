import json

import pytest

import config
from lineage import store, table_graph


def _configure_project(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )


def test_table_graph_load_lineage_data_ignores_old_tool_file(
    monkeypatch, tmp_path
):
    _configure_project(monkeypatch, tmp_path)
    tool_lineage_dir = tmp_path / "tool_lineage"
    tool_lineage_dir.mkdir()
    (tool_lineage_dir / "lineage_data_demo.json").write_text(
        json.dumps({"tables": [], "edges": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        table_graph,
        "__file__",
        str(tool_lineage_dir / "table_graph.py"),
    )

    with pytest.raises(FileNotFoundError):
        table_graph.load_lineage_data("demo")


def test_json_lineage_store_ignores_old_tool_file_by_default(
    monkeypatch, tmp_path
):
    _configure_project(monkeypatch, tmp_path)
    tool_lineage_dir = tmp_path / "tool_lineage"
    tool_lineage_dir.mkdir()
    (tool_lineage_dir / "lineage_data_demo.json").write_text(
        json.dumps({"tables": [], "edges": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        store,
        "__file__",
        str(tool_lineage_dir / "store.py"),
    )

    with pytest.raises(FileNotFoundError):
        store.JsonLineageStore().load_snapshot("demo")
