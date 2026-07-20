from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    load_business_semantics_catalog,
)
from dw_refactor_agent.config import (
    TEXT_ENCODING,
    get_business_domain_config,
    iter_project_asset_files,
    load_model_metadata,
    task_path_for_job,
)
from dw_refactor_agent.config.semantics import (
    business_domain_config_from_semantics_catalog,
)
from dw_refactor_agent.lineage.view import LineageView

DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
FIXED_BOUNDARY_ASSET_ROLES = {"ods", "ads"}
LOGGER = logging.getLogger(__name__)
GENERATED_KEY_FUNCTIONS = frozenset(
    {
        "FARM_FINGERPRINT",
        "HASH",
        "MD5",
        "SHA",
        "SHA1",
        "SHA2",
        "UUID",
        "UUID_STRING",
        "XXHASH64",
    }
)
VERSION_CONTROL_COLUMN_NAMES = frozenset(
    {
        "current_flag",
        "effective_date",
        "effective_from",
        "effective_to",
        "expiration_date",
        "is_current",
        "valid_from",
        "valid_to",
    }
)


def _short_table_name(table_name: str) -> str:
    text = str(table_name or "").strip().rstrip(";")
    text = text.replace("`", "").replace('"', "")
    return text.split(".")[-1].strip()


def _canonical_table_name(table_name: str) -> str:
    text = str(table_name or "").strip().rstrip(";")
    text = text.replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _ambiguous_short_table_names(table_names) -> frozenset[str]:
    qualified_by_short: dict[str, set[str]] = {}
    for table_name in table_names:
        identity = _canonical_table_name(table_name)
        if "." not in identity:
            continue
        short_name = _short_table_name(identity).casefold()
        qualified_by_short.setdefault(short_name, set()).add(identity)
    return frozenset(
        short_name
        for short_name, identities in qualified_by_short.items()
        if len(identities) > 1
    )


@dataclass(frozen=True)
class _CanonicalTableLookup:
    by_identity: dict
    unique_identity_by_short: dict[str, str]
    ambiguous_short_names: frozenset[str]

    def get(self, table_name: str, default=None):
        identity = _canonical_table_name(table_name)
        short_name = _short_table_name(identity).casefold()
        if identity == short_name and short_name in self.ambiguous_short_names:
            return default
        if identity in self.by_identity:
            return self.by_identity[identity]
        if "." in identity:
            return default
        fallback_identity = self.unique_identity_by_short.get(short_name)
        if fallback_identity is None:
            return default
        return self.by_identity[fallback_identity]

    def has_ambiguous_fallback(self, table_name: str) -> bool:
        identity = _canonical_table_name(table_name)
        if "." in identity:
            return False
        short_name = _short_table_name(identity).casefold()
        if short_name not in self.ambiguous_short_names:
            return False
        return identity == short_name or identity not in self.by_identity


def _canonical_table_lookup(
    values: dict,
    *,
    ambiguous_short_names: frozenset[str] = frozenset(),
) -> _CanonicalTableLookup:
    by_identity = {}
    identities_by_short: dict[str, set[str]] = {}
    for table_name, value in values.items():
        identity = _canonical_table_name(table_name)
        if not identity:
            continue
        by_identity.setdefault(identity, value)
        short_name = _short_table_name(identity).casefold()
        identities_by_short.setdefault(short_name, set()).add(identity)

    all_ambiguous_short_names = set(ambiguous_short_names)
    all_ambiguous_short_names.update(
        short_name
        for short_name, identities in identities_by_short.items()
        if len(identities) > 1
    )
    unique_identity_by_short = {
        short_name: next(iter(identities))
        for short_name, identities in identities_by_short.items()
        if len(identities) == 1 and short_name not in all_ambiguous_short_names
    }
    return _CanonicalTableLookup(
        by_identity=by_identity,
        unique_identity_by_short=unique_identity_by_short,
        ambiguous_short_names=frozenset(all_ambiguous_short_names),
    )


def _with_unique_qualified_aliases(values: dict, table_names) -> dict:
    expanded = dict(values)
    qualified_by_short: dict[str, set[str]] = {}
    for table_name in table_names:
        identity = _canonical_table_name(table_name)
        if "." not in identity:
            continue
        qualified_by_short.setdefault(
            _short_table_name(identity).casefold(), set()
        ).add(identity)

    for table_name, value in list(values.items()):
        identity = _canonical_table_name(table_name)
        if not identity or "." in identity:
            continue
        matches = qualified_by_short.get(identity) or set()
        if len(matches) == 1:
            expanded.setdefault(next(iter(matches)), value)
    return expanded


