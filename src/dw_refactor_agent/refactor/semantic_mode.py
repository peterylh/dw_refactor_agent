"""Resolve table semantic modes and verification boundaries."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import ParseError

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.ddl_deriver.ddl_deriver import (
    normalize_schema_id,
    parse_create_table,
)
from dw_refactor_agent.lineage.asset_graph import build_asset_table_graph
from dw_refactor_agent.refactor.artifact_contract import sha256_json

VALID_SEMANTIC_MODES = frozenset(("equivalent", "changed", "unknown"))
SEMANTIC_ASSET_KINDS = (
    "ddl",
    "task",
    "full_refresh_task",
    "model",
)


@dataclass(frozen=True)
class SemanticResolution:
    """Resolved semantics and selected validation boundaries."""

    target_semantics: dict
    boundaries: dict
    selected_tables: tuple
    warnings: tuple
    inherited_declarations: dict
    diagnostics: tuple = ()


@dataclass(frozen=True)
class _AssetFile:
    path: str
    content: bytes

    def descriptor(self) -> dict:
        digest = hashlib.sha256(self.content).hexdigest()
        return {
            "path": self.path,
            "content_sha256": f"sha256:{digest}",
        }

    def text(self) -> str:
        return self.content.decode(TEXT_ENCODING)


def local_change_fingerprint(
    project: str,
    table_id: str,
    baseline: dict,
    current: dict,
) -> str:
    """Hash the baseline/current semantic assets for one stable table."""
    return sha256_json(
        {
            "fingerprint_version": 1,
            "project": project,
            "table_id": table_id,
            "baseline": baseline,
            "current": current,
        }
    )


def semantic_context_fingerprint(
    local_fingerprint: str, upstream_records: list
) -> str:
    """Hash local assets together with affected upstream semantics."""
    ordered_upstreams = sorted(
        upstream_records,
        key=lambda item: (
            item["upstream_table_id"],
            item["upstream_semantic_context_fingerprint"],
            item["upstream_resolved_mode"],
        ),
    )
    return sha256_json(
        {
            "fingerprint_version": 1,
            "local_change_fingerprint": local_fingerprint,
            "affected_upstreams": ordered_upstreams,
        }
    )


def _canonical_identifier_mapping(mapping: dict) -> dict:
    canonical = {}
    for index, (source, target) in enumerate(
        sorted(
            (str(source), str(target))
            for source, target in (mapping or {}).items()
        )
    ):
        token = f"__semantic_rename_{index}"
        canonical[source.casefold()] = token
        canonical[target.casefold()] = token
    return canonical


def _renamed_identifier(node: exp.Expression, mapping: dict) -> exp.Expression:
    if not isinstance(node, exp.Identifier):
        return node
    mapped = mapping.get(str(node.this).casefold())
    if mapped is None:
        return node
    replacement = node.copy()
    replacement.set("this", mapped)
    return replacement


def _normalized_sql_ast(sql_text: str, rename_mapping: dict) -> list:
    statements = sqlglot.parse(sql_text, dialect="doris")
    normalized_mapping = _canonical_identifier_mapping(rename_mapping)
    if not normalized_mapping:
        return statements
    normalized = [
        statement.transform(
            lambda node: _renamed_identifier(node, normalized_mapping),
            copy=True,
        )
        for statement in statements
    ]
    return [
        statement.transform(_remove_redundant_rename_alias, copy=False)
        for statement in normalized
    ]


def _remove_redundant_rename_alias(node: exp.Expression) -> exp.Expression:
    if not isinstance(node, exp.Alias) or not isinstance(
        node.this, exp.Column
    ):
        return node
    if node.alias.casefold() != node.this.name.casefold():
        return node
    return node.this


def sql_ast_equivalent(
    baseline_sql: str,
    current_sql: str,
    rename_mapping: dict,
) -> bool:
    """Return true only when parsed Doris ASTs are exactly equivalent."""
    try:
        baseline_ast = _normalized_sql_ast(baseline_sql, rename_mapping)
        current_ast = _normalized_sql_ast(current_sql, rename_mapping)
    except (ParseError, AttributeError, TypeError, ValueError):
        return False
    return bool(baseline_ast) and baseline_ast == current_ast


def _identity_blocker(message: str) -> dict:
    return {
        "table_id": "",
        "prod_table": "",
        "qa_table": "",
        "column_mapping": [],
        "rename_mapping": {},
        "compare_blocker": message,
    }


def schema_identity_mapping(baseline_ddl: str, current_ddl: str) -> dict:
    """Build a complete production/QA mapping from stable schema IDs."""
    baseline_table = parse_create_table(baseline_ddl or "")
    current_table = parse_create_table(current_ddl or "")
    if baseline_table is None or current_table is None:
        return _identity_blocker(
            "complete stable table identity requires parseable baseline and "
            "current DDL"
        )
    baseline_table_id = normalize_schema_id(baseline_table.table_id)
    current_table_id = normalize_schema_id(current_table.table_id)
    if not baseline_table_id or baseline_table_id != current_table_id:
        return _identity_blocker(
            "complete stable table identity requires the same table_id"
        )

    baseline_columns = {}
    current_columns = {}
    for column in baseline_table.columns:
        column_id = normalize_schema_id(column.column_id)
        if not column_id or column_id in baseline_columns:
            return _identity_blocker(
                "complete stable column identity is required for every "
                "baseline column"
            )
        baseline_columns[column_id] = column.name
    for column in current_table.columns:
        column_id = normalize_schema_id(column.column_id)
        if not column_id or column_id in current_columns:
            return _identity_blocker(
                "complete stable column identity is required for every "
                "current column"
            )
        current_columns[column_id] = column.name
    if set(baseline_columns) != set(current_columns):
        return _identity_blocker(
            "complete stable column identity requires identical column_id sets"
        )

    column_mapping = []
    rename_mapping = {}
    if baseline_table.short_name != current_table.short_name:
        rename_mapping[baseline_table.short_name] = current_table.short_name
    for column in baseline_table.columns:
        column_id = normalize_schema_id(column.column_id)
        current_name = current_columns[column_id]
        column_mapping.append(
            {
                "column_id": column_id,
                "prod": column.name,
                "qa": current_name,
            }
        )
        if column.name != current_name:
            rename_mapping[column.name] = current_name
    return {
        "table_id": baseline_table_id,
        "prod_table": baseline_table.short_name,
        "qa_table": current_table.short_name,
        "column_mapping": column_mapping,
        "rename_mapping": rename_mapping,
        "compare_blocker": None,
    }


def _normalized_model_value(value, rename_mapping: dict):
    canonical_mapping = _canonical_identifier_mapping(rename_mapping)
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized_key = canonical_mapping.get(
                str(key).casefold(), str(key)
            )
            normalized[normalized_key] = _normalized_model_value(
                item, rename_mapping
            )
        return normalized
    if isinstance(value, list):
        return [
            _normalized_model_value(item, rename_mapping) for item in value
        ]
    if isinstance(value, str):
        return canonical_mapping.get(value.casefold(), value)
    return value


def _model_equivalent(
    baseline_model: str, current_model: str, rename_mapping: dict
) -> bool:
    try:
        baseline = yaml.safe_load(baseline_model)
        current = yaml.safe_load(current_model)
    except yaml.YAMLError:
        return False
    return _normalized_model_value(
        baseline, rename_mapping
    ) == _normalized_model_value(current, rename_mapping)


def _optional_sql_equivalent(
    baseline_sql: str | None,
    current_sql: str | None,
    rename_mapping: dict,
) -> bool:
    if baseline_sql is None or current_sql is None:
        return baseline_sql is None and current_sql is None
    return sql_ast_equivalent(baseline_sql, current_sql, rename_mapping)


def automatic_equivalence(
    baseline_assets: dict,
    current_assets: dict,
) -> tuple[str | None, list, dict]:
    """Apply strict deterministic equivalence rules to one table's assets."""
    identity = schema_identity_mapping(
        baseline_assets.get("ddl"), current_assets.get("ddl")
    )
    if identity["compare_blocker"] is not None:
        return None, [], identity
    rename_mapping = identity["rename_mapping"]
    if not sql_ast_equivalent(
        baseline_assets["ddl"], current_assets["ddl"], rename_mapping
    ):
        return None, [], identity
    for asset_kind in ("task", "full_refresh_task"):
        if not _optional_sql_equivalent(
            baseline_assets.get(asset_kind),
            current_assets.get(asset_kind),
            rename_mapping,
        ):
            return None, [], identity

    baseline_model = baseline_assets.get("model")
    current_model = current_assets.get("model")
    if baseline_model is None or current_model is None:
        if baseline_model is not None or current_model is not None:
            return None, [], identity
    elif not _model_equivalent(baseline_model, current_model, rename_mapping):
        return None, [], identity

    rule = (
        "stable_id_pure_rename"
        if rename_mapping
        else "normalized_sql_ast_equal"
    )
    return "equivalent", [{"rule": rule}], identity


