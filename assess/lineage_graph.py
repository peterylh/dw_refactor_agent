"""Compatibility wrapper for table-level lineage graph helpers."""

import sys as _sys

from lineage import table_graph as _impl

_sys.modules[__name__] = _impl
