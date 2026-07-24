"""Strongly typed, deterministic task SQL templates."""

from .contract import (
    CONTRACT_VERSION,
    ContractValidationError,
    TaskTemplateContract,
    parse_contract,
)
from .errors import TaskTemplateError, TemplateRenderError
from .loader import (
    TaskDefinition,
    build_task_definition,
    build_task_definition_from_yaml,
    load_task_definition,
)
from .renderer import (
    RENDERER_VERSION,
    RenderBindings,
    RenderedTask,
    RenderMode,
    render_task,
    renderer_semantics_digest,
)
from .types import ParameterType

__all__ = [
    "CONTRACT_VERSION",
    "RENDERER_VERSION",
    "ContractValidationError",
    "ParameterType",
    "RenderBindings",
    "RenderMode",
    "RenderedTask",
    "TaskDefinition",
    "TaskTemplateContract",
    "TaskTemplateError",
    "TemplateRenderError",
    "build_task_definition",
    "build_task_definition_from_yaml",
    "load_task_definition",
    "parse_contract",
    "render_task",
    "renderer_semantics_digest",
]
