#!/usr/bin/env python3
"""Generate deterministic schema-smoke rows for every Fineract ODS table."""

from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE = "retail_banking_dm"
TEXT_ENCODING = "utf-8"
BASE_DATE = date(2025, 1, 15)
MULTI_ROW_TABLES = {
    "acc_gl_journal_entry": 2,
    "m_account_transfer_transaction": 2,
    "m_cashier_transactions": 2,
    "m_client_transaction": 2,
    "m_loan_transaction": 4,
    "m_savings_account_transaction": 4,
    "m_share_account_transactions": 2,
    "m_wc_loan_transaction": 2,
}


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def _sql_string(value: str) -> str:
    return "'{}'".format(str(value).replace("'", "''"))


def _varchar_length(source_type: str) -> int:
    match = re.search(r"(?i)(?:VAR)?CHAR\s*\(\s*(\d+)\s*\)", source_type)
    return int(match.group(1)) if match else 255


def _string_value(
    table_name: str, column_name: str, row_number: int, length: int
) -> str:
    lower_name = column_name.lower()
    if "currency" in lower_name:
        value = "USD"
    elif "email" in lower_name:
        value = f"user{row_number}@example.com"
    elif "phone" in lower_name or "mobile" in lower_name:
        value = f"1550000{row_number:04d}"
    elif "account_no" in lower_name or "account_number" in lower_name:
        value = f"A{row_number:09d}"
    elif (
        "transaction_id" in lower_name and table_name == "acc_gl_journal_entry"
    ):
        value = "GL-00000001"
    elif "external_id" in lower_name or lower_name.endswith("uuid"):
        value = f"00000000-0000-4000-8000-{row_number:012d}"
    elif "locale" in lower_name:
        value = "en"
    elif "country" in lower_name:
        value = "US"
    elif (
        "password" in lower_name
        or "secret" in lower_name
        or "token" in lower_name
    ):
        value = "SYNTHETIC_REDACTED"
    elif (
        "json" in lower_name
        or "config" in lower_name
        or "payload" in lower_name
    ):
        value = "{}"
    elif lower_name in {"name", "display_name", "firstname", "lastname"}:
        value = f"Synthetic {table_name} {row_number}"
    else:
        value = f"{table_name}_{column_name}_{row_number}"
    if length <= 0:
        return ""
    return value[:length]


def _numeric_value(table_name: str, column_name: str, row_number: int) -> str:
    lower_name = column_name.lower()
    if lower_name == "id" or lower_name.endswith("_id"):
        return str(row_number if lower_name == "id" else 1)
    if "type_enum" in lower_name or lower_name.endswith("_enum"):
        if table_name == "acc_gl_journal_entry" and lower_name == "type_enum":
            return str(row_number)
        return "1"
    if "status" in lower_name:
        return "300"
    if "version" in lower_name:
        return "1"
    if any(
        keyword in lower_name
        for keyword in (
            "amount",
            "balance",
            "principal",
            "interest",
            "fee",
            "penalty",
        )
    ):
        return str(Decimal("100.000000"))
    return str(row_number)


def _value_for(table_name: str, column: dict, row_number: int) -> str:
    column_name = column["name"]
    source_type = " ".join(str(column["source_type"]).upper().split())
    lower_name = column_name.lower()
    if lower_name == "load_time":
        return _sql_string("2025-01-15 00:00:00")
    if "BOOLEAN" in source_type:
        return "FALSE"
    date_offset = 0 if table_name == "acc_gl_journal_entry" else row_number - 1
    if source_type in {"DATE", "DATE NULL"}:
        return _sql_string(
            (BASE_DATE + timedelta(days=date_offset)).isoformat()
        )
    if "TIMESTAMP" in source_type or "DATETIME" in source_type:
        value = BASE_DATE + timedelta(days=date_offset)
        return _sql_string(f"{value.isoformat()} 09:00:00")
    if source_type == "TIME":
        return _sql_string("09:00:00")
    if any(
        source_type.startswith(prefix)
        for prefix in (
            "BIGINT",
            "INT",
            "INTEGER",
            "SMALLINT",
            "TINYINT",
            "DECIMAL",
            "FLOAT",
            "DOUBLE",
        )
    ):
        return _numeric_value(table_name, column_name, row_number)
    length = _varchar_length(source_type)
    return _sql_string(
        _string_value(table_name, column_name, row_number, length)
    )


def _render_insert(mapping: dict, schema: dict, rows: int) -> str:
    table_name = mapping["ods_table"]
    source_table = mapping["source_table"]
    columns = list(schema["columns"])
    columns.append(
        {
            "name": "load_time",
            "source_type": "DATETIME",
            "nullable": False,
            "is_primary_key": False,
        }
    )
    column_sql = ",\n    ".join(f"`{column['name']}`" for column in columns)
    value_rows = []
    for row_number in range(1, rows + 1):
        values = ",\n        ".join(
            _value_for(source_table, column, row_number) for column in columns
        )
        value_rows.append(f"    (\n        {values}\n    )")
    return (
        f"-- Deterministic smoke data for Fineract {source_table}\n"
        f"TRUNCATE TABLE {DATABASE}.{table_name};\n\n"
        f"INSERT INTO {DATABASE}.{table_name} (\n    {column_sql}\n) VALUES\n"
        + ",\n".join(value_rows)
        + ";\n"
    )


def generate(*, output_dir: Path) -> int:
    snapshot = _load_yaml(
        PROJECT_DIR / "mappings/fineract_schema_snapshot.yaml"
    )
    mapping = _load_yaml(PROJECT_DIR / "mappings/fineract_table_mapping.yaml")
    schemas = {table["source_table"]: table for table in snapshot["tables"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_path in output_dir.glob("*.sql"):
        old_path.unlink()
    count = 0
    for item in mapping["mappings"]:
        source_table = item["source_table"]
        rows = MULTI_ROW_TABLES.get(source_table, 1)
        sql = _render_insert(item, schemas[source_table], rows)
        (output_dir / f"{item['ods_table']}.sql").write_text(
            sql, encoding=TEXT_ENCODING
        )
        count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "ods/data/internal/retail_banking_dm",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    count = generate(output_dir=args.output_dir.resolve())
    print(f"Generated deterministic ODS data for {count} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
