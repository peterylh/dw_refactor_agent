"""Read and write verification plan artifacts."""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_bytes,
    atomic_write_json,
    read_json_object,
    require_format_version,
    sha256_json,
)
from dw_refactor_agent.refactor.qa_pool import validate_qa_identifier
from dw_refactor_agent.refactor.session import load_manifest
from dw_refactor_agent.refactor.workspace_snapshot import workspace_fingerprint

_SAFE_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class StalePlanError(ArtifactFormatError):
    """Raised when the current workspace no longer matches an analysis."""


@dataclass(frozen=True)
class FreshPlanBundle:
    """One validated executable plan bound to its analyzed asset root."""

    root: Path
    plan: dict


_ANALYSIS_INPUT_NAMES = (
    "baseline_lineage",
    "current_lineage",
    "change_analysis",
    "manifest_context",
    "verification_intent",
)


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


def _manifest_analysis_context(manifest: dict) -> dict:
    """Return immutable run context separately from mutable user intent."""
    return {
        key: value
        for key, value in manifest.items()
        if key != "verification_intent"
    }


def analysis_input_fingerprints(
    *,
    manifest: dict,
    baseline_lineage: dict,
    current_lineage: dict,
    change_analysis: dict,
) -> dict:
    """Fingerprint every persisted input used by semantic lightweight replan."""
    return {
        "baseline_lineage": sha256_json(baseline_lineage),
        "current_lineage": sha256_json(current_lineage),
        "change_analysis": sha256_json(change_analysis),
        "manifest_context": sha256_json(_manifest_analysis_context(manifest)),
        "verification_intent": sha256_json(
            manifest.get("verification_intent") or {}
        ),
    }


def validate_analysis_input_fingerprints(
    snapshot: dict,
    *,
    manifest: dict,
    baseline_lineage: dict,
    current_lineage: dict,
    change_analysis: dict,
    include_intent: bool = True,
) -> None:
    """Reject missing, malformed, or changed inputs from one analysis."""
    expected = snapshot.get("analysis_inputs")
    if not isinstance(expected, dict):
        raise ArtifactFormatError(
            "verification plan analysis_snapshot.analysis_inputs is required; "
            "run analyze again"
        )
    actual = analysis_input_fingerprints(
        manifest=manifest,
        baseline_lineage=baseline_lineage,
        current_lineage=current_lineage,
        change_analysis=change_analysis,
    )
    names = _ANALYSIS_INPUT_NAMES
    if not include_intent:
        names = tuple(name for name in names if name != "verification_intent")
    for name in names:
        digest = expected.get(name)
        if not isinstance(digest, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", digest
        ):
            raise ArtifactFormatError(
                "verification plan analysis input fingerprint is missing or "
                f"invalid: {name}; run analyze again"
            )
        if digest != actual[name]:
            if name == "verification_intent":
                message = "semantic intent changed after plan publication"
            else:
                message = f"analysis input changed after analyze: {name}"
            raise StalePlanError(f"stale_plan: {message}; run analyze again")


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
        content = ddl_text.encode(TEXT_ENCODING)
        content_digest = _sha256(content)
        ddl_path = ddl_dir / f"{table_name}.{content_digest}.sql"
        atomic_write_bytes(ddl_path, content)
        expected_paths.add(ddl_path)
        refs[table_name] = {
            "path": f"baseline_ddl/{ddl_path.name}",
            "sha256": content_digest,
        }

    persisted = deepcopy(plan)
    persisted.pop("baseline_ddl", None)
    persisted["format_version"] = FORMAT_VERSION
    persisted["baseline_ddl_refs"] = refs
    persisted["plan_fingerprint"] = calculate_plan_fingerprint(persisted)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(plan_path, persisted)
    for downstream_name in ("shadow_run_result.json", "compare_result.json"):
        downstream_path = plan_path.parent / downstream_name
        if downstream_path.exists():
            downstream_path.unlink()
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


def _validate_persisted_plan_schema(plan: dict) -> None:
    for field in ("run_id", "project", "project_db", "qa_db"):
        value = plan.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ArtifactFormatError(
                f"verification plan {field} must be a non-empty string"
            )
    pool = plan.get("qa_database_pool")
    if not isinstance(pool, list) or not pool:
        raise ArtifactFormatError(
            "verification plan qa_database_pool must be a non-empty list"
        )
    try:
        normalized_pool = [validate_qa_identifier(value) for value in pool]
    except ValueError as exc:
        raise ArtifactFormatError(
            f"verification plan qa_database_pool is invalid: {exc}"
        ) from exc
    canonical_pool = [value.casefold() for value in normalized_pool]
    if len(canonical_pool) != len(set(canonical_pool)):
        raise ArtifactFormatError(
            "verification plan qa_database_pool contains duplicate names"
        )
    if plan["qa_db"].casefold() not in set(canonical_pool):
        raise ArtifactFormatError(
            "verification plan qa_db must be a member of qa_database_pool"
        )
    for field in ("ddl_changes", "jobs_to_run"):
        if not isinstance(plan.get(field), list):
            raise ArtifactFormatError(
                f"verification plan {field} must be a list"
            )
    verification = plan.get("verification")
    if not isinstance(verification, dict):
        raise ArtifactFormatError(
            "verification plan verification must be a mapping"
        )
    if not isinstance(verification.get("checks"), list):
        raise ArtifactFormatError(
            "verification plan verification.checks must be a list"
        )
    if not isinstance(plan.get("analysis_snapshot"), dict):
        raise ArtifactFormatError(
            "verification plan analysis_snapshot must be a mapping"
        )


