"""
Project asset paths and model metadata access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from . import core
from .model_governance import (
    UnavailableModelSection,
    UnsupportedModelGovernanceError,
    get_operational_layer,
    get_semantic_layer,
    validate_model_metadata,
)

_model_metadata_cache = {}
_MID_LAYERS = {"DIM", "DWD", "DWS"}


def clear_model_metadata_cache() -> None:
    _model_metadata_cache.clear()


def project_dir(project: str) -> Optional[Path]:
    """Return the data mart project directory."""
    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        return None
    return core.PROJECT_ROOT / cfg["dir"]


def project_dir_from_root(project: str, root: Path) -> Optional[Path]:
    """Return the data mart project directory under an explicit repo root."""
    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        return None
    return Path(root) / cfg["dir"]


def project_artifact_dir(project: str, *parts: str) -> Optional[Path]:
    """Return a project-level generated-artifact directory."""
    base_dir = project_dir(project)
    if not base_dir:
        return None
    return base_dir.joinpath("artifacts", *parts)


def lineage_data_path(project: str, snapshot_id: str | None = None) -> Path:
    """Return the default project lineage JSON path."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    if snapshot_id:
        return lineage_dir / f"lineage_data_{snapshot_id}.json"
    return lineage_dir / "lineage_data.json"


def job_dag_path(project: str) -> Path:
    """Return the default project job DAG path."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "job_dag.json"


def lineage_task_cache_path(project: str) -> Path:
    """Return the default task-level lineage cache path."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "task_lineage_cache.json"


def lineage_html_path(project: str) -> Path:
    """Return the default field-lineage HTML path."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "lineage.html"


def lineage_job_html_path(project: str) -> Path:
    """Return the default job-lineage HTML path."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "lineage_job.html"


def assess_result_path(project: str) -> Path:
    """Return the default middle-layer assessment result path."""
    assess_dir = project_artifact_dir(project, "assessment")
    if assess_dir is None:
        raise KeyError(f"未知项目: {project}")
    return assess_dir / "assess_result.json"


def model_metadata_result_path(project: str) -> Path:
    """Return the default model-metadata writer result path."""
    assess_dir = project_artifact_dir(project, "assessment")
    if assess_dir is None:
        raise KeyError(f"未知项目: {project}")
    return assess_dir / "model_metadata_result.json"


def assess_cache_path(project: str, filename: str) -> Path:
    """Return a default project assessment cache file path."""
    cache_dir = project_artifact_dir(project, "assessment", "cache")
    if cache_dir is None:
        raise KeyError(f"未知项目: {project}")
    return cache_dir / filename


def refactor_runs_dir(project: str, root: Path | None = None) -> Path:
    """Return the default refactor run directory for a warehouse project."""
    base_dir = (
        project_dir_from_root(project, root)
        if root is not None
        else project_dir(project)
    )
    if base_dir is None:
        raise KeyError(f"未知项目: {project}")
    return base_dir / "artifacts" / "refactor_runs"


def project_ods_asset_dir(project: str, asset_kind: str) -> Optional[Path]:
    """Return the configured ODS asset directory for catalog/database assets."""
    cfg = core.PROJECT_CONFIG.get(project)
    base_dir = project_dir(project)
    if not cfg or not base_dir:
        return None
    catalog = str(cfg.get("catalog") or "internal")
    database = str(cfg.get("db") or "")
    return base_dir / "ods" / asset_kind / catalog / database


def project_ods_source_catalog_dialects(project: str) -> dict[str, str]:
    """Return ODS source catalog to DDL dialect mapping."""
    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        return {}

    default_catalog = str(cfg.get("catalog") or "internal")
    result = {default_catalog: "doris"}

    raw_dialects = cfg.get("ods_source_catalog_dialects") or {}
    if not isinstance(raw_dialects, dict):
        return result

    for raw_catalog, raw_dialect in raw_dialects.items():
        catalog = str(raw_catalog)
        if not catalog:
            continue
        result[catalog] = str(raw_dialect or "doris")

    return result


def ods_source_catalog_ddl_dialect(project: str, catalog: str) -> str:
    """Return a source catalog's DDL dialect; default to Doris."""
    catalog_key = str(catalog or "")
    return project_ods_source_catalog_dialects(project).get(
        catalog_key, "doris"
    )


def project_ods_asset_dirs(project: str, asset_kind: str) -> list[Path]:
    """Return on-disk ODS asset directories organized by catalog/database."""
    base_dir = project_dir(project)
    if not base_dir:
        return []

    ods_root = base_dir / "ods" / asset_kind
    if not ods_root.exists():
        return []

    dirs = []
    seen = set()
    default_catalog = str(
        (core.PROJECT_CONFIG.get(project) or {}).get("catalog") or "internal"
    )
    catalog_dirs = [
        path for path in sorted(ods_root.iterdir()) if path.is_dir()
    ]
    catalog_dirs.sort(
        key=lambda path: (0 if path.name == default_catalog else 1, path.name)
    )
    for catalog_dir in catalog_dirs:
        for asset_dir in sorted(catalog_dir.iterdir()):
            if not asset_dir.is_dir():
                continue
            if asset_dir in seen:
                continue
            seen.add(asset_dir)
            dirs.append(asset_dir)
    return dirs


