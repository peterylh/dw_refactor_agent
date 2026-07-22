"""Load and validate task SQL templates with their YAML contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple

import yaml

from .contract import TaskTemplateContract, parse_contract
from .errors import ContractValidationError
from .types import ParameterType

TEXT_ENCODING = "utf-8"
_PROP_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\$\{([a-z][a-z0-9_]*)\}")
_TOKEN_CHAR_RE = re.compile(r"[A-Za-z0-9_$]")
_RELATION_PREFIX_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|USING)\s+"
    r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
    r"(?:(?:\$\{[a-z][a-z0-9_]*\}|`?[A-Za-z_]"
    r"[A-Za-z0-9_]*`?)\s*\.\s*)*$",
    flags=re.IGNORECASE,
)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects silent last-key-wins behavior."""


def _construct_unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be scalar strings",
                key_node.start_mark,
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def canonical_json_bytes(value: object) -> bytes:
    """Serialize contract data deterministically for hashing."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(TEXT_ENCODING)


def sha256_bytes(value: bytes) -> str:
    """Return a namespaced SHA-256 digest."""
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


@dataclass(frozen=True)
class PlaceholderOccurrence:
    """One validated complete-token placeholder in SQL source text."""

    prop: str
    start: int
    end: int
    line: int
    column: int


@dataclass(frozen=True)
class TaskDefinition:
    """A template SQL file paired with one normalized variable contract."""

    sql_text: str
    contract: TaskTemplateContract
    placeholders: Tuple[PlaceholderOccurrence, ...]
    template_digest: str
    contract_digest: str
    sql_path: Optional[Path] = None
    contract_path: Optional[Path] = None

    @property
    def placeholder_names(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys(item.prop for item in self.placeholders))

    def normalized_summary(self) -> dict:
        """Return stable, path-independent facts for caches and artifacts."""
        return {
            "template_digest": self.template_digest,
            "contract_digest": self.contract_digest,
            "placeholder_names": list(self.placeholder_names),
            "contract": self.contract.redacted_dict(),
        }


def _location(sql_text: str, offset: int) -> Tuple[int, int]:
    line = sql_text.count("\n", 0, offset) + 1
    last_newline = sql_text.rfind("\n", 0, offset)
    column = offset + 1 if last_newline < 0 else offset - last_newline
    return line, column


def _invalid_placeholder(
    sql_text: str,
    offset: int,
    message: str,
    *,
    code: str,
) -> ContractValidationError:
    line, column = _location(sql_text, offset)
    return ContractValidationError(
        f"line {line}, column {column}: {message}",
        code=code,
        path=("sql", line, column),
    )


def _scan_placeholders(sql_text: str) -> Tuple[PlaceholderOccurrence, ...]:
    occurrences = []
    state = "normal"
    index = 0
    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""

        if sql_text.startswith("${", index):
            close = sql_text.find("}", index + 2)
            if close < 0:
                raise _invalid_placeholder(
                    sql_text,
                    index,
                    "placeholder has no closing brace",
                    code="template.sql.malformed_placeholder",
                )
            raw_prop = sql_text[index + 2 : close]
            if state != "normal":
                raise _invalid_placeholder(
                    sql_text,
                    index,
                    f"placeholder {raw_prop!r} is inside {state}",
                    code="template.sql.invalid_context",
                )
            if not _PROP_RE.fullmatch(raw_prop):
                raise _invalid_placeholder(
                    sql_text,
                    index,
                    f"invalid placeholder name {raw_prop!r}",
                    code="template.sql.invalid_placeholder",
                )
            before = sql_text[index - 1] if index else ""
            after = sql_text[close + 1] if close + 1 < len(sql_text) else ""
            if (before and _TOKEN_CHAR_RE.fullmatch(before)) or (
                after and _TOKEN_CHAR_RE.fullmatch(after)
            ):
                raise _invalid_placeholder(
                    sql_text,
                    index,
                    "placeholder must occupy a complete SQL token",
                    code="template.sql.embedded_placeholder",
                )
            line, column = _location(sql_text, index)
            occurrences.append(
                PlaceholderOccurrence(
                    prop=raw_prop,
                    start=index,
                    end=close + 1,
                    line=line,
                    column=column,
                )
            )
            index = close + 1
            continue

        if state == "normal":
            if char == "'":
                state = "string literal"
            elif char == '"':
                state = "double-quoted token"
            elif char == "`":
                state = "quoted identifier"
            elif char == "-" and next_char == "-":
                state = "line comment"
                index += 1
            elif char == "#":
                state = "line comment"
            elif char == "/" and next_char == "*":
                state = "block comment"
                index += 1
        elif state == "string literal":
            if char == "\\":
                index += 1
            elif char == "'":
                if next_char == "'":
                    index += 1
                else:
                    state = "normal"
        elif state == "double-quoted token":
            if char == "\\":
                index += 1
            elif char == '"':
                if next_char == '"':
                    index += 1
                else:
                    state = "normal"
        elif state == "quoted identifier":
            if char == "\\":
                index += 1
            elif char == "`":
                if next_char == "`":
                    index += 1
                else:
                    state = "normal"
        elif state == "line comment":
            if char in "\r\n":
                state = "normal"
        elif state == "block comment" and char == "*" and next_char == "/":
            state = "normal"
            index += 1
        index += 1
    return tuple(occurrences)


def _mask_non_code(sql_text: str) -> str:
    """Replace quoted/comment content while retaining SQL offsets."""
    masked = list(sql_text)
    state = "normal"
    index = 0
    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""
        if state == "normal":
            if char == "'":
                state = "string"
                masked[index] = " "
            elif char == '"':
                state = "double"
                masked[index] = " "
            elif char == "`":
                state = "backtick"
                masked[index] = " "
            elif char == "-" and next_char == "-":
                state = "line_comment"
                masked[index] = masked[index + 1] = " "
                index += 1
            elif char == "#":
                state = "line_comment"
                masked[index] = " "
            elif char == "/" and next_char == "*":
                state = "block_comment"
                masked[index] = masked[index + 1] = " "
                index += 1
        elif state in {"string", "double", "backtick"}:
            masked[index] = " "
            quote = {"string": "'", "double": '"', "backtick": "`"}[state]
            if char == "\\":
                if index + 1 < len(sql_text):
                    masked[index + 1] = " "
                    index += 1
            elif char == quote:
                if next_char == quote:
                    masked[index + 1] = " "
                    index += 1
                else:
                    state = "normal"
        elif state == "line_comment":
            if char in "\r\n":
                state = "normal"
            else:
                masked[index] = " "
        elif state == "block_comment":
            masked[index] = " "
            if char == "*" and next_char == "/":
                masked[index + 1] = " "
                state = "normal"
                index += 1
        index += 1
    return "".join(masked)


def _validate_placeholder_contexts(
    sql_text: str,
    occurrences: Iterable[PlaceholderOccurrence],
    parameters: Mapping[str, object],
) -> None:
    code_text = _mask_non_code(sql_text)
    for occurrence in occurrences:
        data_type = parameters[occurrence.prop].data_type
        is_identifier = data_type in {
            ParameterType.IDENTIFIER,
            ParameterType.QUALIFIED_IDENTIFIER,
        }
        statement_start = code_text.rfind(";", 0, occurrence.start) + 1
        prefix = code_text[statement_start : occurrence.start]
        suffix = code_text[occurrence.end :]
        previous = prefix.rstrip()[-1:] or ""
        following = suffix.lstrip()[:1] or ""
        identifier_position = bool(
            _RELATION_PREFIX_RE.search(prefix)
            or previous == "."
            or following in {".", "("}
        )
        if is_identifier and not identifier_position:
            raise _invalid_placeholder(
                sql_text,
                occurrence.start,
                f"identifier {occurrence.prop!r} is not in an identifier position",
                code="template.sql.invalid_identifier_context",
            )
        if not is_identifier and identifier_position:
            raise _invalid_placeholder(
                sql_text,
                occurrence.start,
                f"literal {occurrence.prop!r} is in an identifier position",
                code="template.sql.invalid_literal_context",
            )


def _relevant_parameters(
    contract: TaskTemplateContract,
    placeholder_names: Iterable[str],
) -> set:
    relevant = set(placeholder_names) | set(contract.usage.referenced_props())
    parameters = contract.parameters_by_name
    pending = list(relevant)
    while pending:
        prop = pending.pop()
        definition = parameters.get(prop)
        if definition is None:
            continue
        for dependency in definition.dependencies():
            if dependency not in relevant:
                relevant.add(dependency)
                pending.append(dependency)
    return relevant


def build_task_definition(
    sql_text: str,
    contract_data: object,
    *,
    sql_path: Optional[Path] = None,
    contract_path: Optional[Path] = None,
) -> TaskDefinition:
    """Build a definition from in-memory content and validate the pair."""
    if not isinstance(sql_text, str):
        raise ContractValidationError(
            f"SQL template must be text, received {type(sql_text).__name__}",
            code="template.sql.invalid_shape",
            path=("sql",),
        )
    contract = parse_contract(contract_data)
    occurrences = _scan_placeholders(sql_text)
    parameters = contract.parameters_by_name
    placeholder_names = tuple(dict.fromkeys(item.prop for item in occurrences))
    unknown = sorted(set(placeholder_names) - set(parameters))
    if unknown:
        raise ContractValidationError(
            f"SQL references undeclared parameters: {', '.join(unknown)}",
            code="template.sql.unknown_parameter",
            path=("sql",),
        )
    _validate_placeholder_contexts(sql_text, occurrences, parameters)
    if contract.strict:
        relevant = _relevant_parameters(contract, placeholder_names)
        unused = sorted(set(parameters) - relevant)
        if unused:
            raise ContractValidationError(
                f"declared parameters are unused: {', '.join(unused)}",
                code="template.contract.unused_parameter",
                path=("parameters",),
            )
    contract_dict = contract.as_dict()
    return TaskDefinition(
        sql_text=sql_text,
        contract=contract,
        placeholders=occurrences,
        template_digest=sha256_bytes(sql_text.encode(TEXT_ENCODING)),
        contract_digest=sha256_bytes(canonical_json_bytes(contract_dict)),
        sql_path=Path(sql_path) if sql_path is not None else None,
        contract_path=(
            Path(contract_path) if contract_path is not None else None
        ),
    )


def load_task_definition(
    sql_path: Path,
    contract_path: Path,
) -> TaskDefinition:
    """Read one explicit SQL/YAML pair without discovering project assets."""
    sql_source = Path(sql_path)
    yaml_source = Path(contract_path)
    try:
        sql_text = sql_source.read_text(encoding=TEXT_ENCODING)
    except (OSError, UnicodeError) as exc:
        raise ContractValidationError(
            f"cannot read SQL template {sql_source}: {exc}",
            code="template.sql.read_failed",
            path=(str(sql_source),),
        ) from exc
    try:
        raw = yaml.load(
            yaml_source.read_text(encoding=TEXT_ENCODING),
            Loader=_UniqueKeySafeLoader,
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ContractValidationError(
            f"cannot read task contract {yaml_source}: {exc}",
            code="template.contract.read_failed",
            path=(str(yaml_source),),
        ) from exc
    return build_task_definition(
        sql_text,
        raw,
        sql_path=sql_source,
        contract_path=yaml_source,
    )


__all__ = [
    "PlaceholderOccurrence",
    "TaskDefinition",
    "build_task_definition",
    "canonical_json_bytes",
    "load_task_definition",
    "sha256_bytes",
]