@dataclass
class TableContext:
    table_name: str
    layer: str
    ddl: str
    etl_sql: str
    upstream_tables: list[str]
    downstream_tables: list[str]
    table_identity: str = ""
    upstream_table_layers: dict[str, str] = field(default_factory=dict)
    downstream_table_layers: dict[str, str] = field(default_factory=dict)
    expose_layer_hints: bool = True
    depth_from_ods: int = 0
    upstream_metric_groups: dict[str, dict[str, list[str]]] = field(
        default_factory=dict
    )
    downstream_entity_publication_features: dict[str, dict] = field(
        default_factory=dict
    )
    column_lineage: list[dict] = field(default_factory=list)
    declared_data_domain: str = ""
    declared_business_area: str = ""
    project_context: str = ""
    business_domain_options: dict = field(default_factory=dict)
    business_semantics_options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _ModelMetadataEntry:
    table_name: str
    metadata: dict


def _metric_names(value) -> list[str]:
    names = []
    if isinstance(value, dict):
        iterable = value.values()
    elif isinstance(value, list):
        iterable = value
    else:
        iterable = []

    for item in iterable:
        if isinstance(item, list):
            for nested in item:
                name = _metric_name(nested)
                if name and name not in names:
                    names.append(name)
            continue
        name = _metric_name(item)
        if name and name not in names:
            names.append(name)
    return names


def _metric_name(item) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("column") or "").strip()
    return str(item or "").strip()


def _load_model_metric_groups(
    project: str,
) -> dict[str, dict[str, list[str]]]:
    metric_groups = {}

    for model_path in iter_project_asset_files(project, "models", "*.yaml"):
        try:
            data = (
                yaml.safe_load(model_path.read_text(encoding=TEXT_ENCODING))
                or {}
            )
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        table_name = str(data.get("name") or model_path.stem)
        groups = {
            "atomic_metrics": _metric_names(data.get("atomic_metrics")),
            "derived_metrics": _metric_names(data.get("derived_metrics")),
            "calculated_metrics": _metric_names(
                data.get("calculated_metrics")
            ),
        }
        if any(groups.values()):
            metric_groups[table_name] = groups
    return metric_groups


def _catalog_option_entries(raw_entries) -> list[dict]:
    entries = []
    if not isinstance(raw_entries, list):
        return entries
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").strip()
        if not code:
            continue
        item = {
            "code": code,
            "name": str(entry.get("name") or "").strip(),
        }
        data_domain = str(entry.get("data_domain") or "").strip()
        business_area = str(entry.get("business_area") or "").strip()
        if data_domain:
            item["data_domain"] = data_domain
        if business_area:
            item["business_area"] = business_area
        entries.append(item)
    return entries


def _business_semantics_prompt_options(
    project: str,
    catalog: dict | None = None,
) -> dict:
    catalog = (
        catalog
        if catalog is not None
        else load_business_semantics_catalog(project)
    )
    if not catalog:
        return {}
    options = {}
    processes = _catalog_option_entries(
        catalog.get("business_processes") or []
    )
    subjects = _catalog_option_entries(catalog.get("semantic_subjects") or [])
    if processes:
        options["business_processes"] = processes
    if subjects:
        options["semantic_subjects"] = subjects
    return options


def _project_context(
    project: str,
    catalog: dict | None = None,
) -> str:
    catalog = (
        catalog
        if catalog is not None
        else load_business_semantics_catalog(project)
    )
    if not catalog:
        return ""
    return str(catalog.get("project_context") or "").strip()


def extract_dependencies(lineage_data: dict) -> tuple[dict, dict]:
    """提取正式资产表级上下游关系，过滤并穿透临时表。"""
    return LineageView.from_data("", lineage_data).asset_table_graph()


def extract_column_lineage(lineage_data: dict, table_name: str) -> list[dict]:
    """提取正式资产字段血缘，过滤并穿透临时字段。"""
    return LineageView.from_data("", lineage_data).column_lineage_for_table(
        table_name
    )


