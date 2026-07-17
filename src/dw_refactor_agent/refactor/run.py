#!/usr/bin/env python3
"""Refactor run session CLI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import dw_refactor_agent.assessment.assess_middle_layer as assess_module
import dw_refactor_agent.config as config
import dw_refactor_agent.lineage.lineage_extractor as lineage_extractor_module
import dw_refactor_agent.refactor.change_analysis as change_analysis_module
import dw_refactor_agent.refactor.shadow_run as shadow_run_module
from dw_refactor_agent.assessment.assess_middle_layer import assess
from dw_refactor_agent.config import core as config_core
from dw_refactor_agent.execution.schedule_cli import add_schedule_parser
from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
)
from dw_refactor_agent.lineage.identifiers import identifier_match_key
from dw_refactor_agent.refactor.artifact_contract import (
    ArtifactFormatError,
    atomic_write_json,
    read_json_object,
    sha256_json,
)
from dw_refactor_agent.refactor.change_analysis import (
    build_change_analysis,
    changed_files_since_head,
)
from dw_refactor_agent.refactor.compare import compare_shadow_results
from dw_refactor_agent.refactor.incremental_lineage import (
    build_lineage_artifacts,
)
from dw_refactor_agent.refactor.issue_diff import diff_assess_results
from dw_refactor_agent.refactor.plan_artifact import (
    StalePlanError,
    analysis_input_fingerprints,
    require_fresh_plan,
    validate_analysis_input_fingerprints,
    write_verification_plan,
)
from dw_refactor_agent.refactor.qa_pool import (
    configured_qa_pool,
    inspect_qa_slot,
    parse_age,
    parse_created_before,
    qa_server_epoch,
    release_qa_slot,
    select_cleanup_slots,
    validate_qa_identifier,
)
from dw_refactor_agent.refactor.semantic_mode import resolve_semantic_modes
from dw_refactor_agent.refactor.session import (
    artifact_path,
    create_run_manifest,
    load_historical_manifests,
    load_manifest,
    resolve_manifest_path,
    write_manifest,
)
from dw_refactor_agent.refactor.shadow_run import run_shadow_plan
from dw_refactor_agent.refactor.verification_plan import (
    build_verification_plan,
)
from dw_refactor_agent.refactor.workspace_snapshot import workspace_fingerprint

NO_CHANGES_SCORE_REASON = (
    "No relevant file, lineage, DDL, or job changes were detected; scoped "
    "assessment score is not applicable."
)
_MISSING = object()


def _now() -> datetime:
    return datetime.now().astimezone()


def _write_json(path: Path, data: dict) -> None:
    atomic_write_json(Path(path), data)


def _read_json(path: Path) -> dict:
    path = Path(path)
    return read_json_object(path, path.name)


def _load_baseline_schedule(
    manifest_path: Path, manifest: dict
) -> ScheduleGraph:
    payload = _read_json(artifact_path(manifest_path, "baseline_schedule"))
    expected_digest = manifest.get("baseline_schedule_sha256")
    actual_digest = sha256_json(payload)
    if expected_digest != actual_digest:
        raise ArtifactFormatError(
            "baseline schedule DAG fingerprint mismatch; start a new "
            "refactor run"
        )
    return ScheduleGraph.from_dict(
        payload, expected_project=manifest["project"]
    )


def _sorted_nonempty_strings(values) -> list[str]:
    return sorted(
        {str(value).strip() for value in values or [] if str(value).strip()}
    )


def _scope_values(scope: dict | None, *keys: str) -> list[str]:
    scope = scope or {}
    for key in keys:
        values = _sorted_nonempty_strings(scope.get(key))
        if values:
            return values
    return []


def _first_scope_values(
    scopes: list[dict | None],
    *keys: str,
) -> list[str]:
    for scope in scopes:
        values = _scope_values(scope, *keys)
        if values:
            return values
    return []


def _refactor_scope_metadata(
    assess_result: dict,
    change_analysis: dict | None,
) -> dict:
    scope_plan = assess_result.get("scope_plan") or {}
    scope_sources = [
        (change_analysis or {}).get("affected_scope"),
        scope_plan.get("base_scope"),
    ]
    return {
        "type": "refactor_scope",
        "tables": _first_scope_values(
            scope_sources,
            "assessment_tables",
            "tables",
        ),
        "tasks": _first_scope_values(
            scope_sources,
            "assessment_tasks",
            "tasks",
        ),
    }


def _mark_assessment_full(assess_result: dict) -> dict:
    marked = deepcopy(assess_result)
    marked["assessment_mode"] = "full"
    marked["score_semantics"] = "project_global"
    marked["scope"] = {"type": "project"}
    return marked


def _mark_assessment_scoped(
    assess_result: dict,
    change_analysis: dict | None,
) -> dict:
    marked = deepcopy(assess_result)
    marked["assessment_mode"] = "scoped"
    marked["score_semantics"] = "scope_local"
    marked["scope"] = _refactor_scope_metadata(
        marked,
        change_analysis,
    )
    return marked


def _git_cmd(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_info(root: Path) -> dict:
    branch = _git_cmd(root, "branch", "--show-current")
    head = _git_cmd(root, "rev-parse", "--short", "HEAD")
    dirty = bool(_git_cmd(root, "status", "--short"))
    return {"branch": branch, "head": head, "dirty": dirty}


def _project_dir(project: str) -> str:
    return config.PROJECT_CONFIG[project]["dir"]


def _remember_attr(states: list[tuple[object, str, object]], module, name):
    states.append((module, name, module.__dict__.get(name, _MISSING)))


def _set_attr(states: list[tuple[object, str, object]], module, name, value):
    _remember_attr(states, module, name)
    setattr(module, name, value)


def _restore_attrs(states: list[tuple[object, str, object]]) -> None:
    for module, name, old_value in reversed(states):
        if old_value is _MISSING:
            module.__dict__.pop(name, None)
        else:
            setattr(module, name, old_value)


def _clear_config_caches() -> None:
    config.clear_model_metadata_cache()
    config.clear_naming_config_cache()
    config.clear_business_semantics_cache()


@contextmanager
def _project_root_context(root: Path):
    """Temporarily run refactor workflow helpers against one repo root."""
    root = Path(root).resolve()
    project_config = config_core.load_project_config(root)
    if not project_config:
        warehouses_root = root / "warehouses"
        if not root.exists():
            raise SystemExit(f"项目根目录不存在: {root}")
        if not warehouses_root.exists():
            raise SystemExit(f"项目根目录缺少 warehouses 目录: {root}")
        raise SystemExit(
            "项目根目录未找到任何 warehouse.yaml: "
            f"{warehouses_root}/*/warehouse.yaml"
        )

    states = []
    try:
        _set_attr(states, config_core, "PROJECT_ROOT", root)
        _set_attr(states, config_core, "WAREHOUSES_ROOT", root / "warehouses")
        _set_attr(states, config_core, "PROJECT_CONFIG", project_config)
        _set_attr(states, config_core, "PROJECT_MAP", project_config)

        for module in (config,):
            _set_attr(states, module, "PROJECT_ROOT", root)
            _set_attr(states, module, "WAREHOUSES_ROOT", root / "warehouses")
            _set_attr(states, module, "PROJECT_CONFIG", project_config)
            _set_attr(states, module, "PROJECT_MAP", project_config)

        for module in (lineage_extractor_module, change_analysis_module):
            _set_attr(states, module, "PROJECT_CONFIG", project_config)

        _set_attr(states, assess_module, "PROJECT_ROOT", root)
        _set_attr(states, assess_module, "PROJECT_CONFIG", project_config)
        _set_attr(states, shadow_run_module, "PROJECT_ROOT", root)

        _clear_config_caches()
        yield root
    finally:
        _restore_attrs(states)
        _clear_config_caches()


def _root_from_manifest(manifest: dict, manifest_path: Path) -> Path:
    raw_root = str(manifest.get("root") or "").strip()
    if raw_root:
        return Path(raw_root).expanduser().resolve()

    resolved_manifest = Path(manifest_path).resolve()
    for parent in resolved_manifest.parents:
        if (parent / "warehouses").exists():
            return parent
    return config.PROJECT_ROOT


def _short_name(name: str) -> str:
    return str(name or "").strip().strip("`").split(".")[-1]


def _rename_mapping_from_ddl_changes(
    ddl_changes: list[dict],
) -> dict[str, str]:
    mapping = {}
    for change in ddl_changes or []:
        if change.get("change_type") != "RENAME":
            continue
        old_name = _short_name(change.get("old_name"))
        new_name = _short_name(change.get("new_name"))
        if old_name and new_name:
            mapping[old_name] = new_name
    return dict(sorted(mapping.items()))


def _with_rename_mapping(
    change_analysis: dict,
    ddl_changes: list[dict],
) -> dict:
    rename_mapping = _rename_mapping_from_ddl_changes(ddl_changes)
    if not rename_mapping:
        return change_analysis
    enriched = dict(change_analysis)
    enriched["rename_mapping"] = rename_mapping
    return enriched


def _has_any_items(mapping: dict, keys: tuple[str, ...]) -> bool:
    return any(bool(mapping.get(key)) for key in keys)


def _plan_changes(plan: dict) -> dict:
    return plan.get("changes") or {}


def _change_analysis_has_work(change_analysis: dict) -> bool:
    changed_assets = change_analysis.get("changed_assets") or {}
    affected_scope = change_analysis.get("affected_scope") or {}
    lineage_diff = change_analysis.get("lineage_diff") or {}
    return bool(
        change_analysis.get("changed_files")
        or _has_any_items(
            changed_assets,
            ("ddl_tables", "task_jobs", "model_tables", "config_files"),
        )
        or _has_any_items(
            affected_scope,
            (
                "direct_tables",
                "downstream_tables",
                "anchor_tables",
                "assessment_tables",
                "assessment_tasks",
                "global_dimensions",
            ),
        )
        or _has_any_items(
            lineage_diff,
            ("added_edges", "removed_edges", "changed_tables"),
        )
    )


def _verification_plan_has_work(plan: dict) -> bool:
    changes = _plan_changes(plan)
    verification = plan.get("verification") or {}
    return bool(
        _has_any_items(
            changes,
            ("modified_jobs", "ddl_tables", "model_tables", "config_files"),
        )
        or plan.get("ddl_changes")
        or plan.get("jobs_to_run")
        or _has_any_items(
            verification,
            (
                "anchor_tables",
                "checks",
            ),
        )
    )


def _has_no_refactor_changes(change_analysis: dict, plan: dict) -> bool:
    return not _change_analysis_has_work(
        change_analysis
    ) and not _verification_plan_has_work(plan)


def _not_applicable_dimension(dimension: dict) -> dict:
    marked = dict(dimension)
    marked["score"] = None
    marked["status"] = "not_applicable"
    marked["score_status"] = "not_applicable"
    summary = dict(marked.get("summary") or {})
    summary["status"] = "not_applicable"
    summary["reason"] = NO_CHANGES_SCORE_REASON
    marked["summary"] = summary
    return marked


def _mark_assessment_no_changes(assess_result: dict) -> dict:
    marked = deepcopy(assess_result)
    marked["status"] = "no_changes"
    marked["overall_score"] = None
    marked["score_status"] = "not_applicable"
    marked["assessment_mode"] = "no_changes"
    marked["score_semantics"] = "not_applicable"
    marked["status_reason"] = NO_CHANGES_SCORE_REASON
    marked["dimensions"] = {
        name: _not_applicable_dimension(dimension)
        for name, dimension in (marked.get("dimensions") or {}).items()
    }

    scope_plan = marked.get("scope_plan")
    if scope_plan:
        marked_scope = dict(scope_plan)
        marked_scope["mode"] = "no_changes"
        marked_scope["score_semantics"] = "not_applicable"
        marked_scope["status"] = "no_changes"
        marked_scope["reason"] = [NO_CHANGES_SCORE_REASON]
        marked["scope_plan"] = marked_scope
    return marked


def _start(args) -> int:
    root = Path(args.root).expanduser().resolve()
    with _project_root_context(root) as repo_root:
        if args.project not in config.PROJECT_CONFIG:
            choices = ", ".join(sorted(config.PROJECT_CONFIG)) or "(none)"
            raise SystemExit(f"未知项目: {args.project}; 可选项目: {choices}")
        manifest_path, manifest = create_run_manifest(
            repo_root,
            args.project,
            now=_now(),
            git_info=_git_info(repo_root),
        )
        lineage_path = artifact_path(manifest_path, "baseline_lineage")
        cache_path = artifact_path(manifest_path, "baseline_task_cache")
        lineage_result = build_lineage_artifacts(
            args.project,
            lineage_path,
            cache_path,
        )
        assess_result = assess(
            args.project,
            lineage_data=lineage_result["lineage"],
        )
        assess_result = _mark_assessment_full(assess_result)
        _write_json(
            artifact_path(manifest_path, "baseline_assess"), assess_result
        )
    print(f"Run manifest: {manifest_path}")
    return 0


def _manifest_path_from_args(args) -> Path:
    return resolve_manifest_path(
        manifest_path=getattr(args, "manifest", None),
        run_id=getattr(args, "run", None),
        root=config.PROJECT_ROOT,
    )


def _previous_cache_path(manifest_path: Path) -> Path:
    current_cache = artifact_path(manifest_path, "current_task_cache")
    if current_cache.exists():
        return current_cache
    return artifact_path(manifest_path, "baseline_task_cache")


def _semantic_resolution_for_run(
    manifest_path: Path,
    manifest: dict,
    *,
    repo_root: Path,
    change_analysis: dict,
    baseline_lineage: dict,
    current_lineage: dict,
):
    history, diagnostics = load_historical_manifests(manifest_path, manifest)
    for diagnostic in diagnostics:
        print(f"Warning: {diagnostic}", file=sys.stderr)
    return resolve_semantic_modes(
        project=manifest["project"],
        project_dir=_project_dir(manifest["project"]),
        change_analysis=change_analysis,
        baseline_lineage=baseline_lineage,
        current_lineage=current_lineage,
        base_ref=manifest.get("base_git", {}).get("head") or "HEAD",
        repo_root=repo_root,
        current_manifest=manifest,
        historical_manifests=history,
    )


def _merge_inherited_declarations(
    manifest: dict, inherited_declarations: dict
) -> dict:
    if not inherited_declarations:
        return manifest
    updated = deepcopy(manifest)
    intent = updated.setdefault("verification_intent", {})
    semantic_modes = intent.setdefault("semantic_modes", {})
    for table, declaration in inherited_declarations.items():
        semantic_modes.setdefault(table, declaration)
    return updated


def _analysis_snapshot(
    *,
    manifest: dict,
    repo_root: Path,
    baseline_lineage: dict,
    current_lineage: dict,
    change_analysis: dict,
    partition: str | None,
    workspace_digest: str | None = None,
) -> dict:
    return {
        "partition": partition,
        "workspace_fingerprint": workspace_digest
        or workspace_fingerprint(repo_root, manifest["project"]),
        "analysis_inputs": analysis_input_fingerprints(
            manifest=manifest,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            change_analysis=change_analysis,
        ),
    }


def _require_snapshot_workspace(
    snapshot: dict, *, repo_root: Path, project: str
) -> str:
    expected = snapshot.get("workspace_fingerprint")
    actual = workspace_fingerprint(repo_root, project)
    if expected != actual:
        raise StalePlanError(
            "stale_plan: workspace changed after analyze; run analyze again"
        )
    return actual


def _invalidate_verification_outputs(
    manifest_path: Path, manifest: dict
) -> None:
    """Fail closed before publishing a replacement verification plan."""
    run_root = Path(manifest_path).parent
    for artifact_key in (
        "verification_plan",
        "shadow_run_result",
        "compare_result",
    ):
        relative_path = manifest["artifacts"].get(artifact_key)
        if relative_path is None:
            raise ArtifactFormatError(
                f"manifest.artifacts.{artifact_key} is required"
            )
        path = run_root / relative_path
        if path.exists():
            path.unlink()


def _build_plan_for_run(
    manifest_path: Path,
    manifest: dict,
    *,
    repo_root: Path,
    change_analysis: dict,
    baseline_lineage: dict,
    current_lineage: dict,
    baseline_schedule: ScheduleGraph,
    partition: str | None,
) -> tuple[dict, dict]:
    semantic_resolution = _semantic_resolution_for_run(
        manifest_path,
        manifest,
        repo_root=repo_root,
        change_analysis=change_analysis,
        baseline_lineage=baseline_lineage,
        current_lineage=current_lineage,
    )
    try:
        current_schedule = ScheduleGraph.load_for_project(
            manifest["project"], root=repo_root
        )
        task_names = {
            path.stem
            for path in config.iter_project_task_files(
                manifest["project"], include_full_refresh=False
            )
        }
        task_keys = {identifier_match_key(job) for job in task_names}
        schedule_keys = {
            identifier_match_key(job) for job in current_schedule.jobs
        }
        missing_sql = sorted(
            job
            for job in current_schedule.jobs
            if identifier_match_key(job) not in task_keys
        )
        unscheduled = sorted(
            job
            for job in task_names
            if identifier_match_key(job) not in schedule_keys
        )
        if missing_sql or unscheduled:
            raise ValueError(
                "trusted schedule and task SQL universe differ: "
                f"schedule Jobs without SQL={missing_sql!r}, "
                f"unscheduled task Jobs={unscheduled!r}"
            )
        plan = build_verification_plan(
            manifest["project"],
            change_analysis,
            base_ref=manifest.get("base_git", {}).get("head"),
            repo_root=repo_root,
            lineage_data=current_lineage,
            baseline_lineage_data=baseline_lineage,
            schedule_graph=current_schedule,
            baseline_schedule_graph=baseline_schedule,
            strict_schedule=True,
            partition=partition,
            semantic_resolution=semantic_resolution,
        )
        if "execution_graph" not in plan:
            selected_jobs = [
                job["job"] for job in plan.get("jobs_to_run") or []
            ]
            plan["execution_graph"] = {
                "format_version": 1,
                "project": manifest["project"],
                "jobs": selected_jobs,
                "dependencies": current_schedule.selected_dependencies(
                    selected_jobs
                ),
            }
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    plan["run_id"] = manifest["run_id"]
    updated_manifest = _merge_inherited_declarations(
        manifest, semantic_resolution.inherited_declarations
    )
    if updated_manifest is not manifest:
        write_manifest(manifest_path, updated_manifest)
    return plan, updated_manifest


def _print_semantic_guidance(plan: dict, run_id: str) -> None:
    target_semantics = (plan.get("verification") or {}).get(
        "target_semantics"
    ) or {}
    unknown_tables = sorted(
        table
        for table, semantics in target_semantics.items()
        if semantics.get("resolved_mode") == "unknown"
    )
    if not unknown_tables:
        return
    for table in unknown_tables:
        print(f"\nWarning: {table} 无法自动确认语义。")
        print("  equivalent：预期新旧输出相同；比较本表")
        print("  changed：预期本表语义变化；验证下游边界")
        print("  unknown：暂不判断；验证下游并保留风险 warning")
        print(
            "  设置：dw-refactor semantic-mode set "
            f"--run {run_id} --table {table} --mode <mode>"
        )


def _analyze(args) -> int:
    manifest_path = _manifest_path_from_args(args)
    manifest = load_manifest(manifest_path)
    project = manifest["project"]
    repo_root = _root_from_manifest(manifest, manifest_path)

    with _project_root_context(repo_root) as repo_root:
        _invalidate_verification_outputs(manifest_path, manifest)
        current_lineage_path = artifact_path(manifest_path, "current_lineage")
        current_cache_path = artifact_path(manifest_path, "current_task_cache")
        lineage_result = build_lineage_artifacts(
            project,
            current_lineage_path,
            current_cache_path,
            previous_cache_path=_previous_cache_path(manifest_path),
        )

        baseline_lineage = _read_json(
            artifact_path(manifest_path, "baseline_lineage")
        )
        baseline_schedule = _load_baseline_schedule(manifest_path, manifest)
        current_lineage = lineage_result["lineage"]
        changed_files = changed_files_since_head(
            repo_root,
            manifest.get("base_git", {}).get("head", "HEAD"),
            _project_dir(project),
        )
        change_analysis = build_change_analysis(
            project,
            baseline_lineage,
            current_lineage,
            changed_files,
        )
        _write_json(
            artifact_path(manifest_path, "change_analysis"),
            change_analysis,
        )
        plan, manifest = _build_plan_for_run(
            manifest_path,
            manifest,
            repo_root=repo_root,
            change_analysis=change_analysis,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            baseline_schedule=baseline_schedule,
            partition=args.partition,
        )
        change_analysis = _with_rename_mapping(
            change_analysis,
            plan.get("ddl_changes") or [],
        )
        _write_json(
            artifact_path(manifest_path, "change_analysis"),
            change_analysis,
        )
        plan["analysis_snapshot"] = _analysis_snapshot(
            manifest=manifest,
            repo_root=repo_root,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            change_analysis=change_analysis,
            partition=args.partition,
        )

        current_assess = assess(
            project,
            lineage_data=current_lineage,
            change_analysis=change_analysis,
        )
        current_assess = _mark_assessment_scoped(
            current_assess,
            change_analysis,
        )
        if _has_no_refactor_changes(change_analysis, plan):
            current_assess = _mark_assessment_no_changes(current_assess)
        _write_json(
            artifact_path(manifest_path, "current_assess"), current_assess
        )
        baseline_assess = _read_json(
            artifact_path(manifest_path, "baseline_assess")
        )
        issue_diff = diff_assess_results(
            baseline_assess,
            current_assess,
            scope_plan=current_assess.get("scope_plan"),
            change_analysis=change_analysis,
            verification_plan=plan,
        )
        _write_json(artifact_path(manifest_path, "issue_diff"), issue_diff)
        plan = write_verification_plan(
            artifact_path(manifest_path, "verification_plan"), plan
        )
        _print_semantic_guidance(plan, manifest["run_id"])

    print(f"Analyze complete: {manifest_path}")
    return 0


def _shadow_run(args) -> int:
    manifest_path = _manifest_path_from_args(args)
    manifest = load_manifest(manifest_path)
    repo_root = _root_from_manifest(manifest, manifest_path)
    with _project_root_context(repo_root):
        plan_path = artifact_path(manifest_path, "verification_plan")
        try:
            persisted_plan = require_fresh_plan(
                plan_path,
                root=repo_root,
                project=manifest["project"],
            )
        except ArtifactFormatError as exc:
            raise SystemExit(str(exc)) from None
        result = run_shadow_plan(
            plan_path,
            artifact_path(manifest_path, "shadow_run_result"),
            provenance={
                "workspace_fingerprint": persisted_plan["analysis_snapshot"][
                    "workspace_fingerprint"
                ],
                "plan_fingerprint": persisted_plan["plan_fingerprint"],
            },
            dry_run=args.dry_run,
            timing_detail=args.timing_detail,
            parallel=args.parallel,
            batch_size=args.batch_size,
        )
    return 1 if result.get("status") == "failed" else 0


def _compare(args) -> int:
    manifest_path = _manifest_path_from_args(args)
    manifest = load_manifest(manifest_path)
    repo_root = _root_from_manifest(manifest, manifest_path)
    with _project_root_context(repo_root):
        plan_path = artifact_path(manifest_path, "verification_plan")
        try:
            require_fresh_plan(
                plan_path,
                root=repo_root,
                project=manifest["project"],
            )
            result = compare_shadow_results(
                plan_path,
                artifact_path(manifest_path, "shadow_run_result"),
                artifact_path(manifest_path, "compare_result"),
                method=args.method,
                sample=args.sample,
                precision=args.precision,
            )
        except ArtifactFormatError as exc:
            raise SystemExit(str(exc)) from None
    status = result["verification_status"]
    if status in {"passed", "passed_with_warnings"}:
        return 0
    if status == "inconclusive":
        return 2
    return 1


def _replan(
    manifest_path: Path,
    manifest: dict,
    partition: str | None,
    source_snapshot: dict,
) -> None:
    repo_root = _root_from_manifest(manifest, manifest_path)
    with _project_root_context(repo_root) as repo_root:
        _require_snapshot_workspace(
            source_snapshot,
            repo_root=repo_root,
            project=manifest["project"],
        )
        change_analysis = _read_json(
            artifact_path(manifest_path, "change_analysis")
        )
        baseline_lineage = _read_json(
            artifact_path(manifest_path, "baseline_lineage")
        )
        baseline_schedule = _load_baseline_schedule(manifest_path, manifest)
        current_lineage = _read_json(
            artifact_path(manifest_path, "current_lineage")
        )
        validate_analysis_input_fingerprints(
            source_snapshot,
            manifest=manifest,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            change_analysis=change_analysis,
            include_intent=False,
        )
        plan, updated_manifest = _build_plan_for_run(
            manifest_path,
            manifest,
            repo_root=repo_root,
            change_analysis=change_analysis,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            baseline_schedule=baseline_schedule,
            partition=partition,
        )
        workspace_digest = _require_snapshot_workspace(
            source_snapshot,
            repo_root=repo_root,
            project=manifest["project"],
        )
        plan["analysis_snapshot"] = _analysis_snapshot(
            manifest=updated_manifest,
            repo_root=repo_root,
            baseline_lineage=baseline_lineage,
            current_lineage=current_lineage,
            change_analysis=change_analysis,
            partition=partition,
            workspace_digest=workspace_digest,
        )
        write_verification_plan(
            artifact_path(manifest_path, "verification_plan"), plan
        )


def _semantic_mode_set(args) -> int:
    manifest_path = _manifest_path_from_args(args)
    manifest = load_manifest(manifest_path)
    repo_root = _root_from_manifest(manifest, manifest_path)
    with _project_root_context(repo_root):
        persisted_plan = require_fresh_plan(
            artifact_path(manifest_path, "verification_plan"),
            root=repo_root,
            project=manifest["project"],
        )
        target_semantics = (persisted_plan.get("verification") or {}).get(
            "target_semantics"
        ) or {}
        table_by_key = {
            str(table).casefold(): table for table in target_semantics
        }
        table = table_by_key.get(str(args.table).casefold())
        if table is None:
            raise SystemExit(
                f"table is not in affected semantic scope: {args.table}"
            )
        semantics = target_semantics[table]
        declaration = {
            "table_id": semantics["table_id"],
            "mode": args.mode,
            "semantic_context_fingerprint": semantics[
                "semantic_context_fingerprint"
            ],
            "confirmed_at": _now().isoformat(),
        }
        updated = deepcopy(manifest)
        intent = updated.setdefault("verification_intent", {})
        intent.setdefault("semantic_modes", {})[table] = declaration
        _invalidate_verification_outputs(manifest_path, manifest)
        write_manifest(manifest_path, updated)
        _replan(
            manifest_path,
            updated,
            persisted_plan["analysis_snapshot"].get("partition"),
            persisted_plan["analysis_snapshot"],
        )
    print(f"Semantic mode updated: {table}={args.mode}")
    return 0


def _add_manifest_selector(parser: argparse.ArgumentParser) -> None:
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--manifest")
    selector.add_argument("--run")


def inspect_configured_slots(*, project: str | None = None) -> list:
    """Inspect only databases explicitly listed in loaded project configs."""
    inspections = []
    owners_by_database = {}
    for project_name in sorted(config.PROJECT_CONFIG):
        if project is not None and project_name != project:
            continue
        project_config = config.PROJECT_CONFIG[project_name]
        fixture = project_config.get("fixture") or {}
        if str(fixture.get("execution") or "").casefold() == "disabled":
            continue
        try:
            pool = configured_qa_pool(project_name, project_config)
        except ValueError as exc:
            raise ArtifactFormatError(str(exc)) from exc
        for database in pool:
            database_key = database.casefold()
            previous_project = owners_by_database.setdefault(
                database_key, project_name
            )
            if previous_project != project_name:
                raise ArtifactFormatError(
                    f"QA database {database} is configured by multiple "
                    f"projects: {previous_project}, {project_name}"
                )
            inspections.append(inspect_qa_slot(project_name, database))
    return inspections


def _require_cleanup_project(project: str | None) -> None:
    if project is not None and project not in config.PROJECT_CONFIG:
        raise SystemExit(f"unknown project for cleanup: {project}")


def _print_slot(inspection, *, now_epoch: int) -> None:
    ownership = inspection.ownership
    run_id = ownership.run_id if ownership is not None else "-"
    execution_id = ownership.execution_id if ownership is not None else "-"
    claimed_at = ownership.claimed_at if ownership is not None else "-"
    age = (
        f"{max(0, now_epoch - ownership.claimed_at_epoch)}s"
        if ownership is not None
        else "-"
    )
    diagnostic = inspection.diagnostic or "-"
    print(
        f"{inspection.project}\t{inspection.database}\t"
        f"{inspection.availability}\t{run_id}\t{execution_id}\t"
        f"{claimed_at}\t{age}\t{diagnostic}"
    )


def _cleanup_list(args) -> int:
    with _project_root_context(Path(args.root)):
        _require_cleanup_project(args.project)
        inspections = inspect_configured_slots(project=args.project)
        if args.run:
            inspections = [
                inspection
                for inspection in inspections
                if inspection.ownership is not None
                and inspection.ownership.run_id == args.run
            ]
        if args.project:
            inspections = [
                inspection
                for inspection in inspections
                if inspection.project == args.project
            ]
        print(
            "project\tdatabase\tavailability\trun_id\texecution_id\t"
            "claimed_at\tage\tdiagnostic"
        )
        now_epoch = qa_server_epoch()
        for inspection in inspections:
            _print_slot(inspection, now_epoch=now_epoch)
    return 0


def _cleanup_cutoff(args) -> int | None:
    cutoffs = []
    if args.older_than:
        try:
            age_seconds = parse_age(args.older_than)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        cutoffs.append(qa_server_epoch() - age_seconds)
    if args.created_before:
        try:
            cutoffs.append(parse_created_before(args.created_before))
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
    return min(cutoffs) if cutoffs else None


def _cleanup_delete(args) -> int:
    selectors = (
        args.run,
        args.execution,
        args.database,
        args.older_than,
        args.created_before,
    )
    if not any(selectors):
        raise SystemExit(
            "cleanup delete requires at least one selector: --run, "
            "--execution, --database, --older-than, or --created-before"
        )
    if (args.older_than or args.created_before) and not (
        args.project or args.all_projects
    ):
        raise SystemExit("time cleanup requires --project or --all-projects")
    database = None
    if args.database:
        try:
            database = validate_qa_identifier(args.database)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
    with _project_root_context(Path(args.root)):
        _require_cleanup_project(args.project)
        cutoff_epoch = _cleanup_cutoff(args)
        inspections = inspect_configured_slots(project=args.project)
        selected = select_cleanup_slots(
            inspections,
            project=args.project,
            run_id=args.run,
            execution_id=args.execution,
            database=database,
            cutoff_epoch=cutoff_epoch,
        )
        action = "release" if args.yes else "would release"
        for inspection in selected:
            print(
                f"{action}\t{inspection.project}\t{inspection.database}\t"
                f"{inspection.availability}"
            )
        if not args.yes:
            print(f"preview selected={len(selected)}")
            return 0

        released = 0
        blocked = 0
        failed = 0
        for inspection in selected:
            project_config = config.PROJECT_CONFIG[inspection.project]
            try:
                configured_pool = configured_qa_pool(
                    inspection.project, project_config
                )
                release_qa_slot(
                    inspection,
                    configured_pool=configured_pool,
                    protected_databases={
                        str(project_config.get("db") or ""),
                        str(project_config.get("lineage_db") or ""),
                    },
                )
            except ArtifactFormatError as exc:
                blocked += 1
                print(
                    f"blocked\t{inspection.project}\t"
                    f"{inspection.database}\t{exc}"
                )
            except Exception as exc:
                failed += 1
                print(
                    f"failed\t{inspection.project}\t"
                    f"{inspection.database}\t{exc}"
                )
            else:
                released += 1
                print(f"released\t{inspection.project}\t{inspection.database}")
        print(
            f"cleanup summary released={released} blocked={blocked} "
            f"failed={failed}"
        )
        return 1 if blocked or failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refactor run workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="freeze refactor baseline")
    start.add_argument(
        "--project",
        required=True,
    )
    start.add_argument("--root", default=str(config.PROJECT_ROOT))
    start.set_defaults(func=_start)

    analyze = subparsers.add_parser(
        "analyze",
        help="refresh current lineage, issue diff, and validation plan",
    )
    _add_manifest_selector(analyze)
    analyze.add_argument(
        "--partition",
        default=None,
        help="manual partition value for shadow-run and compare",
    )
    analyze.set_defaults(func=_analyze)

    shadow = subparsers.add_parser("shadow-run", help="run QA shadow plan")
    _add_manifest_selector(shadow)
    shadow.add_argument("--dry-run", action="store_true")
    shadow.add_argument(
        "--timing-detail",
        "--profile",
        action="store_true",
        dest="timing_detail",
        help="record per-invocation timing details in shadow_run_result.json",
    )
    shadow.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="global shadow-run mysql concurrency, default 1",
    )
    shadow.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="number of slice invocations per mysql session, default 1",
    )
    shadow.set_defaults(func=_shadow_run)

    compare = subparsers.add_parser("compare", help="compare prod and QA")
    _add_manifest_selector(compare)
    compare.add_argument(
        "--method",
        default="all",
        choices=["count", "row_compare", "all"],
    )
    compare.add_argument("--sample", type=int, default=0)
    compare.add_argument("--precision", type=float, default=0.01)
    compare.set_defaults(func=_compare)

    semantic_mode = subparsers.add_parser(
        "semantic-mode", help="manage table semantic declarations"
    )
    semantic_commands = semantic_mode.add_subparsers(
        dest="semantic_command", required=True
    )
    semantic_set = semantic_commands.add_parser(
        "set", help="set one affected table semantic mode"
    )
    _add_manifest_selector(semantic_set)
    semantic_set.add_argument("--table", required=True)
    semantic_set.add_argument(
        "--mode",
        required=True,
        choices=["equivalent", "changed", "unknown"],
    )
    semantic_set.set_defaults(func=_semantic_mode_set)

    cleanup = subparsers.add_parser(
        "cleanup", help="inspect or manually release QA database pool slots"
    )
    cleanup_commands = cleanup.add_subparsers(
        dest="cleanup_command", required=True
    )
    cleanup_list = cleanup_commands.add_parser(
        "list", help="list configured QA database pool slots"
    )
    cleanup_list.add_argument("--root", default=str(config.PROJECT_ROOT))
    cleanup_list.add_argument("--project")
    cleanup_list.add_argument("--run")
    cleanup_list.set_defaults(func=_cleanup_list)

    cleanup_delete = cleanup_commands.add_parser(
        "delete", help="preview or release selected QA pool slots"
    )
    cleanup_delete.add_argument("--root", default=str(config.PROJECT_ROOT))
    project_scope = cleanup_delete.add_mutually_exclusive_group()
    project_scope.add_argument("--project")
    project_scope.add_argument("--all-projects", action="store_true")
    cleanup_delete.add_argument("--run")
    cleanup_delete.add_argument("--execution")
    cleanup_delete.add_argument("--database")
    cleanup_delete.add_argument("--older-than")
    cleanup_delete.add_argument("--created-before")
    cleanup_delete.add_argument("--yes", action="store_true")
    cleanup_delete.set_defaults(func=_cleanup_delete)
    add_schedule_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ArtifactFormatError, ScheduleContractError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    raise SystemExit(main())