def _semantic_graph(table_facts: dict, edges) -> tuple[dict, dict]:
    nodes = set(table_facts)
    downstream = {table: set() for table in nodes}
    upstream = {table: set() for table in nodes}
    for source, target in edges or []:
        if source == target or source not in nodes or target not in nodes:
            continue
        downstream[source].add(target)
        upstream[target].add(source)
    return downstream, upstream


def _topological_tables(downstream: dict, upstream: dict) -> tuple[str, ...]:
    remaining_upstreams = {
        table: set(parents) for table, parents in upstream.items()
    }
    ready = sorted(
        table for table, parents in remaining_upstreams.items() if not parents
    )
    ordered = []
    while ready:
        table = ready.pop(0)
        ordered.append(table)
        for child in sorted(downstream[table]):
            remaining_upstreams[child].discard(table)
            if (
                not remaining_upstreams[child]
                and child not in ordered
                and child not in ready
            ):
                ready.append(child)
                ready.sort()
    if len(ordered) != len(remaining_upstreams):
        cyclic = sorted(set(remaining_upstreams) - set(ordered))
        raise ValueError("semantic graph cycle detected: " + ", ".join(cyclic))
    return tuple(ordered)


def _valid_declaration(
    declaration: dict,
    *,
    table_id: str,
    context_fingerprint: str,
) -> bool:
    return bool(
        isinstance(declaration, dict)
        and declaration.get("table_id") == table_id
        and declaration.get("mode") in VALID_SEMANTIC_MODES
        and declaration.get("semantic_context_fingerprint")
        == context_fingerprint
    )


