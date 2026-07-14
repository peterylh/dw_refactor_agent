import pytest

from dw_refactor_agent.lineage.contract import (
    LineageContractError,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.lineage_extractor import build_lineage_output


class CountingSchema(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values_calls = 0

    def values(self):
        self.values_calls += 1
        return super().values()


def _task_result(
    source_file,
    *,
    inputs=(),
    outputs=(),
    created=(),
    temporary=(),
    local_lifecycle=(),
):
    return {
        "source_file": source_file,
        "input_tables": list(inputs),
        "output_tables": list(outputs),
        "created_tables": list(created),
        "temporary_tables": list(temporary),
        "local_lifecycle_tables": list(local_lifecycle),
    }


def test_build_lineage_output_emits_job_owned_edges_without_source_file():
    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "order_id",
                "target_table": "dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "mid/tasks/prepare.sql",
            }
        ],
        {
            "shop_dm": {
                "dwd_orders": {"order_id": "BIGINT"},
                "dws_orders": {"order_id": "BIGINT"},
            }
        },
        task_results=[
            _task_result(
                "mid/tasks/prepare.sql",
                inputs=["shop_dm.dwd_orders"],
                outputs=["shop_dm.dws_orders"],
            )
        ],
    )

    assert output["format_version"] == 2
    assert output["jobs"][0]["name"] == "prepare"
    assert output["edges"][0]["job"] == "prepare"
    assert "source_file" not in output["edges"][0]
    validate_lineage_v2(output)


def test_build_lineage_output_deduplicates_direct_edges_case_insensitively():
    entries = [
        {
            "source_table": "db.source",
            "source_column": "id",
            "target_table": "db.output",
            "target_column": "id",
            "lineage_type": "direct",
            "expression": "ID",
            "source_file": "load.sql",
        },
        {
            "source_table": "DB.Source",
            "source_column": "ID",
            "target_table": "DB.Output",
            "target_column": "ID",
            "lineage_type": "direct",
            "expression": "ID",
            "source_file": "load.sql",
        },
        {
            "source_table": "DB.Source",
            "source_column": "ID",
            "target_table": "DB.Output",
            "target_column": "ID",
            "lineage_type": "direct",
            "expression": "ID + 0",
            "source_file": "load.sql",
        },
    ]

    output = build_lineage_output(
        entries,
        {},
        task_results=[
            _task_result(
                "load.sql",
                inputs=["DB.Source"],
                outputs=["DB.Output"],
            )
        ],
    )

    assert len(output["edges"]) == 2
    assert {edge["expression"] for edge in output["edges"]} == {
        "ID",
        "ID + 0",
    }
    assert {edge["source"]["id"] for edge in output["edges"]} == {
        "db.source.id"
    }
    assert {edge["target"]["id"] for edge in output["edges"]} == {
        "db.output.id"
    }
    validate_lineage_v2(output)


def test_build_lineage_output_keeps_explicit_column_sources_distinct():
    output = build_lineage_output(
        [
            {
                "source_type": "column",
                "source_table": "db.source_a",
                "source_column": "id",
                "target_table": "db.output",
                "target_column": "id",
                "lineage_type": "direct",
                "expression": "id",
                "source_file": "load.sql",
            },
            {
                "source_type": "column",
                "source_table": "db.source_b",
                "source_column": "id",
                "target_table": "db.output",
                "target_column": "id",
                "lineage_type": "direct",
                "expression": "id",
                "source_file": "load.sql",
            },
        ],
        {},
        task_results=[
            _task_result(
                "load.sql",
                inputs=["db.source_a", "db.source_b"],
                outputs=["db.output"],
            )
        ],
    )

    assert len(output["edges"]) == 2
    assert {edge["source"]["id"] for edge in output["edges"]} == {
        "db.source_a.id",
        "db.source_b.id",
    }
    validate_lineage_v2(output)


