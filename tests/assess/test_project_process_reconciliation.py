from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.generation_contract import (
    _validate_semantics,
)
from dw_refactor_agent.assessment.llm.model_metadata_catalog import (
    _catalog_model_payload,
    catalog_discovery_model_mapping,
)
from dw_refactor_agent.assessment.llm.model_metadata_updates import (
    _is_count_aggregate,
    enrich_results_with_project_semantics,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
    result_to_dict,
    validate_inspection_result,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    catalog_mapping_for_model,
)
from tests.case_matrix import case_matrix


@case_matrix(
    ("expression", "expected"),
    [
        ("COUNT(*)", True),
        ("COUNT(*) WHERE is_active = TRUE", True),
        ("SUM(CASE WHEN active THEN 1 ELSE 0 END)", True),
        ("SUM(amount)", False),
        ("SUM(CASE WHEN active THEN amount ELSE 0 END)", False),
        ("SUM(CASE WHEN active THEN 0 ELSE 0 END)", False),
        ("COUNT(*) + 1", False),
        ("COUNT(*) / SUM(amount", False),
        ("COUNT(", False),
        ("COUNT(*) WHERE amount > SUM(x)", False),
        ("COUNT(*) WHERE ROW_NUMBER() OVER () = 1", False),
        ("COUNT(*) WHERE EXISTS (SELECT 1)", False),
    ],
)
def test_count_aggregate_detection(expression, expected):
    assert _is_count_aggregate(expression) is expected


def _result(
    table_name,
    *,
    layer="DWD",
    table_type="fact",
    process="",
    atomic=(),
    derived=(),
    dimensions=(),
):
    return TableInspectResult(
        table_name=table_name,
        declared_layer=layer,
        inferred_layer=layer,
        table_type=table_type,
        business_process=process,
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": list(atomic),
            "derived_metrics": list(derived),
            "calculated_metrics": [],
            "dimensions": list(dimensions),
            "others": [],
        },
    )


def _context(
    table_name,
    *,
    layer="DWD",
    ddl="",
    etl_sql="",
    upstream=(),
    metric_groups=None,
    column_lineage=None,
):
    return TableContext(
        table_name=table_name,
        table_identity=f"analytics.{table_name}",
        layer=layer,
        ddl=ddl,
        etl_sql=etl_sql,
        upstream_tables=list(upstream),
        downstream_tables=[],
        upstream_metric_groups=metric_groups or {},
        column_lineage=column_lineage or [],
    )


