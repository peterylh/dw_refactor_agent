"""Comparison wrapper for refactor validation plans."""

from __future__ import annotations

import json
from pathlib import Path

from config import TEXT_ENCODING


def compare_shadow_results(
    plan_path: Path,
    output_path: Path,
    *,
    method: str = "all",
    sample: int = 0,
    precision: float = 0.01,
) -> dict:
    """Compare production and QA results for a validation plan."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    from refact.verify_check import run_checks

    result = run_checks(
        plan,
        method=method,
        sample=sample,
        precision=precision,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    return result
