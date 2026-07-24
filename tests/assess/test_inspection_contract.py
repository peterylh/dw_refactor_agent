import json
from dataclasses import FrozenInstanceError
from http.client import IncompleteRead
from urllib.error import HTTPError

import pytest

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.generation_contract import (
    GENERATION_ERROR_TYPES,
)
from dw_refactor_agent.assessment.llm.inspection_contract import (
    business_process_codes,
    validate_generate_inspection_contract,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    GENERATION_ERROR_ISSUE_CODES,
    ISSUE_CODES,
    LEGACY_VALIDATION_ISSUE_CODES,
    InspectionInternalError,
    generation_error_to_issue,
    issue_for_code,
    issues_from_validation,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    VALIDATION_ERROR_KEYS,
    VALIDATION_WARNING_KEYS,
    TableInspector,
    TableInspectResult,
    parse_response,
    result_to_dict,
)


def _inspection_response(*, duplicate_roles: bool) -> str:
    entity_codes = (
        ("OFFICE", "OFFICE")
        if duplicate_roles
        else ("FROM_OFFICE", "TO_OFFICE")
    )
    table_process = "TRANSFER_DAILY_SUMMARY" if duplicate_roles else "TRANSFER"
    content = {
        "inferred_layer": "DWS",
        "table_type": "fact",
        "business_process": table_process,
        "confidence": 0.95,
        "reasoning_steps": [],
        "entities": [
            {
                "code": entity_codes[0],
                "type": "foreign",
                "key_columns": ["from_office_id"],
            },
            {
                "code": entity_codes[1],
                "type": "foreign",
                "key_columns": ["to_office_id"],
            },
        ],
        "grain": {
            "entities": list(entity_codes),
            "time_column": "stat_date",
            "time_period": "D",
        },
        "columns": {
            "atomic_metrics": [
                {
                    "name": "record_count",
                    "business_process": "TRANSFER",
                }
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [
                {"name": "stat_date"},
                {"name": "from_office_id"},
                {"name": "to_office_id"},
            ],
            "others": [],
        },
    }
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(content),
                    }
                }
            ]
        }
    )


def test_business_process_codes_use_table_and_metric_evidence():
    assert business_process_codes(
        "cash-transfer daily summary",
        (
            [
                {"business_process": ""},
                {"business_process": "CASH_TRANSFER"},
            ],
            [],
        ),
    ) == ["CASH_TRANSFER_DAILY_SUMMARY", "CASH_TRANSFER"]


def test_generate_inspection_contract_reports_publication_failures():
    result = TableInspectResult(
        table_name="transfer_daily",
        declared_layer="DWD",
        inferred_layer="DWS",
        table_type="fact",
        business_process="",
        confidence=0.95,
        reasoning_steps=[],
        entities=[
            {
                "code": "OFFICE",
                "type": "foreign",
                "key_columns": ["missing_office_id"],
            },
            {
                "code": "OFFICE",
                "type": "foreign",
                "key_columns": ["to_office_id"],
            },
        ],
        grain={
            "entities": ["OFFICE", "CURRENCY"],
            "time_column": "missing_date",
        },
    )

    validation = validate_generate_inspection_contract(
        result,
        {"to_office_id"},
    )

    assert validation == {
        "business_process_missing": [
            "fact inspection requires one business process"
        ],
        "duplicate_entity_codes": ["OFFICE"],
        "entity_key_missing": [
            "OFFICE: key column missing_office_id is absent from DDL"
        ],
        "grain_entity_unknown": ["CURRENCY"],
        "grain_column_missing": ["missing_date"],
    }


def test_generate_inspector_retries_publication_contract_failures(
    monkeypatch,
):
    context = TableContext(
        table_name="transfer_daily",
        layer="DWD",
        ddl=(
            "CREATE TABLE transfer_daily ("
            "stat_date DATE, from_office_id BIGINT, "
            "to_office_id BIGINT, record_count BIGINT)"
        ),
        etl_sql=(
            "SELECT stat_date, from_office_id, to_office_id, "
            "COUNT(*) AS record_count FROM source "
            "GROUP BY stat_date, from_office_id, to_office_id"
        ),
        upstream_tables=["source"],
        downstream_tables=[],
    )
    responses = iter(
        [
            _inspection_response(duplicate_roles=True),
            _inspection_response(duplicate_roles=False),
        ]
    )
    api_calls = []
    inspector = TableInspector(
        api_key="test",
        max_retries=1,
        validate_publication_contract=True,
    )

    def call_api(_prompt):
        api_calls.append("called")
        return next(responses)

    monkeypatch.setattr(inspector, "_call_api", call_api)

    result = inspector.inspect(context)

    assert api_calls == ["called", "called"]
    assert result.status == "passed"
    assert result.retry_count == 1
    assert result.business_process == "TRANSFER"
    assert [entity["code"] for entity in result.entities] == [
        "FROM_OFFICE",
        "TO_OFFICE",
    ]


