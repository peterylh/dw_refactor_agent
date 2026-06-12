"""Compatibility wrapper for lineage depth scoring."""

import sys as _sys

from assess.scoring import depth as _impl

_sys.modules[__name__] = _impl
