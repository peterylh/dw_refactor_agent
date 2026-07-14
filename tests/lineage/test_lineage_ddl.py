from __future__ import annotations

import re
from pathlib import Path


def _column_names(sql: str) -> list[str]:
    body = re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+\w+\s*\((.*?)\)\s*ENGINE",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    ).group(1)
    columns = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        columns.append(stripped.split()[0].strip("`,"))
    return columns


def _key_columns(sql: str) -> list[str]:
    match = re.search(
        r"(?:DUPLICATE|UNIQUE)\s+KEY\s*\((.*?)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return [column.strip().strip("`") for column in match.group(1).split(",")]


def test_lineage_ddl_key_columns_are_schema_prefixes():
    ddl_dir = Path("src/dw_refactor_agent/lineage/ddl")

    for ddl_file in sorted(ddl_dir.glob("*.sql")):
        sql = ddl_file.read_text(encoding="utf-8")
        key_columns = _key_columns(sql)

        assert _column_names(sql)[: len(key_columns)] == key_columns, ddl_file


def test_table_info_persists_dataset_type_with_legacy_compatibility_columns():
    sql = Path("src/dw_refactor_agent/lineage/ddl/table_info.sql").read_text(
        encoding="utf-8"
    )

    columns = _column_names(sql)

    assert "dataset_type" in columns
    assert "is_transient" in columns
    assert "transient_sources" in columns


def test_job_dataset_ddl_uses_snapshot_job_table_io_key_prefix():
    sql = Path("src/dw_refactor_agent/lineage/ddl/job_dataset.sql").read_text(
        encoding="utf-8"
    )

    assert _column_names(sql) == [
        "snapshot_id",
        "job_id",
        "table_id",
        "io_type",
    ]
    assert _key_columns(sql) == [
        "snapshot_id",
        "job_id",
        "table_id",
        "io_type",
    ]


def test_lineage_snapshot_counts_job_dataset_relationships():
    sql = Path(
        "src/dw_refactor_agent/lineage/ddl/lineage_snapshot.sql"
    ).read_text(encoding="utf-8")

    assert "job_dataset_count" in _column_names(sql)