def test_build_lineage_output_deduplicates_effective_passthrough():
    base_entry = {
        "source_table": "db.source",
        "source_column": "id",
        "target_table": "db.output",
        "target_column": "id",
        "lineage_type": "direct",
        "expression": "id",
        "source_file": "load.sql",
    }
    output = build_lineage_output(
        [base_entry, {**base_entry, "transformation_type": "passthrough"}],
        {},
        task_results=[
            _task_result(
                "load.sql",
                inputs=["db.source"],
                outputs=["db.output"],
            )
        ],
    )

    assert len(output["edges"]) == 1
    assert output["edges"][0]["transformation_type"] == "passthrough"
    validate_lineage_v2(output)


def test_build_lineage_output_deduplicates_indirect_edges_case_insensitively():
    output = build_lineage_output(
        [
            {
                "source_table": "db.source",
                "source_column": "id",
                "target_table": "db.output",
                "target_column": "",
                "lineage_type": "indirect",
                "condition_type": "WHERE",
                "condition_expression": "ID > 0",
                "source_file": "load.sql",
            },
            {
                "source_table": "DB.Source",
                "source_column": "ID",
                "target_table": "DB.Output",
                "target_column": "",
                "lineage_type": "indirect",
                "condition_type": "WHERE",
                "condition_expression": "ID > 0",
                "source_file": "load.sql",
            },
            {
                "source_table": "DB.Source",
                "source_column": "ID",
                "target_table": "DB.Output",
                "target_column": "",
                "lineage_type": "indirect",
                "condition_type": "GROUP_BY",
                "condition_expression": "ID > 0",
                "source_file": "load.sql",
            },
        ],
        {},
        task_results=[
            _task_result(
                "load.sql",
                inputs=["DB.Source"],
                outputs=["DB.Output"],
            )
        ],
    )

    assert len(output["edges"]) == 2
    assert {edge["relation_type"] for edge in output["edges"]} == {
        "filter",
        "group_by",
    }
    assert {edge["source"]["id"] for edge in output["edges"]} == {
        "db.source.id"
    }
    assert {edge["target"]["id"] for edge in output["edges"]} == {"db.output"}
    validate_lineage_v2(output)


def test_build_lineage_output_classifies_all_job_datasets():
    output = build_lineage_output(
        [
            {
                "source_table": "ext_orders",
                "source_column": "order_id",
                "target_table": "process_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "prepare.sql",
            },
            {
                "source_table": "process_orders",
                "source_column": "order_id",
                "target_table": "dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "load.sql",
            },
        ],
        {"shop_dm": {"dws_orders": {"order_id": "BIGINT"}}},
        task_results=[
            _task_result(
                "prepare.sql",
                inputs=["ext_orders"],
                outputs=["process_orders"],
                created=["process_orders", "temp_stage"],
                temporary=["temp_stage"],
                local_lifecycle=[{"name": "temp_stage"}],
            ),
            _task_result(
                "load.sql",
                inputs=["process_orders"],
                outputs=["dws_orders"],
            ),
        ],
    )

    tables = {table["name"]: table for table in output["tables"]}
    assert {name: table["dataset_type"] for name, table in tables.items()} == {
        "dws_orders": "managed",
        "ext_orders": "external",
        "process_orders": "process",
        "temp_stage": "temporary",
    }
    table_full_names = {table["full_name"] for table in output["tables"]}
    assert {
        dataset
        for job in output["jobs"]
        for dataset in (*job["inputs"], *job["outputs"])
    } <= table_full_names
    validate_lineage_v2(output)


def test_build_lineage_output_emits_producer_diagnostics_with_jobs():
    output = build_lineage_output(
        [],
        {},
        task_results=[
            _task_result("producer_a.sql", outputs=["db.process_t"]),
            _task_result("producer_b.sql", outputs=["DB.PROCESS_T"]),
            _task_result("consumer.sql", inputs=["db.process_t"]),
        ],
    )

    assert output["diagnostics"] == [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "db.process_t",
            "reason": "multiple_candidates",
            "consumer_jobs": ["consumer"],
            "candidate_producer_jobs": ["producer_a", "producer_b"],
        }
    ]
    assert all("source_file" not in item for item in output["diagnostics"])
    validate_lineage_v2(output)


