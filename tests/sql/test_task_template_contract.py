from copy import deepcopy
from datetime import date

import pytest
import yaml

from dw_refactor_agent.sql.task_template import (
    ContractValidationError,
    build_task_definition,
    load_task_definition,
    parse_contract,
)


def _valid_contract():
    return {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "etl_date",
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": True,
            }
        ],
        "project_params": [
            {
                "prop": "cdm_schema",
                "type": "IDENTIFIER",
                "source": "project.cdm_schema",
                "required": True,
            }
        ],
        "local_params": [
            {
                "prop": "biz_date",
                "direct": "IN",
                "type": "DATE",
                "value": "${etl_date}",
                "render": {"format": "yyyyMMdd"},
            },
            {
                "prop": "run_table",
                "direct": "IN",
                "type": "IDENTIFIER",
                "value": {
                    "derive": {
                        "from": "biz_date",
                        "operation": "format_date",
                        "format": "yyyyMMdd",
                        "prefix": "tmp_run_",
                    }
                },
            },
        ],
        "usage": {
            "slices": [{"prop": "biz_date", "parameter": "etl_date"}],
            "dynamic_relations": [
                {"prop": "run_table", "lifecycle": "invocation"}
            ],
        },
    }


def _valid_sql():
    return (
        "DELETE FROM ${cdm_schema}.target "
        "WHERE data_dt = ${biz_date};\n"
        "DROP TABLE IF EXISTS ${run_table};\n"
    )


def test_contract_normalizes_dolphin_style_parameters_and_variable_usage():
    contract = parse_contract(_valid_contract())

    normalized = contract.as_dict()
    assert normalized["startup_params"][0] == {
        "prop": "etl_date",
        "type": "DATE",
        "overrideable": False,
        "source": "invocation.etl_date",
        "required": True,
    }
    assert normalized["local_params"][0]["value"] == "${etl_date}"
    assert normalized["usage"] == _valid_contract()["usage"]
    assert [item.prop for item in contract.parameters] == [
        "etl_date",
        "cdm_schema",
        "biz_date",
        "run_table",
    ]
    assert contract.usage.referenced_props() == ("biz_date", "run_table")


def test_loader_returns_path_independent_digests_and_pair_summary(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    definitions = []
    for directory in (first_dir, second_dir):
        sql_path = directory / "job.sql"
        yaml_path = directory / "job.yaml"
        sql_path.write_text(_valid_sql(), encoding="utf-8")
        yaml_path.write_text(
            yaml.safe_dump(_valid_contract(), sort_keys=False),
            encoding="utf-8",
        )
        definitions.append(load_task_definition(sql_path, yaml_path))

    assert definitions[0].normalized_summary() == (
        definitions[1].normalized_summary()
    )
    assert definitions[0].placeholder_names == (
        "cdm_schema",
        "biz_date",
        "run_table",
    )
    assert definitions[0].sql_path == first_dir / "job.sql"


def test_contract_digest_normalizes_yaml_temporal_scalars():
    raw = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "etl_date",
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": False,
                "default": date(2024, 2, 29),
            }
        ],
    }

    definition = build_task_definition("SELECT ${etl_date};", raw)

    assert definition.contract.as_dict()["startup_params"][0]["default"] == (
        "2024-02-29"
    )
    assert definition.contract_digest.startswith("sha256:")


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (lambda value: value.update({"layer": "DWD"}), "unknown_field"),
        (
            lambda value: value["local_params"][0].update({"direct": "OUT"}),
            "invalid_direction",
        ),
        (
            lambda value: value["startup_params"][0].update(
                {"prop": "ETL_DATE"}
            ),
            "invalid_prop",
        ),
        (
            lambda value: value["local_params"][0].update(
                {"value": "date=${etl_date}"}
            ),
            "invalid_reference",
        ),
    ],
)
def test_contract_rejects_unknown_fields_and_unsafe_parameter_shapes(
    mutate,
    error_code,
):
    raw = deepcopy(_valid_contract())
    mutate(raw)

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == f"template.contract.{error_code}"
    assert raised.value.as_dict() == {
        "code": raised.value.code,
        "path": list(raised.value.path),
        "message": str(raised.value),
    }


