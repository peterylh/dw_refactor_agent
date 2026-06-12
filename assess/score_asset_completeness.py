"""Compatibility wrapper for asset completeness scoring."""

import sys as _sys

from assess.scoring import asset_completeness as _impl

_sys.modules[__name__] = _impl
