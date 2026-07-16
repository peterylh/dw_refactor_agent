import json
import sys
from pathlib import Path

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.generation_contract import (
    validate_generate_candidate,
)
from dw_refactor_agent.assessment.llm.model_metadata_checkpoint import (
    GenerateCheckpointLockError,
    GenerateModelCheckpoint,
)
from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    run_generate_model_metadata,
    run_metadata_write,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from tests.assess.model_metadata_writer_test_support import (
    _catalog_payload,
    _configure_project_root,
    _expected_pay_amt_1d_metric,
    _sample_dws_result,
    _sample_fact_result,
    _write_catalog_project,
    _write_split_catalog,
)


def test_run_metadata_write_reuses_table_inspector(
    monkeypatch, sample_lineage_data, isolated_writer_project
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    created_cache_files = []
    seen_dws_contexts = []

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.api_key = api_key
            self.model = model
            self.cache_file = cache_file
            self.max_retries = max_retries
            self.parallelism = parallelism
            created_cache_files.append(cache_file)

        def inspect_batch(self, contexts):
            if contexts and contexts[0].layer == "DWS":
                seen_dws_contexts.extend(contexts)
            results = []
            for ctx in contexts:
                if ctx.table_name == "dwd_order_detail":
                    results.append(_sample_fact_result())
                elif ctx.table_name == "dws_store_sales_daily":
                    results.append(_sample_dws_result())
                else:
                    results.append(
                        TableInspectResult(
                            table_name=ctx.table_name,
                            declared_layer=ctx.layer,
                            inferred_layer="DIM",
                            table_type="dimension",
                            confidence=0.9,
                            reasoning_steps=[],
                        )
                    )
            return results

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda project: sample_lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    original_pipeline = writer_module.run_inspection_pipeline
    pipeline_calls = []

    def tracking_pipeline(*args, **kwargs):
        pipeline_calls.append(
            {
                "project": args[0],
                "base_model_metadata": kwargs.get("base_model_metadata"),
                "metric_groups": kwargs.get("metric_groups"),
            }
        )
        return original_pipeline(*args, **kwargs)

    monkeypatch.setattr(
        writer_module, "run_inspection_pipeline", tracking_pipeline
    )

    result = run_metadata_write(
        isolated_writer_project, api_key="test", dry_run=True
    )

    updates_by_table = {
        update["table"]: update for update in result["model_updates"]
    }

    assert result["inspected_table_count"] == 3
    assert result["write_scope"] == "all"
    assert result["metric_table_count"] == 2
    assert result["metadata_only_table_count"] == 1
    assert result["dwd_table_count"] == 1
    assert result["dws_table_count"] == 1
    assert result["dim_table_count"] == 1
    assert result["fact_table_count"] == 2
    assert result["atomic_metric_count"] == 1
    assert result["derived_metric_count"] == 2
    assert result["calculated_metric_count"] == 1
    assert result["metric_count"] == 4
    assert result["derived_metric_violation_count"] == 1
    assert result["calculated_metric_violation_count"] == 1
    assert result["non_atomic_metric_violation_count"] == 2
    assert result["model_update_count"] == 0
    assert result["model_change_count"] == len(result["model_updates"])
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["project"] == isolated_writer_project
    assert (
        pipeline_calls[0]["base_model_metadata"]["dwd_customer"]["layer"]
        == "DWD"
    )
    assert pipeline_calls[0]["metric_groups"] is None
    assert created_cache_files[0] == config.assess_cache_path(
        isolated_writer_project, "inspect.json"
    )
    assert updates_by_table["dwd_customer"]["layer"] == "DIM"
    assert updates_by_table["dwd_customer"]["table_type"] == "dimension"
    assert updates_by_table["dwd_customer"]["updated"] is False
    assert updates_by_table["dws_store_sales_daily"]["table"] == (
        "dws_store_sales_daily"
    )
    assert seen_dws_contexts[0].upstream_metric_groups["dwd_order_detail"] == {
        "atomic_metrics": ["pay_amt"],
        "derived_metrics": [_expected_pay_amt_1d_metric()],
        "calculated_metrics": ["gross_profit"],
    }
    assert result["skipped_model_updates"] == []


def test_model_metadata_writer_cli_dispatches_refresh_and_generate_modes(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
        },
    )

    calls = []

    def fake_catalog_write(*args, **kwargs):
        calls.append(("refresh", args, kwargs))
        return {
            "project": project,
            "source": "catalog",
            "paths": {"taxonomy": "business_taxonomy.yaml"},
            "written_names": ["business_processes"],
            "inspected_table_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
        }

    def fake_generate(*args, **kwargs):
        calls.append(("generate", args, kwargs))
        return {
            "project": project,
            "source": "direct_model_generation",
            "planned_catalog_written_names": [],
            "catalog_init_written_names": [],
            "planned_deleted_model_files": [],
            "model_change_count": 0,
            "model_update_count": 0,
        }

    def fake_metadata_write(*args, **kwargs):
        calls.append(("refresh_llm", args, kwargs))
        return {
            "project": project,
            "write_scope": kwargs["write_scope"],
            "inspected_table_count": 0,
            "metric_table_count": 0,
            "metadata_only_table_count": 0,
            "dwd_table_count": 0,
            "dws_table_count": 0,
            "dim_table_count": 0,
            "fact_table_count": 0,
            "metric_count": 0,
            "atomic_metric_count": 0,
            "derived_metric_count": 0,
            "calculated_metric_count": 0,
            "non_atomic_metric_violation_count": 0,
            "metadata_warning_count": 0,
            "model_change_count": 0,
            "model_update_count": 0,
        }

    monkeypatch.setattr(
        writer_module,
        "run_catalog_metadata_write",
        fake_catalog_write,
    )
    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        fake_generate,
    )
    monkeypatch.setattr(
        writer_module,
        "run_metadata_write",
        fake_metadata_write,
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")

    monkeypatch.setattr(
        sys,
        "argv",
        ["model_metadata_writer.py", "--project", project],
    )

    writer_module.main()
    assert calls[-1][0] == "refresh"
    assert calls[-1][2]["write_scope"] == "business"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "refresh",
            "--llm",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "refresh_llm"
    assert calls[-1][2]["write_scope"] == "all"
    assert calls[-1][2]["update_catalog"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "generate",
            "--dry-run",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "generate"
    assert calls[-1][2]["write_scope"] == "all"
    assert calls[-1][2]["replace_existing_models"] is True
    assert calls[-1][2]["update_catalog"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "generate",
            "--llm",
            "--dry-run",
            "--base-url",
            "https://api.deepseek.com",
            "--max-retries",
            "3",
            "--parallel",
            "4",
            "--request-timeout",
            "12",
            "--no-cache",
            "--quiet",
        ],
    )

    writer_module.main()
    assert calls[-1][0] == "generate"
    assert calls[-1][2]["api_key"] == "test"
    assert calls[-1][2]["base_url"] == (
        "https://api.deepseek.com/chat/completions"
    )
    assert calls[-1][2]["max_retries"] == 3
    assert calls[-1][2]["parallelism"] == 4
    assert calls[-1][2]["request_timeout"] == 12
    assert calls[-1][2]["no_cache"] is True
    assert calls[-1][2]["show_progress"] is False

    output_path = (
        project_dir
        / "artifacts"
        / "assessment"
        / ("model_metadata_result.json")
    )
    assert output_path.exists()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "catalog",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        writer_module.main()
    assert exc_info.value.code == 2


def test_model_metadata_writer_cli_fails_when_generate_publication_is_blocked(
    monkeypatch,
    tmp_path,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "shop"
    project_dir = tmp_path / project
    project_dir.mkdir()
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {"dir": project})
    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        lambda *_args, **_kwargs: {
            "project": project,
            "source": "direct_model_generation",
            "planned_catalog_written_names": [],
            "catalog_init_written_names": [],
            "planned_deleted_model_files": [],
            "model_change_count": 1,
            "model_update_count": 0,
            "publication": {
                "status": "blocked",
                "published": False,
                "validation": {"errors": [{"type": "invalid_model"}]},
            },
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model_metadata_writer.py",
            "--project",
            project,
            "--mode",
            "generate",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        writer_module.main()

    assert "发布被阻断" in str(exc_info.value)
    output_path = (
        project_dir / "artifacts" / "assessment" / "model_metadata_result.json"
    )
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["publication"]["status"] == "blocked"


def test_run_direct_model_generation_delegates_to_generate_entrypoint(
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    calls = []

    def fake_generate(*args, **kwargs):
        calls.append((args, kwargs))
        return {"source": "direct_model_generation"}

    monkeypatch.setattr(
        writer_module,
        "run_generate_model_metadata",
        fake_generate,
    )

    result = writer_module.run_direct_model_generation("demo", dry_run=True)

    assert result == {"source": "direct_model_generation"}
    assert calls == [(("demo",), {"dry_run": True})]


def test_run_generate_model_metadata_dry_run_missing_catalog_uses_in_memory_skeleton(
    tmp_path, monkeypatch
):
    project = "generate_metadata_dry_run"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_existing": {
                "version": 2,
                "name": "dwd_existing",
                "layer": "DWD",
            }
        },
    )
    existing_model = project_dir / "mid" / "models" / "dwd_existing.yaml"

    result = run_generate_model_metadata(project, dry_run=True)

    assert result["catalog_initialized"] is True
    assert result["catalog_init_written_names"] == []
    assert result["planned_catalog_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["model_change_count"] == 1
    assert result["model_update_count"] == 0
    assert str(existing_model) in result["planned_deleted_model_files"]
    assert existing_model.exists()
    assert not (project_dir / "business_taxonomy.yaml").exists()
    assert not (project_dir / "business_processes.yaml").exists()
    assert not (project_dir / "semantic_subjects.yaml").exists()
    assert not (
        project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    ).exists()


def test_run_generate_model_metadata_rejects_reusing_existing_models(
    tmp_path, monkeypatch
):
    project = "generate_metadata_reuse_rejected"
    _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
    )

    with pytest.raises(
        ValueError,
        match="generate 冷启动必须替换现有 models",
    ):
        run_generate_model_metadata(
            project,
            dry_run=True,
            replace_existing_models=False,
        )


