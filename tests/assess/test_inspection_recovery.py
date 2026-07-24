import json

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.inspection_recovery import (
    recover_inspection_result,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    dict_to_result,
    parse_response,
    result_to_cache_dict,
    validate_inspection_result,
)


def _result(table_name, layer="DWD", table_type="fact", **candidate):
    payload = {
        "inferred_layer": layer,
        "table_type": table_type,
        "confidence": 0.9,
    }
    payload.update(candidate)
    response = {"choices": [{"message": {"content": json.dumps(payload)}}]}
    return parse_response(table_name, response, layer)


def _context(table_name, ddl, **changes):
    values = {
        "table_name": table_name,
        "layer": "DWD",
        "ddl": ddl,
        "etl_sql": "",
        "upstream_tables": [],
        "downstream_tables": [],
    }
    values.update(changes)
    return TableContext(**values)


def _metric(name, expression, **changes):
    metric = {"name": name, "expression": expression}
    metric.update(changes)
    return metric


def _repair_codes(result):
    return {repair.repair_code for repair in result.repair_audit}


def test_column_recovery_is_lossless_idempotent_and_section_aware():
    result = _result(
        "dwd_case",
        entities=[
            {"code": "ROW", "type": "primary", "key_columns": ["Status"]}
        ],
        columns={
            "atomic_metrics": [
                {"name": "AMOUNT", "action": "SUM"},
                {"name": "amount", "action": "SUM"},
            ],
            "dimensions": [{"name": "status"}],
            "others": [{"name": "STATUS"}, {"name": "ghost"}],
        },
    )
    context = _context(
        "dwd_case",
        "CREATE TABLE dwd_case ("
        "Amount DECIMAL(10, 2), Status STRING, missing_col BIGINT);",
    )

    recovered = recover_inspection_result(result, context)
    repeated = recover_inspection_result(recovered, context)

    assert recovered is not result
    assert result.atomic_metrics[0]["name"] == "AMOUNT"
    assert [item["name"] for item in recovered.atomic_metrics] == ["Amount"]
    assert [item["name"] for item in recovered.others] == [
        "Status",
        "missing_col",
    ]
    assert (
        repeated.columns,
        repeated.issues,
        repeated.repair_audit,
        repeated.recovered_candidate,
    ) == (
        recovered.columns,
        recovered.issues,
        recovered.repair_audit,
        recovered.recovered_candidate,
    )
    assert {issue.code: issue.sections for issue in recovered.issues} == {
        "column_group_conflict_structure": (
            "business_semantics",
            "classification",
            "entities",
            "grain",
        ),
        "duplicate_columns_same_group": (),
        "hallucinated_column_unreferenced": (),
        "missing_ddl_column": ("metrics",),
    }
    assert _repair_codes(recovered) >= {
        "ddl_casefold_display_name",
        "duplicate_column_same_group_removed",
        "hallucinated_column_removed",
        "column_group_conflict_moved_to_others",
        "missing_ddl_column_added_to_others",
    }
    repairs = {}
    for repair in recovered.repair_audit:
        repairs.setdefault(repair.repair_code, []).append(repair)
    duplicate = repairs["duplicate_column_same_group_removed"][0]
    assert (duplicate.path, duplicate.after) == (
        "columns.atomic_metrics[1]",
        None,
    )
    assert sorted(
        item.path for item in repairs["column_group_conflict_moved_to_others"]
    ) == [
        "columns.dimensions[0]",
        "columns.others[0]",
        "columns.others[0]",
    ]
    assert repairs["missing_ddl_column_added_to_others"][0].path == (
        "columns.others[1]"
    )

    validated = validate_inspection_result(result, context)
    assert validated.status == "blocked"
    assert validated.validation["duplicate_columns"] == ["Status"]
    assert validated.validation["missing_columns"] == ["missing_col"]
    cached = dict_to_result(result_to_cache_dict(validated))
    assert (cached.repair_audit, cached.recovered_candidate) == (
        validated.repair_audit,
        validated.recovered_candidate,
    )


def test_referenced_hallucination_is_removed_but_sections_stay_untrusted():
    result = _result(
        "dws_reference",
        "DWS",
        entities=[
            {"code": "ROW", "type": "primary", "key_columns": ["ghost"]}
        ],
        grain={"time_column": "ghost"},
        columns={
            "derived_metrics": [_metric("metric_value", "SUM(ghost)")],
            "dimensions": [{"name": "id"}],
        },
    )
    context = _context(
        "dws_reference",
        "CREATE TABLE dws_reference (id BIGINT, metric_value BIGINT);",
        layer="DWS",
    )

    recovered = recover_inspection_result(result, context)
    issue = next(
        item
        for item in recovered.issues
        if item.code == "hallucinated_column_reference"
    )

    assert issue.sections == ("entities", "grain", "metrics")
    assert recovered.entities[0]["key_columns"] == []
    assert recovered.grain["time_column"] == ""
    assert recovered.derived_metrics[0]["expression"] == ""
    assert _repair_codes(recovered) >= {
        "hallucinated_entity_key_removed",
        "hallucinated_grain_time_removed",
        "hallucinated_metric_expression_removed",
    }
    assert validate_inspection_result(result, context).status == "blocked"


