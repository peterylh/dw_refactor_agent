import copy
import importlib.util
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.date_window import resolve_etl_dates
from dw_refactor_agent.execution.planner import ExecutionPlanner

PROJECT_DIR = Path(__file__).resolve().parents[1] / "warehouses/retail_banking"
MAPPINGS_DIR = PROJECT_DIR / "mappings"


def _load_yaml(path):
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _stems(path, suffix):
    return {item.stem for item in path.glob(f"*.{suffix}")}


def _load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_tool(module_name, filename):
    return _load_module(module_name, PROJECT_DIR / f"tools/{filename}")


def test_retail_banking_mapping_covers_active_fineract_schema():
    schema = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")

    source_tables = {item["source_table"] for item in schema["tables"]}
    mapped_tables = {item["source_table"] for item in mapping["mappings"]}

    assert schema["upstream_commit"] == mapping["upstream_commit"]
    assert source_tables == mapped_tables
    assert len(source_tables) == schema["active_table_count"] == 277
    assert all(item["disposition"] for item in mapping["mappings"])
    assert all(item["rationale"] for item in mapping["mappings"])
    assert all(
        item["confidence"]
        in {"human_reviewed", "security_reviewed", "candidate"}
        for item in mapping["mappings"]
    )
    savings = {item["source_table"]: item for item in schema["tables"]}
    assert "accrued_till_date" in {
        column["name"] for column in savings["m_savings_account"]["columns"]
    }
    assert "external_id" in {
        column["name"]
        for column in savings["m_savings_account_transaction"]["columns"]
    }
    assert all(
        change["status"] == "overridden"
        for table in schema["tables"]
        for change in table["unresolved_changes"]
    )
    assert all(
        change["status"] == "overridden"
        for change in schema["unresolved_changes"]
    )


def test_retail_banking_generated_asset_sets_match_manifest():
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    manifest = _load_yaml(MAPPINGS_DIR / "generated_asset_manifest.yaml")
    mappings = mapping["mappings"]

    ods_expected = {item["ods_table"] for item in mappings}
    direct_expected = {
        item["target_table"] for item in mappings if item["target_table"]
    }
    semantic_spec = _load_yaml(PROJECT_DIR / "semantic_specs/dim_dwd.yaml")
    snapshot_expected = {
        entry["dimension_policy"]["snapshot_target"]["table"]
        for entry in semantic_spec["entries"]
        if (entry.get("dimension_policy") or {}).get("snapshot_target")
    }
    reviewed_expected = direct_expected | snapshot_expected
    ods_ddl = _stems(PROJECT_DIR / "ods/ddl/internal/retail_banking_dm", "sql")
    ods_models = _stems(
        PROJECT_DIR / "ods/models/internal/retail_banking_dm", "yaml"
    )
    ods_data = _stems(
        PROJECT_DIR / "ods/data/internal/retail_banking_dm", "sql"
    )
    mid_ddl = _stems(PROJECT_DIR / "mid/ddl", "sql")
    mid_models = _stems(PROJECT_DIR / "mid/models", "yaml")
    mid_tasks = _stems(PROJECT_DIR / "mid/tasks", "sql")
    ads_ddl = _stems(PROJECT_DIR / "ads/ddl", "sql")
    ads_models = _stems(PROJECT_DIR / "ads/models", "yaml")
    ads_tasks = _stems(PROJECT_DIR / "ads/tasks", "sql")

    assert ods_ddl == ods_models == ods_data == ods_expected
    assert reviewed_expected <= mid_ddl
    assert mid_ddl == mid_models == mid_tasks
    assert ads_ddl == ads_models == ads_tasks
    assert len(ods_ddl) == manifest["counts"]["ODS"] == 277
    assert len(direct_expected) == 100
    assert len(snapshot_expected) == 4
    assert len(reviewed_expected) == manifest["counts"]["DIM_DWD"] == 104
    assert len(mid_ddl - reviewed_expected) == manifest["counts"]["DWS"] == 18
    assert len(ads_ddl) == manifest["counts"]["ADS"] == 13
    assert (
        len(ods_ddl) + len(mid_ddl) + len(ads_ddl)
        == manifest["counts"]["TOTAL"]
        == 412
    )


def test_retail_banking_physical_table_names_fit_doris_limit():
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    ods_names = {item["ods_table"] for item in mapping["mappings"]}
    builder = _load_tool("retail_asset_inventory_names", "build_assets.py")

    assert max(map(len, ods_names)) <= 64
    assert len(ods_names) == 277
    assert (
        builder._ods_table_name(
            "m_external_asset_owner_loan_product_configurable_attributes"
        )
        == "ods_fineract_m_external_asset_owner_loan_product_config_11bc4520"
    )
    assert (
        builder._ods_table_name(
            "m_external_asset_owner_transfer_journal_entry_mapping"
        )
        == "ods_fineract_m_external_asset_owner_transfer_journal_en_0adfde70"
    )


