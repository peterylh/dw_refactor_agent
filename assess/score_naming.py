"""Compatibility wrapper for naming scoring."""

import sys as _sys

from assess.scoring import naming as _impl

_sys.modules[__name__] = _impl
