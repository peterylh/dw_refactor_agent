from assess.result_model import finalize_dimension, make_check


def test_finalize_dimension_adds_stable_issue_fingerprint():
    checks = [
        make_check(
            rule_id="MODEL_DWS_GRAIN_PRESENT",
            target_type="table",
            target="dws_product_sales_daily",
            passed=False,
            expected="grain present",
            actual="missing",
        )
    ]

    result = finalize_dimension(
        dimension="model_design",
        score=0.0,
        checks=checks,
        rules={
            "MODEL_DWS_GRAIN_PRESENT": {
                "name": "grain",
                "severity": "中",
            }
        },
    )

    assert result["issues"][0]["fingerprint"] == (
        "model_design|MODEL_DWS_GRAIN_PRESENT|table|dws_product_sales_daily"
    )


def test_make_check_accepts_fingerprint_discriminator():
    checks = [
        make_check(
            rule_id="NAMING_COLUMN_NAME",
            target_type="table",
            target="dwd_order_detail",
            passed=False,
            expected="column naming",
            actual="bad_col",
            fingerprint_discriminator="column:bad_col",
        )
    ]

    result = finalize_dimension(
        dimension="naming",
        score=0.0,
        checks=checks,
        rules={
            "NAMING_COLUMN_NAME": {
                "name": "column",
                "severity": "低",
            }
        },
    )

    assert result["issues"][0]["fingerprint"] == (
        "naming|NAMING_COLUMN_NAME|table|dwd_order_detail|column:bad_col"
    )
