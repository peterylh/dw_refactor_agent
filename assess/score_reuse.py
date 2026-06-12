"""Compatibility wrapper for reusability scoring."""

import sys as _sys

from assess.scoring import reuse as _impl

_sys.modules[__name__] = _impl
