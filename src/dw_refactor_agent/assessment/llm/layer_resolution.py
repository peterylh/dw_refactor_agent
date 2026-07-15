"""Prior-aware layer resolution for table metadata writes.

The resolver treats the table inspector result as an LLM candidate and the
declared/direct-rule signals as code-owned priors. Refresh and generate share
the same flow; they differ only in which prior is available and how strong that
prior is expected to be. ODS/ADS are fixed boundaries and should normally be
filtered before table inspection; the fixed-boundary branch here is a defensive
fallback. Evidence scoring is intentionally left as a future extension point.
SQL, DDL, lineage, and naming evidence belongs in the inspector prompt; the
resolver must not reinterpret those features with benchmark-specific rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from typing_extensions import Literal

from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
)

VALID_APPLIED_LAYERS = {"ODS", "DWD", "DWS", "ADS", "DIM"}
VALID_INFERRED_LAYERS = VALID_APPLIED_LAYERS | {"OTHER"}
VALID_TABLE_TYPES = {"dimension", "fact", "other"}
FIXED_BOUNDARY_LAYERS = {"ODS", "ADS"}
DEFAULT_CANDIDATE_LAYERS = ("DWD", "DWS", "DIM")


@dataclass(frozen=True)
class LayerResolutionPolicy:
    """Policy describing the prior used by the shared resolver.

    refresh has a strong prior from existing model declarations. generate has a
    weaker prior from direct rules, except fixed ODS/ADS boundaries which are
    authoritative and should not need an LLM candidate. A usable middle-layer
    candidate is accepted without feature-based remapping.
    """

    mode: Literal["refresh", "generate"]
    candidate_layers: tuple[str, ...] = DEFAULT_CANDIDATE_LAYERS
    fixed_layer: str = ""
    fallback_source: str = "declared"
    min_llm_confidence: float = 0.5


@dataclass(frozen=True)
class LayerResolutionInput:
    """Normalized candidate and prior signals for one table.

    declared_* carries the existing model/declaration prior, while fallback_*
    carries the direct-rule or boundary prior used by cold-start generation.
    inspection_result is the LLM candidate; this module does not read catalog,
    lineage, or YAML files.
    """

    table_name: str
    declared_layer: str = ""
    declared_table_type: str = ""
    fallback_layer: str = ""
    fallback_table_type: str = ""
    inspection_result: TableInspectResult | None = None
    policy: LayerResolutionPolicy = field(
        default_factory=lambda: LayerResolutionPolicy(mode="refresh")
    )


@dataclass(frozen=True)
class LayerResolution:
    """Final prior-aware decision for a table layer.

    inferred_layer preserves the candidate/prior layer that was considered,
    while applied_layer is the layer that downstream YAML/report writing should
    use. layer_score is a reserved slot for future evidence scoring.
    """

    table_name: str
    inferred_layer: str
    applied_layer: str
    table_type: str
    source: str
    reason: str
    warnings: tuple[dict[str, Any], ...] = ()
    validation: dict[str, Any] = field(default_factory=dict)
    llm_confidence: float | None = None
    layer_score: float | None = None


def resolve_layer(payload: LayerResolutionInput) -> LayerResolution:
    """Resolve the final model layer from an LLM candidate and code priors."""
    policy = payload.policy
    fixed_layer = _normalize_layer(policy.fixed_layer)
    prior_layer = _prior_layer(payload)
    prior_table_type = _prior_table_type(payload)
    result = payload.inspection_result
    candidate_layer = _inspection_layer(result)
    candidate_table_type = (
        _normalize_table_type(result.table_type) if result is not None else ""
    )
    validation = _validation_payload(
        payload,
        fixed_layer=fixed_layer,
        prior_layer=prior_layer,
        prior_table_type=prior_table_type,
        candidate_layer=candidate_layer,
        candidate_table_type=candidate_table_type,
    )
    warnings: list[dict[str, Any]] = []

    if fixed_layer in FIXED_BOUNDARY_LAYERS:
        inferred_layer = candidate_layer or fixed_layer
        table_type = _fixed_boundary_table_type(
            prior_table_type=prior_table_type,
        )
        resolution = LayerResolution(
            table_name=payload.table_name,
            inferred_layer=inferred_layer,
            applied_layer=fixed_layer,
            table_type=table_type,
            source="fixed_boundary",
            reason=(
                f"fixed {fixed_layer} boundary prior overrides LLM candidate"
            ),
            warnings=(),
            validation=validation,
            llm_confidence=_inspection_confidence(result),
        )
        return _with_candidate_warning(resolution, policy)

    if result is not None:
        llm_layer = candidate_layer
        table_type = candidate_table_type
        llm_confidence = _inspection_confidence(result)
        if not _usable_candidate_layer(
            llm_layer,
            policy,
            confidence=llm_confidence,
        ):
            warnings.append(
                {
                    "type": "llm_layer_fallback",
                    "severity": "warning",
                    "message": (
                        "LLM candidate layer is empty, OTHER, invalid, "
                        "outside the configured candidates, or below the "
                        "minimum confidence; "
                        "falling back to the configured prior"
                    ),
                    "inferred_layer": str(
                        getattr(result, "inferred_layer", "") or ""
                    ).strip(),
                    "prior_layer": prior_layer,
                    "prior_source": policy.fallback_source,
                    "candidate_layers": _candidate_layers(policy),
                    "llm_confidence": llm_confidence,
                    "min_llm_confidence": policy.min_llm_confidence,
                }
            )
            resolution = LayerResolution(
                table_name=payload.table_name,
                inferred_layer=llm_layer or "OTHER",
                applied_layer=prior_layer,
                table_type=prior_table_type,
                source=policy.fallback_source,
                reason=(
                    "LLM candidate layer was not usable; "
                    "prior/fallback layer applied"
                ),
                warnings=tuple(warnings),
                validation=validation,
                llm_confidence=_inspection_confidence(result),
            )
            return _with_candidate_warning(resolution, policy)

        applied_layer = "DIM" if table_type == "dimension" else llm_layer
        resolution = LayerResolution(
            table_name=payload.table_name,
            inferred_layer=llm_layer,
            applied_layer=applied_layer,
            table_type=table_type or prior_table_type,
            source="table_inspector",
            reason="LLM candidate accepted by prior-aware resolver",
            warnings=(),
            validation=validation,
            llm_confidence=_inspection_confidence(result),
        )
        return _with_candidate_warning(resolution, policy)

    resolution = LayerResolution(
        table_name=payload.table_name,
        inferred_layer=prior_layer,
        applied_layer=prior_layer,
        table_type=prior_table_type,
        source=policy.fallback_source,
        reason=f"no LLM candidate; {policy.fallback_source} prior applied",
        warnings=(),
        validation=validation,
    )
    return _with_candidate_warning(resolution, policy)


def _normalize_layer(value: Any, *, allow_other: bool = True) -> str:
    layer = str(value or "").strip().upper()
    valid_layers = (
        VALID_INFERRED_LAYERS if allow_other else VALID_APPLIED_LAYERS
    )
    return layer if layer in valid_layers else ""


def _normalize_table_type(value: Any) -> str:
    table_type = str(value or "").strip().lower()
    return table_type if table_type in VALID_TABLE_TYPES else ""


def _inspection_layer(result: TableInspectResult | None) -> str:
    if result is None:
        return ""
    return _normalize_layer(result.inferred_layer)


def _inspection_confidence(result: TableInspectResult | None) -> float | None:
    if result is None:
        return None
    try:
        confidence = float(result.confidence)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return None
    return confidence


def _candidate_layers(policy: LayerResolutionPolicy) -> tuple[str, ...]:
    return tuple(
        layer
        for layer in (
            _normalize_layer(item, allow_other=False)
            for item in policy.candidate_layers
        )
        if layer
    )


def _usable_candidate_layer(
    layer: str,
    policy: LayerResolutionPolicy,
    *,
    confidence: float | None,
) -> bool:
    if not layer or layer == "OTHER":
        return False
    candidates = _candidate_layers(policy)
    if candidates and layer not in candidates:
        return False
    return confidence is not None and confidence >= policy.min_llm_confidence


def _prior_layer(payload: LayerResolutionInput) -> str:
    declared_layer = _normalize_layer(
        payload.declared_layer,
        allow_other=False,
    )
    fallback_layer = _normalize_layer(
        payload.fallback_layer,
        allow_other=False,
    )
    if payload.policy.fallback_source == "direct_rule":
        return fallback_layer or declared_layer or "OTHER"
    return declared_layer or fallback_layer or "OTHER"


def _prior_table_type(payload: LayerResolutionInput) -> str:
    declared_table_type = _normalize_table_type(payload.declared_table_type)
    fallback_table_type = _normalize_table_type(payload.fallback_table_type)
    if payload.policy.fallback_source == "direct_rule":
        return fallback_table_type or declared_table_type or "other"
    return declared_table_type or fallback_table_type or "other"


def _fixed_boundary_table_type(*, prior_table_type: str) -> str:
    return prior_table_type


def _validation_payload(
    payload: LayerResolutionInput,
    *,
    fixed_layer: str,
    prior_layer: str,
    prior_table_type: str,
    candidate_layer: str,
    candidate_table_type: str,
) -> dict[str, Any]:
    policy = payload.policy
    confidence = _inspection_confidence(payload.inspection_result)
    prior_source = (
        "fixed_boundary"
        if fixed_layer in FIXED_BOUNDARY_LAYERS
        else policy.fallback_source
    )
    validation: dict[str, Any] = {
        "mode": policy.mode,
        "fallback_source": policy.fallback_source,
        "prior": {
            "source": prior_source,
            "strength": _prior_strength(policy, fixed_layer),
            "layer": fixed_layer
            if fixed_layer in FIXED_BOUNDARY_LAYERS
            else prior_layer,
            "table_type": prior_table_type,
        },
        "candidate": {
            "source": "table_inspector"
            if payload.inspection_result is not None
            else "",
            "layer": candidate_layer,
            "table_type": candidate_table_type,
            "confidence": confidence,
        },
        "candidate_layers": _candidate_layers(policy),
        "min_llm_confidence": policy.min_llm_confidence,
    }
    if confidence is not None:
        validation["llm_confidence_below_min"] = (
            confidence < policy.min_llm_confidence
        )
    return validation


def _prior_strength(
    policy: LayerResolutionPolicy,
    fixed_layer: str,
) -> str:
    if fixed_layer in FIXED_BOUNDARY_LAYERS:
        return "fixed"
    if policy.mode == "refresh" and policy.fallback_source == "declared":
        return "strong"
    return "weak"


def _with_candidate_warning(
    resolution: LayerResolution,
    policy: LayerResolutionPolicy,
) -> LayerResolution:
    candidates = _candidate_layers(policy)
    if (
        not candidates
        or resolution.source == "fixed_boundary"
        or resolution.applied_layer in candidates
        or resolution.applied_layer == "OTHER"
    ):
        return resolution

    warning = {
        "type": "candidate_layer_mismatch",
        "severity": "warning",
        "message": "resolved layer is outside the configured candidates",
        "applied_layer": resolution.applied_layer,
        "candidate_layers": candidates,
    }
    return LayerResolution(
        table_name=resolution.table_name,
        inferred_layer=resolution.inferred_layer,
        applied_layer=resolution.applied_layer,
        table_type=resolution.table_type,
        source=resolution.source,
        reason=resolution.reason,
        warnings=resolution.warnings + (warning,),
        validation=resolution.validation,
        llm_confidence=resolution.llm_confidence,
        layer_score=resolution.layer_score,
    )
