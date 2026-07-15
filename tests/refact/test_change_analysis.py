import subprocess

import pytest

from dw_refactor_agent.refactor.change_analysis import (
    build_change_analysis,
    changed_files_since_head,
    classify_changed_assets,
)
from tests.case_matrix import case_matrix


def test_classify_changed_assets_groups_project_files():
    result = classify_changed_assets(
        [
            "warehouses/shop/ddl/dwd_order.sql",
            "warehouses/shop/mid/ddl/dwd_inventory.sql",
            "warehouses/shop/ads/ddl/ads_order.sql",
            "warehouses/shop/legacy_tasks/legacy_job.sql",
            "warehouses/shop/mid/tasks/dws_order.sql",
            "warehouses/shop/mid/tasks/full_refresh/dwd_order_full_refresh.sql",
            "warehouses/shop/ads/tasks/ads_order.sql",
            "warehouses/shop/models/dwd_order.yaml",
            "warehouses/shop/mid/models/dwd_inventory.yaml",
            "warehouses/shop/ads/models/ads_order.yaml",
            "warehouses/shop/warehouse.yaml",
            "warehouses/shop/business_processes.yaml",
            "warehouses/shop/naming_config.yaml",
            "naming_config.yaml",
            "README.md",
        ],
        "shop",
    )

    assert result == {
        "ddl_tables": ["ads_order", "dwd_inventory"],
        "task_jobs": ["ads_order", "dwd_order", "dws_order"],
        "model_tables": ["ads_order", "dwd_inventory"],
        "config_files": [
            "warehouses/shop/business_processes.yaml",
            "warehouses/shop/naming_config.yaml",
            "warehouses/shop/warehouse.yaml",
        ],
    }


def test_build_change_analysis_marks_warehouse_config_as_global():
    result = build_change_analysis(
        "shop",
        {"tables": [], "edges": []},
        {"tables": [], "edges": []},
        ["warehouses/shop/warehouse.yaml"],
    )

    assert result["changed_assets"]["config_files"] == [
        "warehouses/shop/warehouse.yaml"
    ]
    assert result["affected_scope"]["global_dimensions"] == [
        "asset_completeness",
        "code_quality",
        "depth",
        "metadata_health",
        "model_design",
        "naming",
        "reuse",
    ]


def test_changed_files_since_head_filters_to_project_warehouse(tmp_path):
    (tmp_path / "warehouses" / "shop").mkdir(parents=True)
    (tmp_path / "warehouses" / "finance_analytics").mkdir(parents=True)
    tracked_files = {
        "warehouses/shop/warehouse.yaml": "name: shop\n",
        "warehouses/shop/naming_config.yaml": "version: 1\n",
        "warehouses/finance_analytics/warehouse.yaml": (
            "name: finance_analytics\n"
        ),
        "naming_config.yaml": "version: 1\n",
    }
    for file_name, content in tracked_files.items():
        path = tmp_path / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    (tmp_path / "warehouses/shop/warehouse.yaml").write_text(
        "name: shop\nqa_database: shop_dm_qa\n",
        encoding="utf-8",
    )
    (tmp_path / "warehouses/shop/naming_config.yaml").write_text(
        "version: 2\n",
        encoding="utf-8",
    )
    (tmp_path / "warehouses/shop/business_processes.yaml").write_text(
        "business_processes: []\n",
        encoding="utf-8",
    )
    (tmp_path / "warehouses/finance_analytics/warehouse.yaml").write_text(
        "name: finance_analytics\nqa_database: finance_analytics_dm_qa\n",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "version: 2\n",
        encoding="utf-8",
    )

    assert changed_files_since_head(
        tmp_path,
        "HEAD",
        "warehouses/shop",
    ) == [
        "warehouses/shop/business_processes.yaml",
        "warehouses/shop/naming_config.yaml",
        "warehouses/shop/warehouse.yaml",
    ]


@case_matrix(
    "tables, outputs",
    [
        (
            [
                {
                    "full_name": "internal.shop_dm.stage_sales",
                    "dataset_type": "process",
                }
            ],
            ["internal.shop_dm.stage_sales"],
        ),
        (
            [
                {
                    "full_name": "internal.shop_dm.dwd_order",
                    "dataset_type": "managed",
                },
                {
                    "full_name": "internal.shop_dm.dwd_order_audit",
                    "dataset_type": "managed",
                },
            ],
            [
                "internal.shop_dm.dwd_order",
                "internal.shop_dm.dwd_order_audit",
            ],
        ),
    ],
)
def test_changed_job_requires_one_managed_output_per_lineage_snapshot(
    tables, outputs
):
    lineage = {
        "format_version": 2,
        "tables": tables,
        "jobs": [
            {
                "name": "Prepare_Sales",
                "source_file": "mid/tasks/prepare_sales.sql",
                "inputs": [],
                "outputs": outputs,
            }
        ],
        "edges": [],
        "diagnostics": [],
    }

    with pytest.raises(ValueError, match="changed Job.*managed output"):
        build_change_analysis(
            "shop",
            lineage,
            lineage,
            ["warehouses/shop/mid/tasks/prepare_sales.sql"],
        )