def test_run_generate_model_metadata_dry_run_llm_uses_generated_model_baseline(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_metadata_dry_run_llm"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWS",
                "table_type": "fact",
            }
        },
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    lineage_data = {
        "tables": [
            {
                "name": "dwd_order_detail",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
        ],
        "edges": [],
        "indirect_edges": [],
    }
    seen_contexts = []

    class FakeInspector:
        def __init__(self, api_key, **kwargs):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            seen_contexts.extend(contexts)
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    columns={
                        "atomic_metrics": [],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda _: lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=True,
    )

    assert result["llm_result"]["inspected_table_count"] == 1
    assert result["llm_result"]["model_update_count"] == 0
    assert seen_contexts[0].layer == "DWD"
    assert result["llm_result"]["model_updates"][0]["previous_table_type"] == (
        "other"
    )
    assert result["llm_result"]["model_updates"][0]["table_type"] == "fact"
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert saved["layer"] == "DWS"


def test_run_generate_model_metadata_checkpoints_each_completed_table(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_metadata_partial_checkpoint"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_first", "dwd_second"],
    )
    lineage_data = {
        "tables": [
            {
                "name": table_name,
                "columns": [
                    {"name": "id", "type": "BIGINT"},
                    {"name": "customer_id", "type": "BIGINT"},
                ],
            }
            for table_name in ("dwd_first", "dwd_second")
        ],
        "edges": [],
        "indirect_edges": [],
    }

    class FailingInspector:
        def __init__(self, api_key, **kwargs):
            self.progress_callback = None
            self.result_callback = None

        def inspect_batch(self, contexts):
            ctx = contexts[0]
            result = TableInspectResult(
                table_name=ctx.table_name,
                declared_layer=ctx.layer,
                inferred_layer="DWD",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
                columns={
                    "atomic_metrics": [],
                    "derived_metrics": [],
                    "calculated_metrics": [],
                    "dimensions": [],
                    "others": ["id", "customer_id"],
                },
            )
            self.result_callback(result)
            raise RuntimeError("simulated process interruption")

    monkeypatch.setattr(
        writer_module, "load_lineage_data", lambda _: lineage_data
    )
    monkeypatch.setattr(writer_module, "TableInspector", FailingInspector)
    checkpoint_dir = project_dir / "mid_checkpoints"
    checkpoint_dir.mkdir()
    stale_model = checkpoint_dir / "stale.yaml"
    stale_model.write_text("name: stale\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="simulated process interruption"):
        run_generate_model_metadata(
            project,
            api_key="test",
            dry_run=False,
        )

    checkpoint_model = checkpoint_dir / "dwd_first.yaml"
    missing_model = checkpoint_dir / "dwd_second.yaml"
    manifest = json.loads(
        (checkpoint_dir / "manifest.json").read_text(encoding="utf-8")
    )

    assert checkpoint_model.exists()
    assert not missing_model.exists()
    assert not stale_model.exists()
    assert manifest["status"] == "running"
    assert manifest["table_count"] == 2
    assert manifest["checkpoint_model_count"] == 1
    assert manifest["inspected_table_count"] == 1
    assert manifest["tables"]["dwd_first"]["inspection_status"] == "passed"
    assert not (project_dir / "mid" / "models" / "dwd_first.yaml").exists()
    assert not (project_dir / "mid" / "models" / "dwd_second.yaml").exists()
    released = GenerateModelCheckpoint(
        project,
        project_dir=project_dir,
        plan=_checkpoint_plan(writer_module, project),
    )
    released.close()


def _checkpoint_plan(writer_module, project):
    base_plan = writer_module.plan_generate_model_metadata(
        project,
        _catalog_payload(),
        replace_existing_models=True,
        write_scope="all",
    )
    return writer_module.build_generate_plan(
        project,
        write_scope="all",
        base_model_metadata=base_plan.model_metadata,
        model_paths=base_plan.model_paths,
        planned_deleted_model_files=base_plan.planned_deleted_model_files,
        replace_existing_models=True,
    )


def test_generate_checkpoint_rejects_overlapping_project_run(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_checkpoint_lock"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_first"],
    )
    plan = _checkpoint_plan(writer_module, project)
    first = GenerateModelCheckpoint(
        project,
        project_dir=project_dir,
        plan=plan,
    )
    try:
        with pytest.raises(
            GenerateCheckpointLockError,
            match="another generate --llm run is active",
        ):
            GenerateModelCheckpoint(
                project,
                project_dir=project_dir,
                plan=plan,
            )
    finally:
        first.close()

    second = GenerateModelCheckpoint(
        project,
        project_dir=project_dir,
        plan=plan,
    )
    second.close()


