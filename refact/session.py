"""Refactor run session manifest helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import TEXT_ENCODING


def _artifact_paths(project: str) -> dict:
    return {
        "baseline_lineage": f"baseline/lineage_data_{project}.json",
        "baseline_task_cache": "baseline/task_lineage_cache.json",
        "baseline_assess": "baseline/assess_result.json",
        "current_lineage": f"current/lineage_data_{project}.json",
        "current_task_cache": "current/task_lineage_cache.json",
        "current_assess": "current/assess_result.json",
        "change_analysis": "analysis/change_analysis.json",
        "issue_diff": "analysis/issue_diff.json",
        "verification_plan": "verification/plan.json",
        "shadow_run_result": "verification/shadow_run_result.json",
        "compare_result": "verification/compare_result.json",
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_run_manifest(
    root: Path,
    project: str,
    *,
    now: datetime | None = None,
    git_info: dict | None = None,
) -> tuple[Path, dict]:
    """Create a run directory and return its manifest path and data."""
    now = now or _utc_now()
    root = Path(root)
    run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{project}"
    run_root = root / "refact" / "runs" / run_id
    for dirname in ("baseline", "current", "analysis", "verification"):
        (run_root / dirname).mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "project": project,
        "created_at": now.isoformat(),
        "base_git": git_info or {},
        "artifacts": _artifact_paths(project),
    }
    manifest_path = run_root / "manifest.json"
    write_manifest(manifest_path, manifest)
    return manifest_path, manifest


def write_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(Path(manifest_path).read_text(encoding=TEXT_ENCODING))


def run_root_from_manifest_path(manifest_path: Path) -> Path:
    return Path(manifest_path).parent


def artifact_path(manifest_path: Path, artifact_key: str) -> Path:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    rel_path = manifest["artifacts"][artifact_key]
    return run_root_from_manifest_path(manifest_path) / rel_path