def load_persisted_verification_plan(plan_path: Path) -> dict:
    """Load and validate the exact persisted plan representation."""
    plan_path = Path(plan_path)
    plan = read_json_object(plan_path, "verification plan")
    require_format_version(plan, "verification plan")
    validate_plan_fingerprint(plan)
    try:
        _materialize_baseline_ddl(plan_path, plan)
    except ArtifactFormatError:
        raise
    except ValueError as exc:
        raise ArtifactFormatError(
            f"invalid verification plan {plan_path}: {exc}"
        ) from exc
    _validate_persisted_plan_schema(plan)
    return plan


def _materialize_validated_plan(plan_path: Path, persisted: dict) -> dict:
    """Materialize DDL from one already validated persisted plan snapshot."""
    plan_path = Path(plan_path)
    executable = deepcopy(persisted)
    try:
        executable["baseline_ddl"] = _materialize_baseline_ddl(
            plan_path, persisted
        )
    except ArtifactFormatError:
        raise
    except ValueError as exc:
        raise ArtifactFormatError(
            f"invalid verification plan {plan_path}: {exc}"
        ) from exc
    return executable


def load_verification_plan(plan_path: Path) -> dict:
    """Load a validated plan and materialize referenced baseline DDL."""
    plan_path = Path(plan_path)
    persisted = load_persisted_verification_plan(plan_path)
    return _materialize_validated_plan(plan_path, persisted)


def require_fresh_plan(
    plan_path: Path,
    *,
    root: Path,
    project: str,
    manifest: dict | None = None,
) -> dict:
    """Validate the plan, analyzed workspace, and every persisted input."""
    plan_path = Path(plan_path).resolve()
    persisted = load_persisted_verification_plan(plan_path)
    if persisted.get("project") != project:
        raise ArtifactFormatError(
            "verification plan project does not match the selected run"
        )
    snapshot = persisted.get("analysis_snapshot")
    if not isinstance(snapshot, dict):
        raise ArtifactFormatError(
            "verification plan analysis_snapshot is required; run analyze again"
        )
    expected = snapshot.get("workspace_fingerprint")
    if not isinstance(expected, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", expected
    ):
        raise ArtifactFormatError(
            "verification plan analysis_snapshot.workspace_fingerprint is "
            "required; run analyze again"
        )
    actual = workspace_fingerprint(Path(root), project)
    if expected != actual:
        raise StalePlanError(
            "stale_plan: workspace changed after analyze; run analyze again"
        )

    manifest_path = plan_path.parent.parent / "manifest.json"
    manifest = manifest or load_manifest(manifest_path)
    if manifest.get("project") != project:
        raise ArtifactFormatError(
            "manifest project does not match the verification plan"
        )
    verification_rel = manifest["artifacts"].get("verification_plan")
    if verification_rel is None:
        raise ArtifactFormatError(
            "manifest.artifacts.verification_plan is required"
        )
    declared_plan_path = (manifest_path.parent / verification_rel).resolve()
    if declared_plan_path != plan_path:
        raise ArtifactFormatError(
            "verification plan path does not match its run manifest"
        )

    inputs = {}
    for artifact_key in (
        "baseline_lineage",
        "current_lineage",
        "change_analysis",
    ):
        relative_path = manifest["artifacts"].get(artifact_key)
        if relative_path is None:
            raise ArtifactFormatError(
                f"manifest.artifacts.{artifact_key} is required"
            )
        inputs[artifact_key] = read_json_object(
            manifest_path.parent / relative_path,
            artifact_key.replace("_", " "),
        )
    validate_analysis_input_fingerprints(
        snapshot,
        manifest=manifest,
        baseline_lineage=inputs["baseline_lineage"],
        current_lineage=inputs["current_lineage"],
        change_analysis=inputs["change_analysis"],
    )
    return persisted


def require_fresh_plan_bundle(plan_path: Path) -> FreshPlanBundle:
    """Return one executable plan snapshot after enforcing bundle freshness."""
    plan_path = Path(plan_path).resolve()
    manifest = load_manifest(plan_path.parent.parent / "manifest.json")
    persisted = require_fresh_plan(
        plan_path,
        root=Path(manifest["root"]).expanduser().resolve(),
        project=manifest["project"],
        manifest=manifest,
    )
    return FreshPlanBundle(
        root=Path(manifest["root"]).expanduser().resolve(),
        plan=_materialize_validated_plan(plan_path, persisted),
    )
