from copy import deepcopy

import pytest

import dw_refactor_agent.lineage.contract as lineage_contract
from dw_refactor_agent.lineage.contract import (
    LineageContractError,
    validate_job_dag_v2,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.model import LineageSnapshot
from tests.case_matrix import case_matrix


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


@case_matrix("version", [2.0, "2", True])
def test_v2_requires_integer_format_version(version):
    data = valid_lineage_v2()
    data["format_version"] = version

    with pytest.raises(LineageContractError, match="format_version"):
        validate_lineage_v2(data)

    dag = valid_job_dag_v2()
    dag["format_version"] = version
    with pytest.raises(LineageContractError, match="format_version"):
        validate_job_dag_v2(dag)


@case_matrix(
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


@case_matrix(
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


@case_matrix("dataset_type", ["managed", "process", "temporary", "external"])
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


@case_matrix("field", ["inputs", "outputs"])
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


@case_matrix(
    "field, invalid_ref",
    [
        ("inputs", "evil.internal.shop_dm.source"),
        ("inputs", "shop_dm..source"),
        ("outputs", "evil.internal.shop_dm.output"),
        ("outputs", "shop_dm..output"),
    ],
)
def test_v2_job_io_rejects_invalid_table_qualifier_segments(
    field,
    invalid_ref,
):
    data = valid_lineage_v2()
    data["jobs"][0][field] = [invalid_ref]

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith(f"lineage.jobs[0].{field}[0]:")
    assert "segments" in message


@case_matrix(
    "field, table_index, short_ref, alternate_full_name",
    [
        ("inputs", 0, "source", "external.other_dm.source"),
        ("outputs", 2, "output", "external.other_dm.output"),
    ],
)
def test_v2_job_io_rejects_ambiguous_short_table_refs(
    field,
    table_index,
    short_ref,
    alternate_full_name,
):
    data = valid_lineage_v2()
    alternate = deepcopy(data["tables"][table_index])
    alternate["name"] = f"alternate_{short_ref}"
    alternate["full_name"] = alternate_full_name
    data["tables"].append(alternate)
    data["jobs"][0][field] = [short_ref]

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith(f"lineage.jobs[0].{field}[0]:")
    assert "ambiguous table" in message
    assert data["tables"][table_index]["full_name"] in message
    assert alternate_full_name in message


def test_v2_job_io_unique_refs_share_canonical_duplicate_semantics():
    data = valid_lineage_v2()
    data["jobs"][0]["inputs"] = [
        "source",
        "INTERNAL.SHOP_DM.SOURCE",
    ]

    with pytest.raises(LineageContractError, match="duplicate"):
        validate_lineage_v2(data)


@case_matrix("edge_part", ["source", "target"])
def test_v2_edge_refs_must_be_typed_objects(edge_part):
    data = valid_lineage_v2()
    data["edges"][0][edge_part] = "internal.shop_dm.source.id"

    with pytest.raises(LineageContractError, match=edge_part):
        validate_lineage_v2(data)


@case_matrix(
    "edge_part, ref_type, ref_id, missing_kind",
    [
        (
            "source",
            "column",
            "internal.shop_dm.missing.id",
            "missing table",
        ),
        (
            "source",
            "column",
            "internal.shop_dm.source.missing",
            "missing column",
        ),
        (
            "target",
            "column",
            "internal.shop_dm.missing.id",
            "missing table",
        ),
        (
            "target",
            "column",
            "internal.shop_dm.output.missing",
            "missing column",
        ),
        (
            "target",
            "table",
            "internal.shop_dm.missing",
            "missing table",
        ),
    ],
)
def test_v2_edge_refs_must_resolve_to_table_column_metadata(
    edge_part,
    ref_type,
    ref_id,
    missing_kind,
):
    data = valid_lineage_v2()
    data["edges"][0][edge_part] = {"type": ref_type, "id": ref_id}

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith(f"lineage.edges[0].{edge_part}.id:")
    assert missing_kind in message


def test_v2_edge_refs_resolve_unique_suffixes_case_insensitively():
    data = valid_lineage_v2()
    data["edges"][0]["source"]["id"] = "SHOP_DM.SOURCE.ID"
    data["edges"][0]["target"]["id"] = "OUTPUT.ID"

    validate_lineage_v2(data)

    data["edges"][0]["target"] = {
        "type": "table",
        "id": "SHOP_DM.OUTPUT",
    }
    validate_lineage_v2(data)


@case_matrix(
    "edge_part, ref_type, ref_id",
    [
        (
            "source",
            "column",
            "evil.internal.shop_dm.source.id",
        ),
        (
            "source",
            "column",
            "shop_dm..source.id",
        ),
        (
            "target",
            "column",
            "evil.internal.shop_dm.output.id",
        ),
        (
            "target",
            "column",
            "shop_dm..output.id",
        ),
        (
            "target",
            "table",
            "evil.internal.shop_dm.output",
        ),
        (
            "target",
            "table",
            "shop_dm..output",
        ),
    ],
)
def test_v2_edge_refs_reject_invalid_table_qualifier_segments(
    edge_part,
    ref_type,
    ref_id,
):
    data = valid_lineage_v2()
    data["edges"][0][edge_part] = {"type": ref_type, "id": ref_id}

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith(f"lineage.edges[0].{edge_part}.id:")
    assert "segments" in message


@case_matrix(
    "full_name",
    [
        "evil.internal.shop_dm.source",
        "internal..shop_dm.source",
    ],
)
def test_v2_table_full_name_rejects_invalid_qualifier_segments(full_name):
    data = valid_lineage_v2()
    data["tables"][0]["full_name"] = full_name
    data["jobs"][0]["inputs"] = []
    data["edges"][0]["source"] = {"type": "literal", "value": 1}

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith("lineage.tables[0].full_name:")
    assert "segments" in message


class _IterationCountingDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()

    def items(self):
        self.iterations += 1
        return super().items()


def test_table_reference_index_avoids_metadata_rescans():
    source_key = ("internal", "shop_dm", "source")
    table_metadata = _IterationCountingDict(
        {
            source_key: ("internal.shop_dm.source", {"id"}),
            ("internal", "shop_dm", "output"): (
                "internal.shop_dm.output",
                {"id"},
            ),
        }
    )
    reference_index = lineage_contract._build_table_reference_index(
        table_metadata
    )
    build_iterations = table_metadata.iterations

    assert build_iterations > 0
    assert (
        lineage_contract._resolve_table_ref(
            "SOURCE",
            "lineage.edges[0].source.id",
            reference_index,
        )
        == source_key
    )
    assert (
        lineage_contract._resolve_table_ref(
            "SHOP_DM.SOURCE",
            "lineage.edges[1].source.id",
            reference_index,
        )
        == source_key
    )
    assert (
        lineage_contract._resolve_table_ref(
            "INTERNAL.SHOP_DM.SOURCE",
            "lineage.edges[2].source.id",
            reference_index,
        )
        == source_key
    )
    assert table_metadata.iterations == build_iterations


@case_matrix(
    "alternate_full_name, source_ref",
    [
        ("external.other_dm.source", "source.id"),
        ("external.shop_dm.source", "shop_dm.source.id"),
    ],
)
def test_v2_edge_refs_reject_ambiguous_table_suffixes(
    alternate_full_name,
    source_ref,
):
    data = valid_lineage_v2()
    data["tables"].append(
        {
            "name": "alternate_source",
            "full_name": alternate_full_name,
            "dataset_type": "external",
            "columns": [{"name": "id", "type": "BIGINT"}],
        }
    )
    data["edges"][0]["source"]["id"] = source_ref

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith("lineage.edges[0].source.id:")
    assert "ambiguous table" in message
    assert "internal.shop_dm.source" in message
    assert alternate_full_name in message


@case_matrix(
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


@case_matrix("value", [b"bytes", ("tuple",), {"set"}])
def test_v2_literal_source_must_be_a_json_scalar(value):
    data = valid_lineage_v2()
    data["edges"][0]["source"] = {"type": "literal", "value": value}

    with pytest.raises(LineageContractError, match="JSON scalar"):
        validate_lineage_v2(data)


@case_matrix(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_v2_literal_source_rejects_non_finite_numbers(value):
    data = valid_lineage_v2()
    data["edges"][0]["source"] = {"type": "literal", "value": value}

    with pytest.raises(LineageContractError, match="finite"):
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


@case_matrix(
    "dataset",
    [
        "evil.internal.shop_dm.stage",
        "shop_dm..stage",
    ],
)
def test_v2_diagnostic_dataset_rejects_invalid_qualifier_segments(dataset):
    data = valid_lineage_v2()
    data["diagnostics"] = [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": dataset,
            "reason": "not_found",
            "consumer_jobs": ["build_output"],
            "candidate_producer_jobs": [],
        }
    ]

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith("lineage.diagnostics[0].dataset:")
    assert "segments" in message


def test_v2_diagnostic_dataset_rejects_ambiguous_short_table_ref():
    data = valid_lineage_v2()
    alternate = deepcopy(data["tables"][1])
    alternate["name"] = "alternate_stage"
    alternate["full_name"] = "external.other_dm.stage"
    data["tables"].append(alternate)
    data["diagnostics"] = [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "stage",
            "reason": "not_found",
            "consumer_jobs": ["build_output"],
            "candidate_producer_jobs": [],
        }
    ]

    with pytest.raises(LineageContractError) as error:
        validate_lineage_v2(data)

    message = str(error.value)
    assert message.startswith("lineage.diagnostics[0].dataset:")
    assert "ambiguous table" in message
    assert "internal.shop_dm.stage" in message
    assert "external.other_dm.stage" in message


def test_v2_job_io_and_diagnostic_accept_quoted_casefold_qualification():
    data = valid_lineage_v2()
    data["jobs"][0]["inputs"] = ["`SOURCE`"]
    data["jobs"][0]["outputs"] = ["`SHOP_DM`.`OUTPUT`"]
    data["diagnostics"] = [
        {
            "code": "UNRESOLVED_DATASET_PRODUCER",
            "dataset": "`INTERNAL`.`SHOP_DM`.`STAGE`",
            "reason": "not_found",
            "consumer_jobs": ["BUILD_OUTPUT"],
            "candidate_producer_jobs": [],
        }
    ]

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


@case_matrix(
    "mutate, error_path",
    [
        (
            lambda data: data["edges"][0].__setitem__("job", "missing"),
            "lineage.edges[0].job:",
        ),
        (
            lambda data: data["edges"][0].__setitem__(
                "source_file", "mid/tasks/build_output.sql"
            ),
            "lineage.edges[0]:",
        ),
        (
            lambda data: data["jobs"][0].__setitem__(
                "inputs", "internal.shop_dm.source"
            ),
            "lineage.jobs[0].inputs:",
        ),
        (
            lambda data: data["edges"][0]["source"].__setitem__(
                "id", "internal.shop_dm.missing.id"
            ),
            "lineage.edges[0].source.id:",
        ),
        (
            lambda data: data["edges"][0]["target"].__setitem__(
                "id", "internal.shop_dm.output.missing"
            ),
            "lineage.edges[0].target.id:",
        ),
    ],
    ids=[
        "missing-job",
        "forbidden-edge-field",
        "malformed-job-inputs",
        "missing-source-table",
        "missing-target-column",
    ],
)
def test_lineage_snapshot_v2_validates_before_coercion(mutate, error_path):
    data = valid_lineage_v2()
    mutate(data)

    with pytest.raises(LineageContractError) as error:
        LineageSnapshot.from_dict("shop", data)

    assert str(error.value).startswith(error_path)


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


def test_lineage_snapshot_v1_ignores_v2_dataset_type_for_safe_downgrade():
    snapshot = LineageSnapshot.from_dict(
        "shop",
        {
            "tables": [
                {"name": "stage", "dataset_type": "process"},
                {
                    "name": "tmp_stage",
                    "dataset_type": "process",
                    "is_transient": True,
                },
            ],
            "edges": [],
        },
    )

    assert [table.dataset_type for table in snapshot.tables] == [
        "managed",
        "temporary",
    ]
    assert all("dataset_type" not in table.raw for table in snapshot.tables)
    assert all("dataset_type" not in table for table in snapshot.raw["tables"])
    assert all(
        "dataset_type" not in table for table in snapshot.to_dict()["tables"]
    )


@case_matrix("version", [2.0, "2", True, 3])
def test_lineage_snapshot_rejects_unsupported_explicit_versions(version):
    data = valid_lineage_v2()
    data["format_version"] = version

    with pytest.raises(ValueError, match="format_version"):
        LineageSnapshot.from_dict("shop", data)


def test_valid_job_dag_v2_passes_strict_validation():
    validate_job_dag_v2(valid_job_dag_v2())


def test_job_dag_v2_rejects_canonical_cycle_and_reports_jobs():
    data = {
        "format_version": 2,
        "jobs": ["Job_A", "job_b"],
        "data_dependencies": [
            {
                "upstream_job": "JOB_A",
                "downstream_job": "JOB_B",
                "datasets": ["internal.shop_dm.ab"],
            },
            {
                "upstream_job": "job_b",
                "downstream_job": "job_a",
                "datasets": ["internal.shop_dm.ba"],
            },
        ],
        "deps": {"Job_A": ["JOB_B"], "job_b": ["job_a"]},
        "rev": {"Job_A": ["JOB_B"], "job_b": ["job_a"]},
    }

    with pytest.raises(
        LineageContractError,
        match="Job_A -> job_b -> Job_A",
    ):
        validate_job_dag_v2(data)


def test_job_dag_v2_accepts_long_acyclic_chain_without_recursion():
    jobs = [f"job_{index:04d}" for index in range(1100)]
    dependencies = []
    deps = {job: [] for job in jobs}
    rev = {job: [] for job in jobs}
    for index, upstream in enumerate(jobs[:-1]):
        downstream = jobs[index + 1]
        dependencies.append(
            {
                "upstream_job": upstream,
                "downstream_job": downstream,
                "datasets": [f"internal.shop_dm.stage_{index:04d}"],
            }
        )
        deps[upstream].append(downstream)
        rev[downstream].append(upstream)

    validate_job_dag_v2(
        {
            "format_version": 2,
            "jobs": jobs,
            "data_dependencies": dependencies,
            "deps": deps,
            "rev": rev,
        }
    )


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
