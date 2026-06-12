"""Compatibility wrapper for LLM context building."""

import sys as _sys

from assess.llm import context_builder as _impl

_sys.modules[__name__] = _impl
