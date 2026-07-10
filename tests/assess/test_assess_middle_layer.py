import json
import os
import sys

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.assess_middle_layer import assess
from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.assessment.report import generate_report
from dw_refactor_agent.assessment.rules.dimensions.asset_completeness import (
    score_asset_completeness,
)
from dw_refactor_agent.assessment.rules.dimensions.metadata_health import (
    score_metadata_health,
)
from dw_refactor_agent.assessment.rules.dimensions.model_design import (
    score_model_design_health,
)
from dw_refactor_agent.assessment.rules.dimensions.naming import (
    score_naming_conventions,
)
from dw_refactor_agent.assessment.scoring.config import normalize_score_weights
from dw_refactor_agent.config import (
    PROJECT_ROOT,
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
    load_naming_config,
)


def _business_domain_config():
    return BusinessDomainConfig(
        domains={
            "04": DomainDef(id="04", code="TRAN", name="交易域"),
            "10": DomainDef(id="10", code="MKTG", name="营销域"),
            "99": DomainDef(id="99", code="OTHR", name="其它"),
        },
        business_areas={
            "PAYM": BusinessAreaDef(id="04", code="PAYM", name="支付结算"),
            "CLNT": BusinessAreaDef(id="13", code="CLNT", name="客户经营"),
            "OTHR": BusinessAreaDef(id="99", code="OTHR", name="其它"),
        },
    )


def _context(
    tables=None,
    nc=None,
    models=None,
    business_domain_config=None,
    *,
    project_dir=None,
    edges=None,
    indirect_edges=None,
    assets=None,
):
    if tables:
        table_models = {
            table["name"]: {"name": table["name"], "layer": table["layer"]}
            for table in tables
            if table.get("name") and table.get("layer")
        }
        if models is None:
            models = table_models
        else:
            models = {
                name: dict(metadata) for name, metadata in models.items()
            }
            for table_name, table_model in table_models.items():
                metadata = models.setdefault(table_name, {})
                metadata.setdefault("name", table_name)
                metadata.setdefault("layer", table_model["layer"])
    return AssessmentContext.from_facts(
        tables=tables or [],
        edges=edges or [],
        indirect_edges=indirect_edges or [],
        models=models,
        project_dir=project_dir,
        business_domain_config=business_domain_config,
        naming_config=nc,
        assets=assets,
    )


