"""Context-local compatibility bindings for split lineage modules."""

from contextvars import ContextVar
from functools import wraps
from importlib import import_module
from inspect import signature


class RuntimeBindings:
    """Bind extracted implementations to a compatibility facade.

    Calls made through the facade carry that facade in a context-local value,
    so nested helper calls can still observe facade monkeypatches. Direct calls
    to the extracted module remain usable and lazily resolve the canonical
    extractor for project-aware helpers.
    """

    def __init__(self, module_name, runtime_module):
        self._runtime_module = runtime_module
        self._runtime_var = ContextVar(
            f"{module_name}.runtime",
            default=None,
        )
        self._implementations = {}

    def runtime(self):
        runtime = self._runtime_var.get()
        if runtime is not None:
            return runtime
        return import_module(self._runtime_module)

    def install(self, namespace, names):
        for name in names:
            self._implementations[name] = namespace[name]
        for name in names:
            namespace[name] = self._dispatcher(name)

    def call(self, name, runtime, *args, **kwargs):
        """Call one implementation with a context-local facade."""
        implementation = self._implementations[name]
        token = self._runtime_var.set(runtime)
        try:
            return implementation(*args, **kwargs)
        finally:
            self._runtime_var.reset(token)

    def preserve_metadata(self, namespace, names):
        """Copy observable callable metadata without changing pickle identity."""
        for name in names:
            implementation = self._implementations[name]
            facade = namespace[name]
            facade.__doc__ = implementation.__doc__
            facade.__annotations__ = dict(
                getattr(implementation, "__annotations__", {})
            )
            facade.__signature__ = signature(implementation)

    def _dispatcher(self, name):
        implementation = self._implementations[name]

        @wraps(implementation)
        def dispatched(*args, **kwargs):
            runtime = self._runtime_var.get()
            if runtime is not None:
                candidate = getattr(runtime, name, None)
                binding = getattr(
                    candidate,
                    "__lineage_runtime_binding__",
                    None,
                )
                if candidate is not None and binding != (self, name):
                    return candidate(*args, **kwargs)
            return implementation(*args, **kwargs)

        dispatched.__lineage_runtime_binding__ = (self, name)
        return dispatched
