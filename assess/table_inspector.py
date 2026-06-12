"""Compatibility wrapper for LLM table inspection."""

import sys as _sys

from assess.llm import table_inspector as _impl

_sys.modules[__name__] = _impl
