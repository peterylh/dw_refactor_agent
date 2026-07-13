"""Read and write verification plan artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
    require_format_version,
    sha256_json,
)

_SAFE_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _validate_table_name(table_name: str) -> str:
    value = str(table_name or "")
    if not _SAFE_TABLE_NAME_RE.fullmatch(value):
        raise ValueError(f"invalid baseline DDL table name: {table_name!r}")
    return value


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def calculate_plan_fingerprint(persisted_plan: dict) -> str:
    """Hash a persisted plan while excluding its own digest field."""
    canonical_plan = deepcopy(persisted_plan)
    canonical_plan.pop("plan_fingerprint", None)
    return sha256_json(canonical_plan)


def validate_plan_fingerprint(persisted_plan: dict) -> None:
    """Reject a plan whose persisted content was edited after writing."""
    expected = persisted_plan.get("plan_fingerprint")
    actual = calculate_plan_fingerprint(persisted_plan)
    if expected != actual:
        raise ArtifactFormatError(
            "verification plan plan_fingerprint mismatch; run analyze again"
        )


def write_verification_plan(plan_path: Path, plan: dict) -> dict:
    """Externalize baseline DDL and write the persisted verification plan."""
    plan_path = Path(plan_path)
    ddl_by_table = plan.get("baseline_ddl")
    if not isinstance(ddl_by_table, dict):
        raise ValueError("verification plan baseline_ddl must be a mapping")

    ddl_text_by_table = {}
    for table_name, ddl_text in sorted(ddl_by_table.items()):
        safe_name = _validate_table_name(table_name)
        ddl_text_by_table[safe_name] = str(ddl_text or "")

    ddl_dir = plan_path.parent / "baseline_ddl"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    refs = {}
    expected_paths = set()
    for table_name, ddl_text in ddl_text_by_table.items():
        ddl_path = ddl_dir / f"{table_name}.sql"
        content = ddl_text.encode(TEXT_ENCODING)
        ddl_path.write_bytes(content)
        expected_paths.add(ddl_path)
        refs[table_name] = {
            "path": f"baseline_ddl/{table_name}.sql",
            "sha256": _sha256(content),
        }

    persisted = deepcopy(plan)
    persisted.pop("baseline_ddl", None)
    persisted["format_version"] = FORMAT_VERSION
    persisted["baseline_ddl_refs"] = refs
    persisted["plan_fingerprint"] = calculate_plan_fingerprint(persisted)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(plan_path, persisted)
    for stale_path in ddl_dir.glob("*.sql"):
        if stale_path not in expected_paths:
            stale_path.unlink()
    return persisted


def _resolved_reference_path(
    plan_path: Path, table_name: str, reference_path: str
) -> Path:
    relative_path = Path(reference_path)
    if relative_path.is_absolute():
        raise ValueError(
            f"unsafe baseline DDL path for {table_name}: {reference_path}"
        )
    plan_dir = plan_path.parent.resolve()
    resolved = (plan_dir / relative_path).resolve()
    try:
        resolved.relative_to(plan_dir)
    except ValueError:
        raise ValueError(
            f"unsafe baseline DDL path for {table_name}: {reference_path}"
        ) from None
    return resolved


def _materialize_baseline_ddl(plan_path: Path, plan: dict) -> dict:
    """Verify referenced DDL bytes and return decoded text by table."""
    plan_path = Path(plan_path)
    if "baseline_ddl" in plan:
        raise ValueError(
            "legacy verification plan contains embedded baseline_ddl; "
            "run analyze again to create referenced baseline DDL artifacts"
        )
    refs = plan.get("baseline_ddl_refs")
    if not isinstance(refs, dict):
        raise ValueError(
            "verification plan baseline_ddl_refs must be a mapping"
        )

    ddl_by_table = {}
    for raw_table_name, reference in sorted(refs.items()):
        table_name = _validate_table_name(raw_table_name)
        if not isinstance(reference, dict):
            raise ValueError(
                f"baseline DDL reference for {table_name} must be a mapping"
            )
        reference_path = reference.get("path")
        if not isinstance(reference_path, str) or not reference_path.strip():
            raise ValueError(
                f"baseline DDL reference path must be a non-empty string "
                f"for {table_name}"
            )
        expected_digest = reference.get("sha256")
        if not isinstance(expected_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_digest
        ):
            raise ValueError(
                "baseline DDL reference sha256 must be 64 lowercase hex "
                f"characters for {table_name}"
            )
        ddl_path = _resolved_reference_path(
            plan_path,
            table_name,
            reference_path,
        )
        if not ddl_path.is_file():
            raise ValueError(
                f"baseline DDL for {table_name} does not exist: "
                f"{reference_path}"
            )
        content = ddl_path.read_bytes()
        actual_digest = _sha256(content)
        if actual_digest != expected_digest:
            raise ValueError(
                f"baseline DDL for {table_name} has SHA-256 mismatch: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        try:
            ddl_by_table[table_name] = content.decode(TEXT_ENCODING)
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"baseline DDL for {table_name} is not valid {TEXT_ENCODING}: "
                f"{reference_path}"
            ) from exc

    return ddl_by_table


def load_persisted_verification_plan(plan_path: Path) -> dict:
    """Load and validate the exact persisted plan representation."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    require_format_version(plan, "verification plan")
    validate_plan_fingerprint(plan)
    _materialize_baseline_ddl(plan_path, plan)
    return plan


def load_verification_plan(plan_path: Path) -> dict:
    """Load a validated plan and materialize referenced baseline DDL."""
    plan_path = Path(plan_path)
    plan = load_persisted_verification_plan(plan_path)
    executable = deepcopy(plan)
    executable["baseline_ddl"] = _materialize_baseline_ddl(plan_path, plan)
    return executable