def _business_naming_config(tmp_path):
    raw = yaml.safe_load(
        (PROJECT_ROOT / "naming_config.yaml").read_text(encoding="utf-8")
    )
    raw.pop("dictionaries", None)
    raw["types"]["BUSINESS_AREA_CODE"]["allow"] = {
        "dictionary": "business_areas",
        "value_field": "code",
    }
    raw["types"]["BUSINESS_AREA_CODE"].pop("patterns", None)
    raw["types"]["DATA_DOMAIN_ID"]["allow"] = {
        "dictionary": "data_domains",
        "value_field": "id",
    }
    raw["types"]["DATA_DOMAIN_ID"].pop("patterns", None)
    cfg_path = tmp_path / "business_naming.yaml"
    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": "unit_assess",
                "data_domains": [
                    {"id": "04", "code": "TRAN", "name": "交易域"},
                    {"id": "10", "code": "MKTG", "name": "营销域"},
                    {"id": "99", "code": "OTHR", "name": "其它"},
                ],
                "business_areas": [
                    {"id": "04", "code": "PAYM", "name": "支付结算"},
                    {"id": "13", "code": "CLNT", "name": "客户经营"},
                    {"id": "99", "code": "OTHR", "name": "其它"},
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return load_naming_config(cfg_path)


@pytest.fixture
def isolated_assess_project(tmp_path, monkeypatch):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "unit_assess"
    project_dir = tmp_path / project
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir(parents=True)
    for table_name, layer in [
        ("dwd_customer", "DWD"),
        ("dwd_order_detail", "DWD"),
        ("dws_store_sales_daily", "DWS"),
        ("ads_sales_dashboard", "ADS"),
    ]:
        materialized = "full" if layer == "ADS" else "incremental"
        (models_dir / f"{table_name}.yaml").write_text(
            (
                f"version: 2\nname: {table_name}\nlayer: {layer}\n"
                f"execution:\n  materialized: {materialized}\n"
            ),
            encoding="utf-8",
        )
    ddl_dir = project_dir / "mid" / "ddl"
    ddl_dir.mkdir()
    for table_name in [
        "dwd_customer",
        "dwd_order_detail",
        "dws_store_sales_daily",
        "ads_sales_dashboard",
    ]:
        (ddl_dir / f"{table_name}.sql").write_text(
            f"CREATE TABLE {table_name} (id BIGINT);",
            encoding="utf-8",
        )
    mid_tasks_dir = project_dir / "mid" / "tasks"
    ads_tasks_dir = project_dir / "ads" / "tasks"
    mid_tasks_dir.mkdir(parents=True)
    ads_tasks_dir.mkdir(parents=True)
    for table_name in [
        "dwd_customer",
        "dwd_order_detail",
        "dws_store_sales_daily",
    ]:
        (mid_tasks_dir / f"{table_name}.sql").write_text(
            f"INSERT INTO {table_name} SELECT 1;",
            encoding="utf-8",
        )
    (ads_tasks_dir / "ads_sales_dashboard.sql").write_text(
        "INSERT INTO ads_sales_dashboard SELECT 1;",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        (PROJECT_ROOT / "naming_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(assess_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    yield project
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()


def _issue_rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def _checks_by_rule(result, rule_id):
    return [check for check in result["checks"] if check["rule_id"] == rule_id]


def test_assess_returns_dimension_check_issue_model(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)

    assert result["project"] == isolated_assess_project
    assert "overall_score" in result
    assert set(result["dimensions"]) == {
        "reuse",
        "depth",
        "model_design",
        "naming",
        "asset_completeness",
        "metadata_health",
        "code_quality",
    }
    for dimension in result["dimensions"].values():
        assert set(dimension) >= {
            "score",
            "rule_summary",
            "issues",
        }
        assert "checks" not in dimension
    assert result["dimensions"]["model_design"]["score"] == 50.0
    assert (
        result["dimensions"]["model_design"]["issues"][0]["severity"] == "中"
    )
    assert result["dimensions"]["asset_completeness"]["issues"] == []
    assert result["diagnostic_contract"]["primary_entry"] == (
        "dimensions.*.issues"
    )
    assert result["diagnostic_contract"]["stable_identity"] == (
        "issues[].fingerprint"
    )


def test_assess_omits_checks_from_default_output(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    data = dict(sample_lineage_data)
    data["edges"] = sample_lineage_data["edges"] + [
        {
            "source": "dws_store_sales_daily.order_count",
            "target": "ads_sales_dashboard.total_orders",
            "expression": "order_count",
            "source_file": "ads_sales_dashboard.sql",
        }
    ]
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: data,
    )

    result = assess(project=isolated_assess_project)

    assert all(
        "checks" not in dimension
        for dimension in result["dimensions"].values()
    )
    assert result["dimensions"]["model_design"]["issues"]


def test_assess_can_run_selected_model_design_only(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(
        project=isolated_assess_project,
        selected_dimensions={"model_design"},
    )

    assert set(result["dimensions"]) == {"model_design"}
    assert result["dimensions"]["model_design"]["score"] == 50.0


def test_assess_rejects_architecture_dimension_alias():
    with pytest.raises(ValueError, match="architecture"):
        assess(project="shop", selected_dimensions={"architecture"})


def test_assess_builds_one_context_with_derived_lineage_for_scoring_modules(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    captured = {}

    def dimension(name):
        return {
            "score": 100.0,
            "rule_summary": {},
            "checks": [],
            "issues": [],
            "summary": {},
        }

    def remember_context(name):
        def scorer(context, *args, **kwargs):
            captured[name] = context
            return dimension(name)

        return scorer

    def fake_depth_score(context, **kwargs):
        captured["depth_context"] = context
        captured["depth_upstream_map"] = context.upstream
        captured["depth_table_layers"] = context.table_layers
        return dimension("depth")

    def fake_model_design_score(context, llm_results=None, **kwargs):
        captured["model_context"] = context
        captured["model_lineage"] = context.lineage
        captured["model_table_edges"] = context.table_edges
        captured["model_table_layers"] = context.table_layers
        return dimension("model_design")

    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_reusability",
        remember_context("reuse_context"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_lineage_depth",
        fake_depth_score,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_model_design_health",
        fake_model_design_score,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_asset_completeness",
        remember_context("asset_completeness_context"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_code_quality",
        remember_context("code_quality_context"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_metadata_health",
        remember_context("metadata_health_context"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_naming_conventions",
        remember_context("naming_context"),
    )

    assess(project=isolated_assess_project)

    assert captured["depth_upstream_map"] == {
        "dwd_customer": {"ods_customer"},
        "dwd_order_detail": {"ods_order"},
        "dws_store_sales_daily": {"dwd_order_detail"},
        "ads_sales_dashboard": {"dwd_customer"},
    }
    assert captured["depth_table_layers"] == {
        "dwd_customer": "DWD",
        "dwd_order_detail": "DWD",
        "dws_store_sales_daily": "DWS",
        "ads_sales_dashboard": "ADS",
    }
    assert captured["model_table_edges"] == {
        ("ods_customer", "dwd_customer"): {"dwd_customer.sql"},
        ("ods_order", "dwd_order_detail"): {"dwd_order_detail.sql"},
        ("dwd_order_detail", "dws_store_sales_daily"): {
            "dws_store_sales_daily.sql"
        },
        ("dwd_customer", "ads_sales_dashboard"): {"ads_sales_dashboard.sql"},
    }
    assert captured["model_table_layers"] == captured["depth_table_layers"]
    assert captured["reuse_context"] is captured["depth_context"]
    assert captured["model_context"] is captured["depth_context"]
    assert captured["model_lineage"] is captured["depth_context"].lineage
    assert captured["asset_completeness_context"] is captured["depth_context"]
    assert captured["code_quality_context"] is captured["depth_context"]
    assert captured["metadata_health_context"] is captured["depth_context"]
    assert captured["naming_context"] is captured["depth_context"]


def test_assess_builds_scope_plan_and_passes_dimension_scopes(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    captured = {}

    def dimension(name):
        return {
            "score": 100.0,
            "rule_summary": {},
            "checks": [],
            "issues": [],
        }

    def remember_scope(name):
        def scorer(context, *args, **kwargs):
            captured[name] = kwargs.get("scope")
            return dimension(name)

        return scorer

    def fake_model_design_score(context, llm_results=None, **kwargs):
        captured["model_design"] = kwargs.get("scope")
        return dimension("model_design")

    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_reusability",
        remember_scope("reuse"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_lineage_depth",
        remember_scope("depth"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_model_design_health",
        fake_model_design_score,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_asset_completeness",
        remember_scope("asset_completeness"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_code_quality",
        remember_scope("code_quality"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_metadata_health",
        remember_scope("metadata_health"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_naming_conventions",
        remember_scope("naming"),
    )
    change_analysis = {
        "changed_assets": {
            "ddl_tables": [],
            "task_jobs": ["dwd_customer"],
            "model_tables": [],
            "config_files": [],
        },
        "affected_scope": {
            "direct_tables": ["dwd_customer"],
            "downstream_tables": ["ads_sales_dashboard"],
            "anchor_tables": ["ads_sales_dashboard"],
            "assessment_tables": ["dwd_customer", "ads_sales_dashboard"],
            "assessment_tasks": ["dwd_customer", "ads_sales_dashboard"],
            "global_dimensions": [],
        },
        "lineage_diff": {
            "added_edges": [],
            "removed_edges": [],
            "changed_tables": [],
        },
    }

    result = assess(
        project=isolated_assess_project,
        change_analysis=change_analysis,
    )

    assert result["assessment_mode"] == "scoped"
    assert result["score_semantics"] == "scope_local"
    assert captured["code_quality"]["tasks"] == [
        "ads_sales_dashboard",
        "dwd_customer",
    ]
    assert captured["metadata_health"]["tables"] == [
        "ads_sales_dashboard",
        "dwd_customer",
    ]
    assert captured["depth"]["tables"] == ["ads_sales_dashboard"]
    assert result["scope_plan"]["dimensions"]["naming"]["mode"] == "scoped"


def test_assess_manual_focus_limits_model_design_edges(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    captured = {}

    def dimension(name):
        return {
            "score": 100.0,
            "rule_summary": {},
            "checks": [],
            "issues": [],
        }

    def remember_scope(name):
        def scorer(context, *args, **kwargs):
            captured[name] = kwargs.get("scope")
            return dimension(name)

        return scorer

    def fake_model_design_score(context, llm_results=None, **kwargs):
        captured["model_design"] = kwargs.get("scope")
        return dimension("model_design")

    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_reusability",
        remember_scope("reuse"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_lineage_depth",
        remember_scope("depth"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_model_design_health",
        fake_model_design_score,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_asset_completeness",
        remember_scope("asset_completeness"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_code_quality",
        remember_scope("code_quality"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_metadata_health",
        remember_scope("metadata_health"),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.score_naming_conventions",
        remember_scope("naming"),
    )

    scope_plan = assess_module.build_manual_focus_scope_plan(
        table_names=["dws_store_sales_daily"],
    )

    result = assess(
        project=isolated_assess_project,
        selected_dimensions={"model_design"},
        scope_plan=scope_plan,
    )

    assert result["assessment_mode"] == "manual_focus"
    assert captured["model_design"]["tables"] == ["dws_store_sales_daily"]
    assert captured["model_design"]["edges"] == [
        {
            "source": "dwd_order_detail",
            "target": "dws_store_sales_daily",
        }
    ]


def test_generate_report_reads_dimension_issues(
    monkeypatch, sample_lineage_data, isolated_assess_project
):
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project=isolated_assess_project)
    report = generate_report(
        result, result["weights"], isolated_assess_project
    )

    assert "总体评分" in report
    assert "ARCH_SKIP_LAYER_DEPENDENCY" in report
    assert "问题项" in report
    assert "总体评分(展示)" not in report


def test_assess_cli_defaults_output_to_project_assess_dir(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"
    project_dir = tmp_path / "shop"
    project_dir.mkdir()
    tool_dir = tmp_path / "tool_assess"
    tool_dir.mkdir()
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(assess_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        assess_module,
        "__file__",
        str(tool_dir / "assess_middle_layer.py"),
    )
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": "shop",
            "naming_config": "naming_config.yaml",
        },
    )
    monkeypatch.setattr(
        sys, "argv", ["assess_middle_layer.py", "--project", project]
    )
    monkeypatch.setattr(
        assess_module,
        "assess",
        lambda *args, **kwargs: {
            "project": project,
            "weights": {},
            "dimensions": {},
        },
    )
    monkeypatch.setattr(
        assess_module,
        "generate_report",
        lambda *args, **kwargs: "report",
    )

    assess_module.main()

    output_path = (
        project_dir / "artifacts" / "assessment" / "assess_result.json"
    )
    assert output_path.exists()
    assert not (tool_dir / f"assess_result_{project}.json").exists()


def test_assess_cli_accepts_explicit_lineage_file(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"
    lineage_data = {"tables": [{"name": "dwd_order"}], "edges": []}
    lineage_file = tmp_path / "lineage_data.json"
    lineage_file.write_text(
        json.dumps(lineage_data, ensure_ascii=False),
        encoding="utf-8",
    )
    output_path = tmp_path / "assess_result.json"
    captured = {}

    def fake_assess(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {
            "project": project,
            "weights": {},
            "dimensions": {},
        }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_middle_layer.py",
            "--project",
            project,
            "--lineage-file",
            str(lineage_file),
            "--output",
            str(output_path),
        ],
    )
    monkeypatch.setattr(assess_module, "assess", fake_assess)
    monkeypatch.setattr(
        assess_module,
        "generate_report",
        lambda *args, **kwargs: "report",
    )

    assess_module.main()

    assert captured["args"][0] == project
    assert captured["kwargs"]["lineage_data"] == lineage_data
    assert output_path.exists()


@pytest.mark.parametrize(
    (
        "focus_args",
        "rule_id",
        "selected_dimension",
        "expected_scope",
    ),
    [
        (
            ("--table", "dws_store_sales_daily"),
            "NAMING_ATOMIC_METRIC",
            "naming",
            {
                ("naming", "tables"): ["dws_store_sales_daily"],
                ("model_design", "tables"): ["dws_store_sales_daily"],
            },
        ),
        (
            (
                "--task",
                "warehouses/shop/mid/tasks/dws_store_sales_daily.sql",
            ),
            "CODE_NO_SELECT_STAR_IN_WRITE",
            "code_quality",
            {
                ("code_quality", "tasks"): ["dws_store_sales_daily"],
                ("code_quality", "task_files"): [
                    "warehouses/shop/mid/tasks/dws_store_sales_daily.sql"
                ],
                ("naming", "tasks"): ["dws_store_sales_daily"],
            },
        ),
    ],
    ids=("table", "task"),
)
def test_assess_cli_focus_builds_manual_scope(
    monkeypatch,
    tmp_path,
    focus_args,
    rule_id,
    selected_dimension,
    expected_scope,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"
    output_path = tmp_path / "assess_result.json"
    captured = {}

    def fake_assess(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {
            "project": project,
            "weights": {},
            "dimensions": {
                selected_dimension: {
                    "score": 100.0,
                    "rule_summary": {
                        rule_id: {
                            "name": "test rule",
                            "severity": "高",
                            "pass_count": 1,
                            "total": 1,
                            "pct": 100.0,
                        },
                    },
                    "issues": [],
                }
            },
            "assessment_mode": "manual_focus",
        }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_middle_layer.py",
            "--project",
            project,
            *focus_args,
            "--only-rule",
            rule_id,
            "--output",
            str(output_path),
        ],
    )
    monkeypatch.setattr(assess_module, "assess", fake_assess)
    monkeypatch.setattr(
        assess_module,
        "generate_report",
        lambda *args, **kwargs: "report",
    )

    assess_module.main()

    assert captured["kwargs"]["selected_dimensions"] == {selected_dimension}
    assert captured["kwargs"]["only_rules"] == [rule_id]
    scope_plan = captured["kwargs"]["scope_plan"]
    assert scope_plan["mode"] == "manual_focus"
    for (dimension, field), expected in expected_scope.items():
        assert scope_plan["dimensions"][dimension][field] == expected
    assert output_path.exists()


def test_task_focus_scans_only_requested_task_file(
    monkeypatch,
    sample_lineage_data,
    isolated_assess_project,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = isolated_assess_project
    project_dir = config.PROJECT_ROOT / config.PROJECT_CONFIG[project]["dir"]
    full_refresh_dir = project_dir / "mid" / "tasks" / "full_refresh"
    full_refresh_dir.mkdir(parents=True)
    (full_refresh_dir / "dwd_customer_full_refresh.sql").write_text(
        "INSERT INTO dwd_customer SELECT * FROM ods_customer;",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.assessment.assess_middle_layer.load_lineage_data",
        lambda project_name: sample_lineage_data,
    )

    result = assess(
        project=project,
        selected_dimensions={"code_quality"},
        only_rules=["CODE_NO_SELECT_STAR_IN_WRITE"],
        scope_plan=assess_module.build_manual_focus_scope_plan(
            task_paths=["mid/tasks/dwd_customer.sql"],
        ),
    )

    summary = result["dimensions"]["code_quality"]["rule_summary"][
        "CODE_NO_SELECT_STAR_IN_WRITE"
    ]
    assert summary["pass_count"] == 1
    assert summary["total"] == 1
    assert result["dimensions"]["code_quality"]["issues"] == []


def test_assess_cli_manual_focus_exits_nonzero_on_issue(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"
    output_path = tmp_path / "assess_result.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_middle_layer.py",
            "--project",
            project,
            "--table",
            "dws_store_sales_daily",
            "--only-rule",
            "NAMING_ATOMIC_METRIC",
            "--output",
            str(output_path),
        ],
    )
    monkeypatch.setattr(
        assess_module,
        "assess",
        lambda *args, **kwargs: {
            "project": project,
            "weights": {},
            "dimensions": {
                "naming": {
                    "score": 0.0,
                    "rule_summary": {},
                    "issues": [
                        {
                            "rule_id": "NAMING_ATOMIC_METRIC",
                            "target": {
                                "type": "metric",
                                "name": "customer_count",
                            },
                            "message": "原子指标命名不合规",
                        }
                    ],
                }
            },
            "assessment_mode": "manual_focus",
        },
    )
    monkeypatch.setattr(
        assess_module,
        "generate_report",
        lambda *args, **kwargs: "report",
    )

    with pytest.raises(SystemExit) as exc:
        assess_module.main()

    assert exc.value.code == 1
    assert output_path.exists()


def test_assess_cli_can_refresh_default_lineage_before_scoring(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"
    output_path = tmp_path / "assess_result.json"
    refresh_calls = []

    def fake_refresh(project_name, parallel):
        refresh_calls.append((project_name, parallel))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_middle_layer.py",
            "--project",
            project,
            "--refresh-lineage",
            "--lineage-parallel",
            "3",
            "--output",
            str(output_path),
        ],
    )
    monkeypatch.setattr(
        assess_module,
        "refresh_project_lineage",
        fake_refresh,
        raising=False,
    )
    monkeypatch.setattr(
        assess_module,
        "assess",
        lambda *args, **kwargs: {
            "project": project,
            "weights": {},
            "dimensions": {},
        },
    )
    monkeypatch.setattr(
        assess_module,
        "generate_report",
        lambda *args, **kwargs: "report",
    )

    assess_module.main()

    assert refresh_calls == [(project, 3)]
    assert output_path.exists()


def test_assess_cli_missing_default_lineage_suggests_next_steps(
    monkeypatch,
    capsys,
):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    project = "shop"

    def fake_assess(*args, **kwargs):
        raise FileNotFoundError(
            "未找到 shop 的血缘数据文件 "
            "(warehouses/shop/artifacts/lineage/lineage_data.json)"
        )

    monkeypatch.setattr(
        sys, "argv", ["assess_middle_layer.py", "--project", project]
    )
    monkeypatch.setattr(assess_module, "assess", fake_assess)

    with pytest.raises(SystemExit) as exc:
        assess_module.main()

    assert exc.value.code == 1
    output = capsys.readouterr().err
    assert (
        "python -m dw_refactor_agent.lineage.lineage_extractor --project shop"
        in output
    )
    assert "--refresh-lineage" in output
    assert "--lineage-file" in output


def test_refresh_project_lineage_sets_src_pythonpath(monkeypatch):
    import dw_refactor_agent.assessment.assess_middle_layer as assess_module

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))

    monkeypatch.setattr(assess_module.subprocess, "run", fake_run)

    assess_module.refresh_project_lineage("shop", parallel=2)

    cmd, kwargs = calls[0]
    assert cmd[:3] == [
        sys.executable,
        "-m",
        "dw_refactor_agent.lineage.lineage_extractor",
    ]
    assert kwargs["cwd"] == assess_module.PROJECT_ROOT
    assert str(config.SRC_ROOT) in kwargs["env"]["PYTHONPATH"].split(
        os.pathsep
    )


def test_normalize_score_weights_supports_partial_override():
    weights = normalize_score_weights({"reuse": 0.3})

    assert weights["reuse"] == pytest.approx(0.267857, rel=0, abs=1e-6)
    assert weights["depth"] == pytest.approx(0.160714, rel=0, abs=1e-6)
    assert weights["model_design"] == pytest.approx(0.160714, rel=0, abs=1e-6)
    assert weights["asset_completeness"] == pytest.approx(
        0.080357, rel=0, abs=1e-6
    )
    assert weights["metadata_health"] == pytest.approx(
        0.080357, rel=0, abs=1e-6
    )
    assert weights["naming"] == pytest.approx(0.160714, rel=0, abs=1e-6)
    assert weights["code_quality"] == pytest.approx(0.089286, rel=0, abs=1e-6)


def test_score_metadata_health_validates_model_entity_and_grain_entity():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "DIM_BASE_PROD_INFO_INFO",
            "layer": "DIM",
            "columns": [{"name": "product_id", "type": "BIGINT"}],
        },
        {
            "name": "I_SHOP_CAT_SALE_DS",
            "layer": "DWS",
            "columns": [
                {"name": "category_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
            ],
        },
    ]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "layer": "DIM",
            "table_type": "dimension",
            "semantic_subject": "CUST",
            "entity": {
                "code": "CUST",
                "key_columns": ["product_id"],
            },
        },
        "I_SHOP_CAT_SALE_DS": {
            "layer": "DWS",
            "table_type": "fact",
            "grain": {
                "keys": ["category_id", "stat_date"],
                "entities": ["CAT"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        },
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    assert result["score"] < 100.0
    assert result["rule_summary"]["METADATA_GRAIN_ENTITIES_DEFINED"] == {
        "name": "grain.entities属于当前表entities",
        "severity": "中",
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    grain_check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "METADATA_GRAIN_ENTITIES_DEFINED"
    )
    assert grain_check["target"] == {
        "type": "table",
        "name": "I_SHOP_CAT_SALE_DS",
    }
    assert grain_check["passed"] is False
    assert grain_check["expected"] == "grain.entities引用当前表entities.code"
    assert grain_check["actual"] == "当前表未声明实体: ['CAT']"
    assert grain_check["evidence"] == {
        "grain_entities": ["CAT"],
        "table_entities": [],
    }
    assert grain_check["message"] == (
        "grain.entities不在当前表entities中=['CAT']"
    )
    assert result["issues"][0]["severity"] == "中"
    assert result["issues"][0]["remediation"]["strategy"] == (
        "update_model_grain_entities"
    )


def test_score_metadata_health_requires_grain_entities_on_same_table():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "dim_category",
            "layer": "DIM",
            "columns": [{"name": "category_id", "type": "BIGINT"}],
        },
        {
            "name": "dws_category_sales_daily",
            "layer": "DWS",
            "columns": [
                {"name": "category_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
            ],
        },
    ]
    model_metadata = {
        "dim_category": {
            "layer": "DIM",
            "table_type": "dimension",
            "semantic_subject": "CAT",
            "entities": [
                {
                    "code": "CAT",
                    "type": "primary",
                    "key_columns": ["category_id"],
                }
            ],
        },
        "dws_category_sales_daily": {
            "layer": "DWS",
            "table_type": "fact",
            "entities": [
                {
                    "code": "STORE",
                    "type": "foreign",
                    "key_columns": ["store_id"],
                }
            ],
            "grain": {
                "entities": ["CAT"],
                "time_column": "stat_date",
            },
        },
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "METADATA_GRAIN_ENTITIES_DEFINED"
        and check["target"]["name"] == "dws_category_sales_daily"
    )
    assert check["passed"] is False
    assert check["actual"] == "当前表未声明实体: ['CAT']"
    assert check["evidence"] == {
        "grain_entities": ["CAT"],
        "table_entities": ["STORE"],
    }


def test_score_metadata_health_passes_valid_entities_schema():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "DIM_BASE_PROD_INFO_INFO",
            "layer": "DIM",
            "columns": [
                {"name": "product_id", "type": "BIGINT"},
                {"name": "category_id", "type": "BIGINT"},
            ],
        },
        {
            "name": "I_SHOP_PROD_SALE_DS",
            "layer": "DWS",
            "columns": [
                {"name": "product_id", "type": "BIGINT"},
                {"name": "stat_date", "type": "DATE"},
            ],
        },
    ]
    model_metadata = {
        "DIM_BASE_PROD_INFO_INFO": {
            "layer": "DIM",
            "table_type": "dimension",
            "semantic_subject": "PROD",
            "entities": [
                {
                    "code": "PROD",
                    "type": "primary",
                    "key_columns": ["product_id"],
                },
                {
                    "code": "CAT",
                    "type": "foreign",
                    "key_columns": ["category_id"],
                    "relationship": {
                        "type": "many_to_one",
                        "from_entity": "PROD",
                    },
                },
            ],
        },
        "I_SHOP_PROD_SALE_DS": {
            "layer": "DWS",
            "table_type": "fact",
            "entities": [
                {
                    "code": "PROD",
                    "type": "foreign",
                    "key_columns": ["product_id"],
                }
            ],
            "grain": {
                "entities": ["PROD"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        },
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert all(check["passed"] for check in result["checks"])


def test_score_metadata_health_matches_columns_case_insensitively_and_reports_spelling():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "dws_customer_sales_daily",
            "layer": "DWS",
            "columns": [
                {"name": "Customer_ID", "type": "BIGINT"},
                {"name": "STAT_DATE", "type": "DATE"},
            ],
        }
    ]
    model_metadata = {
        "dws_customer_sales_daily": {
            "layer": "DWS",
            "table_type": "fact",
            "entities": [
                {
                    "code": "CUST",
                    "type": "foreign",
                    "key_columns": ["CUSTOMER_ID"],
                }
            ],
            "grain": {
                "entities": ["CUST"],
                "time_column": "stat_date",
                "time_period": "D",
            },
        }
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    entity_key_check = _checks_by_rule(
        result,
        "METADATA_ENTITY_KEYS_EXIST",
    )[0]
    grain_key_check = _checks_by_rule(
        result,
        "METADATA_GRAIN_KEYS_EXIST",
    )[0]
    spelling_check = _checks_by_rule(
        result,
        "METADATA_MODEL_COLUMN_SPELLING_MATCHES_DDL",
    )[0]
    assert entity_key_check["passed"] is True
    assert grain_key_check["passed"] is True
    assert spelling_check["passed"] is False
    assert spelling_check["evidence"]["mismatches"] == [
        {
            "model_column": "CUSTOMER_ID",
            "ddl_column": "Customer_ID",
        },
        {
            "model_column": "stat_date",
            "ddl_column": "STAT_DATE",
        },
    ]


def test_score_metadata_health_validates_dim_semantic_subject():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "dim_product",
            "layer": "DIM",
            "columns": [{"name": "product_id", "type": "BIGINT"}],
        }
    ]
    model_metadata = {
        "dim_product": {
            "name": "dim_product",
            "layer": "DIM",
            "table_type": "dimension",
            "semantic_subject": "STORE",
            "entities": [
                {
                    "code": "PRODUCT",
                    "type": "primary",
                    "key_columns": ["product_id"],
                }
            ],
        }
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    assert "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY" in _issue_rule_ids(
        result
    )


def test_score_metadata_health_requires_dim_semantic_subject():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {
            "name": "dim_customer",
            "layer": "DIM",
            "columns": [{"name": "customer_id", "type": "BIGINT"}],
        }
    ]
    model_metadata = {
        "dim_customer": {
            "name": "dim_customer",
            "layer": "DIM",
            "table_type": "dimension",
            "entities": [
                {
                    "code": "CUSTOMER",
                    "type": "primary",
                    "key_columns": ["customer_id"],
                }
            ],
        }
    }

    result = score_metadata_health(_context(tables, nc, model_metadata))

    assert "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY" in _issue_rule_ids(
        result
    )


def test_score_metadata_health_requires_dws_grain_entities_from_models():
    nc = load_naming_config(
        PROJECT_ROOT / "warehouses" / "shop" / "naming_config.yaml"
    )
    result = score_metadata_health(
        _context(
            [{"name": "I_SHOP_PROD_SALE_DS", "layer": "DWS", "columns": []}],
            nc,
            {"I_SHOP_PROD_SALE_DS": {"layer": "DWS", "table_type": "fact"}},
        )
    )

    assert result["score"] == 0.0
    assert result["issues"] == [
        {
            "id": "metadata_health.iss_001",
            "fingerprint": (
                "metadata_health|METADATA_GRAIN_ENTITIES_PRESENT|table|"
                "I_SHOP_PROD_SALE_DS"
            ),
            "severity": "高",
            "rule_id": "METADATA_GRAIN_ENTITIES_PRESENT",
            "target": {
                "type": "table",
                "name": "I_SHOP_PROD_SALE_DS",
            },
            "title": "DWS模型缺少grain.entities",
            "message": "缺少grain.entities",
            "remediation": {
                "summary": "在模型YAML中补齐grain.entities",
                "strategy": "update_model_grain_entities",
                "edit_scope": ["models"],
            },
            "check_ids": ["metadata_health.chk_001"],
        }
    ]


def test_score_metadata_health_checks_business_dictionary_metadata(tmp_path):
    nc = _business_naming_config(tmp_path)
    result = score_metadata_health(
        _context(
            [
                {"name": "M_PAYM_04_CHREM_DI", "layer": "DWD", "columns": []},
                {"name": "M_BAD_98_CHREM_DI", "layer": "DWD", "columns": []},
            ],
            nc,
            {
                "M_PAYM_04_CHREM_DI": {
                    "data_domain": "04",
                    "business_area": "PAYM",
                },
                "M_BAD_98_CHREM_DI": {
                    "data_domain": "98",
                    "business_area": "BAD",
                },
            },
            nc.business_domain_config,
        )
    )

    assert result["rule_summary"]["METADATA_DATA_DOMAIN_VALID"] == {
        "name": "data_domain配置有效",
        "severity": "中",
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert (
        result["rule_summary"]["METADATA_BUSINESS_AREA_VALID"]["pass_count"]
        == 1
    )
    assert _issue_rule_ids(result) == {
        "METADATA_DATA_DOMAIN_VALID",
        "METADATA_BUSINESS_AREA_VALID",
    }


def test_score_metadata_health_validates_model_layer_matches_asset_path(
    tmp_path,
):
    project_dir = tmp_path / "demo"
    (project_dir / "ods" / "models" / "internal" / "demo_dm").mkdir(
        parents=True
    )
    (project_dir / "mid" / "models").mkdir(parents=True)
    (project_dir / "ads" / "models").mkdir(parents=True)

    model_files = {
        "ods_bad": (
            project_dir
            / "ods"
            / "models"
            / "internal"
            / "demo_dm"
            / "ods_bad.yaml"
        ),
        "mid_good": project_dir / "mid" / "models" / "mid_good.yaml",
        "mid_bad": project_dir / "mid" / "models" / "mid_bad.yaml",
        "ads_bad": project_dir / "ads" / "models" / "ads_bad.yaml",
    }
    model_files["ods_bad"].write_text(
        "name: ods_bad\nlayer: DWD\n",
        encoding="utf-8",
    )
    model_files["mid_good"].write_text(
        "name: mid_good\nlayer: DIM\n",
        encoding="utf-8",
    )
    model_files["mid_bad"].write_text(
        "name: mid_bad\nlayer: ADS\n",
        encoding="utf-8",
    )
    model_files["ads_bad"].write_text(
        "name: ads_bad\nlayer: DWS\n",
        encoding="utf-8",
    )
    models = {
        table_name: {
            "name": table_name,
            "layer": yaml.safe_load(path.read_text(encoding="utf-8"))["layer"],
        }
        for table_name, path in model_files.items()
    }
    models["mid_good"].update(
        {
            "table_type": "dimension",
            "semantic_subject": "GOOD",
            "entities": [
                {
                    "code": "GOOD",
                    "type": "primary",
                    "key_columns": ["good_id"],
                }
            ],
        }
    )
    models["ads_bad"].update(
        {
            "table_type": "fact",
            "entities": [
                {
                    "code": "BAD",
                    "type": "foreign",
                    "key_columns": ["bad_id"],
                }
            ],
            "grain": {"entities": ["BAD"], "time_column": "stat_date"},
        }
    )

    result = score_metadata_health(
        _context(models=models, project_dir=project_dir)
    )

    layer_checks = _checks_by_rule(
        result,
        "METADATA_MODEL_LAYER_MATCHES_ASSET_PATH",
    )
    assert {
        check["target"]["name"]: check["passed"] for check in layer_checks
    } == {
        "demo/ods/models/internal/demo_dm/ods_bad.yaml": False,
        "demo/mid/models/mid_good.yaml": True,
        "demo/mid/models/mid_bad.yaml": False,
        "demo/ads/models/ads_bad.yaml": False,
    }
    failed_checks = [check for check in layer_checks if not check["passed"]]
    assert {
        check["evidence"]["asset_role"]: check["evidence"]["expected_layers"]
        for check in failed_checks
    } == {
        "ods": ["ODS"],
        "mid": ["DIM", "DWD", "DWS"],
        "ads": ["ADS"],
    }
    assert _issue_rule_ids(result) == {
        "METADATA_MODEL_LAYER_MATCHES_ASSET_PATH"
    }
    assert all(issue["severity"] == "高" for issue in result["issues"])


def test_score_model_design_health_penalizes_declared_table_type_mismatch(
    sample_lineage_data,
):
    result = score_model_design_health(
        _context(
            sample_lineage_data["tables"],
            edges=sample_lineage_data["edges"],
            indirect_edges=sample_lineage_data["indirect_edges"],
            models={
                "dws_store_sales_daily": {
                    "table_type": "fact",
                }
            },
        ),
        llm_results=[
            TableInspectResult(
                table_name="dws_store_sales_daily",
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="dimension",
                confidence=0.9,
                reasoning_steps=[],
            )
        ],
    )

    type_issue = next(
        issue
        for issue in result["issues"]
        if issue["rule_id"] == "ARCH_TABLE_TYPE_MATCHES_LLM"
    )
    assert type_issue["severity"] == "中"
    assert type_issue["target"]["name"] == "dws_store_sales_daily"
    check = next(
        check
        for check in result["checks"]
        if check["id"] == type_issue["check_ids"][0]
    )
    assert check["actual"] == "配置类型=fact, 推断类型=dimension"


def test_score_model_design_health_allows_ads_to_read_dim():
    tables = [
        {"name": "dim_customer", "layer": "DIM", "columns": []},
        {"name": "ads_customer_by_segment", "layer": "ADS", "columns": []},
    ]
    edges = [
        {
            "source": "dim_customer.customer_id",
            "target": "ads_customer_by_segment.customer_id",
            "source_file": "ads_customer_by_segment.sql",
        }
    ]

    result = score_model_design_health(_context(tables, edges=edges))

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert result["checks"] == []


def test_score_model_design_health_penalizes_llm_business_metadata_mismatch():
    business_config = _business_domain_config()
    tables = [{"name": "dwd_transactions", "layer": "DWD", "columns": []}]

    result = score_model_design_health(
        _context(
            tables,
            models={
                "dwd_transactions": {
                    "data_domain": "10",
                    "business_area": "CLNT",
                }
            },
            business_domain_config=business_config,
        ),
        llm_results=[
            TableInspectResult(
                table_name="dwd_transactions",
                declared_layer="DWD",
                inferred_layer="DWD",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                inferred_data_domain="04",
                inferred_business_area="PAYM",
            )
        ],
    )

    assert _issue_rule_ids(result) == {
        "ARCH_DATA_DOMAIN_MATCHES_LLM",
        "ARCH_BUSINESS_AREA_MATCHES_LLM",
    }


def test_score_model_design_health_limits_business_checks_by_layer():
    business_config = _business_domain_config()
    result = score_model_design_health(
        _context(
            [{"name": "dws_transactions", "layer": "DWS", "columns": []}],
            models={
                "dws_transactions": {
                    "business_area": "CLNT",
                }
            },
            business_domain_config=business_config,
        ),
        llm_results=[
            TableInspectResult(
                table_name="dws_transactions",
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                inferred_data_domain="04",
                inferred_business_area="PAYM",
            )
        ],
    )

    assert _issue_rule_ids(result) == {"ARCH_BUSINESS_AREA_MATCHES_LLM"}
    assert not _checks_by_rule(result, "ARCH_DATA_DOMAIN_MATCHES_LLM")


def test_score_asset_completeness_classifies_missing_assets(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()

    (project_dir / "mid" / "ddl" / "dwd_orders.sql").write_text(
        """
CREATE TABLE demo.dwd_orders (
    order_id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1;
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_orders.yaml").write_text(
        "name: dws_orders\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_missing.sql").write_text(
        "INSERT INTO demo.dws_missing SELECT 1 AS order_id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert result["score"] == 25.0
    assert {
        (item["target"]["name"], item["rule_id"]) for item in result["issues"]
    } == {
        ("dwd_orders", "ASSET_DDL_HAS_MODEL"),
        ("dwd_orders", "ASSET_EXECUTABLE_DDL_HAS_TASK"),
        ("dws_orders", "ASSET_MODEL_HAS_DDL"),
        ("dws_missing", "ASSET_TASK_OUTPUT_HAS_DDL"),
        ("dws_missing", "ASSET_TASK_OUTPUT_HAS_MODEL"),
        ("mid/tasks/dws_missing.sql", "ASSET_TASK_LINEAGE_MATCHES_OUTPUT"),
    }
    assert all(item["severity"] == "高" for item in result["issues"])
    assert all(
        check["passed"]
        for rule_id in [
            "ASSET_TASK_SINGLE_OUTPUT",
            "ASSET_TABLE_SINGLE_WRITER",
        ]
        for check in _checks_by_rule(result, rule_id)
    )
    task_lineage_check = next(
        check
        for check in result["checks"]
        if check["rule_id"] == "ASSET_TASK_LINEAGE_MATCHES_OUTPUT"
    )
    assert (
        task_lineage_check["actual"] == "实际产出=['dws_missing']，血缘目标=[]"
    )
    assert task_lineage_check["evidence"] == {
        "outputs": ["dws_missing"],
        "lineage_targets": [],
    }


def test_score_asset_completeness_ignores_dropped_ctas_temp_tables(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()

    (project_dir / "mid" / "ddl" / "dws_orders.sql").write_text(
        """
CREATE TABLE demo.dws_orders (
    order_id BIGINT,
    amount DECIMAL(12, 2)
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1;
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_orders.yaml").write_text(
        "name: dws_orders\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_orders.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT order_id, amount
FROM demo.dwd_orders;

INSERT INTO demo.dws_orders
SELECT order_id, amount
FROM demo.tmp_orders_stage;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {"name": "dws_orders", "layer": "DWS", "columns": []},
            {
                "name": "tmp_orders_stage",
                "layer": "OTHER",
                "columns": [],
                "is_transient": True,
                "transient_sources": ["dws_orders.sql"],
            },
        ],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {
                "source_file": "dws_orders.sql",
                "target": "demo.tmp_orders_stage.order_id",
            },
            {
                "source_file": "dws_orders.sql",
                "target": "demo.dws_orders.order_id",
            },
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert catalog["tasks"][0]["output_tables"] == {"dws_orders"}
    assert catalog["tasks"][0]["lineage_targets"] == {"dws_orders"}
    assert "tmp_orders_stage" not in catalog["tables"]
    assert result["issues"] == []


def test_assets_does_not_link_transient_only_task_as_asset(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "tmp_orders_stage.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT order_id, amount
FROM demo.dwd_orders;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {
                "name": "tmp_orders_stage",
                "layer": "OTHER",
                "columns": [],
                "is_transient": True,
                "transient_sources": ["tmp_orders_stage.sql"],
            },
        ],
        None,
        project_dir,
        edges=[
            {
                "source_file": "tmp_orders_stage.sql",
                "target": "demo.tmp_orders_stage.order_id",
            }
        ],
        indirect_edges=[],
    )

    assert catalog["tasks"][0]["output_tables"] == set()
    assert "tmp_orders_stage" not in catalog["tables"]


def test_assets_links_structured_edge_target_to_task(tmp_path):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "dws_orders.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [{"name": "dws_orders", "layer": "DWS", "columns": []}],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {
                "source": {"type": "column", "id": "dwd_orders.id"},
                "target": {"type": "column", "id": "demo.dws_orders.id"},
                "relation_type": "direct",
                "source_file": "dws_orders.sql",
            }
        ],
        indirect_edges=[],
    )

    assert catalog["tasks"][0]["lineage_targets"] == {"dws_orders"}


def _write_simple_table_assets(project_dir, table_names):
    (project_dir / "mid" / "ddl").mkdir(parents=True, exist_ok=True)
    (project_dir / "mid" / "models").mkdir(exist_ok=True)
    for table_name in table_names:
        (project_dir / "mid" / "ddl" / f"{table_name}.sql").write_text(
            f"""
CREATE TABLE demo.{table_name} (
    id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1;
""",
            encoding="utf-8",
        )
        (project_dir / "mid" / "models" / f"{table_name}.yaml").write_text(
            f"name: {table_name}\nlayer: DWS\n",
            encoding="utf-8",
        )


def test_score_asset_completeness_flags_task_with_no_persistent_output(
    tmp_path,
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "tmp_orders_stage.sql").write_text(
        """
CREATE TABLE demo.tmp_orders_stage AS
SELECT id
FROM demo.dwd_orders;

DROP TABLE IF EXISTS demo.tmp_orders_stage;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert "ASSET_TASK_SINGLE_OUTPUT" in _issue_rule_ids(result)
    task_output_check = _checks_by_rule(
        result,
        "ASSET_TASK_SINGLE_OUTPUT",
    )[0]
    assert (
        task_output_check["target"]["name"] == "mid/tasks/tmp_orders_stage.sql"
    )
    assert task_output_check["actual"] == "实际产出=[]"


def test_score_asset_completeness_flags_task_with_multiple_outputs(tmp_path):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders", "dws_order_extra"])
    (project_dir / "mid" / "tasks").mkdir(exist_ok=True)
    (project_dir / "mid" / "tasks" / "dws_orders.sql").write_text(
        """
INSERT INTO demo.dws_orders SELECT 1 AS id;
INSERT INTO demo.dws_order_extra SELECT 1 AS id;
""",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [
            {"name": "dws_orders", "layer": "DWS", "columns": []},
            {"name": "dws_order_extra", "layer": "DWS", "columns": []},
        ],
        {
            "dws_orders": {"name": "dws_orders", "layer": "DWS"},
            "dws_order_extra": {"name": "dws_order_extra", "layer": "DWS"},
        },
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {"source_file": "dws_orders.sql", "target": "dws_order_extra.id"},
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert _issue_rule_ids(result) == {"ASSET_TASK_SINGLE_OUTPUT"}
    task_output_check = _checks_by_rule(
        result,
        "ASSET_TASK_SINGLE_OUTPUT",
    )[0]
    assert task_output_check["target"]["name"] == "mid/tasks/dws_orders.sql"
    assert task_output_check["actual"] == (
        "实际产出=['dws_order_extra', 'dws_orders']"
    )


def test_score_asset_completeness_flags_duplicate_table_writers(tmp_path):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders"])
    (project_dir / "mid" / "tasks").mkdir(exist_ok=True)
    (project_dir / "mid" / "tasks" / "dws_orders.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_orders_patch.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 2 AS id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [{"name": "dws_orders", "layer": "DWS", "columns": []}],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {"source_file": "dws_orders_patch.sql", "target": "dws_orders.id"},
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert _issue_rule_ids(result) == {"ASSET_TABLE_SINGLE_WRITER"}
    writer_check = _checks_by_rule(
        result,
        "ASSET_TABLE_SINGLE_WRITER",
    )[0]
    assert writer_check["target"]["name"] == "dws_orders"
    assert writer_check["actual"] == (
        "产出Task=['mid/tasks/dws_orders.sql', 'mid/tasks/dws_orders_patch.sql']"
    )


def test_score_asset_completeness_allows_full_refresh_companion_writer(
    tmp_path,
):
    project_dir = tmp_path / "demo"
    _write_simple_table_assets(project_dir, ["dws_orders"])
    (project_dir / "mid" / "tasks" / "full_refresh").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "dws_orders.sql").write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )
    (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dws_orders_full_refresh.sql"
    ).write_text(
        "INSERT INTO demo.dws_orders SELECT 1 AS id;",
        encoding="utf-8",
    )

    catalog = build_asset_catalog(
        [{"name": "dws_orders", "layer": "DWS", "columns": []}],
        {"dws_orders": {"name": "dws_orders", "layer": "DWS"}},
        project_dir,
        edges=[
            {"source_file": "dws_orders.sql", "target": "dws_orders.id"},
            {
                "source_file": "full_refresh/dws_orders_full_refresh.sql",
                "target": "dws_orders.id",
            },
        ],
        indirect_edges=[],
    )
    result = score_asset_completeness(_context(assets=catalog))

    assert result["issues"] == []


def test_naming_diagnostics_are_agent_actionable():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")

    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "dwd_customer",
                    "layer": "DWD",
                    "columns": [{"name": "customer_id"}],
                }
            ],
            nc,
        )
    )

    assert result["score"] == 33.3
    assert _issue_rule_ids(result) == {
        "NAMING_TABLE_TEMPLATE",
        "NAMING_COLUMN_NAME",
    }
    table_check = _checks_by_rule(result, "NAMING_TABLE_TEMPLATE")[0]
    assert table_check["schema_version"] == "assess.diagnostic.v1"
    assert table_check["dimension"] == "naming"
    assert table_check["status"] == "failed"
    assert table_check["severity"] == "中"
    assert table_check["summary"] == "表名不符合规范模板"
    assert table_check["target"] == {
        "type": "table",
        "name": "dwd_customer",
        "layer": "DWD",
    }
    assert table_check["expected"]["rule_names"] == ["TABLE_DWD"]
    assert table_check["actual"] == {"value": "dwd_customer"}
    assert table_check["diagnostic"]["code"] == "literal_mismatch"
    assert (
        table_check["diagnostic"]["attempts"][0]["failure"]["code"]
        == "literal_mismatch"
    )
    assert "evidence" not in table_check
    assert table_check["remediation"]["strategy"] == (
        "rename_table_and_rewrite_references"
    )

    column_check = _checks_by_rule(result, "NAMING_COLUMN_NAME")[0]
    assert column_check["target"] == {
        "type": "column",
        "name": "customer_id",
        "table": "dwd_customer",
        "qualified_name": "dwd_customer.customer_id",
        "layer": "DWD",
    }
    assert column_check["expected"]["rule_names"] == ["COLUMN_DEFAULT"]
    assert column_check["expected"]["attempts"][0]["segments"][0]["type"][
        "patterns"
    ] == ["^[A-Z][A-Z0-9_]{0,14}$"]
    assert column_check["actual"] == {"value": "customer_id"}
    assert column_check["diagnostic"]["code"] == "type_pattern_mismatch"
    assert column_check["diagnostic"]["attempts"][0]["failure"][
        "expected"
    ] == ["^[A-Z][A-Z0-9_]{0,14}$"]
    assert column_check["remediation"]["strategy"] == (
        "rename_columns_and_rewrite_references"
    )
    column_issue = next(
        issue
        for issue in result["issues"]
        if issue["rule_id"] == "NAMING_COLUMN_NAME"
    )
    assert column_issue["fingerprint"] == (
        "naming|NAMING_COLUMN_NAME|column|dwd_customer.customer_id"
    )


def test_score_naming_conventions_does_not_expose_internal_violation_text():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")

    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "dwd_customer_name_that_is_too_long",
                    "layer": "DWD",
                    "columns": [],
                }
            ],
            nc,
        )
    )

    assert {issue["rule_id"] for issue in result["issues"]} == {
        "NAMING_TABLE_TEMPLATE",
        "NAMING_TABLE_MAX_LENGTH",
    }
    rendered_checks = yaml.safe_dump(
        result["checks"],
        allow_unicode=True,
        sort_keys=True,
    )
    assert "违反:" not in rendered_checks


def test_score_naming_conventions_issues_include_related_files(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()

    table_name = "dwd_customer"
    (project_dir / "mid" / "ddl" / f"{table_name}.sql").write_text(
        f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    customer_id BIGINT
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / f"{table_name}.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS customer_id;",
        encoding="utf-8",
    )

    result = score_naming_conventions(
        _context(
            [],
            nc,
            {table_name: {"layer": "DWD"}},
            project_dir=project_dir,
        )
    )

    column_issue = next(
        issue
        for issue in result["issues"]
        if issue["rule_id"] == "NAMING_COLUMN_NAME"
    )
    assert column_issue["remediation"]["related_files"] == [
        "demo/mid/ddl/dwd_customer.sql",
        "demo/mid/tasks/dwd_customer.sql",
        "demo/mid/models/dwd_customer.yaml",
    ]


def test_naming_checks_business_segments_against_valid_model_metadata(
    tmp_path,
):
    nc = _business_naming_config(tmp_path)
    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "M_PAYM_04_CHREM_DI",
                    "layer": "DWD",
                    "columns": [],
                }
            ],
            nc,
            {
                "M_PAYM_04_CHREM_DI": {
                    "layer": "DWD",
                    "data_domain": "10",
                    "business_area": "CLNT",
                },
            },
            nc.business_domain_config,
        )
    )

    semantic_check = _checks_by_rule(
        result,
        "NAMING_SEMANTIC_METADATA_ALIGNMENT",
    )[0]
    assert semantic_check["passed"] is False
    assert any(
        "model.data_domain=10" in violation
        for violation in semantic_check["actual"]["violations"]
    )
    assert any(
        "model.business_area=CLNT" in violation
        for violation in semantic_check["actual"]["violations"]
    )


def test_score_naming_conventions_checks_project_file_names(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()

    table_name = "M_WEMG_04_CHREM_DI"
    ddl = f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    ID BIGINT
) ENGINE=OLAP
DUPLICATE KEY(ID)
DISTRIBUTED BY HASH(ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
    (project_dir / "mid" / "ddl" / "wrong_ddl.sql").write_text(ddl)
    (project_dir / "mid" / "models" / "wrong_model.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n"
    )
    (project_dir / "mid" / "tasks" / "wrong_task.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )

    result = score_naming_conventions(
        _context(
            [{"name": table_name, "layer": "DWD", "columns": []}],
            nc,
            {table_name: {"layer": "DWD"}},
            project_dir=project_dir,
            edges=[
                {
                    "source": "ods_source.ID",
                    "target": f"{table_name}.ID",
                    "source_file": "wrong_task.sql",
                }
            ],
            indirect_edges=[],
        )
    )

    assert _issue_rule_ids(result) == {
        "NAMING_DDL_FILE_NAME",
        "NAMING_MODEL_FILE_NAME",
        "NAMING_TASK_OUTPUT_NAME",
    }
    assert all(issue["severity"] == "低" for issue in result["issues"])


def test_score_naming_conventions_checks_atomic_and_derived_metrics():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "M_WEMG_04_CHREM_DI",
                    "layer": "DWD",
                    "columns": [],
                }
            ],
            nc,
            {
                "M_WEMG_04_CHREM_DI": {
                    "atomic_metrics": ["PAY_AMT", "pay_amt"],
                    "derived_metrics": [
                        "7D_OLD_PAY_AMT",
                        "transaction_count",
                    ],
                }
            },
        )
    )

    assert result["rule_summary"]["NAMING_ATOMIC_METRIC"]["pass_count"] == 1
    assert result["rule_summary"]["NAMING_DERIVED_METRIC"]["pass_count"] == 1
    assert _issue_rule_ids(result) == {
        "NAMING_ATOMIC_METRIC",
        "NAMING_DERIVED_METRIC",
    }


def test_score_naming_conventions_checks_dws_and_dim_entity_alignment():
    nc = load_naming_config(
        PROJECT_ROOT / "warehouses" / "shop" / "naming_config.yaml"
    )

    dws_result = score_naming_conventions(
        _context(
            [
                {
                    "name": "I_SHOP_CAT_SALE_DS",
                    "layer": "DWS",
                    "columns": [
                        {"name": "category_id"},
                        {"name": "stat_date"},
                    ],
                }
            ],
            nc,
            {
                "I_SHOP_CAT_SALE_DS": {
                    "grain": {
                        "keys": ["category_id", "stat_date"],
                        "entities": ["PROD"],
                        "time_column": "stat_date",
                        "time_period": "D",
                    }
                }
            },
        )
    )
    assert "NAMING_DWS_ENTITY_ALIGNMENT" in _issue_rule_ids(dws_result)

    dim_result = score_naming_conventions(
        _context(
            [
                {
                    "name": "DIM_BASE_PROD_INFO_INFO",
                    "layer": "DIM",
                    "columns": [],
                }
            ],
            nc,
            {
                "DIM_BASE_PROD_INFO_INFO": {
                    "entity": {
                        "code": "CUST",
                        "key_columns": ["product_id"],
                    }
                }
            },
        )
    )
    assert "NAMING_DIM_ENTITY_ALIGNMENT" in _issue_rule_ids(dim_result)


def test_score_naming_conventions_checks_dim_classification_alignment():
    nc = load_naming_config(
        PROJECT_ROOT / "warehouses" / "shop" / "naming_config.yaml"
    )

    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "DIM_BASE_PROD_INFO_INFO",
                    "layer": "DIM",
                    "columns": [],
                }
            ],
            nc,
            {
                "DIM_BASE_PROD_INFO_INFO": {
                    "dimension_role": "ADDT",
                    "dimension_content_type": "TAG",
                    "entities": [
                        {
                            "code": "PROD",
                            "type": "primary",
                            "key_columns": ["product_id"],
                        }
                    ],
                }
            },
        )
    )

    assert "NAMING_DIM_CLASSIFICATION_ALIGNMENT" in _issue_rule_ids(result)
    checks = _checks_by_rule(result, "NAMING_DIM_CLASSIFICATION_ALIGNMENT")
    assert checks[0]["passed"] is False
    assert "dimension_role=ADDT" in checks[0]["message"]
    assert "dimension_content_type=TAG" in checks[0]["message"]


def test_score_naming_conventions_ignores_lineage_tables_when_project_dir_exists(
    tmp_path,
):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)

    result = score_naming_conventions(
        _context(
            [
                {
                    "name": "M_WEMG_04_CHREM_DI",
                    "layer": "DWD",
                    "columns": [{"name": "BAD_FIELD"}],
                }
            ],
            nc,
            project_dir=project_dir,
        )
    )

    assert result["score"] == 100.0
    assert result["checks"] == []
    assert result["issues"] == []
