"""Strongly typed values and safe SQL token rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional, Sequence, Tuple

from .errors import ContractValidationError, TemplateRenderError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_FORMAT_PATTERNS = {
    "yyyy": "%Y",
    "yyyyMM": "%Y%m",
    "yyyyMMdd": "%Y%m%d",
    "yyyy-MM-dd": "%Y-%m-%d",
    "HH:mm:ss": "%H:%M:%S",
    "yyyy-MM-dd HH:mm:ss": "%Y-%m-%d %H:%M:%S",
    "yyyyMMddHHmmss": "%Y%m%d%H%M%S",
}
_FORMAT_VALUE_PATTERNS = {
    "yyyy": re.compile(r"^[0-9]{4}$"),
    "yyyyMM": re.compile(r"^[0-9]{6}$"),
    "yyyyMMdd": re.compile(r"^[0-9]{8}$"),
    "yyyy-MM-dd": re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    "HH:mm:ss": re.compile(r"^[0-9]{2}:[0-9]{2}:[0-9]{2}$"),
    "yyyy-MM-dd HH:mm:ss": re.compile(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2} "
        r"[0-9]{2}:[0-9]{2}:[0-9]{2}$"
    ),
    "yyyyMMddHHmmss": re.compile(r"^[0-9]{14}$"),
}
_MAX_NUMERIC_TOKEN_LENGTH = 1024


class ParameterType(Enum):
    """DolphinScheduler-compatible scalar types plus safe identifiers."""

    VARCHAR = "VARCHAR"
    INTEGER = "INTEGER"
    LONG = "LONG"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    DATE = "DATE"
    TIME = "TIME"
    TIMESTAMP = "TIMESTAMP"
    BOOLEAN = "BOOLEAN"
    LIST = "LIST"
    FILE = "FILE"
    IDENTIFIER = "IDENTIFIER"
    QUALIFIED_IDENTIFIER = "QUALIFIED_IDENTIFIER"

    @classmethod
    def parse(
        cls, value: object, *, path: Tuple[object, ...]
    ) -> "ParameterType":
        try:
            return cls(str(value).upper())
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ContractValidationError(
                f"unsupported parameter type {value!r}; expected one of {supported}",
                code="template.contract.invalid_type",
                path=path,
            ) from exc


_TEMPORAL_INPUT_FORMATS = {
    ParameterType.DATE: frozenset({"yyyyMMdd", "yyyy-MM-dd"}),
    ParameterType.TIME: frozenset({"HH:mm:ss"}),
    ParameterType.TIMESTAMP: frozenset(
        {"yyyy-MM-dd HH:mm:ss", "yyyyMMddHHmmss"}
    ),
}
_TEMPORAL_OUTPUT_FORMATS = {
    ParameterType.DATE: frozenset(
        {"yyyy", "yyyyMM", "yyyyMMdd", "yyyy-MM-dd"}
    ),
    ParameterType.TIME: frozenset({"HH:mm:ss"}),
    # A timestamp owns both components, so output formatting may deliberately
    # project a date, time, or complete timestamp without inventing values.
    ParameterType.TIMESTAMP: frozenset(_FORMAT_PATTERNS),
}


@dataclass(frozen=True)
class RenderSpec:
    """Input and SQL output formatting for one typed parameter."""

    input_format: Optional[str] = None
    output_format: Optional[str] = None
    item_type: Optional[ParameterType] = None

    def as_dict(self) -> dict:
        value = {}
        if self.input_format is not None:
            value["input_format"] = self.input_format
        if self.output_format is not None:
            value["format"] = self.output_format
        if self.item_type is not None:
            value["item_type"] = self.item_type.value
        return value


def validate_format(value: object, *, path: Tuple[object, ...]) -> str:
    text = str(value)
    if text not in _FORMAT_PATTERNS:
        raise ContractValidationError(
            f"unsupported date/time format {text!r}",
            code="template.contract.invalid_format",
            path=path,
        )
    return text


def validate_temporal_format(
    format_name: str,
    *,
    data_type: ParameterType,
    is_output: bool,
    path: Tuple[object, ...],
) -> str:
    """Validate that a temporal format cannot invent missing components."""
    formats_by_type = (
        _TEMPORAL_OUTPUT_FORMATS if is_output else _TEMPORAL_INPUT_FORMATS
    )
    allowed = formats_by_type.get(data_type, frozenset())
    if format_name not in allowed:
        field = "output" if is_output else "input"
        expected = ", ".join(sorted(allowed))
        raise ContractValidationError(
            f"{data_type.value} does not accept {field} format "
            f"{format_name!r}; expected one of {expected}",
            code="template.contract.invalid_format",
            path=path,
        )
    return format_name


def format_temporal(value: object, format_name: str) -> str:
    """Format an already typed temporal value using the contract vocabulary."""
    return value.strftime(_FORMAT_PATTERNS[format_name])


def _parse_temporal(
    value: object,
    *,
    data_type: ParameterType,
    input_format: Optional[str],
    prop: str,
) -> object:
    if data_type is ParameterType.DATE:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        default_format = "yyyy-MM-dd"
        target = date
    elif data_type is ParameterType.TIME:
        if isinstance(value, time):
            return value
        default_format = "HH:mm:ss"
        target = time
    else:
        if isinstance(value, datetime):
            return value
        default_format = "yyyy-MM-dd HH:mm:ss"
        target = datetime

    if not isinstance(value, str):
        raise TemplateRenderError(
            f"parameter {prop!r} requires {data_type.value}, received {value!r}",
            code="template.render.invalid_value",
            path=(prop,),
        )
    format_name = input_format or default_format
    if not _FORMAT_VALUE_PATTERNS[format_name].fullmatch(value):
        raise TemplateRenderError(
            f"parameter {prop!r} value does not exactly match {format_name}",
            code="template.render.invalid_temporal",
            path=(prop,),
        )
    try:
        parsed = datetime.strptime(value, _FORMAT_PATTERNS[format_name])
    except ValueError as exc:
        raise TemplateRenderError(
            f"parameter {prop!r} value {value!r} does not match {format_name}",
            code="template.render.invalid_temporal",
            path=(prop,),
        ) from exc
    if target is date:
        return parsed.date()
    if target is time:
        return parsed.time()
    return parsed


def _parse_decimal(value: object, *, prop: str) -> Decimal:
    if isinstance(value, bool):
        raise TemplateRenderError(
            f"parameter {prop!r} requires a finite number, received {value!r}",
            code="template.render.invalid_value",
            path=(prop,),
        )
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TemplateRenderError(
            f"parameter {prop!r} requires a finite number, received {value!r}",
            code="template.render.invalid_value",
            path=(prop,),
        ) from exc
    if not parsed.is_finite():
        raise TemplateRenderError(
            f"parameter {prop!r} requires a finite number, received {value!r}",
            code="template.render.invalid_value",
            path=(prop,),
        )
    return parsed


def _parse_identifier(value: object, *, prop: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise TemplateRenderError(
            f"parameter {prop!r} is not a safe identifier segment: {value!r}",
            code="template.render.invalid_identifier",
            path=(prop,),
        )
    return value


def coerce_value(
    data_type: ParameterType,
    value: object,
    *,
    render: RenderSpec,
    prop: str,
) -> object:
    """Validate and normalize one external or derived parameter value."""
    if data_type in {ParameterType.VARCHAR, ParameterType.FILE}:
        if not isinstance(value, str):
            raise TemplateRenderError(
                f"parameter {prop!r} requires a string, received {value!r}",
                code="template.render.invalid_value",
                path=(prop,),
            )
        return value
    if data_type in {ParameterType.INTEGER, ParameterType.LONG}:
        if isinstance(value, bool) or not _INTEGER_RE.fullmatch(str(value)):
            raise TemplateRenderError(
                f"parameter {prop!r} requires an integer, received {value!r}",
                code="template.render.invalid_value",
                path=(prop,),
            )
        return int(value)
    if data_type in {ParameterType.FLOAT, ParameterType.DOUBLE}:
        return _parse_decimal(value, prop=prop)
    if data_type in {
        ParameterType.DATE,
        ParameterType.TIME,
        ParameterType.TIMESTAMP,
    }:
        return _parse_temporal(
            value,
            data_type=data_type,
            input_format=render.input_format,
            prop=prop,
        )
    if data_type is ParameterType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.casefold() in {"true", "false"}:
            return value.casefold() == "true"
        raise TemplateRenderError(
            f"parameter {prop!r} requires BOOLEAN, received {value!r}",
            code="template.render.invalid_value",
            path=(prop,),
        )
    if data_type is ParameterType.IDENTIFIER:
        return _parse_identifier(value, prop=prop)
    if data_type is ParameterType.QUALIFIED_IDENTIFIER:
        parts: Sequence[object]
        if isinstance(value, str):
            parts = value.split(".")
        elif isinstance(value, (list, tuple)):
            parts = value
        else:
            parts = ()
        if not parts:
            raise TemplateRenderError(
                f"parameter {prop!r} requires a qualified identifier",
                code="template.render.invalid_identifier",
                path=(prop,),
            )
        return tuple(_parse_identifier(part, prop=prop) for part in parts)
    if data_type is ParameterType.LIST:
        if not isinstance(value, (list, tuple)):
            raise TemplateRenderError(
                f"parameter {prop!r} requires a list, received {value!r}",
                code="template.render.invalid_value",
                path=(prop,),
            )
        if not value:
            raise TemplateRenderError(
                f"parameter {prop!r} requires a non-empty list",
                code="template.render.invalid_value",
                path=(prop,),
            )
        if render.item_type is None:
            raise TemplateRenderError(
                f"parameter {prop!r} LIST requires render.item_type",
                code="template.render.missing_item_type",
                path=(prop,),
            )
        item_render = RenderSpec()
        return tuple(
            coerce_value(
                render.item_type,
                item,
                render=item_render,
                prop=f"{prop}[{index}]",
            )
            for index, item in enumerate(value)
        )
    raise AssertionError(f"unhandled parameter type: {data_type}")


def _quote_string(value: str) -> str:
    if "\x00" in value:
        raise TemplateRenderError(
            "SQL string values cannot contain NUL",
            code="template.render.invalid_string",
        )
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _decimal_token(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    text = "".join(str(digit) for digit in digits) or "0"
    if exponent >= 0:
        if len(text) + exponent + sign > _MAX_NUMERIC_TOKEN_LENGTH:
            raise TemplateRenderError(
                "numeric SQL token exceeds the supported length",
                code="template.render.numeric_too_large",
            )
        token = text + ("0" * exponent)
    else:
        split = len(text) + exponent
        if split > 0:
            token = f"{text[:split]}.{text[split:]}"
        else:
            if 2 - split + len(text) + sign > _MAX_NUMERIC_TOKEN_LENGTH:
                raise TemplateRenderError(
                    "numeric SQL token exceeds the supported length",
                    code="template.render.numeric_too_large",
                )
            token = f"0.{('0' * (-split))}{text}"
        token = token.rstrip("0").rstrip(".")
    token = token.lstrip("0") if not token.startswith("0.") else token
    token = token or "0"
    if sign:
        token = f"-{token}"
    if len(token) > _MAX_NUMERIC_TOKEN_LENGTH:
        raise TemplateRenderError(
            "numeric SQL token exceeds the supported length",
            code="template.render.numeric_too_large",
        )
    return token


def render_sql_token(
    data_type: ParameterType,
    value: object,
    *,
    render: RenderSpec,
    prop: str,
) -> str:
    """Render one normalized value as a complete safe SQL token."""
    if data_type in {ParameterType.VARCHAR, ParameterType.FILE}:
        return _quote_string(str(value))
    if data_type in {ParameterType.INTEGER, ParameterType.LONG}:
        return str(value)
    if data_type in {ParameterType.FLOAT, ParameterType.DOUBLE}:
        return _decimal_token(value)
    if data_type is ParameterType.DATE:
        format_name = render.output_format or "yyyy-MM-dd"
        return _quote_string(format_temporal(value, format_name))
    if data_type is ParameterType.TIME:
        format_name = render.output_format or "HH:mm:ss"
        return _quote_string(format_temporal(value, format_name))
    if data_type is ParameterType.TIMESTAMP:
        format_name = render.output_format or "yyyy-MM-dd HH:mm:ss"
        return _quote_string(format_temporal(value, format_name))
    if data_type is ParameterType.BOOLEAN:
        return "TRUE" if value else "FALSE"
    if data_type is ParameterType.IDENTIFIER:
        return f"`{value}`"
    if data_type is ParameterType.QUALIFIED_IDENTIFIER:
        return ".".join(f"`{part}`" for part in value)
    if data_type is ParameterType.LIST:
        item_type = render.item_type
        if item_type is None:
            raise AssertionError("normalized LIST has no item type")
        item_render = RenderSpec()
        return (
            "("
            + ", ".join(
                render_sql_token(
                    item_type,
                    item,
                    render=item_render,
                    prop=prop,
                )
                for item in value
            )
            + ")"
        )
    raise AssertionError(f"unhandled parameter type: {data_type}")


def normalize_value(value: object) -> object:
    """Convert a normalized value into deterministic JSON-compatible data."""
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _decimal_token(value)
    if isinstance(value, (list, tuple)):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): normalize_value(item)
            for key, item in sorted(
                value.items(), key=lambda pair: str(pair[0])
            )
        }
    return value
