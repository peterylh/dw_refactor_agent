"""Compile explicit routing and prefill decisions for a shadow run."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.ddl_deriver.ddl_deriver import parse_create_table
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.schedule_graph import ScheduleGraph
from dw_refactor_agent.execution.sql_executor import terminate_batch_sql_item
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
from dw_refactor_agent.refactor.verification_bindings import (
    materialize_frozen_job_invocations,
)
from dw_refactor_agent.sql.doris import (
    PartitionSelectionKind,
    parse_doris_partitions,
)
from dw_refactor_agent.sql.task_execution import load_execution_task_asset


class PrefillMode(Enum):
    PARTITIONS = "partitions"
    FULL = "full"


_RESERVED_EXECUTION_MARKER = "dw_refactor_execution_marker"


class _RecordMapping(Mapping):
    """Read-only mapping compatibility for migrated manifest records."""

    _mapping_fields: tuple[str, ...] = ()

    def __getitem__(self, key: str) -> Any:
        if key not in self._mapping_fields:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping_fields)

    def __len__(self) -> int:
        return len(self._mapping_fields)


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

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PrefillAction":
        raw_mode = value.get("mode") or PrefillMode.FULL.value
        mode = (
            raw_mode
            if isinstance(raw_mode, PrefillMode)
            else PrefillMode(raw_mode)
        )
        return cls(
            current_table=str(value.get("current_table") or ""),
            baseline_table=str(value.get("baseline_table") or ""),
            mode=mode,
            partitions=tuple(value.get("partitions") or ()),
            reason=str(value.get("reason") or ""),
        )


@dataclass(frozen=True)
class ShadowRelation(_RecordMapping):
    """Current-to-baseline identity and schema state for one relation."""

    current_table: str
    baseline_table: str
    baseline_ddl: str = ""
    schema_changed: bool = False
    phase2_qa_only: bool = False
    dropped: bool = False

    _mapping_fields = (
        "current_table",
        "baseline_table",
        "baseline_ddl",
        "schema_changed",
        "phase2_qa_only",
        "dropped",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShadowRelation":
        return cls(
            current_table=str(value.get("current_table") or ""),
            baseline_table=str(value.get("baseline_table") or ""),
            baseline_ddl=str(value.get("baseline_ddl") or ""),
            schema_changed=bool(value.get("schema_changed")),
            phase2_qa_only=bool(value.get("phase2_qa_only")),
            dropped=bool(value.get("dropped")),
        )

    def to_dict(self) -> dict:
        result = {
            "current_table": self.current_table,
            "baseline_table": self.baseline_table,
            "baseline_ddl": self.baseline_ddl,
            "schema_changed": self.schema_changed,
            "phase2_qa_only": self.phase2_qa_only,
        }
        if self.dropped:
            result["dropped"] = True
        return result


@dataclass(frozen=True)
class ShadowJob(_RecordMapping):
    """Execution routes and readiness requirements for one shadow job."""

    context: RewriteContext
    outputs: frozenset[str] = field(default_factory=frozenset)
    required_qa_tables: frozenset[str] = field(default_factory=frozenset)
    self_read: bool = False
    requires_serial_slices: bool = False

    _mapping_fields = (
        "context",
        "outputs",
        "required_qa_tables",
        "self_read",
        "requires_serial_slices",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShadowJob":
        context = value.get("context")
        if not isinstance(context, RewriteContext):
            raise TypeError("shadow job context must be RewriteContext")
        return cls(
            context=context,
            outputs=frozenset(value.get("outputs") or []),
            required_qa_tables=frozenset(
                value.get("required_qa_tables") or []
            ),
            self_read=bool(value.get("self_read")),
            requires_serial_slices=bool(value.get("requires_serial_slices")),
        )


@dataclass
class CompiledShadowManifest(_RecordMapping):
    """Aggregate root for all routing and prefill decisions of a shadow run."""

    relations: dict[str, ShadowRelation] = field(default_factory=dict)
    jobs: dict[str, ShadowJob] = field(default_factory=dict)
    prefill_actions: list[PrefillAction] = field(default_factory=list)
    prefilled_tables: set[str] = field(default_factory=set)
    writers_by_relation: dict[str, set[str]] = field(default_factory=dict)
    phase2_qa_only_tables: set[str] = field(default_factory=set)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    _mapping_fields = (
        "relations",
        "jobs",
        "prefill_actions",
        "prefilled_tables",
        "writers_by_relation",
        "phase2_qa_only_tables",
        "blockers",
        "warnings",
    )

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> "CompiledShadowManifest":
        return cls(
            relations={
                str(name): relation
                if isinstance(relation, ShadowRelation)
                else ShadowRelation.from_mapping(relation)
                for name, relation in (value.get("relations") or {}).items()
            },
            jobs={
                str(name): job
                if isinstance(job, ShadowJob)
                else ShadowJob.from_mapping(job)
                for name, job in (value.get("jobs") or {}).items()
            },
            prefill_actions=[
                action
                if isinstance(action, PrefillAction)
                else PrefillAction.from_mapping(action)
                for action in value.get("prefill_actions") or []
            ],
            prefilled_tables=set(value.get("prefilled_tables") or []),
            writers_by_relation={
                str(name): set(writers)
                for name, writers in (
                    value.get("writers_by_relation") or {}
                ).items()
            },
            phase2_qa_only_tables=set(
                value.get("phase2_qa_only_tables") or []
            ),
            blockers=list(value.get("blockers") or []),
            warnings=list(value.get("warnings") or []),
        )


def ensure_compiled_shadow_manifest(
    value: CompiledShadowManifest | Mapping[str, Any],
) -> CompiledShadowManifest:
    """Normalize compatibility mappings at the shadow execution boundary."""
    if isinstance(value, CompiledShadowManifest):
        return value
    if isinstance(value, Mapping):
        return CompiledShadowManifest.from_mapping(value)
    raise TypeError(
        "compiled shadow manifest must be CompiledShadowManifest or a mapping; "
        f"received {type(value).__name__}"
    )


@dataclass
class _ShadowJobAnalysis:
    """Intermediate compiler facts for one job."""

    index: int
    job: dict
    sql_text: str
    outputs: set[str]
    write_coverage: RowScope
    read_scopes: dict[str, RowScope]
    data_names: set[str]
    schema_names: set[str]
    existing_scopes: dict[str, RowScope]
    write_coverage_by_output: dict[str, RowScope] = field(default_factory=dict)


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


def _references_reserved_marker(sql_text: str) -> bool:
    if _RESERVED_EXECUTION_MARKER not in str(sql_text or "").casefold():
        return False
    try:
        return any(
            _canonical(table.name) == _RESERVED_EXECUTION_MARKER
            for statement in _parse_statements(sql_text)
            for table in statement.find_all(exp.Table)
        )
    except Exception:
        # A parse failure must not allow SQL mentioning the reserved marker
        # to bypass the ownership boundary.
        return True


def _typed_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        if "T" in value or " " in value:
            return datetime.fromisoformat(value)
        return date.fromisoformat(value)
    except ValueError:
        return value


def _relation_entries(
    plan: dict,
) -> tuple[dict[str, ShadowRelation], dict[str, str], set[str]]:
    baseline_ddl = plan.get("baseline_ddl") or {}
    relations = {
        _canonical(table): ShadowRelation(
            current_table=_short_name(table),
            baseline_table=_short_name(table),
            baseline_ddl=ddl,
        )
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
            previous = relations.pop(old_key, None) or ShadowRelation(
                current_table=old_name,
                baseline_table=old_name,
                baseline_ddl=baseline_ddl.get(old_name, ""),
            )
            relations[new_key] = ShadowRelation(
                current_table=new_name,
                baseline_table=previous.baseline_table or old_name,
                baseline_ddl=previous.baseline_ddl,
                schema_changed=True,
                phase2_qa_only=True,
                dropped=previous.dropped,
            )
            old_to_current[old_key] = new_key
            phase2_only.add(new_key)
        elif change_type == "CREATE":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relations[key] = ShadowRelation(
                current_table=name,
                baseline_table="",
                schema_changed=True,
                phase2_qa_only=True,
            )
            phase2_only.add(key)
        elif change_type == "ALTER":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relation = relations.setdefault(
                key,
                ShadowRelation(
                    current_table=name,
                    baseline_table=name,
                    baseline_ddl=baseline_ddl.get(name, ""),
                ),
            )
            relations[key] = replace(relation, schema_changed=True)
        elif change_type == "DROP":
            name = _short_name(change.get("table_name"))
            key = _canonical(name)
            relation = relations.setdefault(
                key,
                ShadowRelation(
                    current_table=name,
                    baseline_table=name,
                    baseline_ddl=baseline_ddl.get(name, ""),
                ),
            )
            relations[key] = replace(
                relation,
                schema_changed=True,
                dropped=True,
            )
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


def _job_runtime(job: dict, root: Path, planner):
    path = _job_file(root, job)
    if not path.is_file():
        raise ValueError(f"[{job.get('job')}] task SQL does not exist: {path}")
    try:
        spec = planner.task_spec(
            job["job"],
            path,
            model_name=job.get("target") or job["job"],
        )
    except ExecutionConfigError:
        asset = load_execution_task_asset(planner.project, path)
        if asset.is_template:
            raise
        spec = None
    invocations = materialize_frozen_job_invocations(
        job,
        planner=planner,
        root=root,
    )
    sql_texts = []
    for invocation in invocations:
        sql_text = invocation.resolved_sql
        if sql_text is None:
            invocation_path = Path(invocation.sql_path)
            if not invocation_path.is_file():
                raise ValueError(
                    f"[{job.get('job')}] invocation SQL does not exist: "
                    f"{invocation_path}"
                )
            sql_text = invocation_path.read_text(encoding=TEXT_ENCODING)
        sql_texts.append(terminate_batch_sql_item(sql_text))
    return spec, invocations, "\n".join(sql_texts)


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


def _scope_column(relation: ShadowRelation) -> str:
    ddl = relation.baseline_ddl
    if not ddl:
        return "__rows__"
    try:
        catalog = parse_doris_partitions(ddl)
    except ValueError:
        return "__rows__"
    return catalog.column or "__rows__"


def _scope_column_type(relation: ShadowRelation) -> str | None:
    column = _scope_column(relation)
    table = parse_create_table(relation.baseline_ddl)
    if table is None:
        return None
    for column_def in table.columns:
        if _canonical(column_def.name) == _canonical(column):
            return column_def.data_type
    return None


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
    relations: dict[str, ShadowRelation],
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
        column_type = _scope_column_type(relation) if relation else None
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
                        statement,
                        original_name,
                        column,
                        params,
                        column_type,
                    ).read_scope
                )
        scopes[current_name] = scope
    return scopes, data_names, schema_names


def _existing_mutation_scopes(
    sql_text: str,
    invocations,
    outputs: set[str],
    relations: dict[str, ShadowRelation],
) -> dict[str, RowScope]:
    scopes = {}
    params_sets = _analysis_param_sets(invocations)
    merge_type = getattr(exp, "Merge", None)
    for statement in _parse_statements(sql_text):
        target = _canonical(_target_table(statement))
        if target not in outputs or target not in relations:
            continue
        column = _scope_column(relations[target])
        column_type = _scope_column_type(relations[target])
        if merge_type is not None and isinstance(statement, merge_type):
            statement_scope_value = RowScope.unknown(
                column, "MERGE target rows participate in matching"
            )
        elif isinstance(statement, (exp.Update, exp.Delete)):
            statement_scope_value = RowScope.empty(column)
            for params in params_sets:
                access = statement_scope(
                    statement, target, column, params, column_type
                )
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
    current_name: str,
    relation: ShadowRelation,
    scope: RowScope,
    reasons: list[str],
) -> PrefillAction:
    ddl = relation.baseline_ddl
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
            relation.current_table,
            relation.baseline_table,
            PrefillMode.PARTITIONS,
            selection.partitions,
            reason,
        )
    return PrefillAction(
        relation.current_table,
        relation.baseline_table,
        PrefillMode.FULL,
        reason=reason,
    )


def compile_shadow_manifest(
    plan: dict, root: Path, planner
) -> CompiledShadowManifest:
    """Compile relation identity, routes, readiness, and prefill actions."""
    root = Path(root)
    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    relations, old_to_current, phase2_only = _relation_entries(plan)
    warnings = []
    blockers = []
    job_analyses: dict[str, _ShadowJobAnalysis] = {}

    if any(
        _canonical(table_name) == _RESERVED_EXECUTION_MARKER
        or _references_reserved_marker(ddl_text)
        for table_name, ddl_text in (plan.get("baseline_ddl") or {}).items()
    ):
        blockers.append(
            f"reserved relation {_RESERVED_EXECUTION_MARKER} "
            "cannot be defined by baseline DDL"
        )
    for change in plan.get("ddl_changes") or []:
        names = (
            change.get("table_name"),
            change.get("old_name"),
            change.get("new_name"),
        )
        if any(
            _canonical(name) == _RESERVED_EXECUTION_MARKER
            for name in names
            if name
        ) or _references_reserved_marker(str(change.get("sql") or "")):
            blockers.append(
                f"reserved relation {_RESERVED_EXECUTION_MARKER} "
                "cannot be changed by refactor DDL"
            )

    for index, job in enumerate(plan.get("jobs_to_run") or []):
        job_name = str(job.get("job") or "")
        spec, invocations, sql_text = _job_runtime(job, root, planner)
        if _references_reserved_marker(sql_text):
            blockers.append(
                f"{job_name}: reserved relation "
                f"{_RESERVED_EXECUTION_MARKER} cannot be read or written"
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
            relation = relations.get(output)
            if (
                relation
                and relation.dropped
                and output not in created_relations
            ):
                blockers.append(
                    f"{job_name}: write target {output} is dropped in Phase 2"
                )
        for output in outputs:
            relations.setdefault(
                output,
                ShadowRelation(
                    current_table=output,
                    baseline_table=output,
                    baseline_ddl=(plan.get("baseline_ddl") or {}).get(
                        output, ""
                    ),
                ),
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
            relation = relations.get(current_name)
            if relation and relation.dropped:
                blockers.append(
                    f"{job_name}: schema source {current_name} "
                    "is dropped in Phase 2"
                )
        job_analyses[job_name] = _ShadowJobAnalysis(
            index=index,
            job=job,
            sql_text=sql_text,
            outputs=outputs,
            write_coverage=_write_coverage(spec, invocations),
            read_scopes=read_scopes,
            data_names=data_names,
            schema_names=schema_names,
            existing_scopes=_existing_mutation_scopes(
                sql_text, invocations, outputs, relations
            ),
        )

    writers_by_relation = {}
    for job_name, analysis in job_analyses.items():
        for output in analysis.outputs:
            writers_by_relation.setdefault(output, set()).add(job_name)

    graph_data = plan.get("execution_graph")
    if isinstance(graph_data, dict):
        execution_graph = ScheduleGraph.from_dict(
            graph_data, expected_project=plan.get("project")
        )
    else:
        execution_graph = ScheduleGraph(
            str(plan.get("project") or "shadow"),
            list(job_analyses),
            {},
        )

    for job_name, analysis in job_analyses.items():
        primary_output = _canonical(analysis.job.get("target") or job_name)
        analysis.write_coverage_by_output = {
            output: (
                analysis.write_coverage
                if output == primary_output
                else RowScope.unknown(
                    _scope_column(relations[output]),
                    f"secondary output coverage from {job_name} is unknown",
                )
            )
            for output in analysis.outputs
        }

    prefill_scopes = {}
    prefill_reasons = {}

    def request_prefill(
        current_name: str, scope: RowScope, reason: str
    ) -> None:
        if scope.kind is ScopeKind.EMPTY:
            return
        relation = relations.get(current_name)
        if relation is None or not relation.baseline_table:
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
        for current_name, scope in analysis.read_scopes.items():
            if current_name not in relations:
                continue
            if relations[current_name].dropped:
                blockers.append(
                    f"{job_name}: data source {current_name} "
                    "is dropped in Phase 2"
                )
                continue
            writers = writers_by_relation.get(current_name, set())
            if job_name in writers:
                request_prefill(
                    current_name, scope, f"self-read by {job_name}"
                )
                continue
            preceding_writers = sorted(
                writer
                for writer in writers
                if execution_graph.has_path(writer, job_name)
            )
            if not preceding_writers:
                request_prefill(
                    current_name, scope, f"DDL-only source read by {job_name}"
                )
                continue
            coverage = None
            for writer in preceding_writers:
                writer_coverage = job_analyses[
                    writer
                ].write_coverage_by_output[current_name]
                coverage = (
                    writer_coverage
                    if coverage is None
                    else coverage.union(writer_coverage)
                )
            if scope.is_subset_of(coverage) is not True:
                request_prefill(
                    current_name,
                    scope,
                    f"read by {job_name} exceeds preceding writers "
                    f"{preceding_writers!r} write coverage",
                )
        for current_name, scope in analysis.existing_scopes.items():
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
        for occurrence in analyze_occurrences(analysis.sql_text):
            if occurrence.database and _canonical(occurrence.database) not in {
                _canonical(prod_db),
                _canonical(qa_db),
            }:
                continue
            original = _canonical(occurrence.table)
            current = old_to_current.get(original, original)
            relation = relations.get(current)
            display = relation.current_table if relation else occurrence.table
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
                    preceding_writers = {
                        writer
                        for writer in writers_by_relation.get(current, set())
                        if writer != job_name
                        and execution_graph.has_path(writer, job_name)
                    }
                    if preceding_writers:
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
        manifest_jobs[job_name] = ShadowJob(
            context=context,
            outputs=frozenset(analysis.outputs),
            required_qa_tables=frozenset(required_ready),
            self_read=bool(
                set(analysis.read_scopes).intersection(analysis.outputs)
            ),
            requires_serial_slices=bool(_created_relations(analysis.sql_text)),
        )

    return CompiledShadowManifest(
        relations=relations,
        jobs=manifest_jobs,
        prefill_actions=prefill_actions,
        prefilled_tables=prefilled_tables,
        writers_by_relation={
            table: set(writers)
            for table, writers in writers_by_relation.items()
        },
        phase2_qa_only_tables=phase2_only,
        blockers=sorted(set(blockers)),
        warnings=warnings,
    )


def manifest_summary(
    manifest: CompiledShadowManifest | Mapping[str, Any],
) -> dict:
    """Return the JSON-serializable part of a compiled manifest."""
    manifest = ensure_compiled_shadow_manifest(manifest)

    def route_summary(routes: dict[str, RelationRoute]) -> dict:
        return {
            name: {
                "database": route.database,
                "table": route.table,
            }
            for name, route in sorted(routes.items())
        }

    return {
        "relations": {
            name: relation.to_dict()
            for name, relation in manifest.relations.items()
        },
        "jobs": {
            name: {
                "outputs": sorted(job.outputs),
                "required_qa_tables": sorted(job.required_qa_tables),
                "self_read": job.self_read,
                "requires_serial_slices": job.requires_serial_slices,
                "routes": {
                    "write": route_summary(job.context.write_routes),
                    "schema_read": route_summary(job.context.schema_routes),
                    "data_read": route_summary(job.context.data_routes),
                },
            }
            for name, job in manifest.jobs.items()
        },
        "prefill_actions": [
            action.to_dict() for action in manifest.prefill_actions
        ],
        "prefilled_tables": sorted(manifest.prefilled_tables),
        "writers_by_relation": {
            table: sorted(writers)
            for table, writers in manifest.writers_by_relation.items()
        },
        "phase2_qa_only_tables": sorted(manifest.phase2_qa_only_tables),
        "blockers": list(manifest.blockers),
        "warnings": list(manifest.warnings),
    }
