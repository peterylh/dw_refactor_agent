#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dw_refactor_agent.assessment.llm.table_inspector import (  # noqa: E402
    normalize_chat_completions_url,
)

DEFAULT_PROJECTS = ("shop", "finance_analytics")
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_PARALLELISM = 4
DEFAULT_MAX_RETRIES = 1
DEFAULT_REQUEST_TIMEOUT = 240
CATALOG = "internal"
LAYER_PREFIXES = ("ods_", "dwd_", "dws_", "ads_", "dim_")
FIXED_LAYERS = {"ODS", "ADS"}
MIDDLE_LAYERS = {"DWD", "DWS", "DIM"}

LAYER_WORD_PATTERN = re.compile(
    r"(?i)\b(?:ODS|DWD|DWS|ADS|DIM)\b|"
    r"(?:贴源层|原始层|明细层|汇总层|应用层|维度层|维表|维度表|"
    r"明细事实表|汇总事实表|应用表|看板表|驾驶舱|"
    r"明细粒度|汇总指标|分层|数据分层|层级)"
)
SQL_LINE_COMMENT_PATTERN = re.compile(r"(?m)^\s*--[^\n]*(?:\n|$)")
SQL_BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
SQL_COMMENT_CLAUSE_PATTERN = re.compile(
    r"\s+COMMENT\s+(?:'[^']*'|\"[^\"]*\")",
    re.IGNORECASE,
)

MetadataRunner = Callable[..., Dict[str, Any]]
_RUNTIME_CONFIG = None
_RUNTIME_WRITER = None


def _runtime_modules():
    global _RUNTIME_CONFIG, _RUNTIME_WRITER
    if _RUNTIME_CONFIG is None or _RUNTIME_WRITER is None:
        import dw_refactor_agent.assessment.llm.model_metadata_writer as metadata_writer
        import dw_refactor_agent.config as runtime_config

        _RUNTIME_CONFIG = runtime_config
        _RUNTIME_WRITER = metadata_writer
    return _RUNTIME_CONFIG, _RUNTIME_WRITER


@dataclass(frozen=True)
class TempProject:
    source_project: str
    target_project: str
    source_dir: Path
    target_dir: Path
    database: str
    table_mapping: Dict[str, str]
    expected_by_source: Dict[str, Dict[str, Any]]
    expected_catalog: Dict[str, List[str]]

    @property
    def expected_by_target(self) -> Dict[str, Dict[str, Any]]:
        return {
            new: self.expected_by_source[old]
            for old, new in self.table_mapping.items()
            if old in self.expected_by_source
        }


@dataclass(frozen=True)
class ConfigSnapshot:
    project_root: Path
    warehouses_root: Path
    project_config: Dict[str, Dict[str, Any]]
    writer_project_root: Path


