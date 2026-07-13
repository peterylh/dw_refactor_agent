from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "warehouses" / "retail_banking"
SPEC_FILE = WAREHOUSE / "semantic_specs" / "dim_dwd.yaml"


def _load_yaml(path):
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _active_entries(spec):
    return [
        entry for entry in spec["entries"] if entry.get("active_mapping", True)
    ]


def test_semantic_spec_covers_current_direct_dim_dwd_mapping():
    spec = _load_yaml(SPEC_FILE)
    mapping = _load_yaml(
        WAREHOUSE / "mappings" / "fineract_table_mapping.yaml"
    )

    mapped_pairs = {
        (row["source_table"], row["target_table"])
        for row in mapping["mappings"]
        if row["target_layer"] in {"DIM", "DWD"}
    }
    spec_pairs = {
        (entry["source_table"], entry["target_table"])
        for entry in _active_entries(spec)
    }

    assert len(mapped_pairs) == 100
    assert len(spec_pairs) == 100
    assert spec_pairs == mapped_pairs


def test_semantic_spec_has_reviewed_verdicts_and_withdrawn_hard_negatives():
    entries = _load_yaml(SPEC_FILE)["entries"]
    assert len(entries) == 104
    assert Counter(entry["verdict"] for entry in entries) == {
        "accept": 40,
        "revise": 57,
        "reject": 7,
    }

    rejected = {
        entry["current_target"]
        for entry in entries
        if entry["verdict"] == "reject"
    }
    assert rejected == {
        "dim_guarantor",
        "dwd_credit_report",
        "dwd_customer_identifier",
        "dwd_loan_interest_recalculation",
        "dwd_loan_rate_period",
        "dwd_wc_loan_lock_event",
        "dwd_wc_payment_allocation_rule",
    }

    withdrawn = {
        entry["current_target"]
        for entry in entries
        if not entry.get("active_mapping", True)
    }
    assert withdrawn == {
        "dwd_credit_report",
        "dwd_customer_identifier",
        "dwd_wc_loan_lock_event",
        "dwd_wc_payment_allocation_rule",
    }
    for entry in entries:
        if entry["verdict"] == "reject":
            assert entry["allowed_alternatives"]
            assert entry["rationale"]


def test_semantic_spec_uses_only_canonical_catalog_codes():
    spec = _load_yaml(SPEC_FILE)
    process_catalog = _load_yaml(WAREHOUSE / "business_processes.yaml")
    subject_catalog = _load_yaml(WAREHOUSE / "semantic_subjects.yaml")
    valid_processes = {
        item["code"] for item in process_catalog["business_processes"]
    }
    valid_subjects = {
        item["code"] for item in subject_catalog["semantic_subjects"]
    }

    for entry in spec["entries"]:
        process = entry["business_process"]
        subject = entry["semantic_subject"]
        assert process is None or process in valid_processes
        assert subject is None or subject in valid_subjects

    serialized = yaml.safe_dump(spec, allow_unicode=True).lower()
    assert "candidate" not in serialized
    for invalid_code in (
        "loan_management",
        "dpst_management",
        "fina_management",
        "cust_management",
        "paym_management",
        "orgn_management",
        "wcln_management",
    ):
        assert invalid_code not in serialized


def test_semantic_spec_schema_is_complete_and_machine_consumable():
    spec = _load_yaml(SPEC_FILE)
    benchmark_contract = _load_yaml(
        WAREHOUSE / "benchmark/benchmark_contract.yaml"
    )
    alternative_schema = benchmark_contract["table_record"]["fields"][
        "expected"
    ]["allowed_alternatives"]["items"]
    valid_alternative_layers = set(alternative_schema["layer"]["enum"])
    valid_alternative_table_types = set(
        alternative_schema["table_type"]["enum"]
    )
    snapshot = _load_yaml(
        WAREHOUSE / "mappings" / "fineract_schema_snapshot.yaml"
    )
    source_columns = {
        table["source_table"]: {column["name"] for column in table["columns"]}
        for table in snapshot["tables"]
    }
    required = {
        "source_table",
        "current_target",
        "verdict",
        "materialize",
        "target_layer",
        "target_table",
        "table_type",
        "primary_entity",
        "related_entities",
        "grain",
        "business_date",
        "business_process",
        "semantic_subject",
        "sensitivity",
        "allowed_alternatives",
        "rationale",
    }

    for entry in spec["entries"]:
        assert required <= set(entry)
        assert entry["verdict"] in {"accept", "revise", "reject"}
        assert isinstance(entry["materialize"], bool)
        assert entry["source_table"] in source_columns
        assert entry["primary_entity"]["code"]
        assert entry["primary_entity"]["key_columns"]
        assert entry["grain"]["columns"]
        assert entry["grain"]["description"]
        assert entry["rationale"]

        if entry["materialize"]:
            assert entry["target_layer"] in {"DIM", "DWD"}
            assert entry["target_table"]
        else:
            assert entry["target_layer"] is None
            assert entry["target_table"] is None

        for relation in entry["related_entities"]:
            assert {"role", "entity", "key_columns", "source_fk"} <= set(
                relation
            )
            assert relation["role"]
            assert relation["entity"]
            assert relation["key_columns"]
            assert relation["source_fk"]
            assert (
                set(relation["source_fk"])
                <= source_columns[entry["source_table"]]
            )

        business_date = entry["business_date"]
        assert {"kind", "column", "inherit_from"} == set(business_date)
        if business_date["kind"] == "none":
            assert business_date["column"] is None
            assert business_date["inherit_from"] is None
        elif business_date["kind"] == "inherited":
            assert business_date["column"] is None
            assert business_date["inherit_from"]
        else:
            assert business_date["column"]

        sensitivity = entry["sensitivity"]
        assert sensitivity["level"]
        assert sensitivity["action"]

        for alternative in entry["allowed_alternatives"]:
            if isinstance(alternative, str):
                assert alternative.strip()
                continue
            assert {
                "name",
                "layer",
                "table_type",
                "credit",
                "rationale",
            } <= set(alternative)
            assert alternative["name"].strip()
            assert alternative["layer"] in valid_alternative_layers
            assert alternative["table_type"] in valid_alternative_table_types
            assert not isinstance(alternative["credit"], bool)
            assert 0 <= alternative["credit"] <= 1
            assert alternative["rationale"].strip()


