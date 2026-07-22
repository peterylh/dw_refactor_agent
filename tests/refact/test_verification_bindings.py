from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
import yaml

import dw_refactor_agent.refactor.shadow_run as shadow_run_module
from dw_refactor_agent.execution.model_config import ExecutionConfigError
from dw_refactor_agent.execution.sql_executor import ShadowSqlExecutor
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.qa_pool import QaSlotOwnership
from dw_refactor_agent.refactor.shadow_manifest import (
    compile_shadow_manifest,
    manifest_summary,
)
from dw_refactor_agent.refactor.shadow_run import (
    execute_shadow_plan,
    run_shadow_plan,
)
from dw_refactor_agent.refactor.verification_bindings import (
    build_task_rendering_context,
    freeze_job_invocations,
    materialize_frozen_job_invocations,
    validate_task_rendering_context,
    verification_planner,
)


def _write_template_project(tmp_path):
    project_dir = tmp_path / "warehouses" / "demo"
    task_dir = project_dir / "mid" / "tasks"
    model_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    for path in (task_dir, model_dir, ddl_dir):
        path.mkdir(parents=True, exist_ok=True)

    secret = "prod-secret-do-not-log"
    warehouse = {
        "name": "demo",
        "catalog": "internal",
        "database": "demo_dm",
        "qa_database": "demo_dm_qa",
        "task_templates": {
            "version": 1,
            "analysis": {
                "startup": {"etl_date": "2000-02-29"},
                "project": {
                    "cdm_schema": "analysis_dm",
                    "secret_token": "analysis-secret",
                },
            },
            "bindings": {
                "prod": {
                    "project": {
                        "cdm_schema": "demo_dm",
                        "secret_token": secret,
                    }
                }
            },
        },
    }
    (project_dir / "warehouse.yaml").write_text(
        yaml.safe_dump(warehouse, sort_keys=False),
        encoding="utf-8",
    )
    (model_dir / "report.yaml").write_text(
        """version: 2
name: report
layer: DWS
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: D
""",
        encoding="utf-8",
    )
    (ddl_dir / "report.sql").write_text(
        "CREATE TABLE demo_dm.report (stat_date DATE) ENGINE=OLAP;",
        encoding="utf-8",
    )
    sql_path = task_dir / "report.sql"
    sql_path.write_text(
        """CREATE TABLE ${cdm_schema}.${run_table}
LIKE ${cdm_schema}.source_data;
INSERT INTO ${cdm_schema}.${run_table}
SELECT * FROM ${cdm_schema}.source_data
WHERE secret_token = ${secret_token};
INSERT INTO ${cdm_schema}.report
SELECT * FROM ${cdm_schema}.${run_table}
WHERE stat_date = ${etl_date}
""",
        encoding="utf-8",
    )
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
        "project_params": [
            {
                "prop": "cdm_schema",
                "type": "IDENTIFIER",
                "source": "project.cdm_schema",
                "required": True,
            },
            {
                "prop": "secret_token",
                "type": "VARCHAR",
                "source": "project.secret_token",
                "required": True,
                "sensitive": True,
            },
        ],
        "local_params": [
            {
                "prop": "run_table",
                "direct": "IN",
                "type": "IDENTIFIER",
                "value": {
                    "derive": {
                        "from": "etl_date",
                        "operation": "format_date",
                        "format": "yyyyMMdd",
                        "prefix": "tmp_run_",
                    }
                },
            }
        ],
        "usage": {
            "slices": [{"prop": "etl_date", "parameter": "etl_date"}],
            "dynamic_relations": [
                {"prop": "run_table", "lifecycle": "invocation"}
            ],
        },
    }
    contract_path = sql_path.with_suffix(".yaml")
    contract_path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    return sql_path, contract_path, secret


