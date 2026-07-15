import pytest

from dw_refactor_agent.lineage.job_lineage import (
    build_job_records,
    job_name_from_source_file,
    resolve_job_dependencies,
)


def test_job_name_and_records_use_source_stem_and_external_io():
    assert job_name_from_source_file("mid/tasks/prepare_sales.sql") == (
        "prepare_sales"
    )

    jobs = build_job_records(
        [
            {
                "source_file": "mid/tasks/prepare_sales.sql",
                "input_tables": ["src", "tmp_t"],
                "output_tables": ["out"],
                "temporary_tables": [],
                "local_lifecycle_tables": [{"name": "tmp_t"}],
            }
        ],
        lambda table: f"internal.shop_dm.{table}",
    )

    assert jobs == [
        {
            "name": "prepare_sales",
            "source_file": "mid/tasks/prepare_sales.sql",
            "inputs": ["internal.shop_dm.src"],
            "outputs": ["internal.shop_dm.out"],
        }
    ]


def test_build_job_records_rejects_duplicate_source_stems():
    with pytest.raises(ValueError, match="duplicate Job name.*load"):
        build_job_records(
            [
                {"source_file": "mid/tasks/load.sql"},
                {"source_file": "ads/tasks/load.sql"},
            ],
            lambda table: table,
        )


def test_multiple_process_producers_emit_diagnostic_without_guessing():
    dependencies, diagnostics = resolve_job_dependencies(
        [
            {"name": "producer_b", "inputs": [], "outputs": ["db.t"]},
            {"name": "consumer", "inputs": ["DB.T"], "outputs": []},
            {"name": "producer_a", "inputs": [], "outputs": ["Db.t"]},
        ],
        [{"full_name": "db.t", "dataset_type": "process"}],
    )

    assert dependencies == []
    assert diagnostics == [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "db.t",
            "reason": "multiple_candidates",
            "consumer_jobs": ["consumer"],
            "candidate_producer_jobs": ["producer_a", "producer_b"],
        }
    ]


def test_missing_process_and_temporary_producers_are_diagnosed_together():
    dependencies, diagnostics = resolve_job_dependencies(
        [
            {
                "name": "consumer_b",
                "inputs": ["db.process_t"],
                "outputs": [],
            },
            {
                "name": "consumer_a",
                "inputs": ["db.process_t", "db.temp_t"],
                "outputs": [],
            },
        ],
        [
            {"full_name": "db.process_t", "dataset_type": "process"},
            {"full_name": "db.temp_t", "dataset_type": "temporary"},
        ],
    )

    assert dependencies == []
    assert diagnostics == [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "db.process_t",
            "reason": "not_found",
            "consumer_jobs": ["consumer_a", "consumer_b"],
            "candidate_producer_jobs": [],
        },
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "db.temp_t",
            "reason": "not_found",
            "consumer_jobs": ["consumer_a"],
            "candidate_producer_jobs": [],
        },
    ]


def test_dependencies_are_case_insensitive_qualified_and_aggregated():
    dependencies, diagnostics = resolve_job_dependencies(
        [
            {
                "name": "producer",
                "inputs": [],
                "outputs": ["CAT_A.DB.T1", "cat_a.db.t2", "cat_b.db.t1"],
            },
            {
                "name": "consumer",
                "inputs": ["cat_a.db.t2", "cat_a.db.t1"],
                "outputs": [],
            },
        ],
        [
            {"full_name": "cat_a.db.t1", "dataset_type": "process"},
            {"full_name": "cat_a.db.t2", "dataset_type": "process"},
            {"full_name": "cat_b.db.t1", "dataset_type": "process"},
        ],
    )

    assert dependencies == [
        {
            "upstream_job": "producer",
            "downstream_job": "consumer",
            "datasets": ["cat_a.db.t1", "cat_a.db.t2"],
        }
    ]
    assert diagnostics == []
