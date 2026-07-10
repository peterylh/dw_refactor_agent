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
MetricResultEligibility = Callable[[TableInspectResult], bool]


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
    expose_layer_hints: bool = True,
    metric_result_is_eligible: Optional[MetricResultEligibility] = None,
) -> InspectionResultBundle:
    contexts = build_contexts(
        project,
        lineage_data,
        layers=WRITABLE_METADATA_LAYERS,
        model_metadata=base_model_metadata,
        metric_groups=metric_groups,
        expose_layer_hints=expose_layer_hints,
    )
    metric_contexts = [ctx for ctx in contexts if ctx.layer in METRIC_LAYERS]
    dwd_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWD"]
    dws_contexts = [ctx for ctx in metric_contexts if ctx.layer == "DWS"]
    metadata_only_contexts = [
        ctx for ctx in contexts if ctx.layer not in METRIC_LAYERS
    ]

    dwd_results = inspector.inspect_batch(dwd_contexts)
    detected_groups = {}
    for ctx, result in zip(dwd_contexts, dwd_results):
        is_eligible = (
            metric_result_is_eligible(result)
            if metric_result_is_eligible is not None
            else result.status != "blocked"
        )
        if not is_eligible:
            continue
        table_identity = ctx.table_identity or result.table_name
        detected_groups[table_identity] = metric_group_builder(result)
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
    detected_by_identity = {
        _canonical_table_identity(table_name): groups
        for table_name, groups in detected_groups.items()
    }
    detected_identities_by_short: Dict[str, List[str]] = {}
    for identity in detected_by_identity:
        detected_identities_by_short.setdefault(
            _canonical_short_table_name(identity), []
        ).append(identity)
    for ctx in contexts:
        upstream_metric_groups = dict(ctx.upstream_metric_groups)
        upstream_identities_by_short: Dict[str, List[str]] = {}
        for upstream_table in ctx.upstream_tables:
            upstream_identities_by_short.setdefault(
                _canonical_short_table_name(upstream_table), []
            ).append(_canonical_table_identity(upstream_table))
        for upstream_table in ctx.upstream_tables:
            upstream_identity = _canonical_table_identity(upstream_table)
            groups = detected_by_identity.get(upstream_identity)
            if groups is None:
                short_name = _canonical_short_table_name(upstream_table)
                upstream_matches = set(
                    upstream_identities_by_short.get(short_name) or []
                )
                detected_matches = set(
                    detected_identities_by_short.get(short_name) or []
                )
                if len(upstream_matches) == len(detected_matches) == 1:
                    detected_identity = next(iter(detected_matches))
                    both_qualified_but_different = bool(
                        "." in upstream_identity
                        and "." in detected_identity
                        and upstream_identity != detected_identity
                    )
                    if not both_qualified_but_different:
                        groups = detected_by_identity[detected_identity]
            if groups and any(groups.values()):
                upstream_metric_groups[upstream_table] = groups
        ctx.upstream_metric_groups = upstream_metric_groups


def _canonical_table_identity(table_name: str) -> str:
    text = str(table_name or "").strip().replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _canonical_short_table_name(table_name: str) -> str:
    return _canonical_table_identity(table_name).split(".")[-1]