def test_generate_does_not_reuse_refresh_cache_without_contract_validation(
    tmp_path,
    monkeypatch,
):
    context = TableContext(
        table_name="transfer_daily",
        layer="DWD",
        ddl=(
            "CREATE TABLE transfer_daily ("
            "stat_date DATE, from_office_id BIGINT, "
            "to_office_id BIGINT, record_count BIGINT)"
        ),
        etl_sql=(
            "SELECT stat_date, from_office_id, to_office_id, "
            "COUNT(*) AS record_count FROM source "
            "GROUP BY stat_date, from_office_id, to_office_id"
        ),
        upstream_tables=["source"],
        downstream_tables=[],
    )
    cache_file = tmp_path / "inspect.json"
    refresh_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        validate_publication_contract=False,
    )
    monkeypatch.setattr(
        refresh_inspector,
        "_call_api",
        lambda _prompt: _inspection_response(duplicate_roles=True),
    )

    refresh_result = refresh_inspector.inspect(context)

    assert refresh_result.status == "passed"
    generate_calls = []
    generate_inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        validate_publication_contract=True,
    )

    def generate_api(_prompt):
        generate_calls.append("called")
        return _inspection_response(duplicate_roles=False)

    monkeypatch.setattr(generate_inspector, "_call_api", generate_api)

    generate_result = generate_inspector.inspect(context)

    assert generate_calls == ["called"]
    assert generate_result.status == "passed"
    assert generate_result.reuse_source == ""


def _minimal_context() -> TableContext:
    return TableContext(
        table_name="dwd_example",
        layer="DWD",
        ddl="CREATE TABLE dwd_example (id BIGINT)",
        etl_sql="",
        upstream_tables=[],
        downstream_tables=[],
    )


def _minimal_result(**changes) -> TableInspectResult:
    values = {
        "table_name": "dwd_example",
        "declared_layer": "DWD",
        "inferred_layer": "DWD",
        "table_type": "fact",
        "confidence": 0.9,
        "reasoning_steps": [],
    }
    values.update(changes)
    return TableInspectResult(**values)


def _api_response(candidate) -> str:
    return json.dumps(
        {"choices": [{"message": {"content": json.dumps(candidate)}}]}
    )


def test_issue_registries_cover_current_validation_and_generation_types():
    assert set(LEGACY_VALIDATION_ISSUE_CODES) == set(
        VALIDATION_ERROR_KEYS + VALIDATION_WARNING_KEYS
    )
    assert set(GENERATION_ERROR_ISSUE_CODES) == set(GENERATION_ERROR_TYPES)
    assert {
        code
        for codes in LEGACY_VALIDATION_ISSUE_CODES.values()
        for code in codes
    } <= ISSUE_CODES
    assert set(GENERATION_ERROR_ISSUE_CODES.values()) <= ISSUE_CODES
    contract_issue = generation_error_to_issue(
        {
            "type": "execution_slice_missing",
            "table": "dwd_example",
            "message": "contract detail",
        }
    )
    assert (
        contract_issue.code,
        contract_issue.origin,
        contract_issue.stage,
        contract_issue.retryable,
    ) == (
        "execution_slice_missing",
        "deterministic_contract",
        "generation_validation",
        False,
    )
    inspection_issue = generation_error_to_issue(
        {
            "type": "llm_inspection_missing",
            "table": "dwd_example",
            "message": "contract detail",
        }
    )
    assert (
        inspection_issue.code,
        inspection_issue.origin,
        inspection_issue.retryable,
    ) == ("inspection_missing", "llm_validation", True)


def test_raw_and_parsed_candidates_are_separate_lossless_objects():
    candidate = {
        "inferred_layer": "DWD",
        "table_type": "other",
        "confidence": 0.9,
        "reasoning_steps": [],
        "future_parser_field": {"kept": [1, "二"]},
    }
    response = {
        "id": "response-1",
        "choices": [{"message": {"content": json.dumps(candidate)}}],
    }

    result = parse_response("dwd_example", response, "DWD")
    serialized = result_to_dict(result)

    assert result.parsed_candidate.payload == candidate
    assert json.loads(result.raw_response.body) == response
    assert serialized["parsed_candidate"]["payload"] == candidate
    assert serialized["raw_response"]["content_hash"] == (
        result.raw_response.content_hash
    )
    with pytest.raises(FrozenInstanceError):
        result.parsed_candidate.table_name = "changed"