def test_retail_banking_complete_layer_mapping_covers_every_source():
    source_mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")[
        "mappings"
    ]
    layer_mapping = _load_yaml(MAPPINGS_DIR / "fineract_layer_mapping.yaml")
    by_source = {
        item["source_table"]: item for item in layer_mapping["mappings"]
    }

    assert set(by_source) == {item["source_table"] for item in source_mapping}
    assert layer_mapping["source_table_count"] == 277
    assert all(len(item["layers"]["ODS"]) == 1 for item in by_source.values())
    assert any(item["layers"]["DWS"] for item in by_source.values())
    assert any(item["layers"]["ADS"] for item in by_source.values())


def test_retail_banking_only_reviewed_mappings_generate_direct_downstream():
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    mappings = mapping["mappings"]

    reviewed = [
        item for item in mappings if item["confidence"] == "human_reviewed"
    ]
    candidates = [
        item for item in mappings if item["confidence"] == "candidate"
    ]

    assert all(item["target_layer"] in {"DIM", "DWD"} for item in reviewed)
    assert all(item["target_table"] for item in reviewed)
    assert all(item["target_layer"] == "NONE" for item in candidates)
    assert all(not item["target_table"] for item in candidates)


def test_retail_banking_sensitive_and_provisioning_overrides_are_applied():
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    by_source = {item["source_table"]: item for item in mapping["mappings"]}

    for source_table in ("m_creditbureau_token", "request_audit_table"):
        item = by_source[source_table]
        assert item["sensitivity"] == "restricted"
        assert item["disposition"] == "security_excluded"
        assert not item["target_table"]
    for source_table in ("m_client", "m_staff", "m_guarantor"):
        assert by_source[source_table]["sensitivity"] == "restricted"
    assert by_source["m_external_event"]["target_layer"] == "NONE"
    assert (
        by_source["m_loanproduct_provisioning_entry"]["target_table"]
        == "dwd_loan_provision_entry"
    )
    assert (
        by_source["m_provisioning_history"]["target_table"]
        == "dwd_loan_provision_run"
    )


def test_retail_banking_dws_and_ads_use_explicit_reviewed_semantics():
    dws_tasks = PROJECT_DIR / "mid/tasks"
    deposit_sql = (dws_tasks / "dws_deposit_transaction_daily.sql").read_text(
        encoding="utf-8"
    )
    cashier_sql = (dws_tasks / "dws_cashier_transaction_daily.sql").read_text(
        encoding="utf-8"
    )
    installment_sql = (
        dws_tasks / "dws_loan_installment_due_daily.sql"
    ).read_text(encoding="utf-8")
    provision_sql = (dws_tasks / "dws_loan_provision_run_daily.sql").read_text(
        encoding="utf-8"
    )

    assert "running_balance_derived" not in deposit_sql
    assert "cumulative_balance_derived" not in deposit_sql
    assert "`is_reversed` = FALSE" in deposit_sql
    assert "DATE(src.`txn_date`)" in cashier_sql
    assert "DATE(src.`duedate`)" in installment_sql
    assert "`reseve_amount`" in provision_sql
    assert not (PROJECT_DIR / "ads/ddl/ads_trial_balance_daily.sql").exists()
    assert not (
        PROJECT_DIR / "ads/ddl/ads_provision_reconciliation_daily.sql"
    ).exists()
    ads_sql = (
        PROJECT_DIR / "ads/tasks/ads_loan_transaction_kpi_daily.sql"
    ).read_text(encoding="utf-8")
    assert "average_amount" in ads_sql

    gl_sql = (
        PROJECT_DIR / "ads/tasks/ads_gl_posting_reconciliation_daily.sql"
    ).read_text(encoding="utf-8")
    provision_monitor_sql = (
        PROJECT_DIR / "ads/tasks/ads_provision_posting_monitor_daily.sql"
    ).read_text(encoding="utf-8")
    assert "src.`transaction_id`" in gl_sql
    assert "coalesce(src.`journal_entry_created`, false) = false" in (
        provision_monitor_sql
    )