def test_build_lineage_output_rejects_case_insensitive_duplicate_job_names():
    with pytest.raises(ValueError, match="duplicate Job name.*load"):
        build_lineage_output(
            [],
            {},
            task_results=[
                _task_result("mid/tasks/Load.sql"),
                _task_result("ads/tasks/load.sql"),
            ],
        )


def test_build_lineage_output_rejects_unowned_legacy_edge():
    with pytest.raises(LineageContractError, match="source_file"):
        build_lineage_output(
            [
                {
                    "source_table": "src",
                    "source_column": "id",
                    "target_table": "out",
                    "target_column": "id",
                    "expression": "id",
                }
            ],
            {},
        )


def test_build_lineage_output_rejects_source_less_edge_with_one_explicit_job():
    with pytest.raises(LineageContractError, match="source_file"):
        build_lineage_output(
            [
                {
                    "source_table": "src",
                    "source_column": "id",
                    "target_table": "out",
                    "target_column": "id",
                    "expression": "id",
                }
            ],
            {},
            task_results=[
                _task_result(
                    "load.sql",
                    inputs=["src"],
                    outputs=["out"],
                )
            ],
        )


def test_legacy_temporary_metadata_removes_output_case_insensitively():
    output = build_lineage_output(
        [
            {
                "source_table": "src",
                "source_column": "id",
                "target_table": "Tmp_T",
                "target_column": "id",
                "expression": "id",
                "source_file": "prepare.sql",
            }
        ],
        {},
        transient_tables=[
            {
                "name": "tmp_t",
                "source_file": "prepare.sql",
                "is_temporary": True,
            }
        ],
    )

    assert output["jobs"][0]["outputs"] == []
    tmp_table = next(
        table
        for table in output["tables"]
        if table["name"].casefold() == "tmp_t"
    )
    assert tmp_table["dataset_type"] == "temporary"
    validate_lineage_v2(output)


def test_build_lineage_output_indexes_schema_column_types_once():
    schema = CountingSchema(
        {
            "shop_dm": {
                "dwd_orders": {
                    "order_id": "BIGINT",
                    "amount": "DECIMAL(12,2)",
                },
                "dws_orders": {
                    "order_id": "BIGINT",
                    "total_amount": "DECIMAL(12,2)",
                },
            },
        }
    )

    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "order_id",
                "target_table": "dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            },
            {
                "source_table": "dwd_orders",
                "source_column": "amount",
                "target_table": "dws_orders",
                "target_column": "total_amount",
                "lineage_type": "direct",
                "expression": "SUM(amount) AS total_amount",
                "source_file": "dws_orders.sql",
            },
        ],
        schema,
    )

    validate_lineage_v2(output)
    assert schema.values_calls <= 1
    dws_orders = next(
        table for table in output["tables"] if table["name"] == "dws_orders"
    )
    assert {
        column["name"]: column["type"] for column in dws_orders["columns"]
    } == {
        "order_id": "BIGINT",
        "total_amount": "DECIMAL(12,2)",
    }


def test_build_lineage_output_marks_temporary_tables_without_legacy_metadata():
    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "order_id",
                "target_table": "tmp_orders_stage",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            },
            {
                "source_table": "tmp_orders_stage",
                "source_column": "order_id",
                "target_table": "dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            },
        ],
        {
            "shop_dm": {
                "dwd_orders": {"order_id": "BIGINT"},
                "dws_orders": {"order_id": "BIGINT"},
            }
        },
        task_results=[
            _task_result(
                "dws_orders.sql",
                inputs=["dwd_orders", "tmp_orders_stage"],
                outputs=["dws_orders"],
                created=["tmp_orders_stage"],
                temporary=["tmp_orders_stage"],
                local_lifecycle=[{"name": "tmp_orders_stage"}],
            )
        ],
    )

    tmp_table = next(
        table
        for table in output["tables"]
        if table["name"] == "tmp_orders_stage"
    )
    assert "nodes" not in output
    assert "transient_tables" not in output
    assert tmp_table["dataset_type"] == "temporary"
    assert set(tmp_table) == {"name", "full_name", "dataset_type", "columns"}
    validate_lineage_v2(output)


