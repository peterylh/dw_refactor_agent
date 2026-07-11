#!/usr/bin/env python3
"""Build a Doris retail-banking warehouse inventory from Apache Fineract.

The inventory command reads the PostgreSQL Liquibase changelogs from a pinned
Fineract checkout, resolves the active table/column shape that can be expressed
by standard Liquibase changes, classifies every table, and writes the mapping
that drives the warehouse asset generator.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import logging
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import yaml

LOGGER = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parents[1]
TEXT_ENCODING = "utf-8"
UPSTREAM_REPOSITORY = "https://github.com/apache/fineract"
SEMANTIC_SPEC_PATH = PROJECT_DIR / "semantic_specs/dim_dwd.yaml"
_SEMANTIC_SPEC_CACHE: Optional[dict[str, dict]] = None


@dataclass
class ColumnSchema:
    """One source column after applying supported Liquibase migrations."""

    name: str
    source_type: str
    nullable: bool = True
    is_primary_key: bool = False
    remarks: str = ""
    default_value: Optional[str] = None
    default_value_type: str = ""
    auto_increment: bool = False


@dataclass
class TableSchema:
    """One active Fineract table and its resolved source metadata."""

    name: str
    columns: OrderedDict[str, ColumnSchema] = field(
        default_factory=OrderedDict
    )
    source_files: list[str] = field(default_factory=list)
    raw_sql_warnings: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    unique_constraints: list[dict] = field(default_factory=list)
    foreign_keys: list[dict] = field(default_factory=list)
    unresolved_changes: list[dict] = field(default_factory=list)


class SchemaTables(dict):
    """Table mapping plus changelog issues that cannot be tied to one table."""

    def __init__(self, *args, unresolved_changes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.unresolved_changes = unresolved_changes or []


@dataclass(frozen=True)
class MappingEntry:
    """Warehouse mapping for one active Fineract table."""

    source_table: str
    ods_table: str
    business_area: str
    data_domain: str
    domain_name: str
    source_kind: str
    disposition: str
    target_layer: str
    target_table: str
    downstream_targets: list[str]
    grain: str
    load_strategy: str
    optional_module: bool
    confidence: str
    business_processes: list[str]
    quality_rules: list[str]
    sensitivity: str
    rationale: str


@dataclass(frozen=True)
class DomainRule:
    code: str
    name: str
    business_area: str
    patterns: tuple[str, ...]


DOMAIN_RULES = (
    DomainRule(
        "WCLN",
        "营运资金贷款",
        "LOAN",
        (r"(^|_)wc_", r"working_capital"),
    ),
    DomainRule(
        "LOAN",
        "贷款与信贷",
        "LOAN",
        (
            r"(^|_)loan($|_)",
            r"delinquen",
            r"arrears",
            r"guarantor",
            r"collateral",
            r"provision",
            r"creditbureau",
            r"creditreport",
        ),
    ),
    DomainRule(
        "DPST",
        "存款与储蓄",
        "DPST",
        (
            r"savings",
            r"deposit",
            r"mandatory_savings",
            r"standing_instruction",
        ),
    ),
    DomainRule(
        "PAYM",
        "支付结算",
        "PAYM",
        (
            r"account_transfer",
            r"payment",
            r"cashier",
            r"office_transaction",
            r"interop",
            r"beneficiar",
        ),
    ),
    DomainRule(
        "FINA",
        "总账与财务",
        "FMAN",
        (
            r"^acc_",
            r"journal_entry",
            r"accounting",
            r"financial_activity",
            r"gl_",
        ),
    ),
    DomainRule(
        "CUST",
        "客户与参与方",
        "CLNT",
        (
            r"(^|_)client($|_)",
            r"(^|_)group($|_)",
            r"(^|_)center($|_)",
            r"family",
            r"address",
            r"identifier",
            r"beneficial_owner",
        ),
    ),
    DomainRule(
        "ORGN",
        "机构与员工",
        "CHNL",
        (
            r"(^|_)office($|_)",
            r"(^|_)staff($|_)",
            r"employee",
            r"holiday",
            r"fund",
        ),
    ),
    DomainRule(
        "PROD",
        "产品、定价与税费",
        "OTHR",
        (
            r"(^|_)product($|_)",
            r"product_",
            r"(^|_)charge($|_)",
            r"interest_rate",
            r"floating_rate",
            r"(^|_)rate($|_)",
            r"(^|_)tax($|_)",
            r"currency",
        ),
    ),
    DomainRule(
        "INVS",
        "投资、份额与资产持有",
        "ASTM",
        (r"share_", r"external_asset", r"investor", r"ownership"),
    ),
    DomainRule(
        "RISK",
        "风险、合规与审计",
        "OTHR",
        (
            r"risk",
            r"audit",
            r"external_event",
            r"notification",
            r"sms",
            r"hook",
        ),
    ),
    DomainRule(
        "CHNL",
        "渠道与客户服务",
        "CHNL",
        (
            r"selfservice",
            r"device",
            r"pocket",
            r"calendar",
            r"meeting",
            r"attendance",
            r"note",
            r"document",
            r"image",
        ),
    ),
    DomainRule(
        "REFR",
        "公共参考与元数据",
        "OTHR",
        (
            r"(^|_)code($|_)",
            r"configuration",
            r"entity_",
            r"datatable",
            r"stretchy",
            r"account_number_format",
            r"report",
        ),
    ),
    DomainRule(
        "OPER",
        "平台运营与安全",
        "OTHR",
        (
            r"appuser",
            r"permission",
            r"role",
            r"oauth",
            r"twofactor",
            r"scheduler",
            r"(^|_)job($|_)",
            r"^batch_",
            r"command",
            r"cache",
            r"server_connection",
        ),
    ),
)


DOMAIN_OVERRIDES = {
    "glim_accounts": ("LOAN", "贷款与信贷", "LOAN"),
    "gsim_accounts": ("DPST", "存款与储蓄", "DPST"),
    "m_account_transfer_standing_instructions": (
        "PAYM",
        "支付结算",
        "PAYM",
    ),
    "m_account_transfer_standing_instructions_history": (
        "PAYM",
        "支付结算",
        "PAYM",
    ),
    "m_business_date": ("OPER", "平台运营与安全", "OTHR"),
    "m_cashiers": ("PAYM", "支付结算", "PAYM"),
    "m_external_event": ("OPER", "平台运营与安全", "OTHR"),
    "m_external_event_configuration": (
        "OPER",
        "平台运营与安全",
        "OTHR",
    ),
    "m_tax_group": ("PROD", "产品、定价与税费", "OTHR"),
    "m_tax_group_mappings": ("PROD", "产品、定价与税费", "OTHR"),
    "m_tellers": ("PAYM", "支付结算", "PAYM"),
    "m_working_days": ("ORGN", "机构与员工", "CHNL"),
    "oauth_client_details": ("OPER", "平台运营与安全", "OTHR"),
}


DOMAIN_PREFIX_OVERRIDES = (
    ("m_hook", ("OPER", "平台运营与安全", "OTHR")),
    ("m_share_", ("INVS", "投资、份额与资产持有", "ASTM")),
    ("m_survey", ("CHNL", "渠道与客户服务", "CHNL")),
    ("notification_", ("CHNL", "渠道与客户服务", "CHNL")),
    ("ppi_", ("CHNL", "渠道与客户服务", "CHNL")),
    ("sms_", ("CHNL", "渠道与客户服务", "CHNL")),
)


TECHNICAL_PATTERNS = (
    r"^databasechangelog",
    r"^batch_",
    r"(^|_)oauth(_|$)",
    r"twofactor",
    r"^scheduler",
    r"^job($|_)",
    r"^m_permission$",
    r"^m_role($|_)",
    r"^m_appuser($|_)",
    r"^m_portfolio_command_source$",
    r"^m_command$",
    r"^command$",
    r"^c_cache$",
    r"^c_configuration$",
    r"^c_external_service",
    r"^request_audit_table$",
    r"^stretchy_",
    r"^rpt_sequence$",
    r"^m_adhoc$",
    r"^m_report_mailing_",
    r"^scheduled_email_",
    r"^sms_campaign$",
    r"^m_hook",
)

EVENT_PATTERNS = (
    r"transaction",
    r"history",
    r"schedule",
    r"mapping",
    r"relation",
    r"paid_by",
    r"allocation",
    r"event",
    r"audit",
    r"attendance",
    r"transfer",
    r"journal_entry",
    r"breach",
    r"delinquency_action",
    r"run_history",
    r"installment",
)


REVIEWED_DIMENSIONS = {
    "acc_accounting_rule": "dim_accounting_rule",
    "acc_gl_account": "dim_gl_account",
    "m_address": "dim_address",
    "m_calendar": "dim_business_calendar",
    "m_charge": "dim_charge_type",
    "m_client": "dim_customer",
    "m_code_value": "dim_code_value",
    "m_collateral_management": "dim_collateral",
    "m_creditbureau": "dim_credit_bureau",
    "m_currency": "dim_currency",
    "m_delinquency_bucket": "dim_delinquency_bucket",
    "m_delinquency_range": "dim_delinquency_range",
    "m_external_asset_owner": "dim_asset_owner",
    "m_floating_rates": "dim_rate_index",
    "m_group": "dim_customer_group",
    "m_group_level": "dim_customer_group_level",
    "m_guarantor": "dim_guarantor",
    "m_holiday": "dim_holiday",
    "m_loan": "dim_loan_account",
    "m_office": "dim_office",
    "m_payment_type": "dim_payment_type",
    "m_product_loan": "dim_loan_product",
    "m_provision_category": "dim_provision_category",
    "m_rate": "dim_rate",
    "m_savings_account": "dim_deposit_account",
    "m_savings_product": "dim_deposit_product",
    "m_share_account": "dim_share_account",
    "m_share_product": "dim_share_product",
    "m_staff": "dim_staff",
    "m_surveys": "dim_survey",
    "m_tellers": "dim_teller",
    "m_wc_loan": "dim_wc_loan_account",
    "m_wc_loan_product": "dim_wc_loan_product",
    "m_working_days": "dim_working_day_rule",
}


REVIEWED_FACTS = {
    "acc_gl_closure": "dwd_gl_close_event",
    "acc_gl_journal_entry": "dwd_gl_journal_entry",
    "acc_product_mapping": "dwd_product_gl_mapping",
    "m_account_transfer_details": "dwd_account_transfer",
    "m_account_transfer_standing_instructions_history": "dwd_standing_instruction_event",
    "m_account_transfer_transaction": "dwd_account_transfer_transaction",
    "m_cashier_transactions": "dwd_cashier_transaction",
    "m_client_address": "dwd_customer_address_relation",
    "m_client_attendance": "dwd_group_meeting_attendance",
    "m_client_charge": "dwd_client_charge",
    "m_client_charge_paid_by": "dwd_client_charge_allocation",
    "m_client_transaction": "dwd_client_transaction",
    "m_client_transfer_details": "dwd_customer_transfer_event",
    "m_deposit_account_on_hold_transaction": "dwd_deposit_hold_event",
    "m_external_asset_owner_journal_entry_mapping": "dwd_asset_owner_gl_relation",
    "m_external_asset_owner_transfer": "dwd_loan_ownership_transfer",
    "m_external_asset_owner_transfer_details": "dwd_loan_ownership_transfer_detail",
    "m_group_client": "dwd_group_customer_relation",
    "m_group_roles": "dwd_group_role_relation",
    "m_guarantor_funding_details": "dwd_guarantee_commitment",
    "m_guarantor_transaction": "dwd_guarantee_transaction",
    "m_holiday_office": "dwd_office_holiday_relation",
    "m_loan_approved_amount_history": "dwd_loan_approval_event",
    "m_loan_charge": "dwd_loan_charge",
    "m_loan_charge_paid_by": "dwd_loan_charge_allocation",
    "m_loan_collateral_management": "dwd_loan_collateral_pledge",
    "m_loan_delinquency_action": "dwd_collection_action",
    "m_loan_delinquency_tag_history": "dwd_loan_delinquency_event",
    "m_loan_disbursement_detail": "dwd_loan_disbursement",
    "m_loan_installment_charge": "dwd_loan_installment_charge",
    "m_loan_installment_delinquency_tag_history": "dwd_installment_delinquency_event",
    "m_loan_officer_assignment_history": "dwd_loan_officer_assignment",
    "m_loan_rate": "dwd_loan_rate_period",
    "m_loan_recalculation_details": "dwd_loan_interest_recalculation",
    "m_loan_repayment_schedule": "dwd_loan_installment",
    "m_loan_repayment_schedule_history": "dwd_loan_installment_version",
    "m_loan_reschedule_request": "dwd_loan_restructure_event",
    "m_loan_status_change_history": "dwd_loan_lifecycle_event",
    "m_loan_transaction": "dwd_loan_transaction",
    "m_loan_transaction_relation": "dwd_loan_transaction_relation",
    "m_loan_transaction_repayment_schedule_mapping": "dwd_loan_repayment_allocation",
    "m_office_transaction": "dwd_office_cash_transfer",
    "m_loanproduct_provisioning_entry": "dwd_loan_provision_entry",
    "m_provisioning_history": "dwd_loan_provision_run",
    "acc_gl_journal_entry_annual_summary": ("dwd_gl_annual_balance_snapshot"),
    "m_journal_entry_aggregation_summary": "dwd_gl_aggregation_summary",
    "m_journal_entry_aggregation_tracking": "dwd_gl_aggregation_run",
    "m_loan_arrears_aging": "dwd_loan_arrears_snapshot",
    "m_loan_buy_down_fee_balance": "dwd_loan_buy_down_fee_balance",
    "m_loan_capitalized_income_balance": (
        "dwd_loan_capitalized_income_balance"
    ),
    "m_trial_balance": "dwd_gl_trial_balance_snapshot",
    "m_savings_account_charge": "dwd_deposit_charge",
    "m_savings_account_charge_paid_by": "dwd_deposit_charge_allocation",
    "m_savings_account_transaction": "dwd_deposit_transaction",
    "m_savings_account_transaction_tax_details": "dwd_deposit_transaction_tax",
    "m_savings_officer_assignment_history": "dwd_deposit_officer_assignment",
    "m_share_account_charge": "dwd_share_charge",
    "m_share_account_charge_paid_by": "dwd_share_charge_allocation",
    "m_share_account_dividend_details": "dwd_share_dividend",
    "m_share_account_transactions": "dwd_share_transaction",
    "m_share_product_market_price": "dwd_share_market_price",
    "m_staff_assignment_history": "dwd_staff_assignment",
    "m_survey_scorecards": "dwd_survey_response",
    "m_wc_loan_breach_action": "dwd_wc_breach_event",
    "m_wc_loan_disbursement_detail": "dwd_wc_loan_disbursement",
    "m_wc_loan_balance": "dwd_wc_loan_balance_snapshot",
    "m_wc_loan_rate_period": "dwd_wc_rate_period",
    "m_wc_loan_repayment_schedule": "dwd_wc_loan_installment",
    "m_wc_loan_transaction": "dwd_wc_loan_transaction",
}


BRIDGE_SOURCES = {
    "acc_product_mapping",
    "m_client_address",
    "m_external_asset_owner_journal_entry_mapping",
    "m_group_client",
    "m_group_roles",
    "m_holiday_office",
    "m_loan_transaction_relation",
}


SENSITIVE_TABLES = {
    "batch_custom_job_parameters",
    "c_external_service_properties",
    "glim_accounts",
    "gsim_accounts",
    "job_parameters",
    "m_client_non_person",
    "m_creditbureau_configuration",
    "m_document",
    "m_group",
    "m_hook_configuration",
    "m_image",
    "m_note",
    "m_payment_detail",
    "m_portfolio_command_source",
    "m_report_mailing_job_configuration",
    "m_wc_loan_note",
    "scheduled_email_configuration",
    "sms_campaign",
}


SECURITY_EXCLUDED_TABLES = {
    "c_external_service_properties",
    "job",
    "m_adhoc",
    "m_appuser",
    "m_appuser_previous_password",
    "m_appuser_role",
    "m_command",
    "m_creditbureau_configuration",
    "m_creditbureau_token",
    "m_creditreport",
    "m_external_event",
    "m_hook_configuration",
    "m_portfolio_command_source",
    "m_report_mailing_job",
    "m_report_mailing_job_configuration",
    "oauth_access_token",
    "oauth_client_details",
    "oauth_refresh_token",
    "request_audit_table",
    "scheduled_email_campaign",
    "scheduled_email_configuration",
    "scheduled_email_messages_outbound",
    "twofactor_access_token",
    "twofactor_configuration",
}


REVIEWED_ODS_DISPOSITIONS = {
    "m_client_identifier": "bridge_source",
    "m_wc_loan_account_locks": "operational_only",
    "m_wc_loan_payment_allocation_rule": "rule_reference",
}


SOURCE_KIND_OVERRIDES = {
    "m_external_event_configuration": "master_or_reference",
    "m_wc_loan_account_locks": "technical",
    "m_wc_loan_payment_allocation_rule": "master_or_reference",
}


DOMAIN_DEFAULT_PROCESSES = {
    "CHNL": "customer_service_management",
    "CUST": "customer_management",
    "DPST": "deposit_account_management",
    "FINA": "general_ledger_posting",
    "INVS": "investment_account_management",
    "LOAN": "loan_account_management",
    "OPER": "operations_management",
    "ORGN": "organisation_management",
    "OTHR": "operations_management",
    "PAYM": "payment_operation",
    "PROD": "product_configuration",
    "REFR": "reference_data_management",
    "RISK": "risk_management",
    "WCLN": "wc_loan_management",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> Optional[ET.Element]:
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _boolean(value: object, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes"}


DEFAULT_VALUE_ATTRIBUTES = (
    ("defaultValue", "literal"),
    ("defaultValueNumeric", "numeric"),
    ("defaultValueBoolean", "boolean"),
    ("defaultValueDate", "date"),
    ("defaultValueComputed", "computed"),
    ("defaultValueSequenceNext", "sequence_next"),
)


def _default_metadata(element: ET.Element) -> tuple[Optional[str], str]:
    for attribute, value_type in DEFAULT_VALUE_ATTRIBUTES:
        if attribute in element.attrib:
            return str(element.attrib[attribute]), value_type
    return None, ""


def _column_from_xml(element: ET.Element) -> ColumnSchema:
    constraints = _child(element, "constraints")
    nullable = True
    is_primary_key = False
    if constraints is not None:
        nullable = _boolean(constraints.attrib.get("nullable"), True)
        is_primary_key = _boolean(constraints.attrib.get("primaryKey"), False)
    default_value, default_value_type = _default_metadata(element)
    return ColumnSchema(
        name=str(element.attrib["name"]),
        source_type=str(element.attrib.get("type") or "VARCHAR(255)"),
        nullable=nullable,
        is_primary_key=is_primary_key,
        remarks=str(element.attrib.get("remarks") or ""),
        default_value=default_value,
        default_value_type=default_value_type,
        auto_increment=_boolean(element.attrib.get("autoIncrement"), False),
    )


def _postgres_change_set(change_set: ET.Element) -> bool:
    dbms = str(change_set.attrib.get("dbms") or "").strip().lower()
    if dbms and "postgresql" not in dbms and "all" not in dbms:
        return False
    context = str(change_set.attrib.get("context") or "").strip().lower()
    if "mysql" in context and "postgresql" not in context:
        return False
    preconditions = _child(change_set, "preConditions")
    if preconditions is None:
        return True
    dbms_nodes = [
        node
        for node in preconditions.iter()
        if _local_name(node.tag) == "dbms"
    ]
    if not dbms_nodes:
        return True
    allowed = {
        value.strip().lower()
        for node in dbms_nodes
        for value in str(node.attrib.get("type") or "").split(",")
        if value.strip()
    }
    return not allowed or "postgresql" in allowed


def _postgres_operation(operation: ET.Element) -> bool:
    dbms = {
        value.strip().lower()
        for value in str(operation.attrib.get("dbms") or "").split(",")
        if value.strip()
    }
    if not dbms:
        return True
    if "all" in dbms:
        return True
    return "postgresql" in dbms and "!postgresql" not in dbms


def _resource_index(fineract_root: Path) -> dict[str, Path]:
    """Index classpath resources across Fineract Gradle modules."""
    result: dict[str, Path] = {}
    for resource_root in sorted(
        fineract_root.glob("fineract-*/src/main/resources")
    ):
        for path in sorted(resource_root.rglob("*.xml")):
            resource_name = path.relative_to(resource_root).as_posix()
            existing = result.get(resource_name)
            if existing is not None and existing.resolve() != path.resolve():
                raise ValueError(
                    "Ambiguous Liquibase classpath resource {}: {} and {}".format(
                        resource_name, existing, path
                    )
                )
            result[resource_name] = path
    return result


def _normalize_resource_name(value: str) -> str:
    result = str(value).strip()
    if result.startswith("classpath:"):
        result = result[len("classpath:") :]
    return result.lstrip("/")


def _resolve_include(
    *, current: Path, node: ET.Element, resources: dict[str, Path]
) -> Path:
    include_name = _normalize_resource_name(str(node.attrib["file"]))
    if _boolean(node.attrib.get("relativeToChangelogFile"), False):
        candidate = (current.parent / include_name).resolve()
    else:
        candidate = resources.get(include_name)
        if candidate is None:
            raise FileNotFoundError(
                f"Liquibase include cannot be resolved: {include_name} from {current}"
            )
        candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(
            f"Liquibase include does not exist: {candidate} from {current}"
        )
    return candidate


def _walk_changelog(
    *,
    path: Path,
    resources: dict[str, Path],
    result: list[Path],
    seen: set[Path],
) -> None:
    """Expand one master changelog recursively in Liquibase include order."""
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    root = ET.parse(resolved).getroot()
    children = list(root)
    has_changesets = any(
        _local_name(node.tag) == "changeSet" for node in children
    )
    has_includes = any(
        _local_name(node.tag) in {"include", "includeAll"} for node in children
    )
    if has_changesets and has_includes:
        raise ValueError(
            "Mixed changeSet/include changelog requires ordered operation parsing: "
            f"{resolved}"
        )
    if has_changesets:
        result.append(resolved)
        return
    for node in children:
        node_name = _local_name(node.tag)
        if node_name == "include":
            _walk_changelog(
                path=_resolve_include(
                    current=resolved, node=node, resources=resources
                ),
                resources=resources,
                result=result,
                seen=seen,
            )
        elif node_name == "includeAll":
            include_dir = _normalize_resource_name(str(node.attrib["path"]))
            matches = sorted(
                path
                for name, path in resources.items()
                if name.startswith(include_dir.rstrip("/") + "/")
            )
            if not matches and _boolean(
                node.attrib.get("errorIfMissingOrEmpty"), True
            ):
                raise FileNotFoundError(
                    f"Liquibase includeAll is empty: {include_dir}"
                )
            for match in matches:
                _walk_changelog(
                    path=match,
                    resources=resources,
                    result=result,
                    seen=seen,
                )


def _is_clean_tenant_include(node: ET.Element) -> bool:
    include_name = _normalize_resource_name(str(node.attrib.get("file") or ""))
    context = str(node.attrib.get("context") or "").lower()
    if "tenant-store" in include_name or "tenant_store_db" in context:
        return False
    if "custom_changelog" in context:
        return False
    return "tenant_db" in context and "!initial_switch" in context


def discover_changelog_files(fineract_root: Path) -> list[Path]:
    """Return clean-install tenant changelog leaves in execution order.

    A new tenant is compiled as the initial-switch schema followed by the
    normal tenant changes, module masters, and final constraints.  Classpath
    includes are resolved across module resource roots instead of guessed by
    filename globs.
    """
    resources = _resource_index(fineract_root)
    provider_resources = fineract_root / "fineract-provider/src/main/resources"
    initial = (
        provider_resources
        / "db/changelog/tenant/initial-switch-changelog-tenant.xml"
    )
    master = provider_resources / "db/changelog/db.changelog-master.xml"
    if not initial.exists() or not master.exists():
        raise FileNotFoundError(
            "Fineract tenant Liquibase masters not found below "
            f"{provider_resources}"
        )
    result: list[Path] = []
    seen: set[Path] = set()
    _walk_changelog(
        path=initial, resources=resources, result=result, seen=seen
    )
    master_root = ET.parse(master).getroot()
    for node in master_root:
        if _local_name(node.tag) != "include" or not _is_clean_tenant_include(
            node
        ):
            continue
        _walk_changelog(
            path=_resolve_include(
                current=master, node=node, resources=resources
            ),
            resources=resources,
            result=result,
            seen=seen,
        )
    return result


def _record_source(table: TableSchema, source_path: str) -> None:
    if source_path not in table.source_files:
        table.source_files.append(source_path)


def _record_inline_constraints(
    table: TableSchema, column_node: ET.Element, column: ColumnSchema
) -> None:
    constraints = _child(column_node, "constraints")
    if constraints is None:
        return
    if _boolean(constraints.attrib.get("unique"), False):
        table.unique_constraints.append(
            {
                "name": str(
                    constraints.attrib.get("uniqueConstraintName") or ""
                ),
                "columns": [column.name],
            }
        )
    referenced_table = str(constraints.attrib.get("referencedTableName") or "")
    referenced_columns = _column_names(
        constraints.attrib.get("referencedColumnNames")
    )
    references = str(constraints.attrib.get("references") or "")
    if references and not referenced_table:
        match = re.match(r"\s*([^\s(]+)\s*\(([^)]+)\)", references)
        if match:
            referenced_table = match.group(1).strip('`"')
            referenced_columns = _column_names(match.group(2))
    if referenced_table:
        table.foreign_keys.append(
            {
                "name": str(constraints.attrib.get("foreignKeyName") or ""),
                "base_columns": [column.name],
                "referenced_table": referenced_table,
                "referenced_columns": referenced_columns,
                "on_delete": str(
                    constraints.attrib.get("deleteCascade") or ""
                ),
                "on_update": "",
                "deferrable": _boolean(
                    constraints.attrib.get("deferrable"), False
                ),
            }
        )


def _apply_create_table(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    name = str(operation.attrib["tableName"])
    table = TableSchema(name=name)
    for column_node in _children(operation, "column"):
        column = _column_from_xml(column_node)
        table.columns[column.name] = column
        if column.is_primary_key:
            table.primary_key.append(column.name)
        _record_inline_constraints(table, column_node, column)
    _record_source(table, source_path)
    tables[name] = table


def _apply_add_column(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table_name = str(operation.attrib["tableName"])
    table = tables.get(table_name)
    if table is None:
        LOGGER.warning("addColumn references unknown table %s", table_name)
        return
    for column_node in _children(operation, "column"):
        column = _column_from_xml(column_node)
        table.columns[column.name] = column
        if column.is_primary_key and column.name not in table.primary_key:
            table.primary_key.append(column.name)
        _record_inline_constraints(table, column_node, column)
    _record_source(table, source_path)


def _apply_drop_column(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table_name = str(operation.attrib["tableName"])
    table = tables.get(table_name)
    if table is None:
        return
    column_names = []
    if operation.attrib.get("columnName"):
        column_names.append(str(operation.attrib["columnName"]))
    column_names.extend(
        str(node.attrib["name"])
        for node in _children(operation, "column")
        if node.attrib.get("name")
    )
    for column_name in column_names:
        table.columns.pop(column_name, None)
        table.primary_key = [
            name for name in table.primary_key if name != column_name
        ]
        for constraint in table.unique_constraints:
            constraint["columns"] = [
                name for name in constraint["columns"] if name != column_name
            ]
        table.unique_constraints = [
            constraint
            for constraint in table.unique_constraints
            if constraint["columns"]
        ]
        for constraint in table.foreign_keys:
            constraint["base_columns"] = [
                name
                for name in constraint["base_columns"]
                if name != column_name
            ]
        table.foreign_keys = [
            constraint
            for constraint in table.foreign_keys
            if constraint["base_columns"]
        ]
    _record_source(table, source_path)


def _apply_rename_column(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table_name = str(operation.attrib["tableName"])
    old_name = str(operation.attrib["oldColumnName"])
    new_name = str(operation.attrib["newColumnName"])
    table = tables.get(table_name)
    if table is None or old_name not in table.columns:
        return
    renamed = OrderedDict()
    for column_name, column in table.columns.items():
        if column_name == old_name:
            column.name = new_name
            if operation.attrib.get("columnDataType"):
                column.source_type = str(operation.attrib["columnDataType"])
            renamed[new_name] = column
        else:
            renamed[column_name] = column
    table.columns = renamed
    table.primary_key = [
        new_name if name == old_name else name for name in table.primary_key
    ]
    for constraint in table.unique_constraints:
        constraint["columns"] = [
            new_name if name == old_name else name
            for name in constraint["columns"]
        ]
    for constraint in table.foreign_keys:
        constraint["base_columns"] = [
            new_name if name == old_name else name
            for name in constraint["base_columns"]
        ]
    _record_source(table, source_path)


def _apply_modify_type(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table_name = str(operation.attrib["tableName"])
    column_name = str(operation.attrib["columnName"])
    table = tables.get(table_name)
    if table is None or column_name not in table.columns:
        return
    table.columns[column_name].source_type = str(
        operation.attrib["newDataType"]
    )
    _record_source(table, source_path)


def _column_names(value: object) -> list[str]:
    return [
        name.strip().strip('`"')
        for name in str(value or "").split(",")
        if name.strip()
    ]


def _apply_primary_key(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    if table is None:
        return
    columns = _column_names(operation.attrib.get("columnNames"))
    table.primary_key = columns
    for column in table.columns.values():
        column.is_primary_key = column.name in columns
        if column.is_primary_key:
            column.nullable = False
    _record_source(table, source_path)


def _drop_primary_key(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    if table is None:
        return
    for column_name in table.primary_key:
        if column_name in table.columns:
            table.columns[column_name].is_primary_key = False
    table.primary_key = []
    _record_source(table, source_path)


def _apply_unique_constraint(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    if table is None:
        return
    constraint = {
        "name": str(operation.attrib.get("constraintName") or ""),
        "columns": _column_names(operation.attrib.get("columnNames")),
    }
    table.unique_constraints = [
        item
        for item in table.unique_constraints
        if not constraint["name"] or item["name"] != constraint["name"]
    ]
    table.unique_constraints.append(constraint)
    _record_source(table, source_path)


def _drop_unique_constraint(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    if table is None:
        return
    constraint_name = str(operation.attrib.get("constraintName") or "")
    table.unique_constraints = [
        item
        for item in table.unique_constraints
        if item["name"] != constraint_name
    ]
    _record_source(table, source_path)


def _apply_foreign_key(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["baseTableName"]))
    if table is None:
        return
    constraint = {
        "name": str(operation.attrib.get("constraintName") or ""),
        "base_columns": _column_names(operation.attrib.get("baseColumnNames")),
        "referenced_table": str(
            operation.attrib.get("referencedTableName") or ""
        ),
        "referenced_columns": _column_names(
            operation.attrib.get("referencedColumnNames")
        ),
        "on_delete": str(operation.attrib.get("onDelete") or ""),
        "on_update": str(operation.attrib.get("onUpdate") or ""),
        "deferrable": _boolean(operation.attrib.get("deferrable"), False),
    }
    table.foreign_keys = [
        item
        for item in table.foreign_keys
        if not constraint["name"] or item["name"] != constraint["name"]
    ]
    table.foreign_keys.append(constraint)
    _record_source(table, source_path)


def _drop_foreign_key(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["baseTableName"]))
    if table is None:
        return
    constraint_name = str(operation.attrib.get("constraintName") or "")
    table.foreign_keys = [
        item for item in table.foreign_keys if item["name"] != constraint_name
    ]
    _record_source(table, source_path)


def _apply_not_null(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
    *,
    nullable: bool,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    column_name = str(operation.attrib["columnName"])
    if table is None or column_name not in table.columns:
        return
    table.columns[column_name].nullable = nullable
    _record_source(table, source_path)


def _apply_default(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    column_name = str(operation.attrib["columnName"])
    if table is None or column_name not in table.columns:
        return
    value, value_type = _default_metadata(operation)
    table.columns[column_name].default_value = value
    table.columns[column_name].default_value_type = value_type
    _record_source(table, source_path)


def _drop_default(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    column_name = str(operation.attrib["columnName"])
    if table is None or column_name not in table.columns:
        return
    table.columns[column_name].default_value = None
    table.columns[column_name].default_value_type = ""
    _record_source(table, source_path)


def _apply_auto_increment(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    table = tables.get(str(operation.attrib["tableName"]))
    column_name = str(operation.attrib["columnName"])
    if table is None or column_name not in table.columns:
        return
    table.columns[column_name].auto_increment = True
    _record_source(table, source_path)


def _apply_rename_table(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
) -> None:
    old_name = str(operation.attrib["oldTableName"])
    new_name = str(operation.attrib["newTableName"])
    table = tables.pop(old_name, None)
    if table is None:
        return
    table.name = new_name
    _record_source(table, source_path)
    tables[new_name] = table


def _apply_drop_table(
    tables: dict[str, TableSchema], operation: ET.Element
) -> None:
    tables.pop(str(operation.attrib["tableName"]), None)


def _record_raw_sql_warning(
    tables: dict[str, TableSchema],
    operation: ET.Element,
    source_path: str,
    global_unresolved: list[dict],
) -> None:
    sql = " ".join("".join(operation.itertext()).split())
    table_names = re.findall(
        r"(?i)\b(?:alter|update|insert\s+into|delete\s+from|create|drop|truncate)"
        r"\s+(?:table\s+)?[`\"]?([a-zA-Z0-9_]+)",
        sql,
    )
    recorded = False
    for table_name in table_names:
        table = tables.get(table_name)
        if table is None:
            continue
        recorded = True
        warning = f"{source_path}: raw SQL migration requires review"
        if warning not in table.raw_sql_warnings:
            table.raw_sql_warnings.append(warning)
            table.unresolved_changes.append(
                {
                    "operation": "sql",
                    "source": source_path,
                    "description": warning,
                    "status": "unresolved",
                }
            )
    if not recorded:
        global_unresolved.append(
            {
                "operation": "sql",
                "source": source_path,
                "description": (
                    f"{source_path}: raw SQL migration requires review"
                ),
                "status": "unresolved",
            }
        )


def _resolve_unresolved_changes(
    tables: dict[str, TableSchema],
    *,
    global_unresolved: list[dict],
    unresolved_overrides: Optional[list[dict]],
    fail_on_unresolved: bool,
) -> None:
    overrides = unresolved_overrides or []
    unresolved = []
    changes_by_table = [
        (table.name, change)
        for table in tables.values()
        for change in table.unresolved_changes
    ]
    changes_by_table.extend(
        ("<global>", change) for change in global_unresolved
    )
    for table_name, change in changes_by_table:
        description = str(change["description"])
        override = next(
            (
                item
                for item in overrides
                if fnmatch.fnmatch(description, str(item.get("pattern") or ""))
                and fnmatch.fnmatch(table_name, str(item.get("table") or "*"))
            ),
            None,
        )
        if override is None:
            unresolved.append(f"{table_name}: {description}")
            continue
        rationale = str(override.get("rationale") or "").strip()
        if not rationale:
            raise ValueError(
                f"Unresolved-change override requires a rationale: {override}"
            )
        change["status"] = "overridden"
        change["override_rationale"] = rationale
    if unresolved and fail_on_unresolved:
        preview = "\n".join(f"- {item}" for item in unresolved[:20])
        raise ValueError(
            "Unresolved Liquibase SQL changes require explicit overrides:\n"
            f"{preview}"
        )


def parse_fineract_schema(
    fineract_root: Path,
    *,
    unresolved_overrides: Optional[list[dict]] = None,
    fail_on_unresolved: bool = True,
) -> dict[str, TableSchema]:
    """Resolve supported clean-install PostgreSQL schema operations."""
    tables: dict[str, TableSchema] = {}
    global_unresolved: list[dict] = []
    for path in discover_changelog_files(fineract_root):
        relative_path = path.relative_to(fineract_root).as_posix()
        root = ET.parse(path).getroot()
        for change_set in _children(root, "changeSet"):
            if not _postgres_change_set(change_set):
                continue
            for operation in change_set:
                if not _postgres_operation(operation):
                    continue
                name = _local_name(operation.tag)
                if name == "createTable":
                    _apply_create_table(tables, operation, relative_path)
                elif name == "addColumn":
                    _apply_add_column(tables, operation, relative_path)
                elif name == "dropColumn":
                    _apply_drop_column(tables, operation, relative_path)
                elif name == "renameColumn":
                    _apply_rename_column(tables, operation, relative_path)
                elif name == "modifyDataType":
                    _apply_modify_type(tables, operation, relative_path)
                elif name == "addPrimaryKey":
                    _apply_primary_key(tables, operation, relative_path)
                elif name == "dropPrimaryKey":
                    _drop_primary_key(tables, operation, relative_path)
                elif name == "addUniqueConstraint":
                    _apply_unique_constraint(tables, operation, relative_path)
                elif name == "dropUniqueConstraint":
                    _drop_unique_constraint(tables, operation, relative_path)
                elif name == "addForeignKeyConstraint":
                    _apply_foreign_key(tables, operation, relative_path)
                elif name == "dropForeignKeyConstraint":
                    _drop_foreign_key(tables, operation, relative_path)
                elif name == "addNotNullConstraint":
                    _apply_not_null(
                        tables,
                        operation,
                        relative_path,
                        nullable=False,
                    )
                elif name == "dropNotNullConstraint":
                    _apply_not_null(
                        tables,
                        operation,
                        relative_path,
                        nullable=True,
                    )
                elif name == "addDefaultValue":
                    _apply_default(tables, operation, relative_path)
                elif name == "dropDefaultValue":
                    _drop_default(tables, operation, relative_path)
                elif name == "addAutoIncrement":
                    _apply_auto_increment(tables, operation, relative_path)
                elif name == "renameTable":
                    _apply_rename_table(tables, operation, relative_path)
                elif name == "dropTable":
                    _apply_drop_table(tables, operation)
                elif name == "sql":
                    _record_raw_sql_warning(
                        tables,
                        operation,
                        relative_path,
                        global_unresolved,
                    )
    _resolve_unresolved_changes(
        tables,
        global_unresolved=global_unresolved,
        unresolved_overrides=unresolved_overrides,
        fail_on_unresolved=fail_on_unresolved,
    )
    return SchemaTables(
        sorted(tables.items()), unresolved_changes=global_unresolved
    )


def _matches_any(table_name: str, patterns: Iterable[str]) -> bool:
    return any(
        re.search(pattern, table_name, re.IGNORECASE) for pattern in patterns
    )


def classify_domain(table_name: str) -> DomainRule:
    """Classify one Fineract table using ordered banking-domain rules."""
    override = DOMAIN_OVERRIDES.get(table_name.lower())
    if override is not None:
        return DomainRule(*override, ())
    for prefix, value in DOMAIN_PREFIX_OVERRIDES:
        if table_name.lower().startswith(prefix):
            return DomainRule(*value, ())
    for rule in DOMAIN_RULES:
        if _matches_any(table_name, rule.patterns):
            return rule
    return DomainRule("OTHR", "其它银行运营", "OTHR", ())


def source_kind(table_name: str) -> str:
    override = SOURCE_KIND_OVERRIDES.get(table_name.lower())
    if override is not None:
        return override
    if _matches_any(table_name, TECHNICAL_PATTERNS):
        return "technical"
    if _matches_any(table_name, EVENT_PATTERNS):
        return "event_or_relation"
    return "master_or_reference"


def _normalized_entity_name(table_name: str) -> str:
    normalized = table_name.lower()
    for prefix in ("m_", "c_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return re.sub(r"[^a-z0-9_]+", "_", normalized).strip("_")


def _business_processes(table: TableSchema, domain_code: str) -> list[str]:
    table_name = table.name.lower()
    processes = []
    keyword_processes = (
        ("disbursement", "loan_disbursement"),
        ("repayment", "loan_repayment"),
        ("loan_transaction", "loan_transaction"),
        ("reschedule", "loan_restructure"),
        ("delinquen", "delinquency_management"),
        ("provision", "loan_provisioning"),
        ("savings_account_transaction", "deposit_transaction"),
        ("account_transfer", "account_transfer"),
        ("journal_entry", "general_ledger_posting"),
        ("cashier", "cashier_operation"),
        ("client", "customer_management"),
        ("share", "share_account_management"),
        ("external_asset", "loan_asset_transfer"),
        ("external_event", "external_event_delivery"),
        ("survey", "customer_survey"),
    )
    for keyword, process in keyword_processes:
        if keyword in table_name and process not in processes:
            processes.append(process)
    if not processes:
        processes.append(DOMAIN_DEFAULT_PROCESSES[domain_code])
    return processes


def _quality_rules(table: TableSchema) -> list[str]:
    rules = ["source_row_count_reconciliation"]
    if any(column.is_primary_key for column in table.columns.values()):
        rules.append("pk_not_null_unique")
    if any(
        "amount" in column.name.lower() for column in table.columns.values()
    ):
        rules.append("amount_decimal_precision")
    if any(
        "currency" in column.name.lower() for column in table.columns.values()
    ):
        rules.append("currency_code_valid")
    if table.name == "acc_gl_journal_entry":
        rules.append("journal_debit_credit_balance")
    if table.name in {"m_loan_transaction", "m_loan_repayment_schedule"}:
        rules.append("loan_subledger_reconciliation")
    if table.name == "m_savings_account_transaction":
        rules.append("deposit_balance_reconciliation")
    return rules


SECRET_COLUMN_PATTERNS = (
    r"password",
    r"passwd",
    r"(^|_)token($|_)",
    r"secret",
    r"credential",
    r"authentication",
    r"private_key",
    r"connection_string",
)

PII_COLUMN_PATTERNS = (
    r"first_?name",
    r"last_?name",
    r"fullname",
    r"display_name",
    r"email",
    r"mobile",
    r"phone",
    r"address",
    r"postal",
    r"date_of_birth",
    r"identifier",
    r"account_no",
    r"username",
)


def _has_secret_columns(table: TableSchema) -> bool:
    return any(
        _matches_any(column.name, SECRET_COLUMN_PATTERNS)
        for column in table.columns.values()
    )


def _sensitivity(table: TableSchema) -> str:
    table_name = table.name.lower()
    column_names = [column.name.lower() for column in table.columns.values()]
    if table_name in SENSITIVE_TABLES:
        return "restricted"
    if _has_secret_columns(table) or _matches_any(
        table_name,
        (r"appuser", r"oauth", r"twofactor", r"server_connection"),
    ):
        return "restricted"
    if (
        table_name == "m_external_event"
        or _matches_any(
            table_name,
            (r"client_identifier", r"address", r"family", r"creditreport"),
        )
        or any(
            _matches_any(name, PII_COLUMN_PATTERNS) for name in column_names
        )
    ):
        return "restricted"
    return "internal"


def _candidate_disposition(table: TableSchema, kind: str) -> str:
    table_name = table.name.lower()
    if table_name in SECURITY_EXCLUDED_TABLES or _has_secret_columns(table):
        return "security_excluded"
    if kind == "technical":
        if _sensitivity(table) == "restricted":
            return "security_excluded"
        return "operational_only"
    if _matches_any(
        table_name,
        (r"configuration", r"criteria", r"rule", r"strategy", r"template"),
    ):
        return "rule_reference"
    if _matches_any(
        table_name,
        (r"summary", r"balance", r"aggregation", r"arrears_aging"),
    ):
        return "snapshot_source"
    if _matches_any(
        table_name, (r"mapping", r"mappings", r"relation", r"roles")
    ):
        return "bridge_source"
    return "component_source"


def _semantic_specs() -> dict[str, dict]:
    global _SEMANTIC_SPEC_CACHE
    if _SEMANTIC_SPEC_CACHE is not None:
        return _SEMANTIC_SPEC_CACHE
    if not SEMANTIC_SPEC_PATH.exists():
        _SEMANTIC_SPEC_CACHE = {}
        return _SEMANTIC_SPEC_CACHE
    payload = (
        yaml.safe_load(SEMANTIC_SPEC_PATH.read_text(encoding=TEXT_ENCODING))
        or {}
    )
    entries = payload.get("entries") if isinstance(payload, dict) else []
    _SEMANTIC_SPEC_CACHE = {
        str(entry["source_table"]): entry
        for entry in entries or []
        if isinstance(entry, dict)
        and entry.get("source_table")
        and entry.get("active_mapping", True)
        and entry.get("materialize")
    }
    return _SEMANTIC_SPEC_CACHE


def build_mapping_entry(table: TableSchema) -> MappingEntry:
    domain = classify_domain(table.name)
    kind = source_kind(table.name)
    semantic_spec = _semantic_specs().get(table.name)
    if table.name in SECURITY_EXCLUDED_TABLES or _has_secret_columns(table):
        disposition = "security_excluded"
        target_layer = "NONE"
        target_table = ""
        confidence = "security_reviewed"
        rationale = (
            "包含密码、令牌或认证凭据，仅保留受限 ODS，禁止进入普通分析层。"
        )
    elif semantic_spec is not None:
        target_layer = str(semantic_spec["target_layer"])
        target_table = str(semantic_spec["target_table"])
        table_type = str(semantic_spec.get("table_type") or "")
        if target_layer == "DIM":
            disposition = "standalone_dimension"
        elif "bridge" in table_type:
            disposition = "bridge_source"
        elif "snapshot" in table_type or "aggregate" in table_type:
            disposition = "snapshot_source"
        else:
            disposition = "standalone_fact"
        confidence = "human_reviewed"
        rationale = str(semantic_spec.get("rationale") or "").strip()
    elif table.name in REVIEWED_ODS_DISPOSITIONS:
        disposition = REVIEWED_ODS_DISPOSITIONS[table.name]
        target_layer = "NONE"
        target_table = ""
        confidence = "candidate"
        rationale = (
            "经人工复核不应直接生成分析事实；保留受控 ODS，并按明确的规则、"
            "关系或运维用途参与后续模型设计。"
        )
    else:
        disposition = _candidate_disposition(table, kind)
        target_layer = "NONE"
        target_table = ""
        if disposition == "security_excluded":
            confidence = "security_reviewed"
            rationale = (
                "包含秘密、认证信息或高风险自由文本，仅保留受限 ODS，"
                "禁止进入普通分析层。"
            )
        else:
            confidence = "candidate"
            rationale = (
                "已完成领域和处置分类；未通过独立粒度评审，保留 ODS 并作为后续"
                "维度、事实、快照或运维模型的候选组成来源。"
            )
    downstream_targets = [target_table] if target_table else []
    primary_keys = [
        column.name
        for column in table.columns.values()
        if column.is_primary_key
    ]
    semantic_grain = (semantic_spec or {}).get("grain") or {}
    grain_columns = semantic_grain.get("columns") or []
    grain = ", ".join(
        grain_columns
        or primary_keys
        or (["id"] if "id" in table.columns else [])
    )
    if not grain:
        grain = "source row"
    return MappingEntry(
        source_table=table.name,
        ods_table=f"ods_fineract_{table.name.lower()}",
        business_area=domain.business_area,
        data_domain=domain.code,
        domain_name=domain.name,
        source_kind=kind,
        disposition=disposition,
        target_layer=target_layer,
        target_table=target_table,
        downstream_targets=downstream_targets,
        grain=grain,
        load_strategy=(
            "full_snapshot"
            if target_layer == "DIM"
            else "full_replay"
            if target_layer == "DWD"
            else "ods_full_snapshot"
        ),
        optional_module=domain.code in {"WCLN", "INVS"}
        or table.name.startswith(("m_share_", "m_survey", "ppi_")),
        confidence=confidence,
        business_processes=(
            [semantic_spec["business_process"]]
            if semantic_spec and semantic_spec.get("business_process")
            else _business_processes(table, domain.code)
        ),
        quality_rules=_quality_rules(table),
        sensitivity=(
            str((semantic_spec.get("sensitivity") or {}).get("level"))
            if semantic_spec
            and isinstance(semantic_spec.get("sensitivity"), dict)
            and (semantic_spec.get("sensitivity") or {}).get("level")
            else _sensitivity(table)
        ),
        rationale=rationale,
    )


def _git_commit(fineract_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(fineract_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _schema_payload(table: TableSchema) -> dict:
    return {
        "source_table": table.name,
        "columns": [asdict(column) for column in table.columns.values()],
        "primary_key": table.primary_key,
        "unique_constraints": table.unique_constraints,
        "foreign_keys": table.foreign_keys,
        "source_files": table.source_files,
        "raw_sql_warnings": table.raw_sql_warnings,
        "unresolved_changes": table.unresolved_changes,
    }


def write_inventory(
    *,
    tables: dict[str, TableSchema],
    fineract_root: Path,
    output_dir: Path,
) -> None:
    """Write the schema snapshot and complete table mapping artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    commit = _git_commit(fineract_root)
    mappings = [build_mapping_entry(table) for table in tables.values()]
    metadata = {
        "version": 1,
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": commit,
        "source_database": "postgresql",
        "active_table_count": len(tables),
        "analytical_ods_table_count": len(tables),
        "excluded_spring_batch_table_count": 6,
        "excluded_tenant_store_table_count": 4,
        "fineract_physical_table_count": len(tables) + 10,
        "mapped_downstream_count": sum(
            1 for mapping in mappings if mapping.target_table
        ),
    }
    schema_path = output_dir / "fineract_schema_snapshot.yaml"
    schema_path.write_text(
        yaml.safe_dump(
            {
                **metadata,
                "unresolved_changes": getattr(
                    tables, "unresolved_changes", []
                ),
                "tables": [
                    _schema_payload(table) for table in tables.values()
                ],
            },
            allow_unicode=True,
            sort_keys=False,
            width=100,
        ),
        encoding=TEXT_ENCODING,
    )
    mapping_path = output_dir / "fineract_table_mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(
            {
                **metadata,
                "mappings": [asdict(mapping) for mapping in mappings],
            },
            allow_unicode=True,
            sort_keys=False,
            width=100,
        ),
        encoding=TEXT_ENCODING,
    )
    csv_path = output_dir / "fineract_table_mapping.csv"
    with csv_path.open("w", encoding=TEXT_ENCODING, newline="") as handle:
        writer = csv.DictWriter(
            handle,
            lineterminator="\n",
            fieldnames=[
                "source_table",
                "ods_table",
                "business_area",
                "data_domain",
                "domain_name",
                "source_kind",
                "disposition",
                "target_layer",
                "target_table",
                "grain",
                "load_strategy",
                "optional_module",
                "confidence",
                "sensitivity",
                "rationale",
            ],
        )
        writer.writeheader()
        for mapping in mappings:
            row = asdict(mapping)
            row.pop("downstream_targets")
            row.pop("business_processes")
            row.pop("quality_rules")
            writer.writerow(row)
    write_mapping_markdown(
        mappings=mappings,
        metadata=metadata,
        output_path=PROJECT_DIR / "docs/fineract_table_mapping.md",
    )
    LOGGER.info(
        "Wrote %d active Fineract tables to %s", len(tables), output_dir
    )


