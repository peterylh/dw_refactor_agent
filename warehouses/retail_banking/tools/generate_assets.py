#!/usr/bin/env python3
"""Generate Doris assets from the reviewed Fineract mapping manifest."""

from __future__ import annotations

import argparse
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

LOGGER = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parents[1]
DATABASE = "retail_banking_dm"
CATALOG = "internal"
TEXT_ENCODING = "utf-8"
SEMANTIC_SPEC_DIR = PROJECT_DIR / "semantic_specs"
BENCHMARK_CONTRACT_FILENAME = "benchmark_contract.yaml"
PRIVATE_GOLD_SCHEMA_REFERENCE = f"{BENCHMARK_CONTRACT_FILENAME}#table_record"
ODS_REFERENCE_PATTERN = re.compile(
    r"\b(?:from|join)\s+(?:`?[a-z0-9_]+`?\.)?`?"
    r"(ods_fineract_[a-z0-9_]+)`?",
    re.I,
)

DWS_DEFINITIONS = (
    (
        "dws_gl_journal_posting_daily",
        "dwd_gl_journal_entry",
        "entry_date",
        ("office_id", "account_id", "currency_code", "type_enum"),
        ("amount",),
        "`reversed` = FALSE",
    ),
    (
        "dws_loan_transaction_daily",
        "dwd_loan_transaction",
        "transaction_date",
        ("office_id", "loan_id", "transaction_type_enum"),
        (
            "amount",
            "principal_portion_derived",
            "interest_portion_derived",
            "fee_charges_portion_derived",
            "penalty_charges_portion_derived",
        ),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_loan_installment_due_daily",
        "dwd_loan_installment",
        "duedate",
        ("loan_id",),
        (
            "principal_amount",
            "interest_amount",
            "fee_charges_amount",
            "penalty_charges_amount",
        ),
        "1 = 1",
    ),
    (
        "dws_loan_installment_charge_due_daily",
        "dwd_loan_installment_charge",
        "due_date",
        ("loan_charge_id",),
        (
            "amount",
            "amount_paid_derived",
            "amount_waived_derived",
            "amount_writtenoff_derived",
            "amount_outstanding_derived",
        ),
        "1 = 1",
    ),
    (
        "dws_loan_disbursement_daily",
        "dwd_loan_disbursement",
        "disbursedon_date",
        ("loan_id",),
        ("principal", "net_disbursal_amount"),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_loan_delinquency_event_daily",
        "dwd_loan_delinquency_event",
        "addedon_date",
        ("loan_id", "delinquency_range_id"),
        (),
        "1 = 1",
    ),
    (
        "dws_loan_provision_entry_daily",
        "dwd_loan_provision_entry",
        "provision_date",
        (
            "office_id",
            "product_id",
            "category_id",
            "currency_code",
            "journal_entry_created",
        ),
        ("reseve_amount",),
        "1 = 1",
    ),
    (
        "dws_collection_action_daily",
        "dwd_collection_action",
        "start_date",
        ("loan_id", "action"),
        (),
        "1 = 1",
    ),
    (
        "dws_deposit_transaction_daily",
        "dwd_deposit_transaction",
        "transaction_date",
        ("office_id", "savings_account_id", "transaction_type_enum"),
        ("amount", "overdraft_amount_derived"),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_deposit_hold_event_daily",
        "dwd_deposit_hold_event",
        "transaction_date",
        ("savings_account_id", "transaction_type_enum"),
        ("amount",),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_account_transfer_transaction_daily",
        "dwd_account_transfer_transaction",
        "transaction_date",
        ("account_transfer_details_id", "currency_code"),
        ("amount",),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_cashier_transaction_daily",
        "dwd_cashier_transaction",
        "txn_date",
        ("cashier_id", "currency_code", "txn_type"),
        ("txn_amount",),
        "1 = 1",
    ),
    (
        "dws_office_cash_transfer_daily",
        "dwd_office_cash_transfer",
        "transaction_date",
        ("from_office_id", "to_office_id", "currency_code"),
        ("transaction_amount",),
        "1 = 1",
    ),
    (
        "dws_client_transaction_daily",
        "dwd_client_transaction",
        "transaction_date",
        ("office_id", "client_id", "currency_code", "transaction_type_enum"),
        ("amount",),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_share_transaction_daily",
        "dwd_share_transaction",
        "transaction_date",
        ("account_id", "type_enum", "status_enum"),
        ("total_shares", "amount", "charge_amount", "amount_paid"),
        "`is_active` = TRUE",
    ),
    (
        "dws_loan_ownership_transfer_daily",
        "dwd_loan_ownership_transfer",
        "settlement_date",
        ("owner_id", "loan_id", "status"),
        (),
        "1 = 1",
    ),
    (
        "dws_wc_loan_transaction_daily",
        "dwd_wc_loan_transaction",
        "transaction_date",
        ("wc_loan_id", "transaction_type_id"),
        ("transaction_amount",),
        "`is_reversed` = FALSE",
    ),
    (
        "dws_wc_breach_event_daily",
        "dwd_wc_breach_event",
        "start_date",
        ("wc_loan_id", "action"),
        (),
        "1 = 1",
    ),
)

ADS_NAMES = {
    "dws_gl_journal_posting_daily": "ads_gl_posting_monitor_daily",
    "dws_loan_transaction_daily": "ads_loan_transaction_monitor_daily",
    "dws_loan_installment_due_daily": "ads_repayment_schedule_daily",
    "dws_loan_disbursement_daily": "ads_disbursement_monitor_daily",
    "dws_loan_provision_entry_daily": "ads_provision_posting_monitor_daily",
    "dws_deposit_transaction_daily": "ads_deposit_transaction_monitor_daily",
    "dws_deposit_hold_event_daily": "ads_deposit_hold_monitor_daily",
    "dws_account_transfer_transaction_daily": "ads_internal_transfer_monitor_daily",
    "dws_cashier_transaction_daily": "ads_cashier_operation_daily",
    "dws_office_cash_transfer_daily": "ads_branch_cash_transfer_daily",
    "dws_client_transaction_daily": "ads_customer_transaction_monitor_daily",
    "dws_share_transaction_daily": "ads_share_transaction_monitor_daily",
    "dws_wc_loan_transaction_daily": "ads_wc_transaction_monitor_daily",
}

CORE_ENRICHMENT_JOINS = {
    "dwd_loan_transaction": (
        ("ods_fineract_m_loan", "loan_id", "id"),
        ("ods_fineract_m_office", "office_id", "id"),
    ),
    "dwd_loan_installment": (("ods_fineract_m_loan", "loan_id", "id"),),
    "dwd_loan_disbursement": (("ods_fineract_m_loan", "loan_id", "id"),),
    "dwd_loan_charge": (("ods_fineract_m_loan", "loan_id", "id"),),
    "dwd_deposit_transaction": (
        ("ods_fineract_m_savings_account", "savings_account_id", "id"),
        ("ods_fineract_m_office", "office_id", "id"),
    ),
    "dwd_deposit_charge": (
        ("ods_fineract_m_savings_account", "savings_account_id", "id"),
    ),
    "dwd_deposit_hold_event": (
        ("ods_fineract_m_savings_account", "savings_account_id", "id"),
    ),
    "dwd_gl_journal_entry": (
        ("ods_fineract_acc_gl_account", "account_id", "id"),
        ("ods_fineract_m_office", "office_id", "id"),
    ),
    "dwd_loan_provision_entry": (
        ("ods_fineract_m_office", "office_id", "id"),
        ("ods_fineract_m_provision_category", "category_id", "id"),
        ("ods_fineract_acc_gl_account", "liability_account", "id"),
        ("ods_fineract_acc_gl_account", "expense_account", "id"),
    ),
}

DOMAIN_IDS = {
    "CUST": "01",
    "ORGN": "02",
    "PROD": "03",
    "LOAN": "04",
    "DPST": "05",
    "PAYM": "06",
    "FINA": "07",
    "RISK": "08",
    "INVS": "09",
    "WCLN": "10",
    "CHNL": "11",
    "REFR": "12",
    "OPER": "13",
    "OTHR": "99",
}


@dataclass(frozen=True)
class SummarySpec:
    name: str
    source_table: str
    source_mapping: dict
    date_column: str
    group_columns: list[str]
    measure_columns: list[str]
    where_clause: str


class IdentityRegistry:
    """Persistent UUID4 registry used to keep generated schema IDs stable."""

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
        else:
            data = {}
        self.data = data if isinstance(data, dict) else {}
        self.data.setdefault("version", 1)
        self.data.setdefault("tables", {})

    def table_id(self, table_name: str) -> str:
        entry = self.data["tables"].setdefault(table_name, {})
        entry.setdefault("table_id", str(uuid.uuid4()))
        entry.setdefault("columns", {})
        return entry["table_id"]

    def column_id(self, table_name: str, column_name: str) -> str:
        entry = self.data["tables"].setdefault(table_name, {})
        entry.setdefault("table_id", str(uuid.uuid4()))
        columns = entry.setdefault("columns", {})
        columns.setdefault(column_name, str(uuid.uuid4()))
        return columns[column_name]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                self.data, allow_unicode=True, sort_keys=True, width=100
            ),
            encoding=TEXT_ENCODING,
        )

    def prune_tables(self, active_table_names: set[str]) -> None:
        self.data["tables"] = {
            name: entry
            for name, entry in self.data["tables"].items()
            if name in active_table_names
        }


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def _dim_dwd_specs() -> tuple[dict[str, dict], dict[str, str]]:
    payload = _load_yaml(SEMANTIC_SPEC_DIR / "dim_dwd.yaml")
    entries = payload.get("entries") or []
    active = {
        str(entry["source_table"]): entry
        for entry in entries
        if entry.get("active_mapping", True) and entry.get("materialize")
    }
    aliases = {
        str(entry.get("current_target")): str(entry["target_table"])
        for entry in entries
        if entry.get("current_target") and entry.get("materialize")
    }
    return active, aliases


def _dws_ads_specs() -> dict:
    return _load_yaml(SEMANTIC_SPEC_DIR / "dws_ads.yaml")


def _column_sensitivity(column_name: str, table_level: str) -> Optional[dict]:
    if table_level != "restricted":
        return None
    name = column_name.lower()
    if any(
        token in name
        for token in ("password", "token", "secret", "credential")
    ):
        return {
            "name": column_name,
            "classification": "secret",
            "action": "redact",
        }
    if any(
        token in name
        for token in (
            "email",
            "mobile",
            "phone",
            "account_no",
            "account_number",
            "national_id",
            "identifier",
            "external_id",
            "routing_code",
            "bank_number",
            "check_number",
        )
    ):
        return {
            "name": column_name,
            "classification": "identifier",
            "action": "hash",
        }
    if name == "id" or name.endswith("_id"):
        return None
    if any(
        token in name
        for token in (
            "firstname",
            "first_name",
            "middlename",
            "middle_name",
            "lastname",
            "last_name",
            "fullname",
            "full_name",
            "display_name",
            "address",
            "street",
            "town",
            "city",
            "county",
            "postal",
            "zip",
            "latitude",
            "longitude",
            "date_of_birth",
            "dob",
            "note",
            "comment",
            "description",
        )
    ):
        return {"name": column_name, "classification": "pii", "action": "mask"}
    return None


def _protected_columns(columns: list[dict], table_level: str) -> list[dict]:
    return [
        policy
        for column in columns
        for policy in [_column_sensitivity(column["name"], table_level)]
        if policy is not None
    ]


def _protected_ddl_columns(
    columns: list[dict], table_level: str
) -> list[dict]:
    policies = {
        item["name"]: item for item in _protected_columns(columns, table_level)
    }
    result = []
    for column in columns:
        value = dict(column)
        action = (policies.get(column["name"]) or {}).get("action")
        if action == "hash":
            value["source_type"] = "VARCHAR(64)"
        elif action in {"mask", "redact"}:
            value["source_type"] = "VARCHAR(256)"
        result.append(value)
    return result