def test_dws_records_composite_sources_and_normalizes_row_counts():
    transaction = _result(
        "transaction",
        process="TRANSACTION",
        atomic=[
            {
                "name": "amount",
                "business_process": "TRANSACTION",
            }
        ],
    )
    account = _result(
        "account",
        table_type="other",
    )
    summary = _result(
        "customer_monthly",
        layer="DWS",
        derived=[
            {
                "name": "transaction_amount",
                "base_metric": "amount",
                "base_metric_table": "analytics.transaction",
                "expression": "SUM(amount)",
            },
            {
                "name": "active_account_count",
                "base_metric": "",
                "base_metric_table": "analytics.account",
                "expression": "COUNT(*) WHERE is_active",
            },
            {
                "name": "past_due_account_count",
                "base_metric": "",
                "base_metric_table": "analytics.account",
                "expression": ("SUM(CASE WHEN is_past_due THEN 1 ELSE 0 END)"),
            },
            {
                "name": "total_balance",
                "base_metric": "current_balance",
                "base_metric_table": "analytics.account",
                "expression": "SUM(current_balance)",
            },
        ],
        dimensions=[{"name": "customer_id"}, {"name": "year_month"}],
    )
    summary.validation = {
        "missing_base_metrics": [
            "active_account_count",
            "past_due_account_count",
        ],
        "invalid_time_periods": ["derived_metrics[1].time_period=FORTNIGHT"],
        "invalid_metric_expressions": [
            "derived_metrics[2].expression=COUNT(*) BY account"
        ],
        "business_process_missing": [
            "fact inspection requires one business process"
        ],
    }
    contexts = {
        "transaction": _context("transaction"),
        "account": _context("account"),
        "customer_monthly": _context(
            "customer_monthly",
            layer="DWS",
            ddl=(
                "CREATE TABLE customer_monthly ("
                "customer_id BIGINT, year_month STRING, "
                "transaction_amount DECIMAL, active_account_count BIGINT, "
                "past_due_account_count BIGINT, total_balance DECIMAL)"
            ),
            etl_sql=(
                "SELECT customer_id, year_month, SUM(amount), COUNT(*), "
                "SUM(CASE WHEN is_past_due THEN 1 ELSE 0 END), "
                "SUM(current_balance) FROM source "
                "GROUP BY customer_id, year_month"
            ),
            upstream=["analytics.transaction", "analytics.account"],
            metric_groups={
                "analytics.transaction": {
                    "atomic_metrics": ["amount"],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                },
                "analytics.account": {
                    "atomic_metrics": ["current_balance"],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                },
            },
        ),
    }

    enrich_results_with_project_semantics(
        [transaction, account, summary],
        contexts,
        catalog={"business_processes": [{"code": "TRANSACTION"}]},
    )
    validate_inspection_result(
        summary,
        contexts["customer_monthly"],
        validate_publication_contract=True,
    )
    catalog = {"business_processes": [{"code": "TRANSACTION"}]}
    mapping = catalog_discovery_model_mapping(
        "demo",
        summary,
        catalog=catalog,
    )
    model = _catalog_model_payload(
        table_name=summary.table_name,
        existing={
            "name": summary.table_name,
            "layer": "DWS",
            "table_type": "fact",
        },
        mapping=mapping,
    )

    assert summary.status == "passed"
    assert summary.business_process == ""
    assert summary.business_process_mode == "composite"
    assert summary.business_process_sources == [
        "analytics.account",
        "analytics.transaction",
    ]
    assert {metric["name"] for metric in summary.atomic_metrics} == {
        "active_account_count",
        "past_due_account_count",
    }
    assert {metric["name"] for metric in summary.derived_metrics} == {
        "transaction_amount",
        "total_balance",
    }
    processes_by_metric = {
        metric["name"]: metric.get("business_process", "")
        for group in (
            summary.atomic_metrics,
            summary.derived_metrics,
            summary.calculated_metrics,
        )
        for metric in group
    }
    assert processes_by_metric == {
        "active_account_count": "",
        "past_due_account_count": "",
        "transaction_amount": "TRANSACTION",
        "total_balance": "",
    }
    assert model["business_processes"] == ["TRANSACTION"]
    assert model["business_process_mode"] == "composite"
    assert (
        model["business_process_sources"] == summary.business_process_sources
    )
    assert "business_process" not in model
    refresh_mapping = catalog_mapping_for_model(
        catalog,
        summary.table_name,
        model,
    )
    assert refresh_mapping["business_process_mode"] == "composite"
    assert (
        refresh_mapping["business_process_sources"]
        == summary.business_process_sources
    )
    assert (
        _validate_semantics(
            summary.table_name,
            model,
            result_to_dict(summary),
            catalog=catalog,
        )
        == []
    )


def test_single_source_processless_summary_remains_blocked():
    account = _result("account", table_type="other")
    summary = _result(
        "account_summary",
        layer="DWS",
        derived=[
            {
                "name": "total_balance",
                "base_metric": "current_balance",
                "base_metric_table": "analytics.account",
                "expression": "SUM(current_balance)",
            }
        ],
        dimensions=[{"name": "customer_id"}],
    )
    contexts = {
        "account": _context("account"),
        "account_summary": _context(
            "account_summary",
            layer="DWS",
            ddl=(
                "CREATE TABLE account_summary "
                "(customer_id BIGINT, total_balance DECIMAL)"
            ),
            etl_sql=(
                "SELECT customer_id, SUM(current_balance) AS total_balance "
                "FROM account GROUP BY customer_id"
            ),
            upstream=["analytics.account"],
            metric_groups={
                "analytics.account": {
                    "atomic_metrics": ["current_balance"],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                }
            },
        ),
    }

    enrich_results_with_project_semantics([account, summary], contexts)
    validate_inspection_result(
        summary,
        contexts["account_summary"],
        validate_publication_contract=True,
    )

    assert summary.business_process_mode == ""
    assert summary.status == "blocked"
    assert summary.validation["business_process_missing"]


