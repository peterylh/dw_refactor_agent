import ast

import pytest

from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.llm.context_builder import build_contexts
from dw_refactor_agent.assessment.llm.model_metadata_catalog import (
    _catalog_model_payload,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    catalog_mapping_for_model,
)
from dw_refactor_agent.assessment.rules.dimensions.metadata_health import (
    score_metadata_health,
)
from dw_refactor_agent.assessment.rules.dimensions.model_design import (
    score_model_design_health,
)
from dw_refactor_agent.assessment.rules.dimensions.naming import (
    score_naming_conventions,
)
from dw_refactor_agent.assessment.rules.dimensions.reuse import (
    score_reusability,
)
from dw_refactor_agent.assessment.rules.engine.selection import RuleSelection
from dw_refactor_agent.assessment.semantic_models import (
    CanonicalSemanticPayload,
)
from dw_refactor_agent.config import (
    PROJECT_ROOT,
    UnavailableModelSection,
    UnsupportedModelGovernanceError,
    load_naming_config,
)
from dw_refactor_agent.config.model_governance import MODEL_FIELD_SECTIONS
from dw_refactor_agent.config.semantics import (
    business_domain_config_from_dictionaries,
)

_QUARANTINE_REASONS = {
    "classification": "structure_bundle_incomplete",
    "business_semantics": "business_process_missing",
    "entities": "structure_bundle_incomplete",
    "grain": "structure_bundle_incomplete",
    "metrics": "dependent_structure_unavailable",
}


def _quarantined_model(
    name="dws_quarantined",
    layer="DWS",
    sections=tuple(_QUARANTINE_REASONS),
):
    model = {
        "version": 3,
        "name": name,
        "operational_layer": layer,
        "execution": {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        },
        "governance": {
            "status": "quarantined",
            "schema_version": 1,
            "withheld_sections": list(sections),
            "reasons": {
                section: [_QUARANTINE_REASONS[section]] for section in sections
            },
        },
    }
    if "classification" not in sections:
        model.update({"layer": layer, "table_type": "fact"})
    return model


def _active_model(name, layer="DWS"):
    return {
        "version": 2,
        "name": name,
        "layer": layer,
        "table_type": "fact",
    }


def _metrics_quarantined_model(name, layer="DWD"):
    model = _quarantined_model(name, layer, ("metrics",))
    model["governance"]["reasons"]["metrics"] = ["metrics_incomplete"]
    return model


def _context(models):
    return AssessmentContext.from_facts(
        tables=[{"name": name, "columns": []} for name in models],
        models=models,
        naming_config=load_naming_config(PROJECT_ROOT / "naming_config.yaml"),
    )


@pytest.mark.parametrize(
    "scorer",
    (
        score_reusability,
        score_metadata_health,
        score_model_design_health,
        score_naming_conventions,
    ),
)
def test_fully_quarantined_semantics_are_not_assessed(scorer):
    result = scorer(_context({"dws_quarantined": _quarantined_model()}))

    assert result["status"] == "not_assessed"
    assert result["score"] is None
    assert result["effective_score"] == 0.0
    assert result["coverage"]["quarantined_tables"] == ["dws_quarantined"]


def test_partial_quarantine_cannot_improve_dimension_score():
    context = _context(
        {
            "dws_active": _active_model("dws_active"),
            "dws_quarantined": _quarantined_model(),
        }
    )
    context.__dict__["downstream"] = {
        "dws_active": {"ads_a", "ads_b", "ads_c"}
    }

    result = score_reusability(context)

    assert result["score"] == 100.0
    assert result["effective_score"] == 50.0
    assert result["status"] == "quarantined"
    assert result["coverage"]["coverage_pct"] == 50.0


