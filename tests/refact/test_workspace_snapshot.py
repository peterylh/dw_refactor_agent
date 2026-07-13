import os

import pytest

import dw_refactor_agent.refactor.workspace_snapshot as snapshot_module
from dw_refactor_agent.refactor.workspace_snapshot import (
    workspace_file_entries,
    workspace_fingerprint,
)


@pytest.fixture
def configured_root(tmp_path, monkeypatch):
    monkeypatch.setitem(
        snapshot_module.config.PROJECT_CONFIG,
        "shop",
        {
            "dir": "warehouses/shop",
            "naming_config": "naming_config.yaml",
        },
    )
    warehouse = tmp_path / "warehouses" / "shop" / "warehouse.yaml"
    warehouse.parent.mkdir(parents=True)
    warehouse.write_text(
        "name: shop\nnaming_config: ../../naming_config.yaml\n",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "version: 2\n", encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    "relative_path",
    [
        "warehouses/shop/ods/ddl/internal/shop_ods/ods_order.sql",
        "warehouses/shop/mid/ddl/dws_sales.sql",
        "warehouses/shop/ads/ddl/ads_sales.sql",
        "warehouses/shop/mid/tasks/dws_sales.sql",
        "warehouses/shop/mid/tasks/full_refresh/dws_sales.sql",
        "warehouses/shop/ads/tasks/ads_sales.sql",
        "warehouses/shop/ods/models/internal/shop_ods/ods_order.yaml",
        "warehouses/shop/mid/models/dws_sales.yaml",
        "warehouses/shop/ads/models/ads_sales.yaml",
        "warehouses/shop/business_processes.yaml",
        "warehouses/shop/business_taxonomy.yaml",
        "warehouses/shop/semantic_subjects.yaml",
        "src/dw_refactor_agent/refactor/run.py",
        "src/dw_refactor_agent/lineage/asset_graph.py",
        "src/dw_refactor_agent/ddl_deriver/ddl_deriver.py",
        "src/dw_refactor_agent/execution/model_config.py",
        "src/dw_refactor_agent/config/assets.py",
        "src/dw_refactor_agent/sql/doris.py",
    ],
)
def test_relevant_file_content_changes_workspace_fingerprint(
    configured_root, relative_path
):
    path = configured_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before", encoding="utf-8")
    before = workspace_fingerprint(configured_root, "shop")

    path.write_text("after", encoding="utf-8")

    assert workspace_fingerprint(configured_root, "shop") != before


def test_add_delete_and_rename_change_workspace_fingerprint(configured_root):
    first = configured_root / "warehouses/shop/mid/tasks/first.sql"
    second = configured_root / "warehouses/shop/mid/tasks/second.sql"
    first.parent.mkdir(parents=True)
    before = workspace_fingerprint(configured_root, "shop")

    first.write_text("SELECT 1", encoding="utf-8")
    after_add = workspace_fingerprint(configured_root, "shop")
    first.rename(second)
    after_rename = workspace_fingerprint(configured_root, "shop")
    second.unlink()
    after_delete = workspace_fingerprint(configured_root, "shop")

    assert len({before, after_add, after_rename}) == 3
    assert after_delete == before


def test_mtime_does_not_change_workspace_fingerprint(configured_root):
    path = configured_root / "warehouses/shop/mid/tasks/dws_sales.sql"
    path.parent.mkdir(parents=True)
    path.write_text("SELECT 1", encoding="utf-8")
    before = workspace_fingerprint(configured_root, "shop")

    os.utime(path, (path.stat().st_atime + 10, path.stat().st_mtime + 10))

    assert workspace_fingerprint(configured_root, "shop") == before


def test_loaded_runtime_tool_change_changes_workspace_fingerprint(
    configured_root, monkeypatch
):
    monkeypatch.setattr(
        snapshot_module,
        "runtime_tool_file_entries",
        lambda: [
            {
                "path": "src/dw_refactor_agent/refactor/run.py",
                "content_sha256": "sha256:before",
            }
        ],
    )
    before = workspace_fingerprint(configured_root, "shop")
    monkeypatch.setattr(
        snapshot_module,
        "runtime_tool_file_entries",
        lambda: [
            {
                "path": "src/dw_refactor_agent/refactor/run.py",
                "content_sha256": "sha256:after",
            }
        ],
    )

    assert workspace_fingerprint(configured_root, "shop") != before


def test_artifacts_docs_tests_and_other_project_are_excluded(configured_root):
    before = workspace_fingerprint(configured_root, "shop")
    for relative_path in (
        "warehouses/shop/artifacts/refactor_runs/x/plan.json",
        "docs/notes.md",
        "tests/test_notes.py",
        "warehouses/finance_analytics/mid/tasks/dws_sales.sql",
    ):
        path = configured_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored", encoding="utf-8")

    assert workspace_fingerprint(configured_root, "shop") == before


def test_workspace_entries_are_relative_sorted_and_content_hashed(
    configured_root,
):
    task = configured_root / "warehouses/shop/mid/tasks/dws_sales.sql"
    task.parent.mkdir(parents=True)
    task.write_text("SELECT 1", encoding="utf-8")

    entries = workspace_file_entries(configured_root, "shop")

    assert [entry["path"] for entry in entries] == sorted(
        entry["path"] for entry in entries
    )
    assert {entry["path"] for entry in entries} >= {
        "naming_config.yaml",
        "warehouses/shop/warehouse.yaml",
        "warehouses/shop/mid/tasks/dws_sales.sql",
    }
    assert all(
        entry["content_sha256"].startswith("sha256:") for entry in entries
    )
