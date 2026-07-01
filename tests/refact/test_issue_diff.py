from refact.issue_diff import diff_assess_results


def _issue(fingerprint, title):
    return {
        "fingerprint": fingerprint,
        "title": title,
        "target": {"type": "table", "name": title},
    }


def _target_issue(fingerprint, target_type, name):
    return {
        "fingerprint": fingerprint,
        "title": fingerprint,
        "target": {"type": target_type, "name": name},
    }


def test_diff_assess_results_classifies_fixed_remaining_and_new():
    baseline = {
        "overall_score": 50.0,
        "dimensions": {
            "naming": {
                "score": 50.0,
                "issues": [
                    _issue("a", "old-a"),
                    _issue("b", "old-b"),
                ],
            }
        },
    }
    current = {
        "overall_score": 90.0,
        "dimensions": {
            "naming": {
                "score": 90.0,
                "issues": [
                    _issue("b", "new-b"),
                    _issue("c", "new-c"),
                ],
            }
        },
    }

    result = diff_assess_results(baseline, current)

    assert result["summary"] == {
        "baseline_issue_count": 2,
        "current_issue_count": 2,
        "fixed_count": 1,
        "remaining_count": 1,
        "new_count": 1,
    }
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == ["a"]
    assert [issue["fingerprint"] for issue in result["remaining_issues"]] == [
        "b"
    ]
    assert [issue["fingerprint"] for issue in result["new_issues"]] == ["c"]
    assert result["scope_score"]["overall_score"] == 90.0
    assert result["scope_score"]["dimensions"]["naming"]["score"] == 90.0


def test_diff_assess_results_filters_baseline_by_scope_plan():
    baseline = {
        "overall_score": 40.0,
        "dimensions": {
            "naming": {
                "score": 40.0,
                "issues": [
                    _issue("in_scope", "dwd_order"),
                    _issue("out_of_scope", "dwd_customer"),
                ],
            }
        },
    }
    current = {
        "overall_score": 100.0,
        "dimensions": {
            "naming": {
                "score": 100.0,
                "issues": [],
            }
        },
    }
    scope_plan = {
        "dimensions": {
            "naming": {
                "mode": "scoped",
                "tables": ["dwd_order"],
                "tasks": [],
            }
        }
    }

    result = diff_assess_results(
        baseline,
        current,
        scope_plan=scope_plan,
    )

    assert result["summary"]["baseline_issue_count"] == 1
    assert result["summary"]["fixed_count"] == 1
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "in_scope"
    ]


def test_diff_assess_results_filters_task_path_by_job_name():
    baseline = {
        "overall_score": 40.0,
        "dimensions": {
            "code_quality": {
                "score": 40.0,
                "issues": [
                    {
                        "fingerprint": (
                            "code_quality|CODE_FILTER|task|"
                            "shop/tasks/dwd_inventory.sql"
                        ),
                        "title": "wrapped filter",
                        "target": {
                            "type": "task",
                            "name": "shop/tasks/dwd_inventory.sql",
                        },
                    },
                    {
                        "fingerprint": (
                            "code_quality|CODE_FILTER|task|"
                            "shop/tasks/dwd_customer.sql"
                        ),
                        "title": "customer wrapped filter",
                        "target": {
                            "type": "task",
                            "name": "shop/tasks/dwd_customer.sql",
                        },
                    },
                ],
            }
        },
    }
    current = {
        "overall_score": 100.0,
        "dimensions": {
            "code_quality": {
                "score": 100.0,
                "issues": [],
            }
        },
    }
    scope_plan = {
        "dimensions": {
            "code_quality": {
                "mode": "scoped",
                "tables": [],
                "tasks": ["dwd_inventory"],
            }
        }
    }

    result = diff_assess_results(
        baseline,
        current,
        scope_plan=scope_plan,
    )

    assert result["summary"]["baseline_issue_count"] == 1
    assert result["summary"]["fixed_count"] == 1
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "code_quality|CODE_FILTER|task|shop/tasks/dwd_inventory.sql"
    ]


def test_diff_assess_results_maps_renamed_table_fingerprints():
    baseline = {
        "overall_score": 40.0,
        "dimensions": {
            "naming": {
                "score": 40.0,
                "issues": [
                    _target_issue(
                        "naming|NAMING_TABLE_TEMPLATE|table|dwd_customer",
                        "table",
                        "dwd_customer",
                    ),
                    _target_issue(
                        "naming|NAMING_COLUMN_NAME|column|"
                        "dwd_customer.customer_name",
                        "column",
                        "dwd_customer.customer_name",
                    ),
                ],
            },
            "code_quality": {
                "score": 40.0,
                "issues": [
                    _target_issue(
                        "code_quality|CODE_FILTER|task|"
                        "shop/tasks/dwd_customer.sql",
                        "task",
                        "shop/tasks/dwd_customer.sql",
                    )
                ],
            },
        },
    }
    current = {
        "overall_score": 70.0,
        "dimensions": {
            "naming": {
                "score": 70.0,
                "issues": [
                    _target_issue(
                        "naming|NAMING_COLUMN_NAME|column|"
                        "DIM_BASE_CUST_PROFILE_INFO.customer_name",
                        "column",
                        "DIM_BASE_CUST_PROFILE_INFO.customer_name",
                    )
                ],
            },
            "code_quality": {
                "score": 70.0,
                "issues": [
                    _target_issue(
                        "code_quality|CODE_FILTER|task|"
                        "shop/tasks/DIM_BASE_CUST_PROFILE_INFO.sql",
                        "task",
                        "shop/tasks/DIM_BASE_CUST_PROFILE_INFO.sql",
                    )
                ],
            },
        },
    }
    scope_plan = {
        "dimensions": {
            "naming": {
                "mode": "scoped",
                "tables": ["DIM_BASE_CUST_PROFILE_INFO"],
                "tasks": [],
            },
            "code_quality": {
                "mode": "scoped",
                "tables": [],
                "tasks": ["DIM_BASE_CUST_PROFILE_INFO"],
            },
        }
    }
    change_analysis = {
        "rename_mapping": {
            "dwd_customer": "DIM_BASE_CUST_PROFILE_INFO",
        }
    }

    result = diff_assess_results(
        baseline,
        current,
        scope_plan=scope_plan,
        change_analysis=change_analysis,
    )

    assert result["summary"] == {
        "baseline_issue_count": 3,
        "current_issue_count": 2,
        "fixed_count": 1,
        "remaining_count": 2,
        "new_count": 0,
    }
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "naming|NAMING_TABLE_TEMPLATE|table|dwd_customer"
    ]
    assert {issue["fingerprint"] for issue in result["remaining_issues"]} == {
        "naming|NAMING_COLUMN_NAME|column|"
        "DIM_BASE_CUST_PROFILE_INFO.customer_name",
        "code_quality|CODE_FILTER|task|"
        "shop/tasks/DIM_BASE_CUST_PROFILE_INFO.sql",
    }
