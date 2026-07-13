"""Refactor run session manifest helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING, refactor_runs_dir
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    atomic_write_json,
    require_format_version,
)


def _refactor_runs_root(root: Path, project: str) -> Path:
    return refactor_runs_dir(project, root=Path(root))


def _artifact_paths() -> dict:
    return {
        "baseline_lineage": "baseline/lineage_data.json",
        "baseline_task_cache": "baseline/task_lineage_cache.json",
        "baseline_assess": "baseline/assess_result.json",
        "baseline_full_assess": "baseline/assess_result.json",
        "current_lineage": "current/lineage_data.json",
        "current_task_cache": "current/task_lineage_cache.json",
        "current_assess": "current/assess_result.json",
        "current_scoped_assess": "current/assess_result.json",
        "change_analysis": "analysis/change_analysis.json",
        "issue_diff": "analysis/issue_diff.json",
        "scoped_issue_diff": "analysis/issue_diff.json",
        "verification_plan": "verification/plan.json",
        "shadow_run_result": "verification/shadow_run_result.json",
        "compare_result": "verification/compare_result.json",
    }


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _as_local_time(value: datetime) -> datetime:
    return value.astimezone()


def create_run_manifest(
    root: Path,
    project: str,
    *,
    now: datetime | None = None,
    git_info: dict | None = None,
) -> tuple[Path, dict]:
    """Create a run directory and return its manifest path and data."""
    now = _as_local_time(now or _local_now())
    root = Path(root).resolve()
    run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{project}"
    run_root = _refactor_runs_root(root, project) / run_id
    for dirname in ("baseline", "current", "analysis", "verification"):
        (run_root / dirname).mkdir(parents=True, exist_ok=True)

    manifest = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "project": project,
        "root": str(root),
        "created_at": now.isoformat(),
        "base_git": git_info or {},
        "artifacts": _artifact_paths(),
    }
    manifest_path = run_root / "manifest.json"
    write_manifest(manifest_path, manifest)
    return manifest_path, manifest


def write_manifest(manifest_path: Path, manifest: dict) -> None:
    atomic_write_json(Path(manifest_path), manifest)


def load_manifest(manifest_path: Path) -> dict:
    manifest = json.loads(
        Path(manifest_path).read_text(encoding=TEXT_ENCODING)
    )
    require_format_version(manifest, "manifest")
    return manifest


def run_root_from_manifest_path(manifest_path: Path) -> Path:
    return Path(manifest_path).parent


def artifact_path(manifest_path: Path, artifact_key: str) -> Path:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    rel_path = manifest["artifacts"][artifact_key]
    return run_root_from_manifest_path(manifest_path) / rel_path
