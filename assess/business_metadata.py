"""Compatibility wrapper for business metadata helpers."""

import sys as _sys

from assess.project_facts import business_metadata as _impl

_sys.modules[__name__] = _impl
