from dw_refactor_agent.assessment.llm.layer_resolution import (
    LayerResolutionInput,
    LayerResolutionPolicy,
    resolve_layer,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
)
from tests.case_matrix import case_matrix


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


def test_low_confidence_llm_candidate_falls_back_to_prior():
    resolution = resolve_layer(
        LayerResolutionInput(
            table_name="customer_detail",
            declared_layer="DWD",
            declared_table_type="fact",
            inspection_result=_inspect_result(
                table_name="customer_detail",
                inferred_layer="DIM",
                table_type="dimension",
                confidence=0.01,
            ),
            policy=LayerResolutionPolicy(
                mode="refresh",
                min_llm_confidence=0.5,
            ),
        )
    )

    assert resolution.applied_layer == "DWD"
    assert resolution.table_type == "fact"
    assert resolution.source == "declared"
    assert resolution.validation["llm_confidence_below_min"] is True
    assert resolution.warnings[0]["llm_confidence"] == 0.01
    assert resolution.warnings[0]["min_llm_confidence"] == 0.5


@case_matrix(
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
