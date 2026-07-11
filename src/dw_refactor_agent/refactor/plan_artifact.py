"""Read and write verification plan artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING

_SAFE_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_TOP_LEVEL_CLAUSES = (
    "AGGREGATE KEY",
    "DUPLICATE KEY",
    "UNIQUE KEY",
    "PRIMARY KEY",
    "PARTITION BY",
    "DISTRIBUTED BY",
    "PROPERTIES",
    "ENGINE",
)


def _leading_comment_lines(sql_text: str) -> tuple[list[str], str]:
    lines = sql_text.splitlines()
    prefix = []
    while lines and (
        not lines[0].strip() or lines[0].lstrip().startswith("--")
    ):
        prefix.append(lines.pop(0))
    return prefix, "\n".join(lines).strip()


def _append_space(output: list[str]) -> None:
    if output and not output[-1].endswith((" ", "\n")):
        output.append(" ")


def _append_newline(output: list[str], indent: int) -> None:
    while output and output[-1] == " ":
        output.pop()
    if output and not output[-1].endswith("\n"):
        output.append("\n")
    output.append("    " * max(indent, 0))


def _matches_clause(sql_text: str, index: int) -> str:
    remainder = sql_text[index:]
    for clause in _TOP_LEVEL_CLAUSES:
        if not remainder.upper().startswith(clause):
            continue
        end = index + len(clause)
        if end == len(sql_text) or not (
            sql_text[end].isalnum() or sql_text[end] == "_"
        ):
            return sql_text[index:end]
    return ""


def _format_dense_statement(sql_text: str) -> str:
    output: list[str] = []
    depth = 0
    multiline_depths: set[int] = set()
    quote = ""
    block_comment = False
    table_body_formatted = False
    index = 0

    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""

        if block_comment:
            output.append(char)
            if char == "*" and next_char == "/":
                output.append(next_char)
                index += 2
                block_comment = False
            else:
                index += 1
            continue

        if quote:
            output.append(char)
            if char == quote:
                if next_char == quote and quote in ("'", '"'):
                    output.append(next_char)
                    index += 2
                    continue
                quote = ""
            elif char == "\\" and next_char:
                output.append(next_char)
                index += 2
                continue
            index += 1
            continue

        if char == "/" and next_char == "*":
            _append_space(output)
            output.extend((char, next_char))
            block_comment = True
            index += 2
            continue
        if char in ("'", '"', "`"):
            output.append(char)
            quote = char
            index += 1
            continue
        if char.isspace():
            _append_space(output)
            index += 1
            continue

        if depth == 0:
            clause = _matches_clause(sql_text, index)
            if clause:
                _append_newline(output, 0)
                output.append(clause)
                index += len(clause)
                continue

        if char == "(":
            depth += 1
            output.append(char)
            prefix = "".join(output).rstrip().upper()
            is_table_body = (
                depth == 1
                and not table_body_formatted
                and prefix.startswith("CREATE TABLE ")
            )
            is_properties = depth == 1 and (
                prefix.endswith("PROPERTIES(")
                or prefix.endswith("PROPERTIES (")
            )
            if is_table_body or is_properties:
                multiline_depths.add(depth)
                table_body_formatted = table_body_formatted or is_table_body
                _append_newline(output, depth)
            index += 1
            continue
        if char == "," and depth in multiline_depths:
            output.append(char)
            _append_newline(output, depth)
            index += 1
            continue
        if char == ")":
            if depth in multiline_depths:
                _append_newline(output, depth - 1)
                multiline_depths.remove(depth)
            output.append(char)
            depth = max(depth - 1, 0)
            index += 1
            continue

        output.append(char)
        index += 1

    return "".join(output).strip()


def format_baseline_ddl(ddl_text: str) -> str:
    """Return readable DDL without regenerating Doris SQL through an AST."""
    raw = str(ddl_text or "").strip()
    if not raw:
        return ""
    prefix, statement = _leading_comment_lines(raw)
    statement_lines = statement.splitlines()
    if len(statement_lines) <= 1:
        statement = _format_dense_statement(statement)
    parts = prefix + ([statement] if statement else [])
    return "\n".join(parts).rstrip() + "\n"


def _validate_table_name(table_name: str) -> str:
    value = str(table_name or "")
    if not _SAFE_TABLE_NAME_RE.fullmatch(value):
        raise ValueError(f"invalid baseline DDL table name: {table_name!r}")
    return value


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_verification_plan(plan_path: Path, plan: dict) -> dict:
    """Externalize baseline DDL and write the persisted verification plan."""
    plan_path = Path(plan_path)
    ddl_by_table = plan.get("baseline_ddl")
    if not isinstance(ddl_by_table, dict):
        raise ValueError("verification plan baseline_ddl must be a mapping")

    formatted_by_table = {}
    for table_name, ddl_text in sorted(ddl_by_table.items()):
        safe_name = _validate_table_name(table_name)
        formatted_by_table[safe_name] = format_baseline_ddl(ddl_text)

    ddl_dir = plan_path.parent / "baseline_ddl"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    refs = {}
    expected_paths = set()
    for table_name, ddl_text in formatted_by_table.items():
        ddl_path = ddl_dir / f"{table_name}.sql"
        content = ddl_text.encode(TEXT_ENCODING)
        ddl_path.write_bytes(content)
        expected_paths.add(ddl_path)
        refs[table_name] = {
            "path": f"baseline_ddl/{table_name}.sql",
            "sha256": _sha256(content),
        }

    persisted = deepcopy(plan)
    persisted.pop("baseline_ddl", None)
    persisted["baseline_ddl_refs"] = refs
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(persisted, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    for stale_path in ddl_dir.glob("*.sql"):
        if stale_path not in expected_paths:
            stale_path.unlink()
    return persisted


def _resolved_reference_path(
    plan_path: Path, table_name: str, reference_path: str
) -> Path:
    relative_path = Path(reference_path)
    if relative_path.is_absolute():
        raise ValueError(
            f"unsafe baseline DDL path for {table_name}: {reference_path}"
        )
    plan_dir = plan_path.parent.resolve()
    resolved = (plan_dir / relative_path).resolve()
    try:
        resolved.relative_to(plan_dir)
    except ValueError:
        raise ValueError(
            f"unsafe baseline DDL path for {table_name}: {reference_path}"
        ) from None
    return resolved


def load_verification_plan(plan_path: Path) -> dict:
    """Load references, verify their bytes, and materialize baseline DDL."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    if "baseline_ddl" in plan:
        raise ValueError(
            "legacy verification plan contains embedded baseline_ddl; "
            "run analyze again to create referenced baseline DDL artifacts"
        )
    refs = plan.get("baseline_ddl_refs")
    if not isinstance(refs, dict):
        raise ValueError(
            "verification plan baseline_ddl_refs must be a mapping"
        )

    ddl_by_table = {}
    for raw_table_name, reference in sorted(refs.items()):
        table_name = _validate_table_name(raw_table_name)
        if not isinstance(reference, dict):
            raise ValueError(
                f"baseline DDL reference for {table_name} must be a mapping"
            )
        reference_path = reference.get("path")
        if not isinstance(reference_path, str) or not reference_path.strip():
            raise ValueError(
                f"baseline DDL reference path must be a non-empty string "
                f"for {table_name}"
            )
        expected_digest = reference.get("sha256")
        if not isinstance(expected_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_digest
        ):
            raise ValueError(
                "baseline DDL reference sha256 must be 64 lowercase hex "
                f"characters for {table_name}"
            )
        ddl_path = _resolved_reference_path(
            plan_path,
            table_name,
            reference_path,
        )
        if not ddl_path.is_file():
            raise ValueError(
                f"baseline DDL for {table_name} does not exist: "
                f"{reference_path}"
            )
        content = ddl_path.read_bytes()
        actual_digest = _sha256(content)
        if actual_digest != expected_digest:
            raise ValueError(
                f"baseline DDL for {table_name} has SHA-256 mismatch: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        try:
            ddl_by_table[table_name] = content.decode(TEXT_ENCODING)
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"baseline DDL for {table_name} is not valid {TEXT_ENCODING}: "
                f"{reference_path}"
            ) from exc

    executable = deepcopy(plan)
    executable["baseline_ddl"] = ddl_by_table
    return executable
