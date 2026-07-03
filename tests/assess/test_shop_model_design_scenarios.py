import copy

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.assessment.rules.dimensions.model_design import (
    score_model_design_health,
)
from dw_refactor_agent.assessment.scoring.config import MODEL_DESIGN_RULES
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,
    get_business_domain_config,
    iter_project_task_files,
    load_model_metadata,
    project_asset_dirs,
    task_source_file,
)
from dw_refactor_agent.lineage.lineage_extractor import (
    build_lineage_output,
    build_schema_from_ddl,
    configure_project,
    extract_lineage_from_sql,
)
from dw_refactor_agent.lineage.sql_task_facts import extract_task_table_facts


def _build_shop_lineage_from_sources():
    configure_project("shop")
    schema = build_schema_from_ddl(project_asset_dirs("shop", "ddl"))

    all_lineage = []
    transient_tables = []
    task_files = iter_project_task_files("shop")

    for task_path in task_files:
        source_file = task_source_file("shop", task_path)
        sql_text = task_path.read_text(encoding="utf-8")
        task_facts = extract_task_table_facts(sql_text, source_file)
        transient_tables.extend(task_facts["transient_tables"])
        all_lineage.extend(
            extract_lineage_from_sql(sql_text, source_file, schema)
        )

    return build_lineage_output(
        all_lineage,
        schema,
        transient_tables=transient_tables,
    )


def _with_model_rule_scenarios(lineage_data: dict, model_metadata: dict):
    """Keep model-design rule fixtures independent from refreshed models."""
    lineage_data = copy.deepcopy(lineage_data)
    model_metadata = copy.deepcopy(model_metadata)
    overrides = {
        "dim_store_metric_snapshot": {
            "layer": "DIM",
            "table_type": "dimension",
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
            "atomic_metrics": ["store_order_count"],
        },
        "dwd_order_summary_bad": {
            "layer": "DWD",
            "table_type": "fact",
            "business_process": "ORDER_TRANSACTION",
            "atomic_metrics": [
                {
                    "name": "order_count",
                    "business_process": "ORDER_TRANSACTION",
                },
                {
                    "name": "refund_count",
                    "business_process": "REFUND_TRANSACTION",
                },
            ],
        },
        "dws_category_sales_monthly": {
            "layer": "DWS",
            "table_type": "fact",
            "grain": {},
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "base_metric": "ghost_amount",
                    "aggregation": "SUM",
                }
            ],
        },
        "dws_order_passthrough_daily": {
            "layer": "DWS",
            "table_type": "fact",
            "grain": {},
        },
    }

    for table_name, override in overrides.items():
        metadata = dict(model_metadata.get(table_name) or {})
        metadata.update(override)
        model_metadata[table_name] = metadata

    return lineage_data, model_metadata


def test_shop_model_design_has_detectable_scenario_for_each_model_rule():
    project_dir = PROJECT_ROOT / PROJECT_CONFIG["shop"]["dir"]
    lineage_data = _build_shop_lineage_from_sources()
    model_metadata = load_model_metadata("shop")
    lineage_data, model_metadata = _with_model_rule_scenarios(
        lineage_data,
        model_metadata,
    )
    asset_catalog = build_asset_catalog(
        lineage_data["tables"],
        model_metadata,
        project_dir,
        edges=lineage_data["edges"],
        indirect_edges=lineage_data.get("indirect_edges", []),
    )

    context = AssessmentContext.from_facts(
        project="shop",
        tables=lineage_data["tables"],
        edges=lineage_data["edges"],
        indirect_edges=lineage_data.get("indirect_edges", []),
        models=model_metadata,
        business_domain_config=get_business_domain_config("shop"),
        assets=asset_catalog,
    )
    result = score_model_design_health(context)

    rule_ids = {issue["rule_id"] for issue in result["issues"]}
    expected_rule_ids = {
        rule_id
        for rule_id in MODEL_DESIGN_RULES
        if rule_id.startswith("MODEL_")
    }
    assert expected_rule_ids <= rule_ids
