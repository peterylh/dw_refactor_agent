import copy

import pytest

from dw_refactor_agent.assessment.llm.generation_candidate_resolver import (
    PropagationProvenance,
    SectionDecision,
    collect_propagation_provenance,
    prepare_inspection_for_propagation,
    resolve_fixed_point,
    resolve_generation_candidate,
)
from dw_refactor_agent.assessment.llm.inspection_issues import issue_for_code
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import MODEL_SECTIONS


def _decision(table, *, quarantined=()):
    quarantined = set(quarantined)
    statuses = tuple(
        (
            section,
            "quarantined" if section in quarantined else "active",
        )
        for section in MODEL_SECTIONS
    )
    reasons = tuple(
        (
            section,
            (
                "metrics_incomplete"
                if section == "metrics"
                else "structure_bundle_incomplete",
            ),
        )
        for section in MODEL_SECTIONS
        if section in quarantined
    )
    return SectionDecision(
        table_name=table, statuses=statuses, reasons=reasons
    )


def _edge(source, target, evidence_kind="direct_column_lineage"):
    return PropagationProvenance(
        source_table=source,
        source_section="metrics",
        target_table=target,
        target_section="metrics",
        evidence_kind=evidence_kind,
    )


def test_fixed_point_is_casefold_stable_for_chain_fork_cycle_and_isolation():
    decisions = [
        _decision("Source", quarantined={"metrics"}),
        _decision("chain_a"),
        _decision("CHAIN_B"),
        _decision("fork"),
        _decision("independent"),
    ]
    edges = [
        _edge("SOURCE", "CHAIN_A"),
        _edge("chain_a", "chain_b"),
        _edge("Chain_B", "source"),
        _edge("source", "FORK"),
    ]

    resolved, iterations = resolve_fixed_point(decisions, reversed(edges))
    by_name = {item.table_name.casefold(): item for item in resolved}

    assert iterations >= 2
    assert {
        name
        for name, decision in by_name.items()
        if decision.status("metrics") == "quarantined"
    } == {"source", "chain_a", "chain_b", "fork"}
    assert by_name["independent"].status("metrics") == "active"
    rerun, _rerun_iterations = resolve_fixed_point(resolved, edges)
    assert [item.to_dict() for item in rerun] == [
        item.to_dict() for item in resolved
    ]


def _report(table, payload, *, issue=None):
    return {
        "table_name": table,
        "status": "blocked" if issue else "passed",
        "issues": [issue.to_dict()] if issue else [],
        "recovered_candidate": {"payload": copy.deepcopy(payload)},
        **copy.deepcopy(payload),
    }


def _model(table, layer, table_type, **semantic):
    return {
        "version": 2,
        "name": table,
        "layer": layer,
        "table_type": table_type,
        "execution": {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        },
        **semantic,
    }


def _payload(layer="DWD", table_type="fact", **semantic):
    return {
        "inferred_layer": layer,
        "table_type": table_type,
        "columns": {},
        "entities": [],
        "grain": {},
        **semantic,
    }


