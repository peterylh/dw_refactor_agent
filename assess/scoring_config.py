"""Compatibility wrapper for scoring configuration."""

import sys as _sys

from assess.scoring import config as _impl

_sys.modules[__name__] = _impl