def _doris_type(source_type: str) -> str:
    normalized = " ".join(str(source_type).strip().upper().split())
    normalized = re.sub(r"\s+NULL$", "", normalized)
    if normalized.startswith("DECIMAL"):
        match = re.search(
            r"DECIMAL\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)", normalized
        )
        if match:
            precision = min(int(match.group(1)), 38)
            scale = min(int(match.group(2) or 0), precision)
            return f"DECIMAL({precision},{scale})"
        return "DECIMAL(38,6)"
    if normalized.startswith("VARCHAR") or normalized.startswith("CHAR"):
        match = re.search(r"\((\d+)\)", normalized)
        if match and int(match.group(1)) <= 65533:
            return f"VARCHAR({int(match.group(1))})"
        return "STRING"
    if normalized in {"BIGINT"}:
        return "BIGINT"
    if normalized in {"INT", "INTEGER", "SMALLINT", "TINYINT"}:
        return normalized if normalized != "INTEGER" else "INT"
    if normalized == "BOOLEAN":
        return "BOOLEAN"
    if normalized == "DATE":
        return "DATE"
    if "TIMESTAMP" in normalized or "DATETIME" in normalized:
        return "DATETIME"
    if normalized in {"FLOAT", "DOUBLE", "DOUBLE PRECISION"}:
        return "DOUBLE"
    if normalized == "UUID":
        return "VARCHAR(36)"
    return "STRING"


def _comment(value: str) -> str:
    return str(value).replace("'", "''")


def _key_columns(columns: list[dict]) -> list[str]:
    primary = [
        column["name"] for column in columns if column["is_primary_key"]
    ]
    if primary:
        return primary[:8]
    if any(column["name"] == "id" for column in columns):
        return ["id"]
    return [columns[0]["name"]]


def _render_ddl(
    *,
    table_name: str,
    columns: list[dict],
    registry: IdentityRegistry,
    description: str,
) -> str:
    if not columns:
        raise ValueError(f"Cannot render table without columns: {table_name}")
    key_columns = _key_columns(columns)
    key_column_set = set(key_columns)
    columns_by_name = {column["name"]: column for column in columns}
    ordered_columns = [columns_by_name[name] for name in key_columns]
    ordered_columns.extend(
        column for column in columns if column["name"] not in key_column_set
    )
    lines = [
        f"-- {description}",
        f"DROP TABLE IF EXISTS {DATABASE}.{table_name};",
        f"-- table_id: {registry.table_id(table_name)}",
        f"CREATE TABLE IF NOT EXISTS {DATABASE}.{table_name} (",
    ]
    rendered_columns = []
    for column in ordered_columns:
        name = column["name"]
        nullable = "NULL" if column.get("nullable", True) else "NOT NULL"
        remarks = column.get("remarks") or f"Fineract source column {name}"
        rendered_columns.extend(
            [
                f"    -- column_id: {registry.column_id(table_name, name)}",
                "    `{name}` {data_type} {nullable} COMMENT '{remarks}'".format(
                    name=name,
                    data_type=_doris_type(column["source_type"]),
                    nullable=nullable,
                    remarks=_comment(remarks),
                ),
            ]
        )
    for index in range(1, len(rendered_columns), 2):
        if index < len(rendered_columns) - 1:
            rendered_columns[index] += ","
    lines.extend(rendered_columns)
    quoted_keys = ", ".join(f"`{name}`" for name in key_columns)
    lines.extend(
        [
            ") ENGINE=OLAP",
            f"DUPLICATE KEY({quoted_keys})",
            f"DISTRIBUTED BY HASH(`{key_columns[0]}`) BUCKETS 1",
            'PROPERTIES ("replication_num" = "1");',
            "",
        ]
    )
    return "\n".join(lines)


def _with_technical_column(
    columns: list[dict], *, name: str, source_type: str
) -> list[dict]:
    result = [dict(column) for column in columns]
    result.append(
        {
            "name": name,
            "source_type": source_type,
            "nullable": False,
            "is_primary_key": False,
            "remarks": "数仓技术时间",
        }
    )
    return result


def _write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=100),
        encoding=TEXT_ENCODING,
    )


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding=TEXT_ENCODING)


def _clear_generated_files(paths: list[Path]) -> None:
    for root in paths:
        if not root.exists():
            continue
        for path in root.glob("*.sql"):
            path.unlink()
        for path in root.glob("*.yaml"):
            path.unlink()