def test_generate_checkpoint_records_processed_inspection_status(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_checkpoint_processed_status"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_first"],
    )
    checkpoint = GenerateModelCheckpoint(
        project,
        project_dir=project_dir,
        plan=_checkpoint_plan(writer_module, project),
    )
    checkpoint.write_inspection_result(
        TableInspectResult(
            table_name="dwd_first",
            declared_layer="DWD",
            inferred_layer="DWD",
            table_type="fact",
            confidence=0.1,
            reasoning_steps=[],
        )
    )
    checkpoint.close()
    manifest = json.loads(
        (project_dir / "mid_checkpoints" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["tables"]["dwd_first"]["inspection_status"] == "blocked"
    assert manifest["tables"]["dwd_first"]["validation"][
        "resolution_requires_reinspection"
    ]


def test_generate_checkpoint_recovers_journaled_yaml_write(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_checkpoint_recovery"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_first"],
    )
    checkpoint = GenerateModelCheckpoint(
        project,
        project_dir=project_dir,
        plan=_checkpoint_plan(writer_module, project),
    )
    original_write_manifest = checkpoint._write_manifest
    write_count = 0

    def fail_final_manifest():
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("simulated manifest interruption")
        original_write_manifest()

    monkeypatch.setattr(
        checkpoint,
        "_write_manifest",
        fail_final_manifest,
    )
    with pytest.raises(OSError, match="simulated manifest interruption"):
        checkpoint.write_inspection_result(
            TableInspectResult(
                table_name="dwd_first",
                declared_layer="DWD",
                inferred_layer="DWD",
                table_type="fact",
                confidence=0.9,
                reasoning_steps=[],
            )
        )
    checkpoint.close()

    checkpoint_dir = project_dir / "mid_checkpoints"
    interrupted = json.loads(
        (checkpoint_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert (checkpoint_dir / "dwd_first.yaml").exists()
    assert interrupted["pending_write"]["table"] == "dwd_first"

    recovered = GenerateModelCheckpoint.recover_existing(project_dir)

    assert "pending_write" not in recovered
    assert recovered["checkpoint_model_count"] == 1
    assert recovered["inspected_table_count"] == 1
    assert recovered["tables"]["dwd_first"]["inspection_status"] == "passed"


def test_run_generate_model_metadata_missing_catalog_writes_skeleton_and_models(
    tmp_path, monkeypatch
):
    project = "generate_metadata_write"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=None,
        ddl_tables=["dwd_order_detail"],
    )

    result = run_generate_model_metadata(project, dry_run=False)

    assert result["catalog_initialized"] is True
    assert result["catalog_init_written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert result["planned_catalog_written_names"] == []
    assert (project_dir / "business_taxonomy.yaml").exists()
    assert (project_dir / "business_processes.yaml").exists()
    assert (project_dir / "semantic_subjects.yaml").exists()

    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert result["model_update_count"] == 1
    assert model["name"] == "dwd_order_detail"
    assert model["layer"] == "DWD"
    assert model["execution"] == {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }
    assert "config" not in model


def test_run_generate_model_metadata_derives_execution_from_task_sql(
    tmp_path, monkeypatch
):
    project = "generate_execution_contracts"
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir = project_dir / "mid" / "tasks"
    full_refresh_dir = task_dir / "full_refresh"
    ddl_dir.mkdir(parents=True)
    full_refresh_dir.mkdir(parents=True)
    for table_name in ("dwd_full", "dwd_daily", "dwd_companion"):
        (ddl_dir / f"{table_name}.sql").write_text(
            (
                f"CREATE TABLE {table_name} "
                "(id BIGINT, date DATE, processing_status INT, "
                "business_date DATE);\n"
            ),
            encoding="utf-8",
        )
    (task_dir / "dwd_full.sql").write_text(
        "TRUNCATE TABLE demo.dwd_full;\n"
        "INSERT INTO demo.dwd_full SELECT 1, CURDATE();\n",
        encoding="utf-8",
    )
    daily_sql = (
        "SET @etl_date = COALESCE(@etl_date, CURDATE());\n"
        "TRUNCATE TABLE demo.staging_cleanup;\n"
        "DELETE FROM demo.{table} "
        "WHERE processing_status = 1 "
        "AND business_date = CAST(@etl_date AS DATE);\n"
        "INSERT INTO demo.{table} SELECT 1, @etl_date;\n"
    )
    (task_dir / "dwd_daily.sql").write_text(
        daily_sql.format(table="dwd_daily"),
        encoding="utf-8",
    )
    (task_dir / "dwd_companion.sql").write_text(
        daily_sql.format(table="dwd_companion"),
        encoding="utf-8",
    )
    (full_refresh_dir / "dwd_companion_full_refresh.sql").write_text(
        "TRUNCATE TABLE demo.dwd_companion;\n"
        "INSERT INTO demo.dwd_companion SELECT 1, CURDATE();\n",
        encoding="utf-8",
    )
    _write_split_catalog(project_dir, project, _catalog_payload())
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "naming_config": "naming_config.yaml"},
    )

    result = run_generate_model_metadata(project, dry_run=False)
    models = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (project_dir / "mid" / "models").glob("*.yaml")
    }

    assert result["publication"]["status"] == "published"
    assert models["dwd_full"]["execution"] == {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }
    assert models["dwd_daily"]["execution"] == {
        "materialized": "incremental",
        "full_refresh_strategy": "replay_slices",
        "slice": {
            "param": "etl_date",
            "column": "business_date",
            "period": "D",
        },
    }
    assert models["dwd_companion"]["execution"] == {
        "materialized": "incremental",
        "full_refresh_strategy": "companion",
        "slice": {
            "param": "etl_date",
            "column": "business_date",
            "period": "D",
        },
    }


