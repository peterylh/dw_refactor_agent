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
    return [
        column.strip().strip("`")
        for column in match.group(1).split(",")
    ]


def test_lineage_ddl_key_columns_are_schema_prefixes():
    ddl_dir = Path("lineage/ddl")

    for ddl_file in sorted(ddl_dir.glob("*.sql")):
        sql = ddl_file.read_text(encoding="utf-8")
        key_columns = _key_columns(sql)

        assert _column_names(sql)[:len(key_columns)] == key_columns, ddl_file
