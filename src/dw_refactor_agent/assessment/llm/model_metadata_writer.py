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
import json
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

_src_root = Path(__file__).resolve().parents[3]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

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
    metadata_publication_lock,
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
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    PROJECT_ROOT,  # noqa: F401 - compatibility for callers overriding project roots
    TEXT_ENCODING,
    assess_cache_path,
    business_semantics_paths,
    load_model_metadata,
    model_metadata_result_path,
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
    _catalog_candidate_from_llm_result,
    _catalog_entries_by_code,
    _catalog_entry_changes,
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
    metric_counts = {
        table_name: sum(
            _metadata_group_count(metadata.get(group))
            for group in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            )
        )
        for table_name, metadata in model_metadata.items()
    }
    layer_counts: dict[str, int] = {}
    for metadata in model_metadata.values():
        layer = str(metadata.get("layer") or "MISSING").strip().upper()
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    return {
        "model_count": len(model_metadata),
        "metric_count": sum(metric_counts.values()),
        "metric_table_count": sum(
            1 for count in metric_counts.values() if count
        ),
        "entity_table_count": sum(
            1
            for metadata in model_metadata.values()
            if metadata.get("entities")
            or metadata.get("entity")
            or metadata.get("related_entities")
        ),
        "grain_table_count": sum(
            1 for metadata in model_metadata.values() if metadata.get("grain")
        ),
        "layer_counts": dict(sorted(layer_counts.items())),
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
        "published_catalog_summary": _catalog_metadata_summary(catalog),
        "candidate_models": {},
        "publication": {
            "status": "blocked",
            "published": False,
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
    candidate_catalog = catalog
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
            candidate_catalog, resolved_catalog_results = (
                _catalog_candidate_from_llm_result(
                    project,
                    llm_result=llm_result,
                    base_catalog=catalog,
                    model_metadata=generate_plan.base_model_metadata,
                    resolution_policy=generate_plan.resolution_policy,
                    update_catalog=update_catalog,
                )
            )
            final_model_metadata = (
                _apply_catalog_assignments_to_generated_models(
                    project,
                    final_model_metadata,
                    catalog=candidate_catalog,
                    results=resolved_catalog_results,
                )
            )
            if update_catalog:
                catalog_update_report = _merge_llm_catalog_discoveries(
                    project,
                    llm_result=llm_result,
                    base_catalog=catalog,
                    model_metadata=generate_plan.base_model_metadata,
                    resolution_policy=generate_plan.resolution_policy,
                    dry_run=True,
                )
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
            catalog=candidate_catalog,
        )
        (
            candidate_table_names,
            candidate_declared_names,
            candidate_model_paths,
        ) = _candidate_model_publication_targets(
            project,
            generate_plan,
            final_model_metadata,
        )
        should_publish = False
        catalog_rendered_files: dict[Path, str] = {}
        catalog_deleted_files: list[Path] = []
        catalog_written_names: list[str] = []
        _strip_internal_model_metadata(llm_result)
        refinement_updates = (llm_result or {}).get("model_updates") or []
        model_updates: list[dict[str, Any]]
        deleted_model_files: list[str]
        if not dry_run and publication_validation["status"] != "blocked":
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
                        candidate_catalog,
                        enabled=update_catalog,
                    )
                    model_updates, deleted_model_files = (
                        _write_generated_model_metadata(
                            project,
                            generate_plan,
                            final_model_metadata,
                            dry_run=False,
                            delete_existing=replace_existing_models,
                            refinement_updates=refinement_updates,
                            additional_rendered_files=catalog_rendered_files,
                            additional_deleted_files=catalog_deleted_files,
                        )
                    )
                    should_publish = True
        if not should_publish:
            model_updates, deleted_model_files = (
                _write_generated_model_metadata(
                    project,
                    generate_plan,
                    final_model_metadata,
                    dry_run=True,
                    delete_existing=replace_existing_models,
                    refinement_updates=refinement_updates,
                )
            )
        publication_blocked = publication_validation["status"] == "blocked"
        if checkpoint:
            try:
                checkpoint.finish(
                    status="blocked" if publication_blocked else "published",
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
        final_model_metadata
        if should_publish
        else load_model_metadata(project)
    )
    published_catalog = candidate_catalog if should_publish else catalog
    candidate_model_summary = _model_metadata_summary(final_model_metadata)
    published_model_summary = _model_metadata_summary(published_model_metadata)
    candidate_catalog_summary = _catalog_metadata_summary(candidate_catalog)
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
        "published_catalog_summary": published_catalog_summary,
        "candidate_models": (
            {
                table_name: dict(metadata)
                for table_name, metadata in final_model_metadata.items()
            }
            if publication_blocked or dry_run
            else {}
        ),
        "publication": {
            "status": (
                "blocked"
                if publication_blocked
                else ("dry_run" if dry_run else "published")
            ),
            "published": should_publish,
            "validation": publication_validation,
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

    init_result = None
    if init_catalog:
        init_result = write_initial_business_semantics_catalog(
            project,
            overwrite=False,
            dry_run=dry_run,
        )

    catalog = (
        (init_result or {}).get("catalog")
        if init_result and dry_run
        else load_business_semantics_catalog(project)
    )
    if not catalog:
        raise FileNotFoundError(
            f"未找到 {project} 业务语义目录，请先初始化三份 catalog YAML"
        )

    updates = []
    for table_name, asset in sorted(_catalog_table_assets(project).items()):
        if not asset.ddl or not asset.ddl.exists:
            continue
        mapping = catalog_mapping_for_model(
            catalog,
            table_name,
            load_model_metadata(project).get(table_name, {}),
        )
        updates.append(
            update_model_yaml_from_catalog(
                project,
                table_name,
                mapping,
                dry_run=dry_run,
                write_scope=write_scope,
            )
        )
    if not dry_run:
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    changed_updates = [update for update in updates if update["changed"]]
    return {
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
    }


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

    model_metadata = load_model_metadata(project)
    existing_catalog = load_business_semantics_catalog(project)
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
        dry_run=dry_run,
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
            dry_run=dry_run,
            write_scope="business",
        )
        if update["changed"]:
            model_updates.append(update)
    if not dry_run and model_updates:
        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()

    return {
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
    }


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
    business_semantics_catalog: dict[str, Any] | None = None,
    catalog_snapshot_hash: str = "",
    asset_manifest_hash: str = "",
) -> dict[str, Any]:
    """运行项目级 LLM 巡检与模型元数据回写。"""
    write_scope = _validate_write_scope(write_scope)
    plan = _metadata_flow_plan_for_write(
        project,
        write_scope=write_scope,
        update_catalog=update_catalog,
        model_metadata=model_metadata,
        metric_groups=metric_groups,
        model_paths=model_paths,
        resolution_policy=resolution_policy,
    )
    if plan.catalog_plan.ensure_skeleton:
        base_catalog, catalog_report = _ensure_metadata_catalog_skeleton(
            project,
            dry_run=dry_run,
        )
    else:
        base_catalog = (
            business_semantics_catalog
            if business_semantics_catalog is not None
            else load_business_semantics_catalog(project)
        )
        catalog_report = {
            "catalog_initialized": False,
            "catalog_init_written_names": [],
            "planned_catalog_written_names": [],
        }
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
        business_semantics_catalog=business_semantics_catalog,
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
    if inspection_complete_callback is not None:
        inspection_complete_callback(results)
    yaml_updates, skipped_updates = write_model_updates_from_plan(
        project,
        results,
        plan,
        dry_run=dry_run,
        use_plan_existing_metadata=model_metadata is not None,
        include_model_metadata=include_model_metadata,
    )
    reports = [
        result_for_report(
            result,
            existing_model=(plan.base_model_metadata or {}).get(
                result.table_name
            ),
            resolution_policy=plan.resolution_policy,
        )
        for result in results
    ]
    if plan.catalog_plan.merge_llm_discoveries:
        catalog_update_report = _merge_llm_catalog_discoveries(
            project,
            llm_result=None,
            inspection_results=results,
            base_catalog=base_catalog,
            model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
            dry_run=dry_run,
        )

    result = {
        "project": project,
        "write_scope": plan.write_scope,
        "inspected_table_count": len(contexts),
        "metric_table_count": len(metric_contexts),
        "metadata_only_table_count": len(metadata_only_contexts),
        "dwd_table_count": len(inspection.dwd_contexts),
        "dws_table_count": len(inspection.dws_contexts),
        "dim_table_count": len(inspection.metadata_only_contexts),
        "fact_table_count": sum(1 for r in results if r.is_fact_table),
        "passed_table_count": sum(1 for r in results if r.status == "passed"),
        "warning_table_count": sum(
            1
            for result, report in zip(results, reports)
            if result.status == "warning" or report.get("metadata_warnings")
        ),
        "blocked_table_count": sum(
            1 for r in results if r.status == "blocked"
        ),
        "atomic_metric_count": sum(len(r.atomic_metrics) for r in results),
        "derived_metric_count": sum(len(r.derived_metrics) for r in results),
        "calculated_metric_count": sum(
            len(r.calculated_metrics) for r in results
        ),
        "metric_count": sum(len(metric_names_for_model(r)) for r in results),
        "derived_metric_violation_count": _violation_count(
            results,
            "derived_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "calculated_metric_violation_count": _violation_count(
            results,
            "calculated_metrics",
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "non_atomic_metric_violation_count": _violation_count(
            results,
            existing_model_metadata=plan.base_model_metadata,
            resolution_policy=plan.resolution_policy,
        ),
        "metadata_warning_count": sum(
            len(report.get("metadata_warnings") or []) for report in reports
        ),
        "tables": reports,
        "model_updates": yaml_updates,
        "model_update_count": len(
            [update for update in yaml_updates if update.get("updated")]
        ),
        "model_change_count": len(yaml_updates),
        "skipped_model_updates": skipped_updates,
    }
    result.update(catalog_report)
    result.update(catalog_update_report)
    return result


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
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
        if not args.dry_run and publication.get("status") == "blocked":
            error_count = len(
                (publication.get("validation") or {}).get("errors") or []
            )
            raise SystemExit(
                f"冷启动生成发布被阻断（{error_count} 个校验错误），"
                "原有 catalog 与 models 未改动"
            )
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


if __name__ == "__main__":
    main()
