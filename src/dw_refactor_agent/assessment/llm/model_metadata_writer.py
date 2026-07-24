#!/usr/bin/env python3
"""
LLM 表巡检与模型元数据回写工具。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块、维度表 entity/related_entities、DWS grain 以及
DWD/DWS 表中的指标字段回写到 models/{table}.yaml，并把 DWD 事实表的
非原子指标输出为违规项。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

_src_root = Path(__file__).resolve().parents[3]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.llm.context_builder import (
    InspectionContextSetError,
)
from dw_refactor_agent.assessment.llm.generation_candidate_resolver import (
    prepare_inspection_for_propagation,
    resolve_generation_candidate,
)
from dw_refactor_agent.assessment.llm.generation_contract import (
    validate_generate_candidate,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionPolicy,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    MetadataFlowPlan,
    MetadataWriteTargets,
    build_generate_plan,
    build_refresh_plan,
    catalog_plan_for_generate,
    catalog_plan_for_refresh,
    run_inspection_pipeline,
)
from dw_refactor_agent.assessment.llm.model_generation_manifest import (
    GenerateAssetManifest,
    GenerateAssetPreflight,
    build_generate_asset_preflight,
    revalidate_generate_asset_manifest,
)
from dw_refactor_agent.assessment.llm.model_metadata_checkpoint import (
    GenerateModelCheckpoint,
)
from dw_refactor_agent.assessment.llm.model_metadata_publication import (
    MetadataPublicationError,
    MetadataPublicationOutcome,
    metadata_publication_lock,
    read_consistent_metadata_snapshot,
    transactional_metadata_publication,
)
from dw_refactor_agent.assessment.llm.publication_transitions import (
    materialize_refresh_models,
    plan_inspection_run_transition,
    plan_no_llm_generation_decisions,
    plan_publication_transition,
    plan_refresh_transitions,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    DEFAULT_MIN_CACHEABLE_CONFIDENCE,
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspector,
    TableInspectResult,
    normalize_chat_completions_url,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    result_to_dict as inspect_result_to_dict,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    catalog_mapping_for_model,
    load_business_semantics_catalog,
    write_initial_business_semantics_catalog,
)
from dw_refactor_agent.assessment.semantic_models import (
    AssessmentModelSemantics,
)
from dw_refactor_agent.config import (
    MODEL_SECTIONS,
    PROJECT_CONFIG,
    PROJECT_ROOT,  # noqa: F401 - compatibility for callers overriding project roots
    TEXT_ENCODING,
    UnavailableModelSection,
    assess_cache_path,
    business_semantics_paths,
    load_model_metadata,
    model_metadata_result_path,
)
from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    short_table_name,
)
from dw_refactor_agent.lineage.table_graph import load_lineage_data

_DEFAULT_PROJECT_ROOT = PROJECT_ROOT

WRITE_SCOPES = {"all", "table", "metrics", "grain", "business"}
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
TABLE_METADATA_BLOCKING_VALIDATION_KEYS = {
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    "inconsistent_layer_table_types",
    "inconsistent_layer_sql",
    "inconsistent_upstream_metric_layers",
}
DDL_NON_COLUMN_PREFIXES = {
    "AGGREGATE",
    "CREATE",
    "DISTRIBUTED",
    "DUPLICATE",
    "ENGINE",
    "KEY",
    "PARTITION",
    "PARTITIONED",
    "PRIMARY",
    "PROPERTIES",
    "UNIQUE",
}

_REFRESH_SCOPE_SECTIONS = {
    "all": MODEL_SECTIONS,
    "table": ("classification", "business_semantics"),
    "metrics": ("metrics",),
    "grain": ("entities", "grain"),
    "business": ("business_semantics",),
}


def _unique_model_name(
    models: dict[str, dict[str, Any]], reference: str
) -> str:
    reference_key = identifier_match_key(reference)
    exact = [
        name for name in models if identifier_match_key(name) == reference_key
    ]
    if len(exact) == 1:
        return exact[0]
    short_key = identifier_match_key(short_table_name(reference))
    matches = [
        name
        for name in models
        if identifier_match_key(short_table_name(name)) == short_key
    ]
    if len(matches) != 1:
        raise ValueError(
            f"model identity must resolve uniquely: {reference!r}"
        )
    return matches[0]


from dw_refactor_agent.assessment.llm.model_metadata_catalog import (  # noqa: F401
    _business_processes_from_result,
    _catalog_entry_code,
    _catalog_has_code,
    _catalog_model_payload,
    _existing_catalog_assignment,
    _resolved_results_for_catalog_discovery,
    _semantic_subject_from_result,
    catalog_discovery_model_mapping,
    update_model_yaml_from_catalog,
)
from dw_refactor_agent.assessment.llm.model_metadata_generation import (  # noqa: F401
    GenerateModelMetadataPlan,
    _apply_catalog_assignments_to_generated_models,
    _asset_role_from_generate_asset,
    _candidate_model_publication_targets,
    _catalog_table_assets,
    _empty_catalog_update_report,
    _ensure_metadata_catalog_skeleton,
    _final_model_metadata_with_refinements,
    _generate_asset_role_layer,
    _generate_metadata_catalog_for_plan,
    _generate_model_mapping,
    _generate_model_table_assets,
    _generate_model_update_payload,
    _generated_model_path_for_table,
    _merge_final_update_with_refinement,
    _merge_llm_catalog_discoveries,
    _model_files,
    _model_roots,
    _project_dir,
    _published_catalog_reports,
    _render_generated_catalog_files,
    _resolved_catalog_results_from_inspection_results,
    _resolved_catalog_results_from_llm_result,
    _strip_internal_model_metadata,
    _transactional_publish_files,
    _write_generated_model_metadata,
    plan_generate_model_metadata,
)
from dw_refactor_agent.assessment.llm.model_metadata_updates import (  # noqa: F401
    _aggregation_from_expression,
    _as_string_list,
    _blocked_table_metadata_preserves_contract,
    _build_grain_entity_index,
    _canonical_entities_for_write,
    _canonical_grain_for_write,
    _clean_existing_business_metadata_for_layer,
    _column_comments_from_ddl,
    _dedupe_entities,
    _derived_metric_for_model,
    _derived_metrics_for_model,
    _dimension_warnings_for_resolution,
    _drop_deprecated_execution_config,
    _effective_entities,
    _effective_grain,
    _entity_name_from_comment,
    _existing_business_area_for_write,
    _existing_data_domain_for_write,
    _existing_model_data,
    _extract_existing_metric_groups,
    _extract_existing_metric_names,
    _grain_key_entity_pairs,
    _inspection_resolution_is_eligible,
    _is_time_grain_key,
    _layer_resolution_for_model,
    _mark_resolution_reinspection_required,
    _materialized_for_write,
    _merge_related_entities,
    _metric_names,
    _metric_names_from_raw,
    _metric_result_is_eligible_for_propagation,
    _related_entity_identity,
    _resolution_changes_inspection_contract,
    _table_type_prior_for_model,
    _update_models_for_results,
    _validate_write_scope,
    _violation_count,
    build_dwd_contexts,
    build_inspection_contexts,
    build_metric_contexts,
    business_metadata_for_result,
    discover_related_entities_from_grain,
    enrich_results_with_project_semantics,
    enrich_results_with_related_entities,
    layer_for_model,
    metadata_warnings_for_result,
    metric_groups_for_model,
    metric_names_for_model,
    metric_violations,
    model_path_for_table,
    should_write_grain_metadata,
    should_write_metric_groups,
    should_write_table_metadata,
    update_model_yaml,
    warnings_for_resolution,
    write_model_updates_from_plan,
)


def _new_table_inspector(
    api_key: str,
    *,
    model: str,
    base_url: str | None = None,
    cache_file: Path | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    min_cacheable_confidence: float = DEFAULT_MIN_CACHEABLE_CONFIDENCE,
    resume_cache: dict[str, Any] | None = None,
    validate_publication_contract: bool = False,
    catalog_snapshot_hash: str = "",
    asset_manifest_hash: str = "",
) -> TableInspector:
    kwargs: dict[str, Any] = {
        "model": model,
        "cache_file": cache_file,
        "max_retries": max_retries,
        "parallelism": parallelism,
        "request_timeout": request_timeout,
        "min_cacheable_confidence": min_cacheable_confidence,
        "validate_publication_contract": validate_publication_contract,
        "catalog_snapshot_hash": catalog_snapshot_hash,
        "asset_manifest_hash": asset_manifest_hash,
    }
    if resume_cache:
        kwargs["resume_cache"] = resume_cache
    if base_url:
        kwargs["base_url"] = normalize_chat_completions_url(base_url)
    compatibility_keywords = (
        "resume_cache",
        "base_url",
        "request_timeout",
        "min_cacheable_confidence",
        "validate_publication_contract",
        "catalog_snapshot_hash",
        "asset_manifest_hash",
    )
    while True:
        try:
            return TableInspector(api_key, **kwargs)
        except TypeError as exc:
            message = str(exc)
            removed_keyword = next(
                (
                    name
                    for name in compatibility_keywords
                    if name in kwargs and f"'{name}'" in message
                ),
                None,
            )
            if (
                "unexpected keyword argument" not in message
                or removed_keyword is None
            ):
                raise
            kwargs.pop(removed_keyword)


def _metadata_group_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(
            len(items) if isinstance(items, list) else 1
            for items in value.values()
        )
    return 0


def _model_metadata_summary(
    model_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    views = {
        table_name: AssessmentModelSemantics.from_metadata(metadata)
        for table_name, metadata in model_metadata.items()
    }
    metric_counts = {
        table_name: sum(
            _metadata_group_count((metrics or {}).get(group))
            for group in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            )
        )
        for table_name, view in views.items()
        for metrics in [view.active_payload("metrics")]
    }
    layer_counts: dict[str, int] = {}
    for view in views.values():
        layer = view.layer or (
            "QUARANTINED"
            if "classification" in view.quarantined_sections
            else "MISSING"
        )
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    return {
        "model_count": len(model_metadata),
        "metric_count": sum(metric_counts.values()),
        "metric_table_count": sum(
            1 for count in metric_counts.values() if count
        ),
        "entity_table_count": sum(
            1
            for view in views.values()
            if (view.active_payload("entities") or {}).get("entities")
        ),
        "grain_table_count": sum(
            1
            for view in views.values()
            if (view.active_payload("grain") or {}).get("grain")
        ),
        "layer_counts": dict(sorted(layer_counts.items())),
        "quarantined_model_count": sum(
            1 for view in views.values() if view.quarantined_sections
        ),
    }


def _catalog_metadata_summary(catalog: dict[str, Any]) -> dict[str, int]:
    return {
        "business_process_count": len(catalog.get("business_processes") or []),
        "semantic_subject_count": len(catalog.get("semantic_subjects") or []),
    }


def _preflight_blocked_generate_result(
    project: str,
    *,
    preflight: GenerateAssetPreflight,
    catalog: dict[str, Any],
    catalog_report: dict[str, Any],
    write_scope: str,
    update_catalog: bool,
    replace_existing_models: bool,
    dry_run: bool,
) -> dict[str, Any]:
    published_models = load_model_metadata(project)
    result = {
        "project": project,
        "source": "direct_model_generation",
        "mode": "generate",
        "write_scope": write_scope,
        "update_catalog": update_catalog,
        "replace_existing_models": replace_existing_models,
        "asset_manifest": preflight.manifest.to_dict(),
        "confirmed_catalog_snapshot_hash": (
            preflight.manifest.catalog_snapshot_hash
        ),
        "planned_deleted_model_files": [],
        "deleted_model_files": [],
        "generated_model_count": 0,
        "model_updates": [],
        "model_update_count": 0,
        "model_change_count": 0,
        "llm_result": None,
        "inspection_result": None,
        "candidate_model_summary": _model_metadata_summary({}),
        "published_model_summary": _model_metadata_summary(published_models),
        "candidate_catalog_summary": _catalog_metadata_summary(catalog),
        "confirmed_catalog_summary": _catalog_metadata_summary(catalog),
        "published_catalog_summary": _catalog_metadata_summary(catalog),
        "candidate_models": {},
        "publication": {
            "status": "dry_run" if dry_run else "blocked",
            "candidate_status": "blocked",
            "published": False,
            "complete": False,
            "would_publish_status": "blocked" if dry_run else "",
            "formal_files_state": "unchanged",
            "finalization_status": "not_started",
            "recovery_required": False,
            "recoverable": False,
            "retryable": False,
            "quarantined_table_count": 0,
            "withheld_section_count": 0,
            "reason_count": 0,
            "quarantined_tables": [],
            "hard_block_count": len(preflight.errors),
            "validation": preflight.validation(),
        },
        "checkpoint": {
            "enabled": False,
            "status": "not_started",
        },
        "flow": {
            "mode": "generate",
            "prior_source": "direct_rule",
            "llm_enabled": False,
            "base_model_count": 0,
            "final_model_count": 0,
        },
    }
    result.update(catalog_report)
    result.update(_empty_catalog_update_report())
    return result


def _current_generate_lineage_data(
    manifest: GenerateAssetManifest,
) -> dict[str, Any] | None:
    try:
        return load_lineage_data(manifest.project)
    except FileNotFoundError:
        return None


def _fresh_generate_catalog_snapshot(
    project: str,
    *,
    update_catalog: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import dw_refactor_agent.config as _config

    _config.clear_business_semantics_cache()
    return _generate_metadata_catalog_for_plan(
        project,
        dry_run=True,
        update_catalog=update_catalog,
    )


def run_generate_model_metadata(
    project: str,
    *,
    api_key: str | None = None,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    write_scope: str = "all",
    update_catalog: bool = True,
    replace_existing_models: bool = True,
    require_complete: bool = False,
    show_progress: bool = False,
    expose_layer_hints: bool = True,
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("generate 仅支持 write_scope=all/table/business")

    # Always plan against an in-memory catalog first.  Generate publishes the
    # catalog and models only after the complete candidate passes validation.
    catalog, catalog_report = _fresh_generate_catalog_snapshot(
        project,
        update_catalog=update_catalog,
    )
    preflight = build_generate_asset_preflight(project, catalog)
    if not preflight.passed:
        return _preflight_blocked_generate_result(
            project,
            preflight=preflight,
            catalog=catalog,
            catalog_report=catalog_report,
            write_scope=write_scope,
            update_catalog=update_catalog,
            replace_existing_models=replace_existing_models,
            dry_run=dry_run,
        )
    if api_key:
        try:
            preflight_lineage_data = load_lineage_data(project)
        except FileNotFoundError:
            preflight_lineage_data = None
        if preflight_lineage_data is not None:
            preflight = build_generate_asset_preflight(
                project,
                catalog,
                lineage_data=preflight_lineage_data,
            )
            if not preflight.passed:
                return _preflight_blocked_generate_result(
                    project,
                    preflight=preflight,
                    catalog=catalog,
                    catalog_report=catalog_report,
                    write_scope=write_scope,
                    update_catalog=update_catalog,
                    replace_existing_models=replace_existing_models,
                    dry_run=dry_run,
                )
    catalog = preflight.manifest.catalog_data()
    base_plan = plan_generate_model_metadata(
        project,
        catalog,
        replace_existing_models=replace_existing_models,
        write_scope=write_scope,
        asset_manifest=preflight.manifest,
    )

    generate_plan = build_generate_plan(
        project,
        write_scope=write_scope,
        base_model_metadata=base_plan.model_metadata,
        model_paths=base_plan.model_paths,
        planned_deleted_model_files=base_plan.planned_deleted_model_files,
        replace_existing_models=replace_existing_models,
    )
    checkpoint = None
    if api_key and not dry_run:
        checkpoint = GenerateModelCheckpoint(
            project,
            project_dir=_project_dir(project),
            plan=generate_plan,
            resume_enabled=not no_cache,
            catalog_snapshot_hash=preflight.manifest.catalog_snapshot_hash,
            asset_manifest_hash=preflight.manifest.manifest_hash,
        )
        if show_progress:
            print(f"冷启动检查点目录: {checkpoint.root}", flush=True)
    llm_result: dict[str, Any] | None = None
    final_model_metadata = {
        table_name: dict(metadata)
        for table_name, metadata in generate_plan.base_model_metadata.items()
    }
    catalog_update_report = _empty_catalog_update_report()
    confirmed_catalog = catalog
    resolved_catalog_results: list[TableInspectResult] = []
    if api_key:
        try:
            llm_result = run_metadata_write(
                project,
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_retries=max_retries,
                parallelism=parallelism,
                request_timeout=request_timeout,
                no_cache=no_cache,
                dry_run=True,
                write_scope=write_scope,
                show_progress=show_progress,
                model_metadata=generate_plan.base_model_metadata,
                metric_groups=generate_plan.metric_groups,
                model_paths=generate_plan.write_targets.model_paths,
                resolution_policy=generate_plan.resolution_policy,
                include_model_metadata=True,
                update_catalog=False,
                expose_layer_hints=expose_layer_hints,
                resume_cache=checkpoint.resume_cache() if checkpoint else None,
                result_callback=(
                    checkpoint.write_inspection_result if checkpoint else None
                ),
                inspection_complete_callback=(
                    checkpoint.write_layer_classification_report
                    if checkpoint
                    else None
                ),
                lineage_data=preflight.manifest.lineage_data(),
                asset_content=preflight.manifest.inspection_content(),
                inspection_targets=(preflight.manifest.inspection_target_set),
                business_semantics_catalog=catalog,
                catalog_snapshot_hash=(
                    preflight.manifest.catalog_snapshot_hash
                ),
                asset_manifest_hash=preflight.manifest.manifest_hash,
            )
            final_model_metadata = _final_model_metadata_with_refinements(
                generate_plan.base_model_metadata,
                llm_result,
            )
            resolved_catalog_results = (
                _resolved_catalog_results_from_llm_result(
                    llm_result,
                    model_metadata=generate_plan.base_model_metadata,
                    resolution_policy=generate_plan.resolution_policy,
                )
            )
            final_model_metadata = (
                _apply_catalog_assignments_to_generated_models(
                    project,
                    final_model_metadata,
                    catalog=confirmed_catalog,
                    results=resolved_catalog_results,
                )
            )
            catalog_update_report = _merge_llm_catalog_discoveries(
                project,
                llm_result=llm_result,
                base_catalog=confirmed_catalog,
                model_metadata=generate_plan.base_model_metadata,
                resolution_policy=generate_plan.resolution_policy,
                dry_run=True,
            )
            if checkpoint:
                checkpoint.write_catalog_proposal_audit(catalog_update_report)
        except InspectionContextSetError as exc:
            blocked_preflight = GenerateAssetPreflight(
                manifest=preflight.manifest,
                errors=(
                    {
                        "type": exc.code,
                        "table": exc.table,
                        "message": str(exc),
                    },
                ),
            )
            blocked_result = _preflight_blocked_generate_result(
                project,
                preflight=blocked_preflight,
                catalog=catalog,
                catalog_report=catalog_report,
                write_scope=write_scope,
                update_catalog=update_catalog,
                replace_existing_models=replace_existing_models,
                dry_run=dry_run,
            )
            if checkpoint:
                checkpoint.finish(
                    status="blocked",
                    published=False,
                    validation=blocked_preflight.validation(),
                )
                blocked_result["checkpoint"] = checkpoint.report()
            return blocked_result
        except BaseException:
            if checkpoint:
                checkpoint.close()
            raise

    checkpoint_finalization_error = None
    try:
        publication_validation = validate_generate_candidate(
            final_model_metadata,
            preflight.manifest.validation_assets(),
            llm_result=llm_result,
            catalog=confirmed_catalog,
        )
        pre_resolution_validation = publication_validation
        inspection_transition = plan_inspection_run_transition(
            llm_enabled=llm_result is not None,
            inspection_targets=preflight.manifest.inspection_target_set,
            reports=(llm_result or {}).get("tables") or [],
        )
        local_decisions = (llm_result or {}).get(
            "local_section_decisions"
        ) or []
        if llm_result is None:
            local_decisions = plan_no_llm_generation_decisions(
                preflight.manifest.inspection_target_set,
                final_model_metadata,
            )
        resolved_candidate = resolve_generation_candidate(
            final_model_metadata,
            inspection_reports=(llm_result or {}).get("tables") or [],
            catalog=confirmed_catalog,
            operational_layers={
                asset.short_name: asset.operational_layer
                for asset in preflight.manifest.assets
            },
            expected_tables=[
                asset.short_name for asset in preflight.manifest.assets
            ],
            validation_assets=preflight.manifest.validation_assets(),
            generation_issues=publication_validation.get("issues") or [],
            local_decisions=local_decisions,
            lineage_data=preflight.manifest.lineage_data(),
        )
        effective_model_metadata = resolved_candidate.models
        publication_validation = resolved_candidate.validation
        candidate_status = resolved_candidate.status
        if pre_resolution_validation.get(
            "status"
        ) == "blocked" and not pre_resolution_validation.get("issues"):
            publication_validation = pre_resolution_validation
            candidate_status = "blocked"
        if candidate_status in {"active", "passed"}:
            candidate_status = "complete"
        publication_transition = plan_publication_transition(
            candidate_status=candidate_status,
            inspection_transition=inspection_transition,
            dry_run=dry_run,
            require_complete=require_complete,
        )
        (
            candidate_table_names,
            candidate_declared_names,
            candidate_model_paths,
        ) = _candidate_model_publication_targets(
            project,
            generate_plan,
            effective_model_metadata,
        )
        should_publish = False
        catalog_rendered_files: dict[Path, str] = {}
        catalog_deleted_files: list[Path] = []
        catalog_written_names: list[str] = []
        _strip_internal_model_metadata(llm_result)
        refinement_updates = (llm_result or {}).get("model_updates") or []
        model_updates: list[dict[str, Any]]
        deleted_model_files: list[str]
        publication_outcome = MetadataPublicationOutcome(
            formal_files_state="unchanged",
            finalization_status="not_started",
            recovery_required=False,
        )
        if publication_transition.published:
            with metadata_publication_lock(project):
                current_catalog, _current_catalog_report = (
                    _fresh_generate_catalog_snapshot(
                        project,
                        update_catalog=update_catalog,
                    )
                )
                publication_preflight = revalidate_generate_asset_manifest(
                    preflight.manifest,
                    catalog=current_catalog,
                    candidate_table_names=candidate_table_names,
                    candidate_declared_names=candidate_declared_names,
                    rendered_model_paths=candidate_model_paths,
                    lineage_data=(
                        _current_generate_lineage_data(preflight.manifest)
                        if api_key
                        else None
                    ),
                )
                if not publication_preflight.passed:
                    publication_validation = publication_preflight.validation()
                else:
                    (
                        catalog_rendered_files,
                        catalog_deleted_files,
                        catalog_written_names,
                    ) = _render_generated_catalog_files(
                        project,
                        confirmed_catalog,
                        enabled=update_catalog,
                    )
                    try:
                        (
                            model_updates,
                            deleted_model_files,
                            publication_outcome,
                        ) = _write_generated_model_metadata(
                            project,
                            generate_plan,
                            effective_model_metadata,
                            dry_run=False,
                            delete_existing=replace_existing_models,
                            refinement_updates=refinement_updates,
                            additional_rendered_files=catalog_rendered_files,
                            additional_deleted_files=catalog_deleted_files,
                        )
                    except MetadataPublicationError as exc:
                        publication_outcome = exc.outcome
                        publication_validation = {
                            "status": "blocked",
                            "stage": "transactional_publication",
                            "error_count": 1,
                            "errors": [
                                {
                                    "type": "publication_transaction_failed",
                                    "message": str(exc),
                                    "formal_files_state": (
                                        exc.outcome.formal_files_state
                                    ),
                                    "recovery_required": (
                                        exc.outcome.recovery_required
                                    ),
                                }
                            ],
                            "issues": [],
                            "blocked_tables": [],
                            "reinspection_tables": [],
                        }
                        should_publish = (
                            exc.outcome.formal_files_state == "published"
                        )
                        (
                            model_updates,
                            deleted_model_files,
                            _failed_dry_run_outcome,
                        ) = _write_generated_model_metadata(
                            project,
                            generate_plan,
                            effective_model_metadata,
                            dry_run=True,
                            delete_existing=replace_existing_models,
                            refinement_updates=refinement_updates,
                        )
                    else:
                        should_publish = True
        if not should_publish:
            model_updates, deleted_model_files, _dry_run_outcome = (
                _write_generated_model_metadata(
                    project,
                    generate_plan,
                    effective_model_metadata,
                    dry_run=True,
                    delete_existing=replace_existing_models,
                    refinement_updates=refinement_updates,
                )
            )
        else:
            for update in model_updates:
                update["updated"] = bool(update.get("changed"))
            if (
                publication_outcome.recovery_required
                and replace_existing_models
                and not deleted_model_files
            ):
                deleted_model_files = list(
                    generate_plan.write_targets.planned_deleted_model_files
                )
        publication_blocked = publication_validation["status"] == "blocked"
        if publication_blocked and not should_publish:
            publication_transition = plan_publication_transition(
                candidate_status="blocked",
                inspection_transition=inspection_transition,
                dry_run=dry_run,
                require_complete=require_complete,
            )
        if checkpoint:
            try:
                checkpoint.finish(
                    status=publication_transition.status,
                    published=should_publish,
                    validation=publication_validation,
                )
            except Exception as exc:
                checkpoint.close()
                if not should_publish:
                    raise
                checkpoint_finalization_error = f"{type(exc).__name__}: {exc}"
    except BaseException:
        if checkpoint:
            checkpoint.close()
        raise
    if should_publish:
        catalog_report, catalog_update_report = _published_catalog_reports(
            catalog_report,
            catalog_update_report,
            written_names=catalog_written_names,
        )

    published_model_metadata = (
        effective_model_metadata
        if should_publish
        else load_model_metadata(project)
    )
    published_catalog = confirmed_catalog if should_publish else catalog
    candidate_model_summary = _model_metadata_summary(effective_model_metadata)
    published_model_summary = _model_metadata_summary(published_model_metadata)
    candidate_catalog_summary = _catalog_metadata_summary(confirmed_catalog)
    published_catalog_summary = _catalog_metadata_summary(published_catalog)
    changed_updates = [update for update in model_updates if update["changed"]]
    checkpoint_report = (
        checkpoint.report()
        if checkpoint
        else {
            "enabled": False,
            "status": "disabled",
        }
    )
    if llm_result is not None:
        checkpoint_report["inspection_reuse"] = llm_result.get(
            "inspection_reuse",
            {},
        )
    if checkpoint_finalization_error:
        checkpoint_report.update(
            {
                "status": "finalization_failed",
                "error": checkpoint_finalization_error,
            }
        )
    result = {
        "project": project,
        "source": "direct_model_generation",
        "mode": "generate",
        "write_scope": write_scope,
        "update_catalog": update_catalog,
        "replace_existing_models": replace_existing_models,
        "asset_manifest": preflight.manifest.to_dict(),
        "confirmed_catalog_snapshot_hash": (
            preflight.manifest.catalog_snapshot_hash
        ),
        "planned_deleted_model_files": base_plan.planned_deleted_model_files,
        "deleted_model_files": deleted_model_files,
        "generated_model_count": len(base_plan.model_updates),
        "model_updates": changed_updates,
        "model_update_count": len(
            [update for update in changed_updates if update.get("updated")]
        ),
        "model_change_count": len(changed_updates),
        "llm_result": llm_result,
        "inspection_result": llm_result,
        "candidate_model_summary": candidate_model_summary,
        "published_model_summary": published_model_summary,
        "candidate_catalog_summary": candidate_catalog_summary,
        "confirmed_catalog_summary": _catalog_metadata_summary(
            confirmed_catalog
        ),
        "published_catalog_summary": published_catalog_summary,
        "candidate_resolution": (
            resolved_candidate.report()
            if resolved_candidate is not None
            else {
                "status": "not_run",
                "complete": True,
                "fixed_point_iterations": 0,
                "quarantined_table_count": 0,
                "quarantined_tables": [],
                "hard_blocked_table_count": 0,
                "hard_blocked_tables": [],
                "section_decisions": [],
                "propagation_provenance": [],
                "effective_inspections": [],
                "validation": {
                    "status": "not_run",
                    "error_count": 0,
                    "errors": [],
                },
            }
        ),
        "candidate_models": (
            {
                table_name: dict(metadata)
                for table_name, metadata in effective_model_metadata.items()
            }
            if not should_publish
            else {}
        ),
        "publication": {
            "status": publication_transition.status,
            "published": should_publish,
            "candidate_status": publication_transition.candidate_status,
            "complete": publication_transition.complete,
            "would_publish_status": (
                publication_transition.would_publish_status
            ),
            "formal_files_state": publication_outcome.formal_files_state,
            "finalization_status": (
                "failed"
                if checkpoint_finalization_error
                or publication_outcome.finalization_status == "failed"
                else ("completed" if should_publish else "not_started")
            ),
            "recovery_required": bool(
                checkpoint_finalization_error
                or publication_outcome.recovery_required
            ),
            "reason": publication_transition.reason,
            "recoverable": publication_transition.recoverable,
            "retryable": publication_transition.retryable,
            "retry_action": publication_transition.retry_action,
            "quarantined_table_count": len(
                resolved_candidate.quarantined_tables
            ),
            "withheld_section_count": sum(
                len(decision.quarantined_sections)
                for decision in resolved_candidate.decisions
            ),
            "reason_count": sum(
                len(decision.reasons_for(section))
                for decision in resolved_candidate.decisions
                for section in decision.quarantined_sections
            ),
            "quarantined_tables": list(resolved_candidate.quarantined_tables),
            "hard_block_count": int(
                publication_validation.get("error_count")
                or len(publication_validation.get("errors") or [])
            ),
            "validation": publication_validation,
            "inspection_transition": inspection_transition.to_dict(),
            "transition_plan": publication_transition.to_dict(),
        },
        "checkpoint": checkpoint_report,
        "flow": {
            "mode": "generate",
            "prior_source": "direct_rule",
            "llm_enabled": bool(api_key),
            "base_model_count": len(base_plan.model_metadata),
            "final_model_count": len(final_model_metadata),
        },
    }
    result.update(catalog_report)
    result.update(catalog_update_report)
    return result


def run_direct_model_generation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Backward-compatible alias; new code should use generate naming."""
    return run_generate_model_metadata(*args, **kwargs)


