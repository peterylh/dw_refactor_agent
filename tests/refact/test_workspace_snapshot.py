import pytest

import dw_refactor_agent.refactor.workspace_snapshot as snapshot_module
from dw_refactor_agent.refactor.workspace_snapshot import (
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
        "warehouses/shop/mid/tasks/dws_sales.yaml",
        "warehouses/shop/mid/tasks/full_refresh/dws_sales.sql",
        "warehouses/shop/mid/tasks/full_refresh/dws_sales.yml",
        "warehouses/shop/ads/tasks/ads_sales.sql",
        "warehouses/shop/ads/tasks/ads_sales.yaml",
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


def test_renderer_semantics_change_changes_workspace_fingerprint(
    configured_root, monkeypatch
):
    before = workspace_fingerprint(configured_root, "shop")
    monkeypatch.setattr(
        snapshot_module,
        "renderer_semantics_digest",
        lambda: "sha256:" + "f" * 64,
    )

    assert workspace_fingerprint(configured_root, "shop") != before