def test_retail_banking_current_state_snapshots_retain_daily_slices():
    snapshot_tables = {
        "dwd_deposit_account_daily_snapshot",
        "dwd_loan_account_daily_snapshot",
        "dwd_share_account_daily_snapshot",
        "dwd_wc_loan_account_daily_snapshot",
        "dwd_loan_arrears_snapshot",
        "dwd_wc_loan_balance_snapshot",
    }
    for table_name in snapshot_tables:
        task = (PROJECT_DIR / f"mid/tasks/{table_name}.sql").read_text(
            encoding="utf-8"
        )
        model = _load_yaml(PROJECT_DIR / f"mid/models/{table_name}.yaml")
        assert "DELETE FROM" in task
        assert "TRUNCATE TABLE" not in task
        assert "SET @etl_date = CURDATE()" in task
        assert model["execution"]["materialized"] == "incremental"
        assert model["execution"]["slice"] == {
            "param": "etl_date",
            "column": "snapshot_date",
            "period": "D",
        }
        assert model["execution"]["snapshot_mode"] == "current_state_capture"
        assert model["execution"]["historical_replay_supported"] is False

    share_price = _load_yaml(
        PROJECT_DIR / "mid/models/dwd_share_market_price.yaml"
    )
    share_snapshot = _load_yaml(
        PROJECT_DIR / "mid/models/dwd_share_account_daily_snapshot.yaml"
    )
    loan_snapshot = _load_yaml(
        PROJECT_DIR / "mid/models/dwd_loan_account_daily_snapshot.yaml"
    )
    deposit_snapshot = _load_yaml(
        PROJECT_DIR / "mid/models/dwd_deposit_account_daily_snapshot.yaml"
    )
    wc_snapshot = _load_yaml(
        PROJECT_DIR / "mid/models/dwd_wc_loan_account_daily_snapshot.yaml"
    )
    assert "share_value" in share_price["atomic_metrics"]
    assert {
        "total_approved_shares",
        "total_pending_shares",
    } <= set(share_snapshot["atomic_metrics"])
    assert {
        "total_outstanding_derived",
        "interest_outstanding_derived",
        "fee_charges_outstanding_derived",
        "penalty_charges_outstanding_derived",
        "total_expected_repayment_derived",
        "total_repayment_derived",
        "total_costofloan_derived",
        "total_recovered_derived",
    } <= set(loan_snapshot["atomic_metrics"])
    assert {
        "total_deposits_derived",
        "total_withdrawals_derived",
        "total_withhold_tax_derived",
        "on_hold_funds_derived",
    } <= set(deposit_snapshot["atomic_metrics"])
    assert "total_payment_volume" in wc_snapshot["atomic_metrics"]
    for metric in loan_snapshot["metric_semantics"]:
        if "rate" in metric["name"] or "percentage" in metric["name"]:
            assert metric["aggregation_behavior"] == "non_additive"
        else:
            assert metric["aggregation_behavior"] != "additive"


def test_retail_banking_dated_facts_use_safe_etl_date_strategies():
    generator = _load_tool(
        "retail_asset_generator_daily_slices", "generate_assets.py"
    )
    source_schema = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    source_columns = {
        table["source_table"]: {
            column["name"]: column for column in table["columns"]
        }
        for table in source_schema["tables"]
    }
    semantic_entries = _load_yaml(PROJECT_DIR / "semantic_specs/dim_dwd.yaml")[
        "entries"
    ]
    semantic_by_source = {
        entry["source_table"]: entry for entry in semantic_entries
    }
    dated_models = []
    for model_path in sorted((PROJECT_DIR / "mid/models").glob("*.yaml")):
        model = _load_yaml(model_path)
        business_date = model.get("business_date") or {}
        if model.get("layer") != "DWD" or not business_date.get("column"):
            continue
        dated_models.append((model_path, model))
    for model_path in sorted((PROJECT_DIR / "ads/models").glob("*.yaml")):
        dated_models.append((model_path, _load_yaml(model_path)))
    for model_path in sorted((PROJECT_DIR / "mid/models").glob("dws_*.yaml")):
        dated_models.append((model_path, _load_yaml(model_path)))

    assert dated_models
    for model_path, model in dated_models:
        execution = model["execution"]
        task = (
            model_path.parent.parent / "tasks" / f"{model_path.stem}.sql"
        ).read_text(encoding="utf-8")
        if execution["materialized"] == "incremental":
            slice_config = execution["slice"]
            slice_column = slice_config["column"]
            assert slice_config["param"] == "etl_date"
            assert slice_config["period"] == "D"
            if execution.get("historical_replay_supported") is False:
                assert "SET @etl_date = CURDATE()" in task
                assert "COALESCE(@etl_date" not in task
            else:
                assert "SET @etl_date = COALESCE(@etl_date, CURDATE())" in task
            assert "TRUNCATE TABLE" not in task
            assert f"WHERE `{slice_column}` = CAST(@etl_date AS DATE)" in task
            assert task.count("CAST(@etl_date AS DATE)") >= 2
            if (
                model.get("layer") == "DWD"
                and execution.get("historical_replay_supported") is not False
            ):
                assert f"WHERE `{slice_column}` IS NULL;" in task
                delete_prefix = task.split("INSERT INTO", 1)[0]
                assert " OR " not in delete_prefix
        else:
            assert execution["full_refresh_strategy"] == "replace_all"
            assert "TRUNCATE TABLE" in task
            assert "@etl_date" not in task
            if model.get("layer") == "DWD":
                source_table = model["source_mapping"]["source_table"]
                assert not generator._supports_dwd_daily_slice(
                    semantic_by_source[source_table],
                    list(source_columns[source_table].values()),
                )


