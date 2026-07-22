from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import List, Tuple

from dw_refactor_agent.refactor.shadow_scope import (
    Overlap,
    RowScope,
    ScopeKind,
)

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
        r"\bPARTITION\s+BY\s+(?:RANGE|LIST)\s*"
        r"\(\s*(?P<column>`?[\w]+`?)\s*\)",
        str(sql_text or ""),
        flags=re.IGNORECASE,
    )
    return _strip_identifier(match.group("column")) if match else ""


class PartitionSelectionKind(Enum):
    EMPTY = "empty"
    PARTITIONS = "partitions"
    FULL = "full"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PartitionSelection:
    kind: PartitionSelectionKind
    partitions: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class PartitionDef:
    name: str
    scope: RowScope


@dataclass(frozen=True)
class PartitionCatalog:
    column: str
    partitions: tuple[PartitionDef, ...] = ()
    unpartitioned: bool = False
    complete: bool = True

    def map_scope(self, scope: RowScope) -> PartitionSelection:
        if scope.kind is ScopeKind.EMPTY:
            return PartitionSelection(PartitionSelectionKind.EMPTY)
        if self.unpartitioned:
            return PartitionSelection(PartitionSelectionKind.FULL)
        if not self.partitions:
            return PartitionSelection(
                PartitionSelectionKind.UNKNOWN,
                reason="partitioned table has no static partitions",
            )
        if scope.kind is ScopeKind.UNKNOWN:
            return PartitionSelection(
                PartitionSelectionKind.UNKNOWN, reason=scope.reason
            )
        if self.column.casefold() != scope.column.casefold():
            return PartitionSelection(
                PartitionSelectionKind.UNKNOWN,
                reason="scope and partition columns differ",
            )
        selected = []
        for partition in self.partitions:
            overlap = partition.scope.overlap(scope)
            if overlap is Overlap.UNKNOWN:
                return PartitionSelection(
                    PartitionSelectionKind.UNKNOWN,
                    reason=f"cannot compare partition {partition.name}",
                )
            if overlap is Overlap.OVERLAP:
                selected.append(partition.name)
        if not selected:
            if not self.complete:
                return PartitionSelection(
                    PartitionSelectionKind.UNKNOWN,
                    reason="runtime partitions may not be present in static DDL",
                )
            return PartitionSelection(PartitionSelectionKind.EMPTY)
        return PartitionSelection(
            PartitionSelectionKind.PARTITIONS, tuple(selected)
        )


def _split_top_level(value: str) -> List[str]:
    items = []
    start = 0
    depth = 0
    quote = ""
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        items.append(tail)
    return items


def _partition_scalar(value: str):
    text = str(value or "").strip()
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    text = text.strip("'\"`").strip()
    if text.upper() in {"MAXVALUE", "MINVALUE"}:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass
    try:
        if "T" in text or " " in text:
            return datetime.fromisoformat(text)
        return date.fromisoformat(text)
    except ValueError:
        return text