def _historical_declaration(
    historical_manifests: list,
    *,
    table_name: str,
    table_id: str,
    context_fingerprint: str,
) -> tuple[dict, dict] | tuple[None, None]:
    for manifest in historical_manifests or []:
        declarations = (manifest.get("verification_intent") or {}).get(
            "semantic_modes"
        ) or {}
        for declaration in declarations.values():
            if not _valid_declaration(
                declaration,
                table_id=table_id,
                context_fingerprint=context_fingerprint,
            ):
                continue
            inherited = dict(declaration)
            inherited["table_id"] = table_id
            inherited["inherited_from_run_id"] = manifest.get("run_id")
            return (
                {
                    "mode": declaration["mode"],
                    "source": "inherited_user",
                },
                {table_name: inherited},
            )
    return None, None


def _resolved_declaration(
    table_name: str,
    fact: dict,
    context_fingerprint: str,
    current_declarations: dict,
    historical_manifests: list,
) -> tuple[dict | None, dict, dict | None]:
    current = (current_declarations or {}).get(table_name)
    stale_warning = None
    if current is not None:
        if _valid_declaration(
            current,
            table_id=fact["table_id"],
            context_fingerprint=context_fingerprint,
        ):
            return {"mode": current["mode"], "source": "user"}, {}, None
        stale_warning = {
            "type": "stale_semantic_declaration",
            "table": table_name,
            "message": (
                "The saved semantic declaration does not match the current "
                "table identity or semantic context and was not applied."
            ),
        }
    declaration, inherited = _historical_declaration(
        historical_manifests,
        table_name=table_name,
        table_id=fact["table_id"],
        context_fingerprint=context_fingerprint,
    )
    return declaration, inherited or {}, stale_warning


