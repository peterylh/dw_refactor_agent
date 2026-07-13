"""Refactor run session manifest helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dw_refactor_agent.config import refactor_runs_dir
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
    read_json_object,
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
    base_run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{project}"
    runs_root = _refactor_runs_root(root, project)
    runs_root.mkdir(parents=True, exist_ok=True)
    suffix = 0
    while True:
        run_id = base_run_id if suffix == 0 else f"{base_run_id}_{suffix:02d}"
        run_root = runs_root / run_id
        try:
            run_root.mkdir(exist_ok=False)
            break
        except FileExistsError:
            suffix += 1
    for dirname in ("baseline", "current", "analysis", "verification"):
        (run_root / dirname).mkdir()

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
    manifest = read_json_object(manifest_path, "manifest")
    require_format_version(manifest, "manifest")
    _validate_manifest(manifest_path, manifest)
    return manifest


def _require_non_empty_string(manifest: dict, field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactFormatError(
            f"manifest.{field} must be a non-empty string"
        )
    return value


def _validate_manifest(manifest_path: Path, manifest: dict) -> None:
    """Validate manifest structure and keep artifact paths inside the run."""
    _require_non_empty_string(manifest, "run_id")
    _require_non_empty_string(manifest, "project")
    _require_non_empty_string(manifest, "root")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ArtifactFormatError("manifest.artifacts must be a mapping")
    run_root = Path(manifest_path).parent.resolve()
    for artifact_key, relative_value in artifacts.items():
        if not isinstance(artifact_key, str) or not artifact_key.strip():
            raise ArtifactFormatError(
                "manifest artifact keys must be non-empty strings"
            )
        if not isinstance(relative_value, str) or not relative_value.strip():
            raise ArtifactFormatError(
                f"manifest artifact path for {artifact_key!r} must be a "
                "non-empty string"
            )
        relative_path = Path(relative_value)
        if relative_path.is_absolute():
            raise ArtifactFormatError(
                f"manifest artifact path for {artifact_key!r} must be relative"
            )
        resolved = (run_root / relative_path).resolve()
        try:
            resolved.relative_to(run_root)
        except ValueError:
            raise ArtifactFormatError(
                f"manifest artifact path for {artifact_key!r} escapes the "
                f"run directory: {relative_value}"
            ) from None

    intent = manifest.get("verification_intent")
    if intent is None:
        return
    if not isinstance(intent, dict):
        raise ArtifactFormatError(
            "manifest.verification_intent must be a mapping"
        )
    semantic_modes = intent.get("semantic_modes", {})
    if not isinstance(semantic_modes, dict):
        raise ArtifactFormatError(
            "manifest.verification_intent.semantic_modes must be a mapping"
        )
    for table_name, declaration in semantic_modes.items():
        if not isinstance(table_name, str) or not table_name.strip():
            raise ArtifactFormatError(
                "manifest semantic mode table names must be non-empty strings"
            )
        if not isinstance(declaration, dict):
            raise ArtifactFormatError(
                "manifest semantic mode declarations must be mappings: "
                f"{table_name}"
            )


def run_root_from_manifest_path(manifest_path: Path) -> Path:
    return Path(manifest_path).parent


def artifact_path(manifest_path: Path, artifact_key: str) -> Path:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    rel_path = manifest["artifacts"][artifact_key]
    return run_root_from_manifest_path(manifest_path) / rel_path


def resolve_manifest_path(
    *,
    manifest_path: str | Path | None,
    run_id: str | None,
    root: Path,
) -> Path:
    """Resolve one exact manifest path without an implicit latest run."""
    if bool(manifest_path) == bool(run_id):
        raise SystemExit("provide exactly one of --manifest or --run")
    if manifest_path:
        resolved = Path(manifest_path).expanduser().resolve()
        if not resolved.is_file():
            raise SystemExit(f"manifest does not exist: {resolved}")
        return resolved

    matches = []
    for project in sorted(config_project_names()):
        candidate = _refactor_runs_root(Path(root), project) / str(run_id)
        manifest = candidate / "manifest.json"
        if manifest.is_file():
            matches.append(manifest.resolve())
    if not matches:
        raise SystemExit(
            f"no run matches {run_id!r}; pass an exact --manifest path"
        )
    if len(matches) > 1:
        paths = ", ".join(str(path) for path in matches)
        raise SystemExit(
            f"multiple runs match {run_id!r}: {paths}; pass --manifest"
        )
    return matches[0]


def config_project_names() -> list[str]:
    """Return currently configured warehouse project names."""
    from dw_refactor_agent.config import core

    return sorted(core.PROJECT_CONFIG)


def load_historical_manifests(
    manifest_path: Path,
    manifest: dict,
) -> tuple[list[tuple[Path, dict]], list[str]]:
    """Load same-project historical manifests newest-first."""
    current_path = Path(manifest_path).resolve()
    runs_root = current_path.parent.parent
    loaded = []
    diagnostics = []
    if not runs_root.is_dir():
        return loaded, diagnostics
    for run_dir in sorted(runs_root.iterdir(), reverse=True):
        candidate = run_dir / "manifest.json"
        if candidate.resolve() == current_path or not candidate.is_file():
            continue
        try:
            historical = load_manifest(candidate)
            if historical.get("project") != manifest.get("project"):
                continue
            loaded.append((candidate.resolve(), historical))
        except (OSError, ArtifactFormatError) as exc:
            diagnostics.append(
                f"skipped historical manifest {candidate}: {exc}"
            )
    return loaded, diagnostics