def _load_yaml_mapping(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _short_table_name(value: Any) -> str:
    text = str(value or "").strip().rstrip(";")
    if not text:
        return ""
    text = text.replace("`", "").replace('"', "")
    return text.split(".")[-1].strip()


def _source_project_dir(source_root: Path, source_project: str) -> Path:
    return Path(source_root) / "warehouses" / source_project


def _source_database(source_dir: Path, source_project: str) -> str:
    warehouse = _load_yaml_mapping(source_dir / "warehouse.yaml")
    return str(
        warehouse.get("db")
        or warehouse.get("database")
        or f"{source_project}_dm"
    )


def _target_database(source_project: str) -> str:
    return f"{source_project}_benchmark_dm"


def _iter_ddl_paths(source_dir: Path) -> List[Path]:
    roots = [
        source_dir / "ods" / "ddl",
        source_dir / "mid" / "ddl",
        source_dir / "ads" / "ddl",
    ]
    paths: List[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(sorted(root.rglob("*.sql")))
    return paths


def _iter_task_paths(source_dir: Path) -> List[Path]:
    paths: List[Path] = []
    for root in (source_dir / "mid" / "tasks", source_dir / "ads" / "tasks"):
        if root.exists():
            paths.extend(sorted(root.rglob("*.sql")))
    return paths


def _iter_model_paths(source_dir: Path) -> List[Path]:
    paths: List[Path] = []
    for root in (
        source_dir / "ods" / "models",
        source_dir / "mid" / "models",
        source_dir / "ads" / "models",
    ):
        if root.exists():
            paths.extend(sorted(root.rglob("*.yaml")))
    return paths


def _load_expected_models(source_dir: Path) -> Dict[str, Dict[str, Any]]:
    expected: Dict[str, Dict[str, Any]] = {}
    for path in _iter_model_paths(source_dir):
        data = _load_yaml_mapping(path)
        table = _short_table_name(data.get("name") or path.stem)
        if not table:
            continue
        expected[table] = {
            "layer": str(data.get("layer") or "OTHER").upper(),
            "table_type": str(data.get("table_type") or "other").lower(),
            "path": str(path),
        }
    return expected


def _load_expected_catalog(source_dir: Path) -> Dict[str, List[str]]:
    processes = _load_yaml_mapping(source_dir / "business_processes.yaml")
    subjects = _load_yaml_mapping(source_dir / "semantic_subjects.yaml")
    return {
        "business_processes": _catalog_codes(
            processes.get("business_processes") or []
        ),
        "semantic_subjects": _catalog_codes(
            subjects.get("semantic_subjects") or []
        ),
    }


def _catalog_codes(entries: Any) -> List[str]:
    codes = []
    if isinstance(entries, dict):
        iterable = entries.get("values") or entries.values()
    elif isinstance(entries, list):
        iterable = entries
    else:
        iterable = []
    for entry in iterable:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or entry.get("id") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return sorted(codes)


def strip_layer_prefix(name: str) -> str:
    for prefix in LAYER_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def functional_table_name(table_name: str, used: set) -> str:
    base = strip_layer_prefix(table_name)
    base = re.sub(r"__+", "_", base).strip("_") or table_name
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _table_mapping(ddl_paths: Iterable[Path]) -> Dict[str, str]:
    used = set()
    mapping: Dict[str, str] = {}
    for path in ddl_paths:
        mapping[path.stem] = functional_table_name(path.stem, used)
    return mapping


def _replace_identifier(text: str, old: str, new: str) -> str:
    return re.sub(
        r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])".format(re.escape(old)),
        new,
        text,
    )


