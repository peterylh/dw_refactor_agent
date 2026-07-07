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
) -> TableInspectResult:
    return TableInspectResult(
        table_name=table_name,
        declared_layer=declared_layer,
        inferred_layer=inferred_layer,
        table_type=table_type,
        confidence=confidence,
        reasoning_steps=[],
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


def test_unusable_llm_layer_falls_back_to_declared_prior():
    resolution = resolve_layer(
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
        )
    )

    assert resolution.inferred_layer == "OTHER"
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "declared"
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"


def test_out_of_candidate_llm_layer_falls_back_to_prior():
    resolution = resolve_layer(
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
        )
    )

    assert resolution.inferred_layer == "ADS"
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "direct_rule"
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"
    assert resolution.warnings[0]["candidate_layers"] == ("DWD", "DWS", "DIM")


def test_refresh_default_policy_rejects_fixed_boundary_llm_candidate():
    resolution = resolve_layer(
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
        )
    )

    assert resolution.inferred_layer == "ADS"
    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "declared"
    assert resolution.warnings[0]["type"] == "llm_layer_fallback"


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
