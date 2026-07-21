from types import SimpleNamespace

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.catalog_proposals import (
    build_catalog_proposal_report,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    run_catalog_discovery,
    run_catalog_metadata_write,
    run_generate_model_metadata,
    run_metadata_write,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.assessment.semantic_models import (
    CanonicalSemanticPayload,
)
from tests.assess.model_metadata_writer_test_support import (
    _catalog_payload,
    _configure_project_root,
    _customer_subject,
    _order_detail_process,
    _setup_catalog_discovery_model,
    _write_catalog_project,
    _write_split_catalog,
)


def _write_taxonomy_only(project_dir, project):
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {"id": "04", "code": "TRAN", "name": "交易域"}
                ],
                "business_areas": [
                    {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _install_generate_catalog_fake_inspector(
    monkeypatch,
    writer_module,
    *,
    table_names,
    result_factory,
):
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables(*table_names),
    )

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                result = result_factory(ctx)
                if result is not None:
                    results.append(result)
            return results

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)


def _generate_catalog_fact_result(ctx, *, validation=None):
    return TableInspectResult(
        table_name=ctx.table_name,
        declared_layer=ctx.layer,
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        validation=validation or {},
        inferred_data_domain="04",
        inferred_business_area="SHOP",
        columns={
            "atomic_metrics": [
                {
                    "name": "subtotal",
                    "business_process": "ORDER_TRANSACTION",
                }
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )


def _generate_catalog_dimension_result(ctx):
    return TableInspectResult(
        table_name=ctx.table_name,
        declared_layer=ctx.layer,
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="04",
        inferred_business_area="SHOP",
        entities=[
            {
                "code": "CUSTOMER",
                "type": "primary",
                "name": "客户",
                "key_columns": ["customer_id"],
            }
        ],
    )


def _generate_catalog_result_for_context(ctx):
    if ctx.table_name == "dwd_order_detail":
        return _generate_catalog_fact_result(ctx)
    if ctx.table_name == "dim_customer":
        return _generate_catalog_dimension_result(ctx)
    return None


def test_catalog_proposals_dedupe_sources_and_report_name_conflicts():
    results = [
        _generate_catalog_dimension_result(
            SimpleNamespace(table_name=table_name, layer="DIM")
        )
        for table_name in ("dim_customer", "DIM_CUSTOMER_ALIAS")
    ]
    results[0].entities[0].update(code="customer", name="客户")
    results[1].entities[0].update(code="customer", name="Customer")

    report = build_catalog_proposal_report(
        results,
        confirmed_catalog={"semantic_subjects": []},
    )

    assert report["catalog_proposal_count"] == 1
    proposal = report["catalog_proposals"][0]
    assert proposal["code"] == "CUSTOMER"
    assert proposal["display_name"] is None
    assert proposal["display_name_candidates"] == ["Customer", "客户"]
    assert proposal["source_tables"] == [
        "dim_customer",
        "DIM_CUSTOMER_ALIAS",
    ]
    assert len(proposal["evidence"]) == 2
    assert report["catalog_proposal_conflicts"] == [
        {
            "kind": "semantic_subject",
            "code": "CUSTOMER",
            "display_name_candidates": ["Customer", "客户"],
            "source_tables": ["dim_customer", "DIM_CUSTOMER_ALIAS"],
            "status": "conflict",
        }
    ]


@pytest.mark.parametrize("dry_run", [True, False], ids=("dry-run", "write"))
def test_run_generate_model_metadata_only_proposes_new_catalog_codes(
    tmp_path, monkeypatch, dry_run
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = f"generate_llm_catalog_{dry_run}"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=_generate_catalog_result_for_context,
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=dry_run,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_change_count"] == 0
    assert result["catalog_update"] is None
    assert result["catalog_proposal_count"] == 2
    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["published"] is False
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []
    assert not (project_dir / "mid/models/dwd_order_detail.yaml").exists()
    assert not (project_dir / "mid/models/dim_customer.yaml").exists()
    if not dry_run:
        checkpoint_manifest = yaml.safe_load(
            (project_dir / "mid_checkpoints/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        audit = checkpoint_manifest["catalog_proposal_audit"]
        assert audit["proposal_count"] == 2
        assert audit["proposals"] == result["catalog_proposals"]


def test_run_generate_model_metadata_preserves_governed_catalog_code_case(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_catalog_code_case"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            processes=[
                {
                    "code": "order_transaction",
                    "name": "订单交易",
                    "data_domain": "04",
                    "business_area": "SHOP",
                }
            ]
        ),
        ddl_tables=["dwd_order_detail"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail"],
        result_factory=lambda ctx: _generate_catalog_fact_result(ctx),
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    catalog = config.load_business_semantics_catalog(project)
    model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result["publication"]["status"] == "published"
    assert result["catalog_change_count"] == 0
    assert result["catalog_proposals"] == []
    assert catalog["business_processes"][0]["code"] == "order_transaction"
    assert model["business_process"] == "order_transaction"


def test_run_generate_model_metadata_update_catalog_false_keeps_proposals(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_disabled"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail"],
        result_factory=lambda ctx: _generate_catalog_fact_result(ctx),
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
        update_catalog=False,
    )

    assert result["catalog_initialized"] is False
    assert result["catalog_proposal_count"] == 1
    assert result["catalog_proposals"][0]["code"] == "ORDER_TRANSACTION"
    checkpoint = yaml.safe_load(
        (project_dir / "mid_checkpoints/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["catalog_proposal_audit"]["proposal_count"] == 1
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()


def test_run_generate_model_metadata_llm_catalog_merge_skips_blocked_results(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_llm_catalog_blocked"
    _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
    )

    def result_factory(ctx):
        if ctx.table_name == "dwd_order_detail":
            return _generate_catalog_fact_result(
                ctx,
                validation={"unknown_columns": ["ghost_metric"]},
            )
        if ctx.table_name == "dim_customer":
            return _generate_catalog_dimension_result(ctx)
        return None

    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=result_factory,
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_proposal_count"] == 1
    assert result["catalog_proposals"][0]["code"] == "CUSTOMER"
    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["published"] is False
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def _refresh_catalog_models(*table_names):
    return {
        table_name: {
            "version": 2,
            "name": table_name,
            "layer": "DIM" if table_name.startswith("dim_") else "DWD",
            "table_type": (
                "dimension" if table_name.startswith("dim_") else "fact"
            ),
        }
        for table_name in table_names
    }


def test_run_metadata_write_llm_dry_run_plans_proposals_and_skeleton(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "refresh_llm_catalog_dry_run"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail", "dim_customer"],
        models=_refresh_catalog_models("dwd_order_detail", "dim_customer"),
    )
    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dim_customer"],
        result_factory=_generate_catalog_result_for_context,
    )

    result = run_metadata_write(
        project,
        api_key="test",
        dry_run=True,
    )
    proposed_codes = {
        proposal["code"] for proposal in result["catalog_proposals"]
    }

    assert result["catalog_initialized"] is True
    assert result["planned_catalog_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["catalog_proposal_count"] == 2
    assert proposed_codes == {"ORDER_TRANSACTION", "CUSTOMER"}
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()

    disabled = run_metadata_write(
        project,
        api_key="test",
        dry_run=False,
        update_catalog=False,
    )

    assert disabled["catalog_initialized"] is False
    assert disabled["catalog_proposal_count"] == 2
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()

    frozen = run_metadata_write(
        project,
        api_key="test",
        dry_run=True,
        business_semantics_catalog=_catalog_payload(
            processes=[_order_detail_process("ORDER_TRANSACTION")],
            subjects=[_customer_subject()],
        ),
    )

    assert frozen["catalog_initialized"] is False
    assert frozen["catalog_proposals"] == []


def test_run_metadata_write_llm_reports_proposals_without_catalog_mutation(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "refresh_llm_catalog_write"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dwd_event_detail", "dim_customer"],
        models=_refresh_catalog_models(
            "dwd_order_detail",
            "dwd_event_detail",
            "dim_customer",
        ),
    )

    def result_factory(ctx):
        if ctx.table_name == "dwd_order_detail":
            result = _generate_catalog_fact_result(ctx)
            result.inferred_data_domain = "LLM_DOMAIN"
            result.inferred_business_area = "LLM_AREA"
            return result
        if ctx.table_name == "dwd_event_detail":
            result = _generate_catalog_fact_result(
                ctx,
                validation={"unknown_columns": ["ghost_metric"]},
            )
            result.columns["atomic_metrics"][0]["business_process"] = (
                "EVENT_COMPLETION"
            )
            return result
        if ctx.table_name == "dim_customer":
            return _generate_catalog_dimension_result(ctx)
        return None

    _install_generate_catalog_fake_inspector(
        monkeypatch,
        writer_module,
        table_names=["dwd_order_detail", "dwd_event_detail", "dim_customer"],
        result_factory=result_factory,
    )

    result = run_metadata_write(
        project,
        api_key="test",
        dry_run=False,
    )
    taxonomy = yaml.safe_load(
        (project_dir / "business_taxonomy.yaml").read_text(encoding="utf-8")
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog_proposal_count"] == 2
    assert {item["code"] for item in result["catalog_proposals"]} == {
        "ORDER_TRANSACTION",
        "CUSTOMER",
    }
    assert taxonomy["data_domains"] == [
        {"id": "04", "code": "TRAN", "name": "交易域"}
    ]
    assert taxonomy["business_areas"] == [
        {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
    ]
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def _write_single_writer_project(
    tmp_path,
    monkeypatch,
    project,
    *,
    mid_tables=("dwd_order_detail",),
    include_ods_ads=False,
    existing_models=None,
    catalog=None,
):
    project_dir = tmp_path / project
    mid_ddl_dir = project_dir / "mid" / "ddl"
    mid_task_dir = project_dir / "mid" / "tasks"
    mid_ddl_dir.mkdir(parents=True, exist_ok=True)
    mid_task_dir.mkdir(parents=True, exist_ok=True)
    for table_name in mid_tables:
        (mid_ddl_dir / f"{table_name}.sql").write_text(
            f"CREATE TABLE {table_name} (id BIGINT);\n",
            encoding="utf-8",
        )
        (mid_task_dir / f"{table_name}.sql").write_text(
            f"TRUNCATE TABLE {table_name};\n"
            f"INSERT INTO {table_name} SELECT 1;\n",
            encoding="utf-8",
        )
    if include_ods_ads:
        ods_ddl_dir = (
            project_dir / "ods" / "ddl" / "internal" / "single_writer_dm"
        )
        ods_ddl_dir.mkdir(parents=True, exist_ok=True)
        (ods_ddl_dir / "ods_customer.sql").write_text(
            "CREATE TABLE ods_customer (id BIGINT);\n",
            encoding="utf-8",
        )
        ads_ddl_dir = project_dir / "ads" / "ddl"
        ads_ddl_dir.mkdir(parents=True, exist_ok=True)
        (ads_ddl_dir / "ads_sales_dashboard.sql").write_text(
            "CREATE TABLE ads_sales_dashboard (id BIGINT);\n",
            encoding="utf-8",
        )
        ads_task_dir = project_dir / "ads" / "tasks"
        ads_task_dir.mkdir(parents=True, exist_ok=True)
        (ads_task_dir / "ads_sales_dashboard.sql").write_text(
            "TRUNCATE TABLE ads_sales_dashboard;\n"
            "INSERT INTO ads_sales_dashboard SELECT 1;\n",
            encoding="utf-8",
        )
    for table_name, payload in (existing_models or {}).items():
        model_dir = project_dir / "mid" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / f"{table_name}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    _write_split_catalog(
        project_dir,
        project,
        catalog if catalog is not None else _catalog_payload(),
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "single_writer_dm",
            "naming_config": "naming_config.yaml",
        },
    )
    return project_dir


def _lineage_for_tables(*table_names):
    return {
        "tables": [
            {
                "name": table_name,
                "full_name": f"demo.{table_name}",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            for table_name in table_names
        ],
        "edges": [],
        "indirect_edges": [],
    }


@pytest.mark.parametrize(
    (
        "project",
        "existing_contract",
        "inspection",
        "expected_reason",
    ),
    [
        (
            "generate_single_writer_blocked",
            ("DWS", "fact"),
            ("OTHER", "dimension", {"unknown_columns": ["ghost_id"]}, 0.2),
            "validation_blocked",
        ),
        (
            "generate_single_writer_partial_block",
            ("DWD", "other"),
            (
                "DWS",
                "fact",
                {"invalid_base_metrics": ["sale_amount:subtotal"]},
                0.95,
            ),
            "validation_blocked_contract_change",
        ),
    ],
    ids=["invalid-columns", "invalid-metrics"],
)
def test_generate_single_writer_preserves_base_contract_when_llm_blocked(
    tmp_path,
    monkeypatch,
    project,
    existing_contract,
    inspection,
    expected_reason,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    existing_layer, existing_table_type = existing_contract
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        existing_models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": existing_layer,
                "table_type": existing_table_type,
            }
        },
    )
    inferred_layer, table_type, validation, confidence = inspection

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer=inferred_layer,
                    table_type=table_type,
                    validation=validation,
                    confidence=confidence,
                    reasoning_steps=[],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dwd_order_detail"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    saved = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result["llm_result"]["blocked_table_count"] == 1
    assert result["llm_result"]["skipped_model_updates"][0]["reason"] == (
        expected_reason
    )
    assert result["publication"]["status"] == "blocked"
    assert result["deleted_model_files"] == []
    assert saved["layer"] == existing_layer
    assert saved["table_type"] == existing_table_type
    assert "atomic_metrics" not in saved


def test_generate_single_writer_pass_keeps_ods_ads_base_models(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_boundaries"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        mid_tables=("dwd_order_detail",),
        include_ods_ads=True,
        catalog=_catalog_payload(processes=[{"code": "ORDER_TRANSACTION"}]),
    )
    seen_contexts = []

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            seen_contexts.extend(contexts)
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    columns={
                        "atomic_metrics": [
                            {
                                "name": "id",
                                "business_process": "ORDER_TRANSACTION",
                            }
                        ],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables(
            "ods_customer",
            "dwd_order_detail",
            "ads_sales_dashboard",
        ),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )

    assert {ctx.table_name for ctx in seen_contexts} == {"dwd_order_detail"}
    assert result["generated_model_count"] == 3
    assert (
        project_dir
        / "ods"
        / "models"
        / "internal"
        / "single_writer_dm"
        / "ods_customer.yaml"
    ).exists()
    assert (
        project_dir / "ads" / "models" / "ads_sales_dashboard.yaml"
    ).exists()


def test_generate_single_writer_pass_deletes_then_writes_final_models(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_final"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        existing_models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
        catalog=_catalog_payload(subjects=[{"code": "ORDER_DETAIL"}]),
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="dimension",
                    dimension_role="BASE",
                    confidence=0.9,
                    reasoning_steps=[],
                    entities=[
                        {
                            "code": "ORDER_DETAIL",
                            "type": "primary",
                            "key_columns": ["id"],
                        }
                    ],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dwd_order_detail"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert str(model_path) in result["deleted_model_files"]
    assert saved["layer"] == "DIM"
    assert saved["table_type"] == "dimension"
    assert saved["dimension_role"] == "BASE"
    assert result["model_updates"][0]["updated"] is True


def test_generate_single_writer_pass_reports_final_metadata_changes_for_llm_refinement(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_single_writer_final_metadata_report"
    project_dir = _write_single_writer_project(
        tmp_path,
        monkeypatch,
        project,
        mid_tables=("dws_order_summary",),
        existing_models={
            "dws_order_summary": {
                "version": 2,
                "name": "dws_order_summary",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
        catalog=_catalog_payload(processes=[{"code": "ORDER_TRANSACTION"}]),
    )
    model_path = project_dir / "mid" / "models" / "dws_order_summary.yaml"

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWS",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    columns={
                        "atomic_metrics": [
                            {
                                "name": "order_count",
                                "business_process": "ORDER_TRANSACTION",
                            }
                        ],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: _lineage_for_tables("dws_order_summary"),
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )
    llm_update = result["llm_result"]["model_updates"][0]
    update = result["model_updates"][0]
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["inspection_result"] == result["llm_result"]
    assert "model_metadata" not in llm_update
    assert llm_update["metadata_changed"] is False
    assert llm_update["metric_changed"] is True
    assert update["source"] == "llm_refinement"
    assert update["metadata_changed"] is True
    assert update["metric_changed"] is True
    assert update["metric_count"] == 1
    assert update["new_metric_count"] == 1
    assert update["removed_metric_count"] == 0
    assert update["grain_changed"] is False
    assert update["updated"] is True
    assert saved["layer"] == "DWS"
    assert saved["table_type"] == "fact"
    assert saved["atomic_metrics"] == ["order_count"]


def test_catalog_discovery_keeps_existing_assignment_when_llm_incomplete():
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    fact_result = TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [
                {"name": "pay_amount", "business_process": "ORDER_DETAIL"},
                {"name": "refund_amount", "business_process": "REFUND"},
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )

    mapping = writer_module.catalog_discovery_model_mapping(
        "demo",
        fact_result,
        _catalog_payload(processes=[_order_detail_process()]),
        CanonicalSemanticPayload(
            {
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_DETAIL",
            }
        ),
    )

    assert mapping["business_process"] == "ORDER_DETAIL"
    assert mapping["data_domain"] == "04"
    assert mapping["business_area"] == "SHOP"

    dimension_result = TableInspectResult(
        table_name="dwd_customer",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
    )

    mapping = writer_module.catalog_discovery_model_mapping(
        "demo",
        dimension_result,
        _catalog_payload(subjects=[_customer_subject()]),
        CanonicalSemanticPayload(
            {
                "layer": "DWD",
                "table_type": "dimension",
                "semantic_subject": "CUSTOMER",
            }
        ),
    )

    assert mapping["semantic_subject"] == "CUSTOMER"
    assert mapping["data_domain"] == "04"
    assert mapping["business_area"] == "SHOP"


@pytest.mark.parametrize(
    ("metric_processes", "expected_process"),
    [
        ((), "ACCOUNT_TRANSFER"),
        (("",), "ACCOUNT_TRANSFER"),
    ],
    ids=("factless-fallback", "blank-metric-inherits-table-process"),
)
def test_catalog_discovery_table_process_fallback(
    metric_processes,
    expected_process,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    fact_result = TableInspectResult(
        table_name="dwd_fact",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        business_process="ACCOUNT_TRANSFER",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [
                {
                    "name": f"metric_{index}",
                    "business_process": process,
                }
                for index, process in enumerate(metric_processes)
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )

    mapping = writer_module.catalog_discovery_model_mapping(
        "demo",
        fact_result,
        _catalog_payload(
            processes=[
                {
                    "code": "ACCOUNT_TRANSFER",
                    "name": "账户划转",
                    "data_domain": "04",
                    "business_area": "SHOP",
                }
            ]
        ),
    )

    assert mapping.get("business_process") == expected_process


def test_catalog_discovery_rejects_low_confidence_semantics():
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    result = TableInspectResult(
        table_name="customer_detail",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.01,
        reasoning_steps=[],
        entities=[
            {
                "code": "LOW_CONFIDENCE_ENTITY",
                "type": "primary",
                "key_columns": ["customer_id"],
            }
        ],
    )
    existing = {"layer": "DWD", "table_type": "fact"}

    assert (
        writer_module.catalog_discovery_model_mapping(
            "demo",
            result,
            {},
            existing,
        )
        == {}
    )
    assert (
        writer_module._resolved_results_for_catalog_discovery(
            [result],
            {result.table_name: existing},
        )
        == []
    )


def test_run_metadata_write_passes_inspector_configuration(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    seen = {}

    class FakeInspector:
        def __init__(
            self,
            api_key,
            *,
            model,
            cache_file,
            max_retries,
            parallelism,
            request_timeout,
            min_cacheable_confidence,
        ):
            seen["parallelism"] = parallelism
            seen["min_cacheable_confidence"] = min_cacheable_confidence

        def inspect_batch(self, contexts):
            return []

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(
        isolated_writer_project,
        api_key="test",
        dry_run=True,
        parallelism=4,
        resolution_policy=LayerResolutionPolicy(
            mode="refresh",
            min_llm_confidence=0.8,
        ),
    )

    assert seen["parallelism"] == 4
    assert seen["min_cacheable_confidence"] == 0.8


def test_run_metadata_write_report_uses_plan_prior(
    monkeypatch,
    sample_lineage_data,
    isolated_writer_project,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    model_metadata = {
        "dwd_customer": {
            "version": 2,
            "name": "dwd_customer",
            "layer": "DWD",
            "table_type": "fact",
        },
        "dwd_order_detail": {
            "version": 2,
            "name": "dwd_order_detail",
            "layer": "DWD",
            "table_type": "fact",
        },
        "dws_store_sales_daily": {
            "version": 2,
            "name": "dws_store_sales_daily",
            "layer": "DWS",
            "table_type": "fact",
        },
    }

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_customer":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer="",
                            inferred_layer="OTHER",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                        )
                    )
                else:
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer=ctx.layer,
                            table_type="fact",
                            confidence=0.9,
                            reasoning_steps=[],
                        )
                    )
            return results

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_metadata_write(
        isolated_writer_project,
        api_key="test",
        dry_run=True,
        model_metadata=model_metadata,
        metric_groups={},
        resolution_policy=LayerResolutionPolicy(mode="refresh"),
    )
    customer_report = next(
        table
        for table in result["tables"]
        if table["table_name"] == "dwd_customer"
    )

    assert customer_report["metadata_warnings"][0]["type"] == (
        "llm_layer_fallback"
    )
    assert customer_report["metadata_warnings"][0]["prior_layer"] == "DWD"
    assert customer_report["metadata_warnings"][0]["prior_source"] == (
        "declared"
    )


def test_run_metadata_write_discovers_related_entity_from_dws_grain(
    monkeypatch, tmp_path, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_dir = tmp_path / isolated_writer_project
    models_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    models_dir.mkdir(exist_ok=True)
    ddl_dir.mkdir()
    (models_dir / "dwd_product.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dwd_product",
                "layer": "DWD",
                "table_type": "dimension",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (models_dir / "dws_category_sales_monthly.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "name": "dws_category_sales_monthly",
                "layer": "DWS",
                "table_type": "fact",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "dwd_product.sql").write_text(
        """
        CREATE TABLE dwd_product (
            product_id BIGINT COMMENT '商品ID',
            category_id BIGINT COMMENT '品类ID'
        );
        """,
        encoding="utf-8",
    )
    (ddl_dir / "dws_category_sales_monthly.sql").write_text(
        """
        CREATE TABLE dws_category_sales_monthly (
            category_id BIGINT COMMENT '品类ID',
            stat_month_date DATE COMMENT '统计月份'
        );
        """,
        encoding="utf-8",
    )
    lineage_data = {
        "tables": [
            {
                "name": "dwd_product",
                "full_name": "demo.dwd_product",
                "layer": "DWD",
                "columns": [
                    {"name": "product_id", "type": "BIGINT"},
                    {"name": "category_id", "type": "BIGINT"},
                ],
            },
            {
                "name": "dws_category_sales_monthly",
                "full_name": "demo.dws_category_sales_monthly",
                "layer": "DWS",
                "columns": [
                    {"name": "category_id", "type": "BIGINT"},
                    {"name": "stat_month_date", "type": "DATE"},
                ],
            },
        ],
        "edges": [
            {
                "source": "dwd_product.category_id",
                "target": "dws_category_sales_monthly.category_id",
                "expression": "category_id",
                "source_file": "dws_category_sales_monthly.sql",
            }
        ],
        "indirect_edges": [],
    }

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_product":
                    results.append(
                        TableInspectResult(
                            table_name="dwd_product",
                            declared_layer="DWD",
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                            entity={
                                "code": "PROD",
                                "key_columns": ["product_id"],
                            },
                        )
                    )
                elif ctx.table_name == "dws_category_sales_monthly":
                    results.append(
                        TableInspectResult(
                            table_name="dws_category_sales_monthly",
                            declared_layer="DWS",
                            inferred_layer="DWS",
                            table_type="fact",
                            confidence=0.9,
                            reasoning_steps=[],
                            grain={
                                "keys": ["category_id", "stat_month_date"],
                                "entities": ["CAT"],
                                "time_column": "stat_month_date",
                                "time_period": "M",
                            },
                        )
                    )
            return results

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    run_metadata_write(
        isolated_writer_project, api_key="test", write_scope="grain"
    )

    saved = yaml.safe_load(
        (models_dir / "dwd_product.yaml").read_text(encoding="utf-8")
    )

    assert saved["entities"] == [
        {
            "code": "PROD",
            "type": "primary",
            "key_columns": ["product_id"],
        },
        {
            "code": "CAT",
            "type": "foreign",
            "name": "品类",
            "key_columns": ["category_id"],
            "relationship": {
                "type": "many_to_one",
                "from_entity": "PROD",
            },
        },
    ]


def test_run_catalog_discovery_writes_catalog_from_llm_results(
    tmp_path, monkeypatch, sample_lineage_data
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "catalog_discovery"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    for table_name, layer in [
        ("dwd_customer", "DWD"),
        ("dwd_order_detail", "DWD"),
    ]:
        (models_dir / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: sample_lineage_data,
    )

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_order_detail":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DWD",
                            table_type="fact",
                            confidence=0.9,
                            reasoning_steps=[],
                            columns={
                                "atomic_metrics": [
                                    {
                                        "name": "subtotal",
                                        "business_process": "ORDER_TRANSACTION",
                                    }
                                ],
                                "derived_metrics": [],
                                "calculated_metrics": [],
                                "dimensions": [],
                                "others": [],
                            },
                        )
                    )
                elif ctx.table_name == "dwd_customer":
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                            entities=[
                                {
                                    "code": "CUSTOMER",
                                    "type": "primary",
                                    "name": "客户",
                                    "key_columns": ["customer_id"],
                                }
                            ],
                        )
                    )
            return results

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=True,
    )

    catalog = config.load_business_semantics_catalog(project)
    assert result["source"] == "llm_catalog_discovery"
    assert result["updated"] is True
    assert (project_dir / "business_taxonomy.yaml").exists()
    assert (project_dir / "business_processes.yaml").exists()
    assert (project_dir / "semantic_subjects.yaml").exists()
    assert catalog["business_processes"][0]["code"] == "ORDER_TRANSACTION"
    assert "tables" not in catalog["business_processes"][0]
    assert catalog["semantic_subjects"][0]["code"] == "CUSTOMER"
    assert "tables" not in catalog["semantic_subjects"][0]
    assert result["model_update_count"] == 2

    fact_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_order_detail.yaml").read_text(
            encoding="utf-8"
        )
    )
    dim_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dwd_customer.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fact_model["business_process"] == "ORDER_TRANSACTION"
    assert dim_model["semantic_subject"] == "CUSTOMER"
    assert result["paths"]["taxonomy"].endswith("business_taxonomy.yaml")


def test_run_catalog_discovery_uses_resolved_results_for_catalog(
    tmp_path, monkeypatch, sample_lineage_data
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "catalog_discovery_resolved_catalog"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (models_dir / "dwd_order_detail.yaml").write_text(
        "\n".join(
            [
                "version: 2",
                "name: dwd_order_detail",
                "layer: DWD",
                "table_type: fact",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _write_split_catalog(project_dir, project, _catalog_payload())
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    lineage_data = {
        "tables": [
            table
            for table in sample_lineage_data["tables"]
            if table["name"] == "dwd_order_detail"
        ],
        "edges": [],
        "indirect_edges": [],
    }
    monkeypatch.setattr(
        writer_module,
        "load_lineage_data",
        lambda _project: lineage_data,
    )

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            pass

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="OTHER",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                    entities=[
                        {
                            "code": "ORDER",
                            "type": "primary",
                            "key_columns": ["order_id"],
                        }
                    ],
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    original_pipeline = writer_module.run_inspection_pipeline
    pipeline_calls = []

    def tracking_pipeline(*args, **kwargs):
        pipeline_calls.append({"project": args[0], "kwargs": kwargs})
        return original_pipeline(*args, **kwargs)

    monkeypatch.setattr(
        writer_module, "run_inspection_pipeline", tracking_pipeline
    )

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=True,
    )
    catalog = config.load_business_semantics_catalog(project)

    assert result["catalog"]["semantic_subjects"] == []
    assert catalog["semantic_subjects"] == []
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["project"] == project


def test_run_catalog_discovery_no_overwrite_does_not_write_new_catalog_codes(
    tmp_path, monkeypatch, sample_lineage_data
):
    project = "catalog_discovery_no_overwrite"
    models_dir = _setup_catalog_discovery_model(
        tmp_path,
        monkeypatch,
        sample_lineage_data,
        project,
        model_text="version: 2\nname: dwd_order_detail\nlayer: DWD\n",
        inferred_data_domain="04",
        inferred_business_area="SHOP",
    )

    result = run_catalog_discovery(
        project,
        api_key="test",
        dry_run=False,
        overwrite=False,
    )

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    catalog = config.load_business_semantics_catalog(project)
    assert result["changed"] is False
    assert catalog["business_processes"] == []
    assert "business_process" not in model


def test_run_catalog_metadata_write_removes_stale_business_codes(
    tmp_path, monkeypatch
):
    project = "catalog_writer_stale_refs"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail", "dim_customer"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
                "business_process": "STALE_PROCESS",
            },
            "dim_customer": {
                "version": 2,
                "name": "dim_customer",
                "layer": "DWD",
                "table_type": "dimension",
                "data_domain": "04",
                "business_area": "SHOP",
                "semantic_subject": "STALE_SUBJECT",
                "business_process": "STALE_PROCESS",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    result = run_catalog_metadata_write(
        project, dry_run=False, write_scope="business"
    )

    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (models_dir / "dim_customer.yaml").read_text(encoding="utf-8")
    )
    assert result["model_update_count"] == 2
    assert fact_model["data_domain"] == "04"
    assert fact_model["business_area"] == "SHOP"
    assert "business_process" not in fact_model
    assert "semantic_subject" not in fact_model
    assert dim_model["data_domain"] == "04"
    assert dim_model["business_area"] == "SHOP"
    assert "business_process" not in dim_model
    assert "semantic_subject" not in dim_model


def test_run_catalog_metadata_write_removes_subject_from_fact_models(
    tmp_path, monkeypatch
):
    project = "catalog_writer_fact_subject"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            processes=[_order_detail_process()],
            subjects=[_customer_subject("STORE")],
        ),
        ddl_tables=[
            "ads_store_metric_snapshot",
            "dwd_order_detail",
            "dwd_transactions",
        ],
        models={
            "ads_store_metric_snapshot": {
                "version": 2,
                "name": "ads_store_metric_snapshot",
                "layer": "ADS",
                "table_type": "fact",
                "semantic_subject": "STORE",
            },
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "ORDER_DETAIL",
                "semantic_subject": "STORE",
            },
            "dwd_transactions": {
                "version": 2,
                "name": "dwd_transactions",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    ads_model = yaml.safe_load(
        (models_dir / "ads_store_metric_snapshot.yaml").read_text(
            encoding="utf-8"
        )
    )
    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    taxonomy_model = yaml.safe_load(
        (models_dir / "dwd_transactions.yaml").read_text(encoding="utf-8")
    )
    assert "semantic_subject" not in ads_model
    assert "semantic_subject" not in fact_model
    assert fact_model["business_process"] == "ORDER_DETAIL"
    assert taxonomy_model["data_domain"] == "04"
    assert taxonomy_model["business_area"] == "SHOP"
    assert "business_process" not in taxonomy_model
    assert "semantic_subject" not in taxonomy_model


def test_run_catalog_metadata_write_table_scope_removes_stale_business_codes(
    tmp_path, monkeypatch
):
    project = "catalog_writer_table_scope_stale_refs"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "business_process": "STALE_PROCESS",
            }
        },
    )
    models_dir = project_dir / "mid" / "models"

    result = run_catalog_metadata_write(
        project, dry_run=False, write_scope="table"
    )

    model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    assert result["model_update_count"] == 1
    assert "business_process" not in model
    assert "semantic_subject" not in model


def test_run_catalog_metadata_write_filters_process_subject_metadata_by_taxonomy(
    tmp_path, monkeypatch
):
    project = "catalog_writer_taxonomy_filter"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            domains=[],
            areas=[],
            processes=[_order_detail_process()],
            subjects=[_customer_subject()],
        ),
        ddl_tables=["dwd_order_detail", "dwd_customer"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "data_domain": "04",
                "business_area": "SHOP",
                "business_process": "ORDER_DETAIL",
            },
            "dwd_customer": {
                "version": 2,
                "name": "dwd_customer",
                "layer": "DWD",
                "table_type": "dimension",
                "data_domain": "04",
                "business_area": "SHOP",
                "semantic_subject": "CUSTOMER",
            },
        },
    )
    models_dir = project_dir / "mid" / "models"

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    fact_model = yaml.safe_load(
        (models_dir / "dwd_order_detail.yaml").read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (models_dir / "dwd_customer.yaml").read_text(encoding="utf-8")
    )
    assert fact_model["business_process"] == "ORDER_DETAIL"
    assert dim_model["semantic_subject"] == "CUSTOMER"
    assert "data_domain" not in fact_model
    assert "business_area" not in fact_model
    assert "data_domain" not in dim_model
    assert "business_area" not in dim_model