def test_effective_candidate_masks_and_cascades_only_explicit_dependencies():
    source_payload = _payload(
        business_process="SALE",
        columns={
            "atomic_metrics": [{"name": "amount", "business_process": "SALE"}]
        },
    )
    target_payload = _payload(
        layer="DWS",
        business_process="SALE",
        columns={
            "derived_metrics": [
                {
                    "name": "total_amount",
                    "base_metric": "amount",
                    "base_metric_table": "SOURCE",
                    "business_process": "SALE",
                }
            ]
        },
    )
    dimension_payload = _payload(
        layer="DIM",
        table_type="dimension",
        entities=[
            {
                "code": "CUSTOMER",
                "type": "primary",
                "key_columns": ["customer_id"],
            }
        ],
    )
    reports = [
        _report(
            "source",
            source_payload,
            issue=issue_for_code(
                "invalid_base_metrics",
                table="source",
                path="columns.atomic_metrics.amount",
            ),
        ),
        _report("target", target_payload),
        _report("independent", dimension_payload),
    ]
    models = {
        "source": _model(
            "source",
            "DWD",
            "fact",
            business_process="SALE",
            atomic_metrics=[{"name": "amount"}],
        ),
        "target": _model(
            "target",
            "DWS",
            "fact",
            business_process="SALE",
            derived_metrics=[
                {
                    "name": "total_amount",
                    "base_metric": "amount",
                    "base_metric_table": "source",
                }
            ],
        ),
        "independent": _model(
            "independent",
            "DIM",
            "dimension",
            semantic_subject="CUSTOMER",
            entities=dimension_payload["entities"],
        ),
    }
    original_models = copy.deepcopy(models)
    original_reports = copy.deepcopy(reports)

    resolver_args = {
        "inspection_reports": reports,
        "catalog": {
            "business_processes": [{"code": "SALE"}],
            "semantic_subjects": [{"code": "CUSTOMER"}],
        },
        "operational_layers": {
            "source": "DWD",
            "target": "DWS",
            "independent": "DIM",
        },
    }
    resolved = resolve_generation_candidate(models, **resolver_args)

    assert models == original_models
    assert reports == original_reports
    assert resolved.status == "quarantined"
    assert resolved.validation["status"] == "passed"
    assert [edge.to_dict() for edge in resolved.provenance] == [
        _edge("source", "target", "declared_base_metric").to_dict()
    ]
    source = resolved.models["source"]
    target = resolved.models["target"]
    independent = resolved.models["independent"]
    assert source["governance"]["withheld_sections"] == ["metrics"]
    assert target["governance"]["withheld_sections"] == ["metrics"]
    assert "atomic_metrics" not in source
    assert "derived_metrics" not in target
    assert "governance" not in independent
    assert independent["semantic_subject"] == "CUSTOMER"
    assert (
        resolve_generation_candidate(models, **resolver_args).models_json
        == resolved.models_json
    )


def test_provenance_ignores_unreferenced_tables():
    reports = [
        _report(
            "source",
            _payload(columns={"atomic_metrics": [{"name": "amount"}]}),
        ),
        _report(
            "target",
            _payload(
                layer="DWS",
                columns={
                    "derived_metrics": [
                        {
                            "name": "total_amount",
                            "base_metric_table": "SOURCE",
                        }
                    ]
                },
            ),
        ),
        _report(
            "unrelated",
            _payload(columns={"atomic_metrics": [{"name": "other"}]}),
        ),
    ]

    assert collect_propagation_provenance(reports) == (
        _edge("source", "target", "declared_base_metric"),
    )


def test_qualified_process_provenance_cascades_case_insensitively():
    reports = []
    for table in ("a", "b", "c"):
        payload = _payload(business_process="SALE" if table == "a" else "")
        report = _report(table, payload)
        report["business_process"] = "SALE"
        reports.append(report)
    provenance = collect_propagation_provenance(
        reports,
        lineage_data={
            "edges": [
                {"source": "DB.A.id", "target": "db.B.id"},
                {"source": "db.b.id", "target": "Db.C.id"},
            ]
        },
    )

    process_edges = tuple(
        edge
        for edge in provenance
        if edge.evidence_kind == "reconciled_process_lineage"
    )
    assert [
        (edge.source_table, edge.target_table) for edge in process_edges
    ] == [("a", "b"), ("b", "c")]
    resolved, _iterations = resolve_fixed_point(
        [
            _decision("a", quarantined={"business_semantics"}),
            _decision("b"),
            _decision("c"),
        ],
        provenance,
    )
    assert all(
        decision.status("business_semantics") == "quarantined"
        for decision in resolved
    )


def test_unknown_metric_process_does_not_quarantine_confirmed_structure():
    payload = _payload(
        business_process="SALE",
        columns={
            "atomic_metrics": [{"name": "amount", "business_process": "TYPO"}]
        },
    )
    resolved = resolve_generation_candidate(
        {
            "sale": _model(
                "sale",
                "DWD",
                "fact",
                business_process="SALE",
                atomic_metrics=[{"name": "amount"}],
            )
        },
        inspection_reports=[_report("sale", payload)],
        catalog={"business_processes": [{"code": "SALE"}]},
        operational_layers={"sale": "DWD"},
    )

    decision = resolved.decisions[0]
    assert decision.quarantined_sections == ("metrics",)
    assert decision.issues[0].path == (
        "columns.atomic_metrics.amount.business_process"
    )
    assert resolved.models["sale"]["business_process"] == "SALE"
    assert "atomic_metrics" not in resolved.models["sale"]


