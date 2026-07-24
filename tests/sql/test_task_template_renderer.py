from copy import deepcopy
from datetime import date
from decimal import localcontext

import pytest
import yaml

from dw_refactor_agent.sql.task_template import (
    RENDERER_VERSION,
    RenderBindings,
    RenderMode,
    TemplateRenderError,
    build_task_definition,
    render_task,
    renderer_semantics_digest,
)
from dw_refactor_agent.sql.task_template.contract import CONTRACT_VERSION
from dw_refactor_agent.sql.task_template.derivation import (
    DERIVATION_OPERATIONS,
)
from dw_refactor_agent.sql.task_template.loader import (
    canonical_json_bytes,
    sha256_bytes,
)
from dw_refactor_agent.sql.task_template.types import ParameterType


def _render_contract():
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
                "prop": "source_table",
                "type": "QUALIFIED_IDENTIFIER",
                "source": "project.source_table",
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
                "prop": "biz_date_minus_1",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": "biz_date",
                        "operation": "add_days",
                        "amount": -1,
                    }
                },
                "render": {"format": "yyyyMMdd"},
            },
            {
                "prop": "month_end",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": "biz_date",
                        "operation": "month_end",
                    }
                },
                "render": {"format": "yyyyMMdd"},
            },
            {
                "prop": "previous_year_end",
                "direct": "IN",
                "type": "DATE",
                "value": {
                    "derive": {
                        "from": "biz_date",
                        "operation": "previous_year_end",
                    }
                },
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
            {
                "prop": "org_code",
                "direct": "IN",
                "type": "VARCHAR",
                "value": "O'Reilly\\bank",
                "overrideable": True,
            },
            {
                "prop": "row_limit",
                "direct": "IN",
                "type": "INTEGER",
                "value": 100,
            },
            {
                "prop": "enabled",
                "direct": "IN",
                "type": "BOOLEAN",
                "value": True,
            },
            {
                "prop": "ratios",
                "direct": "IN",
                "type": "LIST",
                "value": ["1.50", 2],
                "render": {"item_type": "DOUBLE"},
            },
        ],
        "usage": {
            "dynamic_relations": [
                {"prop": "run_table", "lifecycle": "invocation"}
            ]
        },
    }


def test_renderer_semantics_version_rejects_v1_identity():
    old_v1_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "renderer_version": "task-template-renderer-v1",
                "contract_version": CONTRACT_VERSION,
                "parameter_types": sorted(
                    item.value for item in ParameterType
                ),
                "derivation_operations": sorted(DERIVATION_OPERATIONS),
                "literal_policy": "renderer_emits_complete_sql_tokens",
                "identifier_policy": "ascii_segments_backtick_quoted",
            }
        )
    )

    assert RENDERER_VERSION == "task-template-renderer-v2"
    assert renderer_semantics_digest() != old_v1_digest


def _render_sql():
    return """INSERT INTO ${run_table}
SELECT ${biz_date} AS biz_date
FROM ${source_table}
WHERE data_dt BETWEEN ${biz_date_minus_1} AND ${month_end}
  AND prior_year_end = ${previous_year_end}
  AND org_code = ${org_code}
  AND enabled = ${enabled}
  AND ratio IN ${ratios}
LIMIT ${row_limit};
"""


def _definition():
    return build_task_definition(_render_sql(), _render_contract())


def _bindings(etl_date="2024-02-29", **overrides):
    return RenderBindings(
        startup={"etl_date": etl_date},
        project={"source_table": "cdm.p03_cust_info"},
        overrides=overrides,
    )


def test_execution_render_emits_complete_safe_tokens_and_date_derivations():
    result = render_task(
        _definition(), mode=RenderMode.EXECUTION, bindings=_bindings()
    )

    assert (
        result.sql
        == """INSERT INTO `tmp_run_20240229`
SELECT '20240229' AS biz_date
FROM `cdm`.`p03_cust_info`
WHERE data_dt BETWEEN '20240228' AND '20240229'
  AND prior_year_end = '20231231'
  AND org_code = 'O''Reilly\\\\bank'
  AND enabled = TRUE
  AND ratio IN (1.5, 2)
LIMIT 100;
"""
    )
    assert result.public_bindings["org_code"] == "O'Reilly\\bank"
    assert result.public_bindings["run_table"] == "tmp_run_20240229"
    assert result.normalized_summary()["config_digest"].startswith("sha256:")