def test_build_lineage_output_keeps_temporary_table_without_edges_in_tables():
    output = build_lineage_output(
        [],
        {
            "shop_dm": {
                "dws_orders": {"order_id": "BIGINT"},
            }
        },
        task_results=[
            _task_result(
                "tmp_orders_stage.sql",
                created=["tmp_orders_stage"],
                temporary=["tmp_orders_stage"],
                local_lifecycle=[{"name": "tmp_orders_stage"}],
            )
        ],
    )

    assert "transient_tables" not in output
    assert output["tables"] == [
        {
            "name": "tmp_orders_stage",
            "full_name": "shop_dm.tmp_orders_stage",
            "dataset_type": "temporary",
            "columns": [],
        },
    ]
    validate_lineage_v2(output)


def test_build_lineage_output_uses_typed_edges_for_direct_and_group_by():
    output = build_lineage_output(
        [
            {
                "source_table": "dwd_orders",
                "source_column": "amount",
                "target_table": "dws_orders",
                "target_column": "total_amount",
                "lineage_type": "direct",
                "expression": "SUM(amount) AS total_amount",
                "source_file": "dws_orders.sql",
            },
            {
                "source_table": "dwd_orders",
                "source_column": "order_date",
                "target_table": "dws_orders",
                "target_column": "",
                "lineage_type": "indirect",
                "condition_type": "GROUP_BY",
                "condition_expression": "order_date",
                "source_file": "dws_orders.sql",
            },
        ],
        {
            "shop_dm": {
                "dwd_orders": {
                    "amount": "DECIMAL(12,2)",
                    "order_date": "DATE",
                },
                "dws_orders": {"total_amount": "DECIMAL(12,2)"},
            }
        },
    )

    assert "nodes" not in output
    assert "transient_tables" not in output
    assert output["edges"] == [
        {
            "source": {"type": "column", "id": "dwd_orders.amount"},
            "target": {"type": "column", "id": "dws_orders.total_amount"},
            "relation_type": "direct",
            "transformation_type": "aggregation",
            "expression": "SUM(amount) AS total_amount",
            "job": "dws_orders",
        },
        {
            "source": {"type": "column", "id": "dwd_orders.order_date"},
            "target": {"type": "table", "id": "dws_orders"},
            "relation_type": "group_by",
            "transformation_type": "group_by",
            "expression": "order_date",
            "job": "dws_orders",
        },
    ]
    assert "indirect_edges" not in output
    validate_lineage_v2(output)


def test_build_lineage_output_hides_internal_catalog_but_keeps_external():
    output = build_lineage_output(
        [
            {
                "source_table": "hive.shop_dm.dwd_orders",
                "source_column": "order_id",
                "target_table": "internal.shop_dm.dws_orders",
                "target_column": "order_id",
                "lineage_type": "direct",
                "expression": "order_id",
                "source_file": "dws_orders.sql",
            }
        ],
        {
            "hive": {
                "shop_dm": {
                    "dwd_orders": {
                        "order_id": "BIGINT",
                    }
                }
            },
            "internal": {
                "shop_dm": {
                    "dws_orders": {
                        "order_id": "BIGINT",
                    }
                }
            },
        },
    )

    tables_by_name = {table["name"]: table for table in output["tables"]}
    assert tables_by_name["hive.shop_dm.dwd_orders"]["full_name"] == (
        "hive.shop_dm.dwd_orders"
    )
    assert tables_by_name["dws_orders"]["full_name"] == "shop_dm.dws_orders"
    assert output["edges"][0]["source"]["id"] == (
        "hive.shop_dm.dwd_orders.order_id"
    )
    assert output["edges"][0]["target"]["id"] == "dws_orders.order_id"
    validate_lineage_v2(output)
