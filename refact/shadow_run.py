"""Shadow-run execution wrapper for refactor validation plans."""

from __future__ import annotations

import json
from pathlib import Path

from config import TEXT_ENCODING


def run_shadow_plan(
    plan_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Run or dry-run a validation plan and write a compact result."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    result = {
        "status": "dry_run" if dry_run else "not_executed",
        "plan": str(plan_path),
        "project": plan.get("project"),
        "job_count": len(plan.get("jobs_to_run") or []),
    }
    if not dry_run:
        from refact.verify_run import run_metadata

        run_metadata(plan, dry_run=False)
        result["status"] = "completed"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    return result
