"""Deterministic analysis rendering for project task SQL consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Tuple

from dw_refactor_agent.config.assets import ProjectTaskAsset

from .task_template import (
    ContractValidationError,
    RenderBindings,
    RenderMode,
    load_task_definition,
    render_task,
    renderer_semantics_digest,
)
from .task_template.loader import canonical_json_bytes, sha256_bytes
from .task_template.types import normalize_value

ANALYSIS_PROFILE_VERSION = 1


def _mapping(
    value: object, *, path: Tuple[object, ...]
) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContractValidationError(
            "analysis profile section must be a mapping",
            code="template.analysis.invalid_shape",
            path=path,
        )
    if any(not isinstance(key, str) for key in value):
        raise ContractValidationError(
            "analysis profile keys must be strings",
            code="template.analysis.invalid_key",
            path=path,
        )
    return value


@dataclass(frozen=True)
class TaskAnalysisProfile:
    """Explicit stable roots used only for static SQL analysis."""

    version: int = ANALYSIS_PROFILE_VERSION
    startup: Mapping[str, object] = field(default_factory=dict)
    project: Mapping[str, object] = field(default_factory=dict)
    overrides: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "startup": normalize_value(dict(self.startup)),
            "project": normalize_value(dict(self.project)),
            "overrides": normalize_value(dict(self.overrides)),
        }

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.as_dict()))


@dataclass(frozen=True)
class AnalysisTaskSql:
    """Parser-ready SQL and its complete deterministic cache identity."""

    sql: str
    source_file: str
    is_template: bool
    analysis_identity: Mapping[str, object]
    public_bindings: Mapping[str, object] = field(default_factory=dict)

    def normalized_summary(self) -> dict:
        return {
            "source_file": self.source_file,
            "is_template": self.is_template,
            "analysis_identity": dict(self.analysis_identity),
            "public_bindings": dict(self.public_bindings),
        }


def task_analysis_profile(
    project_config: Mapping[str, object],
) -> TaskAnalysisProfile:
    """Parse one project's versioned, environment-independent profile."""
    templates = _mapping(
        project_config.get("task_templates"),
        path=("task_templates",),
    )
    unknown_templates = sorted(
        set(templates) - {"version", "analysis", "bindings"}
    )
    if unknown_templates:
        raise ContractValidationError(
            f"unknown task_templates fields: {', '.join(unknown_templates)}",
            code="template.analysis.unknown_field",
            path=("task_templates",),
        )
    version = templates.get("version", ANALYSIS_PROFILE_VERSION)
    if isinstance(version, bool) or version != ANALYSIS_PROFILE_VERSION:
        raise ContractValidationError(
            f"task_templates.version must be {ANALYSIS_PROFILE_VERSION}",
            code="template.analysis.unsupported_version",
            path=("task_templates", "version"),
        )
    analysis = _mapping(
        templates.get("analysis"),
        path=("task_templates", "analysis"),
    )
    unknown_analysis = sorted(
        set(analysis) - {"startup", "project", "overrides"}
    )
    if unknown_analysis:
        raise ContractValidationError(
            f"unknown analysis fields: {', '.join(unknown_analysis)}",
            code="template.analysis.unknown_field",
            path=("task_templates", "analysis"),
        )
    return TaskAnalysisProfile(
        version=ANALYSIS_PROFILE_VERSION,
        startup=dict(
            _mapping(
                analysis.get("startup"),
                path=("task_templates", "analysis", "startup"),
            )
        ),
        project=dict(
            _mapping(
                analysis.get("project"),
                path=("task_templates", "analysis", "project"),
            )
        ),
        overrides=dict(
            _mapping(
                analysis.get("overrides"),
                path=("task_templates", "analysis", "overrides"),
            )
        ),
    )


def _scope_bindings(definitions, values: Mapping[str, object]) -> dict:
    allowed = set()
    for definition in definitions:
        allowed.add(definition.prop)
        if definition.source:
            allowed.add(definition.source)
    return {key: value for key, value in values.items() if key in allowed}


