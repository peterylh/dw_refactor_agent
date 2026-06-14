from config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,
    get_business_domain_config,
    load_model_metadata,
)
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.scoring.config import MODEL_DESIGN_RULES
from assess.scoring.model_design import score_model_design_health
from lineage.lineage_extractor import (
    build_lineage_output,
    build_schema_from_ddl,
    configure_project,
    extract_lineage_from_sql,
)
from lineage.sql_task_facts import extract_task_table_facts


def _build_shop_lineage_from_sources():
    configure_project("shop")
    project_dir = PROJECT_ROOT / PROJECT_CONFIG["shop"]["dir"]
    tasks_dir = project_dir / "tasks"
    schema = build_schema_from_ddl(project_dir / "ddl")

    all_lineage = []
    transient_tables = []
    task_files = sorted(tasks_dir.glob("*.sql"))
    full_refresh_dir = tasks_dir / "full_refresh"
    if full_refresh_dir.exists():
        task_files.extend(sorted(full_refresh_dir.glob("*.sql")))

    for task_path in task_files:
        source_file = task_path.relative_to(tasks_dir).as_posix()
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


def test_shop_model_design_has_detectable_scenario_for_each_model_rule():
    project_dir = PROJECT_ROOT / PROJECT_CONFIG["shop"]["dir"]
    lineage_data = _build_shop_lineage_from_sources()
    model_metadata = load_model_metadata("shop")
    asset_catalog = build_asset_catalog(
        lineage_data["tables"],
        model_metadata,
        project_dir,
        edges=lineage_data["edges"],
        indirect_edges=lineage_data.get("indirect_edges", []),
    )

    result = score_model_design_health(
        lineage_data["tables"],
        lineage_data["edges"],
        lineage_data.get("indirect_edges", []),
        model_metadata=model_metadata,
        business_domain_config=get_business_domain_config("shop"),
        asset_catalog=asset_catalog,
    )

    rule_ids = {issue["rule_id"] for issue in result["issues"]}
    expected_rule_ids = {
        rule_id for rule_id in MODEL_DESIGN_RULES
        if rule_id.startswith("MODEL_")
    }
    assert expected_rule_ids <= rule_ids
