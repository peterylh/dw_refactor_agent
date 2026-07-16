"""Project asset catalog collection for assess scoring."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dw_refactor_agent.config import PROJECT_CONFIG, TEXT_ENCODING
from dw_refactor_agent.ddl_deriver.ddl_deriver import parse_create_table
from dw_refactor_agent.lineage.sql_task_facts import extract_task_table_facts
from dw_refactor_agent.lineage.table_graph import _table_from_node
from dw_refactor_agent.sql.doris import extract_doris_partition_column

_MODEL_ROLE_EXPECTED_LAYERS = {
    "ods": ["ODS"],
    "mid": ["DIM", "DWD", "DWS"],
    "ads": ["ADS"],
}


class _RecordMapping(Mapping):
    """Read-only mapping compatibility for migrated domain records."""

    _mapping_fields: tuple[str, ...] = ()

    def __getitem__(self, key: str) -> Any:
        if key not in self._mapping_fields:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping_fields)

    def __len__(self) -> int:
        return len(self._mapping_fields)


@dataclass
class DdlAsset(_RecordMapping):
    """DDL facts associated with one governed table."""

    exists: bool
    path: Path | None
    file_stem: str | None
    declared_name: str
    columns: list[dict] = field(default_factory=list)
    key_type: str = ""
    key_columns: list[str] = field(default_factory=list)
    partition_column: str = ""

    _mapping_fields = (
        "exists",
        "path",
        "file_stem",
        "declared_name",
        "columns",
        "key_type",
        "key_columns",
        "partition_column",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DdlAsset":
        raw_path = value.get("path")
        return cls(
            exists=bool(value.get("exists")),
            path=Path(raw_path) if raw_path else None,
            file_stem=value.get("file_stem"),
            declared_name=str(value.get("declared_name") or ""),
            columns=list(value.get("columns") or []),
            key_type=str(value.get("key_type") or ""),
            key_columns=list(value.get("key_columns") or []),
            partition_column=str(value.get("partition_column") or ""),
        )


@dataclass
class ModelAsset(_RecordMapping):
    """Model-YAML facts associated with one governed table."""

    exists: bool
    path: Path | None
    file_stem: str | None
    declared_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    asset_role: str = ""
    expected_layers: list[str] = field(default_factory=list)

    _mapping_fields = (
        "exists",
        "path",
        "file_stem",
        "declared_name",
        "metadata",
        "asset_role",
        "expected_layers",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAsset":
        raw_path = value.get("path")
        return cls(
            exists=bool(value.get("exists")),
            path=Path(raw_path) if raw_path else None,
            file_stem=value.get("file_stem"),
            declared_name=str(value.get("declared_name") or ""),
            metadata=dict(value.get("metadata") or {}),
            asset_role=str(value.get("asset_role") or ""),
            expected_layers=list(value.get("expected_layers") or []),
        )


@dataclass
class TaskAsset(_RecordMapping):
    """Task-SQL facts associated with one or more governed tables."""

    path: Path | None = None
    file: str = ""
    expected_table: str = ""
    output_tables: set[str] = field(default_factory=set)
    transient_tables: list[dict] = field(default_factory=list)
    lineage_targets: set[str] = field(default_factory=set)
    is_full_refresh: bool = False
    source_file: str = ""
    sql: str = ""

    _mapping_fields = (
        "path",
        "file",
        "expected_table",
        "output_tables",
        "transient_tables",
        "lineage_targets",
        "is_full_refresh",
        "source_file",
        "sql",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TaskAsset":
        raw_path = value.get("path")
        return cls(
            path=Path(raw_path) if raw_path else None,
            file=str(value.get("file") or ""),
            expected_table=str(value.get("expected_table") or ""),
            output_tables=set(value.get("output_tables") or []),
            transient_tables=list(value.get("transient_tables") or []),
            lineage_targets=set(value.get("lineage_targets") or []),
            is_full_refresh=bool(value.get("is_full_refresh")),
            source_file=str(value.get("source_file") or ""),
            sql=str(value.get("sql") or ""),
        )


@dataclass
class TableAsset(_RecordMapping):
    """All discovered assets and facts for one logical table."""

    name: str
    layer: str = "OTHER"
    columns: list[dict] = field(default_factory=list)
    lineage_table: dict[str, Any] | None = None
    ddl: DdlAsset | None = None
    model: ModelAsset | None = None
    tasks: list[TaskAsset] = field(default_factory=list)

    _mapping_fields = (
        "name",
        "layer",
        "columns",
        "lineage_table",
        "ddl",
        "model",
        "tasks",
    )

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any], *, default_name: str = ""
    ) -> "TableAsset":
        raw_ddl = value.get("ddl")
        raw_model = value.get("model")
        return cls(
            name=str(value.get("name") or default_name),
            layer=str(value.get("layer") or "OTHER"),
            columns=list(value.get("columns") or []),
            lineage_table=(
                dict(value["lineage_table"])
                if isinstance(value.get("lineage_table"), Mapping)
                else None
            ),
            ddl=(
                raw_ddl
                if isinstance(raw_ddl, DdlAsset)
                else DdlAsset.from_mapping(raw_ddl)
                if isinstance(raw_ddl, Mapping) and raw_ddl
                else None
            ),
            model=(
                raw_model
                if isinstance(raw_model, ModelAsset)
                else ModelAsset.from_mapping(raw_model)
                if isinstance(raw_model, Mapping) and raw_model
                else None
            ),
            tasks=[
                task
                if isinstance(task, TaskAsset)
                else TaskAsset.from_mapping(task)
                for task in value.get("tasks") or []
            ],
        )


@dataclass
class AssetCatalog(_RecordMapping):
    """Prepared project assets shared by all assessment dimensions."""

    project_dir: Path | None = None
    tables: dict[str, TableAsset] = field(default_factory=dict)
    tasks: list[TaskAsset] = field(default_factory=list)

    _mapping_fields = ("project_dir", "tables", "tasks")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AssetCatalog":
        raw_project_dir = value.get("project_dir")
        return cls(
            project_dir=Path(raw_project_dir) if raw_project_dir else None,
            tables={
                str(name): table
                if isinstance(table, TableAsset)
                else TableAsset.from_mapping(table, default_name=str(name))
                for name, table in (value.get("tables") or {}).items()
            },
            tasks=[
                task
                if isinstance(task, TaskAsset)
                else TaskAsset.from_mapping(task)
                for task in value.get("tasks") or []
            ],
        )


def ensure_asset_catalog(
    value: AssetCatalog | Mapping[str, Any],
) -> AssetCatalog:
    """Normalize compatibility mappings at the assessment boundary."""
    if isinstance(value, AssetCatalog):
        return value
    if isinstance(value, Mapping):
        return AssetCatalog.from_mapping(value)
    raise TypeError(
        "asset catalog must be AssetCatalog or a mapping; "
        f"received {type(value).__name__}"
    )


def _short_table_name(table_name: str) -> str:
    name = str(table_name or "").strip().rstrip(";")
    if not name:
        return ""
    name = name.replace("`", "").replace('"', "")
    return name.split(".")[-1].strip()


def _relative_asset_path(project_dir: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(project_dir).as_posix()
    except ValueError:
        return file_path.as_posix()


def _display_file_path(project_dir: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(project_dir.parent).as_posix()
    except ValueError:
        return file_path.as_posix()


def _ddl_declared_table_name(ddl_path: Path) -> str:
    text = ddl_path.read_text(encoding=TEXT_ENCODING)
    try:
        table_def = parse_create_table(text)
        if table_def:
            return _short_table_name(table_def.short_name)
    except Exception:
        pass

    match = re.search(
        r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:`?\w+`?\.)?`?(\w+)`?",
        text,
        flags=re.IGNORECASE,
    )
    return _short_table_name(match.group(1)) if match else ""


def _ddl_table_for_naming(
    ddl_path: Path, model_metadata: dict | None
) -> dict | None:
    try:
        table_def = parse_create_table(
            ddl_path.read_text(encoding=TEXT_ENCODING)
        )
    except Exception:
        table_def = None
    if not table_def:
        return None

    name = _short_table_name(table_def.short_name)
    if not name:
        return None

    metadata = model_metadata.get(name, {}) if model_metadata else {}
    layer = str(metadata.get("layer") or "OTHER").upper()
    return dict(
        name=name,
        full_name=table_def.full_name,
        layer=layer,
        key_type=table_def.key_type,
        key_columns=list(table_def.key_columns or []),
        columns=[
            {"name": column.name, "type": column.data_type}
            for column in table_def.columns
        ],
    )


def _tables_for_naming(
    tables: list,
    project_dir: Path | None,
    model_metadata: dict | None,
) -> list:
    current_tables = []
    for table in tables:
        name = str(table.get("name") or "")
        metadata = (
            model_metadata.get(_short_table_name(name), {})
            if model_metadata
            else {}
        )
        current = dict(table)
        current["layer"] = (
            str(metadata["layer"]).upper()
            if metadata.get("layer")
            else "OTHER"
        )
        current_tables.append(current)

    if not project_dir:
        return current_tables

    ddl_dirs = _asset_dirs(Path(project_dir), "ddl")
    if not ddl_dirs:
        return []

    ddl_tables = {}

    for ddl_dir in ddl_dirs:
        for ddl_path in sorted(ddl_dir.glob("*.sql")):
            table = _ddl_table_for_naming(
                ddl_path,
                model_metadata,
            )
            if table:
                ddl_tables[table["name"]] = table

    return sorted(
        ddl_tables.values(),
        key=lambda item: str(item.get("name") or ""),
    )


def _extract_task_table_facts(
    task_path: Path,
    source_file: str,
    *,
    default_catalog: str = "internal",
    default_db: str = "",
) -> dict:
    text = task_path.read_text(encoding=TEXT_ENCODING)
    return extract_task_table_facts(
        text,
        source_file,
        default_catalog=default_catalog,
        default_db=default_db,
    )


def _expected_task_table(task_path: Path) -> str:
    stem = task_path.stem
    if task_path.parent.name == "full_refresh" and stem.endswith(
        "_full_refresh"
    ):
        return stem[: -len("_full_refresh")]
    return stem


def _model_asset_role(project_path: Path, model_path: Path) -> str:
    try:
        parts = model_path.relative_to(project_path).parts
    except ValueError:
        return ""
    if len(parts) >= 2 and parts[1] == "models":
        role = str(parts[0]).lower()
        if role in _MODEL_ROLE_EXPECTED_LAYERS:
            return role
    return ""


def _asset_dirs(project_path: Path, asset_kind: str) -> list[Path]:
    dirs = []
    ods_root = project_path / "ods" / asset_kind
    if ods_root.exists():
        dirs.extend(
            path for path in sorted(ods_root.glob("*/*")) if path.is_dir()
        )
    for role_dir in ("mid", "ads"):
        layer_dir = project_path / role_dir / asset_kind
        if layer_dir.exists():
            dirs.append(layer_dir)
    return dirs


def _source_file_keys(source_file: str) -> set[str]:
    source = str(source_file or "").replace("\\", "/").strip()
    if not source:
        return set()
    return {source}


def _edge_ref_type(ref) -> str:
    return str(ref.get("type") or "") if isinstance(ref, dict) else "column"


def _edge_ref_id(ref) -> str:
    if isinstance(ref, dict):
        return str(ref.get("id") or "")
    return str(ref or "")


def _edge_target_table(edge: dict) -> str:
    target = edge.get("target")
    target_id = _edge_ref_id(target)
    if not target_id:
        return ""
    if _edge_ref_type(target) == "table":
        return _short_table_name(target_id)
    return _short_table_name(_table_from_node(target_id))


def _transient_targets_from_lineage_tables(
    tables: list | None,
) -> dict[str, set[str]]:
    targets = defaultdict(set)
    for table in tables or []:
        if not table.get("is_transient"):
            continue
        name = _short_table_name(table.get("name", ""))
        if not name:
            continue
        for source_file in table.get("transient_sources") or []:
            for source_key in _source_file_keys(source_file):
                targets[source_key].add(name)
    return dict(targets)


def _lineage_targets_by_source_file(
    edges: list | None,
    indirect_edges: list | None,
    ignored_targets_by_source_file: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    targets = defaultdict(set)
    ignored_targets_by_source_file = ignored_targets_by_source_file or {}

    for edge in edges or []:
        target = _edge_target_table(edge)
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
            if target in ignored_targets_by_source_file.get(key, set()):
                continue
            targets[key].add(target)

    for edge in indirect_edges or []:
        target = _short_table_name(edge.get("target_table", ""))
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
            if target in ignored_targets_by_source_file.get(key, set()):
                continue
            targets[key].add(target)

    return dict(targets)


def build_asset_catalog(
    tables: list,
    model_metadata: dict | None,
    project_dir: Path | None,
    *,
    edges: list | None = None,
    indirect_edges: list | None = None,
    include_models: bool = True,
) -> AssetCatalog:
    """Collect project asset facts without assigning scores."""
    project_path = Path(project_dir) if project_dir else None
    assets: dict[str, TableAsset] = {}

    def ensure_asset(name: str) -> TableAsset:
        short_name = _short_table_name(name)
        if short_name not in assets:
            assets[short_name] = TableAsset(name=short_name)
        return assets[short_name]

    task_dirs = _asset_dirs(project_path, "tasks") if project_path else []
    task_table_facts_by_path = {}
    transient_targets_by_source_file = defaultdict(set)
    for source_file, names in _transient_targets_from_lineage_tables(
        tables,
    ).items():
        transient_targets_by_source_file[source_file].update(names)

    for task_dir in task_dirs:
        for task_path in sorted(task_dir.rglob("*.sql")):
            relative_source = task_path.relative_to(task_dir).as_posix()
            project_config = PROJECT_CONFIG.get(project_path.name) or {}
            task_facts = _extract_task_table_facts(
                task_path,
                relative_source,
                default_catalog=project_config.get("catalog", "internal"),
                default_db=project_config.get("db", project_path.name),
            )
            task_table_facts_by_path[task_path] = task_facts
            for table in task_facts["transient_tables"]:
                name = _short_table_name(table.get("name", ""))
                if name:
                    transient_targets_by_source_file[relative_source].add(name)
    transient_targets_by_source_file = dict(transient_targets_by_source_file)
    transient_task_tables = {
        name
        for names in transient_targets_by_source_file.values()
        for name in names
    }

    lineage_targets = _lineage_targets_by_source_file(
        edges,
        indirect_edges,
        transient_targets_by_source_file,
    )
    persistent_lineage_tables = {
        target for targets in lineage_targets.values() for target in targets
    }

    for table in tables or []:
        name = _short_table_name(table.get("name", ""))
        if not name:
            continue
        if (
            name in transient_task_tables or table.get("is_transient")
        ) and name not in persistent_lineage_tables:
            continue
        asset = ensure_asset(name)
        asset.lineage_table = dict(table)
        asset.columns = list(table.get("columns") or [])

    for name, metadata in (model_metadata or {}).items():
        if not isinstance(metadata, dict):
            continue
        declared_name = _short_table_name(metadata.get("name") or name)
        if not declared_name:
            continue
        asset = ensure_asset(declared_name)
        asset.model = ModelAsset(
            exists=True,
            path=None,
            file_stem=None,
            declared_name=declared_name,
            metadata=dict(metadata),
        )
        if metadata.get("layer"):
            asset.layer = str(metadata["layer"]).upper()

    if project_path:
        ddl_dirs = _asset_dirs(project_path, "ddl")
        if ddl_dirs:
            for ddl_dir in ddl_dirs:
                for ddl_path in sorted(ddl_dir.glob("*.sql")):
                    table = _ddl_table_for_naming(ddl_path, model_metadata)
                    declared_name = (
                        table["name"]
                        if table
                        else _ddl_declared_table_name(ddl_path)
                    )
                    if not declared_name:
                        continue
                    asset = ensure_asset(declared_name)
                    columns = list(table.get("columns") or []) if table else []
                    asset.ddl = DdlAsset(
                        exists=True,
                        path=ddl_path,
                        file_stem=ddl_path.stem,
                        declared_name=declared_name,
                        columns=columns,
                        key_type=(table or {}).get("key_type", ""),
                        key_columns=list(
                            (table or {}).get("key_columns") or []
                        ),
                        partition_column=extract_doris_partition_column(
                            ddl_path.read_text(encoding=TEXT_ENCODING)
                        ),
                    )
                    asset.columns = columns
                    ddl_layer = (table or {}).get("layer")
                    if ddl_layer and ddl_layer != "OTHER":
                        asset.layer = ddl_layer

        models_dirs = (
            _asset_dirs(project_path, "models") if include_models else []
        )
        if models_dirs:
            for models_dir in models_dirs:
                for model_path in sorted(models_dir.glob("*.yaml")):
                    try:
                        raw = (
                            yaml.safe_load(
                                model_path.read_text(encoding=TEXT_ENCODING)
                            )
                            or {}
                        )
                    except yaml.YAMLError:
                        raw = {}
                    if not isinstance(raw, dict):
                        raw = {}
                    declared_name = _short_table_name(
                        raw.get("name") or model_path.stem
                    )
                    asset = ensure_asset(declared_name)
                    metadata = (model_metadata or {}).get(declared_name) or raw
                    asset_role = _model_asset_role(project_path, model_path)
                    asset.model = ModelAsset(
                        exists=True,
                        path=model_path,
                        file_stem=model_path.stem,
                        declared_name=declared_name,
                        metadata=metadata,
                        asset_role=asset_role,
                        expected_layers=list(
                            _MODEL_ROLE_EXPECTED_LAYERS.get(asset_role, [])
                        ),
                    )
                    if metadata.get("layer"):
                        asset.layer = str(metadata["layer"]).upper()

        task_facts = []
        if task_dirs:
            for task_dir in task_dirs:
                for task_path in sorted(task_dir.rglob("*.sql")):
                    expected = _expected_task_table(task_path)
                    outputs = {
                        _short_table_name(table_name)
                        for table_name in task_table_facts_by_path[task_path][
                            "output_tables"
                        ]
                        if _short_table_name(table_name)
                    }
                    relative_source = task_path.relative_to(
                        task_dir
                    ).as_posix()
                    fact = TaskAsset(
                        path=task_path,
                        file=_relative_asset_path(project_path, task_path),
                        expected_table=expected,
                        output_tables=outputs,
                        transient_tables=task_table_facts_by_path[task_path][
                            "transient_tables"
                        ],
                        lineage_targets=lineage_targets.get(
                            relative_source,
                            set(),
                        ),
                        is_full_refresh=(
                            task_path.parent.name == "full_refresh"
                        ),
                    )
                    task_facts.append(fact)
                    linked_names = set(outputs)
                    if (
                        not linked_names
                        and not (
                            task_table_facts_by_path[task_path][
                                "transient_tables"
                            ]
                        )
                    ):
                        linked_names.add(expected)
                    for table_name in linked_names:
                        ensure_asset(table_name).tasks.append(fact)
        else:
            task_facts = []
    else:
        task_facts = []

    return AssetCatalog(
        project_dir=project_path,
        tables=assets,
        tasks=task_facts,
    )


def _related_files_for_table(
    asset_catalog: AssetCatalog | Mapping[str, Any], table_name: str
) -> list[str]:
    asset_catalog = ensure_asset_catalog(asset_catalog)
    project_dir = asset_catalog.project_dir
    if not project_dir:
        return []
    asset = asset_catalog.tables.get(table_name)
    if asset is None:
        return []
    files = []
    if asset.ddl and asset.ddl.path:
        files.append(_display_file_path(project_dir, asset.ddl.path))
    for task in sorted(asset.tasks, key=lambda item: item.file):
        if task.path:
            files.append(_display_file_path(project_dir, task.path))
    if asset.model and asset.model.path:
        files.append(_display_file_path(project_dir, asset.model.path))
    return files