def test_retail_banking_all_tasks_plan_for_one_business_date():
    planner = ExecutionPlanner("retail_banking")
    task_paths = sorted((PROJECT_DIR / "mid/tasks").glob("*.sql"))
    task_paths += sorted((PROJECT_DIR / "ads/tasks").glob("*.sql"))
    incremental_count = 0
    full_count = 0

    assert len(task_paths) == 135
    etl_date = date.today().isoformat()
    for task_path in task_paths:
        spec = planner.task_spec(task_path.stem, task_path)
        invocations = planner.plan_regular_run(spec, [etl_date])

        assert len(invocations) == 1
        if spec.materialized == "incremental":
            incremental_count += 1
            assert invocations[0].params == {"etl_date": etl_date}
        else:
            full_count += 1
            assert invocations[0].params == {}

    assert incremental_count == 93
    assert full_count == 42


def test_retail_banking_two_month_bootstrap_runs_each_job_once():
    planner = ExecutionPlanner("retail_banking")
    task_paths = sorted((PROJECT_DIR / "mid/tasks").glob("*.sql"))
    task_paths += sorted((PROJECT_DIR / "ads/tasks").glob("*.sql"))
    etl_dates = resolve_etl_dates(
        None,
        lookback_months=2,
        end_date="2026-07-13",
    )

    invocations = []
    for task_path in task_paths:
        spec = planner.task_spec(task_path.stem, task_path)
        invocations.extend(planner.plan_full_refresh(spec, etl_dates))

    assert len(etl_dates) == 62
    assert len(invocations) == len(task_paths) == 135
    companion_invocations = [
        invocation
        for invocation in invocations
        if invocation.strategy == "companion"
    ]
    assert len(companion_invocations) == 87
    assert all(
        invocation.params
        == {
            "etl_start_date": "2026-05-13",
            "etl_end_date": "2026-07-13",
        }
        for invocation in companion_invocations
    )
    assert all(
        invocation.sql_path.parent.name == "full_refresh"
        for invocation in companion_invocations
    )
    for invocation in companion_invocations:
        task = invocation.sql_path.read_text(encoding="utf-8")
        assert "CAST(@etl_start_date AS DATE)" in task
        assert "CAST(@etl_end_date AS DATE)" in task
        assert "TRUNCATE TABLE" in task

    non_companion = [
        invocation
        for invocation in invocations
        if invocation.strategy != "companion"
    ]
    assert len(non_companion) == 48
    assert all(not invocation.params for invocation in non_companion)


def test_retail_banking_daily_slices_declare_mutable_history_replay_policy():
    companion_models = []
    for model_path in sorted((PROJECT_DIR / "mid/models").glob("*.yaml")):
        model = _load_yaml(model_path)
        if model["execution"]["full_refresh_strategy"] == "companion":
            companion_models.append(model)
    for model_path in sorted((PROJECT_DIR / "ads/models").glob("*.yaml")):
        model = _load_yaml(model_path)
        if model["execution"]["full_refresh_strategy"] == "companion":
            companion_models.append(model)

    assert len(companion_models) == 87
    assert all(
        model["execution"]["late_arriving_policy"]
        == "replay_original_and_current_business_dates"
        for model in companion_models
    )


def test_retail_banking_history_replay_skips_only_current_state_captures():
    planner = ExecutionPlanner("retail_banking")
    task_paths = sorted((PROJECT_DIR / "mid/tasks").glob("*.sql"))
    task_paths += sorted((PROJECT_DIR / "ads/tasks").glob("*.sql"))
    current_date = date.today().isoformat()
    historical_date = (date.today() - timedelta(days=1)).isoformat()
    invocations = []
    skipped = []

    for task_path in task_paths:
        spec = planner.task_spec(task_path.stem, task_path)
        for etl_date in [historical_date, current_date]:
            planned = task_run._plan_regular_invocations(
                planner,
                spec,
                etl_date,
                skip_unsupported_history=True,
            )
            invocations.extend(planned)
            if not planned:
                skipped.append((task_path.stem, etl_date))

    assert len(invocations) == 264
    assert len(skipped) == 6
    assert {etl_date for _, etl_date in skipped} == {historical_date}
    assert all(
        planner.task_spec(
            name, PROJECT_DIR / f"mid/tasks/{name}.sql"
        ).historical_replay_supported
        is False
        for name, _ in skipped
    )


