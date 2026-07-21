"""Lossless inspection payloads and typed issue migration contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from dw_refactor_agent.config import TEXT_ENCODING

ISSUE_SCHEMA_VERSION = 1
RAW_RESPONSE_SCHEMA_VERSION = 1
PARSED_CANDIDATE_SCHEMA_VERSION = 1

ISSUE_ORIGINS = frozenset(
    {
        "llm_validation",
        "transport",
        "parser",
        "deterministic_asset",
        "deterministic_contract",
        "internal",
    }
)
ISSUE_STAGES = frozenset(
    {
        "preflight",
        "parse",
        "recovery",
        "local_validation",
        "propagation",
        "generation_validation",
        "publication",
    }
)
ISSUE_SECTIONS = frozenset(
    {
        "classification",
        "business_semantics",
        "entities",
        "grain",
        "metrics",
    }
)
STRUCTURE_SECTIONS = (
    "classification",
    "business_semantics",
    "entities",
    "grain",
)
ALL_SEMANTIC_SECTIONS = STRUCTURE_SECTIONS + ("metrics",)
METRIC_GROUPS = frozenset(
    {
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
    }
)

# This registry intentionally remains independent from table_inspector's
# constants. Contract tests compare the two sets so adding a validator cannot
# silently bypass typed migration.
LEGACY_VALIDATION_ISSUE_CODES = {
    "unknown_columns": (
        "hallucinated_column_unreferenced",
        "hallucinated_column_reference",
    ),
    "duplicate_columns": (
        "duplicate_columns_same_group",
        "column_group_conflict_metric",
        "column_group_conflict_structure",
    ),
    "missing_columns": ("missing_ddl_column",),
    "missing_base_metrics": ("missing_base_metrics",),
    "missing_base_metric_tables": ("missing_base_metric_tables",),
    "invalid_base_metrics": ("invalid_base_metrics",),
    "invalid_base_metric_tables": ("invalid_base_metric_tables",),
    "ambiguous_base_metrics": ("ambiguous_base_metrics",),
    "invalid_time_periods": ("invalid_time_periods",),
    "invalid_metric_expressions": ("invalid_metric_expressions",),
    "missing_primary_entities": ("missing_primary_entities",),
    "inconsistent_layer_table_types": ("inconsistent_layer_table_types",),
    "inconsistent_layer_sql": ("inconsistent_layer_sql",),
    "inconsistent_upstream_metric_layers": (
        "inconsistent_upstream_metric_layers",
    ),
    "business_process_missing": ("business_process_missing",),
    "business_process_ambiguous": ("business_process_ambiguous",),
    "composite_process_invalid": ("composite_process_invalid",),
    "bridge_entities_invalid": ("bridge_entities_invalid",),
    "bridge_grain_invalid": ("bridge_grain_invalid",),
    "bridge_semantics_invalid": ("bridge_semantics_invalid",),
    "duplicate_entity_codes": ("duplicate_entity_codes",),
    "entity_key_missing": ("entity_key_missing",),
    "grain_entity_unknown": ("grain_entity_unknown",),
    "grain_column_missing": ("grain_column_missing",),
    "dimension_primary_entity_invalid": ("dimension_primary_entity_invalid",),
    "ddl_columns_unavailable": ("ddl_columns_unavailable",),
    "resolution_requires_reinspection": ("resolution_requires_reinspection",),
    "metric_context_reinspection_failed": (
        "metric_context_reinspection_failed",
    ),
    "metric_propagation_not_converged": ("metric_propagation_not_converged",),
    "ambiguous_min_max_aggregation": ("ambiguous_min_max_aggregation",),
}

# Generation validation keeps its existing error dictionaries as a
# compatibility view. Every error type must also have one structured issue
# migration registered here.
GENERATION_ERROR_ISSUE_CODES = {
    "bridge_entities_invalid": "bridge_entities_invalid",
    "bridge_grain_invalid": "bridge_grain_invalid",
    "bridge_semantics_invalid": "bridge_semantics_invalid",
    "business_process_ambiguous": "business_process_ambiguous",
    "business_process_missing": "business_process_missing",
    "business_process_unknown": "business_process_unknown",
    "composite_process_invalid": "composite_process_invalid",
    "dimension_primary_entity_invalid": "dimension_primary_entity_invalid",
    "duplicate_entity_codes": "duplicate_entity_codes",
    "entity_key_missing": "entity_key_missing",
    "entity_relationship_origin_missing": (
        "entity_relationship_origin_missing"
    ),
    "entity_relationship_origin_unknown": (
        "entity_relationship_origin_unknown"
    ),
    "execution_materialized_mismatch": "execution_materialized_mismatch",
    "execution_main_task_missing": "execution_main_task_missing",
    "execution_partition_overwrite_unsupported": (
        "execution_partition_overwrite_unsupported"
    ),
    "execution_slice_column_missing": "execution_slice_column_missing",
    "execution_slice_invalid": "execution_slice_invalid",
    "execution_slice_missing": "execution_slice_missing",
    "execution_strategy_invalid": "execution_strategy_invalid",
    "execution_task_binding_conflict": "execution_task_binding_conflict",
    "execution_task_missing": "execution_task_missing",
    "grain_column_missing": "grain_column_missing",
    "grain_entity_unknown": "grain_entity_unknown",
    "inspection_context_set_mismatch": "inspection_context_set_mismatch",
    "llm_inspection_blocked": "inspection_blocked_summary_unexpanded",
    "llm_inspection_missing": "inspection_missing",
    "semantic_subject_missing": "semantic_subject_missing",
    "semantic_subject_unknown": "semantic_subject_unknown",
}

BOUNDARY_ISSUE_CODES = frozenset(
    {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_transport_failed",
        "inspection_request_rejected",
        "inspection_content_parse_failed",
        "inspection_low_confidence",
        "internal_inspection_error",
    }
)
ISSUE_CODES = frozenset(
    BOUNDARY_ISSUE_CODES
    | {
        code
        for codes in LEGACY_VALIDATION_ISSUE_CODES.values()
        for code in codes
    }
    | set(GENERATION_ERROR_ISSUE_CODES.values())
)

METRIC_ISSUE_CODES = frozenset(
    {
        "hallucinated_column_reference",
        "column_group_conflict_metric",
        "missing_ddl_column",
        "missing_base_metrics",
        "missing_base_metric_tables",
        "invalid_base_metrics",
        "invalid_base_metric_tables",
        "ambiguous_base_metrics",
        "invalid_metric_expressions",
        "metric_context_reinspection_failed",
    }
)
BUSINESS_SEMANTICS_ISSUE_CODES = frozenset(
    {
        "business_process_missing",
        "business_process_ambiguous",
        "business_process_unknown",
        "composite_process_invalid",
        "semantic_subject_missing",
        "semantic_subject_unknown",
    }
)
ENTITY_ISSUE_CODES = frozenset(
    {
        "missing_primary_entities",
        "duplicate_entity_codes",
        "entity_key_missing",
        "entity_relationship_origin_missing",
        "entity_relationship_origin_unknown",
        "dimension_primary_entity_invalid",
    }
)
GRAIN_ISSUE_CODES = frozenset(
    {
        "grain_entity_unknown",
        "grain_column_missing",
        "bridge_grain_invalid",
    }
)
STRUCTURE_BUNDLE_ISSUE_CODES = frozenset(
    {
        "column_group_conflict_structure",
        "inconsistent_layer_table_types",
        "inconsistent_layer_sql",
        "inconsistent_upstream_metric_layers",
        "bridge_entities_invalid",
    }
)
HARD_BLOCK_ISSUE_CODES = frozenset(
    {
        "ddl_columns_unavailable",
        "metric_propagation_not_converged",
        "internal_inspection_error",
        "inspection_blocked_summary_unexpanded",
        "inspection_context_set_mismatch",
        "execution_materialized_mismatch",
        "execution_main_task_missing",
        "execution_partition_overwrite_unsupported",
        "execution_slice_column_missing",
        "execution_slice_invalid",
        "execution_slice_missing",
        "execution_strategy_invalid",
        "execution_task_binding_conflict",
        "execution_task_missing",
    }
)
RETRYABLE_ISSUE_CODES = frozenset(
    {
        "inspection_transport_failed",
        "inspection_content_parse_failed",
        "inspection_low_confidence",
        "inspection_missing",
        "resolution_requires_reinspection",
    }
)


class UnknownInspectionIssueError(ValueError):
    """Raised when an issue or legacy validation key is not registered."""


class InspectionIssueMigrationError(ValueError):
    """Raised when a legacy summary lacks evidence required for migration."""


@dataclass(frozen=True)
class IssueEvidence:
    """Reproducible evidence attached to one structured issue."""

    kind: str
    values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.kind or "").strip():
            raise ValueError("issue evidence kind must not be empty")
        object.__setattr__(
            self,
            "values",
            tuple(str(value) for value in self.values),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "values": list(self.values)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueEvidence":
        if not isinstance(data, dict):
            raise ValueError("issue evidence must be an object")
        values = data.get("values") or []
        if not isinstance(values, list):
            raise ValueError("issue evidence values must be a list")
        return cls(
            kind=str(data.get("kind") or ""),
            values=tuple(str(value) for value in values),
        )


@dataclass(frozen=True)
class InspectionIssue:
    """Stable, lossless-enough issue envelope used by later policy stages."""

    code: str
    origin: str
    stage: str
    sections: tuple[str, ...]
    table: str
    path: str = ""
    items: tuple[str, ...] = ()
    retryable: bool = False
    evidence: tuple[IssueEvidence, ...] = ()
    schema_version: int = ISSUE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ISSUE_SCHEMA_VERSION:
            raise UnknownInspectionIssueError(
                f"unsupported inspection issue schema: {self.schema_version}"
            )
        if self.code not in ISSUE_CODES:
            raise UnknownInspectionIssueError(
                f"unknown inspection issue code: {self.code!r}"
            )
        if self.origin not in ISSUE_ORIGINS:
            raise UnknownInspectionIssueError(
                f"unknown inspection issue origin: {self.origin!r}"
            )
        if self.stage not in ISSUE_STAGES:
            raise UnknownInspectionIssueError(
                f"unknown inspection issue stage: {self.stage!r}"
            )
        unknown_sections = set(self.sections) - ISSUE_SECTIONS
        if unknown_sections:
            raise UnknownInspectionIssueError(
                "unknown inspection issue sections: "
                + ", ".join(sorted(unknown_sections))
            )
        object.__setattr__(
            self,
            "sections",
            tuple(sorted(set(self.sections))),
        )
        object.__setattr__(
            self,
            "items",
            tuple(sorted(set(str(item) for item in self.items))),
        )
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "code": self.code,
            "origin": self.origin,
            "stage": self.stage,
            "sections": list(self.sections),
            "table": self.table,
            "path": self.path,
            "items": list(self.items),
            "retryable": self.retryable,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InspectionIssue":
        if not isinstance(data, dict):
            raise ValueError("inspection issue must be an object")
        sections = data.get("sections") or []
        items = data.get("items") or []
        evidence = data.get("evidence") or []
        if not all(
            isinstance(value, list) for value in (sections, items, evidence)
        ):
            raise ValueError(
                "inspection issue sections, items, and evidence must be lists"
            )
        return cls(
            schema_version=int(data.get("schema_version", 0) or 0),
            code=str(data.get("code") or ""),
            origin=str(data.get("origin") or ""),
            stage=str(data.get("stage") or ""),
            sections=tuple(str(section) for section in sections),
            table=str(data.get("table") or ""),
            path=str(data.get("path") or ""),
            items=tuple(str(item) for item in items),
            retryable=bool(data.get("retryable")),
            evidence=tuple(IssueEvidence.from_dict(item) for item in evidence),
        )


@dataclass(frozen=True)
class RawInspectionResponse:
    """Immutable API response body and non-secret request identity."""

    table_name: str
    model: str
    endpoint: str
    context_hash: str
    body: str
    content_hash: str
    schema_version: int = RAW_RESPONSE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        table_name: str,
        model: str,
        endpoint: str,
        context_hash: str,
        body: str,
    ) -> "RawInspectionResponse":
        text = str(body)
        endpoint_parts = urlsplit(str(endpoint))
        endpoint_netloc = endpoint_parts.netloc.rsplit("@", 1)[-1]
        safe_endpoint = urlunsplit(
            (
                endpoint_parts.scheme,
                endpoint_netloc,
                endpoint_parts.path,
                "",
                "",
            )
        )
        return cls(
            table_name=str(table_name),
            model=str(model),
            endpoint=safe_endpoint,
            context_hash=str(context_hash),
            body=text,
            content_hash=hashlib.sha256(
                text.encode(TEXT_ENCODING)
            ).hexdigest(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table_name": self.table_name,
            "model": self.model,
            "endpoint": self.endpoint,
            "context_hash": self.context_hash,
            "body": self.body,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawInspectionResponse":
        if not isinstance(data, dict):
            raise ValueError("raw inspection response must be an object")
        if set(data) != {
            "schema_version",
            "table_name",
            "model",
            "endpoint",
            "context_hash",
            "body",
            "content_hash",
        }:
            raise ValueError(
                "raw inspection response fields are incomplete or unknown"
            )
        schema_version = data.get("schema_version")
        if schema_version != RAW_RESPONSE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported raw response schema: {schema_version!r}"
            )
        body = data.get("body")
        if not isinstance(body, str):
            raise ValueError("raw inspection response body must be a string")
        content_hash = data.get("content_hash")
        actual_hash = hashlib.sha256(body.encode(TEXT_ENCODING)).hexdigest()
        if content_hash != actual_hash:
            raise ValueError("raw inspection response content hash mismatch")
        restored = cls.create(
            table_name=str(data.get("table_name") or ""),
            model=str(data.get("model") or ""),
            endpoint=str(data.get("endpoint") or ""),
            context_hash=str(data.get("context_hash") or ""),
            body=body,
        )
        if restored.endpoint != data.get("endpoint"):
            raise ValueError(
                "raw inspection response endpoint is not sanitized"
            )
        return restored


@dataclass(frozen=True)
class ParsedInspectionCandidate:
    """Immutable, lossless JSON candidate before semantic normalization."""

    table_name: str
    raw_response_hash: str
    payload_json: str
    schema_version: int = PARSED_CANDIDATE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        table_name: str,
        raw_response_hash: str,
        payload: dict[str, Any],
    ) -> "ParsedInspectionCandidate":
        if not isinstance(payload, dict):
            raise ValueError("parsed inspection candidate must be an object")
        return cls(
            table_name=str(table_name),
            raw_response_hash=str(raw_response_hash),
            payload_json=json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("parsed inspection candidate is not an object")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table_name": self.table_name,
            "raw_response_hash": self.raw_response_hash,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedInspectionCandidate":
        if not isinstance(data, dict):
            raise ValueError("parsed inspection candidate must be an object")
        if set(data) != {
            "schema_version",
            "table_name",
            "raw_response_hash",
            "payload",
        }:
            raise ValueError(
                "parsed inspection candidate fields are incomplete or unknown"
            )
        schema_version = data.get("schema_version")
        if schema_version != PARSED_CANDIDATE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported parsed candidate schema: {schema_version!r}"
            )
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(
                "parsed inspection candidate payload must be an object"
            )
        return cls.create(
            table_name=str(data.get("table_name") or ""),
            raw_response_hash=str(data.get("raw_response_hash") or ""),
            payload=payload,
        )


class InspectionBoundaryError(RuntimeError):
    """Base class for typed external inspection boundary failures."""

    issue_code = ""
    origin = ""
    stage = ""
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        evidence: Iterable[IssueEvidence] = (),
    ):
        super().__init__(message)
        self.boundary_evidence = tuple(evidence)

    def to_issue(self, table_name: str) -> InspectionIssue:
        cause = self.__cause__
        evidence = [
            IssueEvidence(
                kind="exception_type",
                values=(
                    type(cause).__name__
                    if cause is not None
                    else type(self).__name__,
                ),
            ),
        ]
        evidence.extend(self.boundary_evidence)
        return issue_for_code(
            self.issue_code,
            table=table_name,
            items=(str(self),),
            evidence=evidence,
            origin=self.origin,
            stage=self.stage,
            retryable=self.retryable,
        )


class InspectionAuthenticationError(InspectionBoundaryError):
    """Authentication or authorization was rejected by the service."""

    issue_code = "inspection_authentication_failed"
    origin = "transport"
    stage = "parse"
    retryable = False


class InspectionConfigurationError(InspectionBoundaryError):
    """The configured inspection endpoint cannot be called safely."""

    issue_code = "inspection_configuration_invalid"
    origin = "transport"
    stage = "parse"
    retryable = False


class InspectionTransportError(InspectionBoundaryError):
    """A request failed before a response candidate could be parsed."""

    issue_code = "inspection_transport_failed"
    origin = "transport"
    stage = "parse"
    retryable = True


class InspectionRequestRejectedError(InspectionBoundaryError):
    """A non-transient request or model configuration was rejected."""

    issue_code = "inspection_request_rejected"
    origin = "transport"
    stage = "parse"
    retryable = False


class InspectionContentParseError(InspectionBoundaryError):
    """The service response could not produce a structured candidate."""

    issue_code = "inspection_content_parse_failed"
    origin = "parser"
    stage = "parse"
    retryable = True


class InspectionInternalError(RuntimeError):
    """Typed hard failure for validator/state-machine programming errors."""

    def __init__(
        self,
        message: str,
        *,
        table_name: str,
        stage: str,
        cause: BaseException | None = None,
        context: str = "",
    ):
        super().__init__(message)
        if stage not in ISSUE_STAGES:
            raise UnknownInspectionIssueError(
                f"unknown internal inspection stage: {stage!r}"
            )
        evidence = [
            IssueEvidence(
                kind="exception_type",
                values=(type(cause).__name__,) if cause is not None else (),
            )
        ]
        if context:
            evidence.append(
                IssueEvidence(
                    kind="internal_context",
                    values=(context,),
                )
            )
        self.issue = issue_for_code(
            "internal_inspection_error",
            table=table_name,
            stage=stage,
            items=(message,),
            evidence=evidence,
        )


def _issue_origin(code: str) -> str:
    if code in {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_request_rejected",
    }:
        return "transport"
    if code == "inspection_transport_failed":
        return "transport"
    if code == "inspection_content_parse_failed":
        return "parser"
    if code in {
        "ddl_columns_unavailable",
    }:
        return "deterministic_asset"
    if code in HARD_BLOCK_ISSUE_CODES or code.startswith("execution_"):
        return (
            "internal"
            if code
            in {
                "metric_propagation_not_converged",
                "internal_inspection_error",
                "inspection_blocked_summary_unexpanded",
            }
            else "deterministic_contract"
        )
    return "llm_validation"


def _issue_stage(code: str) -> str:
    if code in {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_request_rejected",
        "inspection_transport_failed",
        "inspection_content_parse_failed",
    }:
        return "parse"
    if code in {
        "metric_context_reinspection_failed",
        "metric_propagation_not_converged",
    }:
        return "propagation"
    return "local_validation"


def _issue_sections(code: str) -> tuple[str, ...]:
    if code in {
        "inspection_authentication_failed",
        "inspection_configuration_invalid",
        "inspection_request_rejected",
        "inspection_transport_failed",
        "inspection_content_parse_failed",
        "inspection_low_confidence",
        "inspection_missing",
        "inspection_blocked_summary_unexpanded",
        "resolution_requires_reinspection",
    }:
        return ALL_SEMANTIC_SECTIONS
    if code in METRIC_ISSUE_CODES:
        return ("metrics",)
    if code in BUSINESS_SEMANTICS_ISSUE_CODES:
        return ("business_semantics",)
    if code in ENTITY_ISSUE_CODES:
        return ("entities",)
    if code in GRAIN_ISSUE_CODES:
        return ("grain",)
    if code in STRUCTURE_BUNDLE_ISSUE_CODES:
        return STRUCTURE_SECTIONS
    if code == "bridge_semantics_invalid":
        return ALL_SEMANTIC_SECTIONS
    return ()


def issue_for_code(
    code: str,
    *,
    table: str,
    path: str = "",
    items: Iterable[Any] = (),
    sections: Iterable[str] | None = None,
    evidence: Iterable[IssueEvidence] = (),
    origin: str | None = None,
    stage: str | None = None,
    retryable: bool | None = None,
) -> InspectionIssue:
    """Build one validated issue using registry-defined defaults."""
    if code not in ISSUE_CODES:
        raise UnknownInspectionIssueError(
            f"unknown inspection issue code: {code!r}"
        )
    return InspectionIssue(
        code=code,
        origin=_issue_origin(code) if origin is None else origin,
        stage=_issue_stage(code) if stage is None else stage,
        sections=tuple(
            _issue_sections(code) if sections is None else sections
        ),
        table=str(table),
        path=str(path),
        items=tuple(str(item) for item in items),
        retryable=(
            code in RETRYABLE_ISSUE_CODES if retryable is None else retryable
        ),
        evidence=tuple(evidence),
    )


def _canonical_column(value: Any) -> str:
    return (
        str(value or "").strip().replace("`", "").replace('"', "").casefold()
    )


def _normalized_payload(item: dict[str, Any]) -> str:
    payload = dict(item)
    payload["name"] = _canonical_column(payload.get("name"))
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _column_occurrences(
    result: Any,
    column_name: str,
) -> list[tuple[str, int, dict[str, Any]]]:
    wanted = _canonical_column(column_name)
    occurrences = []
    for group_name, items in (getattr(result, "columns", {}) or {}).items():
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if (
                isinstance(item, dict)
                and _canonical_column(item.get("name")) == wanted
            ):
                occurrences.append((str(group_name), index, item))
    return occurrences


def _column_identifier_matches(value: Any, column_name: str) -> bool:
    identifier = _canonical_column(value)
    return bool(
        identifier
        and identifier.rsplit(".", 1)[-1] == _canonical_column(column_name)
    )


def _expression_references_column(value: Any, column_name: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        expression = sqlglot.parse_one(value, dialect="doris")
    except (SqlglotError, TypeError, ValueError):
        return False
    return bool(expression) and any(
        _column_identifier_matches(column.sql(), column_name)
        for column in expression.find_all(exp.Column)
    )


def expression_references_column(value: Any, column_name: str) -> bool:
    """Return whether a valid SQL expression references an exact column."""
    return _expression_references_column(value, column_name)


def _reference_values(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [] if value in (None, "") else [value]


def _column_reference_sections(
    result: Any,
    column_name: str,
    occurrences: list[tuple[str, int, dict[str, Any]]],
) -> tuple[set[str], list[str]]:
    sections = set()
    paths = []
    for group_name, index, _item in occurrences:
        if group_name in METRIC_GROUPS:
            sections.add("metrics")
            paths.append(f"columns.{group_name}[{index}].name")
    for group_name in sorted(METRIC_GROUPS):
        for index, item in enumerate(
            (getattr(result, "columns", {}) or {}).get(group_name) or []
        ):
            if not isinstance(item, dict):
                continue
            if _column_identifier_matches(
                item.get("base_metric"),
                column_name,
            ):
                sections.add("metrics")
                paths.append(f"columns.{group_name}[{index}].base_metric")
            for field_name in ("derived_from",):
                for value_index, value in enumerate(
                    _reference_values(item.get(field_name))
                ):
                    if _column_identifier_matches(value, column_name):
                        sections.add("metrics")
                        paths.append(
                            f"columns.{group_name}[{index}]."
                            f"{field_name}[{value_index}]"
                        )
            if _expression_references_column(
                item.get("expression"),
                column_name,
            ):
                sections.add("metrics")
                paths.append(f"columns.{group_name}[{index}].expression")
    for entity_index, entity in enumerate(
        getattr(result, "entities", []) or []
    ):
        if not isinstance(entity, dict):
            continue
        for key_index, key_column in enumerate(
            _reference_values(entity.get("key_columns"))
        ):
            if _column_identifier_matches(key_column, column_name):
                sections.add("entities")
                paths.append(
                    f"entities[{entity_index}].key_columns[{key_index}]"
                )
    grain = getattr(result, "grain", {}) or {}
    for field_name in ("keys", "additional_key_columns"):
        for key_index, key_column in enumerate(
            _reference_values(grain.get(field_name))
        ):
            if _column_identifier_matches(key_column, column_name):
                sections.add("grain")
                paths.append(f"grain.{field_name}[{key_index}]")
    if _column_identifier_matches(grain.get("time_column"), column_name):
        sections.add("grain")
        paths.append("grain.time_column")
    return sections, sorted(set(paths))


def column_reference_sections(
    result: Any,
    column_name: str,
) -> tuple[set[str], list[str]]:
    """Return formal semantic sections and paths referencing one column."""
    return _column_reference_sections(
        result,
        column_name,
        _column_occurrences(result, column_name),
    )


def _issue_path(validation_key: str, value: str) -> str:
    if validation_key in {
        "invalid_time_periods",
        "invalid_metric_expressions",
    }:
        return str(value).split("=", 1)[0]
    paths = {
        "missing_columns": "columns",
        "missing_base_metrics": "derived_metrics.base_metric",
        "missing_base_metric_tables": "derived_metrics.base_metric_table",
        "invalid_base_metrics": "derived_metrics.base_metric",
        "invalid_base_metric_tables": "derived_metrics.base_metric_table",
        "ambiguous_base_metrics": "derived_metrics.base_metric",
        "missing_primary_entities": "entities",
        "business_process_missing": "business_process",
        "business_process_ambiguous": "business_process",
        "composite_process_invalid": "business_process_mode",
        "entity_key_missing": "entities.key_columns",
        "grain_entity_unknown": "grain.entities",
        "grain_column_missing": "grain",
    }
    return paths.get(validation_key, "")


def _sections_for_validation_issue(
    code: str,
    path: str,
) -> tuple[str, ...] | None:
    if code == "invalid_time_periods":
        return ("grain",) if path.startswith("grain.") else ("metrics",)
    return None


def _legacy_validation_evidence(
    validation_key: str,
    *evidence: IssueEvidence,
) -> tuple[IssueEvidence, ...]:
    return (
        IssueEvidence(
            kind="legacy_validation_key",
            values=(validation_key,),
        ),
    ) + tuple(evidence)


def is_legacy_validation_issue(issue: InspectionIssue) -> bool:
    """Return whether an issue was derived from the compatibility view."""
    return any(
        evidence.kind == "legacy_validation_key" for evidence in issue.evidence
    )


def issues_from_validation(
    result: Any,
    validation: dict[str, list[str]] | None = None,
) -> tuple[InspectionIssue, ...]:
    """Migrate the complete compatibility validation view without dropping keys."""
    raw_validation = (
        getattr(result, "validation", {}) if validation is None else validation
    ) or {}
    unknown_keys = set(raw_validation) - set(LEGACY_VALIDATION_ISSUE_CODES)
    if unknown_keys:
        raise UnknownInspectionIssueError(
            "unregistered validation keys: " + ", ".join(sorted(unknown_keys))
        )

    table_name = str(getattr(result, "table_name", "") or "")
    migrated = []
    for validation_key in sorted(raw_validation):
        values = raw_validation.get(validation_key) or []
        if not isinstance(values, list):
            raise InspectionIssueMigrationError(
                f"validation {validation_key!r} must contain a list"
            )
        for raw_value in values:
            value = str(raw_value)
            if validation_key == "unknown_columns":
                occurrences = _column_occurrences(result, value)
                sections, paths = _column_reference_sections(
                    result,
                    value,
                    occurrences,
                )
                code = (
                    "hallucinated_column_reference"
                    if sections
                    else "hallucinated_column_unreferenced"
                )
                migrated.append(
                    issue_for_code(
                        code,
                        table=table_name,
                        path=",".join(paths),
                        items=(value,),
                        sections=sections,
                        evidence=_legacy_validation_evidence(
                            validation_key,
                            IssueEvidence(
                                kind="column_groups",
                                values=tuple(
                                    sorted(
                                        {
                                            group
                                            for group, _index, _item in occurrences
                                        }
                                    )
                                ),
                            ),
                        ),
                    )
                )
                continue
            if validation_key == "duplicate_columns":
                occurrences = _column_occurrences(result, value)
                if len(occurrences) < 2:
                    raise InspectionIssueMigrationError(
                        "duplicate_columns lacks occurrence evidence for "
                        f"{value!r}"
                    )
                groups = {group for group, _index, _item in occurrences}
                payloads = {
                    _normalized_payload(item)
                    for _group, _index, item in occurrences
                }
                if len(groups) == 1 and len(payloads) == 1:
                    code = "duplicate_columns_same_group"
                elif groups & METRIC_GROUPS:
                    code = "column_group_conflict_metric"
                else:
                    code = "column_group_conflict_structure"
                migrated.append(
                    issue_for_code(
                        code,
                        table=table_name,
                        path="columns",
                        items=(value,),
                        sections=(
                            ("metrics",)
                            if (
                                code == "duplicate_columns_same_group"
                                and groups & METRIC_GROUPS
                            )
                            else None
                        ),
                        evidence=_legacy_validation_evidence(
                            validation_key,
                            IssueEvidence(
                                kind="column_groups",
                                values=tuple(sorted(groups)),
                            ),
                        ),
                    )
                )
                continue

            issue_codes = LEGACY_VALIDATION_ISSUE_CODES[validation_key]
            if len(issue_codes) != 1:
                raise InspectionIssueMigrationError(
                    f"validation {validation_key!r} requires typed evidence"
                )
            code = issue_codes[0]
            path = _issue_path(validation_key, value)
            migrated.append(
                issue_for_code(
                    code,
                    table=table_name,
                    path=path,
                    items=(value,),
                    sections=_sections_for_validation_issue(code, path),
                    evidence=_legacy_validation_evidence(validation_key),
                )
            )
    return sort_issues(migrated)


def generation_error_to_issue(
    error: dict[str, Any],
) -> InspectionIssue:
    """Convert one compatible generation error dictionary to a typed issue."""
    error_type = str(error.get("type") or "")
    if error_type not in GENERATION_ERROR_ISSUE_CODES:
        raise UnknownInspectionIssueError(
            f"unregistered generation error type: {error_type!r}"
        )
    message = str(error.get("message") or "")
    code = GENERATION_ERROR_ISSUE_CODES[error_type]
    if error_type == "llm_inspection_blocked":
        origin = "internal"
    elif error_type == "llm_inspection_missing":
        origin = "llm_validation"
    else:
        origin = "deterministic_contract"
    return issue_for_code(
        code,
        table=str(error.get("table") or ""),
        items=(message,) if message else (),
        evidence=(
            IssueEvidence(
                kind="generation_error_type",
                values=(error_type,),
            ),
        ),
        origin=origin,
        stage="generation_validation",
    )


def sort_issues(
    issues: Iterable[InspectionIssue],
) -> tuple[InspectionIssue, ...]:
    """Return stable, de-duplicated structured issues."""
    by_payload = {
        json.dumps(
            issue.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ): issue
        for issue in issues
    }
    return tuple(by_payload[key] for key in sorted(by_payload))


def issues_to_dicts(
    issues: Iterable[InspectionIssue],
) -> list[dict[str, Any]]:
    return [issue.to_dict() for issue in sort_issues(issues)]
