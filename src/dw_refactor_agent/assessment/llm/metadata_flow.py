"""Shared metadata flow planning and inspection orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from typing_extensions import Literal

from dw_refactor_agent.assessment.llm.context_builder import (
    TableContext,
    build_contexts,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspector,
    TableInspectResult,
)
from dw_refactor_agent.config import load_model_metadata

METRIC_LAYERS = {"DWD", "DWS"}
# ODS/ADS are fixed asset boundaries and should not enter table_inspector.
WRITABLE_METADATA_LAYERS = {"DWD", "DWS", "DIM"}


@dataclass(frozen=True)
class MetadataCatalogPlan:
    ensure_skeleton: bool = False
    merge_llm_discoveries: bool = False
    write_business_assignments: bool = False
    overwrite_discovered_catalog: bool = False


@dataclass(frozen=True)
class MetadataWriteTargets:
    model_paths: Dict[str, Path] = field(default_factory=dict)
    replace_existing_models: bool = False
    planned_deleted_model_files: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MetadataFlowPlan:
    mode: Literal["refresh", "generate"]
    prior_source: Literal["declared", "direct_rule"]
    write_scope: str
    base_model_metadata: Dict[str, Dict[str, Any]]
    metric_groups: Dict[str, Dict[str, List[str]]]
    write_targets: MetadataWriteTargets
    resolution_policy: LayerResolutionPolicy
    catalog_plan: MetadataCatalogPlan


def catalog_plan_for_refresh(llm: bool) -> MetadataCatalogPlan:
    return MetadataCatalogPlan(
        ensure_skeleton=llm,
        merge_llm_discoveries=llm,
        write_business_assignments=True,
        overwrite_discovered_catalog=False,
    )


def catalog_plan_for_generate(llm: bool) -> MetadataCatalogPlan:
    return MetadataCatalogPlan(
        ensure_skeleton=True,
        merge_llm_discoveries=llm,
        write_business_assignments=True,
        overwrite_discovered_catalog=False,
    )


def catalog_plan_for_discovery(overwrite: bool) -> MetadataCatalogPlan:
    return MetadataCatalogPlan(
        ensure_skeleton=False,
        merge_llm_discoveries=True,
        write_business_assignments=True,
        overwrite_discovered_catalog=overwrite,
    )


@dataclass(frozen=True)
class InspectionResultBundle:
    contexts: List[TableContext]
    metric_contexts: List[TableContext]
    dwd_contexts: List[TableContext]
    dws_contexts: List[TableContext]
    metadata_only_contexts: List[TableContext]
    dwd_results: List[TableInspectResult]
    dws_results: List[TableInspectResult]
    metadata_only_results: List[TableInspectResult]
    results: List[TableInspectResult]


MetricGroupBuilder = Callable[
    [TableInspectResult],
    Dict[str, List[Any]],
]
ResultEnricher = Callable[
    [List[TableInspectResult], Dict[str, TableContext]],
    None,
]


def build_refresh_plan(project: str, *, write_scope: str) -> MetadataFlowPlan:
    return MetadataFlowPlan(
        mode="refresh",
        prior_source="declared",
        write_scope=write_scope,
        base_model_metadata=load_model_metadata(project),
        metric_groups={},
        write_targets=MetadataWriteTargets(),
        resolution_policy=LayerResolutionPolicy(mode="refresh"),
        catalog_plan=catalog_plan_for_refresh(llm=False),
    )


def build_generate_plan(
    project: str,
    *,
    write_scope: str,
    base_model_metadata: Dict[str, Dict[str, Any]],
    model_paths: Dict[str, Path],
    planned_deleted_model_files: List[str],
    replace_existing_models: bool,
) -> MetadataFlowPlan:
    return MetadataFlowPlan(
        mode="generate",
        prior_source="direct_rule",
        write_scope=write_scope,
        base_model_metadata=dict(base_model_metadata),
        metric_groups={},
        write_targets=MetadataWriteTargets(
            model_paths=dict(model_paths),
            replace_existing_models=replace_existing_models,
            planned_deleted_model_files=tuple(planned_deleted_model_files),
        ),
        resolution_policy=LayerResolutionPolicy(
            mode="generate",
            candidate_layers=("DWD", "DWS", "DIM"),
            fallback_source="direct_rule",
        ),
        catalog_plan=catalog_plan_for_generate(llm=False),
    )


def run_inspection_pipeline(
    project: str,
    lineage_data: Dict[str, Any],
    inspector: TableInspector,
    *,
    metric_group_builder: MetricGroupBuilder,
    result_enricher: ResultEnricher,
    base_model_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    metric_groups: Optional[Dict[str, Dict[str, List[str]]]] = None,
) -> InspectionResultBundle:
    contexts = build_contexts(
        project,
        lineage_data,
        layers=WRITABLE_METADATA_LAYERS,
        model_metadata=base_model_metadata,
        metric_groups=metric_groups,
    )
    metric_contexts = [ctx for ctx in contexts if ctx.layer in METRIC_LAYERS]
    dwd_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWD"]
    dws_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWS"]
    metadata_only_contexts = [
        ctx for ctx in contexts if ctx.layer not in METRIC_LAYERS
    ]

    dwd_results = inspector.inspect_batch(dwd_contexts)
    detected_groups = {
        result.table_name: metric_group_builder(result)
        for result in dwd_results
        if result.status != "blocked"
    }
    _inject_upstream_metric_groups(dws_contexts, detected_groups)
    dws_results = inspector.inspect_batch(dws_contexts)
    metadata_only_results = inspector.inspect_batch(metadata_only_contexts)
    results = dwd_results + dws_results + metadata_only_results
    contexts_by_name = {ctx.table_name: ctx for ctx in contexts}
    result_enricher(results, contexts_by_name)

    return InspectionResultBundle(
        contexts=contexts,
        metric_contexts=metric_contexts,
        dwd_contexts=dwd_contexts,
        dws_contexts=dws_contexts,
        metadata_only_contexts=metadata_only_contexts,
        dwd_results=dwd_results,
        dws_results=dws_results,
        metadata_only_results=metadata_only_results,
        results=results,
    )


def _inject_upstream_metric_groups(
    contexts: List[TableContext],
    detected_groups: Dict[str, Dict[str, List[Any]]],
) -> None:
    """Inject metrics found earlier in the run into downstream contexts."""
    for ctx in contexts:
        upstream_metric_groups = dict(ctx.upstream_metric_groups)
        for upstream_table in ctx.upstream_tables:
            groups = detected_groups.get(upstream_table)
            if groups and any(groups.values()):
                upstream_metric_groups[upstream_table] = groups
        ctx.upstream_metric_groups = upstream_metric_groups
