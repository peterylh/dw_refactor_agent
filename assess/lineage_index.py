"""Reusable lineage indexes for assessment scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assess.project_facts.asset_catalog import build_asset_catalog
from lineage.table_graph import build_table_layer_map
from lineage.view import LineageView


@dataclass
class AssessmentLineageIndex:
    project: str
    tables: list
    edges: list
    indirect_edges: list
    table_layers: dict
    upstream: dict
    downstream: dict
    table_edges: dict
    lineage_view: LineageView
    asset_catalog: dict

    @classmethod
    def build(
        cls,
        *,
        project: str,
        lineage_data: dict[str, Any],
        model_metadata: dict | None,
        project_dir: Path,
    ) -> "AssessmentLineageIndex":
        tables = lineage_data.get("tables", [])
        edges = lineage_data.get("edges", [])
        indirect_edges = lineage_data.get("indirect_edges", [])
        lineage_view = LineageView.from_parts(
            "assessment",
            tables,
            edges,
            indirect_edges,
        )
        upstream, downstream = lineage_view.asset_table_graph()
        return cls(
            project=project,
            tables=tables,
            edges=edges,
            indirect_edges=indirect_edges,
            table_layers=build_table_layer_map(tables),
            upstream=upstream,
            downstream=downstream,
            table_edges=lineage_view.table_edge_source_files(),
            lineage_view=lineage_view,
            asset_catalog=build_asset_catalog(
                tables,
                model_metadata,
                project_dir,
                edges=edges,
                indirect_edges=indirect_edges,
            ),
        )
