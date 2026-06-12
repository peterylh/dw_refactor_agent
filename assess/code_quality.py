"""Compatibility wrapper for task SQL quality scoring."""

import sys as _sys

from assess.scoring import task_sql_quality as _impl

_sys.modules[__name__] = _impl