def _entity_code(table_name: str) -> str:
    normalized = table_name
    for prefix in ("dim_", "dwd_", "dws_", "ads_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return re.sub(r"[^A-Z0-9]", "_", normalized.upper())[:48]


def _column_entity_code(column_name: str) -> str:
    normalized = re.sub(
        r"_(?:id|key|no|enum)$", "", column_name, flags=re.IGNORECASE
    )
    return re.sub(r"[^A-Z0-9]", "_", normalized.upper())[:48]


def _is_count_metric_name(column_name: str) -> bool:
    return bool(
        re.search(
            r"(?:^|_)(?:count|counter)(?:_|$)", column_name, re.IGNORECASE
        )
    )


def _supports_dwd_daily_slice(
    semantic_spec: dict,
    columns: list[dict],
) -> bool:
    """Return whether a DWD target has a resolvable daily business date."""
    date_spec = semantic_spec.get("business_date") or {}
    if (
        date_spec.get("kind") == "generated_snapshot"
        or date_spec.get("inherit_from") == "etl_context.etl_date"
    ):
        return True
    if date_spec.get("inherit_from"):
        return True
    source_names = {str(column.get("name")) for column in columns}
    return bool(date_spec.get("column") in source_names)


def _full_refresh_window_setup() -> str:
    return (
        "SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());\n"
        "SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);\n\n"
    )


def _full_refresh_window_predicate(date_expression: str) -> str:
    return (
        f"({date_expression} IS NULL OR ("
        f"{date_expression} >= CAST(@etl_start_date AS DATE) AND "
        f"{date_expression} <= CAST(@etl_end_date AS DATE)))"
    )


def _model(
    *,
    mapping: dict,
    table_name: str,
    layer: str,
    columns: list[dict],
    semantic_spec: Optional[dict] = None,
) -> dict:
    semantic_spec = semantic_spec or {}
    key_columns = list(
        (semantic_spec.get("grain") or {}).get("columns")
        or _key_columns(columns)
    )
    primary = semantic_spec.get("primary_entity") or {
        "code": _entity_code(table_name),
        "key_columns": _key_columns(columns),
    }
    physical_columns = {column["name"] for column in columns}
    related_entities = [
        item
        for item in semantic_spec.get("related_entities") or []
        if set(item.get("key_columns") or []) <= physical_columns
    ]
    hierarchy_roles = [
        item
        for item in related_entities
        if item.get("entity") == primary["code"]
    ]
    entities = [
        {
            "code": primary["code"],
            "type": "primary",
            "name": str(primary["code"]).replace("_", " ").title(),
            "key_columns": list(primary.get("key_columns") or []),
        }
    ]
    entities.extend(
        {
            "code": item["entity"],
            "type": "foreign",
            "role": item["role"],
            "name": str(item["entity"]).replace("_", " ").title(),
            "key_columns": list(item.get("key_columns") or []),
            "source_fk": list(item.get("source_fk") or []),
        }
        for item in related_entities
        if item.get("entity") != primary["code"]
    )
    sensitivity = semantic_spec.get("sensitivity") or {
        "level": mapping.get("sensitivity", "internal"),
        "action": "retain",
    }
    sensitivity_level = (
        sensitivity.get("level", "internal")
        if isinstance(sensitivity, dict)
        else str(sensitivity)
    )
    business_date_spec = semantic_spec.get("business_date") or {}
    target_business_date_column = (
        "business_date"
        if "business_date" in physical_columns
        else "provision_date"
        if table_name == "dwd_loan_provision_entry"
        else business_date_spec.get("column")
        if business_date_spec.get("column") in physical_columns
        else None
    )
    model_business_date = {
        **business_date_spec,
        "source_column": business_date_spec.get("column"),
        "column": target_business_date_column,
    }
    is_etl_snapshot = (
        business_date_spec.get("kind") == "generated_snapshot"
        or business_date_spec.get("inherit_from") == "etl_context.etl_date"
    )
    supports_daily_slice = (
        layer == "DWD"
        and bool(target_business_date_column)
        and _supports_dwd_daily_slice(semantic_spec, columns)
    )
    if supports_daily_slice:
        execution = {
            "materialized": "incremental",
            "full_refresh_strategy": (
                "legacy_full_refresh" if is_etl_snapshot else "companion"
            ),
            "slice": {
                "param": "etl_date",
                "column": target_business_date_column,
                "period": "D",
            },
        }
        if is_etl_snapshot:
            execution.update(
                {
                    "snapshot_mode": "current_state_capture",
                    "historical_replay_supported": False,
                    "source_contract": "ODS current state at execution time",
                }
            )
        else:
            execution.update(
                {
                    "late_arriving_policy": (
                        "replay_original_and_current_business_dates"
                    ),
                    "undated_row_policy": "refresh_on_every_daily_run",
                }
            )
    else:
        execution = {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        }
    value = {
        "version": 2,
        "name": table_name,
        "layer": layer,
        "description": semantic_spec.get("rationale")
        or mapping.get("rationale")
        or mapping.get("domain_name"),
        "table_type": semantic_spec.get("table_type")
        or ("dimension" if layer == "DIM" else "fact"),
        "execution": execution,
        "data_domain": DOMAIN_IDS.get(mapping.get("data_domain"), "99"),
        "business_area": mapping.get("business_area") or "OTHR",
        "entities": entities,
        "grain": {
            "description": (semantic_spec.get("grain") or {}).get(
                "description", mapping.get("grain") or "source row"
            ),
            "columns": list(key_columns),
        },
        "business_date": model_business_date
        or {"kind": "none", "column": None, "inherit_from": None},
        "source_mapping": {
            "upstream_repository": "https://github.com/apache/fineract",
            "source_table": mapping["source_table"],
            "ods_table": mapping["ods_table"],
            "disposition": mapping.get("disposition"),
            "confidence": mapping.get("confidence"),
        },
        "sensitivity": sensitivity_level,
        "sensitivity_policy": sensitivity,
        "column_sensitivity": _protected_columns(columns, sensitivity_level),
        "human_review": {
            "verdict": semantic_spec.get("verdict", "unreviewed"),
            "allowed_alternatives": semantic_spec.get(
                "allowed_alternatives", []
            ),
        },
    }
    if hierarchy_roles:
        value["hierarchy_roles"] = hierarchy_roles
    process = semantic_spec.get("business_process")
    if not process:
        processes = mapping.get("business_processes") or []
        process = processes[0] if processes else None
    if process and layer == "DWD":
        value["business_process"] = process
    if layer == "DIM":
        value["semantic_subject"] = semantic_spec.get(
            "semantic_subject", primary["code"]
        )
        value["dimension_role"] = "BASE"
        value["dimension_content_type"] = "INFO"
        if semantic_spec.get("dimension_policy"):
            value["dimension_policy"] = semantic_spec["dimension_policy"]
    metric_columns = [
        column
        for column in columns
        if not column["name"].lower().endswith("_id")
        and _column_sensitivity(column["name"], sensitivity_level) is None
        and (
            re.search(
                r"\b(?:DECIMAL|NUMERIC|FLOAT|DOUBLE|REAL)\b",
                column["source_type"],
                re.I,
            )
            or (
                re.search(
                    r"\b(?:TINYINT|SMALLINT|INT|BIGINT)\b",
                    column["source_type"],
                    re.I,
                )
                and any(
                    token in column["name"].lower()
                    for token in ("quantity", "shares", "volume")
                )
                or _is_count_metric_name(column["name"])
            )
        )
    ]
    if metric_columns and layer == "DWD":
        value["atomic_metrics"] = [column["name"] for column in metric_columns]
        value["metric_semantics"] = [
            {
                "name": column["name"],
                "class": "atomic",
                "aggregation_behavior": (
                    "non_additive"
                    if any(
                        token in column["name"].lower()
                        for token in ("rate", "percentage", "ratio")
                    )
                    else "semi_additive"
                    if semantic_spec.get("table_type") == "snapshot_fact"
                    or "balance" in column["name"].lower()
                    or "outstanding" in column["name"].lower()
                    else "additive"
                ),
                "formula": column["name"],
                "unit": (
                    "rate"
                    if any(
                        token in column["name"].lower()
                        for token in ("rate", "percentage", "ratio")
                    )
                    else "shares"
                    if "shares" in column["name"].lower()
                    else "count"
                    if _is_count_metric_name(column["name"])
                    or "quantity" in column["name"].lower()
                    else "currency"
                ),
                "currency_source": (
                    "not_applicable"
                    if any(
                        token in column["name"].lower()
                        for token in (
                            "rate",
                            "percentage",
                            "ratio",
                            "shares",
                            "quantity",
                        )
                    )
                    or _is_count_metric_name(column["name"])
                    else "currency_code"
                    if "currency_code" in physical_columns
                    else "account_currency"
                ),
                "additive_over": (
                    []
                    if semantic_spec.get("table_type") == "snapshot_fact"
                    else list(key_columns)
                ),
                "sign": "source_defined",
                "reversal": "source_policy",
            }
            for column in metric_columns
        ]
    return value


def _copy_task(
    *, target_table: str, source_table: str, columns: list[dict]
) -> str:
    column_names = [column["name"] for column in columns]
    insert_columns = ",\n    ".join(
        f"`{name}`" for name in column_names + ["etl_time"]
    )
    joins = CORE_ENRICHMENT_JOINS.get(target_table, ())
    source_alias = "src" if joins else ""
    select_columns = ",\n    ".join(
        f"{source_alias + '.' if source_alias else ''}`{name}`"
        for name in column_names
    )
    from_clause = f"FROM {DATABASE}.{source_table}"
    if joins:
        from_clause += " AS src"
        for index, (dimension, source_key, dimension_key) in enumerate(joins):
            alias = f"dim_{index + 1}"
            from_clause += (
                f"\nLEFT JOIN {DATABASE}.{dimension} AS {alias}"
                f"\n    ON src.`{source_key}` = {alias}.`{dimension_key}`"
            )
    return (
        f"-- Target: {DATABASE}.{target_table}\n"
        f"-- Source: {DATABASE}.{source_table}\n"
        "-- Full replay keeps the generated baseline deterministic.\n\n"
        f"TRUNCATE TABLE {DATABASE}.{target_table};\n\n"
        f"INSERT INTO {DATABASE}.{target_table} (\n    {insert_columns}\n)\n"
        f"SELECT\n    {select_columns},\n    CURRENT_TIMESTAMP AS `etl_time`\n"
        f"{from_clause};\n"
    )


def _projection_expression(
    column_name: str, *, table_level: str, source_alias: str = "src"
) -> str:
    policy = _column_sensitivity(column_name, table_level) or {}
    source = f"{source_alias}.`{column_name}`"
    if policy.get("action") == "redact":
        return f"'REDACTED' AS `{column_name}`"
    if policy.get("action") == "hash":
        return (
            f"CASE WHEN {source} IS NULL THEN NULL "
            f"ELSE SHA2(CAST({source} AS STRING), 256) END AS `{column_name}`"
        )
    if policy.get("action") == "mask":
        return (
            f"CASE WHEN {source} IS NULL THEN NULL "
            f"ELSE '***' END AS `{column_name}`"
        )
    return source


def _business_date_join(
    *,
    semantic_spec: dict,
    source_schema: dict,
    schema_tables: dict[str, dict],
    mappings_by_source: dict[str, dict],
) -> tuple[str, str]:
    date_spec = semantic_spec.get("business_date") or {}
    kind = str(date_spec.get("kind") or "none")
    column = str(date_spec.get("column") or "")
    inherit_from = str(date_spec.get("inherit_from") or "")
    source_columns = {item["name"] for item in source_schema["columns"]}
    if kind == "none":
        return "", ""
    if kind == "generated_snapshot" or inherit_from == "etl_context.etl_date":
        return "", "COALESCE(CAST(@etl_date AS DATE), CURDATE())"
    if column and column in source_columns:
        return "", f"DATE(src.`{column}`)"
    if "." not in inherit_from:
        return "", "NULL"
    parent_source, parent_date = inherit_from.rsplit(".", 1)
    parent_schema = schema_tables.get(parent_source)
    parent_mapping = mappings_by_source.get(parent_source)
    if parent_schema is None or parent_mapping is None:
        return "", "NULL"
    known_inherited_joins = {
        (
            "m_external_asset_owner_transfer_details",
            "m_external_asset_owner_transfer",
        ): ("asset_owner_transfer_id", "id"),
    }
    known_keys = known_inherited_joins.get(
        (source_schema["source_table"], parent_source)
    )
    if known_keys:
        source_key, parent_key = known_keys
        return (
            f"LEFT JOIN {DATABASE}.{parent_mapping['ods_table']} AS date_parent\n"
            f"    ON src.`{source_key}` = date_parent.`{parent_key}`",
            f"DATE(date_parent.`{parent_date}`)",
        )
    for foreign_key in source_schema.get("foreign_keys") or []:
        if foreign_key.get("referenced_table") != parent_source:
            continue
        base_columns = foreign_key.get("base_columns") or []
        referenced_columns = foreign_key.get("referenced_columns") or []
        if not base_columns or len(base_columns) != len(referenced_columns):
            continue
        conditions = " AND ".join(
            f"src.`{base}` = date_parent.`{referenced}`"
            for base, referenced in zip(base_columns, referenced_columns)
        )
        join = (
            f"LEFT JOIN {DATABASE}.{parent_mapping['ods_table']} AS date_parent\n"
            f"    ON {conditions}"
        )
        return join, f"DATE(date_parent.`{parent_date}`)"
    for foreign_key in parent_schema.get("foreign_keys") or []:
        if (
            foreign_key.get("referenced_table")
            != source_schema["source_table"]
        ):
            continue
        parent_keys = foreign_key.get("base_columns") or []
        source_keys = foreign_key.get("referenced_columns") or []
        if len(parent_keys) != 1 or len(source_keys) != 1:
            continue
        parent_key = parent_keys[0]
        source_key = source_keys[0]
        join = (
            "LEFT JOIN (\n"
            f"    SELECT `{parent_key}`, MIN(`{parent_date}`) AS `business_date`\n"
            f"    FROM {DATABASE}.{parent_mapping['ods_table']}\n"
            f"    GROUP BY `{parent_key}`\n"
            ") AS date_parent\n"
            f"    ON src.`{source_key}` = date_parent.`{parent_key}`"
        )
        return join, "DATE(date_parent.`business_date`)"
    return "", "NULL"


def _dwd_enrichment(
    *,
    target_table: str,
    schema_tables: dict[str, dict],
    mappings_by_source: dict[str, dict],
) -> Optional[dict]:
    definitions = {
        "dwd_account_transfer_transaction": {
            "parent_source": "m_account_transfer_details",
            "source_key": "account_transfer_details_id",
            "parent_key": "id",
            "fields": ["from_office_id", "to_office_id", "transfer_type"],
        },
        "dwd_loan_installment_charge": {
            "parent_source": "m_loan_charge",
            "source_key": "loan_charge_id",
            "parent_key": "id",
            "fields": ["loan_id"],
        },
    }
    definition = definitions.get(target_table)
    if definition is None:
        return None
    parent_source = definition["parent_source"]
    parent_schema = schema_tables[parent_source]
    parent_mapping = mappings_by_source[parent_source]
    lookup = _column_lookup(parent_schema["columns"])
    return {
        **definition,
        "parent_ods": parent_mapping["ods_table"],
        "columns": [dict(lookup[name]) for name in definition["fields"]],
    }


def _semantic_copy_task(
    *,
    target_table: str,
    source_table: str,
    columns: list[dict],
    semantic_spec: dict,
    source_schema: dict,
    schema_tables: dict[str, dict],
    mappings_by_source: dict[str, dict],
    business_date_output_column: str,
    enrichment: Optional[dict] = None,
    full_refresh: bool = False,
) -> str:
    sensitivity = semantic_spec.get("sensitivity") or {}
    table_level = (
        str(sensitivity.get("level") or "internal")
        if isinstance(sensitivity, dict)
        else str(sensitivity)
    )
    column_names = [column["name"] for column in columns]
    join_sql, date_expression = _business_date_join(
        semantic_spec=semantic_spec,
        source_schema=source_schema,
        schema_tables=schema_tables,
        mappings_by_source=mappings_by_source,
    )
    insert_names = list(column_names)
    select_parts = [
        _projection_expression(name, table_level=table_level)
        for name in column_names
    ]
    if enrichment:
        for column in enrichment["columns"]:
            insert_names.append(column["name"])
            select_parts.append(
                f"enrichment_parent.`{column['name']}` AS `{column['name']}`"
            )
    if business_date_output_column:
        insert_names.append(business_date_output_column)
        select_parts.append(
            f"{date_expression or 'NULL'} AS `{business_date_output_column}`"
        )
    insert_names.append("etl_time")
    select_parts.append("CURRENT_TIMESTAMP AS `etl_time`")
    from_sql = f"FROM {DATABASE}.{source_table} AS src"
    if enrichment:
        from_sql += (
            f"\nLEFT JOIN {DATABASE}.{enrichment['parent_ods']} "
            "AS enrichment_parent\n"
            f"    ON src.`{enrichment['source_key']}` = "
            f"enrichment_parent.`{enrichment['parent_key']}`"
        )
    if join_sql:
        from_sql += f"\n{join_sql}"
    date_spec = semantic_spec.get("business_date") or {}
    is_etl_snapshot = bool(business_date_output_column) and (
        date_spec.get("kind") == "generated_snapshot"
        or date_spec.get("inherit_from") == "etl_context.etl_date"
    )
    supports_daily_slice = bool(
        business_date_output_column
        and date_expression
        and date_expression.upper() != "NULL"
        and _supports_dwd_daily_slice(semantic_spec, source_schema["columns"])
    )
    if supports_daily_slice and full_refresh:
        reset_sql = f"TRUNCATE TABLE {DATABASE}.{target_table};"
        date_filter = "\nWHERE " + _full_refresh_window_predicate(
            date_expression
        )
        parameter_sql = _full_refresh_window_setup()
    elif supports_daily_slice:
        reset_sql = (
            f"DELETE FROM {DATABASE}.{target_table}\n"
            f"WHERE `{business_date_output_column}` = "
            "CAST(@etl_date AS DATE);"
        )
        if not is_etl_snapshot:
            reset_sql += (
                f"\nDELETE FROM {DATABASE}.{target_table}\n"
                f"WHERE `{business_date_output_column}` IS NULL;"
            )
        date_filter = (
            ""
            if is_etl_snapshot
            else (
                f"\nWHERE {date_expression} = CAST(@etl_date AS DATE)"
                f"\n   OR {date_expression} IS NULL"
            )
        )
        parameter_sql = (
            "SET @etl_date = CURDATE();\n\n"
            if is_etl_snapshot
            else "SET @etl_date = COALESCE(@etl_date, CURDATE());\n\n"
        )
    else:
        reset_sql = f"TRUNCATE TABLE {DATABASE}.{target_table};"
        date_filter = ""
        parameter_sql = ""
    return (
        parameter_sql
        + f"-- Human-reviewed semantic target: {DATABASE}.{target_table}\n"
        f"{reset_sql}\n\n"
        f"INSERT INTO {DATABASE}.{target_table} (\n    "
        + ",\n    ".join(f"`{name}`" for name in insert_names)
        + "\n)\nSELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\n{from_sql}{date_filter};\n"
    )


def _provision_entry_columns(source_columns: list[dict]) -> list[dict]:
    columns = [dict(column) for column in source_columns]
    columns.extend(
        [
            {
                "name": "provision_date",
                "source_type": "DATE",
                "nullable": True,
                "is_primary_key": False,
                "remarks": "Provisioning run business date",
            },
            {
                "name": "journal_entry_created",
                "source_type": "BOOLEAN",
                "nullable": True,
                "is_primary_key": False,
                "remarks": "Whether the provisioning run posted journal entries",
            },
        ]
    )
    return columns


def _provision_entry_task(
    *,
    source_table: str,
    source_columns: list[dict],
    full_refresh: bool = False,
) -> str:
    target_table = "dwd_loan_provision_entry"
    source_names = [column["name"] for column in source_columns]
    insert_names = source_names + [
        "provision_date",
        "journal_entry_created",
        "etl_time",
    ]
    select_parts = [f"src.`{name}`" for name in source_names]
    select_parts.extend(
        [
            "DATE(run.`created_date`) AS `provision_date`",
            "run.`journal_entry_created`",
            "CURRENT_TIMESTAMP AS `etl_time`",
        ]
    )
    date_expression = "DATE(run.`created_date`)"
    if full_refresh:
        parameter_sql = _full_refresh_window_setup()
        reset_sql = f"TRUNCATE TABLE {DATABASE}.{target_table};"
        date_filter = "\nWHERE " + _full_refresh_window_predicate(
            date_expression
        )
    else:
        parameter_sql = "SET @etl_date = COALESCE(@etl_date, CURDATE());\n\n"
        reset_sql = (
            f"DELETE FROM {DATABASE}.{target_table}\n"
            "WHERE `provision_date` = CAST(@etl_date AS DATE);\n"
            f"DELETE FROM {DATABASE}.{target_table}\n"
            "WHERE `provision_date` IS NULL;"
        )
        date_filter = (
            f"\nWHERE {date_expression} = CAST(@etl_date AS DATE)"
            f"\n   OR {date_expression} IS NULL"
        )
    return (
        parameter_sql
        + f"-- Provisioning detail enriched with its run header and references\n"
        f"{reset_sql}\n\n"
        f"INSERT INTO {DATABASE}.{target_table} (\n    "
        + ",\n    ".join(f"`{name}`" for name in insert_names)
        + "\n)\nSELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\nFROM {DATABASE}.{source_table} AS src\n"
        + f"LEFT JOIN {DATABASE}.ods_fineract_m_provisioning_history AS run\n"
        + "    ON src.`history_id` = run.`id`\n"
        + f"LEFT JOIN {DATABASE}.ods_fineract_m_office AS office\n"
        + "    ON src.`office_id` = office.`id`\n"
        + f"LEFT JOIN {DATABASE}.ods_fineract_m_provision_category AS category\n"
        + "    ON src.`category_id` = category.`id`\n"
        + f"LEFT JOIN {DATABASE}.ods_fineract_acc_gl_account AS liability_account\n"
        + "    ON src.`liability_account` = liability_account.`id`\n"
        + f"LEFT JOIN {DATABASE}.ods_fineract_acc_gl_account AS expense_account\n"
        + "    ON src.`expense_account` = expense_account.`id`"
        + f"{date_filter};\n"
    )


def generate_ods(
    *,
    schema_tables: dict[str, dict],
    mappings: list[dict],
    registry: IdentityRegistry,
) -> int:
    ddl_root = PROJECT_DIR / "ods/ddl" / CATALOG / DATABASE
    model_root = PROJECT_DIR / "ods/models" / CATALOG / DATABASE
    _clear_generated_files([ddl_root, model_root])
    count = 0
    for mapping in mappings:
        source = schema_tables[mapping["source_table"]]
        columns = _with_technical_column(
            source["columns"], name="load_time", source_type="DATETIME"
        )
        ddl = _render_ddl(
            table_name=mapping["ods_table"],
            columns=columns,
            registry=registry,
            description=(
                f"ODS mirror of Apache Fineract {mapping['source_table']} "
                f"({mapping['domain_name']})"
            ),
        )
        _write(ddl_root / f"{mapping['ods_table']}.sql", ddl)
        model = {
            "version": 2,
            "name": mapping["ods_table"],
            "layer": "ODS",
            "description": f"Fineract {mapping['source_table']} 贴源表",
            "execution": {
                "materialized": "full",
                "full_refresh_strategy": "replace_all",
            },
            "source": {
                "repository": "https://github.com/apache/fineract",
                "table": mapping["source_table"],
                "disposition": mapping["disposition"],
                "confidence": mapping["confidence"],
            },
            "sensitivity": mapping["sensitivity"],
        }
        _write_yaml(model_root / f"{mapping['ods_table']}.yaml", model)
        count += 1
    data_root = PROJECT_DIR / "ods/data" / CATALOG / DATABASE
    data_root.mkdir(parents=True, exist_ok=True)
    _write(
        data_root / "README.md",
        "# ODS data\n\n"
        "DDL, metadata, and fixture SQL cover only Fineract source tables "
        "referenced by generated downstream tasks. Deterministic business-scenario "
        "seed data is generated separately so accounting invariants can be "
        "validated before loading.\n",
    )
    return count


def referenced_ods_tables(task_root: Optional[Path] = None) -> set[str]:
    """Return the ODS tables referenced by generated downstream task SQL."""

    task_root = task_root or PROJECT_DIR / "mid/tasks"
    referenced = set()
    for task_path in task_root.rglob("*.sql"):
        referenced.update(
            match.group(1).lower()
            for match in ODS_REFERENCE_PATTERN.finditer(
                task_path.read_text(encoding=TEXT_ENCODING)
            )
        )
    return referenced


def materialized_ods_mappings(mappings: list[dict]) -> list[dict]:
    """Select only source mirrors that feed a generated downstream task."""

    referenced = referenced_ods_tables()
    mapping_by_ods = {item["ods_table"].lower(): item for item in mappings}
    missing = referenced - set(mapping_by_ods)
    if missing:
        raise ValueError(
            "Downstream tasks reference unknown ODS tables: "
            + ", ".join(sorted(missing))
        )
    declared = {
        item["ods_table"].lower()
        for item in mappings
        if item.get("downstream_targets")
    }
    if declared != referenced:
        raise ValueError(
            "Declared materialized ODS scope does not match downstream task "
            f"references; missing={sorted(referenced - declared)}, "
            f"unused={sorted(declared - referenced)}"
        )
    return [
        item for item in mappings if item["ods_table"].lower() in referenced
    ]


def generate_reviewed_mid(
    *,
    schema_tables: dict[str, dict],
    mappings: list[dict],
    registry: IdentityRegistry,
) -> tuple[int, dict[str, tuple[dict, list[dict]]]]:
    ddl_root = PROJECT_DIR / "mid/ddl"
    model_root = PROJECT_DIR / "mid/models"
    task_root = PROJECT_DIR / "mid/tasks"
    _clear_generated_files(
        [ddl_root, model_root, task_root, task_root / "full_refresh"]
    )
    generated: dict[str, tuple[dict, list[dict]]] = {}
    semantic_specs, _aliases = _dim_dwd_specs()
    mappings_by_source = {item["source_table"]: item for item in mappings}
    for mapping in mappings:
        semantic_spec = semantic_specs.get(mapping["source_table"])
        if semantic_spec is None:
            continue
        target = str(semantic_spec.get("target_table") or "")
        layer = str(semantic_spec.get("target_layer") or "NONE")
        if not target or layer not in {"DIM", "DWD"}:
            continue
        source = schema_tables[mapping["source_table"]]
        source_columns = source["columns"]
        dimension_policy = semantic_spec.get("dimension_policy") or {}
        stable_fields = dimension_policy.get("stable_fields") or []
        if layer == "DIM" and stable_fields:
            source_lookup = {
                column["name"]: column for column in source_columns
            }
            missing = [
                name for name in stable_fields if name not in source_lookup
            ]
            if missing:
                raise ValueError(
                    f"Semantic spec {target} has missing stable fields: {missing}"
                )
            source_columns = [source_lookup[name] for name in stable_fields]
        enrichment = _dwd_enrichment(
            target_table=target,
            schema_tables=schema_tables,
            mappings_by_source=mappings_by_source,
        )
        columns = (
            _provision_entry_columns(source_columns)
            if target == "dwd_loan_provision_entry"
            else source_columns
        )
        if enrichment:
            columns = [dict(column) for column in columns]
            existing_names = {column["name"] for column in columns}
            columns.extend(
                column
                for column in enrichment["columns"]
                if column["name"] not in existing_names
            )
        date_kind = str(
            (semantic_spec.get("business_date") or {}).get("kind") or "none"
        )
        add_business_date = (
            layer == "DWD"
            and date_kind != "none"
            and target != "dwd_loan_provision_entry"
        )
        business_date_output_column = ""
        if add_business_date:
            date_spec = semantic_spec.get("business_date") or {}
            business_date_output_column = (
                str(date_spec.get("column") or "snapshot_date")
                if date_kind == "generated_snapshot"
                else "business_date"
            )
            columns = [dict(column) for column in columns]
            columns.append(
                {
                    "name": business_date_output_column,
                    "source_type": "DATE",
                    "nullable": True,
                    "is_primary_key": False,
                    "remarks": "Standardized business date from the semantic spec",
                }
            )
        sensitivity = semantic_spec.get("sensitivity") or {}
        sensitivity_level = (
            str(sensitivity.get("level") or "internal")
            if isinstance(sensitivity, dict)
            else str(sensitivity)
        )
        ddl_business_columns = _protected_ddl_columns(
            columns, sensitivity_level
        )
        ddl_columns = _with_technical_column(
            ddl_business_columns, name="etl_time", source_type="DATETIME"
        )
        _write(
            ddl_root / f"{target}.sql",
            _render_ddl(
                table_name=target,
                columns=ddl_columns,
                registry=registry,
                description=f"{layer} generated from {mapping['source_table']}",
            ),
        )
        model = _model(
            mapping=mapping,
            table_name=target,
            layer=layer,
            columns=columns,
            semantic_spec=semantic_spec,
        )
        _write_yaml(model_root / f"{target}.yaml", model)
        task_sql = (
            _provision_entry_task(
                source_table=mapping["ods_table"],
                source_columns=source_columns,
            )
            if target == "dwd_loan_provision_entry"
            else _semantic_copy_task(
                target_table=target,
                source_table=mapping["ods_table"],
                columns=source_columns,
                semantic_spec=semantic_spec,
                source_schema=source,
                schema_tables=schema_tables,
                mappings_by_source=mappings_by_source,
                business_date_output_column=business_date_output_column,
                enrichment=enrichment,
            )
        )
        _write(task_root / f"{target}.sql", task_sql)
        if model["execution"]["full_refresh_strategy"] == "companion":
            full_refresh_task = (
                _provision_entry_task(
                    source_table=mapping["ods_table"],
                    source_columns=source_columns,
                    full_refresh=True,
                )
                if target == "dwd_loan_provision_entry"
                else _semantic_copy_task(
                    target_table=target,
                    source_table=mapping["ods_table"],
                    columns=source_columns,
                    semantic_spec=semantic_spec,
                    source_schema=source,
                    schema_tables=schema_tables,
                    mappings_by_source=mappings_by_source,
                    business_date_output_column=business_date_output_column,
                    enrichment=enrichment,
                    full_refresh=True,
                )
            )
            _write(
                task_root / "full_refresh" / f"{target}_full_refresh.sql",
                full_refresh_task,
            )
        generated[target] = (mapping, columns)
        snapshot_policy = dimension_policy.get("snapshot_target") or {}
        if layer == "DIM" and snapshot_policy:
            snapshot_target = str(snapshot_policy["table"])
            snapshot_columns = [dict(column) for column in source["columns"]]
            snapshot_columns.append(
                {
                    "name": "snapshot_date",
                    "source_type": "DATE",
                    "nullable": False,
                    "is_primary_key": True,
                    "remarks": "Warehouse account snapshot date",
                }
            )
            snapshot_mapping = {
                **mapping,
                "target_layer": "DWD",
                "target_table": snapshot_target,
                "business_processes": [
                    "deposit_account_management"
                    if "deposit" in snapshot_target
                    else "share_account_management"
                    if "share" in snapshot_target
                    else "wc_loan_management"
                    if "wc_loan" in snapshot_target
                    else "loan_account_management"
                ],
            }
            snapshot_spec = {
                "verdict": "revise",
                "table_type": "snapshot_fact",
                "primary_entity": semantic_spec["primary_entity"],
                "related_entities": semantic_spec.get("related_entities", []),
                "grain": {
                    "columns": list(
                        semantic_spec["primary_entity"].get("key_columns")
                        or []
                    )
                    + ["snapshot_date"],
                    "description": "one account state per extraction date",
                },
                "business_date": {
                    "kind": "snapshot",
                    "column": "snapshot_date",
                    "inherit_from": "etl_context.etl_date",
                },
                "business_process": snapshot_mapping["business_processes"][0],
                "sensitivity": semantic_spec.get("sensitivity"),
                "allowed_alternatives": [],
                "rationale": "Time-varying account balances split from durable DIM attributes.",
            }
            snapshot_ddl_columns = _with_technical_column(
                _protected_ddl_columns(snapshot_columns, sensitivity_level),
                name="etl_time",
                source_type="DATETIME",
            )
            _write(
                ddl_root / f"{snapshot_target}.sql",
                _render_ddl(
                    table_name=snapshot_target,
                    columns=snapshot_ddl_columns,
                    registry=registry,
                    description=(
                        f"DWD account snapshot generated from {mapping['source_table']}"
                    ),
                ),
            )
            _write_yaml(
                model_root / f"{snapshot_target}.yaml",
                _model(
                    mapping=snapshot_mapping,
                    table_name=snapshot_target,
                    layer="DWD",
                    columns=snapshot_columns,
                    semantic_spec=snapshot_spec,
                ),
            )
            source_projection = [
                _projection_expression(name, table_level=sensitivity_level)
                for name in [column["name"] for column in source["columns"]]
            ]
            insert_names = [column["name"] for column in source["columns"]] + [
                "snapshot_date",
                "etl_time",
            ]
            _write(
                task_root / f"{snapshot_target}.sql",
                "SET @etl_date = CURDATE();\n\n"
                f"DELETE FROM {DATABASE}.{snapshot_target}\n"
                "WHERE `snapshot_date` = CAST(@etl_date AS DATE);\n\n"
                f"INSERT INTO {DATABASE}.{snapshot_target} (\n    "
                + ",\n    ".join(f"`{name}`" for name in insert_names)
                + "\n)\nSELECT\n    "
                + ",\n    ".join(
                    source_projection
                    + [
                        "CAST(@etl_date AS DATE) AS `snapshot_date`",
                        "CURRENT_TIMESTAMP AS `etl_time`",
                    ]
                )
                + f"\nFROM {DATABASE}.{mapping['ods_table']} AS src;\n",
            )
            generated[snapshot_target] = (
                snapshot_mapping,
                snapshot_columns,
            )
    return len(generated), generated


def generate_semantic_subjects(mappings: list[dict]) -> None:
    semantic_specs, _aliases = _dim_dwd_specs()
    subjects = []
    for mapping in mappings:
        spec = semantic_specs.get(mapping["source_table"])
        if spec is None or spec.get("target_layer") != "DIM":
            continue
        target = str(spec["target_table"])
        subject_name = target
        for prefix in ("dim_", "bridge_"):
            if subject_name.startswith(prefix):
                subject_name = subject_name[len(prefix) :]
                break
        code = str(spec.get("semantic_subject") or _entity_code(target))
        subjects.append(
            {
                "code": code,
                "name": subject_name.replace("_", " "),
                "description": (
                    f"{mapping['domain_name']}主数据主题，来源 "
                    f"Fineract {mapping['source_table']}。"
                ),
            }
        )
    _write_yaml(
        PROJECT_DIR / "semantic_subjects.yaml",
        {
            "version": 1,
            "project": "retail_banking",
            "semantic_subjects": subjects,
        },
    )


def _summary_specs(
    generated: dict[str, tuple[dict, list[dict]]],
) -> list[SummarySpec]:
    specs = []
    for definition in DWS_DEFINITIONS:
        name, target, date_column, groups, measures, where_clause = definition
        item = generated.get(target)
        if item is None:
            raise ValueError(f"Reviewed DWS source is not generated: {target}")
        mapping, columns = item
        available = {column["name"] for column in columns}
        required = {date_column, *groups, *measures}
        missing = sorted(required - available)
        if missing:
            raise ValueError(
                f"DWS spec {name} references missing columns: {missing}"
            )
        specs.append(
            SummarySpec(
                name=name,
                source_table=target,
                source_mapping=mapping,
                date_column=date_column,
                group_columns=list(groups),
                measure_columns=list(measures),
                where_clause=where_clause,
            )
        )
    return specs


def _column_lookup(columns: list[dict]) -> dict[str, dict]:
    return {column["name"]: column for column in columns}


def _summary_columns(
    spec: SummarySpec, source_columns: list[dict]
) -> list[dict]:
    lookup = _column_lookup(source_columns)
    columns = [
        {
            "name": "stat_date",
            "source_type": "DATE",
            "nullable": False,
            "is_primary_key": True,
            "remarks": "统计日期",
        }
    ]
    for name in spec.group_columns:
        source = dict(lookup[name])
        source["is_primary_key"] = True
        columns.append(source)
    columns.append(
        {
            "name": "record_count",
            "source_type": "BIGINT",
            "nullable": False,
            "is_primary_key": False,
            "remarks": "明细记录数",
        }
    )
    for name in spec.measure_columns:
        columns.append(
            {
                "name": f"total_{name}",
                "source_type": "DECIMAL(38,6)",
                "nullable": False,
                "is_primary_key": False,
                "remarks": f"{name} 汇总金额",
            }
        )
    return _with_technical_column(
        columns, name="etl_time", source_type="DATETIME"
    )


def _summary_task(spec: SummarySpec) -> str:
    group_select = [f"`{name}`" for name in spec.group_columns]
    select_parts = [
        f"DATE(`{spec.date_column}`) AS `stat_date`"
    ] + group_select
    select_parts.append("COUNT(*) AS `record_count`")
    select_parts.extend(
        f"COALESCE(SUM(`{name}`), 0) AS `total_{name}`"
        for name in spec.measure_columns
    )
    select_parts.append("CURRENT_TIMESTAMP AS `etl_time`")
    insert_names = (
        ["stat_date"]
        + spec.group_columns
        + ["record_count"]
        + [f"total_{name}" for name in spec.measure_columns]
        + ["etl_time"]
    )
    group_by = ["`stat_date`"] + group_select
    return (
        f"-- Daily summary of {DATABASE}.{spec.source_table}\n"
        f"TRUNCATE TABLE {DATABASE}.{spec.name};\n\n"
        f"INSERT INTO {DATABASE}.{spec.name} (\n    "
        + ",\n    ".join(f"`{name}`" for name in insert_names)
        + "\n)\nSELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\nFROM {DATABASE}.{spec.source_table}\n"
        + "WHERE `{}` IS NOT NULL\n  AND ({})\nGROUP BY\n    {};\n".format(
            spec.date_column,
            spec.where_clause,
            ",\n    ".join(group_by),
        )
    )


def _render_reviewed_dws_task(
    *,
    name: str,
    source_names: list[str],
    insert_names: list[str],
    select_parts: list[str],
    joins: str,
    group_by_expressions: list[str],
    parameter_sql: str,
    reset_sql: str,
    conditions: list[str],
    process_table_handoff: Optional[str] = None,
) -> str:
    aggregate_select = (
        "SELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\nFROM {DATABASE}.{source_names[0]} AS src\n"
        + (f"{joins}\n" if joins else "")
        + "WHERE "
        + "\n  AND ".join(conditions)
        + "\nGROUP BY\n    "
        + ",\n    ".join(group_by_expressions)
        + ";\n"
    )
    if process_table_handoff:
        return (
            parameter_sql
            + f"-- Human-reviewed aggregation from {', '.join(source_names)}\n"
            f"DROP TABLE IF EXISTS {DATABASE}.{process_table_handoff};\n\n"
            f"CREATE TABLE {DATABASE}.{process_table_handoff}\n"
            'PROPERTIES ("replication_num" = "1")\n'
            "AS\n"
            + aggregate_select
            + "\n"
            + reset_sql
            + "\n\n"
            + f"INSERT INTO {DATABASE}.{name} (\n    "
            + ",\n    ".join(f"`{item}`" for item in insert_names)
            + "\n)\nSELECT\n    "
            + ",\n    ".join(f"src.`{item}`" for item in insert_names)
            + f"\nFROM {DATABASE}.{process_table_handoff} AS src;\n"
        )
    return (
        parameter_sql
        + f"-- Human-reviewed aggregation from {', '.join(source_names)}\n"
        f"{reset_sql}\n\n"
        f"INSERT INTO {DATABASE}.{name} (\n    "
        + ",\n    ".join(f"`{item}`" for item in insert_names)
        + "\n)\n"
        + aggregate_select
    )


def generate_summaries(
    *,
    generated_mid: dict[str, tuple[dict, list[dict]]],
    registry: IdentityRegistry,
) -> tuple[int, dict[str, tuple[dict, list[dict]]]]:
    """Generate reviewed DWS assets from the explicit semantic contract."""

    def metric_column(metric: dict) -> dict:
        name = str(metric["name"])
        unit = str(metric.get("unit") or "")
        return {
            "name": name,
            "source_type": "BIGINT" if unit == "count" else "DECIMAL(38,6)",
            "nullable": False,
            "is_primary_key": False,
            "remarks": f"{metric.get('class', 'derived')} metric: {metric['formula']}",
        }

    def source_expression(
        column_name: str,
        source_names: list[str],
        source_columns: list[dict[str, dict]],
    ) -> str:
        for index, columns in enumerate(source_columns):
            if column_name in columns:
                return f"src{'_' + str(index + 1) if index else ''}.`{column_name}`"
        raise ValueError(
            f"DWS source columns {source_names} do not contain {column_name}"
        )

    def join_sql(source_names: list[str]) -> str:
        if source_names[:2] == [
            "dwd_account_transfer_transaction",
            "dwd_account_transfer_instruction",
        ]:
            return (
                f"LEFT JOIN {DATABASE}.dwd_account_transfer_instruction AS src_2\n"
                "    ON src.`account_transfer_details_id` = src_2.`id`"
            )
        if source_names[:2] == [
            "dwd_loan_installment_charge",
            "dwd_loan_charge",
        ]:
            return (
                f"LEFT JOIN {DATABASE}.dwd_loan_charge AS src_2\n"
                "    ON src.`loan_charge_id` = src_2.`id`"
            )
        return ""

    def filter_sql(
        spec: dict, source_columns: list[dict[str, dict]]
    ) -> list[str]:
        conditions: list[str] = []
        reversals = {str(item.get("reversal")) for item in spec["metrics"]}
        primary = source_columns[0]
        if (
            "exclude_is_reversed_true" in reversals
            and "is_reversed" in primary
        ):
            conditions.append("src.`is_reversed` = FALSE")
        if "exclude_reversed_true" in reversals and "reversed" in primary:
            conditions.append("src.`reversed` = FALSE")
        if "include_is_active_true" in reversals and "is_active" in primary:
            conditions.append("src.`is_active` = TRUE")
        if (
            spec.get("row_policy")
            == "include_only_adjudicated_settlement_statuses"
        ):
            conditions.append("src.`status` IN ('ACTIVE', 'BUYBACK')")
        return conditions

    payload = _dws_ads_specs()
    _active_specs, aliases = _dim_dwd_specs()
    result: dict[str, tuple[dict, list[dict]]] = {}
    for spec in payload.get("dws") or []:
        name = str(spec["name"])
        source_names = [
            aliases.get(str(item), str(item)) for item in spec["source"]
        ]
        source_names = [item for item in source_names if item in generated_mid]
        if not source_names:
            raise ValueError(
                f"Reviewed DWS source is not generated: {spec['source']}"
            )
        source_items = [generated_mid[item] for item in source_names]
        business_date = spec["business_date"]
        date_source = str(business_date["column"])
        date_output = str(business_date.get("output_column") or date_source)
        grain_columns = list(spec["grain"]["columns"])
        primary_columns = _column_lookup(source_items[0][1])
        required_primary_columns = {
            date_source,
            *(
                date_source if item == date_output else item
                for item in grain_columns
            ),
        }
        for metric in spec["metrics"]:
            match = re.fullmatch(
                r"sum\(([A-Za-z0-9_]+)\)", str(metric["formula"]), re.I
            )
            if match:
                required_primary_columns.add(match.group(1))
        if required_primary_columns <= set(primary_columns):
            source_names = source_names[:1]
            source_items = source_items[:1]
        mapping = source_items[0][0]
        source_lookups = [_column_lookup(item[1]) for item in source_items]
        supports_daily_slice = all(
            (
                _load_yaml(PROJECT_DIR / "mid/models" / f"{source_name}.yaml")
                .get("execution", {})
                .get("materialized")
                == "incremental"
            )
            for source_name in source_names
        )
        columns: list[dict] = []
        for column_name in grain_columns:
            if column_name == date_output:
                column = {
                    "name": column_name,
                    "source_type": "DATE",
                    "nullable": False,
                    "is_primary_key": True,
                    "remarks": str(
                        business_date.get("kind") or "business date"
                    ),
                }
            else:
                expression = source_expression(
                    column_name, source_names, source_lookups
                )
                alias_index = 0 if expression.startswith("src.") else 1
                column = dict(source_lookups[alias_index][column_name])
                column["is_primary_key"] = True
            columns.append(column)
        columns.extend(metric_column(metric) for metric in spec["metrics"])
        columns = _with_technical_column(
            columns, name="etl_time", source_type="DATETIME"
        )
        _write(
            PROJECT_DIR / "mid/ddl" / f"{name}.sql",
            _render_ddl(
                table_name=name,
                columns=columns,
                registry=registry,
                description=f"Reviewed aggregate from {', '.join(source_names)}",
            ),
        )
        model = {
            "version": 2,
            "name": name,
            "layer": "DWS",
            "description": f"{mapping['domain_name']} reviewed aggregate",
            "table_type": "aggregate_fact",
            "execution": (
                {
                    "materialized": "incremental",
                    "full_refresh_strategy": "companion",
                    "slice": {
                        "param": "etl_date",
                        "column": date_output,
                        "period": "D",
                    },
                    "late_arriving_policy": (
                        "replay_original_and_current_business_dates"
                    ),
                }
                if supports_daily_slice
                else {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                }
            ),
            "data_domain": DOMAIN_IDS.get(mapping["data_domain"], "99"),
            "business_area": mapping["business_area"],
            "business_process": spec["canonical_process"],
            "sensitivity": mapping.get("sensitivity", "internal"),
            "business_date": business_date,
            "grain": {
                **spec["grain"],
                "entities": [
                    item["code"] for item in spec.get("entities") or []
                ],
                "degenerate_dimensions": spec.get("degenerate_dimensions")
                or [],
                "time_column": date_output,
                "time_period": "D",
            },
            "entities": spec.get("entities") or [],
            "degenerate_dimensions": spec.get("degenerate_dimensions") or [],
            "derived_metrics": spec["metrics"],
            "metric_semantics": spec["metrics"],
            "human_review": {
                "decision": spec["decision"],
                "current_name": spec.get("current_name"),
                "status": payload["status"],
            },
        }
        if spec.get("row_policy"):
            model["row_policy"] = spec["row_policy"]
        _write_yaml(PROJECT_DIR / "mid/models" / f"{name}.yaml", model)

        select_parts: list[str] = []
        group_by_expressions: list[str] = []
        for column_name in grain_columns:
            source_column = (
                date_source if column_name == date_output else column_name
            )
            expression = source_expression(
                source_column, source_names, source_lookups
            )
            if column_name == date_output:
                expression = f"DATE({expression})"
            select_parts.append(f"{expression} AS `{column_name}`")
            group_by_expressions.append(expression)
        for metric in spec["metrics"]:
            formula = str(metric["formula"])
            if formula.lower() == "count(*)":
                expression = "COUNT(*)"
            else:
                match = re.fullmatch(r"sum\(([A-Za-z0-9_]+)\)", formula, re.I)
                if not match:
                    raise ValueError(
                        f"Unsupported DWS formula in {name}: {formula}"
                    )
                expression = (
                    "COALESCE(SUM("
                    + source_expression(
                        match.group(1), source_names, source_lookups
                    )
                    + "), 0)"
                )
            select_parts.append(f"{expression} AS `{metric['name']}`")
        select_parts.append("CURRENT_TIMESTAMP AS `etl_time`")
        insert_names = (
            grain_columns
            + [item["name"] for item in spec["metrics"]]
            + ["etl_time"]
        )
        joins = join_sql(source_names)
        conditions = [
            f"{source_expression(date_source, source_names, source_lookups)} IS NOT NULL",
            *(
                [
                    f"DATE({source_expression(date_source, source_names, source_lookups)}) "
                    "= CAST(@etl_date AS DATE)"
                ]
                if supports_daily_slice
                else []
            ),
            *filter_sql(spec, source_lookups),
        ]
        reset_sql = (
            f"DELETE FROM {DATABASE}.{name}\n"
            f"WHERE `{date_output}` = CAST(@etl_date AS DATE);"
            if supports_daily_slice
            else f"TRUNCATE TABLE {DATABASE}.{name};"
        )
        task = _render_reviewed_dws_task(
            name=name,
            source_names=source_names,
            insert_names=insert_names,
            select_parts=select_parts,
            joins=joins,
            group_by_expressions=group_by_expressions,
            parameter_sql=(
                "SET @etl_date = COALESCE(@etl_date, CURDATE());\n\n"
                if supports_daily_slice
                else ""
            ),
            reset_sql=reset_sql,
            conditions=conditions,
            process_table_handoff=spec.get("process_table_handoff"),
        )
        _write(PROJECT_DIR / "mid/tasks" / f"{name}.sql", task)
        if supports_daily_slice:
            source_date_expression = f"DATE({source_expression(date_source, source_names, source_lookups)})"
            full_conditions = [
                f"{source_expression(date_source, source_names, source_lookups)} IS NOT NULL",
                _full_refresh_window_predicate(source_date_expression),
                *filter_sql(spec, source_lookups),
            ]
            _write(
                PROJECT_DIR
                / "mid/tasks/full_refresh"
                / f"{name}_full_refresh.sql",
                _render_reviewed_dws_task(
                    name=name,
                    source_names=source_names,
                    insert_names=insert_names,
                    select_parts=select_parts,
                    joins=joins,
                    group_by_expressions=group_by_expressions,
                    parameter_sql=_full_refresh_window_setup(),
                    reset_sql=f"TRUNCATE TABLE {DATABASE}.{name};",
                    conditions=full_conditions,
                    process_table_handoff=spec.get("process_table_handoff"),
                ),
            )
        result[name] = (mapping, columns)
    return len(result), result


def _ads_columns(columns: list[dict]) -> tuple[list[dict], list[str]]:
    result = [dict(column) for column in columns]
    measure_names = [
        column["name"]
        for column in columns
        if column["name"].startswith("total_")
    ]
    average_names = []
    etl_index = next(
        index
        for index, column in enumerate(result)
        if column["name"] == "etl_time"
    )
    for measure_name in measure_names:
        average_name = f"average_{measure_name[6:]}"
        result.insert(
            etl_index,
            {
                "name": average_name,
                "source_type": "DECIMAL(38,6)",
                "nullable": False,
                "is_primary_key": False,
                "remarks": f"{measure_name} divided by record_count",
            },
        )
        etl_index += 1
        average_names.append(average_name)
    return result, average_names


def _ads_task(
    *,
    target_table: str,
    source_table: str,
    source_columns: list[dict],
    average_names: list[str],
) -> str:
    source_names = [
        column["name"]
        for column in source_columns
        if column["name"] != "etl_time"
    ]
    insert_names = source_names + average_names + ["etl_time"]
    select_parts = [f"`{name}`" for name in source_names]
    select_parts.extend(
        "CASE WHEN `record_count` = 0 THEN 0 "
        f"ELSE `{name.replace('average_', 'total_', 1)}` / "
        f"`record_count` END AS `{name}`"
        for name in average_names
    )
    select_parts.append("CURRENT_TIMESTAMP AS `etl_time`")
    return (
        f"-- Application metrics derived from {DATABASE}.{source_table}\n"
        f"TRUNCATE TABLE {DATABASE}.{target_table};\n\n"
        f"INSERT INTO {DATABASE}.{target_table} (\n    "
        + ",\n    ".join(f"`{name}`" for name in insert_names)
        + "\n)\nSELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\nFROM {DATABASE}.{source_table};\n"
    )


def _render_reviewed_ads_task(
    *,
    ads_name: str,
    source_name: str,
    insert_names: list[str],
    select_parts: list[str],
    grain_columns: list[str],
    aggregate_query: bool,
    parameter_sql: str,
    reset_sql: str,
    where_sql: str,
) -> str:
    return (
        parameter_sql
        + f"-- Reviewed application metrics derived from {DATABASE}.{source_name}\n"
        f"{reset_sql}\n\n"
        f"INSERT INTO {DATABASE}.{ads_name} (\n    "
        + ",\n    ".join(f"`{name}`" for name in insert_names)
        + "\n)\nSELECT\n    "
        + ",\n    ".join(select_parts)
        + f"\nFROM {DATABASE}.{source_name} AS src"
        + where_sql
        + (
            "\nGROUP BY\n    "
            + ",\n    ".join(f"src.`{name}`" for name in grain_columns)
            if aggregate_query
            else ""
        )
        + ";\n"
    )


def generate_ads(
    *,
    summaries: dict[str, tuple[dict, list[dict]]],
    registry: IdentityRegistry,
) -> tuple[int, set[str]]:
    """Generate reviewed ADS assets, including executable metric formulas."""

    ddl_root = PROJECT_DIR / "ads/ddl"
    model_root = PROJECT_DIR / "ads/models"
    task_root = PROJECT_DIR / "ads/tasks"
    _clear_generated_files(
        [ddl_root, model_root, task_root, task_root / "full_refresh"]
    )
    payload = _dws_ads_specs()
    dws_specs_by_name = {
        str(item["name"]): item for item in payload.get("dws") or []
    }
    generated_names: set[str] = set()
    for spec in payload.get("ads") or []:
        ads_name = str(spec["name"])
        source_names = [str(item) for item in spec["source"]]
        if len(source_names) != 1 or source_names[0] not in summaries:
            raise ValueError(
                f"ADS {ads_name} has unavailable sources: {source_names}"
            )
        dws_name = source_names[0]
        dws_spec = dws_specs_by_name[dws_name]
        task_source_name = str(
            dws_spec.get("process_table_handoff") or dws_name
        )
        item = summaries[dws_name]
        mapping, columns = item
        dws_model = _load_yaml(PROJECT_DIR / "mid/models" / f"{dws_name}.yaml")
        supports_daily_slice = (
            dws_model.get("execution", {}).get("materialized") == "incremental"
        )
        source_lookup = _column_lookup(columns)
        grain_columns = list(spec["grain"]["columns"])
        missing_grain = sorted(set(grain_columns) - set(source_lookup))
        if missing_grain:
            raise ValueError(
                f"ADS {ads_name} has missing grain: {missing_grain}"
            )
        metrics = list(spec["metrics"])
        metrics_by_name = {str(metric["name"]): metric for metric in metrics}
        source_business_names = {
            column["name"]
            for column in columns
            if column["name"] != "etl_time"
        }

        def expand_formula(
            name: str,
            stack: tuple[str, ...] = (),
            *,
            ads_table: str = ads_name,
            metric_specs: dict[str, dict] = metrics_by_name,
            source_columns: set[str] = source_business_names,
        ) -> str:
            if name in stack:
                raise ValueError(
                    f"ADS metric cycle in {ads_table}: {stack + (name,)}"
                )
            formula = str(metric_specs[name]["formula"])
            formula = re.sub(
                r"\bsource\.([A-Za-z_][A-Za-z0-9_]*)\b",
                lambda match: f"src.`{match.group(1)}`",
                formula,
            )
            for dependency in sorted(metric_specs, key=len, reverse=True):
                if dependency == name:
                    continue
                if dependency in source_columns and re.search(
                    r"\bSUM\s*\(", formula, re.I
                ):
                    continue
                if re.search(
                    rf"(?<![.`])\b{re.escape(dependency)}\b", formula
                ):
                    replacement = expand_formula(dependency, stack + (name,))
                    formula = re.sub(
                        rf"(?<![.`])\b{re.escape(dependency)}\b",
                        f"({replacement})",
                        formula,
                    )
            for source_column in sorted(source_columns, key=len, reverse=True):
                formula = re.sub(
                    rf"(?<![.`])\b{re.escape(source_column)}\b",
                    f"src.`{source_column}`",
                    formula,
                )
            return re.sub(r"\breconciliation_tolerance\b", "0.000001", formula)

        expanded_formulas = {
            name: expand_formula(name) for name in metrics_by_name
        }
        ads_columns = [
            {**dict(source_lookup[name]), "is_primary_key": True}
            for name in grain_columns
        ]
        for metric in metrics:
            unit = str(metric.get("unit") or "")
            source_type = (
                "BOOLEAN"
                if unit == "boolean"
                else "BIGINT"
                if unit == "count"
                else "DECIMAL(38,6)"
            )
            ads_columns.append(
                {
                    "name": metric["name"],
                    "source_type": source_type,
                    "nullable": True,
                    "is_primary_key": False,
                    "remarks": f"{metric['class']} metric: {metric['formula']}",
                }
            )
        ads_columns = _with_technical_column(
            ads_columns, name="etl_time", source_type="DATETIME"
        )
        _write(
            ddl_root / f"{ads_name}.sql",
            _render_ddl(
                table_name=ads_name,
                columns=ads_columns,
                registry=registry,
                description=f"Reviewed application metrics derived from {dws_name}",
            ),
        )
        derived_metrics = [
            metric for metric in metrics if metric.get("class") == "derived"
        ]
        calculated_metrics = [
            metric for metric in metrics if metric.get("class") == "calculated"
        ]
        _write_yaml(
            model_root / f"{ads_name}.yaml",
            {
                "version": 2,
                "name": ads_name,
                "layer": "ADS",
                "description": f"{mapping['domain_name']} reviewed application data",
                "table_type": "application_fact",
                "execution": (
                    {
                        "materialized": "incremental",
                        "full_refresh_strategy": "companion",
                        "slice": {
                            "param": "etl_date",
                            "column": str(spec["business_date"]["column"]),
                            "period": "D",
                        },
                        "late_arriving_policy": (
                            "replay_original_and_current_business_dates"
                        ),
                    }
                    if supports_daily_slice
                    else {
                        "materialized": "full",
                        "full_refresh_strategy": "replace_all",
                    }
                ),
                "data_domain": DOMAIN_IDS.get(mapping["data_domain"], "99"),
                "business_area": mapping["business_area"],
                "business_process": spec["canonical_process"],
                "sensitivity": mapping.get("sensitivity", "internal"),
                "business_date": spec["business_date"],
                "grain": {
                    **spec["grain"],
                    "entities": [
                        item["code"] for item in spec.get("entities") or []
                    ],
                    "degenerate_dimensions": spec.get("degenerate_dimensions")
                    or [],
                },
                "entities": spec.get("entities") or [],
                "degenerate_dimensions": spec.get("degenerate_dimensions")
                or [],
                "derived_metrics": derived_metrics,
                "calculated_metrics": calculated_metrics,
                "metric_semantics": metrics,
                "application_rules": spec.get("application_rules") or [],
                "human_review": {
                    "decision": spec["decision"],
                    "current_name": spec.get("current_name"),
                    "status": payload["status"],
                },
            },
        )
        insert_names = (
            grain_columns
            + [metric["name"] for metric in metrics]
            + ["etl_time"]
        )
        select_parts = [f"src.`{name}`" for name in grain_columns]
        select_parts.extend(
            f"{expanded_formulas[metric['name']]} AS `{metric['name']}`"
            for metric in metrics
        )
        select_parts.append("CURRENT_TIMESTAMP AS `etl_time`")
        aggregate_query = any(
            re.search(r"\bSUM\s*\(", formula, re.I)
            for formula in expanded_formulas.values()
        )
        slice_column = str(spec["business_date"]["column"])
        reset_sql = (
            f"DELETE FROM {DATABASE}.{ads_name}\n"
            f"WHERE `{slice_column}` = CAST(@etl_date AS DATE);"
            if supports_daily_slice
            else f"TRUNCATE TABLE {DATABASE}.{ads_name};"
        )
        task_sql = _render_reviewed_ads_task(
            ads_name=ads_name,
            source_name=task_source_name,
            insert_names=insert_names,
            select_parts=select_parts,
            grain_columns=grain_columns,
            aggregate_query=aggregate_query,
            parameter_sql=(
                "SET @etl_date = COALESCE(@etl_date, CURDATE());\n\n"
                if supports_daily_slice
                else ""
            ),
            reset_sql=reset_sql,
            where_sql=(
                f"\nWHERE src.`{slice_column}` = CAST(@etl_date AS DATE)"
                if supports_daily_slice
                else ""
            ),
        )
        _write(
            task_root / f"{ads_name}.sql",
            task_sql,
        )
        if supports_daily_slice:
            _write(
                task_root / "full_refresh" / f"{ads_name}_full_refresh.sql",
                _render_reviewed_ads_task(
                    ads_name=ads_name,
                    source_name=task_source_name,
                    insert_names=insert_names,
                    select_parts=select_parts,
                    grain_columns=grain_columns,
                    aggregate_query=aggregate_query,
                    parameter_sql=_full_refresh_window_setup(),
                    reset_sql=f"TRUNCATE TABLE {DATABASE}.{ads_name};",
                    where_sql=(
                        "\nWHERE "
                        + _full_refresh_window_predicate(
                            f"src.`{slice_column}`"
                        )
                    ),
                ),
            )
        generated_names.add(ads_name)
    return len(generated_names), generated_names


def generate_manifest(
    *,
    ods_count: int,
    mid_count: int,
    dws_count: int,
    ads_count: int,
    source: dict,
) -> None:
    manifest = {
        "version": 1,
        "project": "retail_banking",
        "upstream_repository": source["upstream_repository"],
        "upstream_commit": source["upstream_commit"],
        "counts": {
            "ODS": ods_count,
            "DIM_DWD": mid_count,
            "DWS": dws_count,
            "ADS": ads_count,
            "TOTAL": ods_count + mid_count + dws_count + ads_count,
        },
        "generation_policy": {
            "all_active_sources_have_ods": False,
            "only_downstream_referenced_sources_have_ods": True,
            "downstream_requires_structural_mapping": True,
            "unused_sources_remain_inventory_only": True,
            "pure_fineract_scope_only": True,
        },
    }
    _write_yaml(
        PROJECT_DIR / "mappings/generated_asset_manifest.yaml", manifest
    )


def generate_complete_layer_mapping(
    *,
    mappings: list[dict],
    materialized_ods_tables: set[str],
    generated_mid: dict,
    summaries: dict,
    source: dict,
) -> None:
    mid_by_source: dict[str, dict[str, list[str]]] = {}
    for target_name, (mapping, _columns) in generated_mid.items():
        layer = str(mapping.get("target_layer") or "DWD")
        mid_by_source.setdefault(mapping["source_table"], {}).setdefault(
            layer, []
        ).append(target_name)
    payload = _dws_ads_specs()
    _active_specs, aliases = _dim_dwd_specs()
    dws_by_mid: dict[str, list[str]] = {}
    for spec in payload.get("dws") or []:
        for source_name in spec["source"]:
            canonical = aliases.get(str(source_name), str(source_name))
            dws_by_mid.setdefault(canonical, []).append(str(spec["name"]))
    ads_by_dws: dict[str, list[str]] = {}
    for spec in payload.get("ads") or []:
        for dws_name in spec["source"]:
            ads_by_dws.setdefault(str(dws_name), []).append(str(spec["name"]))
    entries = []
    for mapping in mappings:
        mid_layers = mid_by_source.get(mapping["source_table"], {})
        dim_tables = sorted(mid_layers.get("DIM", []))
        dwd_tables = sorted(mid_layers.get("DWD", []))
        dws_tables = sorted(
            {
                dws_name
                for target in dim_tables + dwd_tables
                for dws_name in dws_by_mid.get(target, [])
                if dws_name in summaries
            }
        )
        ads_tables = sorted(
            {
                ads_name
                for dws_name in dws_tables
                for ads_name in ads_by_dws.get(dws_name, [])
            }
        )
        entries.append(
            {
                "source_table": mapping["source_table"],
                "business_area": mapping["business_area"],
                "data_domain": mapping["data_domain"],
                "domain_name": mapping["domain_name"],
                "disposition": mapping["disposition"],
                "mapping_status": mapping["confidence"],
                "sensitivity": mapping["sensitivity"],
                "layers": {
                    "ODS": (
                        [mapping["ods_table"]]
                        if mapping["ods_table"] in materialized_ods_tables
                        else []
                    ),
                    "DIM": dim_tables,
                    "DWD": dwd_tables,
                    "DWS": dws_tables,
                    "ADS": ads_tables,
                },
            }
        )
    _write_yaml(
        PROJECT_DIR / "mappings/fineract_layer_mapping.yaml",
        {
            "version": 1,
            "project": "retail_banking",
            "upstream_repository": source["upstream_repository"],
            "upstream_commit": source["upstream_commit"],
            "source_table_count": len(entries),
            "mappings": entries,
        },
    )


def _normalize_gold_alternatives(
    raw_alternatives: list,
    *,
    canonical_layer: str,
    canonical_table_type: str,
    valid_layers: set[str],
    valid_table_types: set[str],
) -> list[dict]:
    """Normalize legacy names and explicit benchmark alternatives."""

    normalized = []
    required_fields = {
        "name",
        "layer",
        "table_type",
        "credit",
        "rationale",
    }
    for index, item in enumerate(raw_alternatives):
        if isinstance(item, str):
            name = item.strip()
            if not name:
                raise ValueError(
                    f"Gold alternative {index} must have a non-empty name"
                )
            normalized.append(
                {
                    "name": name,
                    "layer": canonical_layer,
                    "table_type": canonical_table_type,
                    "credit": 0.5,
                    "rationale": (
                        f"Adjudicated architecture alternative: {name}"
                    ),
                }
            )
            continue
        if not isinstance(item, dict):
            raise ValueError(
                "Gold alternative must be a name or mapping, received "
                f"{item!r}"
            )
        missing_fields = sorted(required_fields - set(item))
        if missing_fields:
            raise ValueError(
                f"Gold alternative {index} is missing fields: {missing_fields}"
            )
        name = item["name"]
        layer = item["layer"]
        table_type = item["table_type"]
        credit = item["credit"]
        rationale = item["rationale"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Gold alternative {index} must have a non-empty name"
            )
        if layer not in valid_layers:
            raise ValueError(
                f"Gold alternative {name!r} has invalid layer {layer!r}"
            )
        if table_type not in valid_table_types:
            raise ValueError(
                f"Gold alternative {name!r} has invalid table_type "
                f"{table_type!r}"
            )
        if (
            isinstance(credit, bool)
            or not isinstance(credit, (int, float))
            or not 0 <= credit <= 1
        ):
            raise ValueError(
                f"Gold alternative {name!r} has invalid credit {credit!r}"
            )
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
                f"Gold alternative {name!r} must have a rationale"
            )
        normalized.append(
            {
                "name": name.strip(),
                "layer": layer,
                "table_type": table_type,
                "credit": credit,
                "rationale": rationale.strip(),
            }
        )
    return normalized