def test_promoted_count_reconciles_after_real_deterministic_validation():
    transaction = _result(
        "transaction",
        process="TRANSACTION",
        atomic=[
            {
                "name": "amount",
                "business_process": "TRANSACTION",
            }
        ],
    )
    summary = _result(
        "transaction_count_summary",
        layer="DWS",
        derived=[
            {
                "name": "transaction_count",
                "base_metric": "",
                "base_metric_table": "analytics.transaction",
                "expression": "COUNT(*)",
                "time_period": "FORTNIGHT",
            }
        ],
        dimensions=[{"name": "customer_id"}],
    )
    contexts = {
        "transaction": _context("transaction"),
        "transaction_count_summary": _context(
            "transaction_count_summary",
            layer="DWS",
            ddl=(
                "CREATE TABLE transaction_count_summary "
                "(customer_id BIGINT, transaction_count BIGINT)"
            ),
            etl_sql=(
                "SELECT customer_id, COUNT(*) AS transaction_count "
                "FROM transaction GROUP BY customer_id"
            ),
            upstream=["analytics.transaction"],
            metric_groups={
                "analytics.transaction": {
                    "atomic_metrics": ["amount"],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                }
            },
        ),
    }
    validate_inspection_result(
        summary,
        contexts["transaction_count_summary"],
        validate_publication_contract=True,
    )
    assert summary.validation["invalid_time_periods"] == [
        "derived_metrics[0].time_period=FORTNIGHT"
    ]

    enrich_results_with_project_semantics(
        [transaction, summary],
        contexts,
        catalog={"business_processes": [{"code": "TRANSACTION"}]},
    )
    validate_inspection_result(
        summary,
        contexts["transaction_count_summary"],
        validate_publication_contract=True,
    )

    assert summary.status == "passed"
    assert summary.business_process == "TRANSACTION"
    assert [metric["name"] for metric in summary.atomic_metrics] == [
        "transaction_count"
    ]
    assert summary.derived_metrics == []


def test_processless_dimension_measure_sources_do_not_form_composite():
    account = _result("account", table_type="dimension")
    profile = _result("profile", table_type="dimension")
    summary = _result(
        "dimension_measure_summary",
        layer="DWS",
        derived=[
            {
                "name": "total_balance",
                "base_metric": "current_balance",
                "base_metric_table": "analytics.account",
                "expression": "SUM(current_balance)",
            },
            {
                "name": "average_risk_score",
                "base_metric": "risk_score",
                "base_metric_table": "analytics.profile",
                "expression": "AVG(risk_score)",
            },
        ],
        dimensions=[{"name": "customer_id"}],
    )
    contexts = {
        "account": _context("account"),
        "profile": _context("profile"),
        "dimension_measure_summary": _context(
            "dimension_measure_summary",
            layer="DWS",
            ddl=(
                "CREATE TABLE dimension_measure_summary "
                "(customer_id BIGINT, total_balance DECIMAL, "
                "average_risk_score DECIMAL)"
            ),
            etl_sql=(
                "SELECT customer_id, SUM(current_balance) AS total_balance, "
                "AVG(risk_score) AS average_risk_score "
                "FROM account JOIN profile USING (customer_id) "
                "GROUP BY customer_id"
            ),
            upstream=["analytics.account", "analytics.profile"],
        ),
    }

    enrich_results_with_project_semantics(
        [account, profile, summary],
        contexts,
    )
    validate_inspection_result(
        summary,
        contexts["dimension_measure_summary"],
        validate_publication_contract=True,
    )

    assert summary.business_process_mode == ""
    assert summary.business_process_sources == []
    assert summary.status == "blocked"
    assert summary.validation["business_process_missing"]


