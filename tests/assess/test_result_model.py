from dw_refactor_agent.assessment.result_model import (
    compact_assessment_result,
    finalize_dimension,
    make_check,
)


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


def test_column_issue_fingerprint_uses_qualified_name():
    checks = [
        make_check(
            rule_id="NAMING_COLUMN_NAME",
            target_type="column",
            target="customer_id",
            target_detail={
                "table": "dwd_customer",
                "qualified_name": "dwd_customer.customer_id",
            },
            passed=False,
            expected="column naming",
            actual={"value": "customer_id"},
            fingerprint_discriminator="column:dwd_customer.customer_id",
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
        "naming|NAMING_COLUMN_NAME|column|dwd_customer.customer_id"
    )


def test_compact_assessment_result_promotes_issue_diagnostics():
    checks = [
        make_check(
            rule_id="NAMING_COLUMN_NAME",
            target_type="column",
            target="customer_id",
            target_detail={
                "table": "dwd_customer",
                "qualified_name": "dwd_customer.customer_id",
                "layer": "DWD",
            },
            passed=False,
            expected={
                "description": "非指标字段符合字段命名规则",
                "rule_names": ["COLUMN_DEFAULT"],
                "attempts": [
                    {
                        "rule_name": "COLUMN_DEFAULT",
                        "description": "默认字段命名大写标识符，长度小于16",
                        "expression": "{COLUMN_IDENTIFIER}",
                        "segments": [
                            {
                                "position": 1,
                                "kind": "type",
                                "name": "COLUMN_IDENTIFIER",
                                "type": {
                                    "name": "COLUMN_IDENTIFIER",
                                    "label": "字段标识符",
                                    "patterns": ["^[A-Z][A-Z0-9_]{0,14}$"],
                                },
                            }
                        ],
                    }
                ],
                "layer": "DWD",
            },
            actual={"value": "customer_id"},
            diagnostic={
                "code": "type_pattern_mismatch",
                "attempts": [
                    {
                        "actual": "customer_id",
                        "passed": False,
                        "rule": {
                            "name": "COLUMN_DEFAULT",
                            "description": "默认字段命名大写标识符，长度小于16",
                        },
                        "expression": "{COLUMN_IDENTIFIER}",
                        "segments": [
                            {
                                "position": 1,
                                "kind": "type",
                                "name": "COLUMN_IDENTIFIER",
                                "type": {
                                    "name": "COLUMN_IDENTIFIER",
                                    "label": "字段标识符",
                                    "patterns": ["^[A-Z][A-Z0-9_]{0,14}$"],
                                },
                            }
                        ],
                        "failure": {
                            "code": "type_pattern_mismatch",
                            "position": 1,
                            "segment": {
                                "position": 1,
                                "kind": "type",
                                "name": "COLUMN_IDENTIFIER",
                                "type": {
                                    "name": "COLUMN_IDENTIFIER",
                                    "label": "字段标识符",
                                    "patterns": ["^[A-Z][A-Z0-9_]{0,14}$"],
                                },
                            },
                            "expected": ["^[A-Z][A-Z0-9_]{0,14}$"],
                            "actual": "customer_id",
                            "actual_remaining": "customer_id",
                            "consumed_chars": 0,
                        },
                    }
                ],
            },
            summary="字段名不符合规范",
            message="不合规字段: customer_id",
        )
    ]
    dimension = finalize_dimension(
        dimension="naming",
        score=0.0,
        checks=checks,
        rules={
            "NAMING_COLUMN_NAME": {
                "name": "column",
                "severity": "低",
                "title": "字段名不符合规范",
            }
        },
    )
    result = compact_assessment_result(
        {
            "project": "shop",
            "overall_score": 0.0,
            "weights": {},
            "dimensions": {"naming": dimension},
        }
    )

    naming = result["dimensions"]["naming"]
    issue = naming["issues"][0]

    assert "checks" not in naming
    assert "check_ids" not in issue
    assert set(issue["diagnostic"]) == {"expected", "actual", "evidence"}
    assert issue["diagnostic"] == {
        "expected": {
            "description": "非指标字段符合字段命名规则",
            "rule_refs": ["COLUMN_DEFAULT"],
        },
        "actual": {"value": "customer_id"},
        "evidence": {
            "code": "type_pattern_mismatch",
            "attempts": [
                {
                    "rule_ref": "COLUMN_DEFAULT",
                    "failure": {
                        "code": "type_pattern_mismatch",
                        "segment": {
                            "name": "COLUMN_IDENTIFIER",
                            "ordinal": 1,
                        },
                        "expected": ["^[A-Z][A-Z0-9_]{0,14}$"],
                        "actual": "customer_id",
                    },
                }
            ],
        },
    }
    assert naming["diagnostic_catalog"] == {
        "naming_rules": {
            "COLUMN_DEFAULT": {
                "expression": "{COLUMN_IDENTIFIER}",
                "segments": [
                    {
                        "name": "COLUMN_IDENTIFIER",
                        "ordinal": 1,
                        "kind": "type",
                        "label": "字段标识符",
                        "patterns": ["^[A-Z][A-Z0-9_]{0,14}$"],
                    }
                ],
            }
        }
    }


def test_compact_assessment_result_keeps_raw_diagnostic_inside_evidence():
    checks = [
        make_check(
            rule_id="MODEL_SQL_PARSEABLE",
            target_type="task",
            target="warehouses/shop/mid/tasks/dwd_order_detail.sql",
            passed=False,
            expected="SQL可以解析",
            actual="SQL解析失败",
            evidence={"line": 12},
            diagnostic={"parser_error": "unexpected token"},
        )
    ]
    dimension = finalize_dimension(
        dimension="code_quality",
        score=0.0,
        checks=checks,
        rules={
            "MODEL_SQL_PARSEABLE": {
                "name": "sql parseable",
                "severity": "高",
                "title": "SQL无法解析",
            }
        },
    )

    result = compact_assessment_result(
        {
            "project": "shop",
            "overall_score": 0.0,
            "weights": {},
            "dimensions": {"code_quality": dimension},
        }
    )
    issue = result["dimensions"]["code_quality"]["issues"][0]

    assert set(issue["diagnostic"]) == {"expected", "actual", "evidence"}
    assert issue["diagnostic"]["evidence"] == {
        "line": 12,
        "raw": {"parser_error": "unexpected token"},
    }
