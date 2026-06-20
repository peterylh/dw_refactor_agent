#!/usr/bin/env python3
"""Refactor run session CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _check(args) -> int:
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

    current_assess = assess(
        project,
        lineage_data=current_lineage,
        scope=change_analysis.get("affected_scope"),
    )
    _write_json(artifact_path(manifest_path, "current_assess"), current_assess)

    baseline_assess = _read_json(
        artifact_path(manifest_path, "baseline_assess")
    )
    issue_diff = diff_assess_results(baseline_assess, current_assess)
    _write_json(artifact_path(manifest_path, "issue_diff"), issue_diff)

    plan = build_verification_plan(project, change_analysis)
    _write_json(artifact_path(manifest_path, "verification_plan"), plan)
    print(f"Check complete: {manifest_path}")
    return 0


def _shadow_run(args) -> int:
    manifest_path = Path(args.manifest)
    run_shadow_plan(
        artifact_path(manifest_path, "verification_plan"),
        artifact_path(manifest_path, "shadow_run_result"),
        dry_run=args.dry_run,
    )
    return 0


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

    check = subparsers.add_parser("check", help="refresh current analysis")
    check.add_argument("--manifest", required=True)
    check.set_defaults(func=_check)

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
