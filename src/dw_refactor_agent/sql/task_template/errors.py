"""Structured errors raised by the task SQL template subsystem."""

from __future__ import annotations

from typing import Iterable, Tuple


class TaskTemplateError(ValueError):
    """Base error with a stable machine-readable code and contract path."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: Iterable[object] = (),
    ) -> None:
        self.code = str(code)
        self.path: Tuple[object, ...] = tuple(path)
        location = "".join(
            f"[{item}]" if isinstance(item, int) else f".{item}"
            for item in self.path
        ).lstrip(".")
        detail = f"{location}: {message}" if location else message
        super().__init__(f"{self.code}: {detail}")

    def as_dict(self) -> dict:
        """Return a JSON-serializable diagnostic without hidden state."""
        return {
            "code": self.code,
            "path": list(self.path),
            "message": str(self),
        }


class ContractValidationError(TaskTemplateError):
    """Raised when task YAML violates the versioned contract."""


class TemplateRenderError(TaskTemplateError):
    """Raised when typed bindings cannot safely render a task SQL template."""