def run_catalog_metadata_write(
    project: str,
    *,
    dry_run: bool = False,
    write_scope: str = "business",
    init_catalog: bool = False,
) -> dict[str, Any]:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("catalog 回写仅支持 write_scope=all/table/business")

    def load_catalog_inputs():
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()
        _config.clear_business_semantics_cache()
        planned_init = None
        if init_catalog:
            planned_init = write_initial_business_semantics_catalog(
                project,
                overwrite=False,
                dry_run=True,
            )
        loaded_catalog = (
            (planned_init or {}).get("catalog")
            if planned_init
            else load_business_semantics_catalog(project)
        )
        return (
            planned_init,
            loaded_catalog,
            load_model_metadata(project),
            _catalog_table_assets(project),
        )

    (
        (init_result, catalog, base_models, table_assets),
        base_formal_snapshot,
    ) = read_consistent_metadata_snapshot(project, load_catalog_inputs)
    if not catalog:
        raise FileNotFoundError(
            f"未找到 {project} 业务语义目录，请先初始化三份 catalog YAML"
        )

    updates = []
    for table_name, asset in sorted(table_assets.items()):
        if not asset.ddl or not asset.ddl.exists:
            continue
        mapping = catalog_mapping_for_model(
            catalog,
            table_name,
            base_models.get(table_name),
        )
        if isinstance(mapping, UnavailableModelSection):
            updates.append(
                {
                    "table": table_name,
                    "status": "not_assessed",
                    "reason": "quarantined",
                    "section": mapping.section,
                    "reason_codes": list(mapping.reasons),
                    "changed": False,
                    "updated": False,
                }
            )
            continue
        updates.append(
            update_model_yaml_from_catalog(
                project,
                table_name,
                mapping,
                dry_run=True,
                write_scope=write_scope,
                existing_model=base_models.get(table_name),
                include_model_metadata=True,
            )
        )

    publication_outcome = MetadataPublicationOutcome(
        formal_files_state="unchanged",
        finalization_status="not_started",
        recovery_required=False,
    )
    publication_error = None
    if not dry_run:
        rendered_files = {
            Path(update["path"]): yaml.safe_dump(
                update["model_metadata"],
                allow_unicode=True,
                sort_keys=False,
            )
            for update in updates
            if update.get("changed")
            and isinstance(update.get("model_metadata"), dict)
        }
        planned_catalog_names = set(
            (init_result or {}).get("written_names") or []
        )
        if planned_catalog_names:
            catalog_files, _deleted, _written = (
                _render_generated_catalog_files(
                    project,
                    catalog,
                    enabled=True,
                )
            )
            catalog_paths = business_semantics_paths(project)
            rendered_files.update(
                {
                    path: content
                    for path, content in catalog_files.items()
                    if any(
                        path == catalog_paths.get(name)
                        for name in planned_catalog_names
                    )
                }
            )

        def clear_catalog_write_caches() -> None:
            import dw_refactor_agent.config as _config

            _config.clear_model_metadata_cache()
            _config.clear_business_semantics_cache()
            _config.clear_naming_config_cache()

        try:
            publication_outcome = transactional_metadata_publication(
                project,
                rendered_files,
                delete_paths=tuple(
                    Path(path)
                    for path in (init_result or {}).get(
                        "legacy_paths_to_remove"
                    )
                    or []
                ),
                expected_snapshot=base_formal_snapshot,
            )
        except MetadataPublicationError as exc:
            publication_outcome = exc.outcome
            publication_error = f"{type(exc).__name__}: {exc}"
        if publication_outcome.formal_files_state == "published":
            clear_catalog_write_caches()
            for update in updates:
                update["updated"] = bool(update.get("changed"))

    for update in updates:
        update.pop("model_metadata", None)

    changed_updates = [update for update in updates if update["changed"]]
    result = {
        "project": project,
        "source": "catalog",
        "write_scope": write_scope,
        "paths": {
            name: str(path)
            for name, path in business_semantics_paths(project).items()
        },
        "written_names": (init_result or {}).get("written_names") or [],
        "inspected_table_count": len(updates),
        "model_updates": changed_updates,
        "model_update_count": len(
            [update for update in changed_updates if update.get("updated")]
        ),
        "model_change_count": len(changed_updates),
        "publication": {
            "status": (
                "dry_run"
                if dry_run
                else (
                    "published"
                    if publication_outcome.formal_files_state == "published"
                    else ("blocked" if publication_error else "unchanged")
                )
            ),
            "published": publication_outcome.formal_files_state == "published",
            **publication_outcome.to_dict(),
        },
    }
    if publication_error:
        result["publication"]["error"] = publication_error
    return result


