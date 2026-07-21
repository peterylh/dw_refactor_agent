import json
from unittest.mock import Mock

import pytest

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.inspection_cache_policy import (
    INSPECTION_CACHE_SCHEMA_VERSION,
    PARSER_SCHEMA_VERSION,
    current_policy_versions,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspector,
    cache_result_digest,
    dict_to_result,
    parse_response,
    result_to_cache_dict,
)

FINGERPRINTS = {
    "catalog_snapshot_hash": "catalog-v1",
    "asset_manifest_hash": "assets-v1",
}


def _context() -> TableContext:
    return TableContext(
        table_name="dwd_example",
        layer="DWD",
        ddl="CREATE TABLE dwd_example (id BIGINT);",
        etl_sql="SELECT id FROM source_table;",
        upstream_tables=["source_table"],
        downstream_tables=[],
    )


def _response() -> str:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "inferred_layer": "DWD",
                                "table_type": "fact",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "code": "EXAMPLE",
                                        "type": "primary",
                                        "key_columns": ["id"],
                                    }
                                ],
                                "columns": {
                                    "dimensions": [{"name": "id"}],
                                },
                            }
                        )
                    }
                }
            ]
        }
    )


def _inspector(cache_file) -> TableInspector:
    return TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        **FINGERPRINTS,
    )


def _seed_cache(tmp_path):
    cache_file = tmp_path / "inspect.json"
    inspector = _inspector(cache_file)
    inspector._call_api = lambda _prompt: _response()
    result = inspector.inspect(_context())
    assert result.status == "passed"
    return cache_file


def _rewrite_active_result(cache_file, transform):
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    entry = cache["dwd_example"]
    transform(entry["result"])
    entry["content_sha256"] = cache_result_digest(entry["result"])
    entry["variants"][entry["hash"]] = {
        "result": entry["result"],
        "content_sha256": entry["content_sha256"],
    }
    cache_file.write_text(json.dumps(cache), encoding="utf-8")


def test_cache_payload_round_trip_preserves_lossless_and_all_validation():
    result = parse_response(
        "dwd_bridge",
        json.loads(_response()),
        "DWD",
    )
    result.validation = {
        "bridge_entities_invalid": ["missing relationship entity"],
        "metric_propagation_not_converged": ["dwd_bridge"],
    }
    result.context_hash = "context-v1"
    result.catalog_snapshot_hash = FINGERPRINTS["catalog_snapshot_hash"]
    result.asset_manifest_hash = FINGERPRINTS["asset_manifest_hash"]

    payload = result_to_cache_dict(result)
    restored = dict_to_result(payload)

    assert payload["cache_policy"] == {
        "schema_version": INSPECTION_CACHE_SCHEMA_VERSION,
        "context_hash": "context-v1",
        "catalog_snapshot_hash": "catalog-v1",
        "asset_manifest_hash": "assets-v1",
        **current_policy_versions(),
    }
    assert restored.validation == result.validation
    assert restored.raw_response == result.raw_response
    assert restored.parsed_candidate == result.parsed_candidate
    assert [issue.code for issue in restored.issues] == [
        "bridge_entities_invalid",
        "metric_propagation_not_converged",
    ]

    payload["issues"][0]["code"] = "future_unknown_issue"
    with pytest.raises(ValueError, match="unknown inspection issue code"):
        dict_to_result(payload)


def test_policy_change_replays_lossless_candidate_without_api(tmp_path):
    cache_file = _seed_cache(tmp_path)

    def make_stale(payload):
        payload["table_type"] = "other"
        payload["cache_policy"]["schema_version"] = 1
        payload["cache_policy"]["recovery_version"] = 0
        payload.pop("recovered_candidate")
        payload.pop("repair_audit")

    _rewrite_active_result(cache_file, make_stale)
    inspector = _inspector(cache_file)
    api = Mock(
        side_effect=AssertionError(
            "lossless policy replay must not call the API"
        )
    )
    inspector._call_api = api
    restored = inspector.inspect(_context())

    api.assert_not_called()
    assert restored.reuse_source == "cache"
    assert restored.table_type == "fact"
    assert restored.status == "passed"
    assert inspector.reuse_report()["policy_replays_by_version"] == {
        "recovery_version": 1,
        "schema_version": 1,
    }