def test_run_generate_model_metadata_blocks_unresolved_execution_contract(
    tmp_path, monkeypatch
):
    project = "generate_execution_blocked"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {"materialized": "full"},
            }
        },
    )
    task_dir = project_dir / "mid" / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "mid" / "ddl" / "dwd_order_detail.sql").write_text(
        (
            "CREATE TABLE dwd_order_detail (id BIGINT, stat_date DATE) "
            "PARTITION BY RANGE(stat_date) ();\n"
        ),
        encoding="utf-8",
    )
    (task_dir / "dwd_order_detail.sql").write_text(
        "SET @retry_limit = 3;\n"
        "INSERT INTO demo.dwd_order_detail SELECT 1, CURRENT_DATE;\n",
        encoding="utf-8",
    )
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    result = run_generate_model_metadata(project, dry_run=False)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["validation"]["errors"] == [
        {
            "type": "execution_slice_missing",
            "table": "dwd_order_detail",
            "message": (
                "incremental replay_slices model requires execution.slice"
            ),
        }
    ]
    assert result["deleted_model_files"] == []
    assert saved["execution"] == {"materialized": "full"}


def test_run_generate_model_metadata_blocks_dwd_without_task_sql(
    tmp_path, monkeypatch
):
    project = "generate_execution_task_missing"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "version": 2,
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {"materialized": "full"},
            }
        },
    )
    (project_dir / "mid" / "tasks" / "dwd_order_detail.sql").unlink()
    model_path = project_dir / "mid" / "models" / "dwd_order_detail.yaml"

    result = run_generate_model_metadata(project, dry_run=False)
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert result["publication"]["status"] == "blocked"
    assert result["publication"]["validation"]["errors"] == [
        {
            "type": "execution_task_missing",
            "table": "dwd_order_detail",
            "message": "DWD execution cannot be inferred without task SQL",
        }
    ]
    assert saved["execution"] == {"materialized": "full"}