def test_metrics_quarantine_keeps_active_model_design_checks_and_cannot_raise():
    tables = [
        {"name": "ads_source", "columns": []},
        {"name": "dwd_target", "columns": []},
    ]
    edge = {
        "source": "ads_source.id",
        "target": "dwd_target.id",
        "source_file": "dwd_target.sql",
    }
    active = AssessmentContext.from_facts(
        tables=tables,
        edges=[edge],
        models={
            "ads_source": _active_model("ads_source", "ADS"),
            "dwd_target": _active_model("dwd_target", "DWD"),
        },
    )
    quarantined = AssessmentContext.from_facts(
        tables=tables,
        edges=[edge],
        models={
            "ads_source": _active_model("ads_source", "ADS"),
            "dwd_target": _metrics_quarantined_model("dwd_target"),
        },
    )

    active_result = score_model_design_health(active)
    quarantined_result = score_model_design_health(quarantined)

    assert "ARCH_REVERSE_DEPENDENCY" in {
        issue["rule_id"] for issue in quarantined_result["issues"]
    }
    assert quarantined_result["effective_score"] <= active_result["score"]
    assert quarantined_result["effective_score"] == 0.0


def test_derived_metric_rule_checks_governance_before_payload_applicability():
    context = AssessmentContext.from_facts(
        tables=[{"name": "dws_target", "columns": []}],
        models={
            "dws_target": _metrics_quarantined_model(
                "dws_target",
                layer="DWS",
            )
        },
    )

    result = score_model_design_health(
        context,
        rule_selection=RuleSelection(
            only={"MODEL_DERIVED_METRIC_BASE_ATOMIC"}
        ),
    )

    assert result["status"] == "not_assessed"
    assert result["effective_score"] == 0.0
    assert result["coverage"]["quarantined_tables"] == ["dws_target"]


def test_irrelevant_metrics_quarantine_keeps_metadata_health_unchanged():
    business_config = business_domain_config_from_dictionaries(
        {"data_domains": [{"id": "01", "code": "TRADE", "name": "交易"}]}
    )
    common = {
        "tables": [{"name": "dwd_order", "columns": []}],
        "naming_config": load_naming_config(
            PROJECT_ROOT / "naming_config.yaml"
        ),
        "business_domain_config": business_config,
    }

    active = score_metadata_health(
        AssessmentContext.from_facts(
            models={"dwd_order": _active_model("dwd_order", "DWD")},
            **common,
        )
    )
    quarantined = score_metadata_health(
        AssessmentContext.from_facts(
            models={"dwd_order": _metrics_quarantined_model("dwd_order")},
            **common,
        )
    )

    assert "METADATA_DATA_DOMAIN_VALID" in {
        issue["rule_id"] for issue in quarantined["issues"]
    }
    assert quarantined["score"] == active["score"]
    assert "status" not in quarantined


def test_metrics_quarantine_keeps_independent_naming_checks():
    active = score_naming_conventions(
        _context({"bad": _active_model("bad", "DWD")})
    )
    quarantined = score_naming_conventions(
        _context({"bad": _metrics_quarantined_model("bad")})
    )

    assert "NAMING_TABLE_TEMPLATE" in {
        issue["rule_id"] for issue in quarantined["issues"]
    }
    assert quarantined["effective_score"] <= active["score"]
    assert quarantined["effective_score"] == 0.0


def test_catalog_and_llm_context_do_not_consume_quarantined_semantics(
    tmp_path,
):
    model = _quarantined_model()
    unavailable = catalog_mapping_for_model({}, model["name"], model)
    assert isinstance(unavailable, UnavailableModelSection)

    contexts = build_contexts(
        "governed_context",
        {"tables": [{"name": model["name"]}], "edges": []},
        ddl_dir=tmp_path,
        tasks_dir=tmp_path,
        model_metadata={model["name"]: model},
        metric_groups={},
    )
    assert contexts == []


