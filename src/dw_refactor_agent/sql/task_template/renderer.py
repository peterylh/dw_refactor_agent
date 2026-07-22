"""Deterministic execution, analysis, and verification SQL rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple

from .contract import (
    CONTRACT_VERSION,
    ParameterDefinition,
    ParameterScope,
    ReferenceValue,
)
from .derivation import DERIVATION_OPERATIONS, DerivationSpec, derive_value
from .errors import TemplateRenderError
from .loader import (
    TaskDefinition,
    canonical_json_bytes,
    sha256_bytes,
)
from .types import (
    ParameterType,
    coerce_value,
    normalize_value,
    render_sql_token,
)

RENDERER_VERSION = "task-template-renderer-v1"
_REDACTED = "<redacted>"
_MISSING = object()


class RenderMode(Enum):
    """Explicit render modes; none may consult ambient time or environment."""

    EXECUTION = "execution"
    ANALYSIS = "analysis"
    VERIFICATION = "verification"

    @classmethod
    def parse(cls, value: object) -> "RenderMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError as exc:
            raise TemplateRenderError(
                f"unsupported render mode {value!r}",
                code="template.render.invalid_mode",
                path=("mode",),
            ) from exc


@dataclass(frozen=True)
class RenderBindings:
    """All explicit roots and approved overrides for one invocation."""

    startup: Mapping[str, object] = field(default_factory=dict)
    project: Mapping[str, object] = field(default_factory=dict)
    overrides: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedTask:
    """Rendered SQL plus stable digests and a safe public binding summary."""

    sql: str
    mode: RenderMode
    renderer_version: str
    template_digest: str
    config_digest: str
    binding_digest: str
    render_digest: str
    public_bindings: Mapping[str, object]
    resolved_bindings: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def normalized_summary(self) -> dict:
        return {
            "mode": self.mode.value,
            "renderer_version": self.renderer_version,
            "template_digest": self.template_digest,
            "config_digest": self.config_digest,
            "binding_digest": self.binding_digest,
            "render_digest": self.render_digest,
            "public_bindings": dict(self.public_bindings),
        }


def renderer_semantics_digest() -> str:
    """Return a stable digest for persisted cache/refactor compatibility."""
    semantics = {
        "renderer_version": RENDERER_VERSION,
        "contract_version": CONTRACT_VERSION,
        "parameter_types": sorted(item.value for item in ParameterType),
        "derivation_operations": sorted(DERIVATION_OPERATIONS),
        "literal_policy": "renderer_emits_complete_sql_tokens",
        "identifier_policy": "ascii_segments_backtick_quoted",
    }
    return sha256_bytes(canonical_json_bytes(semantics))


def _validate_binding_keys(
    definitions: Tuple[ParameterDefinition, ...],
    values: Mapping[str, object],
    *,
    scope: str,
) -> None:
    allowed = set()
    for item in definitions:
        allowed.add(item.prop)
        if item.source:
            allowed.add(item.source)
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise TemplateRenderError(
            f"unknown {scope} bindings: {', '.join(unknown)}",
            code="template.render.unknown_binding",
            path=(scope,),
        )


def _bound_raw_value(
    definition: ParameterDefinition,
    values: Mapping[str, object],
) -> object:
    candidates = []
    for key in (definition.prop, definition.source):
        if key is not None and key in values:
            candidates.append((key, values[key]))
    if candidates:
        first_value = candidates[0][1]
        if any(item[1] != first_value for item in candidates[1:]):
            keys = ", ".join(item[0] for item in candidates)
            raise TemplateRenderError(
                f"conflicting values for {definition.prop!r} from {keys}",
                code="template.render.conflicting_binding",
                path=(definition.prop,),
            )
        return first_value
    return _MISSING


def _coerce_definition(
    definition: ParameterDefinition,
    raw: object,
) -> object:
    try:
        return coerce_value(
            definition.data_type,
            raw,
            render=definition.render,
            prop=definition.prop,
        )
    except TemplateRenderError as exc:
        if not definition.sensitive:
            raise
        raise TemplateRenderError(
            f"parameter {definition.prop!r} has an invalid sensitive value",
            code=exc.code,
            path=exc.path,
        ) from None


def _validate_overrides(
    parameters: Mapping[str, ParameterDefinition],
    overrides: Mapping[str, object],
) -> None:
    unknown = sorted(set(overrides) - set(parameters))
    if unknown:
        raise TemplateRenderError(
            f"unknown overrides: {', '.join(unknown)}",
            code="template.render.unknown_override",
            path=("overrides",),
        )
    forbidden = sorted(
        prop for prop in overrides if not parameters[prop].overrideable
    )
    if forbidden:
        raise TemplateRenderError(
            f"parameters are not overrideable: {', '.join(forbidden)}",
            code="template.render.forbidden_override",
            path=("overrides",),
        )


def _resolve_values(
    definition: TaskDefinition,
    bindings: RenderBindings,
) -> Dict[str, object]:
    contract = definition.contract
    parameters = contract.parameters_by_name
    _validate_binding_keys(
        contract.startup_params, bindings.startup, scope="startup"
    )
    _validate_binding_keys(
        contract.project_params, bindings.project, scope="project"
    )
    _validate_overrides(parameters, bindings.overrides)

    groups = contract.parameter_groups
    resolved: Dict[str, object] = {}
    visiting = set()

    def resolve_parameter(prop: str) -> object:
        if prop in resolved:
            return resolved[prop]
        if prop in visiting:
            raise TemplateRenderError(
                f"parameter dependency cycle reached at {prop!r}",
                code="template.render.dependency_cycle",
                path=(prop,),
            )
        item = parameters[prop]
        group = groups[prop]
        startup = next(
            (
                candidate
                for candidate in group
                if candidate.scope is ParameterScope.STARTUP
            ),
            None,
        )
        local = next(
            (
                candidate
                for candidate in group
                if candidate.scope is ParameterScope.LOCAL
            ),
            None,
        )
        project = next(
            (
                candidate
                for candidate in group
                if candidate.scope is ParameterScope.PROJECT
            ),
            None,
        )
        visiting.add(prop)
        if prop in bindings.overrides:
            raw = bindings.overrides[prop]
        else:
            raw = (
                _bound_raw_value(startup, bindings.startup)
                if startup is not None
                else _MISSING
            )
            if raw is _MISSING and local is not None:
                for dependency in local.dependencies():
                    resolve_parameter(dependency)
                if isinstance(local.value, ReferenceValue):
                    raw = resolved[local.value.prop]
                elif isinstance(local.value, DerivationSpec):
                    raw = derive_value(local.value, resolved)
                else:
                    raw = local.value
            if raw is _MISSING and project is not None:
                raw = _bound_raw_value(project, bindings.project)
            if raw is _MISSING:
                default = next(
                    (
                        candidate
                        for candidate in group
                        if candidate.has_default
                    ),
                    None,
                )
                if default is not None:
                    raw = default.default
            if raw is _MISSING:
                sources = ", ".join(
                    candidate.source
                    for candidate in group
                    if candidate.source is not None
                )
                raise TemplateRenderError(
                    f"required parameter {prop!r} has no binding from {sources}",
                    code="template.render.missing_binding",
                    path=(prop,),
                )
        value = _coerce_definition(item, raw)
        resolved[prop] = value
        visiting.remove(prop)
        return value

    for prop in parameters:
        resolve_parameter(prop)
    return resolved


def _render_sql(
    definition: TaskDefinition,
    values: Mapping[str, object],
) -> str:
    tokens = {}
    for prop in definition.placeholder_names:
        item = definition.contract.parameters_by_name[prop]
        try:
            tokens[prop] = render_sql_token(
                item.data_type,
                values[prop],
                render=item.render,
                prop=prop,
            )
        except TemplateRenderError as exc:
            if not item.sensitive:
                raise
            raise TemplateRenderError(
                f"parameter {prop!r} could not be rendered safely",
                code=exc.code,
                path=exc.path,
            ) from None
    pieces = []
    cursor = 0
    for occurrence in definition.placeholders:
        pieces.append(definition.sql_text[cursor : occurrence.start])
        pieces.append(tokens[occurrence.prop])
        cursor = occurrence.end
    pieces.append(definition.sql_text[cursor:])
    return "".join(pieces)


def render_task(
    definition: TaskDefinition,
    *,
    mode: object,
    bindings: Optional[RenderBindings] = None,
) -> RenderedTask:
    """Render a task using only explicit typed inputs and project bindings."""
    render_mode = RenderMode.parse(mode)
    actual_bindings = bindings or RenderBindings()
    values = _resolve_values(definition, actual_bindings)
    rendered_sql = _render_sql(definition, values)
    normalized_values = {
        prop: normalize_value(values[prop]) for prop in sorted(values)
    }
    binding_digest = sha256_bytes(
        canonical_json_bytes(
            {"mode": render_mode.value, "values": normalized_values}
        )
    )
    public_bindings = {
        prop: (
            _REDACTED
            if definition.contract.parameters_by_name[prop].sensitive
            else normalized_values[prop]
        )
        for prop in sorted(normalized_values)
    }
    render_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "renderer_version": RENDERER_VERSION,
                "renderer_semantics_digest": renderer_semantics_digest(),
                "template_digest": definition.template_digest,
                "config_digest": definition.contract_digest,
                "binding_digest": binding_digest,
                "sql": rendered_sql,
            }
        )
    )
    return RenderedTask(
        sql=rendered_sql,
        mode=render_mode,
        renderer_version=RENDERER_VERSION,
        template_digest=definition.template_digest,
        config_digest=definition.contract_digest,
        binding_digest=binding_digest,
        render_digest=render_digest,
        public_bindings=public_bindings,
        resolved_bindings=dict(values),
    )


__all__ = [
    "RENDERER_VERSION",
    "RenderBindings",
    "RenderMode",
    "RenderedTask",
    "render_task",
    "renderer_semantics_digest",
]