def _frozen_plan(tmp_path):
    sql_path, contract_path, secret = _write_template_project(tmp_path)
    task_rendering = build_task_rendering_context(
        reference_date=date(2025, 1, 20)
    )
    planner = verification_planner("demo", tmp_path, task_rendering)
    job = {
        "job": "report",
        "target": "report",
        "file": sql_path.relative_to(tmp_path).as_posix(),
        "layer": "DWS",
        "execution_values": ["2025-01-15", "2025-01-16"],
    }
    job["verification_invocations"] = freeze_job_invocations(
        job,
        planner=planner,
        root=tmp_path,
    )
    plan = {
        "run_id": "run-1",
        "project": "demo",
        "project_db": "demo_dm",
        "qa_db": "demo_dm_qa",
        "qa_database_pool": ["demo_dm_qa"],
        "baseline_ddl": {
            "source_data": (
                "CREATE TABLE demo_dm.source_data "
                "(stat_date DATE, secret_token VARCHAR(64)) ENGINE=OLAP;"
            ),
            "report": (
                "CREATE TABLE demo_dm.report "
                "(stat_date DATE, secret_token VARCHAR(64)) ENGINE=OLAP;"
            ),
        },
        "ddl_changes": [],
        "jobs_to_run": [job],
        "task_rendering": task_rendering,
        "execution_graph": {
            "format_version": 1,
            "project": "demo",
            "jobs": ["report"],
            "dependencies": {},
        },
        "verification": {"checks": []},
        "analysis_snapshot": {"workspace_fingerprint": "sha256:" + "a" * 64},
        "plan_fingerprint": "sha256:" + "b" * 64,
    }
    return plan, planner, contract_path, secret


def test_verification_plan_freezes_safe_complete_binding_evidence(tmp_path):
    plan, planner, _contract_path, secret = _frozen_plan(tmp_path)

    summaries = plan["jobs_to_run"][0]["verification_invocations"]

    assert len(summaries) == 2
    assert {item["mode"] for item in summaries} == {"verification"}
    assert all(
        item["binding_digest"].startswith("sha256:") for item in summaries
    )
    assert summaries[0]["binding_summary"]["secret_token"] == "<redacted>"
    assert "secret_token" not in summaries[0]["render_inputs"]
    assert secret not in json.dumps(summaries)
    assert (
        len(
            materialize_frozen_job_invocations(
                plan["jobs_to_run"][0],
                planner=planner,
                root=tmp_path,
            )
        )
        == 2
    )


def test_multiple_rendered_dynamic_relations_enter_shadow_scope(tmp_path):
    plan, planner, _contract_path, _secret = _frozen_plan(tmp_path)

    manifest = compile_shadow_manifest(plan, tmp_path, planner)
    summary = manifest_summary(manifest)
    routes = summary["jobs"]["report"]["routes"]["write"]

    assert summary["blockers"] == []
    assert {"tmp_run_20250115", "tmp_run_20250116"}.issubset(routes)
    assert summary["jobs"]["report"]["requires_serial_slices"] is True


def test_shadow_renders_then_rewrites_then_injects_session_params(tmp_path):
    plan, planner, _contract_path, _secret = _frozen_plan(tmp_path)
    job = plan["jobs_to_run"][0]
    manifest = compile_shadow_manifest(plan, tmp_path, planner)
    invocation = materialize_frozen_job_invocations(
        job,
        planner=planner,
        root=tmp_path,
    )[0]
    executor = ShadowSqlExecutor(
        context=manifest.jobs["report"].context,
        qa_ready_tables=set(),
        run_sql_text=lambda *_args, **_kwargs: "",
    )

    rendered = executor.render(invocation)
    comparable = rendered.replace("`", "")

    assert rendered.startswith("SET @etl_date = '2025-01-15';")
    assert "${" not in rendered
    assert "demo_dm_qa.tmp_run_20250115" in comparable
    assert "demo_dm.tmp_run_20250115" not in comparable
    assert rendered.index("SET @full_refresh") < rendered.index("CREATE TABLE")


def test_shadow_result_contains_only_redacted_binding_summaries(
    tmp_path, capsys
):
    plan, _planner, _contract_path, secret = _frozen_plan(tmp_path)

    result = execute_shadow_plan(plan, root=tmp_path, dry_run=True)
    captured = capsys.readouterr()
    serialized = json.dumps(result)
    run_jobs = next(
        phase for phase in result["phases"] if phase["name"] == "run_jobs"
    )

    assert result["status"] == "dry_run"
    assert secret not in serialized
    assert secret not in captured.out
    assert secret not in captured.err
    assert (
        run_jobs["jobs"][0]["rendered_bindings"][0]["binding_summary"][
            "secret_token"
        ]
        == "<redacted>"
    )


