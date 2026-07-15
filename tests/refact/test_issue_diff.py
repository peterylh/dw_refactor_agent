from dw_refactor_agent.refactor.issue_diff import diff_assess_results


def _issue(fingerprint, title):
    return {
        "fingerprint": fingerprint,
        "title": title,
        "target": {"type": "table", "name": title},
    }


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
                            "warehouses/shop/mid/tasks/dwd_inventory.sql"
                        ),
                        "title": "wrapped filter",
                        "target": {
                            "type": "task",
                            "name": "warehouses/shop/mid/tasks/dwd_inventory.sql",
                        },
                    },
                    {
                        "fingerprint": (
                            "code_quality|CODE_FILTER|task|"
                            "warehouses/shop/mid/tasks/dwd_customer.sql"
                        ),
                        "title": "customer wrapped filter",
                        "target": {
                            "type": "task",
                            "name": "warehouses/shop/mid/tasks/dwd_customer.sql",
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
        "code_quality|CODE_FILTER|task|warehouses/shop/mid/tasks/dwd_inventory.sql"
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
                            "warehouses/shop/mid/tasks/dwd_customer.sql"
                        ),
                        "title": "select star",
                        "target": {
                            "type": "task",
                            "name": "warehouses/shop/mid/tasks/dwd_customer.sql",
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
                            f"warehouses/shop/mid/tasks/{current_table}.sql"
                        ),
                        "title": "select star",
                        "target": {
                            "type": "task",
                            "name": f"warehouses/shop/mid/tasks/{current_table}.sql",
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
        "warehouses/shop/mid/tasks/DIM_BASE_CUST_PROFILE_INFO.sql",
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
