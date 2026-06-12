"""Compatibility wrapper for architecture scoring."""

import sys as _sys

from assess.scoring import architecture as _impl

_sys.modules[__name__] = _impl
