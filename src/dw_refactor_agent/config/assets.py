"""
Project asset paths and model metadata access.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from dw_refactor_agent.sql.task_template import (
    ContractValidationError,
    TaskDefinition,
    load_task_definition,
)

from . import core

_model_metadata_cache = {}
_MID_LAYERS = {"DIM", "DWD", "DWS"}


@dataclass(frozen=True)
class ProjectTaskAsset:
    """One discovered SQL job and its optional explicit template contract."""

    project: str
    role: str
    sql_path: Path
    source_file: str
    sql_text: str
    contract_path: Optional[Path] = None
    template_definition: Optional[TaskDefinition] = None
    is_full_refresh: bool = False

    @property
    def job_name(self) -> str:
        return self.sql_path.stem

    @property
    def is_template(self) -> bool:
        return self.template_definition is not None


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


def _task_asset_error(
    message: str,
    *,
    code: str,
    path: Path,
) -> ContractValidationError:
    return ContractValidationError(
        message,
        code=code,
        path=(str(path),),
    )


def _task_role(task_dir: Path) -> str:
    role = task_dir.parent.name.casefold()
    return role if role in {"mid", "ads"} else "unknown"


def _task_directory_assets(
    task_dir: Path,
    *,
    include_full_refresh: bool,
) -> tuple[list[Path], list[Path]]:
    sql_files = []
    contract_files = []
    directories = [task_dir]
    full_refresh_dir = task_dir / "full_refresh"
    if include_full_refresh and full_refresh_dir.is_dir():
        directories.append(full_refresh_dir)
    for directory in directories:
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            suffix = path.suffix
            if suffix == ".sql":
                sql_files.append(path)
            elif suffix in {".yaml", ".yml"}:
                contract_files.append(path)
    return sql_files, contract_files


def _register_task_job_path(
    job_paths: dict,
    *,
    role: str,
    path: Path,
    is_full_refresh: bool,
) -> None:
    """Register one task while allowing a same-role legacy companion pair."""
    collision_key = path.stem.casefold()
    previous_entries = job_paths.setdefault(collision_key, [])
    for (
        previous_role,
        previous_path,
        previous_is_full_refresh,
    ) in previous_entries:
        if previous_role != role:
            code = "template.asset.cross_role_job_collision"
        elif previous_is_full_refresh == is_full_refresh:
            code = "template.asset.duplicate_job"
        elif previous_path.stem == path.stem:
            continue
        else:
            code = "template.asset.duplicate_job"
        raise _task_asset_error(
            f"task job stem collides with {previous_path}",
            code=code,
            path=path,
        )
    previous_entries.append((role, path, is_full_refresh))


def discover_project_tasks(
    project: str,
    *,
    include_full_refresh: bool = True,
) -> list[ProjectTaskAsset]:
    """Discover and validate legacy/template task pairs in stable order.

    SQL files remain the only source of job identity. A same-directory,
    same-stem YAML file opts one SQL job into template mode. Any SQL text that
    contains a template marker must have that explicit contract.
    """
    discovered = []
    job_paths = {}
    for task_dir in project_task_dirs(project):
        role = _task_role(task_dir)
        sql_files, contract_files = _task_directory_assets(
            task_dir,
            include_full_refresh=include_full_refresh,
        )
        sql_by_pair = {(path.parent, path.stem): path for path in sql_files}
        contracts_by_pair = {}
        for contract_path in contract_files:
            pair_key = (contract_path.parent, contract_path.stem)
            if pair_key not in sql_by_pair:
                raise _task_asset_error(
                    "task contract has no same-directory, same-stem SQL job",
                    code="template.asset.orphan_contract",
                    path=contract_path,
                )
            if pair_key in contracts_by_pair:
                raise _task_asset_error(
                    "task SQL has multiple YAML contracts",
                    code="template.asset.duplicate_contract",
                    path=contract_path,
                )
            contracts_by_pair[pair_key] = contract_path

        ordered_sql = sorted(
            (path for path in sql_files if path.parent == task_dir),
            key=lambda path: path.name,
        )
        ordered_sql.extend(
            sorted(
                (path for path in sql_files if path.parent != task_dir),
                key=lambda path: path.name,
            )
        )
        for sql_path in ordered_sql:
            is_full_refresh = sql_path.parent.name == "full_refresh"
            _register_task_job_path(
                job_paths,
                role=role,
                path=sql_path,
                is_full_refresh=is_full_refresh,
            )

            contract_path = contracts_by_pair.get(
                (sql_path.parent, sql_path.stem)
            )
            if contract_path is None:
                try:
                    sql_text = sql_path.read_text(encoding=core.TEXT_ENCODING)
                except (OSError, UnicodeError) as exc:
                    raise _task_asset_error(
                        f"cannot read task SQL: {exc}",
                        code="template.asset.sql_read_failed",
                        path=sql_path,
                    ) from exc
                if "${" in sql_text:
                    raise _task_asset_error(
                        "task SQL contains a template marker but has no contract",
                        code="template.asset.missing_contract",
                        path=sql_path,
                    )
                template_definition = None
            else:
                template_definition = load_task_definition(
                    sql_path,
                    contract_path,
                )
            discovered.append(
                ProjectTaskAsset(
                    project=project,
                    role=role,
                    sql_path=sql_path,
                    source_file=sql_path.relative_to(task_dir).as_posix(),
                    sql_text=(
                        template_definition.sql_text
                        if template_definition is not None
                        else sql_text
                    ),
                    contract_path=contract_path,
                    template_definition=template_definition,
                    is_full_refresh=is_full_refresh,
                )
            )
    return discovered


def iter_project_task_files(
    project: str,
    *,
    include_full_refresh: bool = True,
) -> list[Path]:
    """Return task SQL files, including full-refresh companions if requested."""
    return [
        item.sql_path
        for item in discover_project_tasks(
            project,
            include_full_refresh=include_full_refresh,
        )
    ]


def _task_sql_path_records(
    project: str,
    *,
    include_full_refresh: bool,
) -> list[tuple[str, Path, str, bool]]:
    """Return a lightweight role/path/source/full-refresh SQL index."""
    records = []
    seen_jobs = {}
    for task_dir in project_task_dirs(project):
        role = _task_role(task_dir)
        directories = [task_dir]
        full_refresh_dir = task_dir / "full_refresh"
        if include_full_refresh and full_refresh_dir.is_dir():
            directories.append(full_refresh_dir)
        for directory in directories:
            is_full_refresh = directory != task_dir
            for path in sorted(directory.glob("*.sql")):
                if not path.is_file():
                    continue
                _register_task_job_path(
                    seen_jobs,
                    role=role,
                    path=path,
                    is_full_refresh=is_full_refresh,
                )
                records.append(
                    (
                        role,
                        path,
                        path.relative_to(task_dir).as_posix(),
                        is_full_refresh,
                    )
                )
    return records


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
    for (
        _role,
        path,
        indexed_source,
        _is_full_refresh,
    ) in _task_sql_path_records(project, include_full_refresh=True):
        if indexed_source == normalized:
            return path
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

    clean_key = clean_job_name.casefold()
    records = _task_sql_path_records(
        project,
        include_full_refresh=include_full_refresh,
    )
    for _role, path, _source_file, is_full_refresh in records:
        if not is_full_refresh and path.stem.casefold() == clean_key:
            return path
    if include_full_refresh:
        full_refresh_names = {
            clean_key,
            f"{clean_key}_full_refresh",
        }
        for _role, path, _source_file, is_full_refresh in records:
            if is_full_refresh and path.stem.casefold() in full_refresh_names:
                return path
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
    """Load project models/{table}.yaml table-level metadata."""
    if project in _model_metadata_cache:
        return _model_metadata_cache[project]

    cfg = core.PROJECT_CONFIG.get(project)
    if not cfg:
        _model_metadata_cache[project] = {}
        return {}

    model_paths = iter_project_asset_files(project, "models", "*.yaml")
    if not model_paths:
        _model_metadata_cache[project] = {}
        return {}

    metadata = {}
    for model_path in model_paths:
        raw = (
            yaml.safe_load(model_path.read_text(encoding=core.TEXT_ENCODING))
            or {}
        )
        if not isinstance(raw, dict):
            continue
        name = raw.get("name") or model_path.stem
        raw = dict(raw)
        raw["name"] = name
        metadata[name] = raw

    _model_metadata_cache[project] = metadata
    return metadata


def get_model_metadata(table_name: str, project: str) -> Optional[dict]:
    short = table_name.split(".")[-1]
    return load_model_metadata(project).get(short)


def get_model_layer(table_name: str, project: str) -> Optional[str]:
    metadata = get_model_metadata(table_name, project)
    if not metadata:
        return None
    layer = metadata.get("layer")
    return str(layer).upper() if layer else None


def get_model_names_by_layer(project: str, layer: str) -> list[str]:
    """Return model names for a layer according to model metadata."""
    target_layer = str(layer).upper()
    names = []
    for name, metadata in load_model_metadata(project).items():
        model_layer = metadata.get("layer")
        if model_layer and str(model_layer).upper() == target_layer:
            names.append(name)
    return sorted(names)


def determine_layer(table_name: str, project: str = None) -> str:
    """Return table layer from explicit model metadata."""
    short = table_name.split(".")[-1]
    if not project:
        return "OTHER"
    return get_model_layer(short, project) or "OTHER"


def layer_rank(layer_name: str) -> int:
    """Return stable project layer order; unknown layers return -1."""
    normalized = str(layer_name or "").upper()
    for rank, group in enumerate(core.LAYER_ORDER):
        if normalized in group:
            return rank
    return -1