@pytest.mark.parametrize(
    ("operation", "amount", "etl_date", "expected"),
    [
        ("add_days", -1, "2025-01-01", "2024-12-31"),
        ("add_months", -1, "2024-03-31", "2024-02-29"),
        ("add_years", -1, "2024-02-29", "2023-02-28"),
        ("month_start", None, "2024-02-29", "2024-02-01"),
        ("month_end", None, "2023-02-10", "2023-02-28"),
        ("year_start", None, "2024-02-29", "2024-01-01"),
        ("year_end", None, "2024-02-29", "2024-12-31"),
        ("previous_year_end", None, "2024-02-29", "2023-12-31"),
    ],
)
def test_date_derivation_matrix(operation, amount, etl_date, expected):
    derived = {
        "from": "etl_date",
        "operation": operation,
    }
    if amount is not None:
        derived["amount"] = amount
    contract = {
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
                "prop": "derived_date",
                "direct": "IN",
                "type": "DATE",
                "value": {"derive": derived},
            }
        ],
    }
    definition = build_task_definition("SELECT ${derived_date};", contract)

    rendered = render_task(
        definition,
        mode="analysis",
        bindings=RenderBindings(startup={"etl_date": etl_date}),
    )

    assert rendered.sql == f"SELECT '{expected}';"


@pytest.mark.parametrize(
    ("operation", "amount", "expected"),
    [
        ("add_days", -1, "2024-02-28 12:34:56"),
        ("add_months", -1, "2024-01-29 12:34:56"),
        ("add_years", -1, "2023-02-28 12:34:56"),
        ("month_start", None, "2024-02-01 12:34:56"),
        ("month_end", None, "2024-02-29 12:34:56"),
        ("year_start", None, "2024-01-01 12:34:56"),
        ("year_end", None, "2024-12-31 12:34:56"),
        ("previous_year_end", None, "2023-12-31 12:34:56"),
    ],
)
def test_timestamp_derivations_preserve_time(operation, amount, expected):
    derive = {"from": "run_ts", "operation": operation}
    if amount is not None:
        derive["amount"] = amount
    definition = build_task_definition(
        "SELECT ${derived_ts};",
        {
            "version": 1,
            "strict": True,
            "startup_params": [
                {
                    "prop": "run_ts",
                    "type": "TIMESTAMP",
                    "source": "invocation.run_ts",
                    "required": True,
                }
            ],
            "local_params": [
                {
                    "prop": "derived_ts",
                    "direct": "IN",
                    "type": "TIMESTAMP",
                    "value": {"derive": derive},
                }
            ],
        },
    )

    rendered = render_task(
        definition,
        mode="analysis",
        bindings=RenderBindings(startup={"run_ts": "2024-02-29 12:34:56"}),
    )

    assert rendered.sql == f"SELECT '{expected}';"


def test_timestamp_format_derivation_preserves_time():
    definition = build_task_definition(
        "SELECT ${run_time};",
        {
            "version": 1,
            "strict": True,
            "startup_params": [
                {
                    "prop": "run_ts",
                    "type": "TIMESTAMP",
                    "source": "invocation.run_ts",
                    "required": True,
                }
            ],
            "local_params": [
                {
                    "prop": "run_time",
                    "direct": "IN",
                    "type": "VARCHAR",
                    "value": {
                        "derive": {
                            "from": "run_ts",
                            "operation": "format_date",
                            "format": "HH:mm:ss",
                        }
                    },
                }
            ],
        },
    )

    rendered = render_task(
        definition,
        mode="analysis",
        bindings=RenderBindings(startup={"run_ts": "2024-02-29 12:34:56"}),
    )

    assert rendered.sql == "SELECT '12:34:56';"


