"""Project asset catalog collection for assess scoring."""

import re
from collections import defaultdict
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from ddl_deriver.ddl_deriver import parse_create_table
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


def _ddl_table_for_naming(ddl_path: Path,
                          model_metadata: dict | None) -> dict | None:
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

    ddl_dir = Path(project_dir) / "ddl"
    if not ddl_dir.exists():
        return []

    ddl_tables = {}

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


def _target_table_sql(target_expr) -> str:
    if isinstance(target_expr, exp.Schema):
        target_expr = target_expr.this
    return target_expr.sql(dialect="doris")


def _extract_task_output_tables(task_path: Path) -> set[str]:
    text = task_path.read_text(encoding="utf-8")
    targets = set()
    try:
        statements = sqlglot.parse(text, dialect="doris")
    except Exception:
        statements = []

    for stmt in statements:
        if isinstance(stmt, exp.Insert):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Update):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Delete):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif (
            isinstance(stmt, exp.Create)
            and stmt.args.get("expression") is not None
        ):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.Merge):
            targets.add(_short_table_name(_target_table_sql(stmt.this)))
        elif isinstance(stmt, exp.TruncateTable):
            for table in stmt.expressions:
                targets.add(_short_table_name(_target_table_sql(table)))

    if targets:
        return {target for target in targets if target}

    write_patterns = [
        r"\bINSERT\s+(?:OVERWRITE\s+TABLE|INTO)\s+"
        r"(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bUPDATE\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bDELETE\s+FROM\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bTRUNCATE\s+(?:TABLE\s+)?(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bMERGE\s+INTO\s+(?:`?\w+`?\.)?`?(\w+)`?",
        r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:`?\w+`?\.)?`?(\w+)`?\s+AS\b",
    ]
    for pattern in write_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            target = _short_table_name(match.group(1))
            if target:
                targets.add(target)
    return targets


def _expected_task_table(task_path: Path) -> str:
    stem = task_path.stem
    if task_path.parent.name == "full_refresh" and stem.endswith("_full_refresh"):
        return stem[: -len("_full_refresh")]
    return stem


def _source_file_keys(source_file: str) -> set[str]:
    source = str(source_file or "").replace("\\", "/").strip()
    if not source:
        return set()
    return {source}


def _lineage_targets_by_source_file(
    edges: list | None,
    indirect_edges: list | None,
) -> dict[str, set[str]]:
    targets = defaultdict(set)

    for edge in edges or []:
        target = _short_table_name(_table_from_node(str(edge.get("target") or "")))
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
            targets[key].add(target)

    for edge in indirect_edges or []:
        target = _short_table_name(edge.get("target_table", ""))
        if not target:
            continue
        for key in _source_file_keys(edge.get("source_file", "")):
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

    for table in tables or []:
        name = _short_table_name(table.get("name", ""))
        if not name:
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
        ddl_dir = project_path / "ddl"
        if ddl_dir.exists():
            for ddl_path in sorted(ddl_dir.glob("*.sql")):
                table = _ddl_table_for_naming(ddl_path, model_metadata)
                declared_name = (
                    table["name"] if table
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
                )
                asset["columns"] = columns
                if table and table.get("layer") != "OTHER":
                    asset["layer"] = table["layer"]

        models_dir = project_path / "models"
        if models_dir.exists():
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
                metadata = (
                    (model_metadata or {}).get(declared_name)
                    or raw
                )
                asset["model"] = dict(
                    exists=True,
                    path=model_path,
                    file_stem=model_path.stem,
                    declared_name=declared_name,
                    metadata=metadata,
                )
                if metadata.get("layer"):
                    asset["layer"] = str(metadata["layer"]).upper()

        tasks_dir = project_path / "tasks"
        lineage_targets = _lineage_targets_by_source_file(
            edges,
            indirect_edges,
        )
        task_facts = []
        if tasks_dir.exists():
            for task_path in sorted(tasks_dir.rglob("*.sql")):
                expected = _expected_task_table(task_path)
                outputs = _extract_task_output_tables(task_path)
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
                    is_full_refresh=(
                        task_path.parent.name == "full_refresh"
                    ),
                )
                task_facts.append(fact)
                linked_names = set(outputs)
                if not linked_names:
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

def _related_files_for_table(asset_catalog: dict, table_name: str) -> list[str]:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return []
    asset = (asset_catalog.get("tables") or {}).get(table_name) or {}
    files = []
    ddl = asset.get("ddl") or {}
    if ddl.get("path"):
        files.append(_display_file_path(project_dir, ddl["path"]))
    for task in sorted(asset.get("tasks") or [], key=lambda item: item["file"]):
        files.append(_display_file_path(project_dir, task["path"]))
    model = asset.get("model") or {}
    if model.get("path"):
        files.append(_display_file_path(project_dir, model["path"]))
    return files
