"""
Core repository and runtime configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT_ENV = "DW_REFACTOR_AGENT_ROOT"


def resolve_project_root(
    *,
    default_root: Path | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Resolve the repository root that owns warehouses/."""
    env_map = os.environ if env is None else env
    override = str(env_map.get(PROJECT_ROOT_ENV) or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    candidate = (
        Path(default_root)
        if default_root is not None
        else DEFAULT_PROJECT_ROOT
    )
    if (candidate / "warehouses").exists():
        return candidate

    cwd_candidate = Path(cwd) if cwd is not None else Path.cwd()
    if (cwd_candidate / "warehouses").exists():
        return cwd_candidate

    return candidate


PROJECT_ROOT = resolve_project_root()
WAREHOUSES_ROOT = PROJECT_ROOT / "warehouses"
TEXT_ENCODING = "utf-8"

# Stable layer order for dependency checks and display sorting. Table layer
# ownership comes from model YAML, not table-name prefixes.
LAYER_ORDER = [
    ["ODS"],
    ["DIM", "DWD"],
    ["DWS"],
    ["ADS"],
]


def _relative_to_project(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _warehouse_relative_path(
    warehouse_dir: Path,
    value: str | None,
    project_root: Path = PROJECT_ROOT,
) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return _relative_to_project(warehouse_dir, project_root)

    path = Path(raw_value)
    if path.is_absolute():
        return _relative_to_project(path, project_root)

    if raw_value.startswith("warehouses/"):
        return raw_value
    return _relative_to_project(warehouse_dir / path, project_root)


def load_warehouse_config(
    path: Path,
    project_root: Path | None = None,
) -> dict:
    """Load one warehouse.yaml into the runtime PROJECT_CONFIG shape."""
    warehouse_file = Path(path)
    warehouse_dir = warehouse_file.parent
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    data = yaml.safe_load(warehouse_file.read_text(encoding=TEXT_ENCODING))
    if not isinstance(data, dict):
        raise ValueError(
            f"warehouse 配置必须是 YAML mapping: {warehouse_file}"
        )

    project = str(data.get("name") or warehouse_dir.name).strip()
    if not project:
        raise ValueError(f"warehouse 配置缺少 name: {warehouse_file}")

    catalog = str(data.get("catalog") or "internal")
    default_dialect = str(data.get("default_dialect") or "doris")
    raw_dialects = data.get("ods_source_catalog_dialects") or {
        catalog: default_dialect
    }
    if not isinstance(raw_dialects, dict):
        raise ValueError(
            f"ods_source_catalog_dialects 必须是 mapping: {warehouse_file}"
        )

    raw_verification = data.get("verification") or {}
    if not isinstance(raw_verification, dict):
        raise ValueError(f"verification 必须是 mapping: {warehouse_file}")
    raw_execution = data.get("execution") or {}
    if not isinstance(raw_execution, dict):
        raise ValueError(f"execution 必须是 mapping: {warehouse_file}")
    raw_schema_identity = data.get("schema_identity") or {}
    if not isinstance(raw_schema_identity, dict):
        raise ValueError(f"schema_identity 必须是 mapping: {warehouse_file}")

    config = {
        "dir": _warehouse_relative_path(warehouse_dir, data.get("dir"), root),
        "catalog": catalog,
        "db": str(data.get("db") or data.get("database") or ""),
        "qa_db": str(data.get("qa_db") or data.get("qa_database") or ""),
        "lineage_db": str(
            data.get("lineage_db") or data.get("lineage_database") or ""
        ),
        "naming_config": _warehouse_relative_path(
            warehouse_dir,
            data.get("naming_config") or "naming_config.yaml",
            root,
        ),
        "ods_source_catalog_dialects": {
            str(raw_catalog): str(raw_dialect or default_dialect)
            for raw_catalog, raw_dialect in raw_dialects.items()
            if str(raw_catalog or "").strip()
        },
    }
    if raw_verification:
        config["verification"] = dict(raw_verification)
    if raw_execution:
        config["execution"] = dict(raw_execution)
    if raw_schema_identity:
        config["schema_identity"] = dict(raw_schema_identity)
    return config


def load_project_config(root: Path | None = None) -> dict[str, dict]:
    """Load all warehouse project configs from warehouses/*/warehouse.yaml."""
    project_root = Path(root) if root is not None else PROJECT_ROOT
    warehouses_root = project_root / "warehouses"
    configs = {}
    if not warehouses_root.exists():
        return configs

    for warehouse_file in sorted(warehouses_root.glob("*/warehouse.yaml")):
        data = yaml.safe_load(warehouse_file.read_text(encoding=TEXT_ENCODING))
        project = str((data or {}).get("name") or warehouse_file.parent.name)
        configs[project] = load_warehouse_config(
            warehouse_file,
            project_root=project_root,
        )
    return configs


# Each data mart project is sourced from warehouses/{project}/warehouse.yaml.
PROJECT_CONFIG = load_project_config()

PROJECT_MAP = PROJECT_CONFIG


# Database environment configuration for the MySQL protocol.
DB_ENV_CONFIG = {
    "prod": {
        "host": "172.16.0.90",
        "port": 19030,
        "user": "root",
        "qa_user": "qa",
    },
    "test": {
        "host": "172.16.0.90",
        "port": 9034,
        "user": "root",
        "qa_user": "qa",
    },
}

# Doris HTTP protocol configuration, used by Stream Load.
DORIS_HTTP_PORT = 8030

# Default prod shortcuts.
DORIS_HOST = DB_ENV_CONFIG["prod"]["host"]
DORIS_PORT = DB_ENV_CONFIG["prod"]["port"]
DORIS_USER = DB_ENV_CONFIG["prod"]["user"]
DORIS_QA_USER = DB_ENV_CONFIG["prod"]["qa_user"]


def get_mysql_cmd(env: str = "prod", qa: bool = False) -> list[str]:
    """Return mysql command-line arguments for a configured environment."""
    cfg = DB_ENV_CONFIG[env]
    user = cfg["qa_user"] if qa else cfg["user"]
    return ["mysql", f"-h{cfg['host']}", f"-P{cfg['port']}", f"-u{user}"]


def python_module_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment that can run ``python -m dw_refactor_agent``."""
    merged = dict(os.environ if env is None else env)
    src = str(SRC_ROOT)
    current = merged.get("PYTHONPATH")
    paths = [src]
    if current:
        paths.append(current)
    merged["PYTHONPATH"] = os.pathsep.join(paths)
    return merged