def generate_benchmark_contract(
    *,
    mappings: list[dict],
    source: dict,
    generated_mid: dict,
    summaries: dict,
    private_gold_output: Optional[Path] = None,
    write_input_manifest: bool = True,
) -> None:
    """Write the public contract and optionally emit gold outside the repo."""

    dws_ads_payload = _dws_ads_specs()
    benchmark_root = PROJECT_DIR / "benchmark"
    benchmark_contract = _load_yaml(
        benchmark_root / BENCHMARK_CONTRACT_FILENAME
    )
    alternative_schema = benchmark_contract["table_record"]["fields"][
        "expected"
    ]["allowed_alternatives"]["items"]
    valid_alternative_layers = set(alternative_schema["layer"]["enum"])
    valid_alternative_table_types = set(
        alternative_schema["table_type"]["enum"]
    )
    identity_payload = _load_yaml(
        PROJECT_DIR / "mappings/schema_identities.yaml"
    )
    mapping_by_ods = {item["ods_table"]: item for item in mappings}
    mapping_by_target = {
        target_name: item[0] for target_name, item in generated_mid.items()
    }
    mapping_by_target.update(
        {target_name: item[0] for target_name, item in summaries.items()}
    )
    ads_spec_by_name = {
        item["name"]: item for item in dws_ads_payload.get("ads") or []
    }
    for ads_name, spec in ads_spec_by_name.items():
        source_name = spec["source"][0]
        if source_name in summaries:
            mapping_by_target[ads_name] = summaries[source_name][0]

    model_paths = [
        *PROJECT_DIR.glob("ods/models/*/*/*.yaml"),
        *PROJECT_DIR.glob("mid/models/*.yaml"),
        *PROJECT_DIR.glob("ads/models/*.yaml"),
    ]

    def normalized_table_type(model: dict) -> str:
        value = str(model.get("table_type") or "source")
        return {
            "fact": "transaction_fact",
            "dimension_satellite": "dimension",
            "application_fact": "application_mart",
        }.get(value, value)

    def normalized_time_kind(value: str) -> str:
        lowered = value.lower()
        for token, normalized in (
            ("posting", "posting_date"),
            ("contractual", "contractual_due_date"),
            ("due", "contractual_due_date"),
            ("settlement", "settlement_date"),
            ("effective", "effective_date"),
            ("snapshot", "snapshot_date"),
            ("processing", "processing_date"),
            ("run", "processing_date"),
            ("event", "event_date"),
        ):
            if token in lowered:
                return normalized
        return "timeless"

    def gold_metric(metric: dict) -> dict:
        return {
            "name": metric["name"],
            "class": metric.get("class", "atomic"),
            "formula": metric.get("formula", metric["name"]),
            "unit": metric.get("unit", "source_unit"),
            "currency_source": metric.get("currency_source"),
            "aggregation_behavior": metric.get(
                "aggregation_behavior", "non_additive"
            ),
            "additive_over": metric.get("additive_over") or [],
            "sign_convention": metric.get(
                "sign_convention", metric.get("sign", "source_defined")
            ),
            "reversal_policy": metric.get(
                "reversal_policy", metric.get("reversal", "source_policy")
            ),
        }

    records = []
    for model_path in sorted(model_paths):
        model = _load_yaml(model_path)
        table_name = str(model["name"])
        layer = str(model["layer"])
        mapping = mapping_by_ods.get(table_name) or mapping_by_target.get(
            table_name, {}
        )
        entities = model.get("entities") or []
        primary = next(
            (item for item in entities if item.get("type") == "primary"), None
        )
        related = [item for item in entities if item.get("type") != "primary"]
        raw_alternatives = (model.get("human_review") or {}).get(
            "allowed_alternatives"
        ) or []
        table_type = normalized_table_type(model)
        allowed_alternatives = _normalize_gold_alternatives(
            raw_alternatives,
            canonical_layer=layer,
            canonical_table_type=table_type,
            valid_layers=valid_alternative_layers,
            valid_table_types=valid_alternative_table_types,
        )
        business_date = model.get("business_date") or {}
        sensitivity_level = str(model.get("sensitivity") or "internal")
        if sensitivity_level not in {
            "public",
            "internal",
            "confidential",
            "restricted",
        }:
            sensitivity_level = "restricted"
        model_relative = model_path.relative_to(PROJECT_DIR)
        ddl_relative = Path(
            str(model_relative).replace("models", "ddl")
        ).with_suffix(".sql")
        task_relative = Path(
            str(model_relative).replace("models", "tasks")
        ).with_suffix(".sql")
        if layer == "ODS":
            task_paths: list[str] = []
            source_tables = [mapping.get("source_table", table_name)]
        else:
            task_paths = (
                [str(task_relative)]
                if (PROJECT_DIR / task_relative).exists()
                else []
            )
            source_tables = [
                str(item)
                for item in (
                    (ads_spec_by_name.get(table_name) or {}).get("source")
                    or [mapping.get("source_table")]
                )
                if item
            ]
        process = model.get("business_process")
        records.append(
            {
                "asset_id": identity_payload["tables"][table_name]["table_id"],
                "asset_name": table_name,
                "expected": {
                    "layer": layer,
                    "table_type": table_type,
                    "disposition": (
                        "security_excluded"
                        if layer == "ODS"
                        and mapping.get("disposition") == "security_excluded"
                        else "ods_only"
                        if layer == "ODS"
                        else "materialize"
                    ),
                    "data_domain_id": model.get("data_domain"),
                    "data_domain_code": mapping.get("data_domain"),
                    "business_area_code": model.get("business_area")
                    or mapping.get("business_area"),
                    "business_process_codes": [process] if process else [],
                    "semantic_subject_code": model.get("semantic_subject"),
                    "allowed_alternatives": allowed_alternatives,
                },
                "grain": {
                    "columns": (model.get("grain") or {}).get("columns") or [],
                    "primary_entity": primary.get("code") if primary else None,
                    "related_entities": [item.get("code") for item in related],
                    "degenerate_dimensions": (
                        (model.get("grain") or {}).get("degenerate_dimensions")
                        or model.get("degenerate_dimensions")
                        or []
                    ),
                },
                "time_semantics": {
                    "business_date_column": business_date.get("column"),
                    "kind": normalized_time_kind(
                        str(business_date.get("kind") or "none")
                    ),
                    "as_of_column": (
                        business_date.get("column")
                        if "snapshot" in str(business_date.get("kind") or "")
                        else None
                    ),
                },
                "entities": [
                    {
                        "code": item.get("code"),
                        "role": (
                            "primary"
                            if item.get("type") == "primary"
                            else "related"
                        ),
                        "key_columns": item.get("key_columns") or [],
                    }
                    for item in entities
                ],
                "metrics": [
                    gold_metric(item)
                    for item in model.get("metric_semantics") or []
                ],
                "sensitivity": {
                    "table_level": sensitivity_level,
                    "restricted_columns": [
                        item["name"]
                        for item in model.get("column_sensitivity") or []
                    ],
                },
                "evidence": {
                    "upstream_commit": source["upstream_commit"],
                    "source_tables": source_tables,
                    "ddl_paths": [str(ddl_relative)],
                    "task_paths": task_paths,
                },
                "annotation": {
                    "reviewers": ["reviewer_agent_a", "reviewer_agent_b"],
                    "adjudication": (
                        "accepted_with_alternatives"
                        if allowed_alternatives
                        else "accepted"
                    ),
                    "rationale": model.get("description") or "reviewed asset",
                    "gold_version": "candidate_v0",
                },
            }
        )
    if private_gold_output is not None:
        private_gold_output = private_gold_output.expanduser().resolve()
        try:
            private_gold_output.relative_to(REPOSITORY_ROOT.resolve())
        except ValueError:
            pass
        else:
            raise ValueError(
                "Private gold output must be outside the Git checkout"
            )
        _write_yaml(
            private_gold_output,
            {
                "version": 1,
                "project": "retail_banking",
                "upstream_commit": source["upstream_commit"],
                "warning": (
                    "PRIVATE GOLD: store outside any participant-visible benchmark bundle."
                ),
                "schema": PRIVATE_GOLD_SCHEMA_REFERENCE,
                "status": "candidate_not_gold_v1",
                "records": records,
                "expected_asset_counts": {
                    "ODS": sum(
                        record["expected"]["layer"] == "ODS"
                        for record in records
                    ),
                    "DIM_DWD": len(generated_mid),
                    "DWS": len(summaries),
                    "ADS": len(dws_ads_payload["ads"]),
                },
            },
        )
    input_manifest = {
        "version": 1,
        "project": "retail_banking",
        "task": "semantic_cold_start",
        "participant_delivery": (
            "Only the public/ directory emitted by tools/"
            "build_benchmark_bundle.py may be delivered to participants."
        ),
        "tracks": {
            "named_taxonomy_assisted": {
                "role_blind": False,
                "public_layout": [
                    "ddl/*.sql",
                    "tasks/*.sql",
                    "constraints.yaml",
                    "business_taxonomy.yaml",
                    "manifest.json",
                ],
            },
            "prefixless_role_blind": {
                "role_blind": True,
                "public_layout": [
                    "ddl/asset_*.sql",
                    "tasks/asset_*.sql",
                    "constraints.yaml",
                    "manifest.json",
                ],
                "enforced_transformations": [
                    "opaque_table_aliases",
                    "flatten_directories",
                    "replace_database_name",
                    "remove_sql_comments",
                    "remove_ddl_comments",
                ],
            },
        },
        "must_exclude": [
            "**/models/**/*.yaml",
            "mappings/**",
            "semantic_specs/**",
            "business_processes.yaml",
            "semantic_subjects.yaml",
            f"benchmark/{BENCHMARK_CONTRACT_FILENAME}",
            "artifacts/lineage/**",
        ],
        "role_blind_must_exclude": ["business_taxonomy.yaml"],
        "gold_handling": (
            "Generate private gold directly to access-controlled storage with "
            "generate_assets.py generate-private-gold "
            "--private-gold-output, then pass that external path to "
            "build_benchmark_bundle.py --private-gold."
        ),
    }
    if write_input_manifest:
        _write_yaml(benchmark_root / "input_manifest.yaml", input_manifest)