@pytest.mark.parametrize(
    (
        "llm_enabled",
        "model_process",
        "table_process",
        "metric_processes",
        "catalog_codes",
        "expected_error",
        "expected_message",
    ),
    [
        (
            True,
            "",
            "",
            (),
            ("ORDER", "REFUND"),
            "business_process_missing",
            "fact inspection did not identify a business process",
        ),
        (
            True,
            "",
            "",
            ("ORDER", "REFUND"),
            ("ORDER", "REFUND"),
            "business_process_ambiguous",
            (
                "fact inspection identified multiple business processes: "
                "ORDER, REFUND"
            ),
        ),
        (
            True,
            "ACCOUNT_TRANSFER",
            "ACCOUNT_TRANSFER",
            (),
            ("ACCOUNT_TRANSFER",),
            None,
            None,
        ),
        (
            True,
            "ACCOUNT_TRANSFER",
            "ACCOUNT_TRANSFER",
            ("",),
            ("ACCOUNT_TRANSFER",),
            "business_process_missing",
            "fact inspection did not identify a business process",
        ),
        (
            False,
            "",
            "",
            (),
            (),
            "business_process_missing",
            "fact model requires exactly one business process",
        ),
    ],
    ids=(
        "missing",
        "ambiguous",
        "factless-table-process",
        "unassigned-metric",
        "no-llm",
    ),
)
def test_generate_publication_business_process_contract(
    tmp_path,
    llm_enabled,
    model_process,
    table_process,
    metric_processes,
    catalog_codes,
    expected_error,
    expected_message,
):
    table_name = "dwd_fact"
    task_path = tmp_path / f"{table_name}.sql"
    task_path.write_text(
        f"TRUNCATE TABLE {table_name};\n",
        encoding="utf-8",
    )
    model = {
        "name": table_name,
        "layer": "DWD",
        "table_type": "fact",
        "execution": {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        },
    }
    if model_process:
        model["business_process"] = model_process
    inspection = {
        "table_name": table_name,
        "status": "passed",
        "table_type": "fact",
        "business_process": table_process,
        "columns": {
            "atomic_metrics": [
                {
                    "name": f"metric_{index}",
                    "business_process": code,
                }
                for index, code in enumerate(metric_processes)
            ],
            "derived_metrics": [],
            "calculated_metrics": [],
        },
    }
    validation = validate_generate_candidate(
        {table_name: model},
        {
            table_name: {
                "ddl": {"columns": [{"name": "id"}]},
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={"tables": [inspection]} if llm_enabled else None,
        catalog={
            "business_processes": [{"code": code} for code in catalog_codes]
        },
    )

    if expected_error is None:
        assert validation["status"] == "passed"
        assert validation["errors"] == []
        return
    assert validation["status"] == "blocked"
    assert validation["errors"] == [
        {
            "type": expected_error,
            "table": table_name,
            "message": expected_message,
        }
    ]


def test_generate_publication_requires_complete_llm_mid_coverage(tmp_path):
    task_path = tmp_path / "dwd_order_detail.sql"
    task_path.write_text(
        "TRUNCATE TABLE dwd_order_detail;\n",
        encoding="utf-8",
    )
    validation = validate_generate_candidate(
        {
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
            }
        },
        {
            "dwd_order_detail": {
                "ddl": {"columns": [{"name": "id"}]},
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={"tables": []},
        catalog={},
    )

    assert validation["errors"] == [
        {
            "type": "llm_inspection_missing",
            "table": "dwd_order_detail",
            "message": (
                "LLM generate requires inspection coverage for every MID model"
            ),
        }
    ]


def test_generate_publication_allows_fact_foreign_entities_without_relationship(
    tmp_path,
):
    task_path = tmp_path / "dwd_order_detail.sql"
    task_path.write_text(
        "TRUNCATE TABLE dwd_order_detail;\n",
        encoding="utf-8",
    )
    validation = validate_generate_candidate(
        {
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "DWD",
                "table_type": "fact",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
                "entities": [
                    {
                        "code": "ORDER_DETAIL",
                        "type": "primary",
                        "key_columns": ["id"],
                    },
                    {
                        "code": "CUSTOMER",
                        "type": "foreign",
                        "key_columns": ["customer_id"],
                    },
                ],
                "business_process": "ORDER",
            }
        },
        {
            "dwd_order_detail": {
                "ddl": {
                    "columns": [
                        {"name": "id"},
                        {"name": "customer_id"},
                    ]
                },
                "tasks": [{"path": str(task_path), "is_full_refresh": False}],
            }
        },
        llm_result={
            "tables": [
                {
                    "table_name": "dwd_order_detail",
                    "status": "passed",
                    "table_type": "fact",
                    "columns": {
                        "atomic_metrics": [
                            {"name": "id", "business_process": "ORDER"}
                        ]
                    },
                }
            ]
        },
        catalog={"business_processes": [{"code": "ORDER"}]},
    )

    assert validation == {
        "status": "passed",
        "error_count": 0,
        "errors": [],
        "blocked_tables": [],
    }


def test_generate_publication_validates_entity_keys_and_grain_references():
    validation = validate_generate_candidate(
        {
            "dim_customer": {
                "name": "dim_customer",
                "layer": "DIM",
                "table_type": "dimension",
                "execution": {
                    "materialized": "full",
                    "full_refresh_strategy": "replace_all",
                },
                "entities": [
                    {
                        "code": "CUSTOMER",
                        "type": "primary",
                        "key_columns": [],
                    }
                ],
                "semantic_subject": "CUSTOMER",
                "grain": {
                    "entities": ["GHOST"],
                    "additional_key_columns": ["ghost_id"],
                    "time_column": "ghost_date",
                },
            }
        },
        {
            "dim_customer": {
                "ddl": {"columns": [{"name": "customer_id"}]},
                "tasks": [],
            }
        },
        llm_result={
            "tables": [
                {
                    "table_name": "dim_customer",
                    "status": "passed",
                    "table_type": "dimension",
                    "columns": {},
                }
            ]
        },
        catalog={"semantic_subjects": [{"code": "CUSTOMER"}]},
    )

    assert validation["status"] == "blocked"
    assert {error["type"] for error in validation["errors"]} == {
        "entity_key_missing",
        "grain_entity_unknown",
        "grain_column_missing",
    }


def test_generate_file_set_publication_rolls_back_on_replace_failure(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    catalog_path = tmp_path / "business_processes.yaml"
    model_path = tmp_path / "dwd_order_detail.yaml"
    catalog_path.write_text("catalog: old\n", encoding="utf-8")
    model_path.write_text("model: old\n", encoding="utf-8")
    original_replace = Path.replace
    staged_replace_count = 0

    def flaky_replace(self, target):
        nonlocal staged_replace_count
        if self.name.endswith(".staged"):
            staged_replace_count += 1
            if staged_replace_count == 2:
                raise OSError("simulated replacement failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    with pytest.raises(OSError, match="simulated replacement failure"):
        writer_module._transactional_publish_files(
            {
                catalog_path: "catalog: new\n",
                model_path: "model: new\n",
            },
            delete_paths=[],
        )

    assert catalog_path.read_text(encoding="utf-8") == "catalog: old\n"
    assert model_path.read_text(encoding="utf-8") == "model: old\n"
    assert list(tmp_path.glob(".*.staged")) == []
    assert list(tmp_path.glob(".*.backup")) == []


def test_generate_asset_collection_does_not_read_existing_model_yaml(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project = "generate_ignores_existing_model_content"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "dwd_order_detail": {
                "name": "dwd_order_detail",
                "layer": "ADS",
            }
        },
    )
    original_read_text = Path.read_text

    def reject_model_read(self, *args, **kwargs):
        if "models" in self.parts and self.suffix == ".yaml":
            raise OSError("existing model content must not be read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_model_read)

    assets = writer_module._generate_model_table_assets(project)

    assert assets["dwd_order_detail"]["ddl"]["exists"] is True
    assert assets["dwd_order_detail"]["model"] is None
    assert (project_dir / "mid" / "models" / "dwd_order_detail.yaml").exists()


def test_run_generate_model_metadata_uses_asset_role_for_prefixless_base(
    tmp_path, monkeypatch
):
    project = "generate_metadata_asset_role"
    project_dir = tmp_path / project
    (project_dir / "ods" / "ddl" / "internal" / "demo_dm").mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "ads" / "ddl").mkdir(parents=True)
    (
        project_dir
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "order_event.sql"
    ).write_text(
        "CREATE TABLE order_event (id BIGINT);\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "ddl" / "order_detail.sql").write_text(
        "CREATE TABLE order_detail (id BIGINT);\n",
        encoding="utf-8",
    )
    (project_dir / "ads" / "ddl" / "order_dashboard.sql").write_text(
        "CREATE TABLE order_dashboard (id BIGINT);\n",
        encoding="utf-8",
    )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "catalog": "internal",
            "db": "demo_dm",
            "naming_config": "naming_config.yaml",
        },
    )

    result = run_generate_model_metadata(project, dry_run=True)
    updates = {update["table"]: update for update in result["model_updates"]}

    assert updates["order_event"]["layer"] == "ODS"
    assert updates["order_detail"]["layer"] == "DWD"
    assert updates["order_dashboard"]["layer"] == "ADS"
    assert (
        "/ods/models/internal/demo_dm/order_event.yaml"
        in updates["order_event"]["path"]
    )
    assert "/mid/models/order_detail.yaml" in updates["order_detail"]["path"]
    assert (
        "/ads/models/order_dashboard.yaml"
        in updates["order_dashboard"]["path"]
    )