def test_contract_rejects_unknown_references_and_dependency_cycles():
    unknown = deepcopy(_valid_contract())
    unknown["local_params"][0]["value"] = "${missing_date}"
    with pytest.raises(ContractValidationError) as raised:
        parse_contract(unknown)
    assert raised.value.code == "template.contract.unknown_reference"

    cycle = deepcopy(_valid_contract())
    cycle["local_params"][0]["value"] = "${run_table}"
    cycle["local_params"][0]["type"] = "IDENTIFIER"
    cycle["local_params"][0].pop("render")
    cycle["local_params"][1]["value"] = "${biz_date}"
    with pytest.raises(ContractValidationError) as raised:
        parse_contract(cycle)
    assert raised.value.code == "template.contract.dependency_cycle"
    assert "biz_date -> run_table -> biz_date" in str(raised.value)


@pytest.mark.parametrize(
    ("sql", "error_code"),
    [
        (
            "SELECT '${biz_date}' FROM ${cdm_schema}.target; "
            "DROP TABLE ${run_table};",
            "invalid_context",
        ),
        (
            "SELECT 1 -- ${biz_date}\nFROM ${cdm_schema}.target; "
            "DROP TABLE ${run_table};",
            "invalid_context",
        ),
        (
            "DELETE FROM ${cdm_schema}.target WHERE dt=x_${biz_date}; "
            "DROP TABLE ${run_table};",
            "embedded_placeholder",
        ),
        (
            "DELETE FROM ${cdm_schema}.target WHERE dt=${missing}; "
            "DROP TABLE ${run_table};",
            "unknown_parameter",
        ),
        (
            "DELETE FROM target WHERE dt=${cdm_schema}; "
            "DROP TABLE ${run_table}; SELECT ${biz_date};",
            "invalid_identifier_context",
        ),
    ],
)
def test_sql_contract_rejects_quoted_embedded_unknown_and_mistyped_slots(
    sql,
    error_code,
):
    with pytest.raises(ContractValidationError) as raised:
        build_task_definition(sql, _valid_contract())

    assert raised.value.code == f"template.sql.{error_code}"


def test_strict_contract_rejects_declared_but_unused_variables():
    raw = deepcopy(_valid_contract())
    raw["local_params"].append(
        {
            "prop": "unused_date",
            "direct": "IN",
            "type": "DATE",
            "value": "${etl_date}",
        }
    )

    with pytest.raises(ContractValidationError) as raised:
        build_task_definition(_valid_sql(), raw)

    assert raised.value.code == "template.contract.unused_parameter"
    assert "unused_date" in str(raised.value)


def test_dynamic_relation_usage_requires_identifier_type():
    raw = deepcopy(_valid_contract())
    raw["local_params"][1]["type"] = "VARCHAR"

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_dynamic_relation"


@pytest.mark.parametrize(
    "parameter_path",
    [
        ("startup_params", 0),
        ("local_params", 0),
    ],
)
def test_contract_rejects_removed_sensitive_field(parameter_path):
    raw = deepcopy(_valid_contract())
    section, index = parameter_path
    raw[section][index]["sensitive"] = True

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.unknown_field"
    assert raised.value.path == parameter_path
    assert "sensitive" in str(raised.value)


def test_sql_scanner_respects_backslash_escaped_double_quotes():
    sql = (
        'SELECT "prefix\\" ${biz_date}" FROM ${cdm_schema}.target; '
        "DROP TABLE ${run_table};"
    )

    with pytest.raises(ContractValidationError) as raised:
        build_task_definition(sql, _valid_contract())

    assert raised.value.code == "template.sql.invalid_context"


@pytest.mark.parametrize(
    ("sql", "error_code"),
    [
        (
            "DROP TABLE ${biz_date}; SELECT ${run_table} FROM target;",
            "invalid_literal_context",
        ),
        (
            "SELECT 1 -- FROM\n${run_table}; SELECT ${biz_date}; "
            "SELECT ${cdm_schema}.target;",
            "invalid_identifier_context",
        ),
    ],
)
def test_sql_slot_types_are_bilateral_and_comments_do_not_create_slots(
    sql,
    error_code,
):
    with pytest.raises(ContractValidationError) as raised:
        build_task_definition(sql, _valid_contract())

    assert raised.value.code == f"template.sql.{error_code}"


