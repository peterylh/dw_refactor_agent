"""Compatibility wrapper for project asset catalog helpers."""

import sys as _sys

from assess.project_facts import asset_catalog as _impl

_sys.modules[__name__] = _impl
