from dw_refactor_agent.lineage.view import LineageView


class CountingEdges(list):
    def __init__(self, values):
        super().__init__(values)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


def test_lineage_view_reuses_indexed_column_lineage():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "tmp_orders.amount",
                "expression": "SUM(dwd_orders.amount) AS amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "dws_orders.total_amount",
                "expression": "tmp_orders.amount AS total_amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "group_by",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.raw_table_graph() == (
        {
            "tmp_orders": {"dwd_orders"},
            "dws_orders": {"tmp_orders", "dwd_orders"},
        },
        {
            "dwd_orders": {"tmp_orders", "dws_orders"},
            "tmp_orders": {"dws_orders"},
        },
    )
    assert view.asset_table_graph() == (
        {"dws_orders": {"dwd_orders"}},
        {"dwd_orders": {"dws_orders"}},
    )
    assert view.column_lineage_for_table("dws_orders") == [
        {
            "source": "dwd_orders.amount",
            "target": "dws_orders.total_amount",
            "expression": "tmp_orders.amount AS total_amount",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.amount"],
            "expression_chain": [
                {
                    "source": "dwd_orders.amount",
                    "target": "tmp_orders.amount",
                    "expression": "SUM(dwd_orders.amount) AS amount",
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.amount",
                    "target": "dws_orders.total_amount",
                    "expression": "tmp_orders.amount AS total_amount",
                    "source_file": "dws_orders.sql",
                },
            ],
            "condition_lineage": [
                {
                    "source": "dwd_orders.store_id",
                    "condition_type": "GROUP_BY",
                    "condition_expression": "store_id",
                    "source_file": "dws_orders.sql",
                }
            ],
        }
    ]


def test_lineage_view_collapses_transient_column_lineage_case_insensitively():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
            {
                "source": "DWD_Orders.amount",
                "target": "TMP_Orders.amount",
                "expression": "DWD_Orders.amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "DWS_Orders.total_amount",
                "expression": "tmp_orders.amount AS total_amount",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.asset_table_graph() == (
        {"DWS_Orders": {"DWD_Orders"}},
        {"DWD_Orders": {"DWS_Orders"}},
    )
    assert view.column_lineage_for_table("dws_orders") == [
        {
            "source": "DWD_Orders.amount",
            "target": "DWS_Orders.total_amount",
            "expression": "tmp_orders.amount AS total_amount",
            "source_file": "dws_orders.sql",
            "transient_path": ["tmp_orders.amount"],
            "expression_chain": [
                {
                    "source": "DWD_Orders.amount",
                    "target": "TMP_Orders.amount",
                    "expression": "DWD_Orders.amount",
                    "source_file": "dws_orders.sql",
                },
                {
                    "source": "tmp_orders.amount",
                    "target": "DWS_Orders.total_amount",
                    "expression": "tmp_orders.amount AS total_amount",
                    "source_file": "dws_orders.sql",
                },
            ],
        }
    ]


def test_lineage_view_indexes_design_facts_by_table():
    lineage_data = {
        "tables": [{"name": "dws_orders", "columns": []}],
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "column", "id": "dws_orders.store_id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.amount"},
                "target": {"type": "column", "id": "dws_orders.total_amount"},
                "relation_type": "direct",
                "transformation_type": "aggregation",
                "expression": "SUM(amount) AS total_amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "literal", "value": "ALL"},
                "target": {"type": "column", "id": "dws_orders.channel_type"},
                "relation_type": "direct",
                "transformation_type": "constant",
                "expression": "'ALL' AS channel_type",
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.store_id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "group_by",
                "transformation_type": "group_by",
                "expression": "store_id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    facts = LineageView.from_data(
        "demo", lineage_data
    ).lineage_facts_for_table("dws_orders")

    assert facts == {
        "has_lineage": True,
        "has_group_by": True,
        "has_aggregate": True,
        "aggregate_columns": ["total_amount"],
        "constant_columns": ["channel_type"],
        "plain_columns": ["store_id"],
        "plain_column_sources": {"store_id": "dwd_orders.store_id"},
        "group_by_sources": ["dwd_orders.store_id"],
        "source_files": ["dws_orders.sql"],
    }


