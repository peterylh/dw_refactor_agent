"""Bounded lineage graph queries for CLI and report renderers."""

from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass

from lineage.view import LineageView

VALID_DIRECTIONS = {"upstream", "downstream", "both"}
AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class TableEdge:
    source: str
    target: str
    hops: int
    source_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableColumnLineage:
    source: str
    target: str
    expression: str = ""
    source_file: str = ""
    transformation_type: str = "passthrough"
    conditions: tuple["ColumnCondition", ...] = ()


@dataclass(frozen=True)
class TableSubgraph:
    project: str
    root: str
    direction: str
    depth: int
    tables: set[str]
    table_layers: dict[str, str]
    table_columns: dict[str, tuple[str, ...]]
    edges: tuple[TableEdge, ...]
    column_lineage: tuple[TableColumnLineage, ...]
    layer_counts: dict[str, int]
    hidden_boundary_edges: int = 0

    @property
    def jobs(self) -> set[str]:
        return {
            source_file
            for edge in self.edges
            for source_file in edge.source_files
            if source_file
        }


@dataclass(frozen=True)
class ColumnCondition:
    source: str
    condition_type: str
    condition_expression: str
    source_file: str = ""


@dataclass(frozen=True)
class ColumnStep:
    source: str
    target: str
    expression: str = ""
    source_file: str = ""
    transformation_type: str = "passthrough"
    conditions: tuple[ColumnCondition, ...] = ()


@dataclass(frozen=True)
class ColumnPath:
    nodes: tuple[str, ...]
    steps: tuple[ColumnStep, ...]


@dataclass(frozen=True)
class ColumnLineage:
    project: str
    table: str
    column: str
    direction: str
    depth: int
    paths: tuple[ColumnPath, ...]

    @property
    def source_columns(self) -> set[str]:
        return {path.nodes[0] for path in self.paths if path.nodes}

    @property
    def source_files(self) -> set[str]:
        return {
            step.source_file
            for path in self.paths
            for step in path.steps
            if step.source_file
        }

    @property
    def transformation_counts(self) -> dict[str, int]:
        counts = Counter(
            step.transformation_type or "passthrough"
            for path in self.paths
            for step in path.steps
        )
        return dict(sorted(counts.items()))


@dataclass(frozen=True)
class ProjectStats:
    project: str
    table_count: int
    table_edge_count: int
    column_edge_count: int
    indirect_edge_count: int
    job_count: int
    layer_counts: dict[str, int]


def _normalize_direction(direction: str) -> str:
    normalized = str(direction or "upstream").lower()
    if normalized not in VALID_DIRECTIONS:
        raise ValueError(
            f"direction must be one of {sorted(VALID_DIRECTIONS)}"
        )
    return normalized


def _table_layers(view: LineageView) -> dict[str, str]:
    return {
        table.name: table.layer or "OTHER"
        for table in view.tables()
        if table.name
    }


def _graph_tables(
    upstream: dict[str, set[str]],
    downstream: dict[str, set[str]],
) -> set[str]:
    tables = set(upstream) | set(downstream)
    for parents in upstream.values():
        tables.update(parents)
    for children in downstream.values():
        tables.update(children)
    return tables


def _source_files_for(
    source: str,
    target: str,
    table_edge_files: dict[tuple[str, str], set[str]],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            source_file
            for source_file in table_edge_files.get((source, target), set())
            if source_file
        )
    )


def _column_node(table_name: str, column_name: str) -> str:
    return f"{table_name}.{column_name}"


def _table_from_column(node: str) -> str:
    return str(node or "").rsplit(".", 1)[0]


def _transformation_type(expression: str) -> str:
    return (
        "aggregation"
        if AGGREGATE_PATTERN.search(expression or "")
        else "passthrough"
    )


def _conditions_from_record(record: dict) -> tuple[ColumnCondition, ...]:
    conditions = []
    for condition in record.get("condition_lineage") or []:
        source = str(condition.get("source") or "")
        condition_type = str(condition.get("condition_type") or "").upper()
        condition_expression = str(condition.get("condition_expression") or "")
        if not source or not condition_type:
            continue
        conditions.append(
            ColumnCondition(
                source=source,
                condition_type=condition_type,
                condition_expression=condition_expression,
                source_file=str(condition.get("source_file") or ""),
            )
        )
    return tuple(
        sorted(
            conditions,
            key=lambda item: (
                item.condition_type,
                item.source,
                item.condition_expression,
                item.source_file,
            ),
        )
    )


