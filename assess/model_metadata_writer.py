#!/usr/bin/env python3
"""Compatibility wrapper for the LLM model metadata writer."""

import sys as _sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in _sys.path:
    _sys.path.insert(0, str(_root))

from assess.llm import model_metadata_writer as _impl

if __name__ == "__main__":
    _impl.main()
else:
    _sys.modules[__name__] = _impl