def replace_table_refs(
    text: str,
    table_mapping: Dict[str, str],
    *,
    database_mapping: Optional[Dict[str, str]] = None,
) -> str:
    for old, new in sorted(
        table_mapping.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = _replace_identifier(text, old, new)
    for old, new in sorted(
        (database_mapping or {}).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = _replace_identifier(text, old, new)
    return text


def sanitize_text(text: str) -> str:
    return LAYER_WORD_PATTERN.sub("", text)


def sanitize_sql(
    text: str,
    table_mapping: Dict[str, str],
    *,
    database_mapping: Optional[Dict[str, str]] = None,
) -> str:
    text = replace_table_refs(
        text,
        table_mapping,
        database_mapping=database_mapping,
    )
    text = SQL_LINE_COMMENT_PATTERN.sub("", text)
    text = SQL_BLOCK_COMMENT_PATTERN.sub("", text)
    text = SQL_COMMENT_CLAUSE_PATTERN.sub("", text)
    text = sanitize_text(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _expected_layer(expected: Dict[str, Dict[str, Any]], table: str) -> str:
    return str((expected.get(table) or {}).get("layer") or "OTHER").upper()


def _asset_role_for_expected_layer(layer: str) -> str:
    if layer == "ODS":
        return "ods"
    if layer == "ADS":
        return "ads"
    return "mid"


def _ddl_output_dir(
    target_dir: Path,
    database: str,
    expected: Dict[str, Dict[str, Any]],
    source_table: str,
) -> Path:
    role = _asset_role_for_expected_layer(
        _expected_layer(expected, source_table)
    )
    if role == "ods":
        return target_dir / "ods" / "ddl" / CATALOG / database
    return target_dir / role / "ddl"


def _task_output_dir(
    target_dir: Path,
    expected: Dict[str, Dict[str, Any]],
    source_table: str,
    source_task_root: Path,
    task_path: Path,
) -> Path:
    role = _asset_role_for_expected_layer(
        _expected_layer(expected, source_table)
    )
    rel_parent = task_path.parent.relative_to(source_task_root)
    return target_dir / role / "tasks" / rel_parent


def _write_target_warehouse_yaml(
    source_dir: Path,
    target_dir: Path,
    target_project: str,
    database: str,
) -> None:
    source = _load_yaml_mapping(source_dir / "warehouse.yaml")
    catalog = str(source.get("catalog") or CATALOG)
    dialects = source.get("ods_source_catalog_dialects") or {catalog: "doris"}
    payload = {
        "name": target_project,
        "catalog": catalog,
        "database": database,
        "qa_database": f"{database}_qa",
        "lineage_database": f"{target_project}_lineage",
        "naming_config": "naming_config.yaml",
        "default_dialect": str(source.get("default_dialect") or "doris"),
        "ods_source_catalog_dialects": {
            catalog: str(dialects.get(catalog, "doris"))
        },
    }
    if isinstance(source.get("verification"), dict):
        payload["verification"] = source["verification"]
    _write_yaml(target_dir / "warehouse.yaml", payload)


def _write_target_taxonomy(
    source_dir: Path,
    target_dir: Path,
    target_project: str,
) -> None:
    taxonomy = _load_yaml_mapping(source_dir / "business_taxonomy.yaml")
    payload: Dict[str, Any] = {
        "version": taxonomy.get("version") or 1,
        "project": target_project,
    }
    for key in ("source", "project_context", "data_domains", "business_areas"):
        if key in taxonomy:
            payload[key] = taxonomy[key]
    _write_yaml(target_dir / "business_taxonomy.yaml", payload)
    _write_yaml(
        target_dir / "business_processes.yaml",
        {
            "version": payload["version"],
            "project": target_project,
            "business_processes": [],
        },
    )
    _write_yaml(
        target_dir / "semantic_subjects.yaml",
        {
            "version": payload["version"],
            "project": target_project,
            "semantic_subjects": [],
        },
    )


def _copy_required_project_files(
    source_dir: Path,
    target_dir: Path,
    target_project: str,
    database: str,
) -> None:
    _write_target_warehouse_yaml(
        source_dir, target_dir, target_project, database
    )
    _write_target_taxonomy(source_dir, target_dir, target_project)
    naming_config = source_dir / "naming_config.yaml"
    if naming_config.exists():
        shutil.copy2(
            str(naming_config), str(target_dir / "naming_config.yaml")
        )
    else:
        repo_naming = REPO_ROOT / "naming_config.yaml"
        shutil.copy2(str(repo_naming), str(target_dir / "naming_config.yaml"))


def _task_base_table(
    stem: str, table_mapping: Dict[str, str]
) -> Tuple[str, str]:
    suffix = "_full_refresh"
    if stem.endswith(suffix) and stem[: -len(suffix)] in table_mapping:
        source_table = stem[: -len(suffix)]
        return source_table, f"{table_mapping[source_table]}{suffix}"
    if stem in table_mapping:
        return stem, table_mapping[stem]
    return "", ""


def _copy_rewritten_ddl(
    source_dir: Path,
    target_dir: Path,
    database: str,
    table_mapping: Dict[str, str],
    expected: Dict[str, Dict[str, Any]],
    database_mapping: Dict[str, str],
) -> None:
    for ddl_path in _iter_ddl_paths(source_dir):
        source_table = ddl_path.stem
        new_table = table_mapping[source_table]
        output_dir = _ddl_output_dir(
            target_dir, database, expected, source_table
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{new_table}.sql").write_text(
            sanitize_sql(
                ddl_path.read_text(encoding="utf-8"),
                table_mapping,
                database_mapping=database_mapping,
            ),
            encoding="utf-8",
        )


def _copy_rewritten_tasks(
    source_dir: Path,
    target_dir: Path,
    table_mapping: Dict[str, str],
    expected: Dict[str, Dict[str, Any]],
    database_mapping: Dict[str, str],
) -> None:
    task_roots = [source_dir / "mid" / "tasks", source_dir / "ads" / "tasks"]
    for task_path in _iter_task_paths(source_dir):
        source_root = next(
            root
            for root in task_roots
            if root.exists() and root in task_path.parents
        )
        source_table, new_stem = _task_base_table(
            task_path.stem, table_mapping
        )
        if not source_table:
            continue
        output_dir = _task_output_dir(
            target_dir,
            expected,
            source_table,
            source_root,
            task_path,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{new_stem}.sql").write_text(
            sanitize_sql(
                task_path.read_text(encoding="utf-8"),
                table_mapping,
                database_mapping=database_mapping,
            ),
            encoding="utf-8",
        )


def build_temp_project(
    source_project: str,
    target_project: str,
    tmp_root: Path,
    *,
    source_root: Path = REPO_ROOT,
) -> TempProject:
    """Build a cold-start benchmark project under tmp_root/warehouses."""
    source_dir = _source_project_dir(Path(source_root), source_project)
    if not source_dir.exists():
        raise FileNotFoundError(f"source project not found: {source_dir}")

    target_dir = Path(tmp_root) / "warehouses" / target_project
    if target_dir.exists():
        raise FileExistsError(
            f"target benchmark project already exists: {target_dir}"
        )

    database = _target_database(source_project)
    expected = _load_expected_models(source_dir)
    mapping = _table_mapping(_iter_ddl_paths(source_dir))
    database_mapping = {_source_database(source_dir, source_project): database}

    _copy_required_project_files(
        source_dir, target_dir, target_project, database
    )
    _copy_rewritten_ddl(
        source_dir,
        target_dir,
        database,
        mapping,
        expected,
        database_mapping,
    )
    _copy_rewritten_tasks(
        source_dir,
        target_dir,
        mapping,
        expected,
        database_mapping,
    )
    return TempProject(
        source_project=source_project,
        target_project=target_project,
        source_dir=source_dir,
        target_dir=target_dir,
        database=database,
        table_mapping=mapping,
        expected_by_source=expected,
        expected_catalog=_load_expected_catalog(source_dir),
    )


def _snapshot_config() -> ConfigSnapshot:
    runtime_config, runtime_writer = _runtime_modules()
    return ConfigSnapshot(
        project_root=runtime_config.core.PROJECT_ROOT,
        warehouses_root=runtime_config.core.WAREHOUSES_ROOT,
        project_config={
            key: dict(value)
            for key, value in runtime_config.PROJECT_CONFIG.items()
        },
        writer_project_root=runtime_writer.PROJECT_ROOT,
    )


def _clear_config_caches() -> None:
    runtime_config, _ = _runtime_modules()
    runtime_config.clear_naming_config_cache()
    runtime_config.clear_model_metadata_cache()
    runtime_config.clear_business_semantics_cache()


def _activate_project_root(project_root: Path) -> None:
    runtime_config, runtime_writer = _runtime_modules()
    project_root = Path(project_root)
    runtime_config.core.PROJECT_ROOT = project_root
    runtime_config.core.WAREHOUSES_ROOT = project_root / "warehouses"
    runtime_writer.PROJECT_ROOT = project_root
    _clear_config_caches()


def _restore_config(snapshot: ConfigSnapshot) -> None:
    runtime_config, runtime_writer = _runtime_modules()
    runtime_config.core.PROJECT_ROOT = snapshot.project_root
    runtime_config.core.WAREHOUSES_ROOT = snapshot.warehouses_root
    runtime_writer.PROJECT_ROOT = snapshot.writer_project_root
    runtime_config.PROJECT_CONFIG.clear()
    runtime_config.PROJECT_CONFIG.update(snapshot.project_config)
    _clear_config_caches()


def _register_target_project(
    temp_project: TempProject, tmp_root: Path
) -> None:
    runtime_config, _ = _runtime_modules()
    runtime_config.PROJECT_CONFIG[temp_project.target_project] = (
        runtime_config.core.load_warehouse_config(
            temp_project.target_dir / "warehouse.yaml",
            project_root=tmp_root,
        )
    )
    _clear_config_caches()


def _write_extracted_lineage(
    temp_project: TempProject,
    *,
    parallelism: int,
) -> None:
    from dw_refactor_agent.lineage import lineage_extractor

    runtime_config, _ = _runtime_modules()
    project = temp_project.target_project
    previous_project = lineage_extractor.CURRENT_PROJECT
    try:
        lineage_extractor.configure_project(project)
        schema = lineage_extractor.build_schema_from_project_ddl(project)
        task_files = lineage_extractor.iter_project_task_files(project)
        extraction = lineage_extractor.extract_lineage_from_task_files(
            task_files,
            temp_project.target_dir,
            schema,
            parallel=max(1, int(parallelism or 1)),
            source_file_for_path=lambda path: (
                lineage_extractor.task_source_file(project, path)
            ),
        )
        fatal_diagnostics = lineage_extractor._fatal_diagnostics(
            extraction["errors"]
        )
        if fatal_diagnostics:
            raise RuntimeError(
                f"benchmark lineage extraction failed for {project}: "
                f"{len(fatal_diagnostics)} fatal diagnostics"
            )

        output = lineage_extractor.build_lineage_output(
            extraction["lineage"],
            schema,
            transient_tables=extraction["transient_tables"],
        )
        output_path = runtime_config.lineage_data_path(project)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        lineage_extractor.configure_project(previous_project)


def _read_generated_models(target_project: str) -> Dict[str, Dict[str, Any]]:
    runtime_config, _ = _runtime_modules()
    runtime_config.clear_model_metadata_cache()
    raw = runtime_config.load_model_metadata(target_project)
    return {str(name): dict(data) for name, data in raw.items()}


def _models_from_updates(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for update in result.get("model_updates") or []:
        if not isinstance(update, dict):
            continue
        table = str(update.get("table") or "").strip()
        if not table:
            continue
        models[table] = {
            "name": table,
            "layer": update.get("layer"),
            "table_type": update.get("table_type"),
        }
        for key in (
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
            "entities",
            "entity",
            "related_entities",
            "grain",
        ):
            if key in update:
                models[table][key] = update[key]
    return models


def _metric_count(model: Dict[str, Any]) -> int:
    total = 0
    for key in ("atomic_metrics", "derived_metrics", "calculated_metrics"):
        value = model.get(key)
        if isinstance(value, dict):
            total += sum(
                len(items) if isinstance(items, list) else 1
                for items in value.values()
            )
        elif isinstance(value, list):
            total += len(value)
    return total


def _has_entities(model: Dict[str, Any]) -> bool:
    return bool(
        model.get("entities")
        or model.get("entity")
        or model.get("related_entities")
    )


def _has_grain(model: Dict[str, Any]) -> bool:
    return bool(model.get("grain"))


def _llm_layers(result: Dict[str, Any]) -> Dict[str, str]:
    llm_result = result.get("llm_result") or {}
    layers: Dict[str, str] = {}
    for table_result in llm_result.get("tables") or []:
        if not isinstance(table_result, dict):
            continue
        table = str(
            table_result.get("table") or table_result.get("table_name") or ""
        ).strip()
        if table:
            layers[table] = str(
                table_result.get("inferred_layer") or "MISSING"
            ).upper()
    return layers


def _table_status_counts(result: Dict[str, Any]) -> Dict[str, int]:
    llm_result = result.get("llm_result") or {}
    tables = [
        item
        for item in llm_result.get("tables") or []
        if isinstance(item, dict)
    ]
    return {
        "blocked": int(
            llm_result.get("blocked_table_count")
            if llm_result.get("blocked_table_count") is not None
            else sum(1 for item in tables if item.get("status") == "blocked")
        ),
        "warning": int(
            llm_result.get("warning_table_count")
            if llm_result.get("warning_table_count") is not None
            else sum(1 for item in tables if item.get("status") == "warning")
        ),
        "metadata_warning": int(
            llm_result.get("metadata_warning_count")
            if llm_result.get("metadata_warning_count") is not None
            else sum(
                len(item.get("metadata_warnings") or []) for item in tables
            )
        ),
    }


def _catalog_codes_from_file(path: Path, key: str) -> List[str]:
    return _catalog_codes(_load_yaml_mapping(path).get(key) or [])


def _catalog_codes_from_changes(
    changes: List[Dict[str, Any]],
    section: str,
) -> List[str]:
    codes = []
    for change in changes:
        if change.get("section") != section:
            continue
        entry = (
            change.get("entry")
            if isinstance(change.get("entry"), dict)
            else {}
        )
        code = str(entry.get("code") or change.get("code") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return sorted(codes)


def _catalog_summary(
    temp_project: TempProject,
    result: Dict[str, Any],
    *,
    dry_run: bool,
) -> Dict[str, Any]:
    changes = list(
        result.get("planned_catalog_updates")
        or result.get("catalog_updates")
        or []
    )
    if dry_run:
        business_process_codes = _catalog_codes_from_changes(
            changes,
            "business_processes",
        )
        semantic_subject_codes = _catalog_codes_from_changes(
            changes,
            "semantic_subjects",
        )
    else:
        business_process_codes = _catalog_codes_from_file(
            temp_project.target_dir / "business_processes.yaml",
            "business_processes",
        )
        semantic_subject_codes = _catalog_codes_from_file(
            temp_project.target_dir / "semantic_subjects.yaml",
            "semantic_subjects",
        )

    expected_process = temp_project.expected_catalog["business_processes"]
    expected_subject = temp_project.expected_catalog["semantic_subjects"]
    process_overlap = sorted(
        set(business_process_codes) & set(expected_process)
    )
    subject_overlap = sorted(
        set(semantic_subject_codes) & set(expected_subject)
    )
    return {
        "business_process_count": len(business_process_codes),
        "semantic_subject_count": len(semantic_subject_codes),
        "expected_business_process_codes": expected_process,
        "generated_business_process_codes": business_process_codes,
        "business_process_overlap_codes": process_overlap,
        "business_process_overlap_count": len(process_overlap),
        "expected_semantic_subject_codes": expected_subject,
        "generated_semantic_subject_codes": semantic_subject_codes,
        "semantic_subject_overlap_codes": subject_overlap,
        "semantic_subject_overlap_count": len(subject_overlap),
    }


def _confusion_key(expected_layer: str, actual_layer: str) -> str:
    return f"{expected_layer}->{actual_layer}"


def _summarize_project(
    temp_project: TempProject,
    *,
    result: Dict[str, Any],
    dry_run: bool,
) -> Dict[str, Any]:
    generated_models = (
        _models_from_updates(result)
        if dry_run
        else _read_generated_models(temp_project.target_project)
    )
    if not generated_models:
        generated_models = _models_from_updates(result)

    llm_layers = _llm_layers(result)
    by_expected: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "llm_middle_total": 0,
            "llm_middle_correct": 0,
        }
    )
    confusion: Counter = Counter()
    final_layer_counts: Counter = Counter()
    mismatches = []
    llm_middle_correct = 0
    middle_count = 0

    for source_table, target_table in sorted(
        temp_project.table_mapping.items()
    ):
        expected = temp_project.expected_by_source.get(source_table)
        if not expected:
            continue
        expected_layer = str(expected.get("layer") or "OTHER").upper()
        final_model = generated_models.get(target_table, {})
        final_layer = str(final_model.get("layer") or "MISSING").upper()
        llm_layer = llm_layers.get(target_table, "NOT_RUN")

        by_expected[expected_layer]["total"] += 1
        final_layer_counts[final_layer] += 1

        if expected_layer in MIDDLE_LAYERS:
            middle_count += 1
            by_expected[expected_layer]["llm_middle_total"] += 1
            confusion[_confusion_key(expected_layer, llm_layer)] += 1
            if llm_layer == expected_layer:
                llm_middle_correct += 1
                by_expected[expected_layer]["llm_middle_correct"] += 1
            elif llm_layer != expected_layer:
                mismatches.append(
                    {
                        "source_table": source_table,
                        "target_table": target_table,
                        "expected_layer": expected_layer,
                        "expected_table_type": expected.get("table_type"),
                        "final_layer": final_layer,
                        "final_table_type": final_model.get("table_type"),
                        "llm_middle_layer": llm_layer,
                    }
                )

    table_count = sum(item["total"] for item in by_expected.values())
    metric_count = sum(
        _metric_count(model) for model in generated_models.values()
    )
    catalog_summary = _catalog_summary(temp_project, result, dry_run=dry_run)
    status_counts = _table_status_counts(result)
    return {
        "source_project": temp_project.source_project,
        "target_project": temp_project.target_project,
        "tmp_dir": str(temp_project.target_dir),
        "table_count": table_count,
        "middle_table_count": middle_count,
        "generated_model_count": int(
            result.get("generated_model_count") or len(generated_models)
        ),
        "model_change_count": int(result.get("model_change_count") or 0),
        "model_update_count": int(result.get("model_update_count") or 0),
        "blocked_table_count": status_counts["blocked"],
        "warning_count": status_counts["warning"],
        "metadata_warning_count": status_counts["metadata_warning"],
        "catalog_change_count": int(result.get("catalog_change_count") or 0),
        "catalog_update": result.get("catalog_update"),
        "planned_catalog_updates": result.get("planned_catalog_updates") or [],
        "catalog_updates": result.get("catalog_updates") or [],
        "llm_middle_correct_count": llm_middle_correct,
        "llm_middle_accuracy": (
            llm_middle_correct / middle_count if middle_count else 0.0
        ),
        "by_expected_layer": dict(sorted(by_expected.items())),
        "confusion": dict(sorted(confusion.items())),
        "final_layer_counts": dict(sorted(final_layer_counts.items())),
        "metric_count": metric_count,
        "metric_table_count": sum(
            1 for model in generated_models.values() if _metric_count(model)
        ),
        "entity_table_count": sum(
            1 for model in generated_models.values() if _has_entities(model)
        ),
        "grain_table_count": sum(
            1 for model in generated_models.values() if _has_grain(model)
        ),
        "mismatches": mismatches,
        "catalog_summary": catalog_summary,
    }


def _target_project_name(source_project: str) -> str:
    return f"{source_project}_generate_llm_benchmark"


def _managed_tmp_root(asset_dir: Optional[Path]) -> Tuple[Path, bool]:
    if asset_dir is not None:
        root = Path(asset_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root, False
    return Path(tempfile.mkdtemp(prefix="generate-llm-cold-start-")), True


def run_benchmark(
    *,
    projects: Iterable[str] = DEFAULT_PROJECTS,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    base_url: Optional[str] = DEFAULT_BASE_URL,
    parallelism: int = DEFAULT_PARALLELISM,
    max_retries: int = DEFAULT_MAX_RETRIES,
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    no_cache: bool = False,
    dry_run: bool = False,
    output_path: Optional[Path] = None,
    asset_dir: Optional[Path] = None,
    cleanup: bool = False,
    source_root: Path = REPO_ROOT,
    metadata_runner: Optional[MetadataRunner] = None,
    show_progress: bool = False,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required for generate --llm benchmark "
            "unless api_key is injected by a test"
        )
    base_url = normalize_chat_completions_url(base_url)

    runtime_config, runtime_writer = _runtime_modules()
    if metadata_runner is None:
        metadata_runner = runtime_writer.run_generate_model_metadata

    tmp_root, managed_root = _managed_tmp_root(asset_dir)
    snapshot = _snapshot_config()
    summaries: List[Dict[str, Any]] = []
    try:
        _activate_project_root(tmp_root)
        runtime_config.PROJECT_CONFIG.clear()
        runtime_config.PROJECT_CONFIG.update(snapshot.project_config)
        for source_project in projects:
            target_project = _target_project_name(source_project)
            temp_project = build_temp_project(
                source_project,
                target_project,
                tmp_root,
                source_root=source_root,
            )
            _register_target_project(temp_project, tmp_root)
            _write_extracted_lineage(
                temp_project,
                parallelism=parallelism,
            )
            result = metadata_runner(
                temp_project.target_project,
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_retries=max_retries,
                parallelism=parallelism,
                request_timeout=request_timeout,
                no_cache=no_cache,
                dry_run=dry_run,
                update_catalog=True,
                replace_existing_models=True,
                show_progress=show_progress,
                expose_layer_hints=False,
            )
            summaries.append(
                _summarize_project(
                    temp_project, result=result, dry_run=dry_run
                )
            )
    finally:
        _restore_config(snapshot)
        if cleanup and managed_root:
            shutil.rmtree(str(tmp_root))

    total_tables = sum(item["table_count"] for item in summaries)
    total_middle = sum(item["middle_table_count"] for item in summaries)
    llm_middle_correct = sum(
        item["llm_middle_correct_count"] for item in summaries
    )
    report = {
        "benchmark": "generate_llm_cold_start",
        "model": model,
        "base_url": base_url,
        "layer_hints_visible_to_llm": False,
        "parallelism": parallelism,
        "request_timeout": request_timeout,
        "dry_run": dry_run,
        "tmp_root": str(tmp_root),
        "total_table_count": total_tables,
        "total_middle_table_count": total_middle,
        "combined_llm_middle_accuracy": (
            llm_middle_correct / total_middle if total_middle else 0.0
        ),
        "total_catalog_change_count": sum(
            item["catalog_change_count"] for item in summaries
        ),
        "total_business_process_count": sum(
            item["catalog_summary"]["business_process_count"]
            for item in summaries
        ),
        "total_semantic_subject_count": sum(
            item["catalog_summary"]["semantic_subject_count"]
            for item in summaries
        ),
        "projects": summaries,
    }

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


def _print_report(report: Dict[str, Any]) -> None:
    print("generate --llm cold-start benchmark")
    print(f"  model: {report['model']}")
    print(f"  base_url: {report.get('base_url') or ''}")
    print(f"  tmp_root: {report['tmp_root']}")
    print(
        "  combined: llm_middle={:.2%}".format(
            report["combined_llm_middle_accuracy"],
        )
    )
    for project in report["projects"]:
        print(
            "  {source_project}: llm_middle={llm_middle_accuracy:.2%} "
            "models={generated_model_count} catalog_changes={catalog_change_count}".format(
                **project
            )
        )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the generate --llm cold-start semantic metadata benchmark."
        )
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=list(DEFAULT_PROJECTS),
        help="Source warehouse projects to benchmark.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLELISM)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=DEFAULT_REQUEST_TIMEOUT,
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore table_inspector cache in the temporary project.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview model/catalog updates without writing generated YAML.",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Print table_inspector progress events.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--asset-dir",
        default=None,
        help=(
            "Optional temporary repo root. Assets are created below "
            "<asset-dir>/warehouses/{project} and are never deleted by cleanup."
        ),
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help=(
            "Delete the managed temporary root after the run. Ignored when "
            "--asset-dir is provided."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    args = parse_args(argv)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "DEEPSEEK_API_KEY is required. Export it or call run_benchmark() "
            "with an injected api_key in tests."
        )
    report = run_benchmark(
        projects=args.projects,
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
        parallelism=args.parallel,
        max_retries=args.max_retries,
        request_timeout=args.request_timeout,
        no_cache=args.no_cache,
        dry_run=args.dry_run,
        output_path=Path(args.output) if args.output else None,
        asset_dir=Path(args.asset_dir) if args.asset_dir else None,
        cleanup=args.cleanup,
        show_progress=args.show_progress,
    )
    _print_report(report)
    return report


if __name__ == "__main__":
    main()
