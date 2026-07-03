import re
from pathlib import Path

import dw_refactor_agent.config as config

ROOT = Path(__file__).resolve().parent.parent


def _shop_non_ods_ddls():
    return [
        path
        for path in config.iter_project_asset_files("shop", "ddl", "*.sql")
        if "ods" not in path.relative_to(config.project_dir("shop")).parts
    ]


def _split_top_level_csv(text):
    parts = []
    start = 0
    depth = 0
    in_quote = None
    for idx, char in enumerate(text):
        if in_quote:
            if char == in_quote:
                in_quote = None
            continue
        if char in {"'", '"', "`"}:
            in_quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:idx])
            start = idx + 1
    parts.append(text[start:])
    return parts


def _column_names(create_body):
    columns = []
    for part in _split_top_level_csv(create_body):
        line = part.strip()
        if not line:
            continue
        first = line.split(None, 1)[0].strip("`")
        if first.upper() in {"UNIQUE", "DUPLICATE", "AGGREGATE", "KEY"}:
            continue
        columns.append(first)
    return columns


def _ddl_create_body(sql_text):
    match = re.search(
        r"CREATE\s+TABLE\b.*?\((?P<body>.*)\)\s*ENGINE\s*=\s*OLAP",
        sql_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def _key_columns(sql_text):
    match = re.search(
        r"\b(?:UNIQUE|DUPLICATE|AGGREGATE)\s+KEY\s*\((?P<cols>[^)]*)\)",
        sql_text,
        flags=re.IGNORECASE,
    )
    assert match is not None
    return [col.strip().strip("`") for col in match.group("cols").split(",")]


def _key_type(sql_text):
    match = re.search(
        r"\b(?P<type>UNIQUE|DUPLICATE|AGGREGATE)\s+KEY\s*\(",
        sql_text,
        flags=re.IGNORECASE,
    )
    assert match is not None
    return match.group("type").upper()


def _partition_columns(sql_text):
    match = re.search(
        r"\bPARTITION\s+BY\s+RANGE\s*\((?P<cols>[^)]*)\)",
        sql_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return []
    return [col.strip().strip("`") for col in match.group("cols").split(",")]


def test_shop_doris_key_columns_are_declared_prefixes():
    for ddl_file in _shop_non_ods_ddls():
        sql_text = ddl_file.read_text(encoding="utf-8")
        columns = _column_names(_ddl_create_body(sql_text))
        key_columns = _key_columns(sql_text)

        assert columns[: len(key_columns)] == key_columns, ddl_file


def test_shop_unique_key_partition_columns_are_key_columns():
    for ddl_file in _shop_non_ods_ddls():
        sql_text = ddl_file.read_text(encoding="utf-8")
        if _key_type(sql_text) != "UNIQUE":
            continue

        key_columns = set(_key_columns(sql_text))
        partition_columns = set(_partition_columns(sql_text))

        assert partition_columns <= key_columns, ddl_file