def test_identifier_schema_qualifier_is_valid_for_function_calls():
    sql = (
        "SELECT ${cdm_schema}.table_check(${biz_date}); "
        "DROP TABLE ${run_table};"
    )

    definition = build_task_definition(sql, _valid_contract())

    assert definition.placeholder_names == (
        "cdm_schema",
        "biz_date",
        "run_table",
    )


@pytest.mark.parametrize(
    "yaml_text",
    [
        "version: 1\nversion: 1\nstrict: true\n",
        (
            "version: 1\nstrict: true\nlocal_params:\n"
            "  - prop: value\n    direct: IN\n    type: VARCHAR\n"
            "    value: first\n    value: second\n"
        ),
    ],
)
def test_yaml_loader_rejects_duplicate_keys_at_every_level(
    tmp_path, yaml_text
):
    sql_path = tmp_path / "task.sql"
    yaml_path = tmp_path / "task.yaml"
    sql_path.write_text("SELECT 1;", encoding="utf-8")
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ContractValidationError) as raised:
        load_task_definition(sql_path, yaml_path)

    assert raised.value.code == "template.contract.read_failed"
    assert "duplicate key" in str(raised.value)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["startup_params"][0].update({"type": "VARCHAR"}),
        lambda value: (
            value["local_params"][0].update({"type": "VARCHAR"}),
            value["local_params"][0].pop("render"),
        ),
        lambda value: value["local_params"][1].update({"type": "DATE"}),
    ],
)
def test_contract_validates_reference_and_derivation_type_signatures(mutate):
    raw = deepcopy(_valid_contract())
    mutate(raw)

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code in {
        "template.contract.incompatible_reference",
        "template.contract.invalid_derivation_type",
    }


@pytest.mark.parametrize(
    "section",
    ["local", "default"],
)
def test_contract_prevalidates_static_and_default_values_without_echoing_them(
    section,
):
    secret = "not-an-integer-secret"
    raw = {
        "version": 1,
        "strict": True,
    }
    if section == "local":
        raw["local_params"] = [
            {
                "prop": "secret_value",
                "direct": "IN",
                "type": "INTEGER",
                "value": secret,
            }
        ]
    else:
        raw["startup_params"] = [
            {
                "prop": "secret_value",
                "type": "INTEGER",
                "source": "invocation.secret_value",
                "required": False,
                "default": secret,
            }
        ]

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_static_value"
    assert secret not in str(raised.value)


def test_cross_scope_candidates_require_compatible_overrideable_definitions():
    raw = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "shared",
                "type": "VARCHAR",
                "source": "invocation.shared",
                "required": False,
                "overrideable": True,
            }
        ],
        "project_params": [
            {
                "prop": "shared",
                "type": "INTEGER",
                "source": "project.shared",
                "required": False,
                "overrideable": True,
            }
        ],
    }

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)
    assert raised.value.code == "template.contract.conflicting_candidate"

    raw["project_params"][0]["type"] = "VARCHAR"
    raw["project_params"][0]["overrideable"] = False
    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)
    assert raised.value.code == "template.contract.forbidden_shadowing"


@pytest.mark.parametrize(
    ("data_type", "secret"),
    [
        ("VARCHAR", "contains\x00nul"),
        ("DOUBLE", "1E+1000000000"),
    ],
)
def test_contract_prevalidates_final_sql_tokens_without_echoing_values(
    data_type,
    secret,
):
    raw = {
        "version": 1,
        "strict": True,
        "local_params": [
            {
                "prop": "secret_value",
                "direct": "IN",
                "type": data_type,
                "value": secret,
            }
        ],
    }

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_static_value"
    assert secret not in str(raised.value)


@pytest.mark.parametrize(
    "yaml_text",
    [
        "? [a, b]\n: c\nversion: 1\n",
        "version: 1\n1: invalid\n",
    ],
)
def test_yaml_loader_rejects_non_string_mapping_keys(tmp_path, yaml_text):
    sql_path = tmp_path / "task.sql"
    yaml_path = tmp_path / "task.yaml"
    sql_path.write_text("SELECT 1;", encoding="utf-8")
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ContractValidationError) as raised:
        load_task_definition(sql_path, yaml_path)

    assert raised.value.code == "template.contract.read_failed"
    assert "mapping keys must be scalar strings" in str(raised.value)