def generate(
    project_dir: Path = PROJECT_DIR,
    private_gold_output: Optional[Path] = None,
) -> None:
    del project_dir
    schema = _load_yaml(PROJECT_DIR / "mappings/fineract_schema_snapshot.yaml")
    mapping = _load_yaml(PROJECT_DIR / "mappings/fineract_table_mapping.yaml")
    if schema["upstream_commit"] != mapping["upstream_commit"]:
        raise ValueError(
            "Schema snapshot and mapping use different Fineract commits"
        )
    schema_tables = {
        table["source_table"]: table for table in schema["tables"]
    }
    mappings = mapping["mappings"]
    if set(schema_tables) != {item["source_table"] for item in mappings}:
        raise ValueError(
            "Mapping coverage does not match active schema table set"
        )
    registry = IdentityRegistry(
        PROJECT_DIR / "mappings/schema_identities.yaml"
    )
    mid_count, generated_mid = generate_reviewed_mid(
        schema_tables=schema_tables, mappings=mappings, registry=registry
    )
    generate_semantic_subjects(mappings)
    dws_count, summaries = generate_summaries(
        generated_mid=generated_mid, registry=registry
    )
    ads_count, ads_names = generate_ads(summaries=summaries, registry=registry)
    ods_mappings = materialized_ods_mappings(mappings)
    ods_count = generate_ods(
        schema_tables=schema_tables, mappings=ods_mappings, registry=registry
    )
    active_table_names = (
        {item["ods_table"] for item in ods_mappings}
        | set(generated_mid)
        | set(summaries)
    )
    active_table_names.update(ads_names)
    registry.prune_tables(active_table_names)
    registry.save()
    generate_manifest(
        ods_count=ods_count,
        mid_count=mid_count,
        dws_count=dws_count,
        ads_count=ads_count,
        source=schema,
    )
    generate_complete_layer_mapping(
        mappings=mappings,
        materialized_ods_tables={item["ods_table"] for item in ods_mappings},
        generated_mid=generated_mid,
        summaries=summaries,
        source=schema,
    )
    generate_benchmark_contract(
        mappings=mappings,
        source=schema,
        generated_mid=generated_mid,
        summaries=summaries,
        private_gold_output=private_gold_output,
    )
    LOGGER.info(
        "Generated ODS=%d DIM/DWD=%d DWS=%d ADS=%d total=%d",
        ods_count,
        mid_count,
        dws_count,
        ads_count,
        ods_count + mid_count + dws_count + ads_count,
    )


