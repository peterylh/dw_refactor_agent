import dw_refactor_agent.assessment.scoped_plan as scoped_plan
from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.scoped_plan import (
    build_scoped_assessment_plan,
    changed_types_for_analysis,
)


def _context():
    tables = [
        {"name": "dwd_order", "layer": "DWD", "columns": []},
        {"name": "dws_order_daily", "layer": "DWS", "columns": []},
        {"name": "ads_order_dashboard", "layer": "ADS", "columns": []},
        {"name": "ads_unrelated", "layer": "ADS", "columns": []},
    ]
    return AssessmentContext.from_facts(
        project="shop",
        tables=tables,
        models={
            table["name"]: {"name": table["name"], "layer": table["layer"]}
            for table in tables
        },
        edges=[
            {
                "source": "dwd_order.order_id",
                "target": "dws_order_daily.order_id",
                "source_file": "dws_order_daily.sql",
            },
            {
                "source": "dws_order_daily.order_id",
                "target": "ads_order_dashboard.order_id",
                "source_file": "ads_order_dashboard.sql",
            },
            {
                "source": "ads_unrelated.order_id",
                "target": "dwd_order.order_id",
                "source_file": "bad_dependency.sql",
            },
        ],
    )


def _rename_context():
    return AssessmentContext.from_facts(
        project="shop",
        tables=[
            {"name": "ods_customer", "layer": "ODS", "columns": []},
            {
                "name": "DIM_BASE_CUST_PROFILE_INFO",
                "layer": "DIM",
                "columns": [],
            },
        ],
        edges=[
            {
                "source": "ods_customer.customer_id",
                "target": "DIM_BASE_CUST_PROFILE_INFO.customer_id",
                "source_file": "DIM_BASE_CUST_PROFILE_INFO.sql",
            },
        ],
    )


def test_build_scoped_assessment_plan_uses_current_assets_for_rename():
    change_analysis = {
        "changed_assets": {
            "ddl_tables": ["DIM_BASE_CUST_PROFILE_INFO", "dwd_customer"],
            "task_jobs": ["DIM_BASE_CUST_PROFILE_INFO", "dwd_customer"],
            "model_tables": ["DIM_BASE_CUST_PROFILE_INFO", "dwd_customer"],
            "config_files": [],
        },
        "affected_scope": {
            "direct_tables": ["DIM_BASE_CUST_PROFILE_INFO", "dwd_customer"],
            "downstream_tables": [],
            "anchor_tables": [],
            "assessment_tables": [
                "DIM_BASE_CUST_PROFILE_INFO",
                "dwd_customer",
                "ods_customer",
            ],
            "assessment_tasks": [
                "DIM_BASE_CUST_PROFILE_INFO",
                "dwd_customer",
                "ods_customer",
            ],
            "global_dimensions": [],
        },
        "lineage_diff": {
            "added_edges": [
                {
                    "source": "ods_customer",
                    "target": "DIM_BASE_CUST_PROFILE_INFO",
                }
            ],
            "removed_edges": [
                {"source": "ods_customer", "target": "dwd_customer"}
            ],
            "changed_tables": [
                "DIM_BASE_CUST_PROFILE_INFO",
                "dwd_customer",
                "ods_customer",
            ],
        },
    }

    plan = build_scoped_assessment_plan(
        "shop",
        change_analysis,
        _rename_context(),
    )

    assert plan["base_scope"]["direct_tables"] == [
        "DIM_BASE_CUST_PROFILE_INFO"
    ]
    assert plan["base_scope"]["assessment_tables"] == [
        "DIM_BASE_CUST_PROFILE_INFO",
        "ods_customer",
    ]
    assert plan["base_scope"]["assessment_tasks"] == [
        "DIM_BASE_CUST_PROFILE_INFO",
        "ods_customer",
    ]
    assert "dwd_customer" not in plan["dimensions"]["naming"]["tables"]
    assert "dwd_customer" not in plan["dimensions"]["code_quality"]["tasks"]
    assert {
        "source": "ods_customer",
        "target": "DIM_BASE_CUST_PROFILE_INFO",
    } in plan["dimensions"]["model_design"]["edges"]
    assert {
        "source": "ods_customer",
        "target": "dwd_customer",
    } not in plan["dimensions"]["model_design"]["edges"]


def test_build_scoped_assessment_plan_marks_global_config_dimensions_full():
    change_analysis = {
        "changed_assets": {
            "ddl_tables": [],
            "task_jobs": [],
            "model_tables": [],
            "config_files": [
                "warehouses/shop/naming_config.yaml",
                "warehouses/shop/semantic_subjects.yaml",
            ],
        },
        "affected_scope": {
            "direct_tables": [],
            "downstream_tables": [],
            "anchor_tables": [],
            "assessment_tables": [],
            "assessment_tasks": [],
            "global_dimensions": ["metadata_health", "naming"],
        },
        "lineage_diff": {
            "added_edges": [],
            "removed_edges": [],
            "changed_tables": [],
        },
    }

    plan = build_scoped_assessment_plan("shop", change_analysis, _context())

    assert plan["changed_types"] == [
        "business_semantics",
        "naming_config",
    ]
    assert plan["dimensions"]["naming"]["mode"] == "full"
    assert plan["dimensions"]["metadata_health"]["mode"] == "full"
    assert plan["dimensions"]["code_quality"]["mode"] == "scoped"


def test_changed_types_ignore_root_default_naming_config():
    assert (
        changed_types_for_analysis(
            "shop",
            {
                "changed_assets": {
                    "config_files": ["naming_config.yaml"],
                }
            },
        )
        == set()
    )


def test_changed_types_uses_configured_project_dir_for_business_semantics(
    monkeypatch,
):
    monkeypatch.setitem(
        scoped_plan.config.PROJECT_CONFIG,
        "demo",
        {"dir": "warehouses/custom_demo"},
    )

    assert changed_types_for_analysis(
        "demo",
        {
            "changed_assets": {
                "config_files": [
                    "warehouses/custom_demo/semantic_subjects.yaml"
                ],
            }
        },
    ) == {"business_semantics"}
    changed_types = changed_types_for_analysis(
        "demo",
        {
            "changed_assets": {
                "config_files": ["warehouses/other/semantic_subjects.yaml"],
            }
        },
    )
    assert changed_types == {"config"}


def test_build_scoped_assessment_plan_marks_warehouse_config_full():
    change_analysis = {
        "changed_assets": {
            "ddl_tables": [],
            "task_jobs": [],
            "model_tables": [],
            "config_files": ["warehouses/shop/warehouse.yaml"],
        },
        "affected_scope": {
            "direct_tables": [],
            "downstream_tables": [],
            "anchor_tables": [],
            "assessment_tables": [],
            "assessment_tasks": [],
            "global_dimensions": [
                "asset_completeness",
                "code_quality",
                "depth",
                "metadata_health",
                "model_design",
                "naming",
                "reuse",
            ],
        },
        "lineage_diff": {
            "added_edges": [],
            "removed_edges": [],
            "changed_tables": [],
        },
    }

    plan = build_scoped_assessment_plan("shop", change_analysis, _context())

    assert plan["changed_types"] == ["warehouse_config"]
    assert {
        name: dimension["mode"]
        for name, dimension in plan["dimensions"].items()
    } == {
        "reuse": "full",
        "depth": "full",
        "model_design": "full",
        "naming": "full",
        "asset_completeness": "full",
        "metadata_health": "full",
        "code_quality": "full",
    }