def test_timestamp_derivation_can_explicitly_project_to_date():
    definition = build_task_definition(
        "SELECT ${derived_date};",
        {
            "version": 1,
            "strict": True,
            "startup_params": [
                {
                    "prop": "run_ts",
                    "type": "TIMESTAMP",
                    "source": "invocation.run_ts",
                    "required": True,
                }
            ],
            "local_params": [
                {
                    "prop": "derived_date",
                    "direct": "IN",
                    "type": "DATE",
                    "value": {
                        "derive": {
                            "from": "run_ts",
                            "operation": "add_days",
                            "amount": 1,
                        }
                    },
                }
            ],
        },
    )

    rendered = render_task(
        definition,
        mode="analysis",
        bindings=RenderBindings(startup={"run_ts": "2024-02-29 12:34:56"}),
    )

    assert rendered.sql == "SELECT '2024-03-01';"


def test_timestamp_project_binding_rejects_yaml_date_scalar():
    definition = build_task_definition(
        "SELECT ${run_ts};",
        {
            "version": 1,
            "strict": True,
            "project_params": [
                {
                    "prop": "run_ts",
                    "type": "TIMESTAMP",
                    "source": "project.run_ts",
                    "required": True,
                }
            ],
        },
    )
    project = yaml.safe_load("run_ts: 2025-03-01\n")

    assert isinstance(project["run_ts"], date)
    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=RenderBindings(project=project),
        )

    assert raised.value.code == "template.render.invalid_value"


def test_analysis_render_is_independent_of_working_directory_timezone_and_now(
    tmp_path,
    monkeypatch,
):
    definition = _definition()
    first = render_task(
        definition, mode="analysis", bindings=_bindings("2000-02-29")
    )
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    second = render_task(
        definition, mode="analysis", bindings=_bindings("2000-02-29")
    )

    assert first.sql == second.sql
    assert first.binding_digest == second.binding_digest
    assert first.render_digest == second.render_digest
    assert renderer_semantics_digest() == renderer_semantics_digest()


def test_modes_share_derivation_graph_but_bind_explicit_root_values():
    definition = _definition()
    execution = render_task(
        definition, mode="execution", bindings=_bindings("2025-01-01")
    )
    analysis = render_task(
        definition, mode="analysis", bindings=_bindings("2000-02-29")
    )
    verification = render_task(
        definition, mode="verification", bindings=_bindings("2025-01-01")
    )

    assert "`tmp_run_20250101`" in execution.sql
    assert "`tmp_run_20000229`" in analysis.sql
    assert execution.sql == verification.sql
    assert execution.binding_digest != verification.binding_digest
    assert execution.render_digest != analysis.render_digest


def test_only_declared_overrides_are_accepted():
    definition = _definition()
    first = render_task(
        definition,
        mode="execution",
        bindings=_bindings(org_code="secret-a"),
    )
    second = render_task(
        definition,
        mode="execution",
        bindings=_bindings(org_code="secret-b"),
    )

    assert first.public_bindings["org_code"] == "secret-a"
    assert first.binding_digest != second.binding_digest
    assert "org_code = 'secret-a'" in first.sql

    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=_bindings(row_limit=1),
        )
    assert raised.value.code == "template.render.forbidden_override"


def test_identifier_and_binding_injection_fail_closed():
    definition = _definition()
    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=RenderBindings(
                startup={"etl_date": "2024-02-29"},
                project={"source_table": "cdm.good; DROP TABLE prod"},
            ),
        )
    assert raised.value.code == "template.render.invalid_identifier"

    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="analysis",
            bindings=RenderBindings(
                startup={},
                project={"source_table": "cdm.p03_cust_info"},
            ),
        )
    assert raised.value.code == "template.render.missing_binding"


def test_string_literal_injection_is_escaped_as_one_complete_token():
    contract = deepcopy(_render_contract())
    contract["local_params"][5]["value"] = "safe"
    definition = build_task_definition(_render_sql(), contract)
    rendered = render_task(
        definition,
        mode="execution",
        bindings=_bindings(org_code="x'; DROP TABLE prod; --"),
    )

    assert "org_code = 'x''; DROP TABLE prod; --'" in rendered.sql
    assert rendered.sql.count("DROP TABLE prod") == 1


