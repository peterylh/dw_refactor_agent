from copy import deepcopy

import pytest

from dw_refactor_agent.lineage.contract import (
    LineageContractError,
    validate_job_dag_v2,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.model import LineageSnapshot


def valid_lineage_v2():
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "source",
                "full_name": "internal.shop_dm.source",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
            {
                "name": "stage",
                "full_name": "internal.shop_dm.stage",
                "dataset_type": "process",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
            {
                "name": "output",
                "full_name": "internal.shop_dm.output",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
        ],
        "jobs": [
            {
                "name": "build_output",
                "source_file": "mid/tasks/build_output.sql",
                "inputs": ["internal.shop_dm.source"],
                "outputs": ["internal.shop_dm.output"],
            }
        ],
        "edges": [
            {
                "source": {
                    "type": "column",
                    "id": "internal.shop_dm.source.id",
                },
                "target": {
                    "type": "column",
                    "id": "internal.shop_dm.output.id",
                },
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": "build_output",
            }
        ],
        "diagnostics": [],
    }


def valid_job_dag_v2():
    return {
        "format_version": 2,
        "jobs": ["build_output", "prepare_stage"],
        "data_dependencies": [
            {
                "upstream_job": "prepare_stage",
                "downstream_job": "build_output",
                "datasets": ["internal.shop_dm.stage"],
            }
        ],
        "deps": {
            "build_output": [],
            "prepare_stage": ["build_output"],
        },
        "rev": {
            "build_output": ["prepare_stage"],
            "prepare_stage": [],
        },
    }


def test_valid_lineage_v2_passes_strict_validation():
    validate_lineage_v2(valid_lineage_v2())


@pytest.mark.parametrize("version", [2.0, "2", True])
def test_v2_requires_integer_format_version(version):
    data = valid_lineage_v2()
    data["format_version"] = version

    with pytest.raises(LineageContractError, match="format_version"):
        validate_lineage_v2(data)

    dag = valid_job_dag_v2()
    dag["format_version"] = version
    with pytest.raises(LineageContractError, match="format_version"):
        validate_job_dag_v2(dag)


@pytest.mark.parametrize(
    "missing_key",
    [
        "format_version",
        "tables",
        "jobs",
        "edges",
        "diagnostics",
    ],
)
def test_v2_requires_exact_top_level_keys(missing_key):
    data = valid_lineage_v2()
    data.pop(missing_key)

    with pytest.raises(LineageContractError, match=missing_key):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["extension"] = []
    with pytest.raises(LineageContractError, match="extension"):
        validate_lineage_v2(data)


@pytest.mark.parametrize(
    "record_name, mutate",
    [
        ("table", lambda data: data["tables"][0].update({"extension": True})),
        (
            "column",
            lambda data: data["tables"][0]["columns"][0].update(
                {"extension": True}
            ),
        ),
        ("job", lambda data: data["jobs"][0].update({"extension": True})),
        ("edge", lambda data: data["edges"][0].update({"extension": True})),
        (
            "reference",
            lambda data: data["edges"][0]["source"].update(
                {"extension": True}
            ),
        ),
    ],
)
def test_v2_rejects_unknown_nested_fields(record_name, mutate):
    data = valid_lineage_v2()
    mutate(data)

    with pytest.raises(LineageContractError, match="extension"):
        validate_lineage_v2(data)


@pytest.mark.parametrize(
    "dataset_type", ["managed", "process", "temporary", "external"]
)
def test_v2_accepts_all_dataset_types(dataset_type):
    data = valid_lineage_v2()
    data["tables"][0]["dataset_type"] = dataset_type

    validate_lineage_v2(data)


def test_v2_rejects_unknown_dataset_type():
    data = valid_lineage_v2()
    data["tables"][0]["dataset_type"] = "transient"

    with pytest.raises(LineageContractError, match="transient"):
        validate_lineage_v2(data)


def test_v2_edge_requires_job_and_rejects_source_file():
    data = valid_lineage_v2()
    data["edges"][0]["source_file"] = "job.sql"
    with pytest.raises(LineageContractError, match="source_file"):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["edges"][0].pop("job")
    with pytest.raises(LineageContractError, match="job"):
        validate_lineage_v2(data)


def test_v2_edge_job_must_exist_case_insensitively():
    data = valid_lineage_v2()
    data["edges"][0]["job"] = "BUILD_OUTPUT"
    validate_lineage_v2(data)

    data["edges"][0]["job"] = "missing"
    with pytest.raises(LineageContractError, match="missing"):
        validate_lineage_v2(data)


def test_v2_job_names_are_unique_case_insensitively():
    data = valid_lineage_v2()
    duplicate = deepcopy(data["jobs"][0])
    duplicate["name"] = "BUILD_OUTPUT"
    duplicate["source_file"] = "ads/tasks/build_output.sql"
    data["jobs"].append(duplicate)

    with pytest.raises(LineageContractError, match="BUILD_OUTPUT"):
        validate_lineage_v2(data)


@pytest.mark.parametrize("field", ["inputs", "outputs"])
def test_v2_job_io_must_be_sorted_unique_table_name_arrays(field):
    data = valid_lineage_v2()
    data["jobs"][0][field] = "internal.shop_dm.source"
    with pytest.raises(LineageContractError, match=field):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["jobs"][0][field] = [
        "internal.shop_dm.source",
        "INTERNAL.SHOP_DM.SOURCE",
    ]
    with pytest.raises(LineageContractError, match="duplicate"):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["jobs"][0][field] = [
        "internal.shop_dm.stage",
        "internal.shop_dm.output",
    ]
    with pytest.raises(LineageContractError, match="sorted"):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["jobs"][0][field] = ["internal.shop_dm.missing"]
    with pytest.raises(LineageContractError, match="missing"):
        validate_lineage_v2(data)


@pytest.mark.parametrize("edge_part", ["source", "target"])
def test_v2_edge_refs_must_be_typed_objects(edge_part):
    data = valid_lineage_v2()
    data["edges"][0][edge_part] = "internal.shop_dm.source.id"

    with pytest.raises(LineageContractError, match=edge_part):
        validate_lineage_v2(data)


@pytest.mark.parametrize(
    "source",
    [
        {"type": "literal", "value": "ALL"},
        {"type": "expression", "expression": "CURRENT_DATE()"},
    ],
)
def test_v2_edge_accepts_typed_constant_sources(source):
    data = valid_lineage_v2()
    data["edges"][0]["source"] = source

    validate_lineage_v2(data)


@pytest.mark.parametrize("value", [b"bytes", ("tuple",), {"set"}])
def test_v2_literal_source_must_be_a_json_scalar(value):
    data = valid_lineage_v2()
    data["edges"][0]["source"] = {"type": "literal", "value": value}

    with pytest.raises(LineageContractError, match="JSON scalar"):
        validate_lineage_v2(data)


def test_v2_diagnostics_use_known_reason_and_jobs():
    data = valid_lineage_v2()
    data["diagnostics"] = [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "internal.shop_dm.stage",
            "reason": "not_found",
            "consumer_jobs": ["BUILD_OUTPUT"],
            "candidate_producer_jobs": [],
        }
    ]
    validate_lineage_v2(data)

    data["diagnostics"][0]["reason"] = "guessed"
    with pytest.raises(LineageContractError, match="guessed"):
        validate_lineage_v2(data)

    data = valid_lineage_v2()
    data["diagnostics"] = [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "internal.shop_dm.stage",
            "reason": "not_found",
            "consumer_jobs": ["missing"],
            "candidate_producer_jobs": [],
        }
    ]
    with pytest.raises(LineageContractError, match="missing"):
        validate_lineage_v2(data)


