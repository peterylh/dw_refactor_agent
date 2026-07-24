"""Deterministic, auditable recovery of parsed inspection candidates."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, SqlglotError

from dw_refactor_agent.assessment.llm.inspection_contract import (
    canonical_semantic_code,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    METRIC_GROUPS,
    InspectionIssue,
    IssueEvidence,
    column_reference_sections,
    expression_references_column,
    issue_for_code,
    sort_issues,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    legacy_entity_from_entities,
    legacy_related_entities_from_entities,
)
from dw_refactor_agent.sql.doris import (
    normalize_create_table_for_sqlglot,
)

REPAIR_AUDIT_SCHEMA_VERSION = 1
RECOVERED_CANDIDATE_SCHEMA_VERSION = 1
COLUMN_GROUPS = (
    "atomic_metrics",
    "derived_metrics",
    "calculated_metrics",
    "dimensions",
    "others",
)
METRIC_GROUPING_LAYERS = frozenset({"DWD", "DWS"})


def _json_value(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class InspectionRepair:
    """One deterministic repair with exact before/after evidence."""

    repair_code: str
    table: str
    path: str
    before_json: str
    after_json: str
    evidence_json: str
    schema_version: int = REPAIR_AUDIT_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        repair_code: str,
        table: str,
        path: str,
        before: Any,
        after: Any,
        evidence: dict[str, Any],
    ) -> "InspectionRepair":
        return cls(
            repair_code=str(repair_code),
            table=str(table),
            path=str(path),
            before_json=_json_value(before),
            after_json=_json_value(after),
            evidence_json=_json_value(evidence),
        )

    @property
    def before(self) -> Any:
        return json.loads(self.before_json)

    @property
    def after(self) -> Any:
        return json.loads(self.after_json)

    @property
    def evidence(self) -> dict[str, Any]:
        value = json.loads(self.evidence_json)
        if not isinstance(value, dict):
            raise ValueError("repair evidence must be an object")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repair_code": self.repair_code,
            "table": self.table,
            "path": self.path,
            "before": self.before,
            "after": self.after,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "InspectionRepair":
        if not isinstance(data, dict):
            raise ValueError("inspection repair must be an object")
        if set(data) != {
            "schema_version",
            "repair_code",
            "table",
            "path",
            "before",
            "after",
            "evidence",
        }:
            raise ValueError(
                "inspection repair fields are incomplete or unknown"
            )
        if data.get("schema_version") != REPAIR_AUDIT_SCHEMA_VERSION:
            raise ValueError("unsupported inspection repair schema")
        evidence = data.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError("inspection repair evidence must be an object")
        return cls.create(
            repair_code=str(data.get("repair_code") or ""),
            table=str(data.get("table") or ""),
            path=str(data.get("path") or ""),
            before=data.get("before"),
            after=data.get("after"),
            evidence=evidence,
        )


@dataclass(frozen=True)
class RecoveredInspectionCandidate:
    """Immutable recovered candidate, separate from parsed and effective data."""

    table_name: str
    payload_json: str
    repair_audit: tuple[InspectionRepair, ...]
    schema_version: int = RECOVERED_CANDIDATE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        table_name: str,
        payload: dict[str, Any],
        repair_audit: Iterable[InspectionRepair],
    ) -> "RecoveredInspectionCandidate":
        return cls(
            table_name=str(table_name),
            payload_json=_json_value(payload),
            repair_audit=tuple(repair_audit),
        )

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("recovered inspection payload must be an object")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table_name": self.table_name,
            "payload": self.payload,
            "repair_audit": [repair.to_dict() for repair in self.repair_audit],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RecoveredInspectionCandidate":
        if not isinstance(data, dict):
            raise ValueError(
                "recovered inspection candidate must be an object"
            )
        if set(data) != {
            "schema_version",
            "table_name",
            "payload",
            "repair_audit",
        }:
            raise ValueError(
                "recovered candidate fields are incomplete or unknown"
            )
        if data.get("schema_version") != RECOVERED_CANDIDATE_SCHEMA_VERSION:
            raise ValueError("unsupported recovered candidate schema")
        payload = data.get("payload")
        repair_audit = data.get("repair_audit")
        if not isinstance(payload, dict) or not isinstance(repair_audit, list):
            raise ValueError("invalid recovered candidate payload")
        return cls.create(
            table_name=str(data.get("table_name") or ""),
            payload=payload,
            repair_audit=(
                InspectionRepair.from_dict(item) for item in repair_audit
            ),
        )


def _canonical_column(value: Any) -> str:
    return (
        str(value or "").strip().replace("`", "").replace('"', "").casefold()
    )


def _column_matches(value: Any, column_name: str) -> bool:
    canonical = _canonical_column(value)
    return bool(
        canonical
        and canonical.rsplit(".", 1)[-1] == _canonical_column(column_name)
    )


def _canonical_table(value: Any) -> str:
    text = str(value or "").strip().replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _matching_tables(value: Any, identities: Iterable[Any]) -> list[str]:
    canonical_identities = {
        _canonical_table(identity)
        for identity in identities
        if _canonical_table(identity)
    }
    wanted = _canonical_table(value)
    if not wanted:
        return []
    if wanted in canonical_identities:
        return [wanted]
    if "." in wanted:
        return []
    short_name = wanted.rsplit(".", 1)[-1]
    return sorted(
        identity
        for identity in canonical_identities
        if identity.rsplit(".", 1)[-1] == short_name
    )


def _split_column_identifier(value: Any) -> tuple[str, str]:
    text = str(value or "").strip().replace("`", "").replace('"', "")
    if "." not in text:
        return "", _canonical_column(text)
    table_name, column_name = text.rsplit(".", 1)
    return _canonical_table(table_name), _canonical_column(column_name)


def _ddl_columns(ddl: str) -> tuple[str, ...]:
    if not str(ddl or "").strip():
        return ()
    try:
        statements = sqlglot.parse(
            normalize_create_table_for_sqlglot(ddl),
            dialect="doris",
            error_level=ErrorLevel.RAISE,
        )
    except (SqlglotError, TypeError, ValueError):
        return ()
    creates = [
        statement
        for statement in statements
        if isinstance(statement, exp.Create)
        and isinstance(statement.this, exp.Schema)
    ]
    if len(creates) != 1:
        return ()
    columns = tuple(
        column.this.name
        for column in creates[0].this.expressions
        if isinstance(column, exp.ColumnDef)
        and str(column.this.name or "").strip()
    )
    if not columns or len(
        {_canonical_column(name) for name in columns}
    ) != len(columns):
        return ()
    return columns


def _repair(
    repairs: list[InspectionRepair],
    *,
    code: str,
    table: str,
    path: str,
    before: Any,
    after: Any,
    evidence: dict[str, Any],
) -> None:
    repair = InspectionRepair.create(
        repair_code=code,
        table=table,
        path=path,
        before=before,
        after=after,
        evidence=evidence,
    )
    if repair not in repairs:
        repairs.append(repair)


def _normalized_payload(item: dict[str, Any]) -> str:
    payload = dict(item)
    payload["name"] = _canonical_column(payload.get("name"))
    return _json_value(payload)


def _recovery_issue(
    code: str,
    *,
    table: str,
    column_name: str,
    groups: Iterable[str] = (),
    sections: Iterable[str] | None = None,
    paths: Iterable[str] = (),
) -> InspectionIssue:
    evidence = []
    normalized_groups = tuple(sorted(set(groups)))
    normalized_paths = tuple(sorted(set(paths)))
    if normalized_groups:
        evidence.append(
            IssueEvidence(kind="column_groups", values=normalized_groups)
        )
    if normalized_paths:
        evidence.append(
            IssueEvidence(kind="reference_paths", values=normalized_paths)
        )
    return issue_for_code(
        code,
        table=table,
        path=",".join(normalized_paths) if normalized_paths else "columns",
        items=(column_name,),
        sections=sections,
        stage="recovery",
        evidence=evidence,
    )


def _normalize_count_metrics(
    result: Any,
    repairs: list[InspectionRepair],
) -> None:
    if str(
        result.inferred_layer or ""
    ).upper() not in METRIC_GROUPING_LAYERS or not bool(result.is_fact_table):
        return
    atomic_metrics = result.columns.setdefault("atomic_metrics", [])
    for group_name in ("derived_metrics", "calculated_metrics"):
        retained = []
        for index, metric in enumerate(result.columns.get(group_name) or []):
            expression = str(metric.get("expression") or "").strip()
            relationship_fields = (
                metric.get("base_metric"),
                metric.get("base_metric_table"),
                metric.get("derived_from"),
                metric.get("modifiers"),
                metric.get("time_period"),
            )
            if any(relationship_fields):
                retained.append(metric)
                continue
            try:
                parsed = sqlglot.parse_one(expression, dialect="doris")
            except (SqlglotError, TypeError, ValueError):
                parsed = None
            aggregate_count = (
                sum(1 for _ in parsed.find_all(exp.AggFunc))
                if parsed is not None
                else 0
            )
            argument = parsed.this if isinstance(parsed, exp.Count) else None
            direct_argument = isinstance(argument, (exp.Column, exp.Star))
            if isinstance(argument, exp.Distinct):
                distinct_items = list(argument.expressions)
                direct_argument = len(distinct_items) == 1 and isinstance(
                    distinct_items[0],
                    exp.Column,
                )
            if (
                not isinstance(parsed, exp.Count)
                or aggregate_count != 1
                or parsed.find(exp.Window) is not None
                or not direct_argument
            ):
                retained.append(metric)
                continue
            action = (
                "COUNT_DISTINCT"
                if "DISTINCT" in parsed.sql(dialect="doris").upper()
                else "COUNT"
            )
            atomic_metric = {
                "name": str(metric.get("name") or "").strip(),
                "data_type": str(metric.get("data_type") or ""),
                "business_process": str(metric.get("business_process") or ""),
                "action": action,
                "measure": parsed.sql(dialect="doris"),
                "description": str(metric.get("description") or ""),
                "reason": str(metric.get("reason") or ""),
                "confidence": metric.get("confidence", 0.0),
            }
            atomic_index = len(atomic_metrics)
            atomic_metrics.append(atomic_metric)
            _repair(
                repairs,
                code="count_metric_normalized",
                table=result.table_name,
                path=f"columns.{group_name}[{index}]",
                before=metric,
                after=None,
                evidence={
                    "kind": "sql_ast_exact_count",
                    "operation": "remove_source",
                    "expression": parsed.sql(dialect="doris"),
                },
            )
            _repair(
                repairs,
                code="count_metric_normalized",
                table=result.table_name,
                path=f"columns.atomic_metrics[{atomic_index}]",
                before=None,
                after=atomic_metric,
                evidence={
                    "kind": "sql_ast_exact_count",
                    "operation": "add_target",
                    "expression": parsed.sql(dialect="doris"),
                },
            )
        result.columns[group_name] = retained


def _remove_column_references(
    result: Any,
    column_name: str,
    repairs: list[InspectionRepair],
) -> None:
    for entity_index, entity in enumerate(result.entities or []):
        keys = list(entity.get("key_columns") or [])
        retained = [
            key for key in keys if not _column_matches(key, column_name)
        ]
        if retained != keys:
            entity["key_columns"] = retained
            _repair(
                repairs,
                code="hallucinated_entity_key_removed",
                table=result.table_name,
                path=f"entities[{entity_index}].key_columns",
                before=keys,
                after=retained,
                evidence={"kind": "ddl_column_absent", "column": column_name},
            )
    grain = result.grain or {}
    for field_name in ("keys", "additional_key_columns"):
        values = list(grain.get(field_name) or [])
        retained = [
            value
            for value in values
            if not _column_matches(value, column_name)
        ]
        if retained != values:
            grain[field_name] = retained
            _repair(
                repairs,
                code="hallucinated_grain_key_removed",
                table=result.table_name,
                path=f"grain.{field_name}",
                before=values,
                after=retained,
                evidence={"kind": "ddl_column_absent", "column": column_name},
            )
    if _column_matches(grain.get("time_column"), column_name):
        before = grain.get("time_column")
        grain["time_column"] = ""
        _repair(
            repairs,
            code="hallucinated_grain_time_removed",
            table=result.table_name,
            path="grain.time_column",
            before=before,
            after="",
            evidence={"kind": "ddl_column_absent", "column": column_name},
        )
    for group_name in sorted(METRIC_GROUPS):
        for index, metric in enumerate(result.columns.get(group_name) or []):
            if _column_matches(metric.get("base_metric"), column_name):
                before = metric.get("base_metric")
                metric["base_metric"] = ""
                _repair(
                    repairs,
                    code="hallucinated_metric_base_removed",
                    table=result.table_name,
                    path=f"columns.{group_name}[{index}].base_metric",
                    before=before,
                    after="",
                    evidence={
                        "kind": "ddl_column_absent",
                        "column": column_name,
                    },
                )
            derived_from = list(metric.get("derived_from") or [])
            retained = [
                value
                for value in derived_from
                if not _column_matches(value, column_name)
            ]
            if retained != derived_from:
                metric["derived_from"] = retained
                _repair(
                    repairs,
                    code="hallucinated_metric_dependency_removed",
                    table=result.table_name,
                    path=f"columns.{group_name}[{index}].derived_from",
                    before=derived_from,
                    after=retained,
                    evidence={
                        "kind": "ddl_column_absent",
                        "column": column_name,
                    },
                )
            expression = str(metric.get("expression") or "")
            if expression_references_column(expression, column_name):
                metric["expression"] = ""
                _repair(
                    repairs,
                    code="hallucinated_metric_expression_removed",
                    table=result.table_name,
                    path=f"columns.{group_name}[{index}].expression",
                    before=expression,
                    after="",
                    evidence={
                        "kind": "ddl_column_absent",
                        "column": column_name,
                    },
                )


def _structural_reference_columns(result: Any) -> dict[str, str]:
    references = {}

    def add(value: Any) -> None:
        text = str(value or "").strip()
        canonical = _canonical_column(text).rsplit(".", 1)[-1]
        if canonical:
            references.setdefault(canonical, text.rsplit(".", 1)[-1])

    for entity in result.entities or []:
        for column_name in entity.get("key_columns") or []:
            add(column_name)
    grain = result.grain or {}
    for field_name in ("keys", "additional_key_columns"):
        for column_name in grain.get(field_name) or []:
            add(column_name)
    add(grain.get("time_column"))
    return references


def _recover_columns(
    result: Any,
    ddl_columns: tuple[str, ...],
    repairs: list[InspectionRepair],
    recovery_issues: list[InspectionIssue],
) -> None:
    ddl_by_name = {
        _canonical_column(column_name): column_name
        for column_name in ddl_columns
    }
    for group_name in COLUMN_GROUPS:
        for index, item in enumerate(result.columns.get(group_name) or []):
            canonical = _canonical_column(item.get("name"))
            display_name = ddl_by_name.get(canonical)
            if display_name and item.get("name") != display_name:
                before = item.get("name")
                item["name"] = display_name
                _repair(
                    repairs,
                    code="ddl_casefold_display_name",
                    table=result.table_name,
                    path=f"columns.{group_name}[{index}].name",
                    before=before,
                    after=display_name,
                    evidence={
                        "kind": "ddl_exact_casefold",
                        "ddl_column": display_name,
                    },
                )

    grouped_unknown_names = {
        _canonical_column(item.get("name")): str(
            item.get("name") or ""
        ).strip()
        for group_name in COLUMN_GROUPS
        for item in (result.columns.get(group_name) or [])
        if str(item.get("name") or "").strip()
        and _canonical_column(item.get("name")) not in ddl_by_name
    }
    structural_references = _structural_reference_columns(result)
    referenced_names = dict(grouped_unknown_names)
    referenced_names.update(structural_references)
    unknown_names = sorted(
        {
            canonical: display
            for canonical, display in referenced_names.items()
            if canonical not in ddl_by_name
        }.values(),
        key=str.casefold,
    )
    for column_name in unknown_names:
        sections, paths = column_reference_sections(result, column_name)
        before_occurrences = [
            (group_name, index, item)
            for group_name in COLUMN_GROUPS
            for index, item in enumerate(result.columns.get(group_name) or [])
            if _canonical_column(item.get("name"))
            == _canonical_column(column_name)
        ]
        for group_name in COLUMN_GROUPS:
            result.columns[group_name] = [
                item
                for item in (result.columns.get(group_name) or [])
                if _canonical_column(item.get("name"))
                != _canonical_column(column_name)
            ]
        if sections:
            _remove_column_references(result, column_name, repairs)
            issue_code = "hallucinated_column_reference"
        else:
            issue_code = "hallucinated_column_unreferenced"
        recovery_issues.append(
            _recovery_issue(
                issue_code,
                table=result.table_name,
                column_name=column_name,
                sections=sections,
                paths=paths,
            )
        )
        for group_name, index, item in before_occurrences:
            _repair(
                repairs,
                code="hallucinated_column_removed",
                table=result.table_name,
                path=f"columns.{group_name}[{index}]",
                before=item,
                after=None,
                evidence={
                    "kind": "ddl_column_absent",
                    "operation": "remove",
                    "referenced_sections": sorted(sections),
                },
            )

    occurrences: dict[str, list[tuple[str, int, dict[str, Any]]]] = {}
    for group_name in COLUMN_GROUPS:
        for index, item in enumerate(result.columns.get(group_name) or []):
            canonical = _canonical_column(item.get("name"))
            if canonical:
                occurrences.setdefault(canonical, []).append(
                    (group_name, index, item)
                )
    for canonical, items in sorted(occurrences.items()):
        if len(items) < 2:
            continue
        groups = {group_name for group_name, _index, _item in items}
        payloads = {
            _normalized_payload(item) for _group, _index, item in items
        }
        if len(groups) == 1 and len(payloads) == 1:
            group_name = next(iter(groups))
            duplicate_items = [
                (index, item)
                for index, item in enumerate(result.columns[group_name])
                if _canonical_column(item.get("name")) == canonical
            ]
            for index, item in duplicate_items[1:]:
                _repair(
                    repairs,
                    code="duplicate_column_same_group_removed",
                    table=result.table_name,
                    path=f"columns.{group_name}[{index}]",
                    before=item,
                    after=None,
                    evidence={
                        "kind": "identical_canonical_payload",
                        "operation": "remove",
                        "column": ddl_by_name[canonical],
                    },
                )
            retained_index, retained_item = duplicate_items[0]
            result.columns[group_name] = [
                item
                for item in result.columns[group_name]
                if _canonical_column(item.get("name")) != canonical
            ]
            result.columns[group_name].insert(retained_index, retained_item)
            recovery_issues.append(
                _recovery_issue(
                    "duplicate_columns_same_group",
                    table=result.table_name,
                    column_name=ddl_by_name[canonical],
                    groups=groups,
                )
            )
            continue
        conflict_items = [
            (group_name, index, item)
            for group_name in sorted(groups)
            for index, item in enumerate(result.columns[group_name])
            if _canonical_column(item.get("name")) == canonical
        ]
        for group_name, index, item in conflict_items:
            _repair(
                repairs,
                code="column_group_conflict_moved_to_others",
                table=result.table_name,
                path=f"columns.{group_name}[{index}]",
                before=item,
                after=None,
                evidence={
                    "kind": "cross_group_or_payload_conflict",
                    "operation": "remove",
                    "groups": sorted(groups),
                },
            )
        for group_name in groups:
            result.columns[group_name] = [
                item
                for item in result.columns[group_name]
                if _canonical_column(item.get("name")) != canonical
            ]
        recovered_item = {"name": ddl_by_name[canonical]}
        recovered_index = len(result.columns["others"])
        result.columns["others"].append(recovered_item)
        issue_code = (
            "column_group_conflict_metric"
            if groups & METRIC_GROUPS
            else "column_group_conflict_structure"
        )
        recovery_issues.append(
            _recovery_issue(
                issue_code,
                table=result.table_name,
                column_name=ddl_by_name[canonical],
                groups=groups,
            )
        )
        _repair(
            repairs,
            code="column_group_conflict_moved_to_others",
            table=result.table_name,
            path=f"columns.others[{recovered_index}]",
            before=None,
            after=recovered_item,
            evidence={
                "kind": "cross_group_or_payload_conflict",
                "operation": "add_target",
                "groups": sorted(groups),
            },
        )

    if str(
        result.inferred_layer or ""
    ).upper() in METRIC_GROUPING_LAYERS and bool(result.is_fact_table):
        returned = {
            _canonical_column(item.get("name"))
            for group_name in COLUMN_GROUPS
            for item in (result.columns.get(group_name) or [])
            if _canonical_column(item.get("name"))
        }
        for canonical, display_name in ddl_by_name.items():
            if canonical in returned:
                continue
            recovered_item = {"name": display_name}
            recovered_index = len(result.columns["others"])
            result.columns["others"].append(recovered_item)
            recovery_issues.append(
                _recovery_issue(
                    "missing_ddl_column",
                    table=result.table_name,
                    column_name=display_name,
                    sections=("metrics",),
                )
            )
            _repair(
                repairs,
                code="missing_ddl_column_added_to_others",
                table=result.table_name,
                path=f"columns.others[{recovered_index}]",
                before=None,
                after=recovered_item,
                evidence={
                    "kind": "ddl_column_coverage",
                    "operation": "add",
                    "ddl_column": display_name,
                },
            )


def _lineage_metric_tables(
    ctx: Any,
    *,
    target_metric: str,
    base_metric: str,
) -> list[str]:
    target_key = _canonical_column(target_metric)
    base_key = _canonical_column(base_metric)
    target_identities = {
        value
        for value in (
            getattr(ctx, "table_name", ""),
            getattr(ctx, "table_identity", ""),
        )
        if _canonical_table(value)
    }
    upstream_identities = {
        value
        for value in (
            list(getattr(ctx, "upstream_tables", ()) or ())
            + list((getattr(ctx, "upstream_metric_groups", {}) or {}).keys())
        )
        if _canonical_table(value)
    }
    tables = set()
    for edge in getattr(ctx, "column_lineage", ()) or ():
        if not isinstance(edge, dict):
            continue
        target_table, target_column = _split_column_identifier(
            edge.get("target")
        )
        source_table, source_column = _split_column_identifier(
            edge.get("source")
        )
        target_matches = _matching_tables(
            target_table,
            target_identities,
        )
        source_matches = _matching_tables(
            source_table,
            upstream_identities,
        )
        if (
            target_column == target_key
            and source_column == base_key
            and len(target_matches) == 1
            and len(source_matches) == 1
        ):
            tables.add(source_matches[0])
    return sorted(tables)


def _recover_metric_relationships(
    result: Any,
    ctx: Any,
    repairs: list[InspectionRepair],
) -> None:
    known_identities = {
        value
        for value in (
            [result.table_name]
            + list(getattr(ctx, "upstream_tables", ()) or ())
            + list((getattr(ctx, "upstream_metric_groups", {}) or {}).keys())
        )
        if _canonical_table(value)
    }
    for index, metric in enumerate(result.derived_metrics):
        metric_name = str(metric.get("name") or "").strip()
        base_metric = str(metric.get("base_metric") or "").strip()
        base_table = str(metric.get("base_metric_table") or "").strip()
        if not metric_name or not base_metric:
            continue
        lineage_tables = _lineage_metric_tables(
            ctx,
            target_metric=metric_name,
            base_metric=base_metric,
        )
        if base_table:
            matches = _matching_tables(
                base_table,
                known_identities | set(lineage_tables),
            )
            if len(matches) == 1 and matches[0] != base_table:
                metric["base_metric_table"] = matches[0]
                _repair(
                    repairs,
                    code="canonical_metric_table_normalized",
                    table=result.table_name,
                    path=(
                        f"columns.derived_metrics[{index}].base_metric_table"
                    ),
                    before=base_table,
                    after=matches[0],
                    evidence={
                        "kind": "canonical_table_identity",
                        "matched_table": matches[0],
                    },
                )
            continue
        if len(lineage_tables) != 1:
            continue
        metric["base_metric_table"] = lineage_tables[0]
        _repair(
            repairs,
            code="lineage_metric_table_completed",
            table=result.table_name,
            path=f"columns.derived_metrics[{index}].base_metric_table",
            before="",
            after=lineage_tables[0],
            evidence={
                "kind": "unique_direct_column_lineage",
                "source_table": lineage_tables[0],
                "base_metric": base_metric,
            },
        )


def _confirmed_codes(ctx: Any, option_name: str) -> dict[str, str]:
    options = (getattr(ctx, "business_semantics_options", {}) or {}).get(
        option_name
    )
    if not isinstance(options, list):
        return {}
    displays_by_code: dict[str, set[str]] = {}
    for item in options:
        if not isinstance(item, dict):
            continue
        display = str(item.get("code") or "").strip()
        canonical = canonical_semantic_code(display)
        if canonical:
            displays_by_code.setdefault(canonical, set()).add(display)
    return {
        canonical: next(iter(displays))
        for canonical, displays in displays_by_code.items()
        if len(displays) == 1
    }


def _normalize_semantic_codes(
    result: Any,
    ctx: Any,
    repairs: list[InspectionRepair],
) -> None:
    process_codes = _confirmed_codes(ctx, "business_processes")
    subject_codes = _confirmed_codes(ctx, "semantic_subjects")

    def normalize(
        owner: dict[str, Any],
        field_name: str,
        path: str,
        confirmed: dict[str, str],
    ) -> None:
        before = str(owner.get(field_name) or "").strip()
        after = confirmed.get(canonical_semantic_code(before))
        if not after or after == before:
            return
        owner[field_name] = after
        _repair(
            repairs,
            code="confirmed_semantic_code_normalized",
            table=result.table_name,
            path=path,
            before=before,
            after=after,
            evidence={"kind": "confirmed_catalog_code", "code": after},
        )

    table_process = {"business_process": result.business_process}
    normalize(
        table_process,
        "business_process",
        "business_process",
        process_codes,
    )
    result.business_process = table_process["business_process"]
    for group_name in sorted(METRIC_GROUPS):
        for index, metric in enumerate(result.columns.get(group_name) or []):
            normalize(
                metric,
                "business_process",
                f"columns.{group_name}[{index}].business_process",
                process_codes,
            )
    for index, entity in enumerate(result.entities or []):
        normalize(
            entity,
            "code",
            f"entities[{index}].code",
            subject_codes,
        )
    grain = result.grain if isinstance(result.grain, dict) else {}
    grain_entities = list(grain.get("entities") or [])
    for index, before in enumerate(grain_entities):
        after = subject_codes.get(canonical_semantic_code(before))
        if not after or after == before:
            continue
        grain_entities[index] = after
        _repair(
            repairs,
            code="confirmed_semantic_code_normalized",
            table=result.table_name,
            path=f"grain.entities[{index}]",
            before=before,
            after=after,
            evidence={"kind": "confirmed_catalog_code", "code": after},
        )
    if grain_entities:
        grain["entities"] = grain_entities


def _recover_bridge_grain(
    result: Any,
    ddl_columns: tuple[str, ...],
    repairs: list[InspectionRepair],
) -> None:
    if str(result.table_type or "").lower() != "bridge" or not ddl_columns:
        return
    ddl_names = {_canonical_column(name) for name in ddl_columns}
    entities = [
        item for item in result.entities or [] if isinstance(item, dict)
    ]
    codes = [
        str(entity.get("code") or "").strip()
        for entity in entities
        if str(entity.get("code") or "").strip()
    ]
    valid_keys = all(
        entity.get("key_columns")
        and all(
            _canonical_column(column) in ddl_names
            for column in entity.get("key_columns") or []
        )
        for entity in entities
    )
    if (
        len(entities) < 2
        or len(codes) != len(entities)
        or len({canonical_semantic_code(code) for code in codes}) != len(codes)
        or not valid_keys
    ):
        return
    grain = result.grain if isinstance(result.grain, dict) else {}
    before = list(grain.get("entities") or [])
    if before:
        return
    grain["entities"] = codes
    result.grain = grain
    _repair(
        repairs,
        code="bridge_grain_entities_completed",
        table=result.table_name,
        path="grain.entities",
        before=before,
        after=codes,
        evidence={
            "kind": "validated_bridge_entities",
            "entity_codes": codes,
        },
    )


def _candidate_payload(result: Any) -> dict[str, Any]:
    return {
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "business_process": result.business_process,
        "business_process_mode": result.business_process_mode,
        "business_process_sources": list(result.business_process_sources),
        "business_process_conflicts": list(result.business_process_conflicts),
        "inferred_data_domain": result.inferred_data_domain,
        "inferred_business_area": result.inferred_business_area,
        "dimension_role": result.dimension_role,
        "dimension_content_type": result.dimension_content_type,
        "confidence": result.confidence,
        "reasoning_steps": list(result.reasoning_steps),
        "columns": copy.deepcopy(result.columns),
        "entities": copy.deepcopy(result.entities),
        "grain": copy.deepcopy(result.grain),
    }


def recover_inspection_result(
    result: Any,
    ctx: Any,
) -> Any:
    """Return a new, deterministically recovered and auditable result."""
    recovered = copy.deepcopy(result)
    repairs = list(getattr(recovered, "repair_audit", ()) or ())
    recovery_issues = list(getattr(recovered, "issues", ()) or ())
    _normalize_count_metrics(recovered, repairs)
    ddl_columns = _ddl_columns(getattr(ctx, "ddl", ""))
    if ddl_columns:
        _recover_columns(
            recovered,
            ddl_columns,
            repairs,
            recovery_issues,
        )
    _recover_metric_relationships(recovered, ctx, repairs)
    _normalize_semantic_codes(recovered, ctx, repairs)
    _recover_bridge_grain(recovered, ddl_columns, repairs)
    recovered.entity = legacy_entity_from_entities(recovered.entities)
    recovered.related_entities = legacy_related_entities_from_entities(
        recovered.entities
    )
    recovered.repair_audit = tuple(repairs)
    recovered.issues = sort_issues(recovery_issues)
    recovered.recovered_candidate = RecoveredInspectionCandidate.create(
        table_name=recovered.table_name,
        payload=_candidate_payload(recovered),
        repair_audit=repairs,
    )
    return recovered
