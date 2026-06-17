"""Project asset catalog collection for assess scoring."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml

from ddl_deriver.ddl_deriver import parse_create_table
from lineage.sql_task_facts import extract_task_table_facts
from lineage.table_graph import _table_from_node


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
    text = ddl_path.read_text(encoding="utf-8")
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
        table_def = parse_create_table(ddl_path.read_text(encoding="utf-8"))
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
        metadata = model_metadata.get(name, {}) if model_metadata else {}
        current = dict(table)
        if metadata.get("layer"):
            current["layer"] = str(metadata["layer"]).upper()
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


def _extract_task_table_facts(task_path: Path, source_file: str) -> dict:
    text = task_path.read_text(encoding="utf-8")
    return extract_task_table_facts(text, source_file)


def _expected_task_table(task_path: Path) -> str:
    stem = task_path.stem
    if task_path.parent.name == "full_refresh" and stem.endswith(
        "_full_refresh"
    ):
        return stem[: -len("_full_refresh")]
    return stem


def _asset_dirs(project_path: Path, asset_kind: str) -> list[Path]:
    dirs = []
    root_dir = project_path / asset_kind
    if root_dir.exists():
        dirs.append(root_dir)

    ods_root = project_path / "ods" / asset_kind
    if ods_root.exists():
        dirs.extend(
            path for path in sorted(ods_root.glob("*/*")) if path.is_dir()
        )
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
) -> dict:
    """Collect project asset facts without assigning scores."""
    project_path = Path(project_dir) if project_dir else None
    assets = {}

    def ensure_asset(name: str) -> dict:
        short_name = _short_table_name(name)
        if short_name not in assets:
            assets[short_name] = dict(
                name=short_name,
                layer="OTHER",
                columns=[],
                lineage_table=None,
                ddl=None,
                model=None,
                tasks=[],
            )
        return assets[short_name]

    tasks_dir = project_path / "tasks" if project_path else None
    task_table_facts_by_path = {}
    transient_targets_by_source_file = defaultdict(set)
    for source_file, names in _transient_targets_from_lineage_tables(
        tables,
    ).items():
        transient_targets_by_source_file[source_file].update(names)

    if tasks_dir and tasks_dir.exists():
        for task_path in sorted(tasks_dir.rglob("*.sql")):
            relative_source = task_path.relative_to(tasks_dir).as_posix()
            task_facts = _extract_task_table_facts(
                task_path,
                relative_source,
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
        asset["lineage_table"] = dict(table)
        asset["layer"] = str(table.get("layer") or "OTHER").upper()
        asset["columns"] = list(table.get("columns") or [])

    for name, metadata in (model_metadata or {}).items():
        if not isinstance(metadata, dict):
            continue
        declared_name = _short_table_name(metadata.get("name") or name)
        if not declared_name:
            continue
        asset = ensure_asset(declared_name)
        asset["model"] = dict(
            exists=True,
            path=None,
            file_stem=None,
            declared_name=declared_name,
            metadata=metadata,
        )
        if metadata.get("layer"):
            asset["layer"] = str(metadata["layer"]).upper()

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
                    asset["ddl"] = dict(
                        exists=True,
                        path=ddl_path,
                        file_stem=ddl_path.stem,
                        declared_name=declared_name,
                        columns=columns,
                        key_type=(table or {}).get("key_type", ""),
                        key_columns=list(
                            (table or {}).get("key_columns") or []
                        ),
                    )
                    asset["columns"] = columns
                    if table and table.get("layer") != "OTHER":
                        asset["layer"] = table["layer"]

        models_dirs = _asset_dirs(project_path, "models")
        if models_dirs:
            for models_dir in models_dirs:
                for model_path in sorted(models_dir.glob("*.yaml")):
                    try:
                        raw = (
                            yaml.safe_load(
                                model_path.read_text(encoding="utf-8")
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
                    asset["model"] = dict(
                        exists=True,
                        path=model_path,
                        file_stem=model_path.stem,
                        declared_name=declared_name,
                        metadata=metadata,
                    )
                    if metadata.get("layer"):
                        asset["layer"] = str(metadata["layer"]).upper()

        task_facts = []
        if tasks_dir.exists():
            for task_path in sorted(tasks_dir.rglob("*.sql")):
                expected = _expected_task_table(task_path)
                outputs = task_table_facts_by_path[task_path]["output_tables"]
                relative_source = task_path.relative_to(tasks_dir).as_posix()
                fact = dict(
                    path=task_path,
                    file=_relative_asset_path(project_path, task_path),
                    expected_table=expected,
                    output_tables=outputs,
                    lineage_targets=lineage_targets.get(
                        relative_source,
                        set(),
                    ),
                    is_full_refresh=(task_path.parent.name == "full_refresh"),
                )
                task_facts.append(fact)
                linked_names = set(outputs)
                if (
                    not linked_names
                    and not (
                        task_table_facts_by_path[task_path]["transient_tables"]
                    )
                ):
                    linked_names.add(expected)
                for table_name in linked_names:
                    ensure_asset(table_name)["tasks"].append(fact)
        else:
            task_facts = []
    else:
        task_facts = []

    return dict(
        project_dir=project_path,
        tables=assets,
        tasks=task_facts,
    )


def _related_files_for_table(
    asset_catalog: dict, table_name: str
) -> list[str]:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return []
    asset = (asset_catalog.get("tables") or {}).get(table_name) or {}
    files = []
    ddl = asset.get("ddl") or {}
    if ddl.get("path"):
        files.append(_display_file_path(project_dir, ddl["path"]))
    for task in sorted(
        asset.get("tasks") or [], key=lambda item: item["file"]
    ):
        files.append(_display_file_path(project_dir, task["path"]))
    model = asset.get("model") or {}
    if model.get("path"):
        files.append(_display_file_path(project_dir, model["path"]))
    return files