def _partition_body(sql_text: str):
    match = re.search(
        r"\bPARTITION\s+BY\s+(?P<kind>RANGE|LIST)\s*"
        r"\(\s*(?P<column>`?[\w]+`?)\s*\)\s*\(",
        sql_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    open_index = match.end() - 1
    remainder = sql_text[open_index + 1 :]
    terminator = re.search(
        r"(?m)^\s*\)\s*(?=DISTRIBUTED\b|PROPERTIES\b|;|$)",
        remainder,
        flags=re.IGNORECASE,
    )
    close_index = (
        open_index + 1 + terminator.start()
        if terminator
        else _matching_paren_index(sql_text, open_index)
    )
    if close_index < 0:
        return None
    return (
        match.group("kind").upper(),
        _strip_identifier(match.group("column")),
        sql_text[open_index + 1 : close_index],
    )


def _parse_range_partition(
    clause: str, column: str, previous_upper
) -> tuple[PartitionDef, object]:
    name_match = re.match(
        r"\s*PARTITION\s+(?P<name>`?[\w]+`?)\s+VALUES\s+",
        clause,
        flags=re.IGNORECASE,
    )
    if not name_match:
        raise ValueError("invalid RANGE partition clause")
    name = _strip_identifier(name_match.group("name"))
    values = clause[name_match.end() :].strip()
    less_than = re.match(
        r"LESS\s+THAN\s*\((?P<upper>.*)\)\s*$",
        values,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if less_than:
        upper = _partition_scalar(less_than.group("upper"))
        scope = RowScope.interval(column, previous_upper, upper)
        return PartitionDef(name, scope), upper
    fixed = re.match(
        r"[\[(]\s*\((?P<lower>.*?)\)\s*,\s*"
        r"\((?P<upper>.*?)\)\s*[)\]]\s*$",
        values,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fixed:
        lower = _partition_scalar(fixed.group("lower"))
        upper = _partition_scalar(fixed.group("upper"))
        return PartitionDef(
            name, RowScope.interval(column, lower, upper)
        ), upper
    raise ValueError(f"unsupported RANGE partition: {clause}")


def _parse_list_partition(clause: str, column: str) -> PartitionDef:
    match = re.match(
        r"\s*PARTITION\s+(?P<name>`?[\w]+`?)\s+"
        r"VALUES\s+IN\s*\((?P<values>.*)\)\s*$",
        clause,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"unsupported LIST partition: {clause}")
    values = tuple(
        _partition_scalar(item)
        for item in _split_top_level(match.group("values"))
    )
    return PartitionDef(
        _strip_identifier(match.group("name")),
        RowScope.from_points(column, values),
    )


def parse_doris_partitions(sql_text: str) -> PartitionCatalog:
    """Parse static Doris RANGE/LIST partitions conservatively."""
    ddl_text = str(sql_text or "")
    parsed = _partition_body(ddl_text)
    if parsed is None:
        return PartitionCatalog("", unpartitioned=True)
    kind, column, body = parsed
    clauses = _split_top_level(body)
    partitions = []
    if kind == "RANGE":
        previous_upper = None
        for clause in clauses:
            partition, previous_upper = _parse_range_partition(
                clause, column, previous_upper
            )
            partitions.append(partition)
    else:
        partitions = [
            _parse_list_partition(clause, column) for clause in clauses
        ]
    runtime_partitioned = re.search(
        r"[\"']dynamic_partition\.enable[\"']\s*=\s*[\"']true[\"']",
        ddl_text,
        flags=re.IGNORECASE,
    ) or re.search(r"\bAUTO\s+PARTITION\s+BY\b", ddl_text, re.IGNORECASE)
    return PartitionCatalog(
        column,
        tuple(partitions),
        complete=runtime_partitioned is None,
    )


def _parse_runtime_range(value: str, column: str) -> RowScope:
    match = re.search(
        r"\[\s*\((?P<lower>.*?)\)\s*,\s*\((?P<upper>.*?)\)\s*\)",
        value,
    )
    if not match:
        return RowScope.unknown(
            column, f"unrecognized partition range: {value}"
        )
    return RowScope.interval(
        column,
        _partition_scalar(match.group("lower")),
        _partition_scalar(match.group("upper")),
    )


def parse_show_partitions(output: str, column: str) -> PartitionCatalog:
    """Parse tab-separated SHOW PARTITIONS output."""
    rows = [
        line.split("\t") for line in str(output or "").splitlines() if line
    ]
    if not rows:
        return PartitionCatalog(column)
    headers = {name.casefold(): index for index, name in enumerate(rows[0])}
    name_index = headers.get("partitionname")
    range_index = headers.get("range")
    if name_index is None or range_index is None:
        return PartitionCatalog(column)
    partitions = []
    for row in rows[1:]:
        if max(name_index, range_index) >= len(row):
            continue
        partitions.append(
            PartitionDef(
                row[name_index], _parse_runtime_range(row[range_index], column)
            )
        )
    return PartitionCatalog(column, tuple(partitions))
