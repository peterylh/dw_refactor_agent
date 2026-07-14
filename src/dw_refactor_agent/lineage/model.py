"""Lightweight lineage domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dw_refactor_agent.lineage.identifiers import split_column_ref


def _strip_sql_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".sql") else value


def _job_name_from_source_file(source_file: str) -> str:
    normalized = str(source_file or "").replace("\\", "/")
    return _strip_sql_suffix(normalized.rsplit("/", 1)[-1])


def _lineage_format_version(data: dict[str, Any]) -> int:
    if "format_version" not in data:
        return 1
    version = data["format_version"]
    if type(version) is int and version in {1, 2}:
        return version
    raise ValueError(
        f"lineage format_version must be integer 1 or 2; received {version!r}"
    )


@dataclass(frozen=True)
class LineageColumn:
    name: str
    data_type: str = ""
    raw: dict[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageColumn":
        return cls(
            name=str(data.get("name") or "").strip(),
            data_type=str(data.get("type") or data.get("data_type") or ""),
            raw=dict(data),
        )


@dataclass(frozen=True)
class LineageTable:
    name: str
    full_name: str = ""
    columns: tuple[LineageColumn, ...] = ()
    dataset_type: str = "managed"
    is_transient: bool = False
    transient_sources: tuple[str, ...] = ()
    raw: dict[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageTable":
        raw = dict(data)
        raw.pop("layer", None)
        is_transient = bool(data.get("is_transient"))
        return cls(
            name=str(data.get("name") or "").strip(),
            full_name=str(data.get("full_name") or ""),
            columns=tuple(
                LineageColumn.from_dict(column)
                for column in data.get("columns") or []
                if isinstance(column, dict)
            ),
            dataset_type=str(
                data.get("dataset_type")
                or ("temporary" if is_transient else "managed")
            ),
            is_transient=is_transient,
            transient_sources=tuple(
                str(source or "")
                for source in data.get("transient_sources") or []
                if str(source or "")
            ),
            raw=raw,
        )


@dataclass(frozen=True)
class LineageRef:
    type: str
    id: str
    raw: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_raw(
        cls, value: Any, *, default_type: str = "column"
    ) -> "LineageRef":
        if isinstance(value, dict):
            ref_type = (
                str(value.get("type") or default_type).strip() or default_type
            )
            ref_id = str(
                value.get("id")
                or value.get("value")
                or value.get("expression")
                or ""
            ).strip()
            return cls(type=ref_type, id=ref_id, raw=dict(value))
        return cls(type=default_type, id=str(value or "").strip(), raw=value)

    def table_name(self) -> str:
        if self.type == "table":
            return self.id
        if self.type != "column" or not self.id:
            return ""
        split_ref = split_column_ref(self.id)
        return split_ref[0] if split_ref is not None else ""

    def column_name(self) -> str:
        if self.type != "column" or not self.id:
            return ""
        split_ref = split_column_ref(self.id)
        return split_ref[1] if split_ref is not None else ""


@dataclass(frozen=True)
class LineageEdge:
    source: LineageRef
    target: LineageRef
    relation_type: str = "direct"
    transformation_type: str = ""
    expression: str = ""
    job: str = ""
    source_file: str = ""
    raw: dict[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        legacy: bool = True,
    ) -> "LineageEdge":
        source_file = str(data.get("source_file") or "") if legacy else ""
        job = (
            _job_name_from_source_file(source_file)
            if legacy
            else str(data.get("job") or "")
        )
        return cls(
            source=LineageRef.from_raw(data.get("source")),
            target=LineageRef.from_raw(data.get("target")),
            relation_type=str(data.get("relation_type") or "direct").lower(),
            transformation_type=str(
                data.get("transformation_type") or ""
            ).lower(),
            expression=str(data.get("expression") or ""),
            job=job,
            source_file=source_file,
            raw=dict(data),
        )


@dataclass(frozen=True)
class LineageJob:
    name: str
    source_file: str = ""
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageJob":
        return cls(
            name=str(data.get("name") or "").strip(),
            source_file=str(data.get("source_file") or ""),
            inputs=tuple(str(value) for value in data.get("inputs") or []),
            outputs=tuple(str(value) for value in data.get("outputs") or []),
        )


@dataclass(frozen=True)
class LineageSnapshot:
    project: str
    snapshot_id: str = ""
    tables: tuple[LineageTable, ...] = ()
    edges: tuple[LineageEdge, ...] = ()
    indirect_edges: tuple[dict[str, Any], ...] = ()
    jobs: tuple[LineageJob, ...] = ()
    raw: dict[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )

    @classmethod
    def from_dict(
        cls,
        project: str,
        data: dict[str, Any],
        *,
        snapshot_id: str = "",
    ) -> "LineageSnapshot":
        is_v2 = _lineage_format_version(data) == 2
        raw_edges = [
            edge for edge in data.get("edges") or [] if isinstance(edge, dict)
        ]
        raw_indirect_edges = [
            edge
            for edge in data.get("indirect_edges") or []
            if isinstance(edge, dict)
        ]
        source_files = sorted(
            {
                str(edge.get("source_file") or "")
                for edge in raw_edges + raw_indirect_edges
                if str(edge.get("source_file") or "")
            }
        )
        return cls(
            project=project,
            snapshot_id=snapshot_id,
            tables=tuple(
                LineageTable.from_dict(table)
                for table in data.get("tables") or []
                if isinstance(table, dict)
            ),
            edges=tuple(
                LineageEdge.from_dict(edge, legacy=not is_v2)
                for edge in raw_edges
            ),
            indirect_edges=tuple(dict(edge) for edge in raw_indirect_edges),
            jobs=(
                tuple(
                    LineageJob.from_dict(job)
                    for job in data.get("jobs") or []
                    if isinstance(job, dict)
                )
                if is_v2
                else tuple(
                    LineageJob(
                        name=_job_name_from_source_file(source_file),
                        source_file=source_file,
                    )
                    for source_file in source_files
                )
            ),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data["tables"] = [dict(table.raw) for table in self.tables]
        return data