def write_mapping_markdown(
    *,
    mappings: list[MappingEntry],
    metadata: dict,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    domain_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    for mapping in mappings:
        domain_key = f"{mapping.data_domain} {mapping.domain_name}"
        domain_counts[domain_key] = domain_counts.get(domain_key, 0) + 1
        layer_counts[mapping.target_layer] = (
            layer_counts.get(mapping.target_layer, 0) + 1
        )
    lines = [
        "# Fineract 表到零售银行数仓映射清单",
        "",
        f"- 上游仓库：`{metadata['upstream_repository']}`",
        f"- 固定 commit：`{metadata['upstream_commit']}`",
        f"- 活动源表：{metadata['active_table_count']}",
        f"- 建设下游的源表：{metadata['mapped_downstream_count']}",
        "- 口径：标准 Fineract PostgreSQL clean-install tenant changelog；不包含 tenant-store、custom 示例和历史 upgrade-only changelog。",
        "",
        "## 领域统计",
        "",
        "| 数据域 | 表数 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {domain} | {count} |"
        for domain, count in sorted(domain_counts.items())
    )
    lines.extend(
        [
            "",
            "## 目标层统计",
            "",
            "| 目标层 | 源表数 |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| {layer} | {count} |"
        for layer, count in sorted(layer_counts.items())
    )
    lines.extend(
        [
            "",
            "## 完整映射",
            "",
            "| Fineract 表 | ODS | 业务域 | disposition | 置信度 | 目标层 | 第一目标表 | 粒度 |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for mapping in mappings:
        lines.append(
            "| {source} | {ods} | {domain} | {disposition} | {confidence} | {layer} | "
            "{target} | {grain} |".format(
                source=mapping.source_table,
                ods=mapping.ods_table,
                domain=f"{mapping.data_domain} {mapping.domain_name}",
                disposition=mapping.disposition,
                confidence=mapping.confidence,
                layer=mapping.target_layer,
                target=mapping.target_table or "—",
                grain=mapping.grain,
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding=TEXT_ENCODING)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser(
        "inventory", help="Generate the complete Fineract table mapping"
    )
    inventory.add_argument(
        "--fineract-root", type=Path, required=True, help="Fineract checkout"
    )
    inventory.add_argument(
        "--output-dir", type=Path, default=PROJECT_DIR / "mappings"
    )
    inventory.add_argument(
        "--unresolved-overrides",
        type=Path,
        help=(
            "YAML file with explicit table/pattern/rationale entries for raw "
            "SQL changes that were reviewed outside the compiler"
        ),
    )
    return parser


def _load_unresolved_overrides(path: Optional[Path]) -> list[dict]:
    if path is None:
        return []
    payload = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    if not isinstance(payload, dict) or not isinstance(
        payload.get("overrides"), list
    ):
        raise ValueError(
            "Unresolved override YAML must contain an 'overrides' list: "
            f"{path}"
        )
    return payload["overrides"]


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "inventory":
        fineract_root = args.fineract_root.resolve()
        tables = parse_fineract_schema(
            fineract_root,
            unresolved_overrides=_load_unresolved_overrides(
                args.unresolved_overrides
            ),
        )
        write_inventory(
            tables=tables,
            fineract_root=fineract_root,
            output_dir=args.output_dir.resolve(),
        )
        return 0
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