def run_catalog_discovery(
    project: str,
    *,
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Use table-level LLM inspection results to initialize/update catalog."""
    data = load_lineage_data(project)
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()

    resolution_policy = LayerResolutionPolicy(mode="refresh")
    inspector = _new_table_inspector(
        api_key=api_key,
        model=model,
        base_url=base_url,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
        request_timeout=request_timeout,
        min_cacheable_confidence=resolution_policy.min_llm_confidence,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()

    def load_discovery_inputs():
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()
        _config.clear_business_semantics_cache()
        return load_model_metadata(project), load_business_semantics_catalog(
            project
        )

    (
        (model_metadata, existing_catalog),
        base_formal_snapshot,
    ) = read_consistent_metadata_snapshot(project, load_discovery_inputs)
    inspection = run_inspection_pipeline(
        project,
        data,
        inspector,
        metric_group_builder=metric_groups_for_model,
        result_enricher=lambda results, contexts: (
            enrich_results_with_project_semantics(
                results,
                contexts,
                catalog=existing_catalog,
            )
        ),
        base_model_metadata=model_metadata,
        metric_result_is_eligible=lambda result: (
            _metric_result_is_eligible_for_propagation(
                result,
                existing_model=model_metadata.get(result.table_name),
                resolution_policy=resolution_policy,
            )
        ),
        result_layer_resolver=lambda _ctx, result: layer_for_model(
            result,
            existing_model=model_metadata.get(result.table_name),
            policy=resolution_policy,
        ),
    )
    contexts = inspection.contexts
    dwd_contexts = inspection.dwd_contexts
    dws_contexts = inspection.dws_contexts
    metadata_only_contexts = inspection.metadata_only_contexts
    results = inspection.results
    resolved_results = _resolved_results_for_catalog_discovery(
        results,
        model_metadata,
    )

    write_result = write_initial_business_semantics_catalog(
        project,
        overwrite=overwrite,
        dry_run=True,
        inspection_results=resolved_results,
    )
    model_updates = []
    discovered_catalog = write_result.get("catalog") or {}
    resolved_results_by_table = {
        result.table_name: result for result in resolved_results
    }
    for result in results:
        resolved_result = resolved_results_by_table.get(result.table_name)
        if resolved_result is None:
            continue
        mapping = catalog_discovery_model_mapping(
            project,
            resolved_result,
            discovered_catalog,
            model_metadata.get(result.table_name, {}),
        )
        if not mapping:
            continue
        update = update_model_yaml_from_catalog(
            project,
            result.table_name,
            mapping,
            dry_run=True,
            write_scope="business",
            existing_model=model_metadata.get(result.table_name),
            include_model_metadata=True,
        )
        if update["changed"]:
            model_updates.append(update)

    publication_outcome = MetadataPublicationOutcome(
        formal_files_state="unchanged",
        finalization_status="not_started",
        recovery_required=False,
    )
    publication_error = None
    if not dry_run:
        rendered_files = {
            Path(update["path"]): yaml.safe_dump(
                update["model_metadata"],
                allow_unicode=True,
                sort_keys=False,
            )
            for update in model_updates
            if isinstance(update.get("model_metadata"), dict)
        }
        planned_catalog_names = set(write_result.get("written_names") or [])
        catalog_files, _deleted, _written = _render_generated_catalog_files(
            project,
            discovered_catalog,
            enabled=bool(planned_catalog_names),
        )
        catalog_paths = business_semantics_paths(project)
        rendered_files.update(
            {
                path: content
                for path, content in catalog_files.items()
                if any(
                    path == catalog_paths.get(name)
                    for name in planned_catalog_names
                )
            }
        )

        def clear_discovery_caches() -> None:
            import dw_refactor_agent.config as _config

            _config.clear_model_metadata_cache()
            _config.clear_business_semantics_cache()
            _config.clear_naming_config_cache()

        try:
            publication_outcome = transactional_metadata_publication(
                project,
                rendered_files,
                delete_paths=tuple(
                    Path(path)
                    for path in write_result.get("legacy_paths_to_remove")
                    or []
                ),
                expected_snapshot=base_formal_snapshot,
            )
        except MetadataPublicationError as exc:
            publication_outcome = exc.outcome
            publication_error = f"{type(exc).__name__}: {exc}"
        if publication_outcome.formal_files_state == "published":
            clear_discovery_caches()
            write_result["updated"] = bool(write_result.get("changed"))
            write_result["removed_legacy_paths"] = list(
                write_result.get("legacy_paths_to_remove") or []
            )
            for update in model_updates:
                update["updated"] = True

    for update in model_updates:
        update.pop("model_metadata", None)

    result = {
        "project": project,
        "source": "llm_catalog_discovery",
        "path": write_result["path"],
        "paths": write_result.get("paths") or {},
        "written_names": write_result.get("written_names") or [],
        "changed": write_result["changed"],
        "updated": write_result["updated"],
        "catalog": write_result["catalog"],
        "inspected_table_count": len(contexts),
        "dwd_table_count": len(dwd_contexts),
        "dws_table_count": len(dws_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "fact_table_count": sum(
            1 for result in results if result.is_fact_table
        ),
        "dimension_table_count": sum(
            1 for result in results if result.table_type == "dimension"
        ),
        "business_process_count": len(
            (write_result.get("catalog") or {}).get("business_processes") or []
        ),
        "semantic_subject_count": len(
            (write_result.get("catalog") or {}).get("semantic_subjects") or []
        ),
        "model_updates": model_updates,
        "model_update_count": len(
            [update for update in model_updates if update.get("updated")]
        ),
        "model_change_count": len(model_updates),
        "tables": [result_for_report(result) for result in results],
        "publication": {
            "status": (
                "dry_run"
                if dry_run
                else (
                    "published"
                    if publication_outcome.formal_files_state == "published"
                    else ("blocked" if publication_error else "unchanged")
                )
            ),
            "published": publication_outcome.formal_files_state == "published",
            **publication_outcome.to_dict(),
        },
    }
    if publication_error:
        result["publication"]["error"] = publication_error
    return result


def result_for_report(
    result: TableInspectResult,
    *,
    existing_model: dict[str, Any] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
) -> dict[str, Any]:
    """生成模型元数据回写报告中的单表结果。"""
    resolution = _layer_resolution_for_model(
        result,
        existing_model=existing_model,
        policy=resolution_policy,
    )
    data = inspect_result_to_dict(result)
    data["violations"] = metric_violations(
        result,
        applied_layer=resolution.applied_layer,
        applied_table_type=resolution.table_type,
    )
    data["metadata_warnings"] = warnings_for_resolution(result, resolution)
    return data


def _format_progress_message(event: dict[str, Any]) -> str:
    table_label = (
        f"[{event.get('index', '?')}/{event.get('total', '?')}] "
        f"{event.get('table')}({event.get('layer')})"
    )
    event_name = event.get("event")
    if event_name == "start":
        return f"{table_label} 开始巡检"
    if event_name == "cache_hit":
        return f"{table_label} 命中缓存，跳过 API"
    if event_name == "checkpoint_hit":
        return f"{table_label} 从上一轮检查点恢复，跳过 API"
    if event_name == "checkpoint_retry":
        return f"{table_label} 上一轮检查点已失效，重新调用 API"
    if event_name == "api_call":
        return (
            f"{table_label} 调用 DeepSeek "
            f"({event.get('attempt')}/{event.get('max_attempts')})"
        )
    if event_name == "api_error":
        return (
            f"{table_label} DeepSeek 调用失败 "
            f"({event.get('attempt')}/{event.get('max_attempts')}): "
            f"{event.get('error')}"
        )
    if event_name == "validation_retry":
        validation = event.get("validation") or {}
        issue_count = sum(len(items) for items in validation.values())
        return (
            f"{table_label} 返回校验为 {event.get('status')}，"
            f"发现 {issue_count} 个字段问题，准备重试"
        )
    if event_name == "unexpected_error":
        return f"{table_label} 巡检异常: {event.get('error')}"
    if event_name == "finish":
        metric_count = (
            int(event.get("atomic_metric_count", 0) or 0)
            + int(event.get("derived_metric_count", 0) or 0)
            + int(event.get("calculated_metric_count", 0) or 0)
        )
        return (
            f"{table_label} 完成: status={event.get('status')}, "
            f"retry={event.get('retry_count')}, metrics={metric_count} "
            f"(atomic={event.get('atomic_metric_count')}, "
            f"derived={event.get('derived_metric_count')}, "
            f"calculated={event.get('calculated_metric_count')})"
        )
    return f"{table_label} {event_name}"


def build_progress_callback() -> Callable[[dict[str, Any]], None]:
    """构建线程安全的 CLI 进度输出回调。"""
    print_lock = threading.Lock()

    def callback(event: dict[str, Any]) -> None:
        with print_lock:
            print(_format_progress_message(event), flush=True)

    return callback


def _metadata_flow_plan_for_write(
    project: str,
    *,
    write_scope: str,
    update_catalog: bool,
    model_metadata: dict[str, dict[str, Any]] | None,
    metric_groups: dict[str, dict[str, list[str]]] | None,
    model_paths: dict[str, Path] | None,
    resolution_policy: LayerResolutionPolicy | None,
) -> MetadataFlowPlan:
    if (
        model_metadata is None
        and model_paths is None
        and resolution_policy is None
    ):
        plan = build_refresh_plan(project, write_scope=write_scope)
        plan = replace(
            plan,
            catalog_plan=catalog_plan_for_refresh(llm=update_catalog),
        )
        if metric_groups is not None:
            plan = replace(plan, metric_groups=dict(metric_groups))
        return plan

    policy = resolution_policy or LayerResolutionPolicy(mode="refresh")
    mode = policy.mode
    prior_source = (
        "direct_rule"
        if policy.fallback_source == "direct_rule"
        else "declared"
    )
    catalog_plan = (
        catalog_plan_for_generate(llm=update_catalog)
        if mode == "generate"
        else catalog_plan_for_refresh(llm=update_catalog)
    )
    return MetadataFlowPlan(
        mode=mode,
        prior_source=prior_source,
        write_scope=write_scope,
        base_model_metadata=dict(
            model_metadata
            if model_metadata is not None
            else load_model_metadata(project)
        ),
        metric_groups=dict(metric_groups or {}),
        write_targets=MetadataWriteTargets(
            model_paths=dict(model_paths or {})
        ),
        resolution_policy=policy,
        catalog_plan=catalog_plan,
    )


def run_metadata_write(
    project: str,
    *,
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str | None = None,
    max_retries: int = 1,
    parallelism: int = 2,
    request_timeout: int = 60,
    no_cache: bool = False,
    dry_run: bool = False,
    require_complete: bool = False,
    write_scope: str = "all",
    show_progress: bool = False,
    model_metadata: dict[str, dict[str, Any]] | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
    model_paths: dict[str, Path] | None = None,
    resolution_policy: LayerResolutionPolicy | None = None,
    include_model_metadata: bool = False,
    update_catalog: bool = True,
    expose_layer_hints: bool = True,
    resume_cache: dict[str, Any] | None = None,
    result_callback: (Callable[[TableInspectResult], None] | None) = None,
    inspection_complete_callback: (
        Callable[[list[TableInspectResult]], None] | None
    ) = None,
    lineage_data: dict[str, Any] | None = None,
    asset_content: dict[str, dict[str, str]] | None = None,
    inspection_targets: Iterable[str] | None = None,
    business_semantics_catalog: dict[str, Any] | None = None,
    catalog_snapshot_hash: str = "",
    asset_manifest_hash: str = "",
) -> dict[str, Any]:
    """运行项目级 LLM 巡检与模型元数据回写。"""
    write_scope = _validate_write_scope(write_scope)

    def load_publication_inputs():
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()
        _config.clear_business_semantics_cache()
        loaded_plan = _metadata_flow_plan_for_write(
            project,
            write_scope=write_scope,
            update_catalog=update_catalog,
            model_metadata=model_metadata,
            metric_groups=metric_groups,
            model_paths=model_paths,
            resolution_policy=resolution_policy,
        )
        if business_semantics_catalog is not None:
            loaded_catalog = copy.deepcopy(business_semantics_catalog)
            loaded_report = {
                "catalog_initialized": False,
                "catalog_init_written_names": [],
                "planned_catalog_written_names": [],
                "planned_catalog_deleted_files": [],
            }
        elif loaded_plan.catalog_plan.ensure_skeleton:
            loaded_catalog, loaded_report = _ensure_metadata_catalog_skeleton(
                project,
                dry_run=True,
            )
        else:
            loaded_catalog = load_business_semantics_catalog(project)
            loaded_report = {
                "catalog_initialized": False,
                "catalog_init_written_names": [],
                "planned_catalog_written_names": [],
                "planned_catalog_deleted_files": [],
            }
        return loaded_plan, loaded_catalog, loaded_report

    (
        (plan, base_catalog, catalog_report),
        base_formal_snapshot,
    ) = read_consistent_metadata_snapshot(project, load_publication_inputs)
    catalog_update_report = _empty_catalog_update_report()
    data = (
        lineage_data
        if lineage_data is not None
        else load_lineage_data(project)
    )
    cache_file = assess_cache_path(project, "inspect.json")
    if no_cache and cache_file.exists():
        cache_file.unlink()
    if no_cache:
        resume_cache = None

    inspector = _new_table_inspector(
        api_key=api_key,
        model=model,
        base_url=base_url,
        cache_file=cache_file,
        max_retries=max_retries,
        parallelism=parallelism,
        request_timeout=request_timeout,
        min_cacheable_confidence=plan.resolution_policy.min_llm_confidence,
        resume_cache=resume_cache,
        validate_publication_contract=plan.mode == "generate",
        catalog_snapshot_hash=catalog_snapshot_hash,
        asset_manifest_hash=asset_manifest_hash,
    )
    if show_progress:
        inspector.progress_callback = build_progress_callback()
    inspector.result_callback = result_callback

    local_decisions = {}
    local_proposal_results = {}

    def resolve_local_result(result: TableInspectResult) -> TableInspectResult:
        matching_models = [
            metadata
            for table_name, metadata in plan.base_model_metadata.items()
            if table_name.casefold() == result.table_name.casefold()
        ]
        metadata = matching_models[0] if len(matching_models) == 1 else {}
        local_proposal_results[result.table_name.casefold()] = copy.deepcopy(
            result
        )
        effective_result, decision = prepare_inspection_for_propagation(
            result,
            metadata=metadata,
            catalog=base_catalog,
        )
        local_decisions[result.table_name.casefold()] = decision
        return effective_result

    inspection = run_inspection_pipeline(
        project,
        data,
        inspector,
        metric_group_builder=metric_groups_for_model,
        result_enricher=lambda results, contexts: (
            enrich_results_with_project_semantics(
                results,
                contexts,
                catalog=base_catalog,
            )
        ),
        base_model_metadata=plan.base_model_metadata,
        metric_groups=plan.metric_groups
        if metric_groups is not None
        else None,
        expose_layer_hints=expose_layer_hints,
        use_model_metadata_asset_roles=plan.mode == "generate",
        metric_result_is_eligible=lambda result: (
            _metric_result_is_eligible_for_propagation(
                result,
                existing_model=(plan.base_model_metadata or {}).get(
                    result.table_name
                ),
                resolution_policy=plan.resolution_policy,
            )
        ),
        asset_content=asset_content,
        inspection_targets=inspection_targets,
        business_semantics_catalog=base_catalog,
        local_result_resolver=resolve_local_result,
        result_layer_resolver=lambda _ctx, result: layer_for_model(
            result,
            existing_model=(plan.base_model_metadata or {}).get(
                result.table_name
            ),
            policy=plan.resolution_policy,
        ),
    )
    contexts = inspection.contexts
    metric_contexts = inspection.metric_contexts
    metadata_only_contexts = inspection.metadata_only_contexts
    results = inspection.results
    reported_results = [
        local_proposal_results.get(result.table_name.casefold(), result)
        for result in results
    ]
    if inspection_complete_callback is not None:
        inspection_complete_callback(reported_results)
    yaml_updates, skipped_updates = write_model_updates_from_plan(
        project,
        results,
        plan,
        dry_run=True,
        use_plan_existing_metadata=True,
        include_model_metadata=True,
    )
    reports = [
        result_for_report(
            result,
            existing_model=(plan.base_model_metadata or {}).get(
                result.table_name
            ),
            resolution_policy=plan.resolution_policy,
        )
        for result in reported_results
    ]
    catalog_update_report = _merge_llm_catalog_discoveries(
        project,
        llm_result=None,
        inspection_results=(
            [
                result
                for _table_key, result in sorted(
                    local_proposal_results.items()
                )
            ]
        ),
        base_catalog=base_catalog,
        model_metadata=plan.base_model_metadata,
        resolution_policy=plan.resolution_policy,
        dry_run=True,
    )

    inspection_transition = plan_inspection_run_transition(
        llm_enabled=True,
        inspection_targets=(context.table_name for context in contexts),
        reports=reports,
    )
    refresh_transition_plan = None
    publication_validation = {
        "status": "passed",
        "stage": "effective_candidate",
        "error_count": 0,
        "errors": [],
    }
    candidate_status = "complete"
    quarantined_tables: list[str] = []
    withheld_section_count = 0
    quarantine_reason_count = 0
    if plan.mode == "refresh":
        try:
            existing_refresh_models = {}
            candidate_refresh_models = {}
            update_by_model_name = {}
            for update in yaml_updates:
                candidate_metadata = update.get("model_metadata")
                if not isinstance(candidate_metadata, dict):
                    continue
                model_name = _unique_model_name(
                    plan.base_model_metadata,
                    str(update.get("table") or ""),
                )
                if model_name in candidate_refresh_models:
                    raise ValueError(
                        f"duplicate refresh candidate for {model_name}"
                    )
                existing_refresh_models[model_name] = dict(
                    plan.base_model_metadata[model_name]
                )
                candidate_refresh_models[model_name] = dict(candidate_metadata)
                update_by_model_name[model_name] = update
            decision_items = []
            for _table_key, decision in sorted(local_decisions.items()):
                model_name = _unique_model_name(
                    plan.base_model_metadata, decision.table_name
                )
                if model_name not in existing_refresh_models:
                    base_metadata = dict(plan.base_model_metadata[model_name])
                    existing_refresh_models[model_name] = base_metadata
                    candidate_refresh_models[model_name] = dict(base_metadata)
                    skipped = next(
                        (
                            item
                            for item in skipped_updates
                            if identifier_match_key(
                                str(item.get("table") or "")
                            )
                            == identifier_match_key(decision.table_name)
                        ),
                        {},
                    )
                    update_by_model_name[model_name] = {
                        "table": model_name,
                        "path": str(
                            skipped.get("path")
                            or plan.write_targets.model_paths.get(model_name)
                            or model_path_for_table(project, model_name)
                        ),
                        "status": "passed",
                        "changed": False,
                        "updated": False,
                        "write_scope": write_scope,
                    }
                decision_items.append(decision)
            refresh_transition_plan = plan_refresh_transitions(
                existing_refresh_models,
                candidate_decisions=decision_items,
                requested_sections=_REFRESH_SCOPE_SECTIONS[write_scope],
                retention_eligible={
                    table_name: MODEL_SECTIONS
                    for table_name in existing_refresh_models
                },
            )
            if refresh_transition_plan.status == "blocked":
                raise ValueError("refresh section transition is blocked")
            effective_refresh_models = materialize_refresh_models(
                existing_refresh_models,
                candidate_refresh_models,
                refresh_transition_plan,
            )
            effective_updates = []
            for table_name, metadata in effective_refresh_models.items():
                AssessmentModelSemantics.from_metadata(
                    metadata, source=table_name
                )
                update = dict(update_by_model_name[table_name])
                changed = metadata != existing_refresh_models[table_name]
                update["changed"] = changed
                update["updated"] = False
                update["model_metadata"] = metadata
                if changed:
                    effective_updates.append(update)
            yaml_updates = effective_updates
            effective_views = [
                AssessmentModelSemantics.from_metadata(
                    metadata, source=table_name
                )
                for table_name, metadata in effective_refresh_models.items()
            ]
            if any(view.quarantined_sections for view in effective_views):
                candidate_status = "quarantined"
            quarantined_tables = sorted(
                table_name
                for table_name, view in zip(
                    effective_refresh_models, effective_views
                )
                if view.quarantined_sections
            )
            withheld_section_count = sum(
                len(view.quarantined_sections) for view in effective_views
            )
            quarantine_reason_count = sum(
                len(view.model.governance.reasons_for(section))
                for view in effective_views
                for section in view.quarantined_sections
            )
        except (TypeError, ValueError) as exc:
            candidate_status = "blocked"
            publication_validation = {
                "status": "blocked",
                "stage": "refresh_effective_candidate",
                "error_count": 1,
                "errors": [
                    {
                        "type": "refresh_candidate_invalid",
                        "message": str(exc),
                    }
                ],
            }
    publication_transition = plan_publication_transition(
        candidate_status=candidate_status,
        inspection_transition=inspection_transition,
        dry_run=dry_run,
        require_complete=require_complete,
    )

    publication_outcome = MetadataPublicationOutcome(
        formal_files_state="unchanged",
        finalization_status="not_started",
        recovery_required=False,
    )
    publication_error = None
    if publication_transition.published:
        rendered_files = {
            Path(update["path"]): yaml.safe_dump(
                update["model_metadata"],
                allow_unicode=True,
                sort_keys=False,
            )
            for update in yaml_updates
            if update.get("changed")
            and isinstance(update.get("model_metadata"), dict)
        }
        planned_catalog_names = set(
            catalog_report.get("planned_catalog_written_names") or []
        )
        if planned_catalog_names:
            catalog_files, _catalog_deletes, _catalog_names = (
                _render_generated_catalog_files(
                    project,
                    base_catalog,
                    enabled=True,
                )
            )
            catalog_paths = business_semantics_paths(project)
            rendered_files.update(
                {
                    path: content
                    for path, content in catalog_files.items()
                    if any(
                        path == catalog_paths.get(name)
                        for name in planned_catalog_names
                    )
                }
            )

        def clear_publication_caches() -> None:
            import dw_refactor_agent.config as _config

            _config.clear_model_metadata_cache()
            _config.clear_business_semantics_cache()
            _config.clear_naming_config_cache()

        try:
            publication_outcome = transactional_metadata_publication(
                project,
                rendered_files,
                delete_paths=tuple(
                    Path(path)
                    for path in catalog_report.get(
                        "planned_catalog_deleted_files"
                    )
                    or []
                ),
                expected_snapshot=base_formal_snapshot,
            )
        except MetadataPublicationError as exc:
            publication_outcome = exc.outcome
            publication_error = f"{type(exc).__name__}: {exc}"
        if publication_outcome.formal_files_state == "published":
            clear_publication_caches()
            for update in yaml_updates:
                update["updated"] = bool(update.get("changed"))
            catalog_report["catalog_init_written_names"] = sorted(
                planned_catalog_names
            )
            catalog_report["planned_catalog_written_names"] = []
            catalog_report["planned_catalog_deleted_files"] = []

    if (
        publication_error
        and publication_outcome.formal_files_state != "published"
    ):
        publication_transition = replace(
            publication_transition,
            status="blocked",
            published=False,
            reason="publication_transaction_failed",
        )

    if not include_model_metadata:
        for update in yaml_updates:
            update.pop("model_metadata", None)

    result = {
        "project": project,
        "write_scope": plan.write_scope,
        "inspected_table_count": len(contexts),
        "metric_table_count": len(metric_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "dwd_table_count": len(inspection.dwd_contexts),
        "dws_table_count": len(inspection.dws_contexts),
        "dim_table_count": len(inspection.metadata_only_contexts),
        "fact_table_count": sum(
            1 for result in reported_results if result.is_fact_table
        ),
        "passed_table_count": sum(
            1 for result in reported_results if result.status == "passed"
        ),
        "warning_table_count": sum(
            1
            for result, report in zip(reported_results, reports)
            if result.status == "warning" or report.get("metadata_warnings")
        ),
        "blocked_table_count": sum(
            1 for result in reported_results if result.status == "blocked"
        ),
        "atomic_metric_count": sum(
            len(result.atomic_metrics) for result in reported_results
        ),
        "derived_metric_count": sum(
            len(result.derived_metrics) for result in reported_results
        ),
        "calculated_metric_count": sum(
            len(result.calculated_metrics) for result in reported_results
        ),
        "metric_count": sum(
            len(metric_names_for_model(result)) for result in reported_results
        ),
        "derived_metric_violation_count": _violation_count(
            reported_results,
            "derived_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "calculated_metric_violation_count": _violation_count(
            reported_results,
            "calculated_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "non_atomic_metric_violation_count": _violation_count(
            reported_results,
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "metadata_warning_count": sum(
            len(report.get("metadata_warnings") or []) for report in reports
        ),
        "inspection_reuse": (
            inspector.reuse_report()
            if callable(getattr(inspector, "reuse_report", None))
            else {}
        ),
        "tables": reports,
        "local_section_decisions": [
            decision.to_dict()
            for _table_key, decision in sorted(local_decisions.items())
        ],
        "model_updates": yaml_updates,
        "model_update_count": len(
            [update for update in yaml_updates if update.get("updated")]
        ),
        "model_change_count": len(yaml_updates),
        "skipped_model_updates": skipped_updates,
        "publication": {
            "status": publication_transition.status,
            "published": publication_transition.published,
            "candidate_status": publication_transition.candidate_status,
            "complete": publication_transition.complete,
            "would_publish_status": (
                publication_transition.would_publish_status
            ),
            "reason": publication_transition.reason,
            "recoverable": publication_transition.recoverable,
            "retryable": publication_transition.retryable,
            "retry_action": publication_transition.retry_action,
            "quarantined_table_count": len(quarantined_tables),
            "withheld_section_count": withheld_section_count,
            "reason_count": quarantine_reason_count,
            "quarantined_tables": quarantined_tables,
            "hard_block_count": publication_validation.get("error_count", 0),
            "validation": publication_validation,
            "inspection_transition": inspection_transition.to_dict(),
            "refresh_transition": (
                refresh_transition_plan.to_dict()
                if refresh_transition_plan is not None
                else {"status": "not_applicable", "transitions": []}
            ),
            **publication_outcome.to_dict(),
        },
    }
    if publication_error:
        result["publication"]["error"] = publication_error
    result.update(catalog_report)
    result.update(catalog_update_report)
    return result


def publication_exit_code(publication: dict[str, Any]) -> int:
    """Map the structured publication state to the documented CLI code."""
    if publication.get("published") and (
        publication.get("finalization_status") == "failed"
    ):
        return 3
    status = str(publication.get("status") or "")
    if status == "dry_run":
        status = str(publication.get("would_publish_status") or "")
    if status == "blocked":
        return 1
    if status in {
        "not_published_incomplete",
        "not_published_inspection_failure",
    }:
        return 2
    if status in {"published", "published_with_quarantine"}:
        return 0
    return 1


def _exit_for_publication(publication: dict[str, Any]) -> None:
    if not publication:
        return
    code = publication_exit_code(publication)
    if code:
        summary = (
            "发布状态: {status}; candidate={candidate}; "
            "formal_files={formal}; finalization={finalization}".format(
                status=publication.get("status") or "unknown",
                candidate=publication.get("candidate_status") or "unknown",
                formal=publication.get("formal_files_state") or "unknown",
                finalization=(
                    publication.get("finalization_status") or "unknown"
                ),
            )
        )
        if code == 3:
            summary = (
                "正式文件已经发布，但 checkpoint/report 收尾失败；"
                "请先修复收尾状态，不要重复发布。" + summary
            )
            if publication.get("finalization_error"):
                summary += "; error=" + str(publication["finalization_error"])
        print(summary, file=sys.stderr)
        raise SystemExit(code)


def _write_result_report(output_path: Path, result: dict[str, Any]) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding=TEXT_ENCODING,
        )
    except Exception as exc:
        publication = result.get("publication") or {}
        if publication.get("published") and (
            publication.get("formal_files_state") == "published"
        ):
            publication["finalization_status"] = "failed"
            publication["recovery_required"] = True
            publication["finalization_error"] = f"{type(exc).__name__}: {exc}"
            _exit_for_publication(publication)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM 表巡检与模型元数据回写工具"
    )
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径 (默认 warehouses/{project}/artifacts/assessment/model_metadata_result.json)",
    )
    parser.add_argument(
        "--mode",
        choices=("refresh", "generate"),
        default="refresh",
        help="运行模式: refresh=刷新现有 models, generate=冷启动重建 models",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="调用表级 LLM 巡检补全模型元数据",
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash", help="DeepSeek 模型名称"
    )
    parser.add_argument(
        "--base-url",
        help="DeepSeek/OpenAI-compatible chat completions API 地址",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="LLM 返回校验失败时的最大重试次数",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出巡检结果，不写入 models YAML",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="任一语义 section 被隔离时不发布（退出码 2）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="忽略本地缓存和冷启动检查点，强制重新调用 API",
    )
    parser.add_argument(
        "--parallel", type=int, default=2, help="LLM 并发调用数，默认 2"
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=60,
        help="单次 LLM 请求超时时间（秒）",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="不打印单表巡检进度"
    )
    args = parser.parse_args()

    if args.mode == "refresh" and not args.llm:
        result = run_catalog_metadata_write(
            args.project,
            dry_run=args.dry_run,
            write_scope="business",
            init_catalog=False,
        )
    elif args.mode == "refresh":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
            )

        result = run_metadata_write(
            args.project,
            api_key=api_key,
            model=args.model,
            base_url=normalize_chat_completions_url(args.base_url),
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            require_complete=args.require_complete,
            write_scope="all",
            show_progress=not args.quiet,
            update_catalog=True,
        )
    else:
        api_key = None
        if args.llm:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise SystemExit(
                    "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
                )
        result = run_generate_model_metadata(
            args.project,
            api_key=api_key,
            model=args.model,
            base_url=normalize_chat_completions_url(args.base_url),
            max_retries=args.max_retries,
            parallelism=args.parallel,
            request_timeout=args.request_timeout,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            require_complete=args.require_complete,
            write_scope="all",
            update_catalog=True,
            replace_existing_models=True,
            show_progress=not args.quiet,
        )

    output_path = (
        Path(args.output)
        if args.output
        else model_metadata_result_path(args.project)
    )
    _write_result_report(output_path, result)
    print(f"结果已写入: {output_path}")
    if result.get("source") == "catalog":
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "回写来源: catalog, "
            "目录文件: {paths}, 本次写入目录: {written_names}, "
            "巡检表: {inspected_table_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
                paths=paths,
                written_names=written_names,
                inspected_table_count=result.get("inspected_table_count", 0),
                model_change_count=result.get("model_change_count", 0),
                model_update_count=result.get("model_update_count", 0),
            )
        )
        return
    if result.get("source") == "llm_catalog_discovery":
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "目录发现: {path}, 文件: {paths}, 本次写入: {written_names}, "
            "巡检表: {inspected_table_count}, "
            "业务过程: {business_process_count}, "
            "语义主题: {semantic_subject_count}, 已写入: {updated}".format(
                paths=paths,
                written_names=written_names,
                path=result.get("path"),
                inspected_table_count=result.get("inspected_table_count", 0),
                business_process_count=result.get("business_process_count", 0),
                semantic_subject_count=result.get("semantic_subject_count", 0),
                updated=result.get("updated"),
            )
        )
        return
    if result.get("source") == "direct_model_generation":
        planned_catalog = (
            ", ".join(result.get("planned_catalog_written_names") or []) or "-"
        )
        written_catalog = (
            ", ".join(result.get("catalog_init_written_names") or []) or "-"
        )
        print(
            "冷启动生成: planned_catalog={planned_catalog}, "
            "written_catalog={written_catalog}, "
            "计划删除模型: {planned_delete_count}, "
            "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
                planned_catalog=planned_catalog,
                written_catalog=written_catalog,
                planned_delete_count=len(
                    result.get("planned_deleted_model_files") or []
                ),
                model_change_count=result.get("model_change_count", 0),
                model_update_count=result.get("model_update_count", 0),
            )
        )
        publication = result.get("publication") or {}
        _exit_for_publication(publication)
        return
    if "catalog" in result:
        catalog = result.get("catalog") or {}
        paths = (
            ", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-"
        )
        written_names = ", ".join(result.get("written_names") or []) or "-"
        print(
            "目录初始化: {path}, 文件: {paths}, 本次写入: {written_names}, "
            "业务过程: {process_count}, 语义主题: {subject_count}, 已写入: {updated}".format(
                path=result.get("path"),
                paths=paths,
                written_names=written_names,
                process_count=len(catalog.get("business_processes") or []),
                subject_count=len(catalog.get("semantic_subjects") or []),
                updated=result.get("updated"),
            )
        )
        return
    print(
        "回写范围: {write_scope}, "
        "巡检表: {inspected_table_count}, 指标表: {metric_table_count}, "
        "仅元数据表: {metadata_only_table_count}, DWD表: {dwd_table_count}, "
        "DWS表: {dws_table_count}, DIM表: {dim_table_count}, "
        "事实表: {fact_table_count}, "
        "指标: {metric_count}, 原子指标: {atomic_metric_count}, "
        "派生指标: {derived_metric_count}, 衍生指标: {calculated_metric_count}, "
        "非原子指标违规: {non_atomic_metric_violation_count}, "
        "元数据警告: {metadata_warning_count}, "
        "模型变更: {model_change_count}, 已写入: {model_update_count}".format(
            **result
        )
    )
    publication = result.get("publication") or {}
    if publication:
        _exit_for_publication(publication)


if __name__ == "__main__":
    main()