def _column_steps_for_target(
    view: LineageView,
    target_node: str,
) -> list[ColumnStep]:
    target_table = _table_from_column(target_node)
    steps = []
    for record in view.column_lineage_for_table(target_table):
        source = str(record.get("source") or "")
        target = str(record.get("target") or "")
        if not source or target != target_node:
            continue
        expression = str(record.get("expression") or "")
        steps.append(
            ColumnStep(
                source=source,
                target=target,
                expression=expression,
                source_file=str(record.get("source_file") or ""),
                transformation_type=_transformation_type(expression),
                conditions=_conditions_from_record(record),
            )
        )
    return sorted(steps, key=lambda step: (step.source, step.target))


def _column_lineage_for_subgraph(
    view: LineageView,
    selected_tables: set[str],
) -> tuple[TableColumnLineage, ...]:
    rows = set()
    for table in sorted(selected_tables):
        for record in view.column_lineage_for_table(table):
            source = str(record.get("source") or "")
            target = str(record.get("target") or "")
            if (
                not source
                or not target
                or _table_from_column(source) not in selected_tables
                or _table_from_column(target) not in selected_tables
            ):
                continue
            expression = str(record.get("expression") or "")
            rows.add(
                TableColumnLineage(
                    source=source,
                    target=target,
                    expression=expression,
                    source_file=str(record.get("source_file") or ""),
                    transformation_type=_transformation_type(expression),
                    conditions=_conditions_from_record(record),
                )
            )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                _table_from_column(row.target),
                row.target,
                row.source,
                row.expression,
            ),
        )
    )


def _trace_upstream_column_paths(
    view: LineageView,
    target_node: str,
    remaining_depth: int,
    visiting: set[str],
) -> list[ColumnPath]:
    if remaining_depth <= 0 or target_node in visiting:
        return []

    paths = []
    for step in _column_steps_for_target(view, target_node):
        upstream_paths = _trace_upstream_column_paths(
            view,
            step.source,
            remaining_depth - 1,
            visiting | {target_node},
        )
        if not upstream_paths:
            paths.append(
                ColumnPath(
                    nodes=(step.source, step.target),
                    steps=(step,),
                )
            )
            continue

        for upstream_path in upstream_paths:
            paths.append(
                ColumnPath(
                    nodes=upstream_path.nodes + (step.target,),
                    steps=upstream_path.steps + (step,),
                )
            )
    return sorted(paths, key=lambda path: path.nodes)


def _all_column_steps(view: LineageView) -> list[ColumnStep]:
    steps = set()
    for table in sorted(view.tables(), key=lambda item: item.name):
        if not table.name:
            continue
        for record in view.column_lineage_for_table(table.name):
            source = str(record.get("source") or "")
            target = str(record.get("target") or "")
            if not source or not target:
                continue
            expression = str(record.get("expression") or "")
            steps.add(
                ColumnStep(
                    source=source,
                    target=target,
                    expression=expression,
                    source_file=str(record.get("source_file") or ""),
                    transformation_type=_transformation_type(expression),
                    conditions=_conditions_from_record(record),
                )
            )
    return sorted(steps, key=lambda step: (step.source, step.target))


def _trace_downstream_column_paths(
    source_node: str,
    remaining_depth: int,
    visiting: set[str],
    outgoing: dict[str, list[ColumnStep]],
) -> list[ColumnPath]:
    if remaining_depth <= 0 or source_node in visiting:
        return []

    paths = []
    for step in outgoing.get(source_node, []):
        downstream_paths = _trace_downstream_column_paths(
            step.target,
            remaining_depth - 1,
            visiting | {source_node},
            outgoing,
        )
        if not downstream_paths:
            paths.append(
                ColumnPath(
                    nodes=(step.source, step.target),
                    steps=(step,),
                )
            )
            continue

        for downstream_path in downstream_paths:
            paths.append(
                ColumnPath(
                    nodes=(step.source,) + downstream_path.nodes,
                    steps=(step,) + downstream_path.steps,
                )
            )
    return sorted(paths, key=lambda path: path.nodes)


