#!/usr/bin/env python3
"""
冷启动模型元数据规划、校验与事务化发布逻辑。

复用 table_inspector 的单次 DeepSeek 调用结果，将表级 layer/table_type、
DWD 数据域、DWD/DWS 业务板块、维度表 entity/related_entities、DWS grain 以及
DWD/DWS 表中的指标字段回写到 models/{table}.yaml，并把 DWD 事实表的
非原子指标输出为违规项。
"""

from __future__ import annotations

import sys
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

_src_root = Path(__file__).resolve().parents[3]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.llm.generation_contract import (
    infer_execution_mapping,
)
from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionInput,
    LayerResolutionPolicy,
    resolve_layer,
)
from dw_refactor_agent.assessment.llm.metadata_flow import (
    MetadataFlowPlan,
)
from dw_refactor_agent.assessment.llm.model_metadata_runtime import (
    project_root,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    TableInspectResult,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    dict_to_result as inspect_dict_to_result,
)
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    TableAsset,
    build_asset_catalog,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    LEGACY_BUSINESS_SEMANTICS_FILE_NAME,
    _infer_table_type,
    _layer_from_table_name,
    _normalize_catalog_code,
    _split_catalog_payloads,
    build_business_semantics_catalog_from_inspection,
    build_initial_business_semantics_catalog,
    catalog_mapping_for_model,
    load_business_semantics_catalog,
    write_initial_business_semantics_catalog,
)
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    asset_role_for_layer,
    business_semantics_paths,
    load_model_metadata,
)

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

from dw_refactor_agent.assessment.llm.model_metadata_catalog import (
    _catalog_model_payload,
    catalog_discovery_model_mapping,
)
from dw_refactor_agent.assessment.llm.model_metadata_updates import (
    _existing_model_data,
    _inspection_resolution_is_eligible,
    _layer_resolution_for_model,
    _validate_write_scope,
)


@dataclass
class GenerateModelMetadataPlan:
    model_metadata: dict[str, dict[str, Any]]
    model_paths: dict[str, Path]
    model_updates: list[dict[str, Any]]
    planned_deleted_model_files: list[str]


def _catalog_table_assets(project: str) -> dict[str, TableAsset]:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = project_root() / project_cfg["dir"]
    return build_asset_catalog(
        [],
        load_model_metadata(project),
        project_dir,
    ).tables


def _project_dir(project: str) -> Path:
    project_cfg = PROJECT_CONFIG[project]
    return project_root() / project_cfg["dir"]


def _model_roots(project: str) -> list[Path]:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = _project_dir(project)
    catalog = str(project_cfg.get("catalog") or "internal")
    database = str(project_cfg.get("db") or "")
    return [
        project_dir / "ods" / "models" / catalog / database,
        project_dir / "mid" / "models",
        project_dir / "ads" / "models",
    ]


def _model_files(project: str) -> list[Path]:
    files: list[Path] = []
    for root in _model_roots(project):
        if root.exists():
            files.extend(sorted(root.rglob("*.yaml")))
    return sorted(files)


def _generated_model_path_for_table(
    project: str,
    table_name: str,
    layer: str | None,
) -> Path:
    project_cfg = PROJECT_CONFIG[project]
    project_dir = _project_dir(project)
    catalog = str(project_cfg.get("catalog") or "internal")
    database = str(project_cfg.get("db") or "")
    filename = f"{table_name}.yaml"
    role = asset_role_for_layer(layer)
    if role == "ods":
        return project_dir / "ods" / "models" / catalog / database / filename
    if role in {"mid", "ads"}:
        return project_dir / role / "models" / filename
    return project_dir / "mid" / "models" / filename


def _generate_model_table_assets(project: str) -> dict[str, TableAsset]:
    return build_asset_catalog(
        [],
        {},
        _project_dir(project),
        include_models=False,
    ).tables


