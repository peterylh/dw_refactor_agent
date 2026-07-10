import pytest

from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionInput,
    LayerResolutionPolicy,
    resolve_layer,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
)


def _inspect_result(
    *,
    table_name: str = "dwd_order_detail",
    declared_layer: str = "DWD",
    inferred_layer: str = "DWD",
    table_type: str = "fact",
    confidence: float = 0.9,
    grain=None,
) -> TableInspectResult:
    return TableInspectResult(
        table_name=table_name,
        declared_layer=declared_layer,
        inferred_layer=inferred_layer,
        table_type=table_type,
        confidence=confidence,
        reasoning_steps=[],
        grain=grain or {},
    )


@pytest.mark.parametrize(
    ("payload", "expected_prior"),
    [
        (
            LayerResolutionInput(
                table_name="dwd_customer",
                declared_layer="DWD",
                declared_table_type="fact",
                inspection_result=_inspect_result(
                    table_name="dwd_customer",
                    inferred_layer="DWD",
                    table_type="dimension",
                ),
                policy=LayerResolutionPolicy(mode="refresh"),
            ),
            {
                "source": "declared",
                "strength": "strong",
                "layer": "DWD",
                "table_type": "fact",
            },
        ),
        (
            LayerResolutionInput(
                table_name="dwd_customer",
                fallback_layer="DWD",
                fallback_table_type="fact",
                inspection_result=_inspect_result(
                    table_name="dwd_customer",
                    inferred_layer="DWD",
                    table_type="dimension",
                ),
                policy=LayerResolutionPolicy(
                    mode="generate",
                    candidate_layers=("DWD", "DWS", "DIM"),
                    fallback_source="direct_rule",
                ),
            ),
            {
                "source": "direct_rule",
                "strength": "weak",
                "layer": "DWD",
                "table_type": "fact",
            },
        ),
    ],
)
def test_llm_dimension_candidate_applies_dim_layer(payload, expected_prior):
    resolution = resolve_layer(payload)

    assert resolution.inferred_layer == "DWD"
    assert resolution.applied_layer == "DIM"
    assert resolution.table_type == "dimension"
    assert resolution.source == "table_inspector"
    assert resolution.validation["prior"] == expected_prior
    assert resolution.layer_score is None


@pytest.mark.parametrize(
    ("payload", "expected_inferred", "expected_source"),
    [
        (
            LayerResolutionInput(
                table_name="dwd_order_detail",
                declared_layer="DWD",
                declared_table_type="fact",
                fallback_layer="DWS",
                fallback_table_type="dimension",
                inspection_result=_inspect_result(
                    table_name="dwd_order_detail",
                    inferred_layer="OTHER",
                    table_type="dimension",
                ),
                policy=LayerResolutionPolicy(
                    mode="refresh",
                    fallback_source="declared",
                ),
            ),
            "OTHER",
            "declared",
        ),
        (
            LayerResolutionInput(
                table_name="dwd_order_detail",
                fallback_layer="DWD",
                fallback_table_type="fact",
                inspection_result=_inspect_result(
                    table_name="dwd_order_detail",
                    inferred_layer="ADS",
                    table_type="fact",
                ),
                policy=LayerResolutionPolicy(
                    mode="generate",
                    candidate_layers=("DWD", "DWS", "DIM"),
                    fallback_source="direct_rule",
                ),
            ),
            "ADS",
            "direct_rule",
        ),
        (
            LayerResolutionInput(
                table_name="dwd_order_detail",
                declared_layer="DWD",
                declared_table_type="fact",
                inspection_result=_inspect_result(
                    table_name="dwd_order_detail",
                    inferred_layer="ADS",
                    table_type="fact",
                ),
                policy=LayerResolutionPolicy(mode="refresh"),
            ),
            "ADS",
            "declared",
        ),
    ],
)
def test_unusable_llm_layer_falls_back_to_prior(
    payload, expected_inferred, expected_source
):
    resolution = resolve_layer(payload)

    assert resolution.inferred_layer == expected_inferred
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == expected_source
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"
    assert resolution.warnings[0]["candidate_layers"] == ("DWD", "DWS", "DIM")


