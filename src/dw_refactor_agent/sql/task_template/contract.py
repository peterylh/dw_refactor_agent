"""Versioned YAML contract for strongly typed task SQL templates."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .derivation import DerivationSpec, validate_derivation
from .errors import (
    ContractValidationError,
    TaskTemplateError,
    TemplateRenderError,
)
from .types import (
    ParameterType,
    RenderSpec,
    coerce_value,
    normalize_value,
    render_sql_token,
    validate_format,
)

CONTRACT_VERSION = 1
_PROP_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_REFERENCE_RE = re.compile(r"^\$\{([a-z][a-z0-9_]*)\}$")
_MISSING = object()


class ParameterScope(Enum):
    """Where a parameter obtains its root or derived value."""

    STARTUP = "startup"
    PROJECT = "project"
    LOCAL = "local"


@dataclass(frozen=True)
class ReferenceValue:
    """An exact reference to another declared parameter."""

    prop: str

    def as_dict(self) -> str:
        return f"${{{self.prop}}}"


@dataclass(frozen=True)
class ParameterDefinition:
    """Normalized definition for one startup, project, or local parameter."""

    prop: str
    data_type: ParameterType
    scope: ParameterScope
    render: RenderSpec = RenderSpec()
    source: Optional[str] = None
    required: bool = True
    has_default: bool = False
    default: object = None
    direct: Optional[str] = None
    value: object = None
    overrideable: bool = False
    sensitive: bool = False

    def dependencies(self) -> Tuple[str, ...]:
        """Return parameters that must resolve before this definition."""
        if isinstance(self.value, ReferenceValue):
            return (self.value.prop,)
        if isinstance(self.value, DerivationSpec):
            return (self.value.source,)
        return ()

    def as_dict(self, *, redact_sensitive: bool = False) -> dict:
        result = {
            "prop": self.prop,
            "type": self.data_type.value,
            "overrideable": self.overrideable,
            "sensitive": self.sensitive,
        }
        if self.scope in {ParameterScope.STARTUP, ParameterScope.PROJECT}:
            result.update(
                {
                    "source": self.source,
                    "required": self.required,
                }
            )
            if self.has_default:
                result["default"] = (
                    "<redacted>"
                    if redact_sensitive and self.sensitive
                    else normalize_value(self.default)
                )
        else:
            result["direct"] = self.direct
            if isinstance(self.value, (ReferenceValue, DerivationSpec)):
                result["value"] = self.value.as_dict()
            else:
                result["value"] = (
                    "<redacted>"
                    if redact_sensitive and self.sensitive
                    else normalize_value(self.value)
                )
        if self.render.as_dict():
            result["render"] = self.render.as_dict()
        return result


@dataclass(frozen=True)
class VariableMapping:
    """A variable-to-existing-parameter usage declaration."""

    kind: str
    prop: str
    parameter: str

    def as_dict(self) -> dict:
        return {"prop": self.prop, "parameter": self.parameter}


@dataclass(frozen=True)
class DynamicRelationUsage:
    """Lifecycle metadata for a dynamic identifier variable."""

    prop: str
    lifecycle: str

    def as_dict(self) -> dict:
        return {"prop": self.prop, "lifecycle": self.lifecycle}


@dataclass(frozen=True)
class VariableUsage:
    """Variable-only mappings; deliberately excludes table model metadata."""

    slices: Tuple[VariableMapping, ...] = ()
    partitions: Tuple[VariableMapping, ...] = ()
    dynamic_relations: Tuple[DynamicRelationUsage, ...] = ()

    def referenced_props(self) -> Tuple[str, ...]:
        return tuple(
            item.prop
            for item in self.slices + self.partitions + self.dynamic_relations
        )

    def as_dict(self) -> dict:
        result = {}
        if self.slices:
            result["slices"] = [item.as_dict() for item in self.slices]
        if self.partitions:
            result["partitions"] = [item.as_dict() for item in self.partitions]
        if self.dynamic_relations:
            result["dynamic_relations"] = [
                item.as_dict() for item in self.dynamic_relations
            ]
        return result


@dataclass(frozen=True)
class TaskTemplateContract:
    """Fully validated version 1 task variable contract."""

    version: int
    strict: bool
    startup_params: Tuple[ParameterDefinition, ...] = ()
    project_params: Tuple[ParameterDefinition, ...] = ()
    local_params: Tuple[ParameterDefinition, ...] = ()
    usage: VariableUsage = VariableUsage()

    @property
    def parameters(self) -> Tuple[ParameterDefinition, ...]:
        return self.startup_params + self.project_params + self.local_params

    @property
    def parameter_groups(self) -> Dict[str, Tuple[ParameterDefinition, ...]]:
        result: Dict[str, Tuple[ParameterDefinition, ...]] = {}
        for item in self.parameters:
            result[item.prop] = result.get(item.prop, ()) + (item,)
        return result

    @property
    def sensitive_props(self) -> frozenset:
        sensitive = {item.prop for item in self.parameters if item.sensitive}
        changed = True
        while changed:
            changed = False
            for item in self.local_params:
                if item.prop in sensitive:
                    continue
                if any(prop in sensitive for prop in item.dependencies()):
                    sensitive.add(item.prop)
                    changed = True
        return frozenset(sensitive)

    @property
    def parameters_by_name(self) -> Dict[str, ParameterDefinition]:
        result = {}
        sensitive = self.sensitive_props
        for prop, group in self.parameter_groups.items():
            representative = next(
                (item for item in group if item.scope is ParameterScope.LOCAL),
                group[0],
            )
            result[prop] = replace(
                representative,
                overrideable=all(item.overrideable for item in group),
                sensitive=prop in sensitive,
            )
        return result

    def _as_dict(self, *, redact_sensitive: bool) -> dict:
        result = {"version": self.version, "strict": self.strict}
        sensitive = self.sensitive_props if redact_sensitive else frozenset()

        def serialize(item: ParameterDefinition) -> dict:
            effective = (
                replace(item, sensitive=True)
                if item.prop in sensitive
                else item
            )
            return effective.as_dict(redact_sensitive=redact_sensitive)

        if self.startup_params:
            result["startup_params"] = [
                serialize(item) for item in self.startup_params
            ]
        if self.project_params:
            result["project_params"] = [
                serialize(item) for item in self.project_params
            ]
        if self.local_params:
            result["local_params"] = [
                serialize(item) for item in self.local_params
            ]
        if self.usage.as_dict():
            result["usage"] = self.usage.as_dict()
        return result

    def as_dict(self) -> dict:
        return self._as_dict(redact_sensitive=False)

    def redacted_dict(self) -> dict:
        """Return a public summary with sensitive constants removed."""
        return self._as_dict(redact_sensitive=True)


def _require_mapping(
    value: object,
    *,
    path: Tuple[object, ...],
) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ContractValidationError(
            f"expected mapping, received {type(value).__name__}",
            code="template.contract.invalid_shape",
            path=path,
        )
    return value


def _reject_unknown_fields(
    value: Mapping[str, object],
    allowed: Iterable[str],
    *,
    path: Tuple[object, ...],
) -> None:
    invalid_keys = [key for key in value if not isinstance(key, str)]
    if invalid_keys:
        raise ContractValidationError(
            "mapping field names must be strings",
            code="template.contract.invalid_field_name",
            path=path,
        )
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ContractValidationError(
            f"unknown fields: {', '.join(unknown)}",
            code="template.contract.unknown_field",
            path=path,
        )


def _require_bool(
    value: object,
    *,
    field: str,
    path: Tuple[object, ...],
) -> bool:
    if not isinstance(value, bool):
        raise ContractValidationError(
            f"{field} must be boolean, received {value!r}",
            code="template.contract.invalid_boolean",
            path=path + (field,),
        )
    return value


def _parse_render(
    raw: object,
    *,
    data_type: ParameterType,
    path: Tuple[object, ...],
) -> RenderSpec:
    if raw is None:
        value: Mapping[str, object] = {}
    else:
        value = _require_mapping(raw, path=path)
    _reject_unknown_fields(
        value,
        {"input_format", "format", "item_type"},
        path=path,
    )
    input_format = None
    output_format = None
    if "input_format" in value:
        input_format = validate_format(
            value["input_format"], path=path + ("input_format",)
        )
    if "format" in value:
        output_format = validate_format(
            value["format"], path=path + ("format",)
        )
    item_type = None
    if "item_type" in value:
        item_type = ParameterType.parse(
            value["item_type"], path=path + ("item_type",)
        )
    temporal_types = {
        ParameterType.DATE,
        ParameterType.TIME,
        ParameterType.TIMESTAMP,
    }
    if (input_format or output_format) and data_type not in temporal_types:
        raise ContractValidationError(
            f"{data_type.value} does not accept date/time formats",
            code="template.contract.invalid_format",
            path=path,
        )
    if data_type is ParameterType.LIST:
        if item_type is None or item_type in {
            ParameterType.LIST,
            ParameterType.FILE,
            ParameterType.IDENTIFIER,
            ParameterType.QUALIFIED_IDENTIFIER,
        }:
            raise ContractValidationError(
                "LIST requires a scalar render.item_type",
                code="template.contract.invalid_item_type",
                path=path,
            )
    elif item_type is not None:
        raise ContractValidationError(
            f"{data_type.value} does not accept render.item_type",
            code="template.contract.invalid_item_type",
            path=path,
        )
    return RenderSpec(input_format, output_format, item_type)


def _parse_prop(value: object, *, path: Tuple[object, ...]) -> str:
    if not isinstance(value, str) or not _PROP_RE.fullmatch(value):
        raise ContractValidationError(
            f"prop must use canonical lower_snake_case, received {value!r}",
            code="template.contract.invalid_prop",
            path=path,
        )
    return value


def _parse_root_parameter(
    raw: object,
    *,
    scope: ParameterScope,
    path: Tuple[object, ...],
) -> ParameterDefinition:
    value = _require_mapping(raw, path=path)
    _reject_unknown_fields(
        value,
        {
            "prop",
            "type",
            "source",
            "required",
            "default",
            "overrideable",
            "sensitive",
            "render",
        },
        path=path,
    )
    for field in ("prop", "type", "source"):
        if field not in value:
            raise ContractValidationError(
                f"missing required field {field!r}",
                code="template.contract.missing_field",
                path=path,
            )
    prop = _parse_prop(value["prop"], path=path + ("prop",))
    data_type = ParameterType.parse(value["type"], path=path + ("type",))
    source = value["source"]
    expected_prefix = f"{scope.value}."
    if scope is ParameterScope.STARTUP:
        expected_prefix = "invocation."
    if not isinstance(source, str) or not source.startswith(expected_prefix):
        raise ContractValidationError(
            f"source must start with {expected_prefix!r}, received {source!r}",
            code="template.contract.invalid_source",
            path=path + ("source",),
        )
    source_name = source[len(expected_prefix) :]
    if not _PROP_RE.fullmatch(source_name):
        raise ContractValidationError(
            f"source name must use canonical lower_snake_case: {source!r}",
            code="template.contract.invalid_source",
            path=path + ("source",),
        )
    required = _require_bool(
        value.get("required", True), field="required", path=path
    )
    overrideable = _require_bool(
        value.get("overrideable", False), field="overrideable", path=path
    )
    sensitive = _require_bool(
        value.get("sensitive", False), field="sensitive", path=path
    )
    has_default = "default" in value
    if required and has_default:
        raise ContractValidationError(
            "required root parameter cannot also define default",
            code="template.contract.conflicting_default",
            path=path,
        )
    return ParameterDefinition(
        prop=prop,
        data_type=data_type,
        scope=scope,
        render=_parse_render(
            value.get("render"), data_type=data_type, path=path + ("render",)
        ),
        source=source,
        required=required,
        has_default=has_default,
        default=value.get("default"),
        overrideable=overrideable,
        sensitive=sensitive,
    )


def _parse_local_value(raw: object, *, path: Tuple[object, ...]) -> object:
    if isinstance(raw, str) and "${" in raw:
        match = _REFERENCE_RE.fullmatch(raw)
        if not match:
            raise ContractValidationError(
                "parameter references must be the complete value ${prop}",
                code="template.contract.invalid_reference",
                path=path,
            )
        return ReferenceValue(match.group(1))
    if not isinstance(raw, dict):
        return raw
    _reject_unknown_fields(raw, {"derive"}, path=path)
    if "derive" not in raw:
        raise ContractValidationError(
            "structured local value must contain derive",
            code="template.contract.invalid_value",
            path=path,
        )
    derive = _require_mapping(raw["derive"], path=path + ("derive",))
    _reject_unknown_fields(
        derive,
        {"from", "operation", "amount", "format", "prefix", "suffix"},
        path=path + ("derive",),
    )
    for field in ("from", "operation"):
        if field not in derive:
            raise ContractValidationError(
                f"missing required field {field!r}",
                code="template.contract.missing_field",
                path=path + ("derive",),
            )
    source = _parse_prop(derive["from"], path=path + ("derive", "from"))
    operation = str(derive["operation"])
    amount = derive.get("amount")
    if amount is not None and (
        isinstance(amount, bool) or not isinstance(amount, int)
    ):
        raise ContractValidationError(
            f"amount must be integer, received {amount!r}",
            code="template.contract.invalid_derivation",
            path=path + ("derive", "amount"),
        )
    format_name = None
    if "format" in derive:
        format_name = validate_format(
            derive["format"], path=path + ("derive", "format")
        )
    prefix = derive.get("prefix", "")
    suffix = derive.get("suffix", "")
    if not isinstance(prefix, str) or not isinstance(suffix, str):
        raise ContractValidationError(
            "derive prefix and suffix must be strings",
            code="template.contract.invalid_derivation",
            path=path + ("derive",),
        )
    spec = DerivationSpec(
        source=source,
        operation=operation,
        amount=amount,
        format_name=format_name,
        prefix=prefix,
        suffix=suffix,
    )
    validate_derivation(spec, path=path + ("derive",))
    return spec


def _parse_local_parameter(
    raw: object,
    *,
    path: Tuple[object, ...],
) -> ParameterDefinition:
    value = _require_mapping(raw, path=path)
    _reject_unknown_fields(
        value,
        {
            "prop",
            "direct",
            "type",
            "value",
            "overrideable",
            "sensitive",
            "render",
        },
        path=path,
    )
    for field in ("prop", "direct", "type", "value"):
        if field not in value:
            raise ContractValidationError(
                f"missing required field {field!r}",
                code="template.contract.missing_field",
                path=path,
            )
    if value["direct"] != "IN":
        raise ContractValidationError(
            f"v1 only accepts direct: IN, received {value['direct']!r}",
            code="template.contract.invalid_direction",
            path=path + ("direct",),
        )
    prop = _parse_prop(value["prop"], path=path + ("prop",))
    data_type = ParameterType.parse(value["type"], path=path + ("type",))
    return ParameterDefinition(
        prop=prop,
        data_type=data_type,
        scope=ParameterScope.LOCAL,
        render=_parse_render(
            value.get("render"), data_type=data_type, path=path + ("render",)
        ),
        direct="IN",
        value=_parse_local_value(value["value"], path=path + ("value",)),
        overrideable=_require_bool(
            value.get("overrideable", False),
            field="overrideable",
            path=path,
        ),
        sensitive=_require_bool(
            value.get("sensitive", False), field="sensitive", path=path
        ),
    )


def _parse_parameter_list(
    raw: object,
    *,
    scope: ParameterScope,
    path: Tuple[object, ...],
) -> Tuple[ParameterDefinition, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ContractValidationError(
            f"expected list, received {type(raw).__name__}",
            code="template.contract.invalid_shape",
            path=path,
        )
    parser = (
        _parse_local_parameter
        if scope is ParameterScope.LOCAL
        else lambda value, path: _parse_root_parameter(
            value, scope=scope, path=path
        )
    )
    return tuple(
        parser(item, path=path + (index,)) for index, item in enumerate(raw)
    )


def _parse_mapping_usage(
    raw: object,
    *,
    kind: str,
    path: Tuple[object, ...],
) -> Tuple[VariableMapping, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ContractValidationError(
            "usage entries must be lists",
            code="template.contract.invalid_shape",
            path=path,
        )
    result = []
    for index, item in enumerate(raw):
        item_path = path + (index,)
        value = _require_mapping(item, path=item_path)
        _reject_unknown_fields(value, {"prop", "parameter"}, path=item_path)
        if "prop" not in value or "parameter" not in value:
            raise ContractValidationError(
                "usage mapping requires prop and parameter",
                code="template.contract.missing_field",
                path=item_path,
            )
        prop = _parse_prop(value["prop"], path=item_path + ("prop",))
        parameter = _parse_prop(
            value["parameter"], path=item_path + ("parameter",)
        )
        result.append(VariableMapping(kind, prop, parameter))
    return tuple(result)


def _parse_dynamic_usage(
    raw: object,
    *,
    path: Tuple[object, ...],
) -> Tuple[DynamicRelationUsage, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ContractValidationError(
            "dynamic_relations must be a list",
            code="template.contract.invalid_shape",
            path=path,
        )
    result = []
    for index, item in enumerate(raw):
        item_path = path + (index,)
        value = _require_mapping(item, path=item_path)
        _reject_unknown_fields(value, {"prop", "lifecycle"}, path=item_path)
        if "prop" not in value or "lifecycle" not in value:
            raise ContractValidationError(
                "dynamic relation requires prop and lifecycle",
                code="template.contract.missing_field",
                path=item_path,
            )
        prop = _parse_prop(value["prop"], path=item_path + ("prop",))
        lifecycle = value["lifecycle"]
        if lifecycle not in {"invocation", "task"}:
            raise ContractValidationError(
                f"unsupported dynamic relation lifecycle {lifecycle!r}",
                code="template.contract.invalid_lifecycle",
                path=item_path + ("lifecycle",),
            )
        result.append(DynamicRelationUsage(prop, lifecycle))
    return tuple(result)


def _parse_usage(raw: object) -> VariableUsage:
    if raw is None:
        return VariableUsage()
    value = _require_mapping(raw, path=("usage",))
    _reject_unknown_fields(
        value,
        {"slices", "partitions", "dynamic_relations"},
        path=("usage",),
    )
    return VariableUsage(
        slices=_parse_mapping_usage(
            value.get("slices"), kind="slice", path=("usage", "slices")
        ),
        partitions=_parse_mapping_usage(
            value.get("partitions"),
            kind="partition",
            path=("usage", "partitions"),
        ),
        dynamic_relations=_parse_dynamic_usage(
            value.get("dynamic_relations"),
            path=("usage", "dynamic_relations"),
        ),
    )


def _validate_contract_graph(contract: TaskTemplateContract) -> None:
    parameters = contract.parameters_by_name
    for prop, group in contract.parameter_groups.items():
        scopes = [item.scope for item in group]
        if len(scopes) != len(set(scopes)):
            raise ContractValidationError(
                f"parameter {prop!r} is declared twice in one scope",
                code="template.contract.duplicate_prop",
                path=(prop,),
            )
        if len(group) > 1:
            if not all(item.overrideable for item in group):
                raise ContractValidationError(
                    f"parameter {prop!r} has non-overrideable candidates",
                    code="template.contract.forbidden_shadowing",
                    path=(prop,),
                )
            if any(item.data_type is not group[0].data_type for item in group):
                raise ContractValidationError(
                    f"parameter {prop!r} candidates have different types",
                    code="template.contract.conflicting_candidate",
                    path=(prop, "type"),
                )
            if any(item.render != group[0].render for item in group):
                raise ContractValidationError(
                    f"parameter {prop!r} candidates have different render rules",
                    code="template.contract.conflicting_candidate",
                    path=(prop, "render"),
                )
            if sum(item.has_default for item in group) > 1:
                raise ContractValidationError(
                    f"parameter {prop!r} has multiple defaults",
                    code="template.contract.conflicting_default",
                    path=(prop, "default"),
                )
    sources = {}
    for item in contract.startup_params + contract.project_params:
        if item.source in sources:
            raise ContractValidationError(
                f"source {item.source!r} is bound by multiple parameters",
                code="template.contract.duplicate_source",
                path=(item.prop, "source"),
            )
        sources[item.source] = item.prop
    for item in contract.local_params:
        for dependency in item.dependencies():
            if dependency not in parameters:
                raise ContractValidationError(
                    f"parameter {item.prop!r} references undeclared {dependency!r}",
                    code="template.contract.unknown_reference",
                    path=(item.prop, "value"),
                )
            source_type = parameters[dependency].data_type
            if isinstance(item.value, ReferenceValue):
                compatible_groups = (
                    {ParameterType.INTEGER, ParameterType.LONG},
                    {ParameterType.FLOAT, ParameterType.DOUBLE},
                )
                compatible = item.data_type is source_type or any(
                    {item.data_type, source_type}.issubset(group)
                    for group in compatible_groups
                )
                if not compatible:
                    raise ContractValidationError(
                        f"parameter {item.prop!r} cannot reference "
                        f"{source_type.value} parameter {dependency!r}",
                        code="template.contract.incompatible_reference",
                        path=(item.prop, "value"),
                    )
            elif isinstance(item.value, DerivationSpec):
                temporal = {ParameterType.DATE, ParameterType.TIMESTAMP}
                if source_type not in temporal:
                    raise ContractValidationError(
                        f"derivation source {dependency!r} must be temporal",
                        code="template.contract.invalid_derivation_type",
                        path=(item.prop, "value", "derive", "from"),
                    )
                if item.value.operation == "format_date":
                    formatted_targets = {
                        ParameterType.VARCHAR,
                        ParameterType.FILE,
                        ParameterType.IDENTIFIER,
                        ParameterType.QUALIFIED_IDENTIFIER,
                    }
                    if item.data_type not in formatted_targets:
                        raise ContractValidationError(
                            "format_date must target a string or identifier type",
                            code="template.contract.invalid_derivation_type",
                            path=(item.prop, "type"),
                        )
                elif item.data_type not in temporal:
                    raise ContractValidationError(
                        "date derivations must target DATE or TIMESTAMP",
                        code="template.contract.invalid_derivation_type",
                        path=(item.prop, "type"),
                    )
        if not isinstance(item.value, (ReferenceValue, DerivationSpec)):
            try:
                normalized = coerce_value(
                    item.data_type,
                    item.value,
                    render=item.render,
                    prop=item.prop,
                )
                render_sql_token(
                    item.data_type,
                    normalized,
                    render=item.render,
                    prop=item.prop,
                )
            except TemplateRenderError:
                raise ContractValidationError(
                    f"parameter {item.prop!r} has an invalid static value",
                    code="template.contract.invalid_static_value",
                    path=(item.prop, "value"),
                ) from None
    for item in contract.startup_params + contract.project_params:
        if not item.has_default:
            continue
        try:
            normalized = coerce_value(
                item.data_type,
                item.default,
                render=item.render,
                prop=item.prop,
            )
            render_sql_token(
                item.data_type,
                normalized,
                render=item.render,
                prop=item.prop,
            )
        except TemplateRenderError:
            raise ContractValidationError(
                f"parameter {item.prop!r} has an invalid default",
                code="template.contract.invalid_static_value",
                path=(item.prop, "default"),
            ) from None
    for prop in contract.usage.referenced_props():
        if prop not in parameters:
            raise ContractValidationError(
                f"usage references undeclared parameter {prop!r}",
                code="template.contract.unknown_usage",
                path=("usage", prop),
            )
    for item in contract.usage.dynamic_relations:
        data_type = parameters[item.prop].data_type
        if data_type not in {
            ParameterType.IDENTIFIER,
            ParameterType.QUALIFIED_IDENTIFIER,
        }:
            raise ContractValidationError(
                f"dynamic relation {item.prop!r} must be an identifier type",
                code="template.contract.invalid_dynamic_relation",
                path=("usage", "dynamic_relations", item.prop),
            )

    state: Dict[str, str] = {}

    def visit(prop: str, trail: Tuple[str, ...]) -> None:
        current = state.get(prop)
        if current == "done":
            return
        if current == "visiting":
            cycle = " -> ".join(trail + (prop,))
            raise ContractValidationError(
                f"parameter dependency cycle: {cycle}",
                code="template.contract.dependency_cycle",
                path=(prop,),
            )
        state[prop] = "visiting"
        for dependency in parameters[prop].dependencies():
            visit(dependency, trail + (prop,))
        state[prop] = "done"

    for prop in parameters:
        visit(prop, ())


def parse_contract(raw: object) -> TaskTemplateContract:
    """Parse and strictly validate a version 1 task template contract."""
    value = _require_mapping(raw, path=())
    _reject_unknown_fields(
        value,
        {
            "version",
            "strict",
            "startup_params",
            "project_params",
            "local_params",
            "usage",
        },
        path=(),
    )
    version = value.get("version", _MISSING)
    if isinstance(version, bool) or version != CONTRACT_VERSION:
        raise ContractValidationError(
            f"version must be {CONTRACT_VERSION}, received {version!r}",
            code="template.contract.unsupported_version",
            path=("version",),
        )
    strict = _require_bool(value.get("strict", True), field="strict", path=())
    contract = TaskTemplateContract(
        version=CONTRACT_VERSION,
        strict=strict,
        startup_params=_parse_parameter_list(
            value.get("startup_params"),
            scope=ParameterScope.STARTUP,
            path=("startup_params",),
        ),
        project_params=_parse_parameter_list(
            value.get("project_params"),
            scope=ParameterScope.PROJECT,
            path=("project_params",),
        ),
        local_params=_parse_parameter_list(
            value.get("local_params"),
            scope=ParameterScope.LOCAL,
            path=("local_params",),
        ),
        usage=_parse_usage(value.get("usage")),
    )
    _validate_contract_graph(contract)
    return contract


__all__ = [
    "CONTRACT_VERSION",
    "ContractValidationError",
    "DynamicRelationUsage",
    "ParameterDefinition",
    "ParameterScope",
    "ReferenceValue",
    "TaskTemplateContract",
    "TaskTemplateError",
    "VariableMapping",
    "VariableUsage",
    "parse_contract",
]
