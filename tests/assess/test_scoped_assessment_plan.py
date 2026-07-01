from assess.assessment_context import AssessmentContext
from assess.scoped_plan import build_scoped_assessment_plan


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


def test_build_scoped_assessment_plan_scopes_regular_table_change():
    change_analysis = {
        "changed_assets": {
            "ddl_tables": ["dwd_order"],
            "task_jobs": [],
            "model_tables": [],
            "config_files": [],
        },
        "affected_scope": {
            "direct_tables": ["dwd_order"],
            "downstream_tables": ["dws_order_daily", "ads_order_dashboard"],
            "anchor_tables": ["dws_order_daily"],
            "assessment_tables": [
                "dwd_order",
                "dws_order_daily",
                "ads_order_dashboard",
            ],
            "assessment_tasks": [
                "dwd_order",
                "dws_order_daily",
                "ads_order_dashboard",
            ],
            "global_dimensions": [],
        },
        "lineage_diff": {
            "added_edges": [
                {"source": "ads_unrelated", "target": "dwd_order"}
            ],
            "removed_edges": [],
            "changed_tables": ["ads_unrelated", "dwd_order"],
        },
    }

    plan = build_scoped_assessment_plan("shop", change_analysis, _context())

    assert plan["mode"] == "scoped"
    assert plan["changed_types"] == ["ddl"]
    assert plan["dimensions"]["code_quality"]["tasks"] == [
        "ads_order_dashboard",
        "dwd_order",
        "dws_order_daily",
    ]
    assert plan["dimensions"]["metadata_health"]["tables"] == [
        "ads_order_dashboard",
        "dwd_order",
        "dws_order_daily",
    ]
    assert plan["dimensions"]["depth"]["tables"] == ["ads_order_dashboard"]
    assert {"source": "ads_unrelated", "target": "dwd_order"} in plan[
        "dimensions"
    ]["model_design"]["edges"]


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
                "naming_config.yaml",
                "shop/business_semantics.yaml",
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
