"""Stable fingerprints for refactor analysis and shadow execution inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import dw_refactor_agent.config as config
from dw_refactor_agent.refactor.artifact_contract import sha256_json

TOOL_SOURCE_DIRECTORIES = (
    "src/dw_refactor_agent/refactor",
    "src/dw_refactor_agent/lineage",
    "src/dw_refactor_agent/ddl_deriver",
    "src/dw_refactor_agent/execution",
    "src/dw_refactor_agent/config",
    "src/dw_refactor_agent/sql",
)
PROJECT_ASSET_PATTERNS = (
    "ods/ddl/**/*.sql",
    "mid/ddl/**/*.sql",
    "ads/ddl/**/*.sql",
    "ods/tasks/**/*.sql",
    "mid/tasks/**/*.sql",
    "ads/tasks/**/*.sql",
    "ods/models/**/*.yaml",
    "ods/models/**/*.yml",
    "mid/models/**/*.yaml",
    "mid/models/**/*.yml",
    "ads/models/**/*.yaml",
    "ads/models/**/*.yml",
)


def _configured_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    candidate = path if path.is_absolute() else root / path
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            f"workspace fingerprint input is outside project root: {raw_path}"
        ) from None
    return candidate


def _project_input_paths(root: Path, project: str) -> set[Path]:
    project_config = config.PROJECT_CONFIG.get(project)
    if not project_config:
        raise ValueError(
            f"unknown project for workspace fingerprint: {project}"
        )
    project_dir = _configured_path(root, project_config["dir"])
    paths = set()
    for pattern in PROJECT_ASSET_PATTERNS:
        paths.update(project_dir.glob(pattern))

    paths.add(project_dir / "warehouse.yaml")
    paths.add(project_dir / "naming_config.yaml")
    for file_name in config.BUSINESS_SEMANTICS_FILE_NAMES.values():
        paths.add(project_dir / file_name)

    naming_config = project_config.get("naming_config")
    if naming_config:
        paths.add(_configured_path(root, naming_config))
    else:
        paths.add(root / "naming_config.yaml")
    return paths


def _tool_input_paths(root: Path) -> set[Path]:
    paths = set()
    for relative_dir in TOOL_SOURCE_DIRECTORIES:
        source_dir = root / relative_dir
        if source_dir.is_dir():
            paths.update(source_dir.rglob("*.py"))
    return paths


def _content_digest(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def workspace_file_entries(root: Path, project: str) -> list[dict]:
    """Return path-sorted content hashes for every relevant input file."""
    root = Path(root).resolve()
    candidates = _project_input_paths(root, project) | _tool_input_paths(root)
    entries = {}
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            raise ValueError(
                f"workspace fingerprint input is outside project root: "
                f"{candidate}"
            ) from None
        entries[relative] = {
            "path": relative,
            "content_sha256": _content_digest(resolved),
        }
    return [entries[path] for path in sorted(entries)]


def workspace_fingerprint(root: Path, project: str) -> str:
    """Hash all inputs that can affect analysis or shadow execution."""
    return sha256_json(
        {
            "fingerprint_version": 1,
            "project": project,
            "files": workspace_file_entries(root, project),
        }
    )