def test_catalog_boundaries_require_formal_or_explicit_canonical_models():
    malformed = _quarantined_model()
    malformed.pop("name")

    with pytest.raises(UnsupportedModelGovernanceError):
        catalog_mapping_for_model({}, "dws_malformed", malformed)
    with pytest.raises(UnsupportedModelGovernanceError):
        _catalog_model_payload(
            table_name="dws_malformed",
            existing=malformed,
            mapping={},
        )

    canonical = CanonicalSemanticPayload()
    assert (
        catalog_mapping_for_model({}, "dws_new", canonical)["table"]
        == "dws_new"
    )
    assert (
        _catalog_model_payload(
            table_name="dws_new",
            existing=canonical,
            mapping={"layer": "DWS", "table_type": "fact"},
        )["name"]
        == "dws_new"
    )


def test_llm_context_preserves_quarantined_upstream_metric_status(tmp_path):
    source = _metrics_quarantined_model("dwd_source")
    target = _active_model("dws_target")
    contexts = build_contexts(
        "governed_context",
        {
            "tables": [{"name": "dwd_source"}, {"name": "dws_target"}],
            "edges": [
                {
                    "source": "dwd_source.amount",
                    "target": "dws_target.amount",
                }
            ],
        },
        ddl_dir=tmp_path,
        tasks_dir=tmp_path,
        layers={"DWS"},
        model_metadata={"dwd_source": source, "dws_target": target},
        metric_groups={},
    )

    assert len(contexts) == 1
    assert contexts[0].upstream_metric_groups == {}
    assert contexts[0].upstream_metric_group_status == {
        "dwd_source": {
            "status": "quarantined",
            "reasons": ["metrics_incomplete"],
        }
    }


def test_managed_consumers_do_not_read_raw_model_fields():
    governed_fields = set(MODEL_FIELD_SECTIONS) | {
        "execution",
        "operational_layer",
    }
    managed_files = (
        "assessment/assessment_context.py",
        "assessment/project_facts/asset_catalog.py",
        "assessment/project_facts/business_semantics.py",
        "assessment/project_facts/entity_metadata.py",
        "assessment/llm/context_builder.py",
        "assessment/llm/model_metadata_catalog.py",
        "assessment/llm/model_metadata_writer.py",
        "assessment/rules/dimensions/depth.py",
        "assessment/rules/dimensions/metadata_health.py",
        "assessment/rules/dimensions/model_design.py",
        "assessment/rules/dimensions/naming.py",
        "assessment/rules/dimensions/reuse.py",
        "execution/model_config.py",
        "execution/planner.py",
        "lineage/table_graph.py",
        "refactor/verification_plan.py",
    )
    raw_receivers = {
        "metadata",
        "model_metadata",
        "raw_model_metadata",
        "raw_model",
        "raw",
        "models",
    }

    def receiver_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and node.attr in {
            "models",
            "metadata",
        }:
            return node.attr
        return None

    root = PROJECT_ROOT / "src" / "dw_refactor_agent"
    violations = []
    for relative_path in managed_files:
        path = root / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        tainted = set(raw_receivers)
        if relative_path == "assessment/llm/model_metadata_catalog.py":
            tainted.update({"existing", "existing_model"})
        changed = True
        while changed:
            changed = False
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                source = receiver_name(node.value)
                if source not in tainted:
                    continue
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id not in tainted
                    ):
                        tainted.add(target.id)
                        changed = True
        for node in ast.walk(tree):
            field = None
            owner = None
            if isinstance(node, ast.Call):
                function = node.func
                if (
                    isinstance(function, ast.Attribute)
                    and function.attr == "get"
                    and receiver_name(function.value) is not None
                    and node.args
                    and isinstance(node.args[0], ast.Str)
                ):
                    owner = receiver_name(function.value)
                    field = node.args[0].s
            elif isinstance(node, ast.Subscript) and isinstance(
                node.ctx,
                ast.Load,
            ):
                owner = receiver_name(node.value)
                raw_slice = node.slice
                if isinstance(raw_slice, ast.Index):
                    raw_slice = raw_slice.value
                if isinstance(raw_slice, ast.Str):
                    field = raw_slice.s
            if owner not in tainted or field not in governed_fields:
                continue
            violations.append(f"{relative_path}:{node.lineno}:{field}")
    assert violations == []
