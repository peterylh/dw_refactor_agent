from refact.change_analysis import (
    build_change_analysis,
    classify_changed_assets,
)


def test_classify_changed_assets_groups_project_files():
    result = classify_changed_assets(
        [
            "shop/ddl/dwd_order.sql",
            "shop/mid/ddl/dwd_inventory.sql",
            "shop/ads/ddl/ads_order.sql",
            "shop/tasks/legacy_job.sql",
            "shop/mid/tasks/dws_order.sql",
            "shop/mid/tasks/full_refresh/dwd_order_full_refresh.sql",
            "shop/ads/tasks/ads_order.sql",
            "shop/models/dwd_order.yaml",
            "shop/mid/models/dwd_inventory.yaml",
            "shop/ads/models/ads_order.yaml",
            "shop/business_semantics.yaml",
            "naming_config.yaml",
            "README.md",
        ],
        "shop",
    )

    assert result == {
        "ddl_tables": ["ads_order", "dwd_inventory"],
        "task_jobs": ["ads_order", "dwd_order", "dws_order"],
        "model_tables": ["ads_order", "dwd_inventory"],
        "config_files": ["naming_config.yaml", "shop/business_semantics.yaml"],
    }


def test_build_change_analysis_uses_baseline_and_current_downstream():
    baseline = {
        "tables": [],
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_order.order_id"},
                "target": {"type": "column", "id": "dws_order.order_id"},
                "source_file": "dws_order.sql",
            }
        ],
    }
    current = {
        "tables": [],
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_order.order_id"},
                "target": {"type": "column", "id": "ads_order.order_id"},
                "source_file": "ads_order.sql",
            }
        ],
    }

    result = build_change_analysis(
        "shop",
        baseline,
        current,
        ["shop/mid/ddl/dwd_order.sql"],
    )

    assert result["affected_scope"]["direct_tables"] == ["dwd_order"]
    assert result["affected_scope"]["downstream_tables"] == [
        "ads_order",
        "dws_order",
    ]
    assert result["affected_scope"]["anchor_tables"] == [
        "ads_order",
        "dws_order",
    ]
    assert result["lineage_diff"]["added_edges"] == [
        {"source": "dwd_order", "target": "ads_order"}
    ]
    assert result["lineage_diff"]["removed_edges"] == [
        {"source": "dwd_order", "target": "dws_order"}
    ]