def _canonical_model_metadata_index(
    model_metadata: dict,
) -> dict[str, _ModelMetadataEntry]:
    index = {}
    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        model_table_name = _short_table_name(
            metadata.get("name") or table_name
        )
        entry = _ModelMetadataEntry(model_table_name, metadata)
        key_identity = _canonical_table_name(table_name)
        metadata_identity = _canonical_table_name(metadata.get("name"))
        canonical_name = (
            key_identity
            if "." in key_identity
            else metadata_identity or key_identity
        )
        if canonical_name:
            index.setdefault(canonical_name, entry)
    return index


def _layer_for_context_table(
    table_name: str,
    model_metadata: _CanonicalTableLookup,
) -> str:
    entry = model_metadata.get(table_name)
    metadata = entry.metadata if entry else {}
    return str(metadata.get("layer") or "OTHER").upper()


def _canonical_dependency_index(dependencies: dict) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for table_name, related_tables in dependencies.items():
        canonical_name = _canonical_table_name(table_name)
        if canonical_name:
            index.setdefault(canonical_name, set()).update(related_tables)
    return index


def _project_dir(project: str) -> Path:
    project_cfg = config.PROJECT_CONFIG.get(project) or {}
    if project_cfg.get("dir"):
        return config.PROJECT_ROOT / project_cfg["dir"]
    return Path(__file__).resolve().parent.parent / project


def _project_model_asset_roles(project: str) -> dict[str, set[str]]:
    """Index model names by their independent on-disk asset role."""
    project_path = _project_dir(project)
    roles_by_name: dict[str, set[str]] = {}
    for model_path in iter_project_asset_files(project, "models", "*.yaml"):
        try:
            relative_parts = model_path.relative_to(project_path).parts
        except ValueError:
            continue
        if len(relative_parts) < 2 or relative_parts[1] != "models":
            continue
        role = str(relative_parts[0]).lower()
        if role not in {"ods", "mid", "ads"}:
            continue
        try:
            raw = (
                yaml.safe_load(model_path.read_text(encoding=TEXT_ENCODING))
                or {}
            )
        except (OSError, yaml.YAMLError):
            raw = {}
        declared_name = raw.get("name") if isinstance(raw, dict) else None
        for name in {model_path.stem, str(declared_name or "").strip()}:
            canonical_name = _canonical_table_name(name)
            if canonical_name:
                roles_by_name.setdefault(canonical_name, set()).add(role)
    return roles_by_name


def _metadata_asset_roles(
    model_metadata: dict[str, dict],
) -> dict[str, set[str]]:
    """Build asset roles from an explicit metadata snapshot only."""
    roles_by_name: dict[str, set[str]] = {}
    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        layer = str(metadata.get("layer") or "").upper()
        if layer == "ODS":
            role = "ods"
        elif layer == "ADS":
            role = "ads"
        elif layer in {"DWD", "DWS", "DIM"}:
            role = "mid"
        else:
            continue
        for name in {
            str(table_name or "").strip(),
            str(metadata.get("name") or "").strip(),
        }:
            canonical_name = _canonical_table_name(name)
            if canonical_name:
                roles_by_name.setdefault(canonical_name, set()).add(role)
    return roles_by_name


def _model_asset_roles_for_table(
    table_name: str,
    roles_by_name: dict[str, set[str]],
) -> set[str]:
    identity = _canonical_table_name(table_name)
    exact_roles = roles_by_name.get(identity)
    if exact_roles is not None:
        return exact_roles
    return roles_by_name.get(_short_table_name(identity).casefold(), set())


def _first_project_asset_file(
    project: str,
    asset_kind: str,
    filename: str,
) -> Path | None:
    files = iter_project_asset_files(project, asset_kind, filename)
    if files:
        return files[0]
    canonical_filename = filename.casefold()
    return next(
        (
            path
            for path in iter_project_asset_files(project, asset_kind, "*")
            if path.name.casefold() == canonical_filename
        ),
        None,
    )


def _first_directory_file(directory: Path, filename: str) -> Path | None:
    direct_path = directory / filename
    if direct_path.exists():
        return direct_path
    canonical_filename = filename.casefold()
    return next(
        (
            path
            for path in sorted(directory.glob("*"))
            if path.is_file() and path.name.casefold() == canonical_filename
        ),
        None,
    )