@pytest.mark.parametrize(
    ("columns", "expected_code", "expected_groups"),
    [
        (
            {
                "atomic_metrics": [
                    {"name": "amount", "measure": "amount"},
                    {"name": "AMOUNT", "measure": "amount"},
                ]
            },
            "duplicate_columns_same_group",
            ["atomic_metrics"],
        ),
        (
            {
                "atomic_metrics": [{"name": "amount"}],
                "dimensions": [{"name": "AMOUNT"}],
            },
            "column_group_conflict_metric",
            ["atomic_metrics", "dimensions"],
        ),
        (
            {
                "dimensions": [{"name": "status"}],
                "others": [{"name": "STATUS"}],
            },
            "column_group_conflict_structure",
            ["dimensions", "others"],
        ),
    ],
)
def test_duplicate_column_migration_preserves_conflict_kind(
    columns,
    expected_code,
    expected_groups,
):
    result = _minimal_result(
        columns=columns,
        validation={
            "duplicate_columns": [next(iter(columns.values()))[0]["name"]]
        },
    )

    issues = issues_from_validation(result)

    assert [issue.code for issue in issues] == [expected_code]
    group_evidence = next(
        evidence
        for evidence in issues[0].evidence
        if evidence.kind == "column_groups"
    )
    assert group_evidence.to_dict() == {
        "kind": "column_groups",
        "values": expected_groups,
    }


@pytest.mark.parametrize(
    ("group_name", "expected_code", "expected_sections"),
    [
        ("others", "hallucinated_column_unreferenced", ()),
        ("atomic_metrics", "hallucinated_column_reference", ("metrics",)),
    ],
)
def test_unknown_column_migration_tracks_formal_references(
    group_name,
    expected_code,
    expected_sections,
):
    result = _minimal_result(
        columns={group_name: [{"name": "ghost_amount"}]},
        validation={"unknown_columns": ["ghost_amount"]},
    )

    issue = issues_from_validation(result)[0]

    assert issue.code == expected_code
    assert issue.sections == expected_sections


def test_unknown_column_migration_ignores_codes_and_descriptive_text():
    result = _minimal_result(
        entities=[
            {
                "code": "ORDER",
                "type": "primary",
                "key_columns": ["order_id"],
            }
        ],
        columns={
            "derived_metrics": [
                {
                    "name": "amount",
                    "description": "order amount",
                    "reason": "derived from order activity",
                    "expression": (
                        "CASE WHEN status = 'order' "
                        "THEN SUM(amount) ELSE 0 END"
                    ),
                }
            ],
            "others": [{"name": "order"}],
        },
        validation={"unknown_columns": ["order"]},
    )

    issue = issues_from_validation(result)[0]

    assert issue.code == "hallucinated_column_unreferenced"
    assert issue.sections == ()
    assert issue.path == ""


def test_parser_failures_use_typed_retryable_issues():
    parsed = parse_response(
        "dwd_example",
        {"choices": [{"message": {"content": "not-json"}}]},
        "DWD",
    )
    assert parsed.status == "blocked"
    assert [issue.code for issue in parsed.issues] == [
        "inspection_content_parse_failed"
    ]
    assert parsed.issues[0].retryable is True


def test_retry_fallback_preserves_low_confidence_attempt_issue(monkeypatch):
    payloads = iter(
        [
            {
                "inferred_layer": "DWD",
                "table_type": "fact",
                "confidence": 0.9,
                "columns": {
                    "dimensions": [{"name": "id"}],
                    "others": [{"name": "ghost"}],
                },
            },
            {
                "inferred_layer": "DWD",
                "table_type": "other",
                "confidence": 0.0,
            },
        ]
    )
    inspector = TableInspector(api_key="test", max_retries=1)
    monkeypatch.setattr(
        inspector,
        "_call_api",
        lambda _prompt: _api_response(next(payloads)),
    )

    result = inspector.inspect(_minimal_context())
    serialized = result_to_dict(result)

    assert result.confidence == 0.9
    assert result.resume_eligible is False
    assert "inspection_low_confidence" in {
        issue["code"] for issue in serialized["issues"]
    }