def test_in_memory_contract_rejects_non_string_field_names_structurally():
    with pytest.raises(ContractValidationError) as raised:
        parse_contract({"version": 1, 1: "invalid"})

    assert raised.value.code == "template.contract.invalid_field_name"


def test_contract_rejects_empty_static_lists_before_sql_rendering():
    raw = {
        "version": 1,
        "strict": True,
        "local_params": [
            {
                "prop": "values",
                "direct": "IN",
                "type": "LIST",
                "value": [],
                "render": {"item_type": "INTEGER"},
            }
        ],
    }

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_static_value"


@pytest.mark.parametrize(
    ("data_type", "field", "format_name"),
    [
        ("DATE", "input_format", "HH:mm:ss"),
        ("DATE", "format", "HH:mm:ss"),
        ("DATE", "format", "yyyy-MM-dd HH:mm:ss"),
        ("TIME", "input_format", "yyyy-MM-dd"),
        ("TIME", "format", "yyyyMMdd"),
        ("TIME", "format", "yyyy-MM-dd HH:mm:ss"),
        ("TIMESTAMP", "input_format", "yyyy-MM-dd"),
        ("TIMESTAMP", "input_format", "HH:mm:ss"),
    ],
)
def test_contract_rejects_temporal_formats_that_invent_components(
    data_type,
    field,
    format_name,
):
    raw = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "value",
                "type": data_type,
                "source": "invocation.value",
                "required": True,
                "render": {field: format_name},
            }
        ],
    }

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_format"
    assert raised.value.path[-1] == field


@pytest.mark.parametrize(
    ("data_type", "input_format", "output_format"),
    [
        ("DATE", "yyyy-MM-dd", "yyyy"),
        ("DATE", "yyyyMMdd", "yyyyMM"),
        ("TIME", "HH:mm:ss", "HH:mm:ss"),
        ("TIMESTAMP", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd"),
        ("TIMESTAMP", "yyyyMMddHHmmss", "HH:mm:ss"),
        ("TIMESTAMP", "yyyyMMddHHmmss", "yyyyMMddHHmmss"),
    ],
)
def test_contract_accepts_lossless_temporal_inputs_and_safe_outputs(
    data_type,
    input_format,
    output_format,
):
    contract = parse_contract(
        {
            "version": 1,
            "strict": True,
            "startup_params": [
                {
                    "prop": "value",
                    "type": data_type,
                    "source": "invocation.value",
                    "required": True,
                    "render": {
                        "input_format": input_format,
                        "format": output_format,
                    },
                }
            ],
        }
    )

    render = contract.startup_params[0].render
    assert render.input_format == input_format
    assert render.output_format == output_format


def test_contract_rejects_yaml_date_as_timestamp_default():
    raw = yaml.safe_load(
        """version: 1
strict: true
startup_params:
  - prop: run_ts
    type: TIMESTAMP
    source: invocation.run_ts
    required: false
    default: 2025-03-01
"""
    )

    assert isinstance(raw["startup_params"][0]["default"], date)
    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_static_value"


def test_contract_rejects_temporal_derivations_that_invent_components():
    raw = {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "etl_date",
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": True,
            }
        ],
        "local_params": [
            {
                "prop": "derived_ts",
                "direct": "IN",
                "type": "TIMESTAMP",
                "value": {
                    "derive": {
                        "from": "etl_date",
                        "operation": "add_days",
                        "amount": 1,
                    }
                },
            }
        ],
    }

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_derivation_type"


def test_contract_rejects_time_format_for_date_derivation_source():
    raw = deepcopy(_valid_contract())
    raw["local_params"][1]["value"]["derive"]["format"] = "HH:mm:ss"

    with pytest.raises(ContractValidationError) as raised:
        parse_contract(raw)

    assert raised.value.code == "template.contract.invalid_format"
    assert raised.value.path[-1] == "format"
