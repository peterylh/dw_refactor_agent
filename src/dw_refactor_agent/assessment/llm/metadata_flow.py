"""Shared metadata flow planning and inspection orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import sqlglot
from sqlglot import exp
from typing_extensions import Literal

from dw_refactor_agent.assessment.llm.context_builder import (
    TableContext,
    build_contexts,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    METRIC_PROPAGATION_ERROR_KEY,
    TableInspector,
    TableInspectResult,
    validate_inspection_result,
)
from dw_refactor_agent.config import load_model_metadata

METRIC_LAYERS = {"DWD", "DWS"}
# ODS/ADS are fixed asset boundaries and should not enter table_inspector.
WRITABLE_METADATA_LAYERS = {"DWD", "DWS", "DIM"}
BUSINESS_PROCESS_VALIDATION_KEYS = {
    "business_process_missing",
    "business_process_ambiguous",
}
STRUCTURAL_VALIDATION_KEYS = BUSINESS_PROCESS_VALIDATION_KEYS | {
    "missing_primary_entities",
    "bridge_entities_invalid",
    "bridge_grain_invalid",
    "bridge_semantics_invalid",
    "composite_process_invalid",
    "duplicate_entity_codes",
    "entity_key_missing",
    "grain_entity_unknown",
    "grain_column_missing",
    "dimension_primary_entity_invalid",
}


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
ResultLayerResolver = Callable[[TableContext, TableInspectResult], str]
LocalResultResolver = Callable[[TableInspectResult], TableInspectResult]


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
    if replace_existing_models is not True:
        raise ValueError(
            "generate 冷启动必须替换现有 models，不能读取旧 model YAML"
        )
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
    use_model_metadata_asset_roles: bool = False,
    metric_result_is_eligible: Optional[MetricResultEligibility] = None,
    result_layer_resolver: Optional[ResultLayerResolver] = None,
    asset_content: Optional[Dict[str, Dict[str, str]]] = None,
    business_semantics_catalog: Optional[Dict[str, Any]] = None,
    local_result_resolver: Optional[LocalResultResolver] = None,
) -> InspectionResultBundle:
    contexts = build_contexts(
        project,
        lineage_data,
        layers=WRITABLE_METADATA_LAYERS,
        model_metadata=base_model_metadata,
        metric_groups=metric_groups,
        expose_layer_hints=expose_layer_hints,
        use_model_metadata_asset_roles=use_model_metadata_asset_roles,
        asset_content=asset_content,
        business_semantics_catalog=business_semantics_catalog,
    )
    # Classify every writable model before building metric phases. In a cold
    # start all mid-layer models can carry the same direct-rule prior, so the
    # declared context layer cannot be used to decide which tables receive
    # newly discovered upstream metric groups.
    initial_results = inspector.inspect_batch(contexts)
    if local_result_resolver is not None:
        initial_results = [
            local_result_resolver(result) for result in initial_results
        ]
    final_pairs = list(zip(contexts, initial_results))
    if _promote_upstream_metrics_from_consumer_evidence(
        final_pairs,
        result_layer_resolver=result_layer_resolver,
    ):
        _revalidate_pairs(final_pairs, inspector)
    propagation_converged = False
    max_propagation_passes = max(2, len(final_pairs) + 1)
    for _pass_index in range(max_propagation_passes):
        detected_groups = _detected_metric_groups(
            final_pairs,
            metric_group_builder=metric_group_builder,
            metric_result_is_eligible=metric_result_is_eligible,
            result_layer_resolver=result_layer_resolver,
        )
        contexts_to_reinspect = _contexts_with_new_metric_groups(
            final_pairs,
            detected_groups,
        )
        if not contexts_to_reinspect:
            propagation_converged = True
            break
        reinspection_results = inspector.inspect_batch(contexts_to_reinspect)
        if local_result_resolver is not None:
            reinspection_results = [
                local_result_resolver(result)
                for result in reinspection_results
            ]
        final_pairs = _merge_reinspection_results(
            final_pairs,
            contexts_to_reinspect,
            reinspection_results,
            validate_publication_contract=bool(
                getattr(inspector, "validate_publication_contract", False)
            ),
        )
        if _promote_upstream_metrics_from_consumer_evidence(
            final_pairs,
            result_layer_resolver=result_layer_resolver,
        ):
            _revalidate_pairs(final_pairs, inspector)
    if not propagation_converged:
        unstable_contexts = _contexts_with_new_metric_groups(
            final_pairs,
            _detected_metric_groups(
                final_pairs,
                metric_group_builder=metric_group_builder,
                metric_result_is_eligible=metric_result_is_eligible,
                result_layer_resolver=result_layer_resolver,
            ),
        )
        if not unstable_contexts:
            propagation_converged = True
        else:
            _mark_metric_propagation_not_converged(
                final_pairs,
                unstable_contexts,
                max_propagation_passes,
            )
    dwd_pairs = [
        (ctx, result)
        for ctx, result in final_pairs
        if _result_layer(ctx, result, result_layer_resolver) == "DWD"
    ]
    dws_pairs = [
        (ctx, result)
        for ctx, result in final_pairs
        if _result_layer(ctx, result, result_layer_resolver) == "DWS"
    ]
    metadata_only_pairs = [
        (ctx, result)
        for ctx, result in final_pairs
        if _result_layer(ctx, result, result_layer_resolver)
        not in METRIC_LAYERS
    ]
    dwd_contexts = [ctx for ctx, _ in dwd_pairs]
    dws_contexts = [ctx for ctx, _ in dws_pairs]
    metadata_only_contexts = [ctx for ctx, _ in metadata_only_pairs]
    metric_contexts = dwd_contexts + dws_contexts
    dwd_results = [result for _, result in dwd_pairs]
    dws_results = [result for _, result in dws_pairs]
    metadata_only_results = [result for _, result in metadata_only_pairs]
    results = dwd_results + dws_results + metadata_only_results
    contexts_by_name = {ctx.table_name: ctx for ctx in contexts}
    result_enricher(results, contexts_by_name)
    _revalidate_pairs(
        final_pairs,
        inspector,
        only_non_resumable=True,
    )
    persist_finalized = getattr(
        inspector,
        "persist_finalized_results",
        None,
    )
    if callable(persist_finalized):
        persist_finalized(final_pairs)

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


def _detected_metric_groups(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    *,
    metric_group_builder: MetricGroupBuilder,
    metric_result_is_eligible: Optional[MetricResultEligibility],
    result_layer_resolver: Optional[ResultLayerResolver],
) -> Dict[str, Dict[str, List[Any]]]:
    detected_groups: Dict[str, Dict[str, List[Any]]] = {}
    for ctx, result in pairs:
        if _result_layer(ctx, result, result_layer_resolver) != "DWD":
            continue
        is_eligible = (
            metric_result_is_eligible(result)
            if metric_result_is_eligible is not None
            else result.status != "blocked"
        )
        if not is_eligible:
            continue
        table_identity = ctx.table_identity or result.table_name
        detected_groups[table_identity] = metric_group_builder(result)
    return detected_groups


def _contexts_with_new_metric_groups(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    detected_groups: Dict[str, Dict[str, List[Any]]],
) -> List[TableContext]:
    contexts = []
    for ctx, _result in pairs:
        previous_groups = dict(ctx.upstream_metric_groups)
        _inject_upstream_metric_groups([ctx], detected_groups)
        if ctx.upstream_metric_groups != previous_groups:
            contexts.append(ctx)
    return contexts


def _revalidate_pairs(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    inspector: TableInspector,
    *,
    only_non_resumable: bool = False,
) -> None:
    validate_publication_contract = bool(
        getattr(inspector, "validate_publication_contract", False)
    )
    for ctx, result in pairs:
        if result.confidence <= 0 or (
            only_non_resumable and result.resume_eligible
        ):
            continue
        validate_inspection_result(
            result,
            ctx,
            validate_publication_contract=validate_publication_contract,
        )


def _mark_metric_propagation_not_converged(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    contexts: List[TableContext],
    max_passes: int,
) -> None:
    unstable_ids = {id(ctx) for ctx in contexts}
    message = (
        "upstream metric context did not converge after "
        f"{max_passes} propagation passes"
    )
    for ctx, result in pairs:
        if id(ctx) not in unstable_ids:
            continue
        validation = dict(result.validation or {})
        issues = list(validation.get(METRIC_PROPAGATION_ERROR_KEY) or [])
        if message not in issues:
            issues.append(message)
        validation[METRIC_PROPAGATION_ERROR_KEY] = issues
        result.validation = validation


def _merge_reinspection_results(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    contexts: List[TableContext],
    reinspection_results: List[TableInspectResult],
    *,
    validate_publication_contract: bool,
) -> List[Tuple[TableContext, TableInspectResult]]:
    by_context_id = {id(ctx): result for ctx, result in pairs}
    for ctx, revised in zip(contexts, reinspection_results):
        initial = by_context_id[id(ctx)]
        by_context_id[id(ctx)] = _merge_metric_reinspection(
            initial,
            revised,
            ctx,
            validate_publication_contract=validate_publication_contract,
        )
    return [(ctx, by_context_id[id(ctx)]) for ctx, _result in pairs]


def _merge_metric_reinspection(
    initial: TableInspectResult,
    revised: TableInspectResult,
    ctx: TableContext,
    *,
    validate_publication_contract: bool,
) -> TableInspectResult:
    first_attempt_layer = (
        initial.first_attempt_inferred_layer or initial.inferred_layer
    )
    if revised.confidence <= 0:
        validation = dict(initial.validation or {})
        issues = list(
            validation.get(METRIC_CONTEXT_REINSPECTION_ERROR_KEY) or []
        )
        message = "upstream metric context reinspection failed"
        if message not in issues:
            issues.append(message)
        validation[METRIC_CONTEXT_REINSPECTION_ERROR_KEY] = issues
        return replace(
            initial,
            validation=validation,
            first_attempt_inferred_layer=first_attempt_layer,
        )

    revised = _repair_metric_layer_validation(revised)
    same_table_type = (
        str(initial.table_type or "").casefold()
        == str(revised.table_type or "").casefold()
    )
    initial_has_structural_errors = any(
        initial.validation.get(key) for key in STRUCTURAL_VALIDATION_KEYS
    )
    revised_has_structural_errors = any(
        revised.validation.get(key) for key in STRUCTURAL_VALIDATION_KEYS
    )
    preserve_structure = (
        same_table_type
        and not initial_has_structural_errors
        and not revised_has_structural_errors
    )
    business_process = (
        initial.business_process
        if preserve_structure and initial.business_process
        else revised.business_process
    )
    revised_process_is_ambiguous = any(
        revised.validation.get(key) for key in BUSINESS_PROCESS_VALIDATION_KEYS
    )
    columns = (
        {
            group: [
                dict(item) if isinstance(item, dict) else item
                for item in items or []
            ]
            for group, items in (revised.columns or {}).items()
        }
        if revised_process_is_ambiguous
        else _columns_with_business_process(
            revised.columns,
            business_process=business_process,
        )
    )
    merged = replace(
        revised,
        business_process=business_process,
        columns=columns,
        entities=(
            list(initial.entities)
            if preserve_structure and initial.entities
            else list(revised.entities)
        ),
        entity={},
        related_entities=[],
        grain=(
            dict(initial.grain)
            if preserve_structure and initial.grain
            else dict(revised.grain)
        ),
        dimension_role=(
            initial.dimension_role
            if preserve_structure and initial.dimension_role
            else revised.dimension_role
        ),
        dimension_content_type=(
            initial.dimension_content_type
            if preserve_structure and initial.dimension_content_type
            else revised.dimension_content_type
        ),
        first_attempt_inferred_layer=first_attempt_layer,
    )
    return validate_inspection_result(
        merged,
        ctx,
        validate_publication_contract=validate_publication_contract,
    )


def _columns_with_business_process(
    columns: Dict[str, List[Dict[str, Any]]],
    *,
    business_process: str,
) -> Dict[str, List[Dict[str, Any]]]:
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for group_name, raw_items in (columns or {}).items():
        items = [
            dict(item) if isinstance(item, dict) else item
            for item in raw_items or []
        ]
        if business_process and group_name in {
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        }:
            for item in items:
                if isinstance(item, dict):
                    item["business_process"] = business_process
        normalized[group_name] = items
    return normalized


def _repair_metric_layer_validation(
    result: TableInspectResult,
) -> TableInspectResult:
    validation = dict(result.validation or {})
    if str(result.table_type or "").casefold() == "fact" and validation.get(
        "inconsistent_upstream_metric_layers"
    ):
        return replace(
            result,
            inferred_layer="DWS",
        )
    return result


def _is_key_like_column(column_name: str) -> bool:
    canonical = _canonical_column_name(column_name)
    return canonical in {
        "id",
        "key",
        "code",
        "number",
        "no",
    } or canonical.endswith(("_id", "_key", "_code", "_number", "_no"))


def _aggregate_metric_sources(
    sql_text: str,
    *,
    consumer_identity: str = "",
) -> Dict[str, set[str]]:
    if not str(sql_text or "").strip():
        return {}
    try:
        statements = sqlglot.parse(sql_text, read="doris")
    except (sqlglot.errors.SqlglotError, ValueError):
        return {}
    insert_queries = []
    standalone_queries = []
    for statement in statements:
        if isinstance(statement, exp.Insert):
            query = statement.args.get("expression") or statement.args.get(
                "source"
            )
            target_identity = _insert_target_identity(statement)
            if consumer_identity and not _table_identities_match(
                target_identity,
                consumer_identity,
            ):
                continue
            insert_queries.append(query)
        elif isinstance(statement, exp.Select):
            standalone_queries.append(statement)
    has_insert = any(
        isinstance(statement, exp.Insert) for statement in statements
    )
    queries = (
        insert_queries
        if has_insert
        else standalone_queries
        if len(standalone_queries) == 1
        else []
    )
    sources_by_output: Dict[str, set[str]] = {}
    for query in queries:
        while isinstance(query, (exp.Subquery, exp.Paren)):
            query = query.this
        if not isinstance(query, exp.Select):
            continue
        for projection in query.expressions:
            output_name = _canonical_column_name(projection.alias_or_name)
            expression = (
                projection.this
                if isinstance(projection, exp.Alias)
                else projection
            )
            if (
                not output_name
                or not isinstance(expression, (exp.Sum, exp.Avg))
                or not isinstance(expression.this, exp.Column)
            ):
                continue
            source_name = _canonical_column_name(expression.this.name)
            if source_name and not _is_key_like_column(source_name):
                sources_by_output.setdefault(output_name, set()).add(
                    source_name
                )
    return sources_by_output


def _insert_target_identity(statement: exp.Insert) -> str:
    target = statement.this
    if isinstance(target, exp.Schema):
        target = target.this
    if not isinstance(target, exp.Table):
        return ""
    return _canonical_table_identity(
        ".".join(
            part
            for part in (
                str(target.catalog or "").strip(),
                str(target.db or "").strip(),
                str(target.name or "").strip(),
            )
            if part
        )
    )


def _has_direct_metric_lineage(
    consumer_ctx: TableContext,
    *,
    target_metric: str,
    source_pair: Tuple[TableContext, TableInspectResult],
    source_metric: str,
) -> bool:
    target_key = _canonical_column_name(target_metric)
    source_key = _canonical_column_name(source_metric)
    consumer_identity = _canonical_table_identity(
        consumer_ctx.table_identity or consumer_ctx.table_name
    )
    source_identity = _pair_identity(source_pair)
    for edge in consumer_ctx.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_identifier(
            edge.get("source")
        )
        target_table, target_column = _split_column_identifier(
            edge.get("target")
        )
        if target_column != target_key or source_column != source_key:
            continue
        if target_table and not _table_identities_match(
            target_table,
            consumer_identity,
        ):
            continue
        if source_table and _table_identities_match(
            source_table,
            source_identity,
        ):
            return True
    return False


def _promote_upstream_metrics_from_consumer_evidence(
    pairs: List[Tuple[TableContext, TableInspectResult]],
    *,
    result_layer_resolver: Optional[ResultLayerResolver],
) -> bool:
    promoted = False
    for consumer_ctx, consumer_result in pairs:
        if str(consumer_result.table_type or "").casefold() != "fact":
            continue
        aggregate_sources = _aggregate_metric_sources(
            consumer_ctx.etl_sql,
            consumer_identity=(
                consumer_ctx.table_identity or consumer_ctx.table_name
            ),
        )
        if not aggregate_sources:
            continue
        for metric in consumer_result.derived_metrics:
            metric_name = _canonical_column_name(metric.get("name"))
            base_metric = _canonical_column_name(metric.get("base_metric"))
            if (
                not metric_name
                or not base_metric
                or base_metric not in aggregate_sources.get(metric_name, set())
            ):
                continue
            source_pair = _metric_source_pair(
                consumer_ctx,
                pairs,
                base_table=metric.get("base_metric_table"),
                base_metric=base_metric,
            )
            if source_pair is None:
                continue
            source_ctx, source_result = source_pair
            if not _has_direct_metric_lineage(
                consumer_ctx,
                target_metric=metric_name,
                source_pair=source_pair,
                source_metric=base_metric,
            ):
                continue
            if (
                _result_layer(
                    source_ctx,
                    source_result,
                    result_layer_resolver,
                )
                != "DWD"
                or not source_result.is_fact_table
            ):
                continue
            promoted = (
                _promote_result_metric(
                    source_result,
                    base_metric,
                    consumer_table=consumer_result.table_name,
                )
                or promoted
            )
    return promoted


def _metric_source_pair(
    consumer_ctx: TableContext,
    pairs: List[Tuple[TableContext, TableInspectResult]],
    *,
    base_table: Any,
    base_metric: str,
) -> Optional[Tuple[TableContext, TableInspectResult]]:
    upstream_pairs = [
        pair
        for pair in pairs
        if _pair_matches_upstream(pair, consumer_ctx.upstream_tables)
    ]
    base_identity = _canonical_table_identity(base_table)
    if base_identity:
        matched = _matching_pairs(base_identity, upstream_pairs)
        return matched[0] if len(matched) == 1 else None
    candidates = [
        pair
        for pair in upstream_pairs
        if _result_has_column(pair[1], base_metric)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _pair_matches_upstream(
    pair: Tuple[TableContext, TableInspectResult],
    upstream_tables: List[str],
) -> bool:
    pair_identity = _pair_identity(pair)
    upstream_identities = {
        _canonical_table_identity(table_name)
        for table_name in upstream_tables
        if _canonical_table_identity(table_name)
    }
    matches = [
        identity
        for identity in upstream_identities
        if _table_identities_match(identity, pair_identity)
    ]
    return len(matches) == 1


def _matching_pairs(
    table_identity: str,
    pairs: List[Tuple[TableContext, TableInspectResult]],
) -> List[Tuple[TableContext, TableInspectResult]]:
    exact = [pair for pair in pairs if _pair_identity(pair) == table_identity]
    if exact:
        return exact
    short_name = _canonical_short_table_name(table_identity)
    short_matches = [
        pair
        for pair in pairs
        if _canonical_short_table_name(_pair_identity(pair)) == short_name
    ]
    if len(short_matches) != 1:
        return []
    pair_identity = _pair_identity(short_matches[0])
    if "." in table_identity and "." in pair_identity:
        return []
    return short_matches


def _pair_identity(
    pair: Tuple[TableContext, TableInspectResult],
) -> str:
    ctx, result = pair
    return _canonical_table_identity(
        ctx.table_identity or ctx.table_name or result.table_name
    )


def _split_column_identifier(identifier: Any) -> Tuple[str, str]:
    text = str(identifier or "").strip().replace("`", "").replace('"', "")
    if "." not in text:
        return "", _canonical_column_name(text)
    table_name, column_name = text.rsplit(".", 1)
    return (
        _canonical_table_identity(table_name),
        _canonical_column_name(column_name),
    )


def _table_identities_match(left: str, right: str) -> bool:
    left_identity = _canonical_table_identity(left)
    right_identity = _canonical_table_identity(right)
    if not left_identity or not right_identity:
        return False
    if "." in left_identity and "." in right_identity:
        return left_identity == right_identity
    return _canonical_short_table_name(
        left_identity
    ) == _canonical_short_table_name(right_identity)


def _result_has_column(
    result: TableInspectResult,
    column_name: str,
) -> bool:
    wanted = _canonical_column_name(column_name)
    return any(
        _canonical_column_name(item.get("name")) == wanted
        for items in (result.columns or {}).values()
        for item in items or []
        if isinstance(item, dict)
    )


def _promote_result_metric(
    result: TableInspectResult,
    column_name: str,
    *,
    consumer_table: str,
) -> bool:
    wanted = _canonical_column_name(column_name)
    if any(
        _canonical_column_name(item.get("name")) == wanted
        for item in result.atomic_metrics
        if isinstance(item, dict)
    ):
        return False
    for group_name in ("dimensions", "others"):
        items = result.columns.get(group_name) or []
        for index, item in enumerate(items):
            if (
                not isinstance(item, dict)
                or _canonical_column_name(item.get("name")) != wanted
            ):
                continue
            promoted = dict(item)
            if result.business_process:
                promoted["business_process"] = result.business_process
            promoted["inference_source"] = "consumer_aggregate_evidence"
            promoted["consumer_table"] = consumer_table
            result.columns.setdefault("atomic_metrics", []).append(promoted)
            result.columns[group_name] = items[:index] + items[index + 1 :]
            result.resume_eligible = False
            return True
    return False


def _canonical_column_name(value: Any) -> str:
    return (
        str(value or "").strip().replace("`", "").replace('"', "").casefold()
    )


def _result_layer(
    ctx: TableContext,
    result: TableInspectResult,
    resolver: Optional[ResultLayerResolver],
) -> str:
    if resolver is not None:
        resolved_layer = str(resolver(ctx, result) or "").strip().upper()
        if resolved_layer in WRITABLE_METADATA_LAYERS:
            return resolved_layer
    inferred_layer = str(result.inferred_layer or "").strip().upper()
    if inferred_layer in WRITABLE_METADATA_LAYERS:
        return inferred_layer
    return str(ctx.layer or "").strip().upper()


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