def asset_role_for_layer(layer: str | None) -> str:
    """Return the project asset role for a declared model layer."""
    normalized = str(layer or "").upper()
    if normalized == "ODS":
        return "ods"
    if normalized == "ADS":
        return "ads"
    if normalized in _MID_LAYERS:
        return "mid"
    return "mid"


def _project_role_asset_dir(
    project: str,
    role: str,
    asset_kind: str,
) -> Optional[Path]:
    base_dir = project_dir(project)
    if not base_dir:
        return None
    normalized_role = str(role or "").lower()
    if normalized_role == "ods":
        return project_ods_asset_dir(project, asset_kind)
    if normalized_role in {"mid", "ads"}:
        return base_dir / normalized_role / asset_kind
    return None


def _project_layer_asset_dirs(project: str, asset_kind: str) -> list[Path]:
    base_dir = project_dir(project)
    if not base_dir:
        return []

    dirs = []
    for role_dir in ("mid", "ads"):
        asset_dir = base_dir / role_dir / asset_kind
        if asset_dir.exists():
            dirs.append(asset_dir)
    return dirs


def project_asset_dirs(project: str, asset_kind: str) -> list[Path]:
    """Return project asset directories in stable ODS/MID/ADS order."""
    base_dir = project_dir(project)
    if not base_dir:
        return []
    dirs = []
    for ods_dir in project_ods_asset_dirs(project, asset_kind):
        dirs.append(ods_dir)
    dirs.extend(_project_layer_asset_dirs(project, asset_kind))
    return dirs


def iter_project_asset_files(
    project: str,
    asset_kind: str,
    pattern: str,
) -> list[Path]:
    """Return project asset files in stable order."""
    files: list[Path] = []
    seen: set[Path] = set()
    for asset_dir in project_asset_dirs(project, asset_kind):
        if not asset_dir.exists():
            continue
        for asset_path in sorted(asset_dir.glob(pattern)):
            if asset_path in seen:
                continue
            seen.add(asset_path)
            files.append(asset_path)
    return files


def project_task_dirs(project: str) -> list[Path]:
    """Return ETL task directories in stable MID/ADS order."""
    return [
        asset_dir
        for asset_dir in project_asset_dirs(project, "tasks")
        if asset_dir.exists()
    ]


def iter_project_task_files(
    project: str,
    *,
    include_full_refresh: bool = True,
) -> list[Path]:
    """Return task SQL files, including full-refresh companions if requested."""
    files: list[Path] = []
    seen: set[Path] = set()
    for task_dir in project_task_dirs(project):
        candidates = sorted(task_dir.glob("*.sql"))
        if include_full_refresh:
            full_refresh_dir = task_dir / "full_refresh"
            if full_refresh_dir.exists():
                candidates.extend(sorted(full_refresh_dir.glob("*.sql")))
        for task_path in candidates:
            if task_path in seen:
                continue
            seen.add(task_path)
            files.append(task_path)
    return files


def task_source_file(project: str, task_path: Path) -> str:
    """Return the stable lineage source_file for a task path."""
    path = Path(task_path)
    for task_dir in project_task_dirs(project):
        try:
            return path.relative_to(task_dir).as_posix()
        except ValueError:
            continue
    return path.name


def task_path_for_source_file(
    project: str, source_file: str
) -> Optional[Path]:
    """Return the task path for a lineage source_file value."""
    normalized = str(source_file or "").replace("\\", "/").strip()
    if not normalized:
        return None
    for task_dir in project_task_dirs(project):
        candidate = task_dir / normalized
        if candidate.exists():
            return candidate
    return None


def task_path_for_job(
    project: str,
    job_name: str,
    *,
    include_full_refresh: bool = True,
) -> Optional[Path]:
    """Return the SQL path for a job name across MID and ADS dirs."""
    clean_job_name = str(job_name or "").strip()
    if not clean_job_name:
        return None

    task_dirs = project_task_dirs(project)
    candidates = [task_dir / f"{clean_job_name}.sql" for task_dir in task_dirs]
    if include_full_refresh:
        for task_dir in task_dirs:
            full_dir = task_dir / "full_refresh"
            candidates.extend(
                [
                    full_dir / f"{clean_job_name}_full_refresh.sql",
                    full_dir / f"{clean_job_name}.sql",
                ]
            )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def model_path_for_table(
    project: str,
    table_name: str,
    *,
    layer: str | None = None,
) -> Path:
    """Return the write path for table-level model metadata."""
    cfg = core.PROJECT_CONFIG[project]
    filename = f"{table_name}.yaml"
    normalized_layer = str(layer or "").upper()

    for model_dir in project_asset_dirs(project, "models"):
        candidate = model_dir / filename
        if candidate.exists():
            return candidate

    role = asset_role_for_layer(normalized_layer)
    role_dir = _project_role_asset_dir(project, role, "models")
    if role_dir:
        return role_dir / filename

    return core.PROJECT_ROOT / cfg["dir"] / "mid" / "models" / filename