def test_lineage_view_indexes_targets_by_source_file():
    lineage_data = {
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "column", "id": "dws_orders.id"},
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "where",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_payments.id",
                "target_table": "dws_payments",
                "source_file": "dws_payments.sql",
            }
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.targets_by_source_file("dws_orders.sql") == {"dws_orders"}
    assert view.targets_by_source_file("dws_payments.sql") == {"dws_payments"}


def test_lineage_view_indexes_table_edge_source_files():
    lineage_data = {
        "edges": [
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "column", "id": "dws_orders.id"},
                "source_file": "dws_orders.sql",
            },
            {
                "source": {"type": "column", "id": "dwd_orders.status"},
                "target": {"type": "table", "id": "dws_orders"},
                "relation_type": "where",
                "source_file": "dws_orders.sql",
            },
        ],
        "indirect_edges": [
            {
                "source": "dwd_payments.id",
                "target_table": "dws_payments",
                "source_file": "dws_payments.sql",
            }
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.table_edge_source_files() == {
        ("dwd_orders", "dws_orders"): {"dws_orders.sql"},
        ("dwd_payments", "dws_payments"): {"dws_payments.sql"},
    }


def test_lineage_view_exposes_self_edges_separately_from_table_graphs():
    lineage_data = {
        "tables": [{"name": "tmp_orders", "is_transient": True}],
        "edges": [
            {
                "source": "dwd_orders.amount",
                "target": "DWD_Orders.amount",
                "expression": "amount + 1",
                "source_file": "dwd_orders.sql",
            },
            {
                "source": "tmp_orders.amount",
                "target": "tmp_orders.amount",
                "expression": "amount + 1",
                "source_file": "tmp_orders.sql",
            },
            {
                "source": "dwd_orders.id",
                "target": "dws_orders.id",
                "source_file": "dws_orders.sql",
            },
        ],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.raw_table_graph() == (
        {"dws_orders": {"dwd_orders"}},
        {"dwd_orders": {"dws_orders"}},
    )
    assert view.raw_self_edges() == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.amount",
            "target": "DWD_Orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        },
        {
            "table": "tmp_orders",
            "source_table": "tmp_orders",
            "target_table": "tmp_orders",
            "source": "tmp_orders.amount",
            "target": "tmp_orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "tmp_orders.sql",
        },
    ]
    assert view.asset_self_edges() == [
        {
            "table": "dwd_orders",
            "source_table": "dwd_orders",
            "target_table": "dwd_orders",
            "source": "dwd_orders.amount",
            "target": "DWD_Orders.amount",
            "relation_type": "direct",
            "expression": "amount + 1",
            "source_file": "dwd_orders.sql",
        }
    ]
    assert view.self_edges_for_table("DWD_ORDERS") == view.asset_self_edges()


def test_lineage_view_resolves_v2_edge_job_to_source_file():
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "name": "src",
                "full_name": "src",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
            {
                "name": "out",
                "full_name": "out",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
        ],
        "jobs": [
            {
                "name": "publish",
                "source_file": "mid/tasks/publish.sql",
                "inputs": ["src"],
                "outputs": ["out"],
            }
        ],
        "edges": [
            {
                "source": {"type": "column", "id": "src.id"},
                "target": {"type": "column", "id": "out.id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": "publish",
            }
        ],
        "diagnostics": [],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert view.column_lineage_for_table("out") == [
        {
            "source": "src.id",
            "target": "out.id",
            "expression": "id",
            "job": "publish",
            "source_file": "mid/tasks/publish.sql",
        }
    ]
    assert view.lineage_facts_for_table("out")["source_files"] == [
        "mid/tasks/publish.sql"
    ]
    assert view.targets_by_source_file("mid/tasks/publish.sql") == {"out"}
    assert view.table_edge_source_files() == {
        ("src", "out"): {"mid/tasks/publish.sql"}
    }


def test_lineage_view_resolves_v2_self_edge_job_to_source_file():
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "name": "out",
                "full_name": "out",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
        ],
        "jobs": [
            {
                "name": "refresh",
                "source_file": "mid/tasks/refresh.sql",
                "inputs": ["out"],
                "outputs": ["out"],
            }
        ],
        "edges": [
            {
                "source": {"type": "column", "id": "out.id"},
                "target": {"type": "column", "id": "out.id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": "refresh",
            }
        ],
        "diagnostics": [],
    }

    view = LineageView.from_data("demo", lineage_data)

    expected = [
        {
            "table": "out",
            "source_table": "out",
            "target_table": "out",
            "source": {"type": "column", "id": "out.id"},
            "target": {"type": "column", "id": "out.id"},
            "relation_type": "direct",
            "expression": "id",
            "job": "refresh",
            "source_file": "mid/tasks/refresh.sql",
        }
    ]
    assert view.raw_self_edges() == expected
    assert view.asset_self_edges() == expected


def test_lineage_view_scopes_same_name_process_columns_by_job():
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "name": name,
                "full_name": name,
                "dataset_type": "process" if name == "t" else "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            for name in ("src_a", "src_b", "t", "out_a", "out_b")
        ],
        "jobs": [
            {
                "name": "job_a",
                "source_file": "mid/tasks/job_a.sql",
                "inputs": ["src_a", "t"],
                "outputs": ["t", "out_a"],
            },
            {
                "name": "job_b",
                "source_file": "mid/tasks/job_b.sql",
                "inputs": ["src_b", "t"],
                "outputs": ["t", "out_b"],
            },
        ],
        "edges": [
            {
                "source": {"type": "column", "id": f"{source}.id"},
                "target": {"type": "column", "id": f"{target}.id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": job,
            }
            for source, target, job in (
                ("src_a", "t", "job_a"),
                ("t", "out_a", "job_a"),
                ("src_b", "t", "job_b"),
                ("t", "out_b", "job_b"),
            )
        ],
        "diagnostics": [],
    }

    view = LineageView.from_data("demo", lineage_data)

    assert {
        record["source"] for record in view.column_lineage_for_table("out_a")
    } == {"src_a.id"}
    assert {
        record["source"] for record in view.column_lineage_for_table("out_b")
    } == {"src_b.id"}


