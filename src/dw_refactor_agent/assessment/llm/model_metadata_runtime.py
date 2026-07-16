"""Shared runtime configuration access for model metadata modules."""

from __future__ import annotations

import sys
from pathlib import Path

import dw_refactor_agent.config as config

WRITER_MODULE_NAME = "dw_refactor_agent.assessment.llm.model_metadata_writer"


def project_root() -> Path:
    """Return the active project root, honoring the legacy writer override."""
    writer_module = sys.modules.get(WRITER_MODULE_NAME)
    if writer_module is not None:
        default_root = getattr(
            writer_module,
            "_DEFAULT_PROJECT_ROOT",
            None,
        )
        writer_root = getattr(writer_module, "PROJECT_ROOT", default_root)
        if writer_root is not None and writer_root != default_root:
            return Path(writer_root)
    return Path(config.core.PROJECT_ROOT)
