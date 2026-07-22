"""Frozen task rendering contract for refactor verification plans."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Mapping

from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.sql.task_execution import load_execution_task_asset
from dw_refactor_agent.sql.task_template import (
    RENDERER_VERSION,
    RenderMode,
    renderer_semantics_digest,
)

TASK_RENDERING_VERSION = 1
VERIFICATION_BINDING_ENVIRONMENT = "prod"
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_REDACTED = "<redacted>"


def build_task_rendering_context(
    *, reference_date: date | None = None
) -> dict:
    """Freeze every ambient selector used to plan verification renders."""
    return {
        "version": TASK_RENDERING_VERSION,
        "mode": RenderMode.VERIFICATION.value,
        "environment": VERIFICATION_BINDING_ENVIRONMENT,
        "reference_date": (reference_date or date.today()).isoformat(),
        "renderer_semantics_digest": renderer_semantics_digest(),
    }


def validate_task_rendering_context(value: object) -> dict:
    if not isinstance(value, dict):
        raise ArtifactFormatError(
            "verification plan task_rendering must be a mapping; "
            "run analyze again"
        )
    if value.get("version") != TASK_RENDERING_VERSION:
        raise ArtifactFormatError(
            "verification plan task_rendering.version must be 1; "
            "run analyze again"
        )
    if value.get("mode") != RenderMode.VERIFICATION.value:
        raise ArtifactFormatError(
            "verification plan task_rendering.mode must be verification"
        )
    environment = value.get("environment")
    if environment != VERIFICATION_BINDING_ENVIRONMENT:
        raise ArtifactFormatError(
            "verification plan task_rendering.environment must be prod"
        )
    raw_reference_date = value.get("reference_date")
    try:
        reference_date = date.fromisoformat(str(raw_reference_date))
    except ValueError as exc:
        raise ArtifactFormatError(
            "verification plan task_rendering.reference_date must be an "
            "ISO date"
        ) from exc
    semantics_digest = value.get("renderer_semantics_digest")
    if not isinstance(semantics_digest, str) or not _DIGEST_RE.fullmatch(
        semantics_digest
    ):
        raise ArtifactFormatError(
            "verification plan task_rendering.renderer_semantics_digest "
            "must be a SHA-256 digest"
        )
    if semantics_digest != renderer_semantics_digest():
        raise ArtifactFormatError(
            "verification plan renderer semantics differ from this runtime; "
            "start a new refactor run"
        )
    return {
        "version": TASK_RENDERING_VERSION,
        "mode": RenderMode.VERIFICATION.value,
        "environment": environment,
        "reference_date": reference_date.isoformat(),
        "renderer_semantics_digest": semantics_digest,
    }


def verification_planner(
    project: str,
    root: Path,
    task_rendering: object,
) -> ExecutionPlanner:
    context = validate_task_rendering_context(task_rendering)
    return ExecutionPlanner(
        project,
        project_root=Path(root),
        db_env=context["environment"],
        render_mode=RenderMode.VERIFICATION,
        current_date=date.fromisoformat(context["reference_date"]),
    )


def _relative_path(path: Path, root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def invocation_binding_summary(
    invocation: TaskInvocation,
    *,
    root: Path,
) -> dict:
    """Return a stable public record with no sensitive binding values."""
    public = dict(invocation.public_summary)
    session_params = dict(invocation.public_session_params)
    public_bindings = public.get("public_bindings")
    is_template = isinstance(public_bindings, Mapping)
    result = {
        "file": _relative_path(invocation.sql_path, root),
        "full_refresh": bool(invocation.full_refresh),
        "strategy": invocation.strategy,
        "is_template": is_template,
        "session_params": session_params,
    }
    if not is_template:
        return result

    binding_summary = dict(public_bindings)
    result.update(
        {
            "mode": public.get("mode"),
            "renderer_version": public.get("renderer_version"),
            "template_digest": public.get("template_digest"),
            "config_digest": public.get("config_digest"),
            "binding_digest": public.get("binding_digest"),
            "render_digest": public.get("render_digest"),
            "render_inputs": {
                key: value
                for key, value in binding_summary.items()
                if value != _REDACTED
            },
            "binding_summary": binding_summary,
        }
    )
    return result


def plan_job_invocations(
    job: dict,
    *,
    planner: ExecutionPlanner,
    root: Path,
) -> list[TaskInvocation]:
    return planner.plan_shadow_job(job, project_root=Path(root))


def _plan_with_legacy_fallback(
    job: dict,
    *,
    planner: ExecutionPlanner,
    root: Path,
) -> list[TaskInvocation]:
    try:
        return plan_job_invocations(
            job,
            planner=planner,
            root=root,
        )
    except ExecutionConfigError:
        raw_path = Path(str(job.get("file") or ""))
        task_path = (
            raw_path if raw_path.is_absolute() else Path(root) / raw_path
        )
        if any(
            candidate.is_file()
            for candidate in (
                task_path.with_suffix(".yaml"),
                task_path.with_suffix(".yml"),
            )
        ):
            raise
        load_execution_task_asset(
            planner.project,
            task_path,
        )
        # Preserve legacy plan construction for projects whose old metadata
        # is incomplete. Shadow execution retains its existing planner-time
        # failure; no template binding is allowed to degrade this way.
        return [
            TaskInvocation(
                job_name=str(job.get("job") or ""),
                sql_path=task_path,
                params={},
                full_refresh=False,
                strategy="legacy_deferred",
            )
        ]


def freeze_job_invocations(
    job: dict,
    *,
    planner: ExecutionPlanner,
    root: Path,
) -> list[dict]:
    invocations = _plan_with_legacy_fallback(
        job,
        planner=planner,
        root=root,
    )
    return [
        invocation_binding_summary(invocation, root=root)
        for invocation in invocations
    ]


def materialize_frozen_job_invocations(
    job: dict,
    *,
    planner: ExecutionPlanner,
    root: Path,
) -> list[TaskInvocation]:
    expected = job.get("verification_invocations")
    if not isinstance(expected, list):
        raise ArtifactFormatError(
            f"[{job.get('job')}] verification_invocations are required; "
            "run analyze again"
        )
    invocations = _plan_with_legacy_fallback(
        job,
        planner=planner,
        root=root,
    )
    actual = [
        invocation_binding_summary(invocation, root=root)
        for invocation in invocations
    ]
    if actual != expected:
        raise ArtifactFormatError(
            f"[{job.get('job')}] rendered task bindings differ from the "
            "frozen verification plan; run analyze again"
        )
    return invocations


def validate_frozen_invocation_summary(
    value: object,
    *,
    job_name: str,
    index: int,
) -> None:
    if not isinstance(value, dict):
        raise ArtifactFormatError(
            f"[{job_name}] verification_invocations[{index}] must be a mapping"
        )
    for field in ("file", "strategy"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ArtifactFormatError(
                f"[{job_name}] verification_invocations[{index}].{field} "
                "must be a non-empty string"
            )
    if not isinstance(value.get("full_refresh"), bool):
        raise ArtifactFormatError(
            f"[{job_name}] verification_invocations[{index}].full_refresh "
            "must be boolean"
        )
    if not isinstance(value.get("is_template"), bool):
        raise ArtifactFormatError(
            f"[{job_name}] verification_invocations[{index}].is_template "
            "must be boolean"
        )
    if not isinstance(value.get("session_params"), dict):
        raise ArtifactFormatError(
            f"[{job_name}] verification_invocations[{index}].session_params "
            "must be a mapping"
        )
    if not value["is_template"]:
        return
    if value.get("mode") != RenderMode.VERIFICATION.value:
        raise ArtifactFormatError(
            f"[{job_name}] frozen template invocation mode must be "
            "verification"
        )
    if value.get("renderer_version") != RENDERER_VERSION:
        raise ArtifactFormatError(
            f"[{job_name}] frozen template invocation renderer_version "
            "does not match this runtime"
        )
    for field in (
        "template_digest",
        "config_digest",
        "binding_digest",
        "render_digest",
    ):
        digest = value.get(field)
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise ArtifactFormatError(
                f"[{job_name}] verification_invocations[{index}].{field} "
                "must be a SHA-256 digest"
            )
    for field in ("render_inputs", "binding_summary"):
        if not isinstance(value.get(field), dict):
            raise ArtifactFormatError(
                f"[{job_name}] verification_invocations[{index}].{field} "
                "must be a mapping"
            )
    if any(value == _REDACTED for value in value["render_inputs"].values()):
        raise ArtifactFormatError(
            f"[{job_name}] frozen render_inputs cannot contain redacted "
            "sentinels"
        )


__all__ = [
    "TASK_RENDERING_VERSION",
    "VERIFICATION_BINDING_ENVIRONMENT",
    "build_task_rendering_context",
    "freeze_job_invocations",
    "invocation_binding_summary",
    "materialize_frozen_job_invocations",
    "plan_job_invocations",
    "validate_frozen_invocation_summary",
    "validate_task_rendering_context",
    "verification_planner",
]