def test_retail_banking_restricted_projection_preserves_keys_and_masks_pii():
    bridge_sql = (
        PROJECT_DIR / "mid/tasks/bridge_customer_address.sql"
    ).read_text(encoding="utf-8")
    assert "src.`address_id`" in bridge_sql
    assert "'***' AS `address_id`" not in bridge_sql

    expected_masked = {
        "dim_customer": ["middlename", "fullname", "date_of_birth"],
        "dim_address": ["street", "city", "postal_code"],
        "dwd_loan_guarantor_relation": ["dob", "city", "zip", "comment"],
        "dim_customer_group": ["display_name"],
    }
    for table_name, columns in expected_masked.items():
        task = (PROJECT_DIR / f"mid/tasks/{table_name}.sql").read_text(
            encoding="utf-8"
        )
        for column in columns:
            assert f"ELSE '***' END AS `{column}`" in task

    ownership_sql = (
        PROJECT_DIR / "mid/tasks/dwd_loan_ownership_transfer_detail.sql"
    ).read_text(encoding="utf-8")
    assert "DATE(date_parent.`effective_date_from`)" in ownership_sql
    assert "NULL AS `business_date`" not in ownership_sql


def test_retail_banking_ods_has_date_discovery_column():
    ddl_root = PROJECT_DIR / "ods/ddl/internal/retail_banking_dm"
    missing = []
    for ddl_path in sorted(ddl_root.glob("*.sql")):
        text = ddl_path.read_text(encoding="utf-8").lower()
        if "`load_time` datetime not null" not in text:
            missing.append(ddl_path.name)
    assert missing == []


def test_retail_banking_identity_registry_covers_all_generated_columns():
    registry = _load_yaml(MAPPINGS_DIR / "schema_identities.yaml")["tables"]
    manifest = _load_yaml(MAPPINGS_DIR / "generated_asset_manifest.yaml")
    ddl_paths = list(PROJECT_DIR.glob("ods/ddl/*/*/*.sql"))
    ddl_paths += list((PROJECT_DIR / "mid/ddl").glob("*.sql"))
    ddl_paths += list((PROJECT_DIR / "ads/ddl").glob("*.sql"))

    assert len(ddl_paths) == manifest["counts"]["TOTAL"]
    assert {path.stem for path in ddl_paths} == set(registry)
    assert all(entry["table_id"] for entry in registry.values())
    assert all(entry["columns"] for entry in registry.values())


def test_retail_banking_doris_keys_are_ordered_schema_prefixes():
    ddl_paths = list(PROJECT_DIR.glob("ods/ddl/*/*/*.sql"))
    ddl_paths += list((PROJECT_DIR / "mid/ddl").glob("*.sql"))
    ddl_paths += list((PROJECT_DIR / "ads/ddl").glob("*.sql"))

    violations = []
    for ddl_path in ddl_paths:
        ddl = ddl_path.read_text(encoding="utf-8")
        body_match = re.search(
            r"CREATE TABLE IF NOT EXISTS[^\n]+\((.*?)\) ENGINE=OLAP",
            ddl,
            flags=re.S | re.I,
        )
        key_match = re.search(
            r"DUPLICATE\s+KEY\s*\(([^)]*)\)", ddl, flags=re.I
        )
        assert body_match is not None, ddl_path
        assert key_match is not None, ddl_path
        columns = re.findall(r"^\s*`([^`]+)`", body_match.group(1), re.M)
        keys = re.findall(r"`([^`]+)`", key_match.group(1))
        if columns[: len(keys)] != keys:
            violations.append(ddl_path.name)
    assert violations == []


def test_retail_banking_ods_fixture_volume_is_deterministic_and_bounded():
    generator = _load_module(
        "retail_ods_fixture_generator",
        PROJECT_DIR / "generate_ods_data.py",
    )
    snapshot = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    context = generator._build_context(snapshot, mapping)
    targets = {
        item["ods_table"]: context.row_counts[item["source_table"]]
        for item in mapping["mappings"]
    }

    assert len(targets) == 277
    assert min(targets.values()) >= 1000
    assert max(targets.values()) <= 5000
    assert sum(targets.values()) == 834597
    assert targets["ods_fineract_x_table_column_code_mappings"] == 3463
    assert (
        context.row_counts
        == generator._build_context(snapshot, mapping).row_counts
    )