def _mode_and_source(
    declaration: dict | None,
    risky_upstreams: list,
    automatic_mode: str | None,
) -> tuple[str, str]:
    if declaration is not None:
        return declaration["mode"], declaration["source"]
    if risky_upstreams:
        return "unknown", "upstream_propagation"
    if automatic_mode == "equivalent":
        return "equivalent", "automatic"
    return "unknown", "default_unknown"


def _unknown_warning(table_name: str) -> dict:
    return {
        "type": "unknown_table_semantics",
        "table": table_name,
        "message": (
            "Only downstream observational anchors are compared; passing "
            "checks does not prove this table is equivalent."
        ),
    }


def _selected_boundaries(
    table_facts: dict,
    semantics: dict,
    downstream: dict,
    topological_order: tuple,
) -> tuple[dict, tuple]:
    authority = set()
    observational = set()
    selected = set()

    def walk(table_name: str) -> None:
        selected.add(table_name)
        mode = semantics[table_name]["resolved_mode"]
        if mode == "equivalent":
            authority.add(table_name)
            return
        children = sorted(downstream[table_name])
        if not children:
            if mode == "unknown" and table_facts[table_name].get(
                "comparable", True
            ):
                observational.add(table_name)
            return
        for child in children:
            walk(child)

    seeds = []
    for table_name in topological_order:
        fact = table_facts[table_name]
        source = semantics[table_name]["resolved_source"]
        if fact.get("is_direct") or source in {"user", "inherited_user"}:
            seeds.append(table_name)
    for table_name in seeds:
        walk(table_name)

    selected_order = tuple(
        table for table in topological_order if table in selected
    )
    return {
        "authority": sorted(authority),
        "observational": sorted(observational),
    }, selected_order