@pytest.mark.parametrize(
    ("input_format", "value"),
    [
        ("yyyyMMdd", "202411"),
        (None, "2024-1-1"),
    ],
)
def test_temporal_inputs_require_exact_zero_padded_formats(
    input_format, value
):
    parameter = {
        "prop": "etl_date",
        "type": "DATE",
        "source": "invocation.etl_date",
        "required": True,
    }
    if input_format is not None:
        parameter["render"] = {"input_format": input_format}
    definition = build_task_definition(
        "SELECT ${etl_date};",
        {
            "version": 1,
            "strict": True,
            "startup_params": [parameter],
        },
    )

    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=RenderBindings(startup={"etl_date": value}),
        )

    assert raised.value.code == "template.render.invalid_temporal"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1E+100", "1" + ("0" * 100)),
        ("00012.340000", "12.34"),
        (
            "0.0000000000000000000000000012300",
            "0.00000000000000000000000000123",
        ),
    ],
)
def test_decimal_rendering_is_canonical_and_context_independent(
    value, expected
):
    definition = build_task_definition(
        "SELECT ${number};",
        {
            "version": 1,
            "strict": True,
            "local_params": [
                {
                    "prop": "number",
                    "direct": "IN",
                    "type": "DOUBLE",
                    "value": value,
                }
            ],
        },
    )

    with localcontext() as context:
        context.prec = 2
        context.rounding = "ROUND_DOWN"
        low_precision = render_task(definition, mode="analysis").sql
    with localcontext() as context:
        context.prec = 50
        context.rounding = "ROUND_UP"
        high_precision = render_task(definition, mode="analysis").sql

    assert low_precision == high_precision == f"SELECT {expected};"


def _priority_contract(include_local=True):
    contract = {
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
                "type": "VARCHAR",
                "source": "project.shared",
                "required": False,
                "default": "default",
                "overrideable": True,
            }
        ],
    }
    if include_local:
        contract["local_params"] = [
            {
                "prop": "shared",
                "direct": "IN",
                "type": "VARCHAR",
                "value": "local",
                "overrideable": True,
            }
        ]
    return contract


def test_dolphin_style_candidate_priority_is_deterministic():
    with_local = build_task_definition(
        "SELECT ${shared};", _priority_contract()
    )
    without_local = build_task_definition(
        "SELECT ${shared};", _priority_contract(include_local=False)
    )

    overridden = render_task(
        with_local,
        mode="execution",
        bindings=RenderBindings(
            startup={"shared": "startup"},
            project={"shared": "project"},
            overrides={"shared": "override"},
        ),
    )
    startup = render_task(
        with_local,
        mode="execution",
        bindings=RenderBindings(
            startup={"shared": "startup"},
            project={"shared": "project"},
        ),
    )
    local = render_task(
        with_local,
        mode="execution",
        bindings=RenderBindings(project={"shared": "project"}),
    )
    project = render_task(
        without_local,
        mode="execution",
        bindings=RenderBindings(project={"shared": "project"}),
    )
    default = render_task(without_local, mode="execution")

    assert overridden.sql == "SELECT 'override';"
    assert startup.sql == "SELECT 'startup';"
    assert local.sql == "SELECT 'local';"
    assert project.sql == "SELECT 'project';"
    assert default.sql == "SELECT 'default';"


def test_binding_alias_conflicts_and_identifier_overrides_fail_closed():
    definition = build_task_definition(
        "SELECT ${shared};", _priority_contract(include_local=False)
    )
    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=RenderBindings(
                startup={
                    "shared": "first",
                    "invocation.shared": "second",
                }
            ),
        )
    assert raised.value.code == "template.render.conflicting_binding"

    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            _definition(),
            mode="execution",
            bindings=_bindings(source_table="other.table"),
        )
    assert raised.value.code == "template.render.forbidden_override"


def test_empty_list_override_fails_before_emitting_invalid_in_clause():
    contract = {
        "version": 1,
        "strict": True,
        "local_params": [
            {
                "prop": "values",
                "direct": "IN",
                "type": "LIST",
                "value": [1],
                "render": {"item_type": "INTEGER"},
                "overrideable": True,
            }
        ],
    }
    definition = build_task_definition(
        "SELECT 1 WHERE 1 IN ${values};",
        contract,
    )

    with pytest.raises(TemplateRenderError) as raised:
        render_task(
            definition,
            mode="execution",
            bindings=RenderBindings(overrides={"values": []}),
        )

    assert raised.value.code == "template.render.invalid_value"