def test_non_retryable_semantic_quarantine_reuses_lossless_payload(tmp_path):
    cache_file = tmp_path / "inspect.json"
    first = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        validate_publication_contract=True,
        **FINGERPRINTS,
    )
    first._call_api = Mock(return_value=_response())

    quarantined = first.inspect(_context())

    assert quarantined.status == "blocked"
    assert quarantined.resume_eligible is True
    assert [issue.code for issue in quarantined.issues] == [
        "business_process_missing"
    ]
    first_payload = result_to_cache_dict(quarantined)

    resumed = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        validate_publication_contract=True,
        **FINGERPRINTS,
    )
    api = Mock(side_effect=AssertionError("quarantine reuse called API"))
    resumed._call_api = api

    replayed = resumed.inspect(_context())

    api.assert_not_called()
    assert replayed.status == "blocked"
    assert replayed.reuse_source == "cache"
    assert result_to_cache_dict(replayed) == first_payload
    assert resumed.reuse_report()["hits_by_kind"] == {"semantic_quarantine": 1}


def test_unsettled_propagation_removes_previously_cached_quarantine(tmp_path):
    cache_file = tmp_path / "inspect.json"
    context = _context()
    inspector = TableInspector(
        api_key="test",
        cache_file=cache_file,
        max_retries=0,
        validate_publication_contract=True,
        **FINGERPRINTS,
    )
    inspector._call_api = Mock(return_value=_response())
    result = inspector.inspect(context)
    result.validation["metric_propagation_not_converged"] = [
        context.table_name
    ]

    inspector.persist_finalized_results([(context, result)])

    assert result.resume_eligible is False
    assert [issue.code for issue in result.issues][-1] == (
        "metric_propagation_not_converged"
    )
    assert json.loads(cache_file.read_text(encoding="utf-8")) == {}


@pytest.mark.parametrize(
    "mutation",
    [
        "legacy",
        "parser",
        "unknown_validation",
        "content_hash",
        "root_list",
        "nan_result",
        "low_confidence",
    ],
)
def test_unsafe_cache_variant_retries_instead_of_restoring_passed(
    tmp_path,
    mutation,
):
    cache_file = _seed_cache(tmp_path)
    if mutation == "root_list":
        cache_file.write_text("[]", encoding="utf-8")
    elif mutation in {"content_hash", "nan_result"}:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        if mutation == "content_hash":
            cache["dwd_example"]["content_sha256"] = "corrupt"
        else:
            cache["dwd_example"]["result"]["confidence"] = float("nan")
        cache_file.write_text(json.dumps(cache), encoding="utf-8")
    else:

        def mutate(payload):
            if mutation == "legacy":
                payload.pop("cache_policy")
            elif mutation == "parser":
                payload["cache_policy"]["parser_schema_version"] = (
                    PARSER_SCHEMA_VERSION + 1
                )
            elif mutation == "low_confidence":
                payload["confidence"] = 0.2
                payload["parsed_candidate"]["payload"]["confidence"] = 0.2
            else:
                payload["validation"]["future_validation"] = ["unsafe"]

        _rewrite_active_result(cache_file, mutate)

    inspector = _inspector(cache_file)
    api = Mock(return_value=_response())
    inspector._call_api = api
    result = inspector.inspect(_context())

    api.assert_called_once()
    assert result.reuse_source == ""
    assert result.status == "passed"
    assert isinstance(
        json.loads(cache_file.read_text(encoding="utf-8")),
        dict,
    )