def resolve_semantic_graph(
    table_facts: dict,
    edges,
    *,
    current_declarations: dict | None = None,
    historical_manifests: list | None = None,
) -> SemanticResolution:
    """Resolve modes topologically and select nearest validation boundaries."""
    downstream, upstream = _semantic_graph(table_facts, edges)
    topological_order = _topological_tables(downstream, upstream)
    semantics = {}
    warnings = []
    inherited_declarations = {}

    for table_name in topological_order:
        fact = table_facts[table_name]
        upstream_records = []
        upstream_context = []
        risky_upstreams = []
        for upstream_table in sorted(upstream[table_name]):
            upstream_semantics = semantics[upstream_table]
            upstream_records.append(
                {
                    "upstream_table_id": upstream_semantics["table_id"],
                    "upstream_semantic_context_fingerprint": (
                        upstream_semantics["semantic_context_fingerprint"]
                    ),
                    "upstream_resolved_mode": upstream_semantics[
                        "resolved_mode"
                    ],
                }
            )
            upstream_context.append(
                {
                    "table": upstream_table,
                    "resolved_mode": upstream_semantics["resolved_mode"],
                }
            )
            if upstream_semantics["resolved_mode"] in {"changed", "unknown"}:
                risky_upstreams.append(upstream_table)

        context_fingerprint = semantic_context_fingerprint(
            fact["local_change_fingerprint"], upstream_records
        )
        declaration, inherited, stale_warning = _resolved_declaration(
            table_name,
            fact,
            context_fingerprint,
            current_declarations or {},
            historical_manifests or [],
        )
        inherited_declarations.update(inherited)
        if stale_warning is not None:
            warnings.append(stale_warning)
        resolved_mode, resolved_source = _mode_and_source(
            declaration,
            risky_upstreams,
            fact.get("automatic_mode"),
        )
        record = {
            "table_id": fact["table_id"],
            "declared_mode": (
                declaration["mode"] if declaration is not None else None
            ),
            "automatic_mode": fact.get("automatic_mode"),
            "resolved_mode": resolved_mode,
            "resolved_source": resolved_source,
            "local_change_fingerprint": fact["local_change_fingerprint"],
            "semantic_context_fingerprint": context_fingerprint,
            "upstream_context": upstream_context,
            "evidence": list(fact.get("evidence") or []),
        }
        for key in (
            "prod_table",
            "qa_table",
            "column_mapping",
            "compare_blocker",
        ):
            if key in fact:
                record[key] = fact[key]
        semantics[table_name] = record
        if resolved_mode == "unknown":
            warnings.append(_unknown_warning(table_name))

    boundaries, selected_tables = _selected_boundaries(
        table_facts,
        semantics,
        downstream,
        topological_order,
    )
    return SemanticResolution(
        target_semantics=semantics,
        boundaries=boundaries,
        selected_tables=selected_tables,
        warnings=tuple(warnings),
        inherited_declarations=inherited_declarations,
    )


def _git_output(repo_root: Path, *args: str, text: bool):
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=text,
    ).stdout


def _baseline_asset_files(
    repo_root: Path, project_dir: str, base_ref: str
) -> dict[str, bytes]:
    output = _git_output(
        repo_root,
        "ls-tree",
        "-r",
        "--name-only",
        base_ref,
        "--",
        project_dir,
        text=True,
    )
    files = {}
    for line in output.splitlines():
        relative_path = line.strip()
        if not relative_path:
            continue
        classification = _asset_path_classification(relative_path, project_dir)
        if classification is None:
            continue
        files[relative_path] = _git_output(
            repo_root,
            "show",
            f"{base_ref}:{relative_path}",
            text=False,
        )
    return files


def _current_asset_files(
    repo_root: Path, project_dir: str
) -> dict[str, bytes]:
    project_root = repo_root / project_dir
    files = {}
    if not project_root.is_dir():
        return files
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(repo_root).as_posix()
        if _asset_path_classification(relative_path, project_dir) is None:
            continue
        files[relative_path] = path.read_bytes()
    return files


def _asset_path_classification(
    relative_path: str, project_dir: str
) -> tuple[str, str] | None:
    path = Path(relative_path)
    try:
        project_relative = path.relative_to(Path(project_dir))
    except ValueError:
        return None
    parts = project_relative.parts
    if len(parts) < 3 or parts[0] not in {"ods", "mid", "ads"}:
        return None
    asset_group = parts[1]
    suffix = path.suffix.casefold()
    if asset_group == "ddl" and suffix == ".sql":
        return "ddl", path.stem
    if asset_group == "tasks" and suffix == ".sql":
        table_name = path.stem
        is_full_refresh = "full_refresh" in parts[2:-1]
        if table_name.endswith("_full_refresh"):
            table_name = table_name[: -len("_full_refresh")]
            is_full_refresh = True
        kind = "full_refresh_task" if is_full_refresh else "task"
        return kind, table_name
    if asset_group == "models" and suffix in {".yaml", ".yml"}:
        return "model", path.stem
    return None