def _project_task_path(project: str, table_name: str) -> Path | None:
    task_path = task_path_for_job(
        project,
        table_name,
        include_full_refresh=False,
    )
    if task_path:
        return task_path
    return _first_project_asset_file(project, "tasks", f"{table_name}.sql")


def _normalized_output_name(expression) -> str:
    return (
        str(getattr(expression, "alias_or_name", "") or "").strip().casefold()
    )


def _uses_generated_key_function(expression) -> bool:
    return any(
        str(function.sql_name() or "").upper() in GENERATED_KEY_FUNCTIONS
        for function in expression.find_all(exp.Func)
    )


def _downstream_entity_publication_features(sql_text: str) -> dict:
    """Extract layer-neutral evidence of a downstream entity publish step."""
    if not str(sql_text or "").strip():
        return {}
    try:
        statements = sqlglot.parse(sql_text, dialect="doris")
    except Exception:
        return {}

    generated_key_columns = set()
    natural_key_aliases = set()
    added_version_control_columns = set()
    contains_aggregation = False
    combines_sources_with_union = False

    for statement in statements:
        if statement is None:
            continue
        if any(True for _ in statement.find_all(exp.Union)):
            combines_sources_with_union = True
        if any(True for _ in statement.find_all(exp.AggFunc)):
            contains_aggregation = True
        for select in statement.find_all(exp.Select):
            if select.args.get("group") is not None:
                contains_aggregation = True
            for projection in select.expressions:
                if not isinstance(projection, exp.Alias):
                    continue
                alias = _normalized_output_name(projection)
                if not alias:
                    continue
                source_expression = projection.this
                if alias.endswith("_key") and _uses_generated_key_function(
                    source_expression
                ):
                    generated_key_columns.add(alias)
                if "natural_key" in alias and any(
                    True for _ in source_expression.find_all(exp.Column)
                ):
                    natural_key_aliases.add(alias)
                if alias in VERSION_CONTROL_COLUMN_NAMES and not isinstance(
                    source_expression, exp.Column
                ):
                    added_version_control_columns.add(alias)

    # A generated entity key alone is common in facts too. Requiring an
    # explicit natural-key alias and no aggregation keeps this signal focused
    # on a later entity publication boundary without using table/layer names.
    if (
        not generated_key_columns
        or not natural_key_aliases
        or contains_aggregation
    ):
        return {}
    return {
        "generated_key_columns": sorted(generated_key_columns),
        "natural_key_aliases": sorted(natural_key_aliases),
        "added_version_control_columns": sorted(added_version_control_columns),
        "combines_sources_with_union": combines_sources_with_union,
        "contains_aggregation": contains_aggregation,
    }


