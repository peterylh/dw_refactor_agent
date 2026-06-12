"""Compatibility wrapper for metadata health scoring."""

import sys as _sys

from assess.scoring import metadata_health as _impl

_sys.modules[__name__] = _impl
