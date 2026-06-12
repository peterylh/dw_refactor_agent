"""Compatibility wrapper for entity metadata helpers."""

import sys as _sys

from assess.project_facts import entity_metadata as _impl

_sys.modules[__name__] = _impl