def load_model_metadata(project: str) -> dict:
    """Load validated, governance-aware model metadata."""
    if project in _model_metadata_cache:
        return _model_metadata_cache[project]

    metadata = _load_model_metadata_files(project, governed=True)
    _model_metadata_cache[project] = metadata
    return metadata


def load_raw_model_metadata(project: str) -> dict:
    """Load lossless YAML documents keyed by project-relative file identity."""
    return _load_model_metadata_files(project, governed=False)


def _load_model_metadata_files(project: str, *, governed: bool) -> dict:
    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        return {}

    model_paths = iter_project_asset_files(project, "models", "*.yaml")
    if not model_paths:
        return {}

    metadata = {}
    governed_names = {}
    for model_path in model_paths:
        loaded = yaml.safe_load(
            model_path.read_text(encoding=core.TEXT_ENCODING)
        )
        if not governed:
            try:
                identity = model_path.relative_to(project_dir(project))
            except ValueError:
                identity = model_path
            metadata[identity.as_posix()] = loaded
            continue
        raw = {} if loaded is None else loaded
        if not isinstance(raw, dict):
            validate_model_metadata(raw, source=str(model_path))
        declared_name = raw.get("name")
        name = (
            model_path.stem if declared_name in (None, "") else declared_name
        )
        raw = dict(raw)
        raw["name"] = name
        model = validate_model_metadata(
            raw,
            source=str(model_path),
        )
        governed_name = str(model["name"])
        name_key = governed_name.casefold()
        if name_key in governed_names:
            raise UnsupportedModelGovernanceError(
                "model metadata names collide under case-insensitive lookup: "
                f"{governed_names[name_key]!r} and {governed_name!r}"
            )
        governed_names[name_key] = governed_name
        metadata[governed_name] = model
    return metadata


def get_model_metadata(table_name: str, project: str) -> Optional[dict]:
    short = table_name.split(".")[-1]
    models = load_model_metadata(project)
    matches = [
        metadata
        for name, metadata in models.items()
        if str(name).casefold() == short.casefold()
    ]
    if len(matches) > 1:
        raise UnsupportedModelGovernanceError(
            "model metadata names collide under case-insensitive lookup: "
            f"{short!r}"
        )
    return matches[0] if matches else None


def get_model_layer(
    table_name: str,
    project: str,
) -> Optional[str] | UnavailableModelSection:
    metadata = get_model_metadata(table_name, project)
    if not metadata:
        return None
    return get_semantic_layer(metadata)


def get_model_operational_layer(
    table_name: str,
    project: str,
) -> Optional[str]:
    """Return the deterministic runtime layer for one model."""
    metadata = get_model_metadata(table_name, project)
    if not metadata:
        return None
    return get_operational_layer(metadata)


def get_model_names_by_layer(project: str, layer: str) -> list[str]:
    """Return model names for a layer according to model metadata."""
    target_layer = str(layer).upper()
    names = []
    for name, metadata in load_model_metadata(project).items():
        model_layer = get_semantic_layer(metadata)
        if isinstance(model_layer, UnavailableModelSection):
            continue
        if model_layer == target_layer:
            names.append(name)
    return sorted(names)


def get_model_names_by_operational_layer(
    project: str,
    layer: str,
) -> list[str]:
    """Return model names routed through one deterministic asset layer."""
    target_layer = str(layer).upper()
    return sorted(
        name
        for name, metadata in load_model_metadata(project).items()
        if get_operational_layer(metadata) == target_layer
    )


def determine_layer(
    table_name: str,
    project: str = None,
) -> str | UnavailableModelSection:
    """Return table layer from explicit model metadata."""
    short = table_name.split(".")[-1]
    if not project:
        return "OTHER"
    layer = get_model_layer(short, project)
    if isinstance(layer, UnavailableModelSection):
        return layer
    return layer or "OTHER"


def determine_operational_layer(
    table_name: str,
    project: str = None,
) -> str:
    """Return the deterministic runtime layer without semantic fallback."""
    short = table_name.split(".")[-1]
    if not project:
        return "OTHER"
    return get_model_operational_layer(short, project) or "OTHER"


def layer_rank(layer_name: str) -> int:
    """Return stable project layer order; unknown layers return -1."""
    normalized = str(layer_name or "").upper()
    for rank, group in enumerate(core.LAYER_ORDER):
        if normalized in group:
            return rank
    return -1