def test_retail_banking_ods_fixture_primary_and_foreign_keys_are_valid():
    generator = _load_module(
        "retail_ods_fixture_key_validator",
        PROJECT_DIR / "generate_ods_data.py",
    )
    snapshot = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    context = generator._build_context(snapshot, mapping)
    parent_key_values = {}

    for table_name, schema in context.schemas.items():
        primary_key = schema["primary_key"]
        if not primary_key:
            continue
        keys = {
            tuple(
                generator._value_for(
                    context,
                    table_name,
                    context.columns[table_name][column_name],
                    row_number,
                )
                for column_name in primary_key
            )
            for row_number in range(1, context.row_counts[table_name] + 1)
        }
        assert len(keys) == context.row_counts[table_name], table_name

    external_foreign_keys = set()
    for table_name, schema in context.schemas.items():
        for foreign_key in schema["foreign_keys"]:
            referenced_table = foreign_key["referenced_table"]
            if referenced_table not in context.schemas:
                external_foreign_keys.add(
                    (
                        table_name,
                        tuple(foreign_key["base_columns"]),
                        referenced_table,
                        tuple(foreign_key["referenced_columns"]),
                    )
                )
                continue
            base_column = foreign_key["base_columns"][0]
            referenced_column = foreign_key["referenced_columns"][0]
            parent_key = (referenced_table, referenced_column)
            if parent_key not in parent_key_values:
                parent_key_values[parent_key] = {
                    generator._value_for(
                        context,
                        referenced_table,
                        context.columns[referenced_table][referenced_column],
                        row_number,
                    )
                    for row_number in range(
                        1, context.row_counts[referenced_table] + 1
                    )
                }
            child_values = {
                generator._value_for(
                    context,
                    table_name,
                    context.columns[table_name][base_column],
                    row_number,
                )
                for row_number in range(1, context.row_counts[table_name] + 1)
            }
            assert child_values <= parent_key_values[parent_key], (
                table_name,
                foreign_key["name"],
            )

    assert external_foreign_keys == {
        (
            "m_journal_entry_aggregation_summary",
            ("job_execution_id",),
            "batch_job_execution",
            ("job_execution_id",),
        ),
        (
            "m_journal_entry_aggregation_tracking",
            ("job_execution_id",),
            "batch_job_execution",
            ("job_execution_id",),
        ),
    }


def test_retail_banking_ods_fixture_integer_values_fit_source_types():
    generator = _load_module(
        "retail_ods_fixture_integer_validator",
        PROJECT_DIR / "generate_ods_data.py",
    )
    snapshot = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    context = generator._build_context(snapshot, mapping)
    bounds = {
        "TINYINT": (-128, 127),
        "SMALLINT": (-32768, 32767),
        "INT": (-2147483648, 2147483647),
        "INTEGER": (-2147483648, 2147483647),
        "BIGINT": (-9223372036854775808, 9223372036854775807),
    }

    for table_name, schema in context.schemas.items():
        for column in schema["columns"]:
            source_type = " ".join(str(column["source_type"]).upper().split())
            integer_type = next(
                (
                    type_name
                    for type_name in bounds
                    if source_type.startswith(type_name)
                ),
                None,
            )
            if integer_type is None:
                continue
            lower, upper = bounds[integer_type]
            for row_number in range(1, context.row_counts[table_name] + 1):
                value = int(
                    generator._value_for(
                        context,
                        table_name,
                        column,
                        row_number,
                    )
                )
                assert lower <= value <= upper, (
                    table_name,
                    column["name"],
                    value,
                )


def test_retail_banking_committed_ods_matches_generator():
    generator = _load_module(
        "retail_ods_fixture_content_validator",
        PROJECT_DIR / "generate_ods_data.py",
    )
    snapshot = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    context = generator._build_context(snapshot, mapping)
    data_dir = PROJECT_DIR / "ods/data/internal/retail_banking_dm"

    for item in mapping["mappings"]:
        source_table = item["source_table"]
        expected = generator._render_insert(
            item,
            context.schemas[source_table],
            context.row_counts[source_table],
            context,
        )
        assert (data_dir / f"{item['ods_table']}.sql").read_text(
            encoding="utf-8"
        ) == expected