@pytest.mark.parametrize(
    (
        "fixed_layer",
        "fallback_type",
        "llm_layer",
        "llm_type",
        "expected_type",
    ),
    [
        ("ODS", "other", "DIM", "dimension", "other"),
        ("ODS", "other", "DWD", "fact", "other"),
        ("ADS", "fact", "DWS", "fact", "fact"),
    ],
)
def test_fixed_boundaries_ignore_llm_candidates(
    fixed_layer,
    fallback_type,
    llm_layer,
    llm_type,
    expected_type,
):
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name=f"{fixed_layer.lower()}_table",
            fallback_layer=fixed_layer,
            fallback_table_type=fallback_type,
            inspection_result=_inspect_result(
                table_name=f"{fixed_layer.lower()}_table",
                declared_layer=fixed_layer,
                inferred_layer=llm_layer,
                table_type=llm_type,
            ),
            policy=LayerResolutionPolicy(
                mode="generate",
                fixed_layer=fixed_layer,
                fallback_source="direct_rule",
            ),
        )
    )

    assert resolution.inferred_layer == llm_layer
    assert resolution.applied_layer == fixed_layer
    assert resolution.table_type == expected_type
    assert resolution.source == "fixed_boundary"
    assert resolution.validation["prior"]["strength"] == "fixed"


def test_generate_without_llm_falls_back_to_direct_rule():
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name="dws_store_sales_daily",
            fallback_layer="DWS",
            fallback_table_type="fact",
            policy=LayerResolutionPolicy(
                mode="generate",
                fallback_source="direct_rule",
            ),
        )
    )

    assert resolution.inferred_layer == "DWS"
    assert resolution.applied_layer == "DWS"
    assert resolution.table_type == "fact"
    assert resolution.source == "direct_rule"
    assert resolution.validation["candidate"]["source"] == ""


def test_generate_rejects_ads_dimension_candidate():
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name="customer_2",
            fallback_layer="DWD",
            fallback_table_type="fact",
            inspection_result=_inspect_result(
                table_name="customer_2",
                inferred_layer="ADS",
                table_type="dimension",
            ),
            policy=LayerResolutionPolicy(
                mode="generate",
                candidate_layers=("DWD", "DWS", "DIM"),
                fallback_source="direct_rule",
            ),
        )
    )

    assert resolution.inferred_layer == "ADS"
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "direct_rule"
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"


def test_generate_rejects_ads_summary_fact_candidate_even_with_grain():
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name="inventory_daily",
            fallback_layer="DWD",
            fallback_table_type="fact",
            inspection_result=_inspect_result(
                table_name="inventory_daily",
                inferred_layer="ADS",
                table_type="fact",
                grain={
                    "entities": ["PROD", "STOR"],
                    "time_column": "stat_date",
                    "time_period": "D",
                },
            ),
            policy=LayerResolutionPolicy(
                mode="generate",
                candidate_layers=("DWD", "DWS", "DIM"),
                fallback_source="direct_rule",
            ),
        )
    )

    assert resolution.inferred_layer == "ADS"
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "direct_rule"
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"


@pytest.mark.parametrize(
    (
        "hint",
        "inferred_layer",
        "table_type",
        "expected_layer",
        "expected_type",
    ),
    [
        (
            "dwd_intermediate_downstream_model",
            "DIM",
            "dimension",
            "DIM",
            "dimension",
        ),
        ("dwd_fact_from_dwd_source", "DIM", "dimension", "DIM", "dimension"),
        ("dim_surrogate_from_dwd_source", "DWD", "fact", "DWD", "fact"),
        ("dws_reusable_snapshot", "DWD", "fact", "DWD", "fact"),
        ("dws_entity_metric_summary", "DIM", "dimension", "DIM", "dimension"),
        ("dim_entity_snapshot", "DWD", "other", "DWD", "other"),
    ],
)
def test_generate_does_not_override_llm_candidate_from_context_hint(
    hint,
    inferred_layer,
    table_type,
    expected_layer,
    expected_type,
):
    result = _inspect_result(
        table_name="ambiguous_table_2",
        inferred_layer=inferred_layer,
        table_type=table_type,
    )
    # Old cache entries can still contain these former benchmark-driven hints.
    # The resolver must treat them as inert metadata rather than decisions.
    result.validation["context_hints"] = [hint]

    resolution = resolve_layer(
        LayerResolutionInput(
            table_name="ambiguous_table_2",
            fallback_layer="DWD",
            fallback_table_type="other",
            inspection_result=result,
            policy=LayerResolutionPolicy(
                mode="generate",
                candidate_layers=("DWD", "DWS", "DIM"),
                fallback_source="direct_rule",
            ),
        )
    )

    assert resolution.inferred_layer == inferred_layer
    assert resolution.applied_layer == expected_layer
    assert resolution.table_type == expected_type
    assert resolution.source == "table_inspector"
    assert resolution.warnings == ()
