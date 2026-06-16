"""Lightweight lineage domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _strip_sql_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".sql") else value


@dataclass(frozen=True)
class LineageColumn:
    name: str
    data_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

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
    layer: str = "OTHER"
    columns: tuple[LineageColumn, ...] = ()
    is_transient: bool = False
    transient_sources: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageTable":
        return cls(
            name=str(data.get("name") or "").strip(),
            full_name=str(data.get("full_name") or ""),
            layer=str(data.get("layer") or "OTHER").upper(),
            columns=tuple(
                LineageColumn.from_dict(column)
                for column in data.get("columns") or []
                if isinstance(column, dict)
            ),
            is_transient=bool(data.get("is_transient")),
            transient_sources=tuple(
                str(source or "")
                for source in data.get("transient_sources") or []
                if str(source or "")
            ),
            raw=dict(data),
        )


@dataclass(frozen=True)
class LineageRef:
    type: str
    id: str
    raw: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_raw(cls, value: Any, *, default_type: str = "column") -> "LineageRef":
        if isinstance(value, dict):
            ref_type = str(value.get("type") or default_type).strip() or default_type
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
        return self.id.rsplit(".", 1)[0]

    def column_name(self) -> str:
        if self.type != "column" or not self.id:
            return ""
        return self.id.rsplit(".", 1)[-1]


@dataclass(frozen=True)
class LineageEdge:
    source: LineageRef
    target: LineageRef
    relation_type: str = "direct"
    transformation_type: str = ""
    expression: str = ""
    source_file: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageEdge":
        return cls(
            source=LineageRef.from_raw(data.get("source")),
            target=LineageRef.from_raw(data.get("target")),
            relation_type=str(data.get("relation_type") or "direct").lower(),
            transformation_type=str(data.get("transformation_type") or "").lower(),
            expression=str(data.get("expression") or ""),
            source_file=str(data.get("source_file") or ""),
            raw=dict(data),
        )


@dataclass(frozen=True)
class LineageJob:
    name: str
    source_file: str


@dataclass(frozen=True)
class LineageSnapshot:
    project: str
    snapshot_id: str = ""
    tables: tuple[LineageTable, ...] = ()
    edges: tuple[LineageEdge, ...] = ()
    indirect_edges: tuple[dict[str, Any], ...] = ()
    jobs: tuple[LineageJob, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(
        cls,
        project: str,
        data: dict[str, Any],
        *,
        snapshot_id: str = "",
    ) -> "LineageSnapshot":
        raw_edges = [
            edge for edge in data.get("edges") or []
            if isinstance(edge, dict)
        ]
        raw_indirect_edges = [
            edge for edge in data.get("indirect_edges") or []
            if isinstance(edge, dict)
        ]
        source_files = sorted({
            str(edge.get("source_file") or "")
            for edge in raw_edges + raw_indirect_edges
            if str(edge.get("source_file") or "")
        })
        return cls(
            project=project,
            snapshot_id=snapshot_id,
            tables=tuple(
                LineageTable.from_dict(table)
                for table in data.get("tables") or []
                if isinstance(table, dict)
            ),
            edges=tuple(LineageEdge.from_dict(edge) for edge in raw_edges),
            indirect_edges=tuple(dict(edge) for edge in raw_indirect_edges),
            jobs=tuple(
                LineageJob(
                    name=_strip_sql_suffix(source_file.rsplit("/", 1)[-1]),
                    source_file=source_file,
                )
                for source_file in source_files
            ),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)