def test_retail_banking_gl_fixture_balances_by_transaction_and_date():
    generator = _load_module(
        "retail_ods_gl_fixture_generator",
        PROJECT_DIR / "generate_ods_data.py",
    )
    snapshot = _load_yaml(MAPPINGS_DIR / "fineract_schema_snapshot.yaml")
    mapping = _load_yaml(MAPPINGS_DIR / "fineract_table_mapping.yaml")
    context = generator._build_context(snapshot, mapping)
    table_name = "acc_gl_journal_entry"
    columns = context.columns[table_name]
    row_count = context.row_counts[table_name]
    balances = defaultdict(Decimal)

    for row_number in range(1, row_count + 1):
        key = tuple(
            generator._value_for(
                context, table_name, columns[column_name], row_number
            )
            for column_name in (
                "entry_date",
                "transaction_id",
                "currency_code",
            )
        )
        type_enum = generator._value_for(
            context, table_name, columns["type_enum"], row_number
        )
        amount = Decimal(
            generator._value_for(
                context, table_name, columns["amount"], row_number
            )
        )
        assert type_enum in {"1", "2"}
        balances[key] += amount if type_enum == "1" else -amount

    assert row_count % 2 == 0
    assert len(balances) == row_count // 2
    assert set(balances.values()) == {Decimal("0")}
    assert {key[0] for key in balances} == {
        f"'{(date(2026, 5, 14) + timedelta(days=offset)).isoformat()}'"
        for offset in range(62)
    }


