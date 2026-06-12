"""Compatibility wrapper for shared scoring utilities."""

import sys as _sys

from assess.scoring import utils as _impl

_sys.modules[__name__] = _impl
