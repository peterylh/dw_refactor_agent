import pytest

from dw_refactor_agent.assessment.llm.generation_candidate_resolver import (
    SectionDecision,
    resolve_generation_candidate,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    ParsedInspectionCandidate,
    issue_for_code,
)
from dw_refactor_agent.assessment.llm.publication_transitions import (
    plan_inspection_run_transition,
    plan_no_llm_generation_decisions,
    plan_publication_transition,
    plan_refresh_transitions,
)
from dw_refactor_agent.config import MODEL_SECTIONS
from dw_refactor_agent.config.model_governance import STRUCTURE_SECTIONS


def _active_model(name="fact"):
    return {
        "version": 2,
        "name": name,
        "layer": "DWD",
        "table_type": "fact",
        "business_process": "SALE",
        "atomic_metrics": [{"name": "amount"}],
        "execution": {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        },
    }


def _quarantined_model(name="fact", *, layer="DWD", withheld=("metrics",)):
    withheld = tuple(withheld)
    model = {
        "version": 3,
        "name": name,
        "operational_layer": layer,
        "execution": {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        },
        "governance": {
            "schema_version": 1,
            "status": "quarantined",
            "withheld_sections": list(withheld),
            "reasons": {
                section: [
                    (
                        "inspection_not_requested"
                        if set(withheld) == set(MODEL_SECTIONS)
                        else (
                            "metrics_incomplete"
                            if section == "metrics"
                            else "business_semantics_untrusted"
                        )
                    )
                ]
                for section in withheld
            },
        },
    }
    if set(withheld) != set(MODEL_SECTIONS):
        model.update(
            {
                "layer": layer,
                "table_type": "fact" if layer in {"DWD", "DWS"} else "other",
            }
        )
        if layer in {"DWD", "DWS"}:
            model["business_process"] = "SALE"
    return model


def _decision(table="fact", *, quarantined=(), not_applicable=(), issues=()):
    quarantined = set(quarantined)
    not_applicable = set(not_applicable)
    return SectionDecision(
        table_name=table,
        statuses=tuple(
            (
                section,
                (
                    "quarantined"
                    if section in quarantined
                    else (
                        "not_applicable"
                        if section in not_applicable
                        else "active"
                    )
                ),
            )
            for section in MODEL_SECTIONS
        ),
        reasons=tuple(
            (
                section,
                (
                    "metrics_incomplete"
                    if section == "metrics"
                    else "structure_bundle_incomplete",
                ),
            )
            for section in quarantined
        ),
        issues=tuple(issues),
    )


def _report(table, *, parsed=True, issue_code=None):
    parsed_candidate = None
    if parsed:
        parsed_candidate = ParsedInspectionCandidate.create(
            table_name=table,
            raw_response_hash=f"hash-{table}",
            payload={"table_name": table},
        ).to_dict()
    issues = (
        ()
        if issue_code is None
        else (issue_for_code(issue_code, table=table),)
    )
    return {
        "table_name": table,
        "parsed_candidate": parsed_candidate,
        "issues": [issue.to_dict() for issue in issues],
    }


def _inspection(targets, reports=(), run_issues=()):
    return plan_inspection_run_transition(
        llm_enabled=True,
        inspection_targets=targets,
        reports=reports,
        run_issues=run_issues,
    )


def _transitions_by_section(plan):
    return {item.section: item for item in plan.transitions}


def test_refresh_retention_requires_explicit_eligibility():
    failure = issue_for_code("inspection_transport_failed", table="fact")
    decision = _decision(quarantined={"metrics"}, issues=(failure,))
    retained = plan_refresh_transitions(
        {"fact": _active_model()},
        candidate_decisions=[decision],
        retention_eligible={"FACT": MODEL_SECTIONS},
    )
    metrics = _transitions_by_section(retained)["metrics"]
    assert (
        retained.status,
        metrics.action,
        metrics.effective_status,
        metrics.effective_source,
        metrics.reason,
    ) == (
        "ready",
        "retain_existing_active",
        "active",
        "existing",
        "retryable_inspection_failure",
    )

    stale = plan_refresh_transitions(
        {"fact": _active_model()}, candidate_decisions=[decision]
    )
    assert stale.status == "blocked"
    assert _transitions_by_section(stale)["metrics"].action == (
        "blocked_existing_active_stale"
    )


def test_refresh_hard_block_issue_preempts_section_updates():
    issue = issue_for_code("internal_inspection_error", table="fact")
    plan = plan_refresh_transitions(
        {"fact": _active_model()},
        candidate_decisions=[_decision(issues=(issue,))],
    )
    assert plan.status == "blocked"
    assert {item.action for item in plan.transitions} == {
        "blocked_hard_block_issue"
    }