def test_endpoint_configuration_and_network_read_failures_are_separate(
    monkeypatch,
):
    context = _minimal_context()
    configured = TableInspector(
        api_key="test",
        base_url="not-a-url?api_key=SECRET",
        max_retries=2,
    ).inspect(context)

    assert configured.retry_count == 0
    assert [issue.code for issue in configured.issues] == [
        "inspection_configuration_invalid"
    ]
    assert configured.issues[0].retryable is False
    assert "SECRET" not in json.dumps(
        result_to_dict(configured),
        ensure_ascii=False,
    )

    class BrokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            raise IncompleteRead(b"partial", 10)

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: BrokenResponse(),
    )
    transported = TableInspector(
        api_key="test",
        max_retries=0,
    ).inspect(context)

    assert [issue.code for issue in transported.issues] == [
        "inspection_transport_failed"
    ]
    assert transported.issues[0].retryable is True
    assert transported.issues[0].origin == "transport"
    assert transported.issues[0].evidence[0].values == ("IncompleteRead",)


@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (401, "inspection_authentication_failed", False),
        (400, "inspection_request_rejected", False),
        (429, "inspection_transport_failed", True),
    ],
)
def test_http_failures_preserve_status_and_retry_policy(
    monkeypatch,
    status_code,
    expected_code,
    retryable,
):
    error = HTTPError(
        "https://api.example.test?api_key=SECRET",
        status_code,
        "rejected SECRET",
        {},
        None,
    )

    def fail_http(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", fail_http)
    result = TableInspector(api_key="test", max_retries=0).inspect(
        _minimal_context()
    )
    serialized = result_to_dict(result)
    issue = result.issues[0]
    status_evidence = next(
        item for item in issue.evidence if item.kind == "http_status"
    )

    assert issue.code == expected_code
    assert issue.retryable is retryable
    assert status_evidence.values == (str(status_code),)
    assert "SECRET" not in json.dumps(serialized, ensure_ascii=False)


def test_internal_validator_errors_propagate_as_typed_hard_failures(
    monkeypatch,
):
    inspector = TableInspector(api_key="test", max_retries=0)
    context = _minimal_context()
    response = _api_response(
        {
            "inferred_layer": "DWD",
            "table_type": "other",
            "confidence": 0.9,
        }
    )
    monkeypatch.setattr(inspector, "_call_api", lambda _prompt: response)

    def fail_validation(*_args, **_kwargs):
        raise RuntimeError("validator invariant")

    monkeypatch.setattr(
        "dw_refactor_agent.assessment.llm.table_inspector."
        "validate_inspection_result",
        fail_validation,
    )

    with pytest.raises(InspectionInternalError) as caught:
        inspector.inspect(context)

    assert caught.value.issue.code == "internal_inspection_error"
    assert caught.value.issue.retryable is False
    assert caught.value.issue.stage == "local_validation"
    assert caught.value.issue.path == ""

    parser_error = InspectionInternalError(
        "parser invariant",
        table_name="dwd_example",
        stage="parse",
    )
    assert parser_error.issue.stage == "parse"

    worker_inspector = TableInspector(api_key="test", parallelism=1)

    def fail_worker(*_args, **_kwargs):
        raise RuntimeError("worker invariant")

    monkeypatch.setattr(worker_inspector, "inspect", fail_worker)
    with pytest.raises(InspectionInternalError) as worker_failure:
        worker_inspector.inspect_batch([context])

    assert worker_failure.value.issue.stage == "local_validation"
    assert worker_failure.value.issue.evidence[-1].to_dict() == {
        "kind": "internal_context",
        "values": ["worker"],
    }


def test_serialization_resynchronizes_late_compatibility_validation():
    result = _minimal_result()
    assert result.issues == ()

    result.validation = {
        "resolution_requires_reinspection": [
            "inspected=DWD/fact, resolved=DWS/fact"
        ]
    }
    serialized = result_to_dict(result)

    assert serialized["status"] == "blocked"
    assert [issue["code"] for issue in serialized["issues"]] == [
        "resolution_requires_reinspection"
    ]
    assert serialized["issues"][0]["sections"] == [
        "business_semantics",
        "classification",
        "entities",
        "grain",
        "metrics",
    ]
    assert [issue.code for issue in result.issues] == [
        "resolution_requires_reinspection"
    ]

    result.validation = {}
    typed_only = issue_for_code(
        "missing_ddl_column",
        table=result.table_name,
        items=("missing_amount",),
    )
    result.issues = result.issues + (typed_only,)
    resynchronized = result_to_dict(result)

    assert [issue["code"] for issue in resynchronized["issues"]] == [
        "missing_ddl_column"
    ]


def test_unknown_validation_keys_fail_closed():
    result = _minimal_result(
        table_type="other",
        validation={"future_validation_key": ["unsafe"]},
    )
    with pytest.raises(ValueError, match="unregistered validation keys"):
        issues_from_validation(result)