def _asset_index(
    files: dict[str, bytes], project_dir: str
) -> dict[str, dict[str, _AssetFile]]:
    index = {}
    for relative_path, content in sorted(files.items()):
        classification = _asset_path_classification(relative_path, project_dir)
        if classification is None:
            continue
        kind, table_name = classification
        table_assets = index.setdefault(table_name, {})
        if kind in table_assets:
            raise ValueError(
                f"duplicate semantic {kind} asset for table {table_name}: "
                f"{table_assets[kind].path}, {relative_path}"
            )
        table_assets[kind] = _AssetFile(relative_path, content)
    return index


def _name_lookup(index: dict) -> dict[str, str]:
    return {str(name).casefold(): name for name in index}


def _ddl_table(asset: _AssetFile | None):
    if asset is None:
        return None
    try:
        return parse_create_table(asset.text())
    except UnicodeDecodeError:
        return None


def _table_id_by_name(index: dict) -> dict[str, str]:
    result = {}
    for table_name, assets in index.items():
        table = _ddl_table(assets.get("ddl"))
        if table is None:
            continue
        table_id = normalize_schema_id(table.table_id)
        if table_id:
            result[table_name] = table_id
    return result


def _assets_as_text(index: dict, table_name: str | None) -> dict:
    table_assets = index.get(table_name, {}) if table_name else {}
    result = {}
    for kind in SEMANTIC_ASSET_KINDS:
        asset = table_assets.get(kind)
        if asset is None:
            result[kind] = None
            continue
        try:
            result[kind] = asset.text()
        except UnicodeDecodeError:
            result[kind] = None
    return result


def _assets_for_fingerprint(index: dict, table_name: str | None) -> dict:
    table_assets = index.get(table_name, {}) if table_name else {}
    result = {"logical_name": table_name}
    for kind in SEMANTIC_ASSET_KINDS:
        asset = table_assets.get(kind)
        result[kind] = asset.descriptor() if asset is not None else None
    return result


def _affected_table_names(change_analysis: dict) -> list[str]:
    scope = change_analysis.get("affected_scope") or {}
    names = set(scope.get("direct_tables") or [])
    names.update(scope.get("downstream_tables") or [])
    names.update(scope.get("anchor_tables") or [])
    return sorted(names, key=lambda name: str(name).casefold())


def _direct_table_keys(change_analysis: dict) -> set[str]:
    scope = change_analysis.get("affected_scope") or {}
    direct = set(scope.get("direct_tables") or [])
    assets = change_analysis.get("changed_assets") or {}
    for key in ("ddl_tables", "task_jobs", "model_tables"):
        direct.update(assets.get(key) or [])
    return {str(name).casefold() for name in direct}


def _matched_table_names(
    affected_name: str,
    baseline_index: dict,
    current_index: dict,
    baseline_ids: dict,
    current_ids: dict,
) -> tuple[str | None, str | None, str]:
    baseline_names = _name_lookup(baseline_index)
    current_names = _name_lookup(current_index)
    affected_key = str(affected_name).casefold()
    current_name = current_names.get(affected_key)
    baseline_name = baseline_names.get(affected_key)

    current_id = current_ids.get(current_name) if current_name else None
    baseline_by_id = {
        table_id: table_name for table_name, table_id in baseline_ids.items()
    }
    current_by_id = {
        table_id: table_name for table_name, table_id in current_ids.items()
    }
    if current_id:
        baseline_name = baseline_by_id.get(current_id, baseline_name)
    elif baseline_name:
        baseline_id = baseline_ids.get(baseline_name)
        if baseline_id:
            current_name = current_by_id.get(baseline_id, current_name)

    table_id = (
        (current_ids.get(current_name) if current_name else None)
        or (baseline_ids.get(baseline_name) if baseline_name else None)
        or f"unmanaged:{affected_key}"
    )
    return baseline_name, current_name, table_id