def test_boundary_layer_alternatives_are_explicit_and_adjudicated():
    entries = _load_yaml(SPEC_FILE)["entries"]
    by_target = {
        entry["target_table"]: entry
        for entry in entries
        if entry.get("target_table")
    }
    expected = {
        "bridge_loan_rate": {
            ("loan_rate_assignment_satellite", "DIM", "dimension", 0.85),
            (
                "dwd_loan_rate_assignment_relation",
                "DWD",
                "bridge",
                0.65,
            ),
        },
        "bridge_customer_address": {
            ("dim_customer_address_bridge", "DIM", "bridge", 0.8),
            ("customer_address_satellite", "DIM", "dimension", 0.65),
        },
        "bridge_product_gl_mapping": {
            ("dim_product_accounting_rule", "DIM", "rule_reference", 0.9),
            (
                "dwd_product_gl_mapping_relation",
                "DWD",
                "bridge",
                0.55,
            ),
        },
        "dwd_gl_annual_balance_snapshot": {
            ("dws_gl_annual_opening_balance", "DWS", "snapshot_fact", 0.5)
        },
        "dwd_gl_aggregation_summary": {
            (
                "dws_gl_posting_aggregation_daily",
                "DWS",
                "aggregate_fact",
                0.75,
            )
        },
        "dwd_gl_trial_balance_snapshot": {
            ("dws_gl_trial_balance_daily", "DWS", "snapshot_fact", 0.5)
        },
    }

    for table_name, expected_alternatives in expected.items():
        alternatives = by_target[table_name]["allowed_alternatives"]
        assert {
            (
                item["name"],
                item["layer"],
                item["table_type"],
                item["credit"],
            )
            for item in alternatives
        } == expected_alternatives

    assert by_target["bridge_product_gl_mapping"]["target_layer"] == "DIM"
    assert by_target["bridge_product_gl_mapping"]["business_process"] is None
    assert (
        by_target["bridge_product_gl_mapping"]["semantic_subject"]
        == "PRODUCT_GL_MAPPING"
    )


def test_dim_bridge_subject_names_do_not_leak_partial_prefixes():
    subjects = _load_yaml(WAREHOUSE / "semantic_subjects.yaml")[
        "semantic_subjects"
    ]
    by_code = {item["code"]: item for item in subjects}

    assert by_code["LOAN_RATE_RELATION"]["name"] == "loan rate"
    assert by_code["PRODUCT_GL_MAPPING"]["name"] == "product gl mapping"


def test_account_dimensions_define_stable_fields_and_snapshot_targets():
    entries = _load_yaml(SPEC_FILE)["entries"]
    by_target = {entry["current_target"]: entry for entry in entries}
    expected_accounts = {
        "dim_loan_account": "dwd_loan_account_daily_snapshot",
        "dim_deposit_account": "dwd_deposit_account_daily_snapshot",
        "dim_share_account": "dwd_share_account_daily_snapshot",
        "dim_wc_loan_account": "dwd_wc_loan_account_daily_snapshot",
    }

    for target, snapshot_target in expected_accounts.items():
        policy = by_target[target]["dimension_policy"]
        assert "id" in policy["stable_fields"]
        assert len(policy["stable_fields"]) >= 7
        assert policy["snapshot_target"]["layer"] == "DWD"
        assert policy["snapshot_target"]["table"] == snapshot_target
        assert policy["snapshot_target"]["date_column"]


def test_new_snapshot_sources_have_explicit_snapshot_semantics():
    entries = _load_yaml(SPEC_FILE)["entries"]
    by_target = {entry["current_target"]: entry for entry in entries}
    snapshot_targets = {
        "dwd_gl_annual_balance_snapshot",
        "dwd_gl_aggregation_summary",
        "dwd_gl_aggregation_run",
        "dwd_loan_arrears_snapshot",
        "dwd_loan_buy_down_fee_balance",
        "dwd_loan_capitalized_income_balance",
        "dwd_gl_trial_balance_snapshot",
        "dwd_wc_loan_balance_snapshot",
    }

    for target in snapshot_targets:
        entry = by_target[target]
        assert entry.get("active_mapping", True)
        assert entry["target_layer"] == "DWD"
        assert entry["business_date"]["kind"] != "none"
        assert entry["grain"]["description"]