def test_shared_metric_with_multiple_fact_processes_is_blocked():
    sale = _result(
        "sale",
        process="SALE",
        atomic=[{"name": "amount", "business_process": "SALE"}],
    )
    refund = _result(
        "refund",
        process="REFUND",
        atomic=[{"name": "amount", "business_process": "REFUND"}],
    )
    summary = _result(
        "net_summary",
        layer="DWS",
        derived=[
            {
                "name": "net_amount",
                "base_metric": "amount",
                "base_metric_table": "analytics.sale",
                "expression": "sale_amount - refund_amount",
            }
        ],
        dimensions=[{"name": "customer_id"}],
    )
    contexts = {
        "sale": _context("sale"),
        "refund": _context("refund"),
        "net_summary": _context(
            "net_summary",
            layer="DWS",
            ddl=(
                "CREATE TABLE net_summary "
                "(customer_id BIGINT, net_amount DECIMAL)"
            ),
            etl_sql=(
                "SELECT customer_id, SUM(sale.amount) - "
                "SUM(refund.amount) AS net_amount "
                "FROM sale JOIN refund USING (customer_id) "
                "GROUP BY customer_id"
            ),
            upstream=["analytics.sale", "analytics.refund"],
            column_lineage=[
                {
                    "source": "analytics.sale.amount",
                    "target": "analytics.net_summary.net_amount",
                },
                {
                    "source": "analytics.refund.amount",
                    "target": "analytics.net_summary.net_amount",
                },
            ],
        ),
    }

    enrich_results_with_project_semantics(
        [sale, refund, summary],
        contexts,
    )
    validate_inspection_result(
        summary,
        contexts["net_summary"],
        validate_publication_contract=True,
    )

    assert summary.business_process_mode == "composite"
    assert summary.business_process_sources == [
        "analytics.refund",
        "analytics.sale",
    ]
    assert summary.business_process_conflicts == ["net_amount"]
    assert summary.derived_metrics[0].get("business_process", "") == ""
    assert summary.status == "blocked"
    assert summary.validation["composite_process_invalid"]
    model = {
        "name": "net_summary",
        "layer": "DWS",
        "table_type": "fact",
        "business_process_mode": "composite",
        "business_processes": ["REFUND", "SALE"],
        "business_process_sources": summary.business_process_sources,
    }
    errors = _validate_semantics(
        summary.table_name,
        model,
        result_to_dict(summary),
        catalog={
            "business_processes": [
                {"code": "REFUND"},
                {"code": "SALE"},
            ]
        },
    )
    assert any(
        error["type"] == "composite_process_invalid" for error in errors
    )


def test_metric_process_must_match_contributing_fact_evidence():
    sale = _result(
        "sale",
        process="SALE",
        atomic=[{"name": "amount", "business_process": "SALE"}],
    )
    account = _result("account", table_type="other")
    summary = _result(
        "sales_account_summary",
        layer="DWS",
        derived=[
            {
                "name": "total_amount",
                "business_process": "RETURN",
                "base_metric": "amount",
                "base_metric_table": "analytics.sale",
                "expression": "SUM(amount)",
            },
            {
                "name": "account_count",
                "base_metric": "",
                "base_metric_table": "analytics.account",
                "expression": "COUNT(*)",
            },
        ],
        dimensions=[{"name": "customer_id"}],
    )
    contexts = {
        "sale": _context("sale"),
        "account": _context("account"),
        "sales_account_summary": _context(
            "sales_account_summary",
            layer="DWS",
            ddl=(
                "CREATE TABLE sales_account_summary "
                "(customer_id BIGINT, total_amount DECIMAL, "
                "account_count BIGINT)"
            ),
            etl_sql=(
                "SELECT customer_id, SUM(amount) AS total_amount, "
                "COUNT(*) AS account_count FROM source "
                "GROUP BY customer_id"
            ),
            upstream=["analytics.sale", "analytics.account"],
        ),
    }

    enrich_results_with_project_semantics(
        [sale, account, summary],
        contexts,
    )
    validate_inspection_result(
        summary,
        contexts["sales_account_summary"],
        validate_publication_contract=True,
    )

    assert summary.business_process_mode == "composite"
    assert summary.business_process_conflicts == ["total_amount"]
    assert summary.derived_metrics[0]["business_process"] == "RETURN"
    assert summary.status == "blocked"
    assert summary.validation["composite_process_invalid"]


def test_equivalent_source_process_codes_use_one_stable_value():
    sale = _result(
        "sale",
        process="SALE",
        atomic=[{"name": "amount", "business_process": "SALE"}],
    )
    legacy_sale = _result(
        "legacy_sale",
        process="sale",
        atomic=[{"name": "amount", "business_process": "sale"}],
    )
    summary = _result(
        "combined_sale_summary",
        layer="DWS",
        derived=[
            {
                "name": "total_amount",
                "base_metric": "amount",
                "base_metric_table": "analytics.sale",
                "expression": "SUM(amount)",
            }
        ],
    )
    contexts = {
        "sale": _context("sale"),
        "legacy_sale": _context("legacy_sale"),
        "combined_sale_summary": _context(
            "combined_sale_summary",
            layer="DWS",
            column_lineage=[
                {
                    "source": "analytics.sale.amount",
                    "target": "analytics.combined_sale_summary.total_amount",
                },
                {
                    "source": "analytics.legacy_sale.amount",
                    "target": "analytics.combined_sale_summary.total_amount",
                },
            ],
        ),
    }

    enrich_results_with_project_semantics(
        [sale, legacy_sale, summary],
        contexts,
    )

    assert summary.business_process_mode == "composite"
    assert summary.business_process_conflicts == []
    assert summary.derived_metrics[0]["business_process"] == "SALE"