def build_contexts(
    project: str,
    lineage_data: dict,
    ddl_dir: Path = None,
    tasks_dir: Path = None,
    layers: set[str] | None = None,
    model_metadata: dict | None = None,
    metric_groups: dict[str, dict[str, list[str]]] | None = None,
    expose_layer_hints: bool = True,
    use_model_metadata_asset_roles: bool = False,
    asset_content: dict[str, dict[str, str]] | None = None,
    business_semantics_catalog: dict | None = None,
) -> list[TableContext]:
    """为 DWD/DWS/DIM 层所有表构建分类上下文"""
    use_project_asset_dirs = ddl_dir is None
    use_project_task_dirs = tasks_dir is None

    lineage_view = LineageView.from_data(project, lineage_data)
    upstream, downstream = lineage_view.asset_table_graph()
    dependency_table_names = set(upstream) | set(downstream)
    for dependencies in (upstream, downstream):
        for related_tables in dependencies.values():
            dependency_table_names.update(related_tables)
    dependency_table_names.update(
        table.get("name")
        for table in lineage_data.get("tables", [])
        if table.get("name")
    )
    ambiguous_short_names = _ambiguous_short_table_names(
        dependency_table_names
    )
    canonical_upstream = _canonical_table_lookup(
        _canonical_dependency_index(upstream),
        ambiguous_short_names=ambiguous_short_names,
    )
    canonical_downstream = _canonical_table_lookup(
        _canonical_dependency_index(downstream),
        ambiguous_short_names=ambiguous_short_names,
    )
    has_lineage_edges = any(upstream.values()) or any(downstream.values())
    target_layers = set(layers or ("DWD", "DWS", "DIM"))
    metric_groups = (
        metric_groups
        if metric_groups is not None
        else _load_model_metric_groups(project)
    )
    explicit_model_metadata = model_metadata is not None
    model_metadata = (
        model_metadata
        if explicit_model_metadata
        else load_model_metadata(project)
    )
    canonical_model_metadata = _canonical_table_lookup(
        _with_unique_qualified_aliases(
            _canonical_model_metadata_index(model_metadata),
            dependency_table_names,
        ),
        ambiguous_short_names=ambiguous_short_names,
    )
    canonical_metric_groups = _canonical_table_lookup(
        _with_unique_qualified_aliases(
            metric_groups,
            dependency_table_names,
        ),
        ambiguous_short_names=ambiguous_short_names,
    )
    business_domain_config = (
        business_domain_config_from_semantics_catalog(
            business_semantics_catalog
        )
        if business_semantics_catalog is not None
        else get_business_domain_config(project)
    )
    business_domain_options = (
        business_domain_config.prompt_options()
        if business_domain_config
        else {}
    )
    business_semantics_options = _business_semantics_prompt_options(
        project,
        business_semantics_catalog,
    )
    project_context = _project_context(project, business_semantics_catalog)
    if not use_project_asset_dirs:
        model_asset_roles = {}
    elif explicit_model_metadata and use_model_metadata_asset_roles:
        # Generate passes an in-memory cold-start candidate.  Its inspection
        # boundary must not depend on stale YAML files still present on disk.
        model_asset_roles = _metadata_asset_roles(model_metadata)
    else:
        model_asset_roles = _project_model_asset_roles(project)
    contexts = []
    canonical_asset_content = {
        _canonical_table_name(table_name): dict(content)
        for table_name, content in (asset_content or {}).items()
    }

    def get_asset_content(table_name: str) -> dict[str, str] | None:
        identity = _canonical_table_name(table_name)
        content = canonical_asset_content.get(identity)
        if content is not None:
            return content
        return canonical_asset_content.get(
            _short_table_name(identity).casefold()
        )

    memo = {}
    downstream_publication_feature_cache: dict[str, dict] = {}

    def get_downstream_publication_features(table_name: str) -> dict:
        canonical_name = _canonical_table_name(table_name)
        if canonical_name in downstream_publication_feature_cache:
            return downstream_publication_feature_cache[canonical_name]

        model_entry = canonical_model_metadata.get(table_name)
        if canonical_model_metadata.has_ambiguous_fallback(table_name):
            LOGGER.warning(
                "Ambiguous downstream table name %s; qualified task "
                "identity is required for publication feature extraction",
                _short_table_name(table_name),
            )
            downstream_publication_feature_cache[canonical_name] = {}
            return {}
        model_table_name = (
            model_entry.table_name
            if model_entry
            else _short_table_name(table_name)
        )
        snapshot_content = get_asset_content(model_table_name)
        if snapshot_content is not None:
            sql_text = str(snapshot_content.get("etl_sql") or "")
        else:
            task_path = (
                _project_task_path(project, model_table_name)
                if use_project_task_dirs
                else _first_directory_file(
                    tasks_dir,
                    f"{model_table_name}.sql",
                )
            )
            sql_text = (
                task_path.read_text(encoding=TEXT_ENCODING)
                if task_path and task_path.exists()
                else ""
            )
        features = _downstream_entity_publication_features(sql_text)
        downstream_publication_feature_cache[canonical_name] = features
        return features

    def get_depth_from_ods(table_name: str, visiting: set = None) -> int:
        canonical_name = _canonical_table_name(table_name)
        if visiting is None:
            visiting = set()
        if canonical_name in memo:
            return memo[canonical_name]
        if canonical_name in visiting:
            return 0
        visiting.add(canonical_name)

        parents = canonical_upstream.get(table_name, set())
        if not parents:
            short_name = _short_table_name(canonical_name).casefold()
            result = 0 if short_name.startswith("ods_") else 1
        else:
            result = min(get_depth_from_ods(p, visiting) for p in parents) + 1

        visiting.remove(canonical_name)
        memo[canonical_name] = result
        return result

    for table in lineage_data.get("tables", []):
        name = table["name"]
        short_name = _short_table_name(name)
        model_entry = canonical_model_metadata.get(name)
        if canonical_model_metadata.has_ambiguous_fallback(name):
            LOGGER.warning(
                "Ambiguous short table name %s; qualified model metadata is "
                "required",
                short_name,
            )
        metadata = model_entry.metadata if model_entry else {}
        model_table_name = (
            model_entry.table_name if model_entry else short_name
        )
        layer = str(metadata.get("layer") or "OTHER").upper()
        fixed_boundary_roles = (
            _model_asset_roles_for_table(
                model_table_name,
                model_asset_roles,
            )
            & FIXED_BOUNDARY_ASSET_ROLES
        )
        if fixed_boundary_roles:
            if layer in target_layers:
                LOGGER.warning(
                    "Skipping fixed-boundary model %s from %s/models: "
                    "declared layer %s is not eligible for table inspection",
                    model_table_name,
                    "/".join(sorted(fixed_boundary_roles)),
                    layer,
                )
            continue
        if layer not in target_layers:
            continue

        # Read DDL
        snapshot_content = get_asset_content(model_table_name)
        if snapshot_content is not None:
            ddl_content = str(snapshot_content.get("ddl") or "")
            etl_content = str(snapshot_content.get("etl_sql") or "")
        else:
            ddl_path = (
                _first_project_asset_file(
                    project,
                    "ddl",
                    f"{model_table_name}.sql",
                )
                if use_project_asset_dirs
                else _first_directory_file(ddl_dir, f"{model_table_name}.sql")
            )
            ddl_content = (
                ddl_path.read_text(encoding=TEXT_ENCODING)
                if ddl_path and ddl_path.exists()
                else ""
            )

            # Read ETL
            task_path = (
                _project_task_path(project, model_table_name)
                if use_project_task_dirs
                else _first_directory_file(
                    tasks_dir,
                    f"{model_table_name}.sql",
                )
            )
            etl_content = (
                task_path.read_text(encoding=TEXT_ENCODING)
                if task_path and task_path.exists()
                else ""
            )
        upstream_tables = sorted(canonical_upstream.get(name, set()))
        downstream_tables = sorted(canonical_downstream.get(name, set()))
        upstream_metric_groups = {}
        for upstream_table in upstream_tables:
            groups = canonical_metric_groups.get(upstream_table)
            if groups is not None:
                upstream_metric_groups[upstream_table] = groups
            elif canonical_metric_groups.has_ambiguous_fallback(
                upstream_table
            ):
                LOGGER.warning(
                    "Ambiguous short table name %s; qualified metric groups "
                    "are required",
                    _short_table_name(upstream_table),
                )
        downstream_entity_publication_features = {}
        for downstream_table in downstream_tables:
            features = get_downstream_publication_features(downstream_table)
            if features:
                downstream_entity_publication_features[downstream_table] = (
                    features
                )

        contexts.append(
            TableContext(
                table_name=model_table_name,
                table_identity=name,
                layer=layer,
                ddl=ddl_content,
                etl_sql=etl_content,
                upstream_tables=upstream_tables,
                downstream_tables=downstream_tables,
                upstream_table_layers={
                    table_name: _layer_for_context_table(
                        table_name,
                        canonical_model_metadata,
                    )
                    for table_name in upstream_tables
                },
                downstream_table_layers={
                    table_name: _layer_for_context_table(
                        table_name,
                        canonical_model_metadata,
                    )
                    for table_name in downstream_tables
                },
                expose_layer_hints=expose_layer_hints,
                depth_from_ods=get_depth_from_ods(name),
                upstream_metric_groups=upstream_metric_groups,
                downstream_entity_publication_features=(
                    downstream_entity_publication_features
                ),
                column_lineage=(lineage_view.column_lineage_for_table(name)),
                declared_data_domain=(
                    str(metadata.get("data_domain") or "")
                    if layer in DATA_DOMAIN_LAYERS
                    else ""
                ),
                declared_business_area=(
                    str(metadata.get("business_area") or "")
                    if layer in BUSINESS_AREA_LAYERS
                    else ""
                ),
                project_context=project_context,
                business_domain_options=business_domain_options,
                business_semantics_options=business_semantics_options,
            )
        )

    task_context_count = sum(bool(ctx.etl_sql.strip()) for ctx in contexts)
    if not has_lineage_edges and task_context_count:
        LOGGER.warning(
            "Lineage graph is empty for project %s while %s inspected "
            "tables have task SQL; dependencies were not inferred from SQL. "
            "Refresh or repair the lineage snapshot.",
            project,
            task_context_count,
        )

    return contexts
