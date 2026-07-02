from refact.issue_diff import diff_assess_results


def _issue(fingerprint, title):
    return {
        "fingerprint": fingerprint,
        "title": title,
        "target": {"type": "table", "name": title},
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
        "baseline_scoped_issue_count": 2,
        "current_scoped_issue_count": 2,
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

    assert result["summary"]["baseline_scoped_issue_count"] == 1
    assert result["summary"]["fixed_count"] == 1
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "in_scope"
    ]


def test_diff_assess_results_filters_column_issue_by_qualified_name():
    baseline = {
        "overall_score": 40.0,
        "dimensions": {
            "naming": {
                "score": 40.0,
                "issues": [
                    {
                        "fingerprint": (
                            "naming|NAMING_COLUMN_NAME|column|"
                            "dwd_order.customer_id"
                        ),
                        "title": "bad customer id",
                        "target": {
                            "type": "column",
                            "name": "customer_id",
                            "qualified_name": "dwd_order.customer_id",
                        },
                    },
                    {
                        "fingerprint": (
                            "naming|NAMING_COLUMN_NAME|column|"
                            "dwd_customer.customer_id"
                        ),
                        "title": "other bad customer id",
                        "target": {
                            "type": "column",
                            "name": "customer_id",
                            "qualified_name": "dwd_customer.customer_id",
                        },
                    },
                ],
            }
        },
    }
    current = {
        "overall_score": 100.0,
        "dimensions": {"naming": {"score": 100.0, "issues": []}},
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

    assert result["summary"]["baseline_scoped_issue_count"] == 1
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "naming|NAMING_COLUMN_NAME|column|dwd_order.customer_id"
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

    assert result["summary"]["baseline_scoped_issue_count"] == 1
    assert result["summary"]["fixed_count"] == 1
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "code_quality|CODE_FILTER|task|shop/tasks/dwd_inventory.sql"
    ]


def test_diff_assess_results_treats_table_rename_issues_as_remaining():
    baseline = {
        "overall_score": 50.0,
        "dimensions": {
            "naming": {
                "score": 50.0,
                "issues": [
                    _issue(
                        "naming|NAMING_TABLE_TEMPLATE|table|dwd_customer",
                        "dwd_customer",
                    ),
                    _issue(
                        "naming|NAMING_COLUMN_NAME|table|dwd_customer",
                        "dwd_customer",
                    ),
                ],
            },
            "model_design": {
                "score": 50.0,
                "issues": [
                    _issue(
                        (
                            "model_design|"
                            "MODEL_DATE_PARTITION_USES_DATA_DT|"
                            "table|dwd_customer"
                        ),
                        "dwd_customer",
                    ),
                ],
            },
            "reuse": {
                "score": 50.0,
                "issues": [
                    _issue(
                        (
                            "reuse|REUSE_DOWNSTREAM_REACHES_TARGET|"
                            "table|dwd_customer"
                        ),
                        "dwd_customer",
                    ),
                ],
            },
            "code_quality": {
                "score": 50.0,
                "issues": [
                    {
                        "fingerprint": (
                            "code_quality|CODE_SELECT_STAR|task|"
                            "shop/tasks/dwd_customer.sql"
                        ),
                        "title": "select star",
                        "target": {
                            "type": "task",
                            "name": "shop/tasks/dwd_customer.sql",
                        },
                    },
                ],
            },
        },
    }
    current_table = "DIM_BASE_CUST_PROFILE_INFO"
    current = {
        "overall_score": 70.0,
        "dimensions": {
            "naming": {
                "score": 70.0,
                "issues": [
                    _issue(
                        f"naming|NAMING_COLUMN_NAME|table|{current_table}",
                        current_table,
                    ),
                ],
            },
            "model_design": {
                "score": 70.0,
                "issues": [
                    _issue(
                        (
                            "model_design|"
                            "MODEL_DATE_PARTITION_USES_DATA_DT|"
                            f"table|{current_table}"
                        ),
                        current_table,
                    ),
                ],
            },
            "reuse": {
                "score": 70.0,
                "issues": [
                    _issue(
                        (
                            "reuse|REUSE_DOWNSTREAM_REACHES_TARGET|"
                            f"table|{current_table}"
                        ),
                        current_table,
                    ),
                ],
            },
            "code_quality": {
                "score": 70.0,
                "issues": [
                    {
                        "fingerprint": (
                            "code_quality|CODE_SELECT_STAR|task|"
                            f"shop/tasks/{current_table}.sql"
                        ),
                        "title": "select star",
                        "target": {
                            "type": "task",
                            "name": f"shop/tasks/{current_table}.sql",
                        },
                    },
                ],
            },
        },
    }
    verification_plan = {
        "ddl_changes": [
            {
                "change_type": "RENAME",
                "old_name": "shop_dm.dwd_customer",
                "new_name": f"shop_dm.{current_table}",
            }
        ]
    }

    result = diff_assess_results(
        baseline,
        current,
        verification_plan=verification_plan,
    )

    assert result["summary"]["fixed_count"] == 1
    assert result["summary"]["remaining_count"] == 4
    assert result["summary"]["new_count"] == 0
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == [
        "naming|NAMING_TABLE_TEMPLATE|table|dwd_customer"
    ]
    assert [issue["fingerprint"] for issue in result["remaining_issues"]] == [
        "code_quality|CODE_SELECT_STAR|task|"
        "shop/tasks/DIM_BASE_CUST_PROFILE_INFO.sql",
        (
            "model_design|MODEL_DATE_PARTITION_USES_DATA_DT|"
            "table|DIM_BASE_CUST_PROFILE_INFO"
        ),
        "naming|NAMING_COLUMN_NAME|table|DIM_BASE_CUST_PROFILE_INFO",
        (
            "reuse|REUSE_DOWNSTREAM_REACHES_TARGET|"
            "table|DIM_BASE_CUST_PROFILE_INFO"
        ),
    ]


def test_diff_assess_results_reads_rename_mapping_from_change_analysis():
    baseline = {
        "dimensions": {
            "reuse": {
                "issues": [
                    _issue(
                        (
                            "reuse|REUSE_DOWNSTREAM_REACHES_TARGET|"
                            "table|dwd_customer"
                        ),
                        "dwd_customer",
                    )
                ]
            }
        }
    }
    current = {
        "dimensions": {
            "reuse": {
                "issues": [
                    _issue(
                        (
                            "reuse|REUSE_DOWNSTREAM_REACHES_TARGET|"
                            "table|DIM_BASE_CUST_PROFILE_INFO"
                        ),
                        "DIM_BASE_CUST_PROFILE_INFO",
                    )
                ]
            }
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
        change_analysis=change_analysis,
    )

    assert result["summary"]["fixed_count"] == 0
    assert result["summary"]["remaining_count"] == 1
    assert result["summary"]["new_count"] == 0