def generate_private_gold(output: Path) -> None:
    """Generate evaluator gold from committed assets without rebuilding them."""

    schema = _load_yaml(PROJECT_DIR / "mappings/fineract_schema_snapshot.yaml")
    mapping_payload = _load_yaml(
        PROJECT_DIR / "mappings/fineract_table_mapping.yaml"
    )
    layer_mapping = _load_yaml(
        PROJECT_DIR / "mappings/fineract_layer_mapping.yaml"
    )
    mappings = mapping_payload["mappings"]
    mapping_by_source = {item["source_table"]: item for item in mappings}
    generated_mid = {}
    summaries = {}
    for entry in layer_mapping["mappings"]:
        mapping = mapping_by_source[entry["source_table"]]
        for layer in ("DIM", "DWD"):
            for table_name in entry["layers"][layer]:
                generated_mid.setdefault(table_name, (mapping, []))
        for table_name in entry["layers"]["DWS"]:
            summaries.setdefault(table_name, (mapping, []))
    generate_benchmark_contract(
        mappings=mappings,
        source=schema,
        generated_mid=generated_mid,
        summaries=summaries,
        private_gold_output=output,
        write_input_manifest=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["generate", "generate-private-gold"]
    )
    parser.add_argument(
        "--private-gold-output",
        type=Path,
        help=(
            "Optional access-controlled output path outside the Git checkout; "
            "private gold is never written into the repository by default."
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        generate(private_gold_output=args.private_gold_output)
        return 0
    if args.private_gold_output is None:
        raise ValueError(
            "generate-private-gold requires --private-gold-output"
        )
    generate_private_gold(args.private_gold_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
