"""Whitelisted deterministic derivations for task template parameters."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping, Optional

from .errors import ContractValidationError, TemplateRenderError
from .types import format_temporal

DERIVATION_OPERATIONS = frozenset(
    {
        "add_days",
        "add_months",
        "add_years",
        "month_start",
        "month_end",
        "year_start",
        "year_end",
        "previous_year_end",
        "format_date",
    }
)


@dataclass(frozen=True)
class DerivationSpec:
    """One safe transformation from an already resolved parameter."""

    source: str
    operation: str
    amount: Optional[int] = None
    format_name: Optional[str] = None
    prefix: str = ""
    suffix: str = ""

    def as_dict(self) -> dict:
        value = {"from": self.source, "operation": self.operation}
        if self.amount is not None:
            value["amount"] = self.amount
        if self.format_name is not None:
            value["format"] = self.format_name
        if self.prefix:
            value["prefix"] = self.prefix
        if self.suffix:
            value["suffix"] = self.suffix
        return {"derive": value}


def validate_derivation(spec: DerivationSpec, *, path: tuple) -> None:
    """Validate operation-specific fields before any runtime binding exists."""
    if spec.operation not in DERIVATION_OPERATIONS:
        raise ContractValidationError(
            f"unsupported derivation operation {spec.operation!r}",
            code="template.contract.invalid_derivation",
            path=path + ("operation",),
        )
    requires_amount = spec.operation in {"add_days", "add_months", "add_years"}
    if requires_amount != (spec.amount is not None):
        expectation = "requires" if requires_amount else "does not accept"
        raise ContractValidationError(
            f"operation {spec.operation!r} {expectation} amount",
            code="template.contract.invalid_derivation",
            path=path,
        )
    if spec.operation == "format_date":
        if spec.format_name is None:
            raise ContractValidationError(
                "format_date requires format",
                code="template.contract.invalid_derivation",
                path=path,
            )
    elif spec.format_name is not None or spec.prefix or spec.suffix:
        raise ContractValidationError(
            f"operation {spec.operation!r} does not accept format/prefix/suffix",
            code="template.contract.invalid_derivation",
            path=path,
        )


def _as_temporal(value: object, *, source: str) -> date:
    if isinstance(value, (date, datetime)):
        return value
    raise TemplateRenderError(
        f"derivation source {source!r} must resolve to DATE or TIMESTAMP",
        code="template.render.invalid_derivation_source",
        path=(source,),
    )


def _add_months(value: date, amount: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + amount
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _add_years(value: date, amount: int) -> date:
    year = value.year + amount
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def derive_value(spec: DerivationSpec, values: Mapping[str, object]) -> object:
    """Evaluate a validated derivation against resolved typed values."""
    if spec.source not in values:
        raise TemplateRenderError(
            f"derivation source {spec.source!r} is not resolved",
            code="template.render.missing_dependency",
            path=(spec.source,),
        )
    source = _as_temporal(values[spec.source], source=spec.source)
    operation = spec.operation
    if operation == "add_days":
        return source + timedelta(days=int(spec.amount or 0))
    if operation == "add_months":
        return _add_months(source, int(spec.amount or 0))
    if operation == "add_years":
        return _add_years(source, int(spec.amount or 0))
    if operation == "month_start":
        return source.replace(day=1)
    if operation == "month_end":
        return source.replace(
            day=calendar.monthrange(source.year, source.month)[1]
        )
    if operation == "year_start":
        return source.replace(month=1, day=1)
    if operation == "year_end":
        return source.replace(month=12, day=31)
    if operation == "previous_year_end":
        return source.replace(year=source.year - 1, month=12, day=31)
    if operation == "format_date":
        formatted = format_temporal(source, str(spec.format_name))
        return f"{spec.prefix}{formatted}{spec.suffix}"
    raise AssertionError(f"unhandled derivation operation: {operation}")
