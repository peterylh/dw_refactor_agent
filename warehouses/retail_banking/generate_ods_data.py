#!/usr/bin/env python3
"""Generate deterministic medium-volume fixtures for every Fineract ODS table."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE = "retail_banking_dm"
TEXT_ENCODING = "utf-8"
BASE_DATE = date(2026, 5, 14)
DATE_WINDOW_DAYS = 62
MIN_ROWS_PER_TABLE = 1000
MAX_ROWS_PER_TABLE = 5000
INSERT_BATCH_SIZE = 200
ROW_COUNT_OVERRIDES = {
    # Keep the committed fixture aligned with the validated Doris dataset.
    "ods_fineract_x_table_column_code_mappings": 3463,
}


@dataclass(frozen=True)
class GenerationContext:
    schemas: dict[str, dict]
    columns: dict[str, dict[str, dict]]
    foreign_keys: dict[str, dict[str, dict]]
    row_counts: dict[str, int]


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


def _target_row_count(ods_table: str) -> int:
    if ods_table in ROW_COUNT_OVERRIDES:
        return ROW_COUNT_OVERRIDES[ods_table]
    digest = hashlib.sha256(ods_table.encode(TEXT_ENCODING)).digest()
    span = MAX_ROWS_PER_TABLE - MIN_ROWS_PER_TABLE + 1
    target = MIN_ROWS_PER_TABLE + int.from_bytes(digest[:4], "big") % span
    if ods_table == "ods_fineract_acc_gl_journal_entry" and target % 2:
        target = target + 1 if target < MAX_ROWS_PER_TABLE else target - 1
    return target


def _build_context(snapshot: dict, mapping: dict) -> GenerationContext:
    schemas = {table["source_table"]: table for table in snapshot["tables"]}
    columns = {
        table_name: {column["name"]: column for column in schema["columns"]}
        for table_name, schema in schemas.items()
    }
    foreign_keys: dict[str, dict[str, dict]] = {}
    for table_name, schema in schemas.items():
        by_column = {}
        for foreign_key in schema["foreign_keys"]:
            if len(foreign_key["base_columns"]) != 1:
                raise ValueError(
                    f"Composite foreign key is not supported: "
                    f"{table_name}.{foreign_key['name']}"
                )
            column_name = foreign_key["base_columns"][0]
            if column_name in by_column:
                existing = by_column[column_name]
                if (
                    existing["referenced_table"]
                    == foreign_key["referenced_table"]
                    and existing["referenced_columns"]
                    == foreign_key["referenced_columns"]
                ):
                    continue
                raise ValueError(
                    f"Conflicting foreign keys use {table_name}.{column_name}"
                )
            referenced_table = foreign_key["referenced_table"]
            if (
                referenced_table in schemas
                and foreign_key["referenced_columns"]
                != schemas[referenced_table]["primary_key"]
            ):
                raise ValueError(
                    f"Foreign key does not reference a complete primary key: "
                    f"{table_name}.{foreign_key['name']}"
                )
            by_column[column_name] = foreign_key
        foreign_keys[table_name] = by_column

    row_counts = {
        item["source_table"]: _target_row_count(item["ods_table"])
        for item in mapping["mappings"]
    }
    if set(row_counts) != set(schemas):
        raise ValueError("Schema snapshot and table mapping do not match")

    # A table whose single-column PK is also an FK cannot contain more rows
    # than its parent has distinct keys. Grow the parent deterministically;
    # every base target is already bounded by MAX_ROWS_PER_TABLE.
    changed = True
    while changed:
        changed = False
        for table_name, schema in schemas.items():
            primary_key = schema["primary_key"]
            if len(primary_key) != 1:
                continue
            foreign_key = foreign_keys[table_name].get(primary_key[0])
            if not foreign_key:
                continue
            referenced_table = foreign_key["referenced_table"]
            if referenced_table not in row_counts:
                continue
            required = row_counts[table_name]
            if row_counts[referenced_table] < required:
                row_counts[referenced_table] = required
                changed = True

    if not all(
        MIN_ROWS_PER_TABLE <= count <= MAX_ROWS_PER_TABLE
        for count in row_counts.values()
    ):
        raise ValueError("Resolved row counts exceed fixture bounds")

    return GenerationContext(
        schemas=schemas,
        columns=columns,
        foreign_keys=foreign_keys,
        row_counts=row_counts,
    )


def _date_offset(table_name: str, row_number: int) -> int:
    if table_name == "acc_gl_journal_entry":
        return ((row_number - 1) // 2) % DATE_WINDOW_DAYS
    return (row_number - 1) % DATE_WINDOW_DAYS


def _primary_key_capacity(
    context: GenerationContext,
    table_name: str,
    column_name: str,
) -> int:
    foreign_key = context.foreign_keys[table_name].get(column_name)
    if foreign_key and foreign_key["referenced_table"] in context.row_counts:
        return context.row_counts[foreign_key["referenced_table"]]
    return context.row_counts[table_name]


def _primary_key_ordinal(
    context: GenerationContext,
    table_name: str,
    column_name: str,
    row_number: int,
) -> int:
    primary_key = context.schemas[table_name]["primary_key"]
    position = primary_key.index(column_name)
    stride = 1
    for preceding_column in primary_key[:position]:
        stride *= _primary_key_capacity(context, table_name, preceding_column)
    capacity = _primary_key_capacity(context, table_name, column_name)
    return ((row_number - 1) // stride) % capacity + 1


def _key_string_value(row_number: int, length: int) -> str:
    value = f"PK-{row_number:08d}"
    if len(value) > length:
        value = str(row_number).zfill(length)[-length:]
    return value


def _string_value(
    table_name: str, column_name: str, row_number: int, length: int
) -> str:
    lower_name = column_name.lower()
    if table_name == "acc_gl_journal_entry" and lower_name == "transaction_id":
        value = f"GL-SYN-{(row_number + 1) // 2:08d}"
    elif lower_name in {"status", "state"}:
        value = "ACTIVE"
    elif "currency" in lower_name:
        value = "USD"
    elif "email" in lower_name:
        value = f"user{row_number}@example.com"
    elif "phone" in lower_name or "mobile" in lower_name:
        value = f"155{row_number:08d}"
    elif "account_no" in lower_name or "account_number" in lower_name:
        value = f"A{row_number:09d}"
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


def _numeric_value(
    table_name: str,
    column_name: str,
    source_type: str,
    row_number: int,
) -> str:
    lower_name = column_name.lower()
    if lower_name == "id":
        return str(row_number)
    if lower_name.endswith("_id"):
        return str((row_number - 1) % MIN_ROWS_PER_TABLE + 1)
    if "type_enum" in lower_name or lower_name.endswith("_enum"):
        if table_name == "acc_gl_journal_entry" and lower_name == "type_enum":
            return "1" if row_number % 2 else "2"
        return "1"
    if source_type.startswith("TINYINT"):
        return "1"
    if "status" in lower_name:
        return "300"
    if "version" in lower_name:
        return "1"
    if source_type.startswith(("DECIMAL", "FLOAT", "DOUBLE")):
        return "1.000000"
    return str(row_number)


def _value_for(
    context: GenerationContext,
    table_name: str,
    column: dict,
    row_number: int,
) -> str:
    column_name = column["name"]
    source_type = " ".join(str(column["source_type"]).upper().split())
    lower_name = column_name.lower()
    value_date = BASE_DATE + timedelta(
        days=_date_offset(table_name, row_number)
    )
    if lower_name == "load_time":
        return _sql_string(f"{value_date.isoformat()} 00:00:00")

    foreign_key = context.foreign_keys[table_name].get(column_name)
    if foreign_key and foreign_key["referenced_table"] in context.schemas:
        referenced_table = foreign_key["referenced_table"]
        if column_name in context.schemas[table_name]["primary_key"]:
            referenced_row = _primary_key_ordinal(
                context, table_name, column_name, row_number
            )
        else:
            referenced_row = (row_number - 1) % context.row_counts[
                referenced_table
            ] + 1
        referenced_column = foreign_key["referenced_columns"][0]
        return _value_for(
            context,
            referenced_table,
            context.columns[referenced_table][referenced_column],
            referenced_row,
        )

    is_primary_key = column_name in context.schemas[table_name]["primary_key"]
    primary_key_ordinal = (
        _primary_key_ordinal(context, table_name, column_name, row_number)
        if is_primary_key
        else None
    )
    if "BOOLEAN" in source_type:
        return (
            "TRUE"
            if lower_name in {"is_active", "active", "enabled"}
            else "FALSE"
        )
    if source_type in {"DATE", "DATE NULL"}:
        return _sql_string(value_date.isoformat())
    if "TIMESTAMP" in source_type or "DATETIME" in source_type:
        return _sql_string(f"{value_date.isoformat()} 09:00:00")
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
        if primary_key_ordinal is not None:
            return str(primary_key_ordinal)
        return _numeric_value(
            table_name,
            column_name,
            source_type,
            row_number,
        )
    length = _varchar_length(source_type)
    if primary_key_ordinal is not None:
        return _sql_string(_key_string_value(primary_key_ordinal, length))
    return _sql_string(
        _string_value(table_name, column_name, row_number, length)
    )


def _render_insert(
    mapping: dict,
    schema: dict,
    rows: int,
    context: GenerationContext,
) -> str:
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
    statements = [
        f"-- Deterministic medium-volume data for Fineract {source_table}",
        f"TRUNCATE TABLE {DATABASE}.{table_name};",
    ]
    for batch_start in range(1, rows + 1, INSERT_BATCH_SIZE):
        batch_end = min(rows, batch_start + INSERT_BATCH_SIZE - 1)
        value_rows = []
        for row_number in range(batch_start, batch_end + 1):
            values = ",\n        ".join(
                _value_for(context, source_table, column, row_number)
                for column in columns
            )
            value_rows.append(f"    (\n        {values}\n    )")
        statements.append(
            f"INSERT INTO {DATABASE}.{table_name} (\n    {column_sql}\n) VALUES\n"
            + ",\n".join(value_rows)
            + ";"
        )
    return "\n\n".join(statements) + "\n"


def generate(*, output_dir: Path) -> tuple[int, int]:
    snapshot = _load_yaml(
        PROJECT_DIR / "mappings/fineract_schema_snapshot.yaml"
    )
    mapping = _load_yaml(PROJECT_DIR / "mappings/fineract_table_mapping.yaml")
    context = _build_context(snapshot, mapping)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_path in output_dir.glob("*.sql"):
        old_path.unlink()
    table_count = 0
    row_count = 0
    for item in mapping["mappings"]:
        source_table = item["source_table"]
        rows = context.row_counts[source_table]
        sql = _render_insert(
            item,
            context.schemas[source_table],
            rows,
            context,
        )
        (output_dir / f"{item['ods_table']}.sql").write_text(
            sql, encoding=TEXT_ENCODING
        )
        table_count += 1
        row_count += rows
    return table_count, row_count


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
    tables, rows = generate(output_dir=args.output_dir.resolve())
    print(f"Generated {rows} deterministic ODS rows for {tables} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
