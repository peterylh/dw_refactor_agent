"""Prior-aware layer resolution for table metadata writes.

The resolver treats the table inspector result as an LLM candidate and the
declared/direct-rule signals as code-owned priors. Refresh and generate share
the same flow; they differ only in which prior is available and how strong that
prior is expected to be. ODS/ADS are fixed boundaries and should normally be
filtered before table inspection; the fixed-boundary branch here is a defensive
fallback. Evidence scoring is intentionally left as a future extension point.
"""

from __future__ import annotations

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
    authoritative and should not need an LLM candidate. When a candidate exists,
    it is resolved by code rather than applied directly.
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
        if not _usable_candidate_layer(llm_layer, policy):
            remapped = _remap_generate_boundary_candidate(
                payload,
                llm_layer=llm_layer,
                table_type=table_type,
                validation=validation,
            )
            if remapped is not None:
                return _with_candidate_warning(remapped, policy)
            warnings.append(
                {
                    "type": "llm_layer_fallback",
                    "severity": "warning",
                    "message": (
                        "LLM candidate layer is empty, OTHER, invalid, "
                        "or outside the configured candidates; "
                        "falling back to the configured prior"
                    ),
                    "inferred_layer": str(
                        getattr(result, "inferred_layer", "") or ""
                    ).strip(),
                    "prior_layer": prior_layer,
                    "prior_source": policy.fallback_source,
                    "candidate_layers": _candidate_layers(policy),
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

        preserved = _preserve_generate_dwd_intermediate_prior(
            payload,
            llm_layer=llm_layer,
            table_type=table_type,
            prior_layer=prior_layer,
            prior_table_type=prior_table_type,
            validation=validation,
        )
        if preserved is not None:
            return _with_candidate_warning(preserved, policy)

        dim_surrogate = _remap_generate_dim_surrogate_candidate(
            payload,
            llm_layer=llm_layer,
            table_type=table_type,
            prior_layer=prior_layer,
            validation=validation,
        )
        if dim_surrogate is not None:
            return _with_candidate_warning(dim_surrogate, policy)

        dws_snapshot = _remap_generate_dws_snapshot_candidate(
            payload,
            llm_layer=llm_layer,
            table_type=table_type,
            prior_layer=prior_layer,
            validation=validation,
        )
        if dws_snapshot is not None:
            return _with_candidate_warning(dws_snapshot, policy)

        dws_entity_metric = _remap_generate_dws_entity_metric_candidate(
            payload,
            llm_layer=llm_layer,
            table_type=table_type,
            prior_layer=prior_layer,
            validation=validation,
        )
        if dws_entity_metric is not None:
            return _with_candidate_warning(dws_entity_metric, policy)

        dim_snapshot = _remap_generate_dim_entity_snapshot_candidate(
            payload,
            llm_layer=llm_layer,
            table_type=table_type,
            prior_layer=prior_layer,
            validation=validation,
        )
        if dim_snapshot is not None:
            return _with_candidate_warning(dim_snapshot, policy)

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


def _context_hints(result: TableInspectResult | None) -> set[str]:
    if result is None or not isinstance(result.validation, dict):
        return set()
    raw = result.validation.get("context_hints") or []
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def _preserve_generate_dwd_intermediate_prior(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    prior_layer: str,
    prior_table_type: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    hints = _context_hints(result)
    is_dwd_intermediate = "dwd_intermediate_downstream_model" in hints
    is_dwd_fact = "dwd_fact_from_dwd_source" in hints
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or prior_layer != "DWD"
        or llm_layer not in {"DWD", "DIM"}
        or table_type != "dimension"
        or not (is_dwd_intermediate or is_dwd_fact)
    ):
        return None
    warning_type = (
        "dwd_fact_prior_preserved"
        if is_dwd_fact
        else "dwd_intermediate_prior_preserved"
    )
    warning = {
        "type": warning_type,
        "severity": "warning",
        "message": (
            "LLM dimension candidate was preserved as DWD because the table "
            "looks like a cleaned intermediate or DWD fact source"
        ),
        "inferred_layer": llm_layer,
        "applied_layer": prior_layer,
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer=prior_layer,
        table_type="fact" if is_dwd_fact else prior_table_type or "other",
        source=policy.fallback_source,
        reason="DWD prior preserved by context hint",
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _remap_generate_dim_surrogate_candidate(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    prior_layer: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or prior_layer != "DWD"
        or llm_layer != "DWD"
        or table_type != "fact"
        or "dim_surrogate_from_dwd_source" not in _context_hints(result)
    ):
        return None
    warning = {
        "type": "dim_surrogate_candidate_remapped",
        "severity": "warning",
        "message": (
            "LLM DWD fact candidate was remapped to DIM because the table "
            "looks like a surrogate-key dimension built from a DWD source"
        ),
        "inferred_layer": llm_layer,
        "applied_layer": "DIM",
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer="DIM",
        table_type="dimension",
        source="table_inspector",
        reason="DWD candidate remapped to DIM by surrogate-key context",
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _remap_generate_dws_snapshot_candidate(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    prior_layer: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or prior_layer != "DWD"
        or llm_layer != "DWD"
        or table_type != "fact"
        or "dws_reusable_snapshot" not in _context_hints(result)
    ):
        return None
    warning = {
        "type": "dws_snapshot_candidate_remapped",
        "severity": "warning",
        "message": (
            "LLM DWD fact candidate was remapped to DWS because the table "
            "looks like a reusable metric snapshot"
        ),
        "inferred_layer": llm_layer,
        "applied_layer": "DWS",
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer="DWS",
        table_type="fact",
        source="table_inspector",
        reason="DWD candidate remapped to DWS by snapshot metric context",
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _remap_generate_dws_entity_metric_candidate(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    prior_layer: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or prior_layer != "DWD"
        or llm_layer != "DIM"
        or table_type != "dimension"
        or "dws_entity_metric_summary" not in _context_hints(result)
    ):
        return None
    warning = {
        "type": "dws_entity_metric_candidate_remapped",
        "severity": "warning",
        "message": (
            "LLM dimension candidate was remapped to DWS because the table "
            "looks like an entity-grain metric summary"
        ),
        "inferred_layer": llm_layer,
        "applied_layer": "DWS",
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer="DWS",
        table_type="fact",
        source="table_inspector",
        reason="DIM candidate remapped to DWS by entity metric context",
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _remap_generate_dim_entity_snapshot_candidate(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    prior_layer: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or prior_layer != "DWD"
        or llm_layer != "DWD"
        or table_type not in {"fact", "other"}
        or "dim_entity_snapshot" not in _context_hints(result)
    ):
        return None
    warning = {
        "type": "dim_entity_snapshot_candidate_remapped",
        "severity": "warning",
        "message": (
            "LLM DWD fact candidate was remapped to DIM because the table "
            "looks like an entity attribute snapshot"
        ),
        "inferred_layer": llm_layer,
        "applied_layer": "DIM",
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer="DIM",
        table_type="dimension",
        source="table_inspector",
        reason="DWD candidate remapped to DIM by entity snapshot context",
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _remap_generate_boundary_candidate(
    payload: LayerResolutionInput,
    *,
    llm_layer: str,
    table_type: str,
    validation: dict[str, Any],
) -> LayerResolution | None:
    policy = payload.policy
    result = payload.inspection_result
    if (
        result is None
        or policy.mode != "generate"
        or policy.fallback_source != "direct_rule"
        or llm_layer != "ADS"
    ):
        return None
    candidates = _candidate_layers(policy)
    target_layer = ""
    reason = ""
    if table_type == "dimension" and "DIM" in candidates:
        target_layer = "DIM"
        reason = (
            "ADS boundary candidate had dimension table evidence; "
            "remapped to DIM for middle-layer generation"
        )
    elif (
        table_type == "fact"
        and "DWS" in candidates
        and _result_has_grain(result)
    ):
        target_layer = "DWS"
        reason = (
            "ADS boundary candidate had summary fact grain evidence; "
            "remapped to DWS for middle-layer generation"
        )
    if not target_layer:
        return None

    warning = {
        "type": "llm_boundary_candidate_remapped",
        "severity": "warning",
        "message": reason,
        "inferred_layer": llm_layer,
        "applied_layer": target_layer,
    }
    return LayerResolution(
        table_name=payload.table_name,
        inferred_layer=llm_layer,
        applied_layer=target_layer,
        table_type=table_type or _prior_table_type(payload),
        source="table_inspector",
        reason=reason,
        warnings=(warning,),
        validation=validation,
        llm_confidence=_inspection_confidence(result),
    )


def _result_has_grain(result: TableInspectResult) -> bool:
    grain = result.grain if isinstance(result.grain, dict) else {}
    return bool(
        grain.get("entities")
        or grain.get("time_column")
        or grain.get("time_period")
    )


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
        return float(result.confidence)
    except (TypeError, ValueError):
        return None


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
) -> bool:
    if not layer or layer == "OTHER":
        return False
    candidates = _candidate_layers(policy)
    return not candidates or layer in candidates


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