def test_refresh_activates_requested_quarantine_and_preserves_unrequested():
    plan = plan_refresh_transitions(
        {"fact": _quarantined_model()},
        candidate_decisions=[_decision()],
        requested_sections=("metrics",),
        retention_eligible={"fact": STRUCTURE_SECTIONS},
    )
    transitions = _transitions_by_section(plan)
    assert (
        transitions["metrics"].action,
        transitions["metrics"].clear_governance,
        transitions["classification"].action,
    ) == ("activate_candidate", True, "preserve_unrequested")

    retained = plan_refresh_transitions(
        {"fact": _quarantined_model()},
        candidate_decisions=[_decision(quarantined={"metrics"})],
        retention_eligible={"fact": STRUCTURE_SECTIONS},
    )
    assert _transitions_by_section(retained)["metrics"].quarantine_reasons == (
        "metrics_incomplete",
    )


def test_refresh_without_llm_preserves_governance_but_not_stale_active():
    plan = plan_refresh_transitions(
        {"fact": _quarantined_model()},
        llm_enabled=False,
        retention_eligible={"fact": STRUCTURE_SECTIONS},
    )
    metrics = _transitions_by_section(plan)["metrics"]
    assert (
        plan.status,
        metrics.action,
        metrics.effective_status,
        metrics.reason,
    ) == (
        "ready",
        "retain_existing_governance",
        "quarantined",
        "inspection_not_requested",
    )

    stale = plan_refresh_transitions(
        {"fact": _active_model()}, llm_enabled=False
    )
    assert stale.status == "blocked"
    assert {
        item.action
        for item in stale.transitions
        if item.existing_status == "active"
    } == {"blocked_existing_active_stale"}


@pytest.mark.parametrize(
    ("requested_section", "not_applicable"),
    [
        ("classification", ()),
        ("metrics", ()),
        ("metrics", ("metrics",)),
    ],
)
def test_refresh_rejects_partial_mid_structure_bundle(
    requested_section, not_applicable
):
    plan = plan_refresh_transitions(
        {"fact": _quarantined_model(withheld=MODEL_SECTIONS)},
        candidate_decisions=[_decision(not_applicable=not_applicable)],
        requested_sections=(requested_section,),
    )
    assert plan.status == "blocked"
    assert {item.action for item in plan.transitions} == {
        "blocked_structure_bundle_incomplete"
    }


def test_refresh_does_not_apply_mid_bundle_rule_to_ods():
    plan = plan_refresh_transitions(
        {
            "ods_source": _quarantined_model(
                "ods_source",
                layer="ODS",
                withheld=("business_semantics",),
            )
        },
        llm_enabled=False,
        retention_eligible={"ods_source": ("classification",)},
    )
    assert plan.status == "ready"
    assert (
        _transitions_by_section(plan)["business_semantics"].effective_status
        == "quarantined"
    )


def test_inspection_breaker_allows_low_confidence_and_exact_half_failure():
    low_confidence = _report("A")
    low_confidence["issues"] = [
        issue_for_code("inspection_low_confidence", table="db.a").to_dict()
    ]
    transition = _inspection(
        ("`DB`.`A`", "db.b"),
        (
            low_confidence,
            _report(
                "b", parsed=False, issue_code="inspection_content_parse_failed"
            ),
        ),
    )
    assert (
        transition.status,
        transition.valid_structured_tables,
        transition.service_failure_tables,
    ) == ("healthy", ("`DB`.`A`",), ("db.b",))


@pytest.mark.parametrize(
    ("issue_codes", "expected"),
    [
        (
            ("inspection_content_parse_failed",) * 3,
            (
                "inspection_zero_valid_structured_results",
                "retry",
                True,
            ),
        ),
        (
            ("inspection_authentication_failed", None, None),
            ("inspection_configuration_failure", "fix_configuration", False),
        ),
    ],
)
def test_inspection_breaker_classifies_service_failure(issue_codes, expected):
    names = ("a", "b", "c")
    reports = tuple(
        _report(name, parsed=code is None, issue_code=code)
        for name, code in zip(names, issue_codes)
    )
    transition = _inspection(names, reports)
    assert transition.status == "inspection_failure"
    assert (
        transition.reasons[0],
        transition.retry_action,
        transition.retryable,
    ) == expected
    assert transition.candidate_status_override == "quarantined"


