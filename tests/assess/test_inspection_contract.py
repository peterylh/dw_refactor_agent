import json

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.inspection_contract import (
    business_process_codes,
    validate_generate_inspection_contract,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspector,
    TableInspectResult,
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
