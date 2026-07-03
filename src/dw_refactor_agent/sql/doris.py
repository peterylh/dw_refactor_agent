from __future__ import annotations

import re
from typing import List, Tuple

_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>(?:`?[\w]+`?\.)?`?[\w]+`?)",
    flags=re.IGNORECASE,
)


def _strip_identifier(value: str) -> str:
    text = str(value or "").strip()
    while len(text) >= 2 and (
        (text[0] == text[-1] == "`") or (text[0] == text[-1] == '"')
    ):
        text = text[1:-1].strip()
    return text


def _split_identifier_list(value: str) -> List[str]:
    identifiers = []
    for item in str(value or "").split(","):
        name = _strip_identifier(item.strip())
        if name:
            identifiers.append(name)
    return identifiers


def _matching_paren_index(sql_text: str, open_index: int) -> int:
    depth = 0
    quote = ""
    i = open_index
    while i < len(sql_text):
        char = sql_text[i]
        if quote:
            if char == quote:
                if (
                    quote == "'"
                    and i + 1 < len(sql_text)
                    and sql_text[i + 1] == "'"
                ):
                    i += 2
                    continue
                quote = ""
            i += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def normalize_create_table_for_sqlglot(sql_text: str) -> str:
    """Return a Doris CREATE TABLE shape that sqlglot 26.9 can parse."""
    text = str(sql_text or "")
    match = _CREATE_TABLE_RE.search(text)
    if not match:
        return text

    open_index = text.find("(", match.end())
    if open_index < 0:
        return text
    close_index = _matching_paren_index(text, open_index)
    if close_index < 0:
        return text

    normalized = text[match.start() : close_index + 1].strip()
    suffix = text[close_index + 1 :]
    engine_match = re.search(
        r"\bENGINE\s*=\s*([A-Za-z_][\w]*)", suffix, flags=re.IGNORECASE
    )
    if engine_match:
        normalized = f"{normalized} ENGINE={engine_match.group(1)}"
    return normalized.rstrip(";") + ";"


def extract_create_table_name(sql_text: str) -> str:
    match = _CREATE_TABLE_RE.search(str(sql_text or ""))
    if not match:
        return ""
    return ".".join(
        _strip_identifier(part) for part in match.group("name").split(".")
    )


def extract_doris_key(sql_text: str) -> Tuple[str, List[str]]:
    match = re.search(
        r"\b(DUPLICATE|UNIQUE)\s+KEY\s*\((?P<columns>[^)]*)\)",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return "DUPLICATE", []
    return match.group(1).upper(), _split_identifier_list(
        match.group("columns")
    )


def extract_doris_distribution_column(sql_text: str) -> str:
    match = re.search(
        r"\bDISTRIBUTED\s+BY\s+HASH\s*\((?P<columns>[^)]*)\)",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    columns = _split_identifier_list(match.group("columns"))
    return columns[0] if columns else ""


def extract_doris_partition_column(sql_text: str) -> str:
    match = re.search(
        r"\bPARTITION\s+BY\s+RANGE\s*\(\s*(?P<column>`?[\w]+`?)\s*\)",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    )
    return _strip_identifier(match.group("column")) if match else ""
