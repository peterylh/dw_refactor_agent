import subprocess

import pytest

import dw_refactor_agent.refactor.change_analysis as change_analysis_module
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
            "warehouses/shop/mid/tasks/dws_order.yaml",
            "warehouses/shop/mid/tasks/full_refresh/dwd_order_full_refresh.sql",
            "warehouses/shop/mid/tasks/full_refresh/dwd_order_full_refresh.yml",
            "warehouses/shop/ads/tasks/ads_order.sql",
            "warehouses/shop/ads/tasks/ads_order.yaml",
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


def test_task_contract_change_maps_to_same_job_and_downstream_scope():
    lineage = {
        "format_version": 2,
        "tables": [
            {
                "full_name": "internal.shop_dm.dws_order",
                "dataset_type": "managed",
            },
            {
                "full_name": "internal.shop_dm.ads_order",
                "dataset_type": "managed",
            },
        ],
        "jobs": [
            {
                "name": "dws_order",
                "source_file": "mid/tasks/dws_order.sql",
                "inputs": [],
                "outputs": ["internal.shop_dm.dws_order"],
            }
        ],
        "edges": [
            {
                "source": {
                    "type": "column",
                    "id": "internal.shop_dm.dws_order.id",
                },
                "target": {
                    "type": "column",
                    "id": "internal.shop_dm.ads_order.id",
                },
            }
        ],
    }

    result = build_change_analysis(
        "shop",
        lineage,
        lineage,
        ["warehouses/shop/mid/tasks/dws_order.yaml"],
    )

    assert result["changed_assets"]["task_jobs"] == ["dws_order"]
    assert result["affected_scope"]["direct_tables"] == [
        "internal.shop_dm.dws_order"
    ]
    assert result["affected_scope"]["downstream_tables"] == [
        "internal.shop_dm.ads_order"
    ]


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


def _template_config_lineage():
    return {
        "format_version": 2,
        "tables": [
            {
                "full_name": "internal.demo.dws_order",
                "dataset_type": "managed",
            }
        ],
        "jobs": [
            {
                "name": "dws_order",
                "source_file": "dws_order.sql",
                "inputs": ["internal.source.orders"],
                "outputs": ["internal.demo.dws_order"],
            }
        ],
        "edges": [],
    }


def _init_template_config_repo(
    tmp_path,
    monkeypatch,
    *,
    task_relative_dir="mid/tasks",
):
    project_dir = tmp_path / "warehouses" / "demo"
    task_dir = project_dir / task_relative_dir
    task_dir.mkdir(parents=True)
    warehouse_path = project_dir / "warehouse.yaml"
    warehouse_path.write_text(
        """\
name: demo
catalog: internal
database: demo
description: baseline
task_templates:
  version: 1
  analysis:
    project:
      source_schema: internal.source
  bindings:
    prod:
      project:
        source_schema: internal.source
""",
        encoding="utf-8",
    )
    (task_dir / "dws_order.sql").write_text(
        "INSERT INTO internal.demo.dws_order "
        "SELECT order_id FROM ${source_schema}.orders;\n",
        encoding="utf-8",
    )
    (task_dir / "dws_order.yaml").write_text(
        """\
version: 1
strict: true
project_params:
  - prop: source_schema
    type: QUALIFIED_IDENTIFIER
    source: project.source_schema
    required: true
""",
        encoding="utf-8",
    )
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
    monkeypatch.setitem(
        change_analysis_module.PROJECT_CONFIG,
        "demo",
        {
            "dir": "warehouses/demo",
            "catalog": "internal",
            "db": "demo",
        },
    )
    return warehouse_path


@pytest.mark.parametrize(
    ("task_relative_dir", "old", "new"),
    [
        (
            "mid/tasks",
            "        source_schema: internal.source\n",
            "        source_schema: internal.changed_source\n",
        ),
        (
            "mid/tasks",
            "      source_schema: internal.source\n",
            "      source_schema: internal.analysis_source\n",
        ),
        (
            "ods/tasks/internal/source",
            "        source_schema: internal.source\n",
            "        source_schema: internal.changed_source\n",
        ),
    ],
)
def test_template_binding_change_selects_affected_job(
    tmp_path, monkeypatch, task_relative_dir, old, new
):
    warehouse_path = _init_template_config_repo(
        tmp_path,
        monkeypatch,
        task_relative_dir=task_relative_dir,
    )
    warehouse_path.write_text(
        warehouse_path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )
    lineage = _template_config_lineage()

    result = build_change_analysis(
        "demo",
        lineage,
        lineage,
        ["warehouses/demo/warehouse.yaml"],
        repo_root=tmp_path,
        base_ref="HEAD",
    )

    assert result["changed_assets"]["task_jobs"] == ["dws_order"]
    assert result["affected_scope"]["direct_tables"] == [
        "internal.demo.dws_order"
    ]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "        source_schema: internal.source\n",
            "        source_schema: internal.source\n"
            "        unused_schema: internal.unused\n",
        ),
        ("description: baseline", "description: unrelated change"),
    ],
)
def test_irrelevant_warehouse_change_does_not_select_template_jobs(
    tmp_path, monkeypatch, old, new
):
    warehouse_path = _init_template_config_repo(tmp_path, monkeypatch)
    warehouse_path.write_text(
        warehouse_path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )
    lineage = _template_config_lineage()

    result = build_change_analysis(
        "demo",
        lineage,
        lineage,
        ["warehouses/demo/warehouse.yaml"],
        repo_root=tmp_path,
        base_ref="HEAD",
    )

    assert result["changed_assets"]["task_jobs"] == []
    assert result["affected_scope"]["direct_tables"] == []


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
