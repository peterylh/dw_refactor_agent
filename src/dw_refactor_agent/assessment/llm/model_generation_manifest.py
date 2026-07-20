"""Immutable asset manifest and deterministic preflight for metadata generate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from dw_refactor_agent.assessment.llm.generation_contract import (
    _validate_execution,
    infer_execution_mapping,
)
from dw_refactor_agent.assessment.llm.model_metadata_runtime import (
    project_root,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    LEGACY_BUSINESS_SEMANTICS_FILE_NAME,
    _layer_from_table_name,
)
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    business_semantics_paths,
    iter_project_asset_files,
    iter_project_task_files,
    lineage_data_path,
    load_warehouse_config,
)
from dw_refactor_agent.config.semantics import (
    load_business_semantics_catalog_from_dir,
)
from dw_refactor_agent.ddl_deriver.ddl_deriver import parse_create_table
from dw_refactor_agent.lineage.identifiers import (
    qualified_table_name,
    short_table_name,
    table_identity,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.sql_task_facts import extract_task_table_facts

ABSENT_CONTENT_HASH = "absent"
MANIFEST_SCHEMA_VERSION = 1
INSPECTION_LAYERS = frozenset({"DIM", "DWD", "DWS"})


def _content_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _path_content_hash(path: Path) -> str:
    return (
        _content_hash(path.read_bytes())
        if path.exists()
        else ABSENT_CONTENT_HASH
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in sorted(
                value.items(), key=lambda item: str(item[0])
            )
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(TEXT_ENCODING)


def _json_hash(value: Any) -> str:
    return _content_hash(_json_bytes(value))


def _display_path(path: Path) -> str:
    root = project_root()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _preflight_error(
    error_type: str,
    *,
    table: str = "",
    path: Path | str | None = None,
    message: str,
) -> dict[str, str]:
    error = {
        "type": error_type,
        "table": str(table or ""),
        "message": message,
    }
    if path:
        error["path"] = _display_path(Path(path))
    return error


def _sorted_unique_errors(
    errors: Iterable[dict[str, str]],
) -> tuple[dict[str, str], ...]:
    unique = {
        (
            str(error.get("type") or ""),
            str(error.get("table") or ""),
            str(error.get("path") or ""),
            str(error.get("message") or ""),
        ): dict(error)
        for error in errors
    }
    return tuple(
        unique[key]
        for key in sorted(
            unique,
            key=lambda item: (
                item[0],
                item[1].casefold(),
                item[2].casefold(),
                item[3],
            ),
        )
    )


@dataclass(frozen=True)
class ExcludedGenerateDataset:
    """A task output intentionally excluded from the managed model set."""

    canonical_identity: str
    display_identity: str
    dataset_type: str
    task_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_identity": self.canonical_identity,
            "display_identity": self.display_identity,
            "dataset_type": self.dataset_type,
            "task_paths": list(self.task_paths),
        }


@dataclass(frozen=True)
class ManagedGenerateAsset:
    """One immutable managed-table entry in a generate manifest."""

    canonical_identity: str
    display_identity: str
    short_name: str
    asset_role: str
    operational_layer: str
    ddl_path: str
    ddl_content_hash: str
    ddl_content: str
    ddl_columns_json: str
    task_paths: tuple[str, ...]
    task_content_hashes: tuple[str, ...]
    task_contents: tuple[str, ...]
    task_full_refresh_flags: tuple[bool, ...]
    target_model_path: str
    existing_target_hash: str
    execution_contract_json: str
    execution_evidence_hash: str
    lineage_evidence_hash: str
    inspection_target: bool
    managed: bool = True

    def execution_contract(self) -> dict[str, Any]:
        value = json.loads(self.execution_contract_json)
        return value if isinstance(value, dict) else {}

    def validation_asset(self) -> dict[str, Any]:
        columns = json.loads(self.ddl_columns_json)
        return {
            "ddl": {
                "columns": columns if isinstance(columns, list) else [],
            },
            "tasks": [
                {
                    "path": path,
                    "sql": content,
                    "is_full_refresh": is_full_refresh,
                }
                for path, content, is_full_refresh in zip(
                    self.task_paths,
                    self.task_contents,
                    self.task_full_refresh_flags,
                )
            ],
        }

    def inspection_content(self) -> dict[str, str]:
        main_task_contents = [
            content
            for content, is_full_refresh in zip(
                self.task_contents,
                self.task_full_refresh_flags,
            )
            if not is_full_refresh
        ]
        return {
            "ddl": self.ddl_content,
            "etl_sql": "\n".join(main_task_contents),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_identity": self.canonical_identity,
            "display_identity": self.display_identity,
            "short_name": self.short_name,
            "asset_role": self.asset_role,
            "operational_layer": self.operational_layer,
            "ddl_path": self.ddl_path,
            "ddl_content_hash": self.ddl_content_hash,
            "task_paths": list(self.task_paths),
            "task_content_hashes": list(self.task_content_hashes),
            "target_model_path": self.target_model_path,
            "existing_target_hash": self.existing_target_hash,
            "execution_contract": self.execution_contract(),
            "execution_evidence_hash": self.execution_evidence_hash,
            "lineage_evidence_hash": self.lineage_evidence_hash,
            "inspection_target": self.inspection_target,
            "managed": self.managed,
        }


@dataclass(frozen=True)
class GenerateAssetManifest:
    """Frozen preflight input and publication-CAS snapshot."""

    schema_version: int
    project: str
    project_config_hash: str
    project_config_source_hash: str
    catalog_snapshot_hash: str
    catalog_snapshot_json: str
    lineage_snapshot_json: str
    base_formal_files_hash: str
    formal_file_hashes: tuple[tuple[str, str], ...]
    inspection_target_set: tuple[str, ...]
    expected_model_paths: tuple[str, ...]
    existing_model_paths: tuple[str, ...]
    assets: tuple[ManagedGenerateAsset, ...]
    excluded_datasets: tuple[ExcludedGenerateDataset, ...]
    manifest_hash: str

    def asset_for_table(self, table_name: str) -> ManagedGenerateAsset:
        wanted = str(table_name or "").casefold()
        matches = [
            asset
            for asset in self.assets
            if asset.short_name.casefold() == wanted
        ]
        if len(matches) != 1:
            raise KeyError(
                f"manifest table must resolve uniquely: {table_name!r}, "
                f"matches={len(matches)}"
            )
        return matches[0]

    def lineage_data(self) -> dict[str, Any]:
        value = json.loads(self.lineage_snapshot_json)
        return value if isinstance(value, dict) else {}

    def catalog_data(self) -> dict[str, Any]:
        value = json.loads(self.catalog_snapshot_json)
        return value if isinstance(value, dict) else {}

    def validation_assets(self) -> dict[str, dict[str, Any]]:
        return {
            asset.short_name: asset.validation_asset() for asset in self.assets
        }

    def inspection_content(self) -> dict[str, dict[str, str]]:
        return {
            asset.short_name: asset.inspection_content()
            for asset in self.assets
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "project_config_hash": self.project_config_hash,
            "project_config_source_hash": self.project_config_source_hash,
            "catalog_snapshot_hash": self.catalog_snapshot_hash,
            "base_formal_files_hash": self.base_formal_files_hash,
            "formal_file_hashes": dict(self.formal_file_hashes),
            "inspection_target_set": list(self.inspection_target_set),
            "expected_model_paths": list(self.expected_model_paths),
            "existing_model_paths": list(self.existing_model_paths),
            "assets": [asset.to_dict() for asset in self.assets],
            "excluded_datasets": [
                dataset.to_dict() for dataset in self.excluded_datasets
            ],
            "manifest_hash": self.manifest_hash,
        }


@dataclass(frozen=True)
class GenerateAssetPreflight:
    """Manifest plus deterministic hard-block findings."""

    manifest: GenerateAssetManifest
    errors: tuple[dict[str, str], ...]

    @property
    def passed(self) -> bool:
        return not self.errors

    def validation(self) -> dict[str, Any]:
        return {
            "status": "passed" if self.passed else "blocked",
            "stage": "preflight",
            "error_count": len(self.errors),
            "errors": [dict(error) for error in self.errors],
            "blocked_tables": sorted(
                {
                    str(error.get("table") or "")
                    for error in self.errors
                    if str(error.get("table") or "")
                },
                key=str.casefold,
            ),
            "reinspection_tables": [],
        }


def _project_dir(project: str) -> Path:
    config = PROJECT_CONFIG.get(project)
    if not config:
        raise KeyError(f"未知项目: {project}")
    return project_root() / str(config["dir"])


def _project_config_source_path(project: str) -> Path | None:
    config = PROJECT_CONFIG.get(project) or {}
    configured_path = str(config.get("warehouse_config_path") or "").strip()
    if configured_path:
        path = Path(configured_path)
        return path if path.is_absolute() else project_root() / path

    warehouses_root = project_root() / "warehouses"
    if not warehouses_root.exists():
        return None
    source_path = None
    for path in sorted(warehouses_root.glob("*/warehouse.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING))
        except (OSError, yaml.YAMLError):
            continue
        source_project = str(
            (payload or {}).get("name") or path.parent.name
        ).strip()
        if source_project == project:
            source_path = path
    return source_path


def _asset_role(project_dir: Path, ddl_path: Path) -> str:
    try:
        parts = ddl_path.relative_to(project_dir).parts
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


def _operational_layer(asset_role: str, table_name: str) -> str:
    if asset_role == "ods":
        return "ODS"
    if asset_role == "ads":
        return "ADS"
    if asset_role == "mid":
        inferred = str(_layer_from_table_name(table_name) or "").upper()
        return inferred if inferred in INSPECTION_LAYERS else "DWD"
    return ""


def _target_model_path(
    project_dir: Path,
    ddl_path: Path,
    asset_role: str,
    table_name: str,
) -> Path:
    if asset_role == "ods":
        relative = ddl_path.relative_to(project_dir / "ods" / "ddl")
        return project_dir / "ods" / "models" / relative.with_suffix(".yaml")
    return project_dir / asset_role / "models" / f"{table_name}.yaml"


def _identity(
    name: str,
    *,
    default_catalog: str,
    default_database: str,
) -> tuple[tuple[str, str, str], str, str]:
    catalog, database, table = table_identity(
        name,
        default_catalog=default_catalog,
        default_db=default_database,
    )
    display = qualified_table_name(catalog, database, table)
    key = table_identity_match_key(
        display,
        default_catalog=default_catalog,
        default_db=default_database,
    )
    canonical = ".".join(key)
    return key, canonical, display


def _lineage_snapshot(
    project: str,
    *,
    default_catalog: str,
    default_database: str,
    lineage_data: dict[str, Any] | None = None,
) -> tuple[
    str,
    str,
    dict[tuple[str, str, str], str],
    list[dict[str, str]],
]:
    path = lineage_data_path(project)
    if lineage_data is not None:
        payload = lineage_data
        content = _json_bytes(payload)
    elif not path.exists():
        return ABSENT_CONTENT_HASH, "{}", {}, []
    else:
        content = path.read_bytes()
        try:
            payload = json.loads(content.decode(TEXT_ENCODING))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return (
                _content_hash(content),
                "{}",
                {},
                [
                    _preflight_error(
                        "lineage_snapshot_invalid",
                        path=path,
                        message=(
                            "lineage snapshot is not valid JSON: "
                            f"{type(exc).__name__}"
                        ),
                    )
                ],
            )
    if not isinstance(payload, dict):
        return (
            _content_hash(content),
            "{}",
            {},
            [
                _preflight_error(
                    "lineage_snapshot_invalid",
                    path=path,
                    message="lineage snapshot root must be a mapping",
                )
            ],
        )
    excluded: dict[tuple[str, str, str], str] = {}
    for dataset in payload.get("tables") or []:
        if not isinstance(dataset, dict):
            continue
        dataset_type = str(dataset.get("dataset_type") or "").casefold()
        if dataset_type not in {"process", "temporary"}:
            continue
        name = str(dataset.get("full_name") or dataset.get("name") or "")
        key, _canonical, _display = _identity(
            name,
            default_catalog=default_catalog,
            default_database=default_database,
        )
        if all(key):
            excluded[key] = dataset_type
    return (
        _content_hash(content),
        _json_bytes(payload).decode(TEXT_ENCODING),
        excluded,
        [],
    )


def _asset_identity_defaults(
    project_dir: Path,
    path: Path,
    asset_kind: str,
    *,
    default_catalog: str,
    default_database: str,
) -> tuple[str, str]:
    try:
        parts = path.relative_to(project_dir).parts
    except ValueError:
        return default_catalog, default_database
    if len(parts) >= 5 and parts[0] == "ods" and parts[1] == asset_kind:
        return str(parts[2]), str(parts[3])
    return default_catalog, default_database


def _explicit_identity_parts(name: str) -> tuple[str, ...]:
    return tuple(
        part.strip().strip("`").strip('"')
        for part in str(name or "").split(".")
        if part.strip()
    )


def _explicit_identity_mismatches_directory(
    name: str,
    *,
    catalog: str,
    database: str,
) -> bool:
    parts = _explicit_identity_parts(name)
    if len(parts) == 2:
        return parts[0].casefold() != database.casefold()
    if len(parts) >= 3:
        return (
            parts[-3].casefold() != catalog.casefold()
            or parts[-2].casefold() != database.casefold()
        )
    return False


def _is_ods_asset_path(
    project_dir: Path,
    path: Path,
    asset_kind: str,
) -> bool:
    try:
        parts = path.relative_to(project_dir).parts
    except ValueError:
        return False
    return len(parts) >= 5 and parts[:2] == ("ods", asset_kind)


def _formal_file_hashes(
    project: str,
    expected_model_paths: Iterable[Path],
) -> tuple[tuple[str, str], ...]:
    project_dir = _project_dir(project)
    paths = set(expected_model_paths)
    for root in (
        project_dir / "ods" / "models",
        project_dir / "mid" / "models",
        project_dir / "ads" / "models",
    ):
        if root.exists():
            paths.update(root.rglob("*.yaml"))
    semantic_paths = business_semantics_paths(project)
    paths.update(semantic_paths.values())
    paths.add(project_dir / LEGACY_BUSINESS_SEMANTICS_FILE_NAME)
    return tuple(
        (_display_path(path), _path_content_hash(path))
        for path in sorted(paths, key=lambda item: item.as_posix().casefold())
    )


def _task_records(
    project: str,
    *,
    project_dir: Path,
    default_catalog: str,
    default_database: str,
    lineage_excluded: dict[tuple[str, str, str], str],
) -> tuple[
    dict[tuple[str, str, str], list[dict[str, Any]]],
    dict[tuple[str, str, str], dict[str, Any]],
    set[tuple[str, str, str]],
    list[dict[str, str]],
]:
    outputs: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    excluded: dict[tuple[str, str, str], dict[str, Any]] = {}
    task_created_outputs: set[tuple[str, str, str]] = set()
    errors: list[dict[str, str]] = []
    for task_path in iter_project_task_files(project):
        task_catalog, task_database = _asset_identity_defaults(
            project_dir,
            task_path,
            "tasks",
            default_catalog=default_catalog,
            default_database=default_database,
        )
        content = task_path.read_bytes()
        try:
            text = content.decode(TEXT_ENCODING)
            facts = extract_task_table_facts(
                text,
                _display_path(task_path),
                default_catalog=task_catalog,
                default_db=task_database,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append(
                _preflight_error(
                    "task_sql_unparseable",
                    path=task_path,
                    message=f"task SQL facts cannot be extracted: {type(exc).__name__}",
                )
            )
            continue
        record = {
            "path": task_path,
            "display_path": _display_path(task_path),
            "content_hash": _content_hash(content),
            "content": text,
            "is_full_refresh": task_path.parent.name == "full_refresh",
        }
        created_keys = {
            _identity(
                raw_name,
                default_catalog=task_catalog,
                default_database=task_database,
            )[0]
            for raw_name in facts.get("created_tables") or []
        }
        for raw_name in facts.get("output_tables") or []:
            if _is_ods_asset_path(
                project_dir,
                task_path,
                "tasks",
            ) and _explicit_identity_mismatches_directory(
                raw_name,
                catalog=task_catalog,
                database=task_database,
            ):
                errors.append(
                    _preflight_error(
                        "task_identity_directory_mismatch",
                        path=task_path,
                        message=(
                            f"ODS task output {raw_name!r} does not match "
                            "its catalog/database directory: "
                            f"{task_catalog}.{task_database}"
                        ),
                    )
                )
            key, canonical, display = _identity(
                raw_name,
                default_catalog=task_catalog,
                default_database=task_database,
            )
            if not all(key):
                errors.append(
                    _preflight_error(
                        "task_output_unresolved",
                        path=task_path,
                        message=f"task output has no stable table identity: {raw_name!r}",
                    )
                )
                continue
            dataset_type = (
                lineage_excluded.get(key) if key in created_keys else None
            )
            if dataset_type:
                item = excluded.setdefault(
                    key,
                    {
                        "canonical_identity": canonical,
                        "display_identity": display,
                        "dataset_type": dataset_type,
                        "task_paths": set(),
                    },
                )
                item["task_paths"].add(record["display_path"])
                continue
            outputs.setdefault(key, []).append(record)
            if key in created_keys:
                task_created_outputs.add(key)
        for transient in facts.get("local_lifecycle_tables") or []:
            raw_name = str(transient.get("name") or "")
            key, canonical, display = _identity(
                raw_name,
                default_catalog=task_catalog,
                default_database=task_database,
            )
            if not all(key):
                continue
            item = excluded.setdefault(
                key,
                {
                    "canonical_identity": canonical,
                    "display_identity": display,
                    "dataset_type": "temporary",
                    "task_paths": set(),
                },
            )
            item["task_paths"].add(record["display_path"])
    return outputs, excluded, task_created_outputs, errors


def build_generate_asset_preflight(
    project: str,
    catalog: dict[str, Any],
    *,
    lineage_data: dict[str, Any] | None = None,
) -> GenerateAssetPreflight:
    """Build the immutable generate manifest and all deterministic findings."""
    config = PROJECT_CONFIG.get(project)
    if not config:
        raise KeyError(f"未知项目: {project}")
    config_source_path = _project_config_source_path(project)
    project_dir = _project_dir(project)
    default_catalog = str(config.get("catalog") or "internal")
    default_database = str(config.get("db") or project_dir.name)
    errors: list[dict[str, str]] = []
    if config_source_path is not None:
        if not config_source_path.exists():
            errors.append(
                _preflight_error(
                    "project_config_source_missing",
                    path=config_source_path,
                    message=(
                        "cached PROJECT_CONFIG source warehouse.yaml is "
                        "missing"
                    ),
                )
            )
        else:
            try:
                fresh_config = load_warehouse_config(
                    config_source_path,
                    project_root=project_root(),
                )
            except (OSError, ValueError, yaml.YAMLError) as exc:
                errors.append(
                    _preflight_error(
                        "project_config_source_invalid",
                        path=config_source_path,
                        message=(
                            "warehouse.yaml source cannot be loaded: "
                            f"{type(exc).__name__}"
                        ),
                    )
                )
            else:
                if _json_hash(fresh_config) != _json_hash(config):
                    errors.append(
                        _preflight_error(
                            "project_config_stale",
                            path=config_source_path,
                            message=(
                                "cached PROJECT_CONFIG does not match the "
                                "current warehouse.yaml source"
                            ),
                        )
                    )
    catalog_paths = business_semantics_paths(project)
    if catalog_paths and all(path.exists() for path in catalog_paths.values()):
        fresh_catalog = load_business_semantics_catalog_from_dir(
            next(iter(catalog_paths.values())).parent,
            project=project,
        )
        comparable_catalog = dict(catalog)
        comparable_catalog.setdefault("project", project)
        if _json_hash(fresh_catalog) != _json_hash(comparable_catalog):
            errors.append(
                _preflight_error(
                    "catalog_snapshot_stale",
                    message=(
                        "catalog mapping does not match the current split "
                        "catalog YAML files"
                    ),
                )
            )
    (
        lineage_hash,
        lineage_snapshot_json,
        lineage_excluded,
        lineage_errors,
    ) = _lineage_snapshot(
        project,
        default_catalog=default_catalog,
        default_database=default_database,
        lineage_data=lineage_data,
    )
    errors.extend(lineage_errors)
    (
        task_outputs,
        excluded_records,
        task_created_outputs,
        task_errors,
    ) = _task_records(
        project,
        project_dir=project_dir,
        default_catalog=default_catalog,
        default_database=default_database,
        lineage_excluded=lineage_excluded,
    )
    errors.extend(task_errors)

    ddl_records: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for ddl_path in iter_project_asset_files(project, "ddl", "*.sql"):
        ddl_catalog, ddl_database = _asset_identity_defaults(
            project_dir,
            ddl_path,
            "ddl",
            default_catalog=default_catalog,
            default_database=default_database,
        )
        content = ddl_path.read_bytes()
        try:
            ddl_text = content.decode(TEXT_ENCODING)
            table_def = parse_create_table(ddl_text)
        except (UnicodeDecodeError, ValueError):
            table_def = None
        if table_def is None or not str(table_def.short_name or "").strip():
            errors.append(
                _preflight_error(
                    "ddl_unparseable",
                    path=ddl_path,
                    message="DDL cannot be parsed into a stable table identity",
                )
            )
            continue
        key, canonical, display = _identity(
            table_def.full_name,
            default_catalog=ddl_catalog,
            default_database=ddl_database,
        )
        role = _asset_role(project_dir, ddl_path)
        short_name = short_table_name(table_def.short_name)
        if not role:
            errors.append(
                _preflight_error(
                    "ddl_asset_role_unknown",
                    table=display,
                    path=ddl_path,
                    message="DDL path is outside ods/mid/ads managed roots",
                )
            )
            continue
        if role == "ods" and _explicit_identity_mismatches_directory(
            table_def.full_name,
            catalog=ddl_catalog,
            database=ddl_database,
        ):
            errors.append(
                _preflight_error(
                    "ddl_identity_directory_mismatch",
                    table=display,
                    path=ddl_path,
                    message=(
                        "ODS DDL qualifier does not match its "
                        f"catalog/database directory: "
                        f"{ddl_catalog}.{ddl_database}"
                    ),
                )
            )
        if ddl_path.stem.casefold() != short_name.casefold():
            errors.append(
                _preflight_error(
                    "ddl_filename_mismatch",
                    table=display,
                    path=ddl_path,
                    message=(
                        f"DDL file stem={ddl_path.stem!r} does not match "
                        f"declared table={short_name!r}"
                    ),
                )
            )
        ddl_records.setdefault(key, []).append(
            {
                "canonical_identity": canonical,
                "display_identity": display,
                "short_name": short_name,
                "asset_role": role,
                "operational_layer": _operational_layer(role, short_name),
                "path": ddl_path,
                "content_hash": _content_hash(content),
                "content": ddl_text,
                "table_def": table_def,
            }
        )

    for key, records in sorted(ddl_records.items()):
        if len(records) > 1:
            errors.append(
                _preflight_error(
                    "ddl_identity_conflict",
                    table=records[0]["display_identity"],
                    message=(
                        "multiple DDL files declare the same canonical identity: "
                        + ", ".join(
                            sorted(
                                _display_path(record["path"])
                                for record in records
                            )
                        )
                    ),
                )
            )
        if key in excluded_records:
            errors.append(
                _preflight_error(
                    "excluded_dataset_has_managed_ddl",
                    table=records[0]["display_identity"],
                    message=(
                        "dataset_type="
                        f"{excluded_records[key]['dataset_type']} conflicts with "
                        "a managed DDL"
                    ),
                )
            )

    for key in sorted(task_created_outputs):
        if key in ddl_records or key not in task_outputs:
            continue
        records = task_outputs.pop(key)
        item = excluded_records.setdefault(
            key,
            {
                "canonical_identity": ".".join(key),
                "display_identity": ".".join(key),
                "dataset_type": "process",
                "task_paths": set(),
            },
        )
        item["task_paths"].update(record["display_path"] for record in records)

    for key, task_records in sorted(task_outputs.items()):
        if key in ddl_records:
            continue
        _catalog, _database, table = key
        errors.append(
            _preflight_error(
                "task_target_missing_ddl",
                table=".".join(key),
                message=(
                    "persistent task target has no managed DDL: "
                    f"{table}; tasks="
                    + ", ".join(
                        sorted(
                            record["display_path"] for record in task_records
                        )
                    )
                ),
            )
        )

    assets: list[ManagedGenerateAsset] = []
    target_path_keys: dict[str, list[dict[str, Any]]] = {}
    for key, records in sorted(ddl_records.items()):
        record = records[0]
        target_path = _target_model_path(
            project_dir,
            record["path"],
            record["asset_role"],
            record["short_name"],
        )
        target_path_keys.setdefault(
            target_path.as_posix().casefold(), []
        ).append(
            {
                "table": record["display_identity"],
                "path": target_path,
            }
        )
        table_tasks = sorted(
            task_outputs.get(key, []),
            key=lambda item: item["display_path"].casefold(),
        )
        main_tasks = [
            task for task in table_tasks if not task["is_full_refresh"]
        ]
        if (
            record["asset_role"] in {"mid", "ads"}
            and record["operational_layer"] not in {"DWD", "DWS"}
            and not main_tasks
        ):
            errors.append(
                _preflight_error(
                    "execution_task_missing",
                    table=record["short_name"],
                    path=record["path"],
                    message=(
                        f"{record['operational_layer']} execution cannot be "
                        "inferred without task SQL"
                    ),
                )
            )
        execution_asset = {
            "ddl": {
                "columns": [
                    {"name": column.name, "type": column.data_type}
                    for column in record["table_def"].columns
                ]
            },
            "tasks": [
                {
                    "path": task["path"],
                    "sql": task["content"],
                    "is_full_refresh": task["is_full_refresh"],
                }
                for task in table_tasks
            ],
        }
        execution = infer_execution_mapping(
            record["short_name"],
            execution_asset,
            layer=record["operational_layer"],
        )
        errors.extend(
            _validate_execution(
                record["short_name"],
                {
                    "layer": record["operational_layer"],
                    "execution": execution,
                },
                execution_asset,
            )
        )
        execution_json = _json_bytes(execution).decode(TEXT_ENCODING)
        assets.append(
            ManagedGenerateAsset(
                canonical_identity=record["canonical_identity"],
                display_identity=record["display_identity"],
                short_name=record["short_name"],
                asset_role=record["asset_role"],
                operational_layer=record["operational_layer"],
                ddl_path=_display_path(record["path"]),
                ddl_content_hash=record["content_hash"],
                ddl_content=record["content"],
                ddl_columns_json=_json_bytes(
                    execution_asset["ddl"]["columns"]
                ).decode(TEXT_ENCODING),
                task_paths=tuple(task["display_path"] for task in table_tasks),
                task_content_hashes=tuple(
                    task["content_hash"] for task in table_tasks
                ),
                task_contents=tuple(task["content"] for task in table_tasks),
                task_full_refresh_flags=tuple(
                    task["is_full_refresh"] for task in table_tasks
                ),
                target_model_path=_display_path(target_path),
                existing_target_hash=_path_content_hash(target_path),
                execution_contract_json=execution_json,
                execution_evidence_hash=_json_hash(
                    {
                        "execution": execution,
                        "task_hashes": [
                            task["content_hash"] for task in table_tasks
                        ],
                    }
                ),
                lineage_evidence_hash=lineage_hash,
                inspection_target=(
                    record["operational_layer"] in INSPECTION_LAYERS
                ),
            )
        )

    for collisions in target_path_keys.values():
        if len(collisions) <= 1:
            continue
        errors.append(
            _preflight_error(
                "model_path_conflict",
                table=", ".join(sorted(item["table"] for item in collisions)),
                path=collisions[0]["path"],
                message=(
                    "multiple canonical identities map to the same casefold "
                    "model path"
                ),
            )
        )

    short_name_groups: dict[str, list[ManagedGenerateAsset]] = {}
    for asset in assets:
        short_name_groups.setdefault(asset.short_name.casefold(), []).append(
            asset
        )
    for collisions in short_name_groups.values():
        if len(collisions) <= 1:
            continue
        errors.append(
            _preflight_error(
                "model_key_conflict",
                table=", ".join(
                    sorted(asset.display_identity for asset in collisions)
                ),
                message=(
                    "multiple fully-qualified identities share one short model "
                    "key; the current candidate mapping cannot represent both"
                ),
            )
        )

    expected_paths = tuple(sorted(asset.target_model_path for asset in assets))
    if len({path.casefold() for path in expected_paths}) != len(
        expected_paths
    ):
        errors.append(
            _preflight_error(
                "expected_model_set_incomplete",
                message="expected managed model path set is not unique",
            )
        )
    formal_hashes = _formal_file_hashes(
        project,
        (project_root() / path for path in expected_paths),
    )
    existing_model_paths = tuple(
        path
        for path, content_hash in formal_hashes
        if "/models/" in f"/{path}" and content_hash != ABSENT_CONTENT_HASH
    )
    existing_path_groups: dict[str, list[str]] = {}
    for path in existing_model_paths:
        existing_path_groups.setdefault(path.casefold(), []).append(path)
    for collisions in existing_path_groups.values():
        if len(collisions) <= 1:
            continue
        errors.append(
            _preflight_error(
                "existing_model_path_conflict",
                path=project_root() / collisions[0],
                message=(
                    "existing managed model files collide under casefold: "
                    + ", ".join(sorted(collisions))
                ),
            )
        )
    excluded_datasets = tuple(
        ExcludedGenerateDataset(
            canonical_identity=item["canonical_identity"],
            display_identity=item["display_identity"],
            dataset_type=item["dataset_type"],
            task_paths=tuple(sorted(item["task_paths"])),
        )
        for _key, item in sorted(excluded_records.items())
    )
    manifest_payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project": project,
        "project_config_hash": _json_hash(config),
        "project_config_source_hash": (
            _path_content_hash(config_source_path)
            if config_source_path is not None
            else ABSENT_CONTENT_HASH
        ),
        "catalog_snapshot_hash": _json_hash(catalog),
        "lineage_snapshot_hash": lineage_hash,
        "base_formal_files_hash": _json_hash(formal_hashes),
        "formal_file_hashes": formal_hashes,
        "inspection_target_set": sorted(
            asset.canonical_identity
            for asset in assets
            if asset.inspection_target
        ),
        "expected_model_paths": expected_paths,
        "existing_model_paths": existing_model_paths,
        "assets": [asset.to_dict() for asset in assets],
        "excluded_datasets": [
            dataset.to_dict() for dataset in excluded_datasets
        ],
    }
    manifest = GenerateAssetManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        project=project,
        project_config_hash=manifest_payload["project_config_hash"],
        project_config_source_hash=manifest_payload[
            "project_config_source_hash"
        ],
        catalog_snapshot_hash=manifest_payload["catalog_snapshot_hash"],
        catalog_snapshot_json=_json_bytes(catalog).decode(TEXT_ENCODING),
        lineage_snapshot_json=lineage_snapshot_json,
        base_formal_files_hash=manifest_payload["base_formal_files_hash"],
        formal_file_hashes=formal_hashes,
        inspection_target_set=tuple(manifest_payload["inspection_target_set"]),
        expected_model_paths=expected_paths,
        existing_model_paths=existing_model_paths,
        assets=tuple(assets),
        excluded_datasets=excluded_datasets,
        manifest_hash=_json_hash(manifest_payload),
    )
    return GenerateAssetPreflight(
        manifest=manifest,
        errors=_sorted_unique_errors(errors),
    )


def revalidate_generate_asset_manifest(
    expected: GenerateAssetManifest,
    *,
    catalog: dict[str, Any],
    candidate_table_names: Iterable[str],
    candidate_declared_names: Iterable[tuple[str, str]],
    rendered_model_paths: Iterable[Path],
    lineage_data: dict[str, Any] | None = None,
) -> GenerateAssetPreflight:
    """Rebuild fingerprints and verify the expected publication model set."""
    current = build_generate_asset_preflight(
        expected.project,
        catalog,
        lineage_data=lineage_data,
    )
    errors = [dict(error) for error in current.errors]
    if current.manifest.manifest_hash != expected.manifest_hash:
        errors.append(
            _preflight_error(
                "asset_manifest_changed",
                message=(
                    "DDL/task/config/lineage/catalog or formal files changed "
                    "after generate preflight"
                ),
            )
        )
    candidate_names = [str(name) for name in candidate_table_names]
    expected_names = [asset.short_name for asset in expected.assets]
    candidate_name_keys = [name.casefold() for name in candidate_names]
    expected_name_keys = [name.casefold() for name in expected_names]
    if (
        len(set(candidate_name_keys)) != len(candidate_name_keys)
        or set(candidate_name_keys) != set(expected_name_keys)
        or set(candidate_names) != set(expected_names)
    ):
        errors.append(
            _preflight_error(
                "candidate_model_set_changed",
                message=(
                    "candidate table set differs from immutable manifest; "
                    f"expected={sorted(expected_names)}, "
                    f"actual={sorted(candidate_names)}"
                ),
            )
        )
    expected_name_by_key = {
        asset.short_name: asset.short_name for asset in expected.assets
    }
    candidate_identities = list(candidate_declared_names)
    if len(candidate_identities) != len(expected_name_by_key) or any(
        key not in expected_name_by_key
        or declared_name != expected_name_by_key[key]
        for key, declared_name in candidate_identities
    ):
        errors.append(
            _preflight_error(
                "candidate_model_identity_changed",
                message=(
                    "candidate YAML names differ from immutable manifest; "
                    f"expected={sorted(expected_name_by_key.items())}, "
                    f"actual={sorted(candidate_identities)}"
                ),
            )
        )
    rendered_paths = [
        _display_path(Path(path)) for path in rendered_model_paths
    ]
    expected_paths = list(expected.expected_model_paths)
    rendered_path_keys = [path.casefold() for path in rendered_paths]
    expected_path_keys = [path.casefold() for path in expected_paths]
    if (
        len(set(rendered_path_keys)) != len(rendered_path_keys)
        or set(rendered_path_keys) != set(expected_path_keys)
        or set(rendered_paths) != set(expected_paths)
    ):
        errors.append(
            _preflight_error(
                "expected_model_set_changed",
                message=(
                    "rendered model path set differs from immutable manifest; "
                    f"expected={sorted(expected_paths)}, "
                    f"actual={sorted(rendered_paths)}"
                ),
            )
        )
    return GenerateAssetPreflight(
        manifest=current.manifest,
        errors=_sorted_unique_errors(errors),
    )