def test_template_execution_error_is_redacted_from_logs_and_results(
    tmp_path,
    monkeypatch,
    capsys,
):
    plan, _planner, _contract_path, secret = _frozen_plan(tmp_path)
    monkeypatch.setattr(
        shadow_run_module,
        "require_slot_ownership",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        shadow_run_module,
        "run_sql",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        shadow_run_module,
        "run_sql_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"syntax error near {secret}")
        ),
    )
    ownership = QaSlotOwnership(
        2,
        "demo",
        "run-1",
        "execution-1",
        "demo_dm_qa",
        plan["plan_fingerprint"],
        plan["analysis_snapshot"]["workspace_fingerprint"],
        "2026-07-22 12:00:00",
        1784702400,
    )

    result = execute_shadow_plan(
        plan,
        root=tmp_path,
        claimed_ownership=ownership,
        timing_detail=True,
    )
    captured = capsys.readouterr()
    serialized = json.dumps(result)
    job = next(
        phase for phase in result["phases"] if phase["name"] == "run_jobs"
    )["jobs"][0]

    assert result["status"] == "failed"
    assert secret not in serialized
    assert secret not in captured.out
    assert secret not in captured.err
    assert "sensitive details omitted" in job["error"]
    assert "sensitive details omitted" in job["invocations"][0]["error"]


def test_template_compile_error_is_redacted_before_result_and_logging(
    tmp_path,
    monkeypatch,
    capsys,
):
    plan, _planner, _contract_path, secret = _frozen_plan(tmp_path)
    monkeypatch.setattr(
        shadow_run_module,
        "compile_shadow_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"parse failed near {secret}")
        ),
    )

    result = execute_shadow_plan(plan, root=tmp_path, dry_run=True)
    captured = capsys.readouterr()

    assert result["status"] == "failed"
    assert secret not in json.dumps(result)
    assert secret not in captured.out
    assert secret not in captured.err
    assert result["phases"][0]["blockers"] == [
        "shadow manifest compilation failed; sensitive details omitted"
    ]


def test_sensitive_dynamic_relation_is_rejected_before_manifest(tmp_path):
    plan, _planner, contract_path, _secret = _frozen_plan(tmp_path)
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    contract["local_params"][0]["sensitive"] = True
    contract_path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    planner = verification_planner(
        "demo",
        tmp_path,
        plan["task_rendering"],
    )

    with pytest.raises(
        ExecutionConfigError,
        match="sensitive_identifier",
    ):
        freeze_job_invocations(
            plan["jobs_to_run"][0],
            planner=planner,
            root=tmp_path,
        )


def test_binding_change_after_analysis_rejects_frozen_plan(tmp_path):
    plan, _planner, _contract_path, _secret = _frozen_plan(tmp_path)
    warehouse_path = tmp_path / "warehouses" / "demo" / "warehouse.yaml"
    warehouse = yaml.safe_load(warehouse_path.read_text(encoding="utf-8"))
    warehouse["task_templates"]["bindings"]["prod"]["project"][
        "secret_token"
    ] = "changed-secret"
    warehouse_path.write_text(
        yaml.safe_dump(warehouse, sort_keys=False),
        encoding="utf-8",
    )
    planner = verification_planner(
        "demo",
        tmp_path,
        plan["task_rendering"],
    )

    with pytest.raises(ArtifactFormatError, match="differ from the frozen"):
        materialize_frozen_job_invocations(
            plan["jobs_to_run"][0],
            planner=planner,
            root=tmp_path,
        )


def test_verification_context_rejects_ambient_environment_and_renderer_change():
    context = build_task_rendering_context(reference_date=date(2025, 1, 20))
    context["environment"] = "test"
    with pytest.raises(ArtifactFormatError, match="must be prod"):
        validate_task_rendering_context(context)

    context = build_task_rendering_context(reference_date=date(2025, 1, 20))
    context["renderer_semantics_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ArtifactFormatError, match="semantics differ"):
        validate_task_rendering_context(context)


def test_template_load_failure_precedes_qa_slot_claim(tmp_path, monkeypatch):
    plan, _planner, contract_path, _secret = _frozen_plan(tmp_path)
    contract_path.write_text(
        "version: 1\nstrict: true\nstartup_params: invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        shadow_run_module,
        "require_fresh_plan_bundle",
        lambda _path: SimpleNamespace(plan=plan, root=tmp_path),
    )
    claims = []
    monkeypatch.setattr(
        shadow_run_module,
        "claim_qa_slot",
        lambda **kwargs: claims.append(kwargs),
    )
    output_path = tmp_path / "verification" / "result.json"

    result = run_shadow_plan(
        tmp_path / "verification" / "plan.json",
        output_path,
        provenance={
            "workspace_fingerprint": plan["analysis_snapshot"][
                "workspace_fingerprint"
            ],
            "plan_fingerprint": plan["plan_fingerprint"],
        },
    )

    assert result["status"] == "failed"
    assert result["phases"][0]["name"] == "compile_shadow_manifest"
    assert claims == []