def test_lineage_snapshot_v2_prefers_explicit_jobs_and_fields():
    snapshot = LineageSnapshot.from_dict("shop", valid_lineage_v2())

    assert snapshot.tables[1].dataset_type == "process"
    assert snapshot.jobs[0].name == "build_output"
    assert snapshot.jobs[0].source_file == "mid/tasks/build_output.sql"
    assert snapshot.jobs[0].inputs == ("internal.shop_dm.source",)
    assert snapshot.jobs[0].outputs == ("internal.shop_dm.output",)
    assert snapshot.edges[0].job == "build_output"
    assert snapshot.edges[0].source_file == ""


def test_lineage_snapshot_v1_derives_jobs_and_keeps_transient_safe():
    snapshot = LineageSnapshot.from_dict(
        "shop",
        {
            "tables": [
                {
                    "name": "tmp_stage",
                    "is_transient": True,
                    "transient_sources": ["mid/tasks/build.sql"],
                },
                {"name": "dws_output"},
            ],
            "edges": [
                {
                    "source": "tmp_stage.id",
                    "target": "dws_output.id",
                    "job": "unexpected_v2_field",
                    "source_file": "mid/tasks/build.sql",
                }
            ],
        },
    )

    assert snapshot.tables[0].dataset_type == "temporary"
    assert snapshot.tables[0].is_transient is True
    assert snapshot.tables[1].dataset_type == "managed"
    assert snapshot.jobs[0].name == "build"
    assert snapshot.jobs[0].inputs == ()
    assert snapshot.jobs[0].outputs == ()
    assert snapshot.edges[0].job == "build"
    assert snapshot.edges[0].source_file == "mid/tasks/build.sql"


@pytest.mark.parametrize("version", [2.0, "2", True, 3])
def test_lineage_snapshot_rejects_unsupported_explicit_versions(version):
    data = valid_lineage_v2()
    data["format_version"] = version

    with pytest.raises(ValueError, match="format_version"):
        LineageSnapshot.from_dict("shop", data)


def test_valid_job_dag_v2_passes_strict_validation():
    validate_job_dag_v2(valid_job_dag_v2())


def test_job_dag_v2_rejects_unknown_job_references():
    data = valid_job_dag_v2()
    data["data_dependencies"][0]["upstream_job"] = "missing"

    with pytest.raises(LineageContractError, match="missing"):
        validate_job_dag_v2(data)


def test_job_dag_v2_requires_consistent_dependency_views():
    data = valid_job_dag_v2()
    data["deps"]["prepare_stage"] = []

    with pytest.raises(LineageContractError, match="data_dependencies"):
        validate_job_dag_v2(data)


def test_job_dag_v2_rejects_unknown_fields():
    data = valid_job_dag_v2()
    data["extension"] = []
    with pytest.raises(LineageContractError, match="extension"):
        validate_job_dag_v2(data)

    data = valid_job_dag_v2()
    data["data_dependencies"][0]["extension"] = []
    with pytest.raises(LineageContractError, match="extension"):
        validate_job_dag_v2(data)