def test_lineage_view_preindexes_conditions_once_for_all_target_jobs():
    jobs = [f"job_{index}" for index in range(4)]
    edges = CountingEdges(
        [
            {
                "source": {"type": "column", "id": f"src_{index}.id"},
                "target": {"type": "column", "id": "out.id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": job,
            }
            for index, job in enumerate(jobs)
        ]
        + [
            {
                "source": {
                    "type": "column",
                    "id": f"src_{index}.status",
                },
                "target": {"type": "table", "id": "out"},
                "relation_type": "filter",
                "transformation_type": "filter",
                "expression": "status = 'READY'",
                "job": job,
            }
            for index, job in enumerate(jobs)
        ]
    )
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "name": name,
                "full_name": name,
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            for name in ["out"] + [f"src_{index}" for index in range(4)]
        ],
        "jobs": [
            {
                "name": job,
                "source_file": f"mid/tasks/{job}.sql",
                "inputs": [f"src_{index}"],
                "outputs": ["out"],
            }
            for index, job in enumerate(jobs)
        ],
        "edges": edges,
        "diagnostics": [],
    }
    view = LineageView.from_data("demo", lineage_data)
    edges.iterations = 0

    records = view.column_lineage_for_table("out")

    assert len(records) == 4
    assert edges.iterations == 2