def _ensure_metadata_catalog_skeleton(
    project: str,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    init_result = write_initial_business_semantics_catalog(
        project,
        overwrite=False,
        dry_run=dry_run,
    )
    written_names = sorted(init_result.get("written_names") or [])
    catalog = init_result.get("catalog") or load_business_semantics_catalog(
        project
    )
    report = {
        "catalog_initialized": bool(written_names),
        "catalog_init_written_names": [] if dry_run else written_names,
        "planned_catalog_written_names": written_names if dry_run else [],
    }
    return catalog, report


def _generate_metadata_catalog_for_plan(
    project: str,
    *,
    dry_run: bool,
    update_catalog: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if update_catalog:
        return _ensure_metadata_catalog_skeleton(project, dry_run=dry_run)

    catalog = load_business_semantics_catalog(project)
    if not catalog:
        catalog = build_initial_business_semantics_catalog(
            project,
            base_catalog={},
        )
    return catalog, {
        "catalog_initialized": False,
        "catalog_init_written_names": [],
        "planned_catalog_written_names": [],
    }


def _catalog_entries_by_code(
    catalog: dict[str, Any],
    key: str,
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for entry in catalog.get(key) or []:
        if not isinstance(entry, dict):
            continue
        raw_code = str(entry.get("code") or "").strip()
        canonical_code = _normalize_catalog_code(raw_code)
        if not canonical_code:
            continue
        normalized = dict(entry)
        normalized["code"] = raw_code
        normalized.pop("tables", None)
        entries[canonical_code] = normalized
    return entries


def _catalog_entry_changes(
    base_catalog: dict[str, Any],
    candidate_catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    changes = []
    for section in ("business_processes", "semantic_subjects"):
        before = _catalog_entries_by_code(base_catalog, section)
        after = _catalog_entries_by_code(candidate_catalog, section)
        for code, entry in sorted(after.items()):
            previous = before.get(code)
            if previous is None:
                changes.append(
                    {
                        "section": section,
                        "action": "add",
                        "code": code,
                        "entry": entry,
                    }
                )
            elif previous != entry:
                changes.append(
                    {
                        "section": section,
                        "action": "update",
                        "code": code,
                        "previous": previous,
                        "entry": entry,
                    }
                )
    return changes


def _empty_catalog_update_report() -> dict[str, Any]:
    return {
        "catalog_update": None,
        "catalog_change_count": 0,
        "catalog_updates": [],
        "planned_catalog_updates": [],
    }


def _resolved_catalog_results_from_inspection_results(
    results: list[TableInspectResult],
    *,
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
) -> list[TableInspectResult]:
    resolved_results = []
    for result in results or []:
        resolution = _layer_resolution_for_model(
            result,
            existing_model=model_metadata.get(result.table_name, {}),
            policy=resolution_policy,
        )
        if not _inspection_resolution_is_eligible(result, resolution):
            continue
        resolved = replace(
            result,
            inferred_layer=resolution.applied_layer,
            table_type=resolution.table_type,
        )
        if resolved.table_type not in {"fact", "dimension"}:
            continue
        resolved_results.append(resolved)
    return resolved_results


def _resolved_catalog_results_from_llm_result(
    llm_result: dict[str, Any],
    *,
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
) -> list[TableInspectResult]:
    results = []
    for item in llm_result.get("tables") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() == "blocked":
            continue
        results.append(inspect_dict_to_result(item))
    return _resolved_catalog_results_from_inspection_results(
        results,
        model_metadata=model_metadata,
        resolution_policy=resolution_policy,
    )


def _merge_llm_catalog_discoveries(
    project: str,
    *,
    llm_result: dict[str, Any] | None,
    inspection_results: list[TableInspectResult] | None = None,
    base_catalog: dict[str, Any],
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
    dry_run: bool,
) -> dict[str, Any]:
    if inspection_results is None and not llm_result:
        return _empty_catalog_update_report()

    if inspection_results is not None:
        catalog_results = _resolved_catalog_results_from_inspection_results(
            inspection_results,
            model_metadata=model_metadata,
            resolution_policy=resolution_policy,
        )
    else:
        catalog_results = _resolved_catalog_results_from_llm_result(
            llm_result or {},
            model_metadata=model_metadata,
            resolution_policy=resolution_policy,
        )
    candidate_catalog = build_business_semantics_catalog_from_inspection(
        project,
        catalog_results,
        base_catalog=base_catalog,
    )
    changes = _catalog_entry_changes(base_catalog, candidate_catalog)
    if not changes:
        return _empty_catalog_update_report()

    write_result = write_initial_business_semantics_catalog(
        project,
        overwrite=True,
        dry_run=dry_run,
        inspection_results=catalog_results,
    )
    written_names = sorted(write_result.get("written_names") or [])
    update = {
        "project": project,
        "path": write_result.get("path"),
        "paths": write_result.get("paths") or {},
        "changed": True,
        "updated": bool(write_result.get("updated")),
        "dry_run": dry_run,
        "change_count": len(changes),
        "changes": changes,
        "written_names": [] if dry_run else written_names,
        "planned_written_names": written_names if dry_run else [],
    }
    return {
        "catalog_update": update,
        "catalog_change_count": len(changes),
        "catalog_updates": [] if dry_run else changes,
        "planned_catalog_updates": changes if dry_run else [],
    }


def _catalog_candidate_from_llm_result(
    project: str,
    *,
    llm_result: dict[str, Any],
    base_catalog: dict[str, Any],
    model_metadata: dict[str, dict[str, Any]],
    resolution_policy: LayerResolutionPolicy,
    update_catalog: bool,
) -> tuple[dict[str, Any], list[TableInspectResult]]:
    resolved_results = _resolved_catalog_results_from_llm_result(
        llm_result,
        model_metadata=model_metadata,
        resolution_policy=resolution_policy,
    )
    if not update_catalog:
        return base_catalog, resolved_results
    candidate = build_business_semantics_catalog_from_inspection(
        project,
        resolved_results,
        base_catalog=base_catalog,
    )
    return candidate, resolved_results


def _apply_catalog_assignments_to_generated_models(
    project: str,
    model_metadata: dict[str, dict[str, Any]],
    *,
    catalog: dict[str, Any],
    results: list[TableInspectResult],
) -> dict[str, dict[str, Any]]:
    updated_models = {
        table_name: dict(metadata)
        for table_name, metadata in model_metadata.items()
    }
    for result in results:
        existing = updated_models.get(result.table_name)
        if existing is None:
            continue
        mapping = catalog_discovery_model_mapping(
            project,
            result,
            catalog,
            existing,
        )
        if not mapping:
            continue
        updated_models[result.table_name] = _catalog_model_payload(
            table_name=result.table_name,
            existing=existing,
            mapping=mapping,
        )
    return updated_models


def _asset_role_from_generate_asset(
    project: str,
    asset: TableAsset,
) -> str:
    ddl_path = asset.ddl.path if asset.ddl else None
    if not ddl_path:
        return ""
    try:
        parts = Path(ddl_path).relative_to(_project_dir(project)).parts
    except ValueError:
        return ""
    if (
        len(parts) >= 2
        and parts[1] == "ddl"
        and parts[0]
        in {
            "ods",
            "mid",
            "ads",
        }
    ):
        return parts[0]
    return ""


def _generate_asset_role_layer(asset_role: str) -> str:
    if asset_role == "ods":
        return "ODS"
    if asset_role == "ads":
        return "ADS"
    if asset_role == "mid":
        return "DWD"
    return ""


def _generate_model_mapping(
    catalog: dict[str, Any],
    table_name: str,
    *,
    asset: dict[str, Any] | None = None,
    asset_role: str = "",
) -> dict[str, Any]:
    mapping = catalog_mapping_for_model(catalog, table_name, {})
    asset_layer = _generate_asset_role_layer(asset_role)
    mapped_layer = str(mapping.get("layer") or "").upper()
    name_layer = _layer_from_table_name(table_name)
    if mapped_layer == "OTHER":
        mapped_layer = ""
    if name_layer == "OTHER":
        name_layer = ""
    if asset_layer in {"ODS", "ADS"}:
        layer = asset_layer
    else:
        layer = mapped_layer or name_layer or asset_layer or "OTHER"
    table_type = str(
        mapping.get("table_type") or _infer_table_type(table_name, layer)
    ).strip()
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name=table_name,
            fallback_layer=layer,
            fallback_table_type=table_type,
            policy=LayerResolutionPolicy(
                mode="generate",
                candidate_layers=("DWD", "DWS", "DIM"),
                fixed_layer=layer if layer in {"ODS", "ADS"} else "",
                fallback_source="direct_rule",
            ),
        )
    )
    layer = resolution.applied_layer
    table_type = resolution.table_type
    execution = infer_execution_mapping(
        table_name,
        asset or {},
        layer=layer,
    )
    materialized = str(execution.get("materialized") or "").strip()
    mapping.update(
        {
            "table": table_name,
            "layer": layer,
            "table_type": table_type or "other",
            "materialized": materialized,
            "execution": execution,
        }
    )
    return mapping


def _generate_model_update_payload(
    *,
    table_name: str,
    path: Path,
    previous: dict[str, Any],
    updated: dict[str, Any],
    dry_run: bool,
    write_scope: str,
    source: str = "direct_generation",
) -> dict[str, Any]:
    business_changed = any(
        updated.get(key) != previous.get(key)
        for key in (
            "data_domain",
            "business_area",
            "business_process",
            "semantic_subject",
            "dimension_role",
            "dimension_content_type",
        )
    )
    changed = updated != previous
    return {
        "table": table_name,
        "path": str(path),
        "status": "passed",
        "changed": changed,
        "metadata_changed": any(
            updated.get(key) != previous.get(key)
            for key in ("layer", "table_type")
        ),
        "business_changed": business_changed,
        "metric_changed": False,
        "grain_changed": False,
        "updated": bool(changed and not dry_run),
        "write_scope": write_scope,
        "source": source,
        "previous_layer": previous.get("layer"),
        "layer": updated.get("layer"),
        "previous_table_type": previous.get("table_type"),
        "table_type": updated.get("table_type"),
        "previous_data_domain": previous.get("data_domain"),
        "data_domain": updated.get("data_domain"),
        "previous_business_area": previous.get("business_area"),
        "business_area": updated.get("business_area"),
        "business_process": updated.get("business_process"),
        "semantic_subject": updated.get("semantic_subject"),
        "dimension_role": updated.get("dimension_role"),
        "dimension_content_type": updated.get("dimension_content_type"),
    }


def plan_generate_model_metadata(
    project: str,
    catalog: dict[str, Any],
    *,
    replace_existing_models: bool,
    write_scope: str,
) -> GenerateModelMetadataPlan:
    write_scope = _validate_write_scope(write_scope)
    if write_scope not in {"all", "table", "business"}:
        raise ValueError("generate 仅支持 write_scope=all/table/business")
    if replace_existing_models is not True:
        raise ValueError(
            "generate 冷启动必须替换现有 models，不能读取旧 model YAML"
        )

    model_files = _model_files(project)
    planned_deleted_model_files = [str(path) for path in model_files]
    model_metadata: dict[str, dict[str, Any]] = {}
    model_paths: dict[str, Path] = {}
    model_updates = []
    for table_name, asset in sorted(
        _generate_model_table_assets(project).items()
    ):
        if not asset.ddl or not asset.ddl.exists:
            continue
        mapping = _generate_model_mapping(
            catalog,
            table_name,
            asset=asset,
            asset_role=_asset_role_from_generate_asset(project, asset),
        )
        path = _generated_model_path_for_table(
            project,
            table_name,
            mapping.get("layer"),
        )
        existing: dict[str, Any] = {}
        updated = _catalog_model_payload(
            table_name=table_name,
            existing=existing,
            mapping=mapping,
        )
        model_metadata[table_name] = updated
        model_paths[table_name] = path
        model_updates.append(
            _generate_model_update_payload(
                table_name=table_name,
                path=path,
                previous=dict(existing),
                updated=updated,
                dry_run=True,
                write_scope=write_scope,
            )
        )
    return GenerateModelMetadataPlan(
        model_metadata=model_metadata,
        model_paths=model_paths,
        model_updates=model_updates,
        planned_deleted_model_files=planned_deleted_model_files,
    )


def _write_generated_model_metadata(
    project: str,
    plan: MetadataFlowPlan,
    final_model_metadata: dict[str, dict[str, Any]],
    *,
    dry_run: bool,
    delete_existing: bool,
    refinement_updates: list[dict[str, Any]] | None = None,
    additional_rendered_files: dict[Path, str] | None = None,
    additional_deleted_files: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    existing_model_files = _model_files(project) if delete_existing else []
    deleted_model_files: list[str] = []

    refinements_by_table = {
        str(update.get("table") or ""): update
        for update in refinement_updates or []
        if isinstance(update, dict) and str(update.get("table") or "")
    }
    model_updates = []
    rendered_models: list[tuple[Path, str]] = []
    for table_name, metadata in sorted(final_model_metadata.items()):
        path = plan.write_targets.model_paths.get(table_name)
        if path is None:
            path = _generated_model_path_for_table(
                project,
                table_name,
                metadata.get("layer"),
            )
        previous = {} if delete_existing else _existing_model_data(path)
        update = _generate_model_update_payload(
            table_name=table_name,
            path=path,
            previous=dict(previous),
            updated=metadata,
            dry_run=dry_run,
            write_scope=plan.write_scope,
        )
        if table_name in refinements_by_table:
            update = _merge_final_update_with_refinement(
                update,
                refinements_by_table[table_name],
            )
        if update["changed"] and not dry_run:
            rendered_models.append(
                (
                    path,
                    yaml.safe_dump(
                        metadata,
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                )
            )
        model_updates.append(update)

    if not dry_run:
        rendered_files = dict(additional_rendered_files or {})
        rendered_files.update(dict(rendered_models))
        target_paths = {
            path.resolve() for path in plan.write_targets.model_paths.values()
        }
        obsolete_model_files = [
            path
            for path in existing_model_files
            if path.resolve() not in target_paths
        ]
        deleted_model_files.extend(str(path) for path in existing_model_files)
        _transactional_publish_files(
            rendered_files,
            delete_paths=(
                obsolete_model_files + list(additional_deleted_files or [])
            ),
        )

        import dw_refactor_agent.config as _config

        _config.clear_model_metadata_cache()
        if additional_rendered_files or additional_deleted_files:
            _config.clear_business_semantics_cache()
            _config.clear_naming_config_cache()

    return model_updates, deleted_model_files


def _transactional_publish_files(
    rendered_files: dict[Path, str],
    *,
    delete_paths: list[Path],
) -> None:
    """Publish a generated file set with rollback on ordinary exceptions."""
    token = uuid4().hex
    staged_files: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed_paths: list[Path] = []
    publication_succeeded = False
    rendered_paths = set(rendered_files)
    deletion_targets = [
        path for path in delete_paths if path not in rendered_paths
    ]
    try:
        for path, rendered in sorted(
            rendered_files.items(), key=lambda item: str(item[0])
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            staged_path = path.with_name(f".{path.name}.{token}.staged")
            staged_path.write_text(rendered, encoding=TEXT_ENCODING)
            staged_files.append((staged_path, path))

        targets = [path for _staged, path in staged_files]
        targets.extend(path for path in deletion_targets if path.exists())
        for path in targets:
            if not path.exists():
                continue
            backup_path = path.with_name(f".{path.name}.{token}.backup")
            path.replace(backup_path)
            backups.append((backup_path, path))

        for staged_path, path in staged_files:
            staged_path.replace(path)
            installed_paths.append(path)
        publication_succeeded = True
    except Exception:
        for path in reversed(installed_paths):
            if path.exists():
                path.unlink()
        for backup_path, path in reversed(backups):
            if path.exists():
                path.unlink()
            if backup_path.exists():
                backup_path.replace(path)
        raise
    finally:
        for staged_path, _path in staged_files:
            if staged_path.exists():
                with suppress(OSError):
                    staged_path.unlink()
        if publication_succeeded:
            for backup_path, _path in backups:
                if backup_path.exists():
                    with suppress(OSError):
                        backup_path.unlink()


def _render_generated_catalog_files(
    project: str,
    catalog: dict[str, Any],
    *,
    enabled: bool,
) -> tuple[dict[Path, str], list[Path], list[str]]:
    if not enabled:
        return {}, [], []
    paths = business_semantics_paths(project)
    payloads = _split_catalog_payloads(catalog)
    rendered_files: dict[Path, str] = {}
    written_names = []
    for name, path in sorted(paths.items()):
        rendered = yaml.safe_dump(
            payloads[name],
            allow_unicode=True,
            sort_keys=False,
        )
        existing = (
            path.read_text(encoding=TEXT_ENCODING) if path.exists() else None
        )
        if existing == rendered:
            continue
        rendered_files[path] = rendered
        written_names.append(name)
    legacy_path = (
        next(iter(paths.values())).parent / LEGACY_BUSINESS_SEMANTICS_FILE_NAME
    )
    deleted_files = [legacy_path] if legacy_path.exists() else []
    return rendered_files, deleted_files, written_names


def _published_catalog_reports(
    catalog_report: dict[str, Any],
    catalog_update_report: dict[str, Any],
    *,
    written_names: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog_report = dict(catalog_report)
    planned_init = set(
        catalog_report.get("planned_catalog_written_names") or []
    )
    catalog_report["catalog_init_written_names"] = [
        name for name in written_names if name in planned_init
    ]
    catalog_report["planned_catalog_written_names"] = []

    catalog_update_report = dict(catalog_update_report)
    update = catalog_update_report.get("catalog_update")
    if isinstance(update, dict):
        update = dict(update)
        planned_names = set(update.get("planned_written_names") or [])
        update["dry_run"] = False
        update["updated"] = True
        update["written_names"] = [
            name for name in written_names if name in planned_names
        ]
        update["planned_written_names"] = []
        catalog_update_report["catalog_update"] = update
        catalog_update_report["catalog_updates"] = list(
            catalog_update_report.get("planned_catalog_updates") or []
        )
        catalog_update_report["planned_catalog_updates"] = []
    return catalog_report, catalog_update_report


def _merge_final_update_with_refinement(
    final_update: dict[str, Any],
    refinement_update: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(refinement_update)
    merged.pop("model_metadata", None)
    merged["path"] = final_update.get("path")
    merged["changed"] = bool(
        final_update.get("changed") or refinement_update.get("changed")
    )
    merged["metadata_changed"] = bool(
        final_update.get("metadata_changed")
        or refinement_update.get("metadata_changed")
    )
    merged["business_changed"] = bool(
        final_update.get("business_changed")
        or refinement_update.get("business_changed")
    )
    merged["updated"] = final_update.get("updated", False)
    merged["source"] = "llm_refinement"
    for key in (
        "write_scope",
        "layer",
        "table_type",
        "data_domain",
        "business_area",
        "business_process",
        "semantic_subject",
        "dimension_role",
        "dimension_content_type",
    ):
        if key in final_update:
            merged[key] = final_update[key]
    return merged


def _final_model_metadata_with_refinements(
    base_model_metadata: dict[str, dict[str, Any]],
    llm_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    final_model_metadata = {
        table_name: dict(metadata)
        for table_name, metadata in base_model_metadata.items()
    }
    for update in llm_result.get("model_updates") or []:
        table_name = str(update.get("table") or "").strip()
        if not table_name:
            continue
        refined_metadata = update.get("model_metadata")
        if not isinstance(refined_metadata, dict):
            continue
        if update.get("status") == "blocked" and update.get("reason") not in {
            "validation_blocked_schema_migration",
            "validation_blocked_table_metadata_only",
        }:
            continue
        final_model_metadata[table_name] = dict(refined_metadata)
    return final_model_metadata


def _strip_internal_model_metadata(result: dict[str, Any] | None) -> None:
    if not result:
        return
    for update in result.get("model_updates") or []:
        if isinstance(update, dict):
            update.pop("model_metadata", None)