def resolve_task_analysis_sql(
    asset: ProjectTaskAsset,
    project_config: Mapping[str, object],
    *,
    profile: Optional[TaskAnalysisProfile] = None,
) -> AnalysisTaskSql:
    """Resolve one discovered task to stable parser-ready analysis SQL."""
    if not asset.is_template:
        sql_digest = sha256_bytes(asset.sql_text.encode("utf-8"))
        return AnalysisTaskSql(
            sql=asset.sql_text,
            source_file=asset.source_file,
            is_template=False,
            analysis_identity={
                "kind": "legacy",
                "analysis_sql_digest": sql_digest,
            },
        )

    definition = asset.template_definition
    if definition is None:
        raise AssertionError("template asset has no TaskDefinition")
    actual_profile = profile or task_analysis_profile(project_config)
    parameters = definition.contract.parameters_by_name
    rendered = render_task(
        definition,
        mode=RenderMode.ANALYSIS,
        bindings=RenderBindings(
            startup=_scope_bindings(
                definition.contract.startup_params,
                actual_profile.startup,
            ),
            project=_scope_bindings(
                definition.contract.project_params,
                actual_profile.project,
            ),
            overrides={
                key: value
                for key, value in actual_profile.overrides.items()
                if key in parameters
            },
        ),
    )
    identity = {
        "kind": "template",
        "template_digest": rendered.template_digest,
        "config_digest": rendered.config_digest,
        "binding_digest": rendered.binding_digest,
        "render_digest": rendered.render_digest,
        "analysis_sql_digest": sha256_bytes(rendered.sql.encode("utf-8")),
        "analysis_profile_digest": actual_profile.digest,
        "renderer_version": rendered.renderer_version,
        "renderer_semantics_digest": renderer_semantics_digest(),
    }
    return AnalysisTaskSql(
        sql=rendered.sql,
        source_file=asset.source_file,
        is_template=True,
        analysis_identity=identity,
        public_bindings=rendered.public_bindings,
    )


def resolve_project_tasks_analysis(
    project: str,
    *,
    include_full_refresh: bool = True,
) -> list[tuple[ProjectTaskAsset, AnalysisTaskSql]]:
    """Discover and resolve all selected project tasks in stable order."""
    import dw_refactor_agent.config as config

    project_config = config.PROJECT_CONFIG[project]
    assets = config.discover_project_tasks(
        project,
        include_full_refresh=include_full_refresh,
    )
    profile = task_analysis_profile(project_config)
    return [
        (
            asset,
            resolve_task_analysis_sql(
                asset,
                project_config,
                profile=profile,
            ),
        )
        for asset in assets
    ]


def analysis_sql_for_task_path(
    project: str,
    task_path: Path,
    *,
    resolved_tasks=None,
) -> AnalysisTaskSql:
    """Return stable analysis SQL for one project task path."""
    resolved = (
        resolved_tasks
        if resolved_tasks is not None
        else resolve_project_tasks_analysis(project)
    )
    target = Path(task_path)
    for asset, analysis_sql in resolved:
        if asset.sql_path == target:
            return analysis_sql
    raise ContractValidationError(
        "task path is not a discovered project SQL job",
        code="template.analysis.unknown_task",
        path=(str(target),),
    )


def resolve_task_path_analysis(
    project: str,
    task_path: Path,
    *,
    source_file: Optional[str] = None,
    resolved_tasks=None,
) -> AnalysisTaskSql:
    """Resolve configured or explicitly supplied task SQL for analysis.

    Compatibility entry points may receive a task directory instead of using
    project discovery. Explicit same-stem SQL/YAML pairs still use the
    project's stable analysis profile; a plain SQL file remains byte-for-byte
    legacy input.
    """
    import dw_refactor_agent.config as config

    target = Path(task_path)
    resolved = (
        resolved_tasks
        if resolved_tasks is not None
        else resolve_project_tasks_analysis(project)
    )
    target_resolved = target.resolve()
    for asset, analysis_sql in resolved:
        if asset.sql_path.resolve() == target_resolved:
            return analysis_sql

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

    role = "ads" if "ads" in target.parts else "mid"
    asset = ProjectTaskAsset(
        project=project,
        role=role,
        sql_path=target,
        source_file=source_file or target.name,
        sql_text=sql_text,
        contract_path=(
            contract_candidates[0] if contract_candidates else None
        ),
        template_definition=definition,
        is_full_refresh=target.parent.name == "full_refresh",
    )
    return resolve_task_analysis_sql(
        asset,
        config.PROJECT_CONFIG[project],
    )


__all__ = [
    "ANALYSIS_PROFILE_VERSION",
    "AnalysisTaskSql",
    "TaskAnalysisProfile",
    "analysis_sql_for_task_path",
    "resolve_project_tasks_analysis",
    "resolve_task_path_analysis",
    "resolve_task_analysis_sql",
    "task_analysis_profile",
]
