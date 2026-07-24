"""Shared assessment context for scoring dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    AssetCatalog,
    build_asset_catalog,
    ensure_asset_catalog,
)
from dw_refactor_agent.assessment.semantic_models import (
    AssessmentModelSemantics,
    SemanticCoverage,
)
from dw_refactor_agent.config import UnavailableModelSection, determine_layer
from dw_refactor_agent.lineage.view import LineageView


class _cached_property:
    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = self.func(instance)
        return instance.__dict__[self.name]


def _empty_asset_catalog(project_dir: Path | None = None) -> AssetCatalog:
    return AssetCatalog(
        project_dir=Path(project_dir) if project_dir else None,
    )


@dataclass
class AssessmentContext:
    """Prepared facts and indexes shared by assessment scorers."""

    project: str
    lineage: LineageView
    assets: AssetCatalog
    models: dict | None = None
    naming_config: Any = None
    business_domain_config: Any = None

    def __post_init__(self) -> None:
        self.assets = ensure_asset_catalog(self.assets)

    @_cached_property
    def model_views(self) -> dict[str, AssessmentModelSemantics]:
        return {
            str(name).split(".")[-1]: AssessmentModelSemantics.from_metadata(
                metadata,
                source=f"assessment model {name}",
            )
            for name, metadata in (self.models or {}).items()
            if isinstance(metadata, dict)
        }

    def model_view(self, table_name: str) -> AssessmentModelSemantics | None:
        return self.model_views.get(str(table_name).split(".")[-1])

    def operational_layer(self, table_name: str) -> str | None:
        view = self.model_view(table_name)
        return view.operational_layer if view is not None else None

    def semantic_coverage(
        self,
        eligible_names,
        sections,
    ) -> SemanticCoverage:
        views = {
            str(name): view
            for name in eligible_names
            for view in [self.model_view(name)]
            if view is not None
        }
        return SemanticCoverage.build(
            views,
            eligible_names,
            sections,
        )

    @_cached_property
    def tables(self) -> list:
        tables = []
        for table in self.lineage.tables():
            row = dict(table.raw)
            if row.get("name"):
                short_name = str(row["name"]).split(".")[-1]
                view = self.model_view(short_name)
                layer = (
                    view.layer
                    if view is not None
                    else determine_layer(short_name, self.project)
                )
                if isinstance(layer, UnavailableModelSection):
                    layer = None
                row["layer"] = str(layer).upper() if layer else None
                row["semantic_status"] = (
                    "quarantined"
                    if view is not None
                    and "classification" in view.quarantined_sections
                    else "active"
                )
            tables.append(row)
        return tables

    @_cached_property
    def table_layers(self) -> dict:
        return {
            str(table.get("name")): table.get("layer")
            for table in self.tables
            if table.get("name")
        }

    @_cached_property
    def upstream(self) -> dict:
        upstream, _downstream = self.lineage.asset_table_graph()
        return upstream

    @_cached_property
    def downstream(self) -> dict:
        _upstream, downstream = self.lineage.asset_table_graph()
        return downstream

    @_cached_property
    def table_edges(self) -> dict:
        return self.lineage.table_edge_source_files()

    @classmethod
    def from_lineage_data(
        cls,
        *,
        project: str,
        lineage_data: dict[str, Any],
        models: dict | None,
        project_dir: Path | None,
        business_domain_config: Any = None,
        naming_config: Any = None,
    ) -> "AssessmentContext":
        return cls.from_facts(
            project=project,
            tables=lineage_data.get("tables", []),
            edges=lineage_data.get("edges", []),
            indirect_edges=lineage_data.get("indirect_edges", []),
            models=models,
            project_dir=project_dir,
            business_domain_config=business_domain_config,
            naming_config=naming_config,
        )

    @classmethod
    def from_facts(
        cls,
        *,
        project: str = "assessment",
        tables: list | None = None,
        edges: list | None = None,
        indirect_edges: list | None = None,
        models: dict | None = None,
        project_dir: Path | None = None,
        business_domain_config: Any = None,
        naming_config: Any = None,
        assets: AssetCatalog | dict | None = None,
    ) -> "AssessmentContext":
        tables = tables or []
        edges = edges or []
        indirect_edges = indirect_edges or []
        project_dir = Path(project_dir) if project_dir else None
        lineage = LineageView.from_parts(
            project,
            tables,
            edges,
            indirect_edges,
        )
        if assets is None:
            assets = (
                build_asset_catalog(
                    tables,
                    models,
                    project_dir,
                    edges=edges,
                    indirect_edges=indirect_edges,
                )
                if project_dir
                else _empty_asset_catalog(project_dir)
            )
        return cls(
            project=project,
            lineage=lineage,
            assets=assets,
            models=models,
            naming_config=naming_config,
            business_domain_config=business_domain_config,
        )
