"""Typed execution rendering for task SQL/YAML pairs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Tuple

from dw_refactor_agent.config.assets import ProjectTaskAsset

from .task_analysis import task_analysis_profile
from .task_template import (
    ContractValidationError,
    RenderBindings,
    RenderMode,
    TemplateRenderError,
    load_task_definition,
    render_task,
)
from .task_template.scoped_bindings import scope_bindings


def _mapping(
    value: object,
    *,
    path: Tuple[object, ...],
) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContractValidationError(
            "execution binding section must be a mapping",
            code="template.execution.invalid_shape",
            path=path,
        )
    if any(not isinstance(key, str) for key in value):
        raise ContractValidationError(
            "execution binding keys must be strings",
            code="template.execution.invalid_key",
            path=path,
        )
    return value


@dataclass(frozen=True)
class TaskExecutionProfile:
    """Environment-selected project roots and approved overrides."""

    environment: str
    project: Mapping[str, object] = field(default_factory=dict)
    overrides: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionTaskSql:
    """Execution SQL plus typed roots and a stable public summary."""

    sql: Optional[str]
    is_template: bool
    render_inputs: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
    )
    public_summary: Mapping[str, object] = field(default_factory=dict)
    public_session_params: Mapping[str, object] = field(default_factory=dict)


def task_execution_profile(
    project_config: Mapping[str, object],
    environment: str,
) -> TaskExecutionProfile:
    """Parse versioned environment bindings without consulting ambient env."""
    task_analysis_profile(project_config)
    templates = _mapping(
        project_config.get("task_templates"),
        path=("task_templates",),
    )
    bindings = _mapping(
        templates.get("bindings"),
        path=("task_templates", "bindings"),
    )
    parsed = {}
    for env_name, raw_profile in bindings.items():
        profile = _mapping(
            raw_profile,
            path=("task_templates", "bindings", env_name),
        )
        unknown = sorted(set(profile) - {"project", "overrides"})
        if unknown:
            raise ContractValidationError(
                f"unknown execution binding fields: {', '.join(unknown)}",
                code="template.execution.unknown_field",
                path=("task_templates", "bindings", env_name),
            )
        parsed[env_name] = TaskExecutionProfile(
            environment=env_name,
            project=dict(
                _mapping(
                    profile.get("project"),
                    path=(
                        "task_templates",
                        "bindings",
                        env_name,
                        "project",
                    ),
                )
            ),
            overrides=dict(
                _mapping(
                    profile.get("overrides"),
                    path=(
                        "task_templates",
                        "bindings",
                        env_name,
                        "overrides",
                    ),
                )
            ),
        )
    if bindings and environment not in parsed:
        raise ContractValidationError(
            f"missing execution bindings for environment {environment!r}",
            code="template.execution.missing_environment",
            path=("task_templates", "bindings", environment),
        )
    return parsed.get(
        environment, TaskExecutionProfile(environment=environment)
    )


def load_execution_task_asset(
    project: str,
    task_path: Path,
    *,
    source_file: Optional[str] = None,
) -> ProjectTaskAsset:
    """Load one explicit legacy SQL file or same-stem template pair."""
    target = Path(task_path)
    contract_candidates = [
        candidate
        for candidate in (
            target.with_suffix(".yaml"),
            target.with_suffix(".yml"),
        )
        if candidate.is_file()
    ]
    if len(contract_candidates) > 1:
        raise ContractValidationError(
            "task SQL has multiple YAML contracts",
            code="template.asset.duplicate_contract",
            path=(str(target),),
        )
    if contract_candidates:
        definition = load_task_definition(target, contract_candidates[0])
        sql_text = definition.sql_text
    else:
        try:
            sql_text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ContractValidationError(
                f"cannot read task SQL: {exc}",
                code="template.asset.sql_read_failed",
                path=(str(target),),
            ) from exc
        if "${" in sql_text:
            raise ContractValidationError(
                "task SQL contains a template marker but has no contract",
                code="template.asset.missing_contract",
                path=(str(target),),
            )
        definition = None

    return ProjectTaskAsset(
        project=project,
        role="ads" if "ads" in target.parts else "mid",
        sql_path=target,
        source_file=source_file or target.name,
        sql_text=sql_text,
        contract_path=(
            contract_candidates[0] if contract_candidates else None
        ),
        template_definition=definition,
        is_full_refresh=target.parent.name == "full_refresh",
    )


def render_task_execution_sql(
    asset: ProjectTaskAsset,
    *,
    session_params: Mapping[str, object],
    project_config: Mapping[str, object],
    environment: str,
    mode: object = RenderMode.EXECUTION,
) -> ExecutionTaskSql:
    """Render one invocation from scheduler roots and environment bindings."""
    if not asset.is_template:
        return ExecutionTaskSql(
            sql=None,
            is_template=False,
            public_session_params=dict(session_params),
        )

    definition = asset.template_definition
    if definition is None:
        raise AssertionError("template asset has no TaskDefinition")
    profile = task_execution_profile(project_config, environment)
    startup = scope_bindings(
        definition.contract.startup_params,
        session_params,
        source_prefix="invocation",
    )
    project = scope_bindings(
        definition.contract.project_params,
        profile.project,
        source_prefix="project",
    )
    parameters = definition.contract.parameters_by_name
    overrides = {
        key: value
        for key, value in profile.overrides.items()
        if key in parameters
    }
    protected_props = set()
    pending = [
        item.prop
        for item in (
            definition.contract.usage.slices
            + definition.contract.usage.partitions
        )
    ]
    pending.extend(
        item.prop
        for item in definition.contract.usage.dynamic_relations
        if item.lifecycle == "invocation"
    )
    while pending:
        prop = pending.pop()
        if prop in protected_props:
            continue
        protected_props.add(prop)
        pending.extend(parameters[prop].dependencies())
    forbidden_overrides = sorted(set(overrides) & protected_props)
    if forbidden_overrides:
        raise TemplateRenderError(
            "execution overrides cannot replace invocation-scoped usage "
            "values or their dependencies: "
            f"{', '.join(forbidden_overrides)}",
            code="template.execution.protected_override",
            path=("task_templates", "bindings", environment, "overrides"),
        )
    rendered = render_task(
        definition,
        mode=mode,
        bindings=RenderBindings(
            startup=startup,
            project=project,
            overrides=overrides,
        ),
    )
    return ExecutionTaskSql(
        sql=rendered.sql,
        is_template=True,
        render_inputs=dict(rendered.resolved_bindings),
        public_summary=rendered.normalized_summary(),
        public_session_params=dict(session_params),
    )


__all__ = [
    "ExecutionTaskSql",
    "TaskExecutionProfile",
    "load_execution_task_asset",
    "render_task_execution_sql",
    "task_execution_profile",
]