def build_column_lineage(
    view: LineageView,
    table_name: str,
    column_name: str,
    *,
    direction: str = "upstream",
    depth: int = 1,
) -> ColumnLineage:
    """Return bounded column lineage paths for one required table column."""
    normalized_direction = _normalize_direction(direction)

    table = str(table_name or "").strip()
    column = str(column_name or "").strip()
    if not column:
        raise ValueError("column is required for column lineage")

    layers = _table_layers(view)
    if table not in layers:
        raise ValueError(f"unknown table: {table}")

    max_depth = max(0, int(depth))
    target_node = _column_node(table, column)
    paths = []
    if normalized_direction in {"upstream", "both"}:
        paths.extend(
            _trace_upstream_column_paths(
                view,
                target_node,
                max_depth,
                set(),
            )
        )
    if normalized_direction in {"downstream", "both"}:
        outgoing: dict[str, list[ColumnStep]] = {}
        for step in _all_column_steps(view):
            outgoing.setdefault(step.source, []).append(step)
        paths.extend(
            _trace_downstream_column_paths(
                target_node,
                max_depth,
                set(),
                outgoing,
            )
        )

    return ColumnLineage(
        project=view.snapshot.project,
        table=table,
        column=column,
        direction=normalized_direction,
        depth=max_depth,
        paths=tuple(sorted(paths, key=lambda path: path.nodes)),
    )


def build_project_stats(view: LineageView) -> ProjectStats:
    """Return project-wide lineage counts for a snapshot."""
    tables = view.tables()
    layer_counts = Counter(table.layer or "OTHER" for table in tables)
    return ProjectStats(
        project=view.snapshot.project,
        table_count=len(tables),
        table_edge_count=len(view.table_edge_source_files()),
        column_edge_count=len(view.snapshot.edges),
        indirect_edge_count=len(view.snapshot.indirect_edges),
        job_count=len(view.snapshot.jobs),
        layer_counts=dict(sorted(layer_counts.items())),
    )


def build_table_subgraph(
    view: LineageView,
    table_name: str,
    *,
    direction: str = "upstream",
    depth: int = 1,
) -> TableSubgraph:
    """Return a bounded table-level lineage subgraph around one root table."""
    normalized_direction = _normalize_direction(direction)
    max_depth = max(0, int(depth))
    root = str(table_name or "").strip()

    upstream, downstream = view.asset_table_graph()
    layers = _table_layers(view)
    known_tables = set(layers) | _graph_tables(upstream, downstream)
    if root not in known_tables:
        raise ValueError(f"unknown table: {root}")

    table_edge_files = view.table_edge_source_files()
    distances = {root: 0}
    selected_edges: set[TableEdge] = set()
    hidden_boundary_edges = 0
    queue = deque([root])

    while queue:
        current = queue.popleft()
        current_depth = distances[current]

        steps: list[tuple[str, str, str]] = []
        if normalized_direction in {"upstream", "both"}:
            steps.extend(
                (parent, current, parent)
                for parent in sorted(upstream.get(current, set()))
            )
        if normalized_direction in {"downstream", "both"}:
            steps.extend(
                (current, child, child)
                for child in sorted(downstream.get(current, set()))
            )

        for source, target, neighbor in steps:
            next_depth = current_depth + 1
            if next_depth > max_depth:
                hidden_boundary_edges += 1
                continue

            selected_edges.add(
                TableEdge(
                    source=source,
                    target=target,
                    hops=next_depth,
                    source_files=_source_files_for(
                        source,
                        target,
                        table_edge_files,
                    ),
                )
            )
            if neighbor not in distances or next_depth < distances[neighbor]:
                distances[neighbor] = next_depth
                queue.append(neighbor)

    selected_tables = set(distances)
    selected_layers = {
        table: layers.get(table, "OTHER") for table in selected_tables
    }
    table_columns = {
        table.name: tuple(
            column.name for column in table.columns if column.name
        )
        for table in view.tables()
        if table.name in selected_tables
    }
    counts = Counter(layers.get(table, "OTHER") for table in selected_tables)
    return TableSubgraph(
        project=view.snapshot.project,
        root=root,
        direction=normalized_direction,
        depth=max_depth,
        tables=selected_tables,
        table_layers=selected_layers,
        table_columns=table_columns,
        edges=tuple(
            sorted(
                selected_edges,
                key=lambda edge: (edge.hops, edge.target, edge.source),
            )
        ),
        column_lineage=_column_lineage_for_subgraph(view, selected_tables),
        layer_counts=dict(sorted(counts.items())),
        hidden_boundary_edges=hidden_boundary_edges,
    )