def test_retail_banking_private_gold_is_external_and_fully_validated(tmp_path):
    generator = _load_tool("retail_asset_generator", "generate_assets.py")
    builder = _load_tool(
        "retail_bundle_builder_gold", "build_benchmark_bundle.py"
    )
    gold_path = tmp_path / "private_gold.yaml"
    input_manifest = PROJECT_DIR / "benchmark/input_manifest.yaml"
    manifest_content = input_manifest.read_bytes()
    manifest_mtime = input_manifest.stat().st_mtime_ns

    generator.generate_private_gold(gold_path)
    gold = builder.validate_private_gold(gold_path)

    assert input_manifest.read_bytes() == manifest_content
    assert input_manifest.stat().st_mtime_ns == manifest_mtime
    assert not (PROJECT_DIR / "benchmark/private_gold.yaml").exists()
    assert gold["status"] == "candidate_not_gold_v1"
    assert gold["schema"] == "benchmark_contract.yaml#table_record"
    assert len(gold["records"]) == 412
    assert len({record["asset_id"] for record in gold["records"]}) == 412

    legacy_schema_gold = copy.deepcopy(gold)
    legacy_schema_gold["schema"] = "gold_schema.yaml#table_record"
    legacy_schema_path = tmp_path / "legacy_schema_private_gold.yaml"
    legacy_schema_path.write_text(
        yaml.safe_dump(
            legacy_schema_gold,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert builder.validate_private_gold(legacy_schema_path)["schema"] == (
        "gold_schema.yaml#table_record"
    )

    by_asset = {record["asset_name"]: record for record in gold["records"]}
    expected_alternatives = {
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
    for asset_name, expected in expected_alternatives.items():
        alternatives = by_asset[asset_name]["expected"]["allowed_alternatives"]
        assert {
            (
                item["name"],
                item["layer"],
                item["table_type"],
                item["credit"],
            )
            for item in alternatives
        } == expected

    legacy_alternative = by_asset["dim_address"]["expected"][
        "allowed_alternatives"
    ]
    assert legacy_alternative == [
        {
            "name": "customer_address_satellite",
            "layer": "DIM",
            "table_type": "dimension",
            "credit": 0.5,
            "rationale": (
                "Adjudicated architecture alternative: "
                "customer_address_satellite"
            ),
        }
    ]

    invalid_gold = copy.deepcopy(gold)
    invalid_gold["records"][0]["metrics"][0]["class"] = "hallucinated"
    invalid_path = tmp_path / "invalid_private_gold.yaml"
    invalid_path.write_text(
        yaml.safe_dump(invalid_gold, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="is not in enum"):
        builder.validate_private_gold(invalid_path)

    missing_alternative_name = copy.deepcopy(gold)
    alternative = next(
        item
        for record in missing_alternative_name["records"]
        for item in record["expected"]["allowed_alternatives"]
    )
    del alternative["name"]
    missing_alternative_name_path = tmp_path / "missing_alternative_name.yaml"
    missing_alternative_name_path.write_text(
        yaml.safe_dump(
            missing_alternative_name,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required fields.*name"):
        builder.validate_private_gold(missing_alternative_name_path)

    invalid_evidence = copy.deepcopy(gold)
    first_record = invalid_evidence["records"][0]
    first_record["evidence"]["ddl_paths"] = [
        f"ads/models/{first_record['asset_name']}.yaml"
    ]
    invalid_evidence_path = tmp_path / "invalid_evidence_gold.yaml"
    invalid_evidence_path.write_text(
        yaml.safe_dump(invalid_evidence, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not a registered DDL asset"):
        builder.validate_private_gold(invalid_evidence_path)

    invalid_task_evidence = copy.deepcopy(gold)
    invalid_task_evidence["records"][0]["evidence"]["task_paths"] = [
        "README.md"
    ]
    invalid_task_path = tmp_path / "invalid_task_evidence_gold.yaml"
    invalid_task_path.write_text(
        yaml.safe_dump(
            invalid_task_evidence, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must exactly match"):
        builder.validate_private_gold(invalid_task_path)

    missing_task_evidence = copy.deepcopy(gold)
    missing_task_evidence["records"][0]["evidence"]["task_paths"] = []
    missing_task_path = tmp_path / "missing_task_evidence_gold.yaml"
    missing_task_path.write_text(
        yaml.safe_dump(
            missing_task_evidence, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must exactly match"):
        builder.validate_private_gold(missing_task_path)

    repository_gold = PROJECT_DIR.parents[1] / "tests/private_gold.yaml"
    with pytest.raises(ValueError, match="outside the Git checkout"):
        generator.generate_private_gold(repository_gold)
    with pytest.raises(ValueError, match="outside the Git checkout"):
        builder.validate_private_gold(repository_gold)


def test_prefixless_bundle_physically_separates_answers(tmp_path):
    module = _load_tool("retail_bundle_builder", "build_benchmark_bundle.py")
    generator = _load_tool(
        "retail_asset_generator_bundle", "generate_assets.py"
    )
    output = tmp_path / "bundle"
    private_gold = tmp_path / "private_gold.yaml"
    generator.generate_private_gold(private_gold)
    legacy_gold = _load_yaml(private_gold)
    legacy_gold["schema"] = "gold_schema.yaml#table_record"
    private_gold.write_text(
        yaml.safe_dump(legacy_gold, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    module.build_bundle(
        output=output,
        track="prefixless_role_blind",
        force=False,
        private_gold=private_gold,
    )

    manifest = _load_yaml(output / "public/manifest.json")
    public_sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((output / "public").rglob("*.sql"))
    )
    assert manifest["counts"] == {"ddl": 412, "tasks": 135}
    assert manifest["constraint_counts"]["tables"] == 412
    assert manifest["constraint_counts"]["unique_constraints"] == 118
    assert manifest["constraint_counts"]["foreign_keys"] == 561
    assert manifest["constraint_counts"]["external_foreign_keys"] == 2
    assert manifest["constraint_counts"]["source_foreign_keys"] == 563
    assert manifest["evaluator_gold_included"] is True
    assert not re.search(
        r"\b(?:ods|dim|dwd|dws|ads)_[a-z0-9_]+", public_sql, re.I
    )
    assert not any(
        line.lstrip().startswith("--") for line in public_sql.splitlines()
    )
    assert not list((output / "public").rglob("*gold*"))
    assert (output / "evaluator/private_gold.yaml").exists()
    assert (output / "evaluator/benchmark_contract.yaml").exists()
    assert not (output / "evaluator/gold_schema.yaml").exists()
    evaluator_gold = _load_yaml(output / "evaluator/private_gold.yaml")
    assert evaluator_gold["schema"] == ("benchmark_contract.yaml#table_record")
    assert (output / "evaluator/alias_map.yaml").exists()
    constraints = _load_yaml(output / "public/constraints.yaml")
    aliases = _load_yaml(output / "evaluator/alias_map.yaml")["table_aliases"]
    opaque_names = set(aliases.values())
    assert {item["table"] for item in constraints["tables"]} == opaque_names
    assert all(
        foreign_key["referenced_table"] in opaque_names
        for table in constraints["tables"]
        for foreign_key in table["foreign_keys"]
    )
    external_foreign_keys = [
        foreign_key
        for table in constraints["tables"]
        for foreign_key in table["external_foreign_keys"]
    ]
    assert len(external_foreign_keys) == 2
    assert all(
        foreign_key["referenced_external_table"].startswith("external_asset_")
        for foreign_key in external_foreign_keys
    )
    assert "batch_job_execution" not in yaml.safe_dump(constraints)


def test_bundle_omits_private_gold_without_external_input(tmp_path):
    module = _load_tool(
        "retail_bundle_builder_public_only", "build_benchmark_bundle.py"
    )
    output = tmp_path / "public_only_bundle"

    module.build_bundle(
        output=output, track="named_taxonomy_assisted", force=False
    )

    manifest = _load_yaml(output / "public/manifest.json")
    assert manifest["evaluator_gold_included"] is False
    assert (output / "public/constraints.yaml").exists()
    assert not (output / "evaluator/private_gold.yaml").exists()

    repository_output = PROJECT_DIR.parents[1] / "work/benchmark_bundle"
    with pytest.raises(ValueError, match="outside the Git checkout"):
        module.build_bundle(
            output=repository_output,
            track="named_taxonomy_assisted",
            force=False,
        )