def test_unparseable_ddl_does_not_guess_column_repairs():
    result = _result(
        "dwd_invalid_ddl",
        columns={
            "atomic_metrics": [{"name": "AMOUNT"}],
            "others": [{"name": "ghost"}],
        },
    )
    recovered = recover_inspection_result(
        result,
        _context("dwd_invalid_ddl", "CREATE TABLE broken ("),
    )

    assert recovered.columns == result.columns
    assert recovered.repair_audit == recovered.issues == ()


def test_metric_recovery_requires_ast_or_unique_direct_lineage():
    metrics = [
        _metric(
            "event_count",
            "COUNT(id)",
            business_process="payment",
        ),
        _metric("revenue", "SUM(amount)", base_metric="amount"),
        _metric(
            "window_count",
            "COUNT(id) OVER (PARTITION BY id)",
        ),
        _metric("nested_count", "SUM(COUNT(id))"),
        _metric(
            "ambiguous_revenue",
            "SUM(amount)",
            base_metric="amount",
        ),
        _metric(
            "modified_count",
            "COUNT(id)",
            modifiers=["paid_only"],
        ),
        _metric(
            "conditional_count",
            "COUNT(CASE WHEN id > 0 THEN id END)",
        ),
        _metric(
            "wrong_source_revenue",
            "SUM(amount)",
            base_metric="amount",
            base_metric_table="wrong_db.source",
        ),
    ]
    result = _result(
        "dws_metrics",
        "DWS",
        business_process="payment",
        columns={
            "derived_metrics": metrics,
            "dimensions": [{"name": "id"}],
        },
    )
    ddl_columns = ["id"] + [metric["name"] for metric in metrics]
    context = _context(
        "dws_metrics",
        "CREATE TABLE dws_metrics ("
        + ", ".join(f"{name} BIGINT" for name in ddl_columns)
        + ");",
        layer="DWS",
        etl_sql=(
            "SELECT id, COUNT(id) AS event_count, SUM(amount) AS revenue "
            "FROM source GROUP BY id"
        ),
        upstream_tables=["source", "source_alt"],
        upstream_metric_groups={
            table: {"atomic_metrics": ["amount"]}
            for table in ("source", "source_alt")
        },
        column_lineage=[
            {"source": "source.amount", "target": "dws_metrics.revenue"},
            *[
                {
                    "source": f"{table}.amount",
                    "target": "dws_metrics.ambiguous_revenue",
                }
                for table in ("source", "source_alt")
            ],
        ],
        business_semantics_options={
            "business_processes": [{"code": "PAYMENT"}]
        },
    )

    recovered = recover_inspection_result(result, context)
    derived = {metric["name"]: metric for metric in recovered.derived_metrics}

    assert recovered.business_process == "PAYMENT"
    assert [
        (metric["name"], metric["action"])
        for metric in recovered.atomic_metrics
    ] == [("event_count", "COUNT")]
    assert derived["revenue"]["base_metric_table"] == "source"
    assert derived["ambiguous_revenue"]["base_metric_table"] == ""
    assert derived["wrong_source_revenue"]["base_metric_table"] == (
        "wrong_db.source"
    )
    assert {
        "window_count",
        "nested_count",
        "modified_count",
        "conditional_count",
    } <= set(derived)
    assert _repair_codes(recovered) >= {
        "count_metric_normalized",
        "lineage_metric_table_completed",
        "confirmed_semantic_code_normalized",
    }
    assert sorted(
        repair.path
        for repair in recovered.repair_audit
        if repair.repair_code == "count_metric_normalized"
    ) == [
        "columns.atomic_metrics[0]",
        "columns.derived_metrics[0]",
    ]
    validated = validate_inspection_result(result, context)
    assert (
        "wrong_source_revenue:wrong_db.source"
        in validated.validation["invalid_base_metric_tables"]
    )


def test_valid_bridge_entities_complete_grain_and_confirmed_codes():
    entity_codes = ("customer", "account")
    result = _result(
        "dwd_bridge",
        table_type="bridge",
        entities=[
            {
                "code": code,
                "type": "foreign",
                "key_columns": [f"{code}_id"],
            }
            for code in entity_codes
        ],
        columns={
            "dimensions": [{"name": f"{code}_id"} for code in entity_codes]
        },
    )
    context = _context(
        "dwd_bridge",
        "CREATE TABLE dwd_bridge (customer_id BIGINT, account_id BIGINT);",
        business_semantics_options={
            "semantic_subjects": [
                {"code": code.upper()} for code in entity_codes
            ]
        },
    )

    recovered = recover_inspection_result(result, context)

    assert [entity["code"] for entity in recovered.entities] == [
        "CUSTOMER",
        "ACCOUNT",
    ]
    assert recovered.grain["entities"] == ["CUSTOMER", "ACCOUNT"]
    assert _repair_codes(recovered) >= {
        "confirmed_semantic_code_normalized",
        "bridge_grain_entities_completed",
    }
