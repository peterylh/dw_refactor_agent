#!/usr/bin/env python3
"""Refactor run session CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from assess.assess_middle_layer import assess
from config import PROJECT_CONFIG, TEXT_ENCODING
from refact.change_analysis import (
    build_change_analysis,
    changed_files_since_head,
)
from refact.compare import compare_shadow_results
from refact.incremental_lineage import build_lineage_artifacts
from refact.issue_diff import diff_assess_results
from refact.session import (
    artifact_path,
    create_run_manifest,
    load_manifest,
    write_manifest,
)
from refact.shadow_run import run_shadow_plan
from refact.verification_plan import build_verification_plan

NO_CHANGES_SCORE_REASON = (
    "No relevant file, lineage, DDL, or job changes were detected; scoped "
    "assessment score is not applicable."
)


def _now() -> datetime:
    return datetime.now().astimezone()


def _write_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding=TEXT_ENCODING))


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
    return PROJECT_CONFIG[project]["dir"]


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


def _plan_scope(plan: dict) -> dict:
    return plan.get("scope") or plan.get("affected_scope") or {}


def _plan_changes(plan: dict) -> dict:
    if plan.get("changes"):
        return plan.get("changes") or {}
    return {
        "modified_jobs": plan.get("modified_jobs") or [],
    }


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
    scope = _plan_scope(plan)
    changes = _plan_changes(plan)
    return bool(
        _has_any_items(
            changes,
            ("modified_jobs", "ddl_tables", "model_tables", "config_files"),
        )
        or plan.get("anchors")
        or plan.get("ddl_changes")
        or plan.get("jobs_to_run")
        or _has_any_items(
            scope,
            (
                "direct_tables",
                "downstream_tables",
                "anchor_tables",
                "assessment_tables",
                "assessment_tasks",
                "global_dimensions",
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
    root = Path(args.root)
    manifest_path, manifest = create_run_manifest(
        root,
        args.project,
        now=_now(),
        git_info=_git_info(root),
    )
    write_manifest(manifest_path, manifest)
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
    _write_json(artifact_path(manifest_path, "baseline_assess"), assess_result)
    print(f"Run manifest: {manifest_path}")
    return 0


def _previous_cache_path(manifest_path: Path) -> Path:
    current_cache = artifact_path(manifest_path, "current_task_cache")
    if current_cache.exists():
        return current_cache
    return artifact_path(manifest_path, "baseline_task_cache")


def _analyze(args) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    project = manifest["project"]

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
    current_lineage = lineage_result["lineage"]
    changed_files = changed_files_since_head(
        config.PROJECT_ROOT,
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

    plan = build_verification_plan(
        project,
        change_analysis,
        base_ref=manifest.get("base_git", {}).get("head"),
        repo_root=config.PROJECT_ROOT,
        lineage_data=current_lineage,
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

    current_assess = assess(
        project,
        lineage_data=current_lineage,
        change_analysis=change_analysis,
    )
    if _has_no_refactor_changes(change_analysis, plan):
        current_assess = _mark_assessment_no_changes(current_assess)
    _write_json(artifact_path(manifest_path, "current_assess"), current_assess)
    _write_json(artifact_path(manifest_path, "verification_plan"), plan)

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

    print(f"Analyze complete: {manifest_path}")
    return 0


def _shadow_run(args) -> int:
    manifest_path = Path(args.manifest)
    result = run_shadow_plan(
        artifact_path(manifest_path, "verification_plan"),
        artifact_path(manifest_path, "shadow_run_result"),
        dry_run=args.dry_run,
    )
    return 1 if result.get("status") == "failed" else 0


def _compare(args) -> int:
    manifest_path = Path(args.manifest)
    compare_shadow_results(
        artifact_path(manifest_path, "verification_plan"),
        artifact_path(manifest_path, "compare_result"),
        method=args.method,
        sample=args.sample,
        precision=args.precision,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refactor run workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="freeze refactor baseline")
    start.add_argument(
        "--project",
        required=True,
        choices=list(PROJECT_CONFIG.keys()),
    )
    start.add_argument("--root", default=str(config.PROJECT_ROOT))
    start.set_defaults(func=_start)

    analyze = subparsers.add_parser(
        "analyze",
        help="refresh current lineage, issue diff, and validation plan",
    )
    analyze.add_argument("--manifest", required=True)
    analyze.add_argument(
        "--partition",
        default=None,
        help="manual partition value for shadow-run and compare",
    )
    analyze.set_defaults(func=_analyze)

    shadow = subparsers.add_parser("shadow-run", help="run QA shadow plan")
    shadow.add_argument("--manifest", required=True)
    shadow.add_argument("--dry-run", action="store_true")
    shadow.set_defaults(func=_shadow_run)

    compare = subparsers.add_parser("compare", help="compare prod and QA")
    compare.add_argument("--manifest", required=True)
    compare.add_argument(
        "--method",
        default="all",
        choices=["count", "row_compare", "all"],
    )
    compare.add_argument("--sample", type=int, default=0)
    compare.add_argument("--precision", type=float, default=0.01)
    compare.set_defaults(func=_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