def test_run_catalog_metadata_write_can_dry_run_with_init_catalog(
    tmp_path, monkeypatch
):
    project = "catalog_writer_dry_run"
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_catalog_metadata_write(
        project,
        dry_run=True,
        write_scope="business",
        init_catalog=True,
    )

    assert result["source"] == "catalog"
    assert result["paths"]["taxonomy"].endswith("business_taxonomy.yaml")
    assert "catalog_paths" not in result
    assert result["model_change_count"] == 1
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()


def test_run_catalog_metadata_write_respects_business_metadata_layers(
    tmp_path, monkeypatch
):
    project = "catalog_writer_layers"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            domains=[{"id": "03", "code": "STOR", "name": "门店域"}],
            areas=[{"id": "SHOP", "code": "SHOP", "name": "零售业务"}],
            processes=[
                _order_detail_process("STORE_SALES"),
                _order_detail_process("IGNORED_DIM_PROCESS"),
            ],
            subjects=[
                {
                    "code": "STORE",
                    "name": "门店",
                    "data_domain": "03",
                    "business_area": "SHOP",
                }
            ],
        ),
        ddl_tables=["dws_store_sales_daily", "dim_store"],
        models={
            "dws_store_sales_daily": {
                "version": 2,
                "name": "dws_store_sales_daily",
                "layer": "DWS",
                "table_type": "fact",
                "business_process": "STORE_SALES",
            },
            "dim_store": {
                "version": 2,
                "name": "dim_store",
                "layer": "DIM",
                "table_type": "dimension",
                "semantic_subject": "STORE",
            },
        },
    )

    run_catalog_metadata_write(project, dry_run=False, write_scope="business")

    dws_model = yaml.safe_load(
        (
            project_dir / "mid" / "models" / "dws_store_sales_daily.yaml"
        ).read_text(encoding="utf-8")
    )
    dim_model = yaml.safe_load(
        (project_dir / "mid" / "models" / "dim_store.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "data_domain" not in dws_model
    assert dws_model["business_area"] == "SHOP"
    assert dws_model["business_process"] == "STORE_SALES"
    assert "data_domain" not in dim_model
    assert "business_area" not in dim_model
    assert "business_process" not in dim_model
    assert dim_model["semantic_subject"] == "STORE"