def _semantic_table_facts(
    project: str,
    change_analysis: dict,
    baseline_index: dict,
    current_index: dict,
) -> tuple[dict, dict]:
    baseline_ids = _table_id_by_name(baseline_index)
    current_ids = _table_id_by_name(current_index)
    direct_keys = _direct_table_keys(change_analysis)
    facts = {}
    baseline_to_current = {}
    for affected_name in _affected_table_names(change_analysis):
        baseline_name, current_name, table_id = _matched_table_names(
            affected_name,
            baseline_index,
            current_index,
            baseline_ids,
            current_ids,
        )
        display_name = current_name or baseline_name or affected_name
        baseline_assets = _assets_as_text(baseline_index, baseline_name)
        current_assets = _assets_as_text(current_index, current_name)
        automatic_mode, evidence, identity = automatic_equivalence(
            baseline_assets, current_assets
        )
        fact = {
            "table_id": table_id,
            "local_change_fingerprint": local_change_fingerprint(
                project,
                table_id,
                _assets_for_fingerprint(baseline_index, baseline_name),
                _assets_for_fingerprint(current_index, current_name),
            ),
            "automatic_mode": automatic_mode,
            "is_direct": str(affected_name).casefold() in direct_keys,
            "comparable": identity["compare_blocker"] is None,
            "evidence": evidence,
            "prod_table": identity["prod_table"]
            or baseline_name
            or display_name,
            "qa_table": identity["qa_table"] or current_name or display_name,
            "column_mapping": identity["column_mapping"],
            "compare_blocker": identity["compare_blocker"],
        }
        facts[display_name] = fact
        if baseline_name:
            baseline_to_current[baseline_name.casefold()] = display_name
    return facts, baseline_to_current


def _lineage_edges(lineage_data: dict) -> set[tuple[str, str]]:
    _upstream, downstream = build_asset_table_graph(lineage_data or {})
    return {
        (source, target)
        for source, targets in downstream.items()
        for target in targets
        if source and target and source != target
    }


def _affected_edges(
    facts: dict,
    baseline_lineage: dict,
    current_lineage: dict,
    baseline_to_current: dict,
) -> list[tuple[str, str]]:
    names = _name_lookup(facts)
    edges = set()
    for source, target in _lineage_edges(baseline_lineage):
        mapped_source = baseline_to_current.get(source.casefold(), source)
        mapped_target = baseline_to_current.get(target.casefold(), target)
        source_name = names.get(mapped_source.casefold())
        target_name = names.get(mapped_target.casefold())
        if source_name and target_name and source_name != target_name:
            edges.add((source_name, target_name))
    for source, target in _lineage_edges(current_lineage):
        source_name = names.get(source.casefold())
        target_name = names.get(target.casefold())
        if source_name and target_name and source_name != target_name:
            edges.add((source_name, target_name))
    return sorted(edges)


def resolve_semantic_modes(
    *,
    project: str,
    project_dir: str,
    change_analysis: dict,
    baseline_lineage: dict,
    current_lineage: dict,
    base_ref: str,
    repo_root: Path,
    current_manifest: dict,
    historical_manifests: list,
) -> SemanticResolution:
    """Resolve semantic modes from baseline Git and current worktree assets."""
    repo_root = Path(repo_root)
    baseline_index = _asset_index(
        _baseline_asset_files(repo_root, project_dir, base_ref), project_dir
    )
    current_index = _asset_index(
        _current_asset_files(repo_root, project_dir), project_dir
    )
    facts, baseline_to_current = _semantic_table_facts(
        project, change_analysis, baseline_index, current_index
    )
    edges = _affected_edges(
        facts,
        baseline_lineage,
        current_lineage,
        baseline_to_current,
    )
    declarations = (current_manifest.get("verification_intent") or {}).get(
        "semantic_modes"
    ) or {}
    history = [
        item[1] if isinstance(item, tuple) else item
        for item in historical_manifests or []
    ]
    return resolve_semantic_graph(
        facts,
        edges,
        current_declarations=declarations,
        historical_manifests=history,
    )