@pytest.mark.parametrize(
    ("expected_tables", "error_type"),
    [
        (("present", "missing"), "candidate_set_mismatch"),
        (
            ("present", "PRESENT"),
            "candidate_set_identity_conflict",
        ),
    ],
)
def test_effective_candidate_validates_explicit_expected_model_set(
    expected_tables, error_type
):
    resolved = resolve_generation_candidate(
        {"present": _model("present", "ODS", "other")},
        inspection_reports=[],
        catalog={},
        operational_layers={"present": "ODS"},
        expected_tables=expected_tables,
    )

    assert resolved.status == "blocked"
    assert [error["type"] for error in resolved.validation["errors"]] == [
        error_type
    ]


def test_local_mask_precedes_propagation_and_preserves_recovered_payload():
    result = TableInspectResult(
        table_name="dwd_sale",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [
                {"name": "amount", "business_process": "NEW_SALE"}
            ]
        },
    )
    original = copy.deepcopy(result)

    effective, decision = prepare_inspection_for_propagation(
        result,
        metadata=_model("dwd_sale", "DWD", "fact"),
        catalog={"business_processes": []},
    )

    assert result == original
    assert result.recovered_candidate is None
    assert decision.quarantined_sections == tuple(MODEL_SECTIONS)
    assert effective.table_type == "other"
    assert effective.atomic_metrics == []
    assert effective.recovered_candidate.payload["table_type"] == "fact"
    assert effective.recovered_candidate.payload["columns"]["atomic_metrics"]


def test_entity_alignment_provenance_records_only_changed_target():
    source_payload = _payload(
        layer="DIM",
        table_type="dimension",
        entities=[
            {
                "code": "CUSTOMER",
                "type": "primary",
                "key_columns": ["customer_id"],
            }
        ],
    )
    target_payload = _payload(
        entities=[
            {
                "code": "CLIENT",
                "type": "foreign",
                "key_columns": ["customer_id"],
            }
        ],
    )
    reports = [
        _report("dim_customer", source_payload),
        _report("dwd_sale", target_payload),
    ]
    reports[1]["entities"][0]["code"] = "CUSTOMER"
    lineage_data = {
        "edges": [
            {
                "source": "dim_customer.customer_id",
                "target": "dwd_sale.customer_id",
                "expression": "dim_customer.customer_id",
                "source_file": "dwd_sale.sql",
            }
        ]
    }

    provenance = collect_propagation_provenance(
        reports,
        lineage_data=lineage_data,
    )

    assert provenance == (
        PropagationProvenance(
            source_table="dim_customer",
            source_section="entities",
            target_table="dwd_sale",
            target_section="entities",
            evidence_kind="entity_key_lineage_alignment",
        ),
    )

    resolved = resolve_generation_candidate(
        {
            "dim_customer": _model(
                "dim_customer",
                "DIM",
                "dimension",
                semantic_subject="CUSTOMER",
                entities=source_payload["entities"],
            ),
            "dwd_sale": _model(
                "dwd_sale",
                "DWD",
                "fact",
                business_process="SALE",
                entities=target_payload["entities"],
            ),
        },
        inspection_reports=reports,
        catalog={
            "business_processes": [{"code": "SALE"}],
            "semantic_subjects": [{"code": "CUSTOMER"}],
        },
        operational_layers={"dim_customer": "DIM", "dwd_sale": "DWD"},
        lineage_data=lineage_data,
    )
    target_inspection = next(
        candidate
        for candidate in resolved.effective_inspections
        if candidate.table_name == "dwd_sale"
    )
    assert resolved.models["dwd_sale"]["entities"][0]["code"] == "CUSTOMER"
    assert target_inspection.payload["entities"][0]["code"] == "CUSTOMER"