def test_inspection_breaker_rejects_majority_incomplete_and_internal_failure():
    degraded = _inspection(
        ("a", "b", "c"),
        tuple(
            _report(
                name, parsed=False, issue_code="inspection_transport_failed"
            )
            for name in ("a", "b")
        )
        + (_report("c"),),
    )
    incomplete = _inspection(("a", "b"), (_report("a"),))
    internal = _inspection(
        ("a",),
        (_report("a"),),
        (issue_for_code("internal_inspection_error", table="a"),),
    )
    configuration = _inspection(
        ("a",),
        run_issues=(
            issue_for_code("inspection_authentication_failed", table="a"),
        ),
    )
    assert (degraded.reasons, degraded.retryable) == (
        ("inspection_service_degraded",),
        True,
    )
    assert (
        incomplete.reasons,
        incomplete.candidate_status_override,
        incomplete.retry_action,
    ) == (("inspection_settled_set_incomplete",), "unknown", "resume_recovery")
    assert (
        internal.status,
        internal.reasons,
        internal.candidate_status_override,
        internal.retry_action,
    ) == (
        "blocked",
        ("internal_or_deterministic_inspection_block",),
        "unknown",
        "",
    )
    assert (
        configuration.status,
        configuration.reasons,
        configuration.retry_action,
        configuration.retryable,
    ) == (
        "inspection_failure",
        ("inspection_configuration_failure",),
        "fix_configuration",
        False,
    )


def test_inspection_breaker_fail_closes_invalid_typed_candidates():
    untyped = _inspection(
        ("a", "b", "c"),
        (_report("a"), _report("b", parsed=False), _report("c", parsed=False)),
    )
    empty_candidate = _inspection(
        ("a",),
        ({"table_name": "a", "parsed_candidate": {}, "issues": []},),
    )
    mismatched = _report("a")
    mismatched["parsed_candidate"] = _report("b")["parsed_candidate"]
    mismatch = _inspection(("a",), (mismatched,))
    assert {item.status for item in (untyped, empty_candidate, mismatch)} == {
        "blocked"
    }
    assert {item.reasons for item in (untyped, empty_candidate, mismatch)} == {
        ("invalid_inspection_candidate_contract",)
    }


@pytest.mark.parametrize(
    (
        "candidate_status",
        "inspection_status",
        "require_complete",
        "dry_run",
        "expected_status",
    ),
    [
        ("blocked", "healthy", False, False, "blocked"),
        (
            "quarantined",
            "inspection_failure",
            False,
            False,
            "not_published_inspection_failure",
        ),
        (
            "unknown",
            "inspection_failure",
            False,
            False,
            "not_published_inspection_failure",
        ),
        (
            "quarantined",
            "healthy",
            True,
            False,
            "not_published_incomplete",
        ),
        (
            "quarantined",
            "healthy",
            False,
            False,
            "published_with_quarantine",
        ),
        ("complete", "healthy", False, False, "published"),
        ("quarantined", "healthy", False, True, "dry_run"),
    ],
)
def test_publication_transition_distinguishes_gate_outcomes(
    candidate_status,
    inspection_status,
    require_complete,
    dry_run,
    expected_status,
):
    inspection = plan_inspection_run_transition(
        llm_enabled=False, inspection_targets=(), reports=()
    )
    if inspection_status == "inspection_failure":
        inspection = _inspection(
            ("a",),
            (
                _report(
                    "a",
                    parsed=False,
                    issue_code="inspection_transport_failed",
                ),
            ),
        )
    transition = plan_publication_transition(
        candidate_status=candidate_status,
        inspection_transition=inspection,
        require_complete=require_complete,
        dry_run=dry_run,
    )
    assert transition.status == expected_status
    assert transition.published is expected_status.startswith("published")
    if dry_run:
        assert transition.would_publish_status == "published_with_quarantine"
        assert transition.formal_files_state == "unchanged"
    if candidate_status == "blocked":
        assert transition.candidate_status == "blocked"


def test_no_llm_generate_builds_operational_only_v3_quarantine():
    models = {"fact": _active_model()}
    resolved = resolve_generation_candidate(
        models,
        inspection_reports=(),
        catalog={"business_processes": [{"code": "SALE"}]},
        operational_layers={"fact": "DWD"},
        local_decisions=plan_no_llm_generation_decisions(("db.FACT",), models),
    )
    candidate = resolved.models["fact"]
    assert resolved.status == "quarantined"
    assert candidate["version"] == 3
    assert candidate["operational_layer"] == "DWD"
    assert set(candidate) == {
        "version",
        "name",
        "operational_layer",
        "execution",
        "governance",
    }
    assert candidate["governance"]["withheld_sections"] == list(MODEL_SECTIONS)
    assert all(
        reasons == ["inspection_not_requested"]
        for reasons in candidate["governance"]["reasons"].values()
    )

    with pytest.raises(ValueError, match="cannot activate semantics"):
        resolve_generation_candidate(
            models,
            inspection_reports=(),
            catalog={},
            operational_layers={"fact": "DWD"},
            local_decisions=(_decision(),),
        )

    hard_issue = issue_for_code("internal_inspection_error", table="fact")
    hard_blocked = resolve_generation_candidate(
        models,
        inspection_reports=(),
        catalog={},
        operational_layers={"fact": "DWD"},
        local_decisions=(
            _decision(quarantined=MODEL_SECTIONS, issues=(hard_issue,)),
        ),
    )
    assert hard_blocked.status == "blocked"
    assert hard_blocked.validation["errors"][0]["type"] == "hard_block_issue"
