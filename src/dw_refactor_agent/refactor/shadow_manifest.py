"""Compile explicit routing and prefill decisions for a shadow run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.refactor.shadow_rewrite import (
    ReferenceRole,
    RelationRoute,
    RewriteContext,
    analyze_occurrences,
    unresolved_relations,
)
from dw_refactor_agent.refactor.shadow_scope import (
    RowScope,
    ScopeKind,
    statement_scope,
)
from dw_refactor_agent.sql.doris import (
    PartitionSelectionKind,
    parse_doris_partitions,
)


class PrefillMode(Enum):
    PARTITIONS = "partitions"
    FULL = "full"


@dataclass(frozen=True)
class PrefillAction:
    current_table: str
    baseline_table: str
    mode: PrefillMode
    partitions: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "current_table": self.current_table,
            "baseline_table": self.baseline_table,
            "mode": self.mode.value,
            "partitions": list(self.partitions),
            "reason": self.reason,
        }


def _canonical(value: str) -> str:
    return str(value or "").split(".")[-1].strip('`"').casefold()


def _short_name(value: str) -> str:
    return str(value or "").split(".")[-1].strip('`"')


def _target_table(statement: exp.Expression) -> str:
    target = statement.this
    if isinstance(target, exp.Schema):
        target = target.this
    return target.name if isinstance(target, exp.Table) else ""


def _parse_statements(sql_text: str) -> list[exp.Expression]:
    return [
        statement
        for statement in sqlglot.parse(
            sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
        )
        if statement is not None
    ]


def _typed_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        if "T" in value or " " in value:
            return datetime.fromisoformat(value)
        return date.fromisoformat(value)
    except ValueError:
        return value


def _relation_entries(plan: dict) -> tuple[dict, dict, set[str]]:
    baseline_ddl = plan.get("baseline_ddl") or {}
    relations = {
        _canonical(table): {
            "current_table": _short_name(table),
            "baseline_table": _short_name(table),
            "baseline_ddl": ddl,
            "schema_changed": False,
            "phase2_qa_only": False,
        }
        for table, ddl in baseline_ddl.items()
    }
    old_to_current = {}
    phase2_only = set()
    for change in plan.get("ddl_changes") or []:
        change_type = str(change.get("change_type") or "").upper()
        if change_type == "RENAME":
            old_name = _short_name(change.get("old_name"))
            new_name = _short_name(change.get("new_name"))
            old_key = _canonical(old_name)
            new_key = _canonical(new_name)
            previous = relations.pop(old_key, None) or {
                "baseline_table": old_name,
                "baseline_ddl": baseline_ddl.get(old_name, ""),
            }
            relations[new_key] = {
                **previous,
                "current_table": new_name,
                "baseline_table": previous.get("baseline_table") or old_name,
                "schema_changed": True,
                "phase2_qa_only": True,
            }
            old_to_current[old_key] = new_key
            phase2_only.add(new_key)
        elif change_type == "CREATE":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relations[key] = {
                "current_table": name,
                "baseline_table": "",
                "baseline_ddl": "",
                "schema_changed": True,
                "phase2_qa_only": True,
            }
            phase2_only.add(key)
        elif change_type == "ALTER":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relation = relations.setdefault(
                key,
                {
                    "current_table": name,
                    "baseline_table": name,
                    "baseline_ddl": baseline_ddl.get(name, ""),
                    "phase2_qa_only": False,
                },
            )
            relation["schema_changed"] = True
        elif change_type == "DROP":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relation = relations.setdefault(
                key,
                {
                    "current_table": name,
                    "baseline_table": name,
                    "baseline_ddl": baseline_ddl.get(name, ""),
                    "phase2_qa_only": False,
                },
            )
            relation["schema_changed"] = True
            relation["dropped"] = True
    for old_name in list(old_to_current):
        current_name = old_to_current[old_name]
        visited = {old_name}
        while (
            current_name in old_to_current
            and old_to_current[current_name] != current_name
            and current_name not in visited
        ):
            visited.add(current_name)
            current_name = old_to_current[current_name]
        old_to_current[old_name] = current_name
    return relations, old_to_current, phase2_only


def _job_file(root: Path, job: dict) -> Path:
    path = Path(str(job.get("file") or ""))
    return path if path.is_absolute() else root / path


def _job_runtime(job: dict, root: Path, planner, warnings: list[str]):
    path = _job_file(root, job)
    if not path.exists():
        return None, [], ""
    sql_text = path.read_text(encoding=TEXT_ENCODING)
    try:
        spec = planner.task_spec(job["job"], path)
        invocations = planner.plan_shadow_job(job, project_root=root)
    except Exception as exc:
        warnings.append(f"[{job.get('job')}] scope planning degraded: {exc}")
        return None, [], sql_text
    return spec, invocations, sql_text


def _mutation_outputs(sql_text: str, known_relations: set[str]) -> set[str]:
    outputs = set()
    created = set()
    mutation_types = (exp.Insert, exp.Update, exp.Delete)
    merge_type = getattr(exp, "Merge", None)
    if merge_type is not None:
        mutation_types = mutation_types + (merge_type,)
    for statement in _parse_statements(sql_text):
        if isinstance(statement, exp.Create):
            target = _target_table(statement)
            if target:
                created.add(_canonical(target))
        if isinstance(statement, mutation_types):
            target = _target_table(statement)
            if target:
                outputs.add(_canonical(target))
    return outputs - (created - known_relations)


def _created_relations(sql_text: str) -> set[str]:
    return {
        _canonical(_target_table(statement))
        for statement in _parse_statements(sql_text)
        if isinstance(statement, exp.Create) and _target_table(statement)
    }


def _write_coverage(spec, invocations) -> RowScope:
    if spec is None:
        return RowScope.unknown("__rows__", "execution metadata unavailable")
    column = spec.slice_column or "__rows__"
    if spec.materialized == "full":
        return RowScope.all(column)
    if not spec.slice_param or not spec.slice_column:
        return RowScope.unknown(column, "incremental slice is not declared")
    values = []
    for invocation in invocations:
        value = invocation.params.get(spec.slice_param)
        if value is not None:
            values.append(_typed_value(value))
    if not values:
        return RowScope.unknown(column, "incremental execution values missing")
    return RowScope.from_points(column, tuple(values))


def _scope_column(relation: dict) -> str:
    ddl = relation.get("baseline_ddl") or ""
    if not ddl:
        return "__rows__"
    try:
        catalog = parse_doris_partitions(ddl)
    except ValueError:
        return "__rows__"
    return catalog.column or "__rows__"


def _analysis_param_sets(invocations) -> list[dict]:
    if not invocations:
        return [{}]
    return [
        {
            **invocation.params,
            "full_refresh": 1 if invocation.full_refresh else 0,
        }
        for invocation in invocations
    ]


def _read_scopes(
    sql_text: str,
    invocations,
    relations: dict,
    old_to_current: dict,
    prod_db: str,
    qa_db: str,
) -> tuple[dict[str, RowScope], set[str], set[str]]:
    project_dbs = {_canonical(prod_db), _canonical(qa_db)}
    data_names = {
        _canonical(item.table)
        for item in analyze_occurrences(sql_text)
        if item.role is ReferenceRole.DATA_READ
        and (not item.database or _canonical(item.database) in project_dbs)
    }
    schema_names = {
        _canonical(item.table)
        for item in analyze_occurrences(sql_text)
        if item.role is ReferenceRole.SCHEMA_READ
        and (not item.database or _canonical(item.database) in project_dbs)
    }
    scopes = {}
    params_sets = _analysis_param_sets(invocations)
    for original_name in data_names:
        current_name = old_to_current.get(original_name, original_name)
        relation = relations.get(current_name)
        column = _scope_column(relation) if relation else "__rows__"
        scope = RowScope.empty(column)
        for statement in _parse_statements(sql_text):
            statement_occurrences = analyze_occurrences(
                statement.sql(dialect="doris")
            )
            if not any(
                item.role is ReferenceRole.DATA_READ
                and _canonical(item.table) == original_name
                for item in statement_occurrences
            ):
                continue
            for params in params_sets:
                scope = scope.union(
                    statement_scope(
                        statement, original_name, column, params
                    ).read_scope
                )
        scopes[current_name] = scope
    return scopes, data_names, schema_names


def _existing_mutation_scopes(
    sql_text: str,
    invocations,
    outputs: set[str],
    relations: dict,
) -> dict[str, RowScope]:
    scopes = {}
    params_sets = _analysis_param_sets(invocations)
    merge_type = getattr(exp, "Merge", None)
    for statement in _parse_statements(sql_text):
        target = _canonical(_target_table(statement))
        if target not in outputs or target not in relations:
            continue
        column = _scope_column(relations[target])
        if merge_type is not None and isinstance(statement, merge_type):
            statement_scope_value = RowScope.unknown(
                column, "MERGE target rows participate in matching"
            )
        elif isinstance(statement, (exp.Update, exp.Delete)):
            statement_scope_value = RowScope.empty(column)
            for params in params_sets:
                access = statement_scope(statement, target, column, params)
                if access.target_requires_existing:
                    statement_scope_value = statement_scope_value.union(
                        access.read_scope
                    )
        else:
            continue
        if statement_scope_value.kind is ScopeKind.EMPTY:
            continue
        previous = scopes.get(target, RowScope.empty(column))
        scopes[target] = previous.union(statement_scope_value)
    return scopes


def _prefill_action(
    current_name: str, relation: dict, scope: RowScope, reasons: list[str]
) -> PrefillAction:
    ddl = relation.get("baseline_ddl") or ""
    if not ddl:
        raise ValueError("baseline DDL is unavailable")
    try:
        selection = parse_doris_partitions(ddl).map_scope(scope)
    except ValueError:
        selection = None
    reason = "; ".join(sorted(set(reasons)))
    if (
        selection is not None
        and selection.kind is PartitionSelectionKind.PARTITIONS
    ):
        return PrefillAction(
            relation["current_table"],
            relation["baseline_table"],
            PrefillMode.PARTITIONS,
            selection.partitions,
            reason,
        )
    return PrefillAction(
        relation["current_table"],
        relation["baseline_table"],
        PrefillMode.FULL,
        reason=reason,
    )


def compile_shadow_manifest(plan: dict, root: Path, planner) -> dict:
    """Compile relation identity, routes, readiness, and prefill actions."""
    root = Path(root)
    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    relations, old_to_current, phase2_only = _relation_entries(plan)
    warnings = []
    blockers = []
    job_analyses = {}

    for index, job in enumerate(plan.get("jobs_to_run") or []):
        job_name = str(job.get("job") or "")
        spec, invocations, sql_text = _job_runtime(
            job, root, planner, warnings
        )
        unresolved = unresolved_relations(sql_text)
        if unresolved:
            blockers.append(
                f"{job_name}: unresolved relation roles: "
                f"{', '.join(sorted(set(unresolved)))}"
            )
        outputs = _mutation_outputs(sql_text, set(relations))
        outputs.add(_canonical(job.get("target") or job_name))
        outputs = {name for name in outputs if name}
        created_relations = _created_relations(sql_text)
        for output in outputs:
            if (relations.get(output) or {}).get(
                "dropped"
            ) and output not in created_relations:
                blockers.append(
                    f"{job_name}: write target {output} is dropped in Phase 2"
                )
        for output in outputs:
            relations.setdefault(
                output,
                {
                    "current_table": output,
                    "baseline_table": output,
                    "baseline_ddl": (plan.get("baseline_ddl") or {}).get(
                        output, ""
                    ),
                    "schema_changed": False,
                    "phase2_qa_only": False,
                },
            )
        read_scopes, data_names, schema_names = _read_scopes(
            sql_text,
            invocations,
            relations,
            old_to_current,
            prod_db,
            qa_db,
        )
        for original_name in schema_names:
            current_name = old_to_current.get(original_name, original_name)
            if (relations.get(current_name) or {}).get("dropped"):
                blockers.append(
                    f"{job_name}: schema source {current_name} "
                    "is dropped in Phase 2"
                )
        job_analyses[job_name] = {
            "index": index,
            "job": job,
            "sql_text": sql_text,
            "outputs": outputs,
            "write_coverage": _write_coverage(spec, invocations),
            "read_scopes": read_scopes,
            "data_names": data_names,
            "schema_names": schema_names,
            "existing_scopes": _existing_mutation_scopes(
                sql_text, invocations, outputs, relations
            ),
        }

    producers = {}
    for job_name, analysis in job_analyses.items():
        for output in analysis["outputs"]:
            previous = producers.setdefault(output, job_name)
            if previous != job_name:
                blockers.append(
                    f"{output}: multiple producer jobs: {previous}, {job_name}"
                )

    for job_name, analysis in job_analyses.items():
        primary_output = _canonical(analysis["job"].get("target") or job_name)
        primary_coverage = analysis.pop("write_coverage")
        analysis["write_coverage_by_output"] = {
            output: (
                primary_coverage
                if output == primary_output
                else RowScope.unknown(
                    _scope_column(relations[output]),
                    f"secondary output coverage from {job_name} is unknown",
                )
            )
            for output in analysis["outputs"]
        }

    prefill_scopes = {}
    prefill_reasons = {}

    def request_prefill(
        current_name: str, scope: RowScope, reason: str
    ) -> None:
        if scope.kind is ScopeKind.EMPTY:
            return
        relation = relations.get(current_name)
        if relation is None or not relation.get("baseline_table"):
            blockers.append(
                f"{current_name}: data is required but no baseline table exists ({reason})"
            )
            return
        previous = prefill_scopes.get(current_name)
        prefill_scopes[current_name] = (
            scope if previous is None else previous.union(scope)
        )
        prefill_reasons.setdefault(current_name, []).append(reason)

    for job_name, analysis in job_analyses.items():
        for current_name, scope in analysis["read_scopes"].items():
            if current_name not in relations:
                continue
            if relations[current_name].get("dropped"):
                blockers.append(
                    f"{job_name}: data source {current_name} "
                    "is dropped in Phase 2"
                )
                continue
            producer = producers.get(current_name)
            if producer == job_name:
                request_prefill(
                    current_name, scope, f"self-read by {job_name}"
                )
                continue
            if producer is None:
                request_prefill(
                    current_name, scope, f"DDL-only source read by {job_name}"
                )
                continue
            producer_analysis = job_analyses[producer]
            coverage = producer_analysis["write_coverage_by_output"][
                current_name
            ]
            if scope.is_subset_of(coverage) is not True:
                request_prefill(
                    current_name,
                    scope,
                    f"read by {job_name} exceeds {producer} write coverage",
                )
        for current_name, scope in analysis["existing_scopes"].items():
            request_prefill(
                current_name,
                scope,
                f"existing target rows are mutated by {job_name}",
            )

    prefill_actions = []
    for current_name in sorted(prefill_scopes):
        scope = prefill_scopes[current_name]
        if scope.kind is ScopeKind.EMPTY:
            continue
        prefill_actions.append(
            _prefill_action(
                current_name,
                relations[current_name],
                scope,
                prefill_reasons[current_name],
            )
        )
    prefilled_tables = {
        _canonical(action.current_table) for action in prefill_actions
    }

    manifest_jobs = {}
    selected = set(relations)
    for job_name, analysis in job_analyses.items():
        write_routes = {}
        schema_routes = {}
        data_routes = {}
        required_ready = set()
        for occurrence in analyze_occurrences(analysis["sql_text"]):
            if occurrence.database and _canonical(occurrence.database) not in {
                _canonical(prod_db),
                _canonical(qa_db),
            }:
                continue
            original = _canonical(occurrence.table)
            current = old_to_current.get(original, original)
            relation = relations.get(current)
            display = (
                relation["current_table"] if relation else occurrence.table
            )
            if occurrence.role is ReferenceRole.WRITE:
                write_routes[original] = RelationRoute(qa_db, display)
            elif occurrence.role is ReferenceRole.SCHEMA_READ:
                schema_routes[original] = (
                    RelationRoute(qa_db, display)
                    if current in selected
                    else RelationRoute(prod_db, occurrence.table)
                )
            elif occurrence.role is ReferenceRole.DATA_READ:
                if current in selected:
                    data_routes[original] = RelationRoute(qa_db, display)
                    producer = producers.get(current)
                    if producer is not None and producer != job_name:
                        required_ready.add(current)
                else:
                    data_routes[original] = RelationRoute(
                        prod_db, occurrence.table
                    )
        context = RewriteContext(
            prod_db=prod_db,
            qa_db=qa_db,
            write_routes=write_routes,
            schema_routes=schema_routes,
            data_routes=data_routes,
            selected_tables=selected,
            qa_ready_tables=set(),
            required_qa_tables=required_ready,
            current_job=job_name,
            strict=True,
        )
        manifest_jobs[job_name] = {
            "context": context,
            "outputs": set(analysis["outputs"]),
            "required_qa_tables": required_ready,
            "self_read": bool(
                set(analysis["read_scopes"]).intersection(analysis["outputs"])
            ),
        }

    return {
        "relations": relations,
        "jobs": manifest_jobs,
        "prefill_actions": prefill_actions,
        "prefilled_tables": prefilled_tables,
        "producers": dict(producers),
        "phase2_qa_only_tables": phase2_only,
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
    }


def manifest_summary(manifest: dict) -> dict:
    """Return the JSON-serializable part of a compiled manifest."""

    def route_summary(routes: dict[str, RelationRoute]) -> dict:
        return {
            name: {
                "database": route.database,
                "table": route.table,
            }
            for name, route in sorted(routes.items())
        }

    return {
        "relations": manifest.get("relations", {}),
        "jobs": {
            name: {
                "outputs": sorted(job.get("outputs") or []),
                "required_qa_tables": sorted(
                    job.get("required_qa_tables") or []
                ),
                "self_read": bool(job.get("self_read")),
                "routes": {
                    "write": route_summary(job["context"].write_routes),
                    "schema_read": route_summary(job["context"].schema_routes),
                    "data_read": route_summary(job["context"].data_routes),
                },
            }
            for name, job in (manifest.get("jobs") or {}).items()
        },
        "prefill_actions": [
            action.to_dict()
            for action in manifest.get("prefill_actions") or []
        ],
        "prefilled_tables": sorted(manifest.get("prefilled_tables") or []),
        "producers": dict(manifest.get("producers") or {}),
        "phase2_qa_only_tables": sorted(
            manifest.get("phase2_qa_only_tables") or []
        ),
        "blockers": list(manifest.get("blockers") or []),
        "warnings": list(manifest.get("warnings") or []),
    }
