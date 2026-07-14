import json
from datetime import datetime, timezone

import pytest

import dw_refactor_agent.refactor.run as run_cli
from dw_refactor_agent.refactor.plan_artifact import StalePlanError
from dw_refactor_agent.refactor.semantic_mode import SemanticResolution
from dw_refactor_agent.refactor.session import (
    create_run_manifest,
    write_manifest,
)


def _local_datetime(*args):
    return datetime(*args).astimezone()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _write_warehouse_config(root, project="shop"):
    warehouse_dir = root / "warehouses" / project
    warehouse_dir.mkdir(parents=True)
    (warehouse_dir / "warehouse.yaml").write_text(
        "\n".join(
            [
                f"name: {project}",
                f"database: {project}_dm",
                f"qa_database: {project}_dm_qa",
                f"lineage_database: {project}_lineage",
            ]
        ),
        encoding="utf-8",
    )


def _install_start_fakes(monkeypatch):
    def fake_lineage(
        project, output_path, cache_path, previous_cache_path=None
    ):
        _write_json(output_path, {"tables": [], "edges": []})
        _write_json(cache_path, {"project": project, "tasks": []})
        return {"lineage": {"tables": [], "edges": []}}

    def fake_assess(project, **kwargs):
        return {"project": project, "overall_score": 100.0, "dimensions": {}}

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    monkeypatch.setattr(run_cli, "assess", fake_assess)
    monkeypatch.setattr(
        run_cli,
        "_git_info",
        lambda _root: {"branch": "main", "head": "abc123", "dirty": False},
    )
    monkeypatch.setattr(
        run_cli,
        "_now",
        lambda: _local_datetime(2026, 6, 20, 7, 30),
    )


def _install_empty_semantic_resolution(monkeypatch):
    monkeypatch.setattr(
        run_cli,
        "resolve_semantic_modes",
        lambda **kwargs: SemanticResolution(
            target_semantics={},
            boundaries={"authority": [], "observational": []},
            selected_tables=(),
            warnings=(),
            inherited_declarations={},
        ),
    )


def test_start_creates_manifest_and_baseline_artifacts(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path)
    _install_start_fakes(monkeypatch)

    exit_code = run_cli.main(
        ["start", "--project", "shop", "--root", str(tmp_path)]
    )

    assert exit_code == 0
    run_root = (
        tmp_path
        / "warehouses"
        / "shop"
        / "artifacts"
        / "refactor_runs"
        / "20260620_073000_shop"
    )
    assert (run_root / "manifest.json").exists()
    manifest = json.loads((run_root / "manifest.json").read_text())
    assert manifest["root"] == str(tmp_path.resolve())
    assert (run_root / "baseline" / "lineage_data.json").exists()
    assert (run_root / "baseline" / "task_lineage_cache.json").exists()
    assert (run_root / "baseline" / "assess_result.json").exists()
    baseline_assess = json.loads(
        (run_root / "baseline" / "assess_result.json").read_text()
    )
    assert baseline_assess["assessment_mode"] == "full"
    assert baseline_assess["score_semantics"] == "project_global"
    assert baseline_assess["scope"] == {"type": "project"}


def test_start_loads_project_choices_from_target_root(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path, "demo")
    _install_start_fakes(monkeypatch)

    exit_code = run_cli.main(
        ["start", "--project", "demo", "--root", str(tmp_path)]
    )

    assert exit_code == 0
    run_root = (
        tmp_path
        / "warehouses"
        / "demo"
        / "artifacts"
        / "refactor_runs"
        / "20260620_073000_demo"
    )
    assert (run_root / "manifest.json").exists()
    manifest = json.loads((run_root / "manifest.json").read_text())
    assert manifest["project"] == "demo"


def test_start_rejects_root_without_warehouse_config(tmp_path):
    root = tmp_path / "empty-root"
    root.mkdir()

    try:
        run_cli.main(["start", "--project", "shop", "--root", str(root)])
    except SystemExit as exc:
        assert "缺少 warehouses 目录" in str(exc)
    else:
        raise AssertionError("start should reject a root without warehouses/")


def test_analyze_refreshes_current_analysis_diff_and_plan(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={"branch": "main", "head": "abc123", "dirty": False},
    )
    write_manifest(manifest_path, manifest)
    run_root = manifest_path.parent
    _write_json(
        run_root / "baseline" / "lineage_data.json",
        {"tables": [], "edges": []},
    )
    _write_json(
        run_root / "baseline" / "assess_result.json",
        {
            "project": "shop",
            "overall_score": 50.0,
            "dimensions": {
                "naming": {
                    "score": 50.0,
                    "issues": [
                        {
                            "fingerprint": (
                                "naming|NAMING_COLUMN_NAME|table|dwd_customer"
                            ),
                            "target": {
                                "type": "table",
                                "name": "dwd_customer",
                            },
                        }
                    ],
                }
            },
        },
    )
    _write_json(run_root / "baseline" / "task_lineage_cache.json", {})

    def fake_lineage(
        project, output_path, cache_path, previous_cache_path=None
    ):
        _write_json(output_path, {"tables": [], "edges": []})
        _write_json(cache_path, {"project": project, "tasks": []})
        return {"lineage": {"tables": [], "edges": []}}

    assess_calls = []

    def fake_assess(project, **kwargs):
        assess_calls.append(kwargs)
        return {
            "project": project,
            "overall_score": 90.0,
            "scope_plan": {"dimensions": {}},
            "dimensions": {
                "naming": {
                    "score": 90.0,
                    "issues": [
                        {
                            "fingerprint": (
                                "naming|NAMING_COLUMN_NAME|table|"
                                "DIM_BASE_CUST_PROFILE_INFO"
                            ),
                            "target": {
                                "type": "table",
                                "name": "DIM_BASE_CUST_PROFILE_INFO",
                            },
                        }
                    ],
                }
            },
        }

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    monkeypatch.setattr(run_cli, "assess", fake_assess)
    _install_empty_semantic_resolution(monkeypatch)

    diff_calls = []

    def fake_changed_files(root, head, project_dir):
        diff_calls.append(
            {
                "root": root,
                "head": head,
                "project_dir": project_dir,
            }
        )
        return ["warehouses/shop/mid/models/dwd_order.yaml"]

    monkeypatch.setattr(
        run_cli,
        "changed_files_since_head",
        fake_changed_files,
    )
    plan_calls = []

    def fake_plan(
        project,
        analysis,
        base_ref=None,
        repo_root=None,
        lineage_data=None,
        partition=None,
        semantic_resolution=None,
    ):
        assert isinstance(semantic_resolution, SemanticResolution)
        plan_calls.append(
            {
                "base_ref": base_ref,
                "repo_root": repo_root,
                "lineage_data": lineage_data,
                "partition": partition,
            }
        )
        return {
            "project": project,
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {
                "dwd_order": "CREATE TABLE shop_dm.dwd_order (id BIGINT);"
            },
            "ddl_changes": [
                {
                    "change_type": "RENAME",
                    "old_name": "shop_dm.dwd_customer",
                    "new_name": "shop_dm.DIM_BASE_CUST_PROFILE_INFO",
                }
            ],
            "partition_info": {},
            "jobs_to_run": [],
            "verification": {"checks": []},
        }

    monkeypatch.setattr(run_cli, "build_verification_plan", fake_plan)

    exit_code = run_cli.main(
        [
            "analyze",
            "--manifest",
            str(manifest_path),
            "--partition",
            "2025-01-15",
        ]
    )

    assert exit_code == 0
    assert (run_root / "current" / "lineage_data.json").exists()
    assert (run_root / "current" / "assess_result.json").exists()
    assert (run_root / "analysis" / "change_analysis.json").exists()
    manifest_after_analyze = json.loads(
        (run_root / "manifest.json").read_text()
    )
    assert manifest_after_analyze["artifacts"]["baseline_full_assess"] == (
        "baseline/assess_result.json"
    )
    assert manifest_after_analyze["artifacts"]["current_scoped_assess"] == (
        "current/assess_result.json"
    )
    current_assess = json.loads(
        (run_root / "current" / "assess_result.json").read_text()
    )
    assert current_assess["assessment_mode"] == "scoped"
    assert current_assess["score_semantics"] == "scope_local"
    assert current_assess["scope"] == {
        "type": "refactor_scope",
        "tables": ["dwd_order"],
        "tasks": ["dwd_order"],
    }
    issue_diff = json.loads(
        (run_root / "analysis" / "issue_diff.json").read_text()
    )
    assert issue_diff["summary"]["fixed_count"] == 0
    assert issue_diff["summary"]["remaining_count"] == 1
    assert issue_diff["summary"]["new_count"] == 0
    assert issue_diff["scope_score"]["assessment_mode"] == "scoped"
    assert issue_diff["scope_score"]["score_semantics"] == "scope_local"
    assert issue_diff["scope_score"]["scope"] == {
        "type": "refactor_scope",
        "tables": ["dwd_order"],
        "tasks": ["dwd_order"],
    }
    assert assess_calls[0]["change_analysis"]["affected_scope"][
        "assessment_tables"
    ] == ["dwd_order"]
    assert assess_calls[0]["change_analysis"]["changed_assets"][
        "model_tables"
    ] == ["dwd_order"]
    assert (run_root / "verification" / "plan.json").exists()
    persisted_plan = json.loads(
        (run_root / "verification" / "plan.json").read_text()
    )
    assert persisted_plan["analysis_snapshot"]["partition"] == "2025-01-15"
    assert persisted_plan["analysis_snapshot"][
        "workspace_fingerprint"
    ].startswith("sha256:")
    assert set(persisted_plan["analysis_snapshot"]["analysis_inputs"]) == {
        "baseline_lineage",
        "current_lineage",
        "change_analysis",
        "manifest_context",
        "verification_intent",
    }
    assert "baseline_ddl" not in persisted_plan
    ddl_reference = persisted_plan["baseline_ddl_refs"]["dwd_order"]["path"]
    assert ddl_reference.startswith("baseline_ddl/dwd_order.")
    assert ddl_reference.endswith(".sql")
    persisted_ddl = (run_root / "verification" / ddl_reference).read_text()
    assert persisted_ddl == "CREATE TABLE shop_dm.dwd_order (id BIGINT);"
    assert diff_calls == [
        {
            "root": tmp_path.resolve(),
            "head": "abc123",
            "project_dir": "warehouses/shop",
        }
    ]
    assert plan_calls == [
        {
            "base_ref": "abc123",
            "repo_root": tmp_path.resolve(),
            "lineage_data": {"tables": [], "edges": []},
            "partition": "2025-01-15",
        }
    ]


def test_analyze_maps_changed_job_to_managed_output_before_table_bfs(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={"branch": "main", "head": "abc123", "dirty": False},
    )
    write_manifest(manifest_path, manifest)
    run_root = manifest_path.parent

    def lineage_snapshot(dwd_table, ads_table, build_job):
        return {
            "format_version": 2,
            "tables": [
                {
                    "name": dwd_table.rsplit(".", 1)[-1],
                    "full_name": dwd_table,
                    "dataset_type": "managed",
                    "columns": [],
                },
                {
                    "name": ads_table.rsplit(".", 1)[-1],
                    "full_name": ads_table,
                    "dataset_type": "managed",
                    "columns": [],
                },
            ],
            "jobs": [
                {
                    "name": build_job,
                    "source_file": (
                        f"warehouses/shop/ads/tasks/{build_job}.sql"
                    ),
                    "inputs": [dwd_table],
                    "outputs": [ads_table],
                },
                {
                    "name": "Prepare_Sales",
                    "source_file": (
                        "warehouses/shop/mid/tasks/Prepare_Sales.sql"
                    ),
                    "inputs": [],
                    "outputs": [dwd_table],
                },
            ],
            "edges": [
                {
                    "source": {"type": "column", "id": f"{dwd_table}.id"},
                    "target": {"type": "column", "id": f"{ads_table}.id"},
                    "relation_type": "DIRECT",
                    "transformation_type": "IDENTITY",
                    "expression": "id",
                    "job": build_job,
                }
            ],
            "diagnostics": [],
        }

    baseline_lineage = lineage_snapshot(
        "internal.shop_dm.DWD_Order",
        "internal.shop_dm.ADS_Old",
        "Build_Old",
    )
    current_lineage = lineage_snapshot(
        "internal.shop_dm.dwd_order",
        "internal.shop_dm.ads_new",
        "Build_New",
    )
    _write_json(run_root / "baseline" / "lineage_data.json", baseline_lineage)
    _write_json(
        run_root / "baseline" / "assess_result.json",
        {"project": "shop", "overall_score": 100.0, "dimensions": {}},
    )
    _write_json(run_root / "baseline" / "task_lineage_cache.json", {})

    def fake_lineage(
        project, output_path, cache_path, previous_cache_path=None
    ):
        _write_json(output_path, current_lineage)
        _write_json(cache_path, {"project": project, "tasks": []})
        return {"lineage": current_lineage}

    observed_analysis = []

    def fake_plan(project, analysis, **kwargs):
        observed_analysis.append(analysis)
        return {
            "project": project,
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {},
            "ddl_changes": [],
            "jobs_to_run": [],
            "job_dependencies": {},
            "verification": {"checks": []},
        }

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    monkeypatch.setattr(
        run_cli,
        "changed_files_since_head",
        lambda *args: ["warehouses/shop/mid/tasks/Prepare_Sales.sql"],
    )
    monkeypatch.setattr(run_cli, "build_verification_plan", fake_plan)
    monkeypatch.setattr(
        run_cli,
        "assess",
        lambda project, **kwargs: {
            "project": project,
            "overall_score": 100.0,
            "scope_plan": {"dimensions": {}},
            "dimensions": {},
        },
    )
    monkeypatch.setattr(
        run_cli,
        "diff_assess_results",
        lambda *args, **kwargs: {"summary": {}},
    )
    _install_empty_semantic_resolution(monkeypatch)

    exit_code = run_cli.main(["analyze", "--manifest", str(manifest_path)])

    assert exit_code == 0
    assert len(observed_analysis) == 1
    scope = observed_analysis[0]["affected_scope"]
    assert scope["direct_tables"] == ["internal.shop_dm.dwd_order"]
    assert scope["downstream_tables"] == [
        "internal.shop_dm.ADS_Old",
        "internal.shop_dm.ads_new",
    ]
    assert scope["anchor_tables"] == [
        "internal.shop_dm.ADS_Old",
        "internal.shop_dm.ads_new",
    ]
    assert "Prepare_Sales" not in scope["assessment_tables"]


def test_analyze_reports_partition_requirement_cleanly(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={"branch": "main", "head": "abc123", "dirty": False},
    )
    write_manifest(manifest_path, manifest)
    run_root = manifest_path.parent
    _write_json(
        run_root / "baseline" / "lineage_data.json",
        {"tables": [], "edges": []},
    )
    _write_json(
        run_root / "baseline" / "assess_result.json",
        {"project": "shop", "overall_score": 50.0, "dimensions": {}},
    )
    _write_json(run_root / "baseline" / "task_lineage_cache.json", {})

    def fake_lineage(
        project, output_path, cache_path, previous_cache_path=None
    ):
        _write_json(output_path, {"tables": [], "edges": []})
        _write_json(cache_path, {"project": project, "tasks": []})
        return {"lineage": {"tables": [], "edges": []}}

    def fake_plan(
        project,
        analysis,
        base_ref=None,
        repo_root=None,
        lineage_data=None,
        partition=None,
        semantic_resolution=None,
    ):
        raise ValueError(
            "refactor analyze requires --partition for incremental jobs "
            "with execution slices: ads_dashboard"
        )

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    _install_empty_semantic_resolution(monkeypatch)
    monkeypatch.setattr(run_cli, "changed_files_since_head", lambda *args: [])
    monkeypatch.setattr(run_cli, "build_verification_plan", fake_plan)
    monkeypatch.setattr(
        run_cli,
        "assess",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("assess should not run after plan validation fails")
        ),
    )

    try:
        run_cli.main(["analyze", "--manifest", str(manifest_path)])
    except SystemExit as exc:
        assert "--partition" in str(exc)
        assert "ads_dashboard" in str(exc)
    else:
        raise AssertionError("analyze should exit with a clean error")

    assert not (run_root / "verification" / "plan.json").exists()
    assert not (run_root / "current" / "assess_result.json").exists()


def test_analyze_marks_empty_diff_assessment_not_applicable(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={"branch": "main", "head": "abc123", "dirty": False},
    )
    write_manifest(manifest_path, manifest)
    run_root = manifest_path.parent
    lineage = {"tables": [], "edges": []}
    _write_json(run_root / "baseline" / "lineage_data.json", lineage)
    _write_json(
        run_root / "baseline" / "assess_result.json",
        {
            "project": "shop",
            "overall_score": 50.0,
            "dimensions": {
                "naming": {
                    "score": 50.0,
                    "issues": [
                        {
                            "fingerprint": (
                                "naming|NAMING_COLUMN_NAME|table|dwd_customer"
                            ),
                            "target": {
                                "type": "table",
                                "name": "dwd_customer",
                            },
                        }
                    ],
                }
            },
        },
    )
    _write_json(run_root / "baseline" / "task_lineage_cache.json", {})

    def fake_lineage(
        project, output_path, cache_path, previous_cache_path=None
    ):
        _write_json(output_path, lineage)
        _write_json(cache_path, {"project": project, "tasks": []})
        return {"lineage": lineage}

    def fake_assess(project, **kwargs):
        return {
            "project": project,
            "overall_score": 82.0,
            "assessment_mode": "scoped",
            "score_semantics": "scope_local",
            "scope_plan": {
                "mode": "scoped",
                "score_semantics": "scope_local",
                "dimensions": {},
            },
            "dimensions": {
                "reuse": {"score": 0.0, "issues": []},
                "naming": {"score": 100.0, "issues": []},
            },
        }

    def fake_plan(
        project,
        analysis,
        base_ref=None,
        repo_root=None,
        lineage_data=None,
        partition=None,
        semantic_resolution=None,
    ):
        return {
            "project": project,
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "changes": {
                "modified_jobs": [],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "baseline_ddl": {},
            "ddl_changes": [],
            "jobs_to_run": [],
            "verification": {
                "anchor_tables": [],
                "checks": [],
                "data_anchor_status": "not_required",
            },
        }

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    monkeypatch.setattr(run_cli, "assess", fake_assess)
    _install_empty_semantic_resolution(monkeypatch)
    monkeypatch.setattr(run_cli, "changed_files_since_head", lambda *args: [])
    monkeypatch.setattr(run_cli, "build_verification_plan", fake_plan)

    exit_code = run_cli.main(["analyze", "--manifest", str(manifest_path)])

    assert exit_code == 0
    current_assess = json.loads(
        (run_root / "current" / "assess_result.json").read_text()
    )
    assert current_assess["status"] == "no_changes"
    assert current_assess["overall_score"] is None
    assert current_assess["score_status"] == "not_applicable"
    assert current_assess["assessment_mode"] == "no_changes"
    assert current_assess["score_semantics"] == "not_applicable"
    assert current_assess["dimensions"]["reuse"]["score"] is None
    assert current_assess["dimensions"]["naming"]["score"] is None

    issue_diff = json.loads(
        (run_root / "analysis" / "issue_diff.json").read_text()
    )
    assert issue_diff["status"] == "no_changes"
    assert issue_diff["summary"] == {
        "baseline_scoped_issue_count": 0,
        "current_scoped_issue_count": 0,
        "fixed_count": 0,
        "remaining_count": 0,
        "new_count": 0,
    }
    assert issue_diff["scope_score"]["overall_score"] is None


def test_check_subcommand_is_removed():
    try:
        run_cli.main(["check", "--manifest", "missing.json"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("check subcommand should not be registered")


def test_semantic_guidance_is_neutral_and_uses_short_run_selector(capsys):
    run_cli._print_semantic_guidance(
        {
            "verification": {
                "target_semantics": {
                    "dws_store_sales_daily": {"resolved_mode": "unknown"},
                    "ads_sales": {"resolved_mode": "equivalent"},
                }
            }
        },
        "20260713_113226_shop",
    )

    output = capsys.readouterr().out
    assert "dws_store_sales_daily 无法自动确认语义" in output
    assert "equivalent：预期新旧输出相同" in output
    assert "changed：预期本表语义变化" in output
    assert "unknown：暂不判断" in output
    assert "建议：equivalent" not in output
    assert "--run 20260713_113226_shop" in output


def test_shadow_run_and_compare_delegate_to_plan_handlers(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    plan_path = manifest_path.parent / "verification" / "plan.json"
    _write_json(plan_path, {"project": "shop"})
    calls = []

    monkeypatch.setattr(
        run_cli,
        "require_fresh_plan",
        lambda *args, **kwargs: {
            "analysis_snapshot": {"workspace_fingerprint": "sha256:workspace"},
            "plan_fingerprint": "sha256:plan",
        },
    )

    def fake_shadow(
        plan,
        output,
        provenance,
        dry_run=False,
        timing_detail=False,
        parallel=1,
        batch_size=1,
    ):
        calls.append(
            (
                "shadow",
                plan,
                output,
                provenance,
                dry_run,
                timing_detail,
                parallel,
                batch_size,
                run_cli.config.PROJECT_ROOT,
                run_cli.shadow_run_module.PROJECT_ROOT,
            )
        )
        _write_json(output, {"ok": True})
        return {"ok": True}

    def fake_compare(
        plan,
        shadow_result,
        output,
        method="all",
        sample=0,
        precision=0.01,
    ):
        calls.append(
            (
                "compare",
                plan,
                shadow_result,
                output,
                method,
                sample,
                precision,
            )
        )
        _write_json(output, {"ok": True})
        return {"verification_status": "passed"}

    monkeypatch.setattr(run_cli, "run_shadow_plan", fake_shadow)
    monkeypatch.setattr(run_cli, "compare_shadow_results", fake_compare)

    assert run_cli.main(["shadow-run", "--manifest", str(manifest_path)]) == 0
    assert run_cli.main(["compare", "--manifest", str(manifest_path)]) == 0

    assert calls[0][0] == "shadow"
    assert calls[0][1] == plan_path
    assert calls[0][3] == {
        "workspace_fingerprint": "sha256:workspace",
        "plan_fingerprint": "sha256:plan",
    }
    assert calls[0][5] is False
    assert calls[0][6] == 1
    assert calls[0][7] == 1
    assert calls[0][8] == tmp_path.resolve()
    assert calls[0][9] == tmp_path.resolve()
    assert calls[1][0] == "compare"
    assert calls[1][1] == plan_path
    assert calls[1][2] == (
        manifest_path.parent / "verification" / "shadow_run_result.json"
    )

    calls.clear()
    assert (
        run_cli.main(
            [
                "shadow-run",
                "--manifest",
                str(manifest_path),
                "--timing-detail",
            ]
        )
        == 0
    )
    assert calls[0][0] == "shadow"
    assert calls[0][5] is True


def test_shadow_run_cli_reports_handler_failure(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    plan_path = manifest_path.parent / "verification" / "plan.json"
    _write_json(plan_path, {"project": "shop"})

    monkeypatch.setattr(
        run_cli,
        "require_fresh_plan",
        lambda *args, **kwargs: {
            "analysis_snapshot": {"workspace_fingerprint": "sha256:workspace"},
            "plan_fingerprint": "sha256:plan",
        },
    )

    def fake_shadow(
        plan,
        output,
        provenance,
        dry_run=False,
        timing_detail=False,
        parallel=1,
        batch_size=1,
    ):
        _write_json(output, {"status": "failed"})
        return {"status": "failed"}

    monkeypatch.setattr(run_cli, "run_shadow_plan", fake_shadow)

    assert run_cli.main(["shadow-run", "--manifest", str(manifest_path)]) == 1


def test_manifest_commands_accept_exact_run_selector_and_reject_both():
    parser = run_cli.build_parser()

    args = parser.parse_args(["analyze", "--run", "20260713_113226_shop"])

    assert args.run == "20260713_113226_shop"
    assert args.manifest is None
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "analyze",
                "--run",
                "20260713_113226_shop",
                "--manifest",
                "/tmp/manifest.json",
            ]
        )


def test_semantic_mode_set_preserves_manifest_and_lightly_replans(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 13, 11, 32, 26, tzinfo=timezone.utc),
        git_info={"head": "base"},
    )
    manifest["verification_intent"] = {
        "semantic_modes": {
            "other_table": {
                "table_id": "id-other",
                "mode": "unknown",
                "semantic_context_fingerprint": "sha256:other",
                "confirmed_at": "2026-07-12T10:00:00+08:00",
            }
        }
    }
    write_manifest(manifest_path, manifest)
    persisted_plan = {
        "format_version": 1,
        "plan_fingerprint": "sha256:plan",
        "analysis_snapshot": {
            "partition": "2024-12-31",
            "workspace_fingerprint": "sha256:workspace",
        },
        "verification": {
            "target_semantics": {
                "dws_store_sales_daily": {
                    "table_id": "id-dws-store-sales",
                    "semantic_context_fingerprint": "sha256:context",
                }
            }
        },
    }
    monkeypatch.setattr(
        run_cli,
        "require_fresh_plan",
        lambda plan_path, root, project: persisted_plan,
    )
    replans = []

    def fake_replan(path, updated_manifest, partition, source_snapshot):
        replans.append((path, updated_manifest, partition, source_snapshot))

    monkeypatch.setattr(run_cli, "_replan", fake_replan)
    monkeypatch.setattr(
        run_cli,
        "_now",
        lambda: datetime(2026, 7, 13, 15, 30, tzinfo=timezone.utc),
    )

    assert (
        run_cli.main(
            [
                "semantic-mode",
                "set",
                "--manifest",
                str(manifest_path),
                "--table",
                "dws_store_sales_daily",
                "--mode",
                "equivalent",
            ]
        )
        == 0
    )

    updated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated["artifacts"] == manifest["artifacts"]
    assert updated["base_git"] == manifest["base_git"]
    assert updated["root"] == manifest["root"]
    assert (
        updated["verification_intent"]["semantic_modes"]["other_table"]
        == manifest["verification_intent"]["semantic_modes"]["other_table"]
    )
    assert updated["verification_intent"]["semantic_modes"][
        "dws_store_sales_daily"
    ] == {
        "table_id": "id-dws-store-sales",
        "mode": "equivalent",
        "semantic_context_fingerprint": "sha256:context",
        "confirmed_at": "2026-07-13T15:30:00+00:00",
    }
    assert len(replans) == 1
    assert replans[0][0] == manifest_path
    assert replans[0][2] == "2024-12-31"
    assert replans[0][3] == persisted_plan["analysis_snapshot"]


def test_semantic_mode_replan_failure_invalidates_old_verification_outputs(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 13, 11, 32, 26, tzinfo=timezone.utc),
        git_info={"head": "base"},
    )
    write_manifest(manifest_path, manifest)
    for artifact_key in (
        "verification_plan",
        "shadow_run_result",
        "compare_result",
    ):
        path = manifest_path.parent / manifest["artifacts"][artifact_key]
        _write_json(path, {"stale": artifact_key})
    persisted_plan = {
        "analysis_snapshot": {
            "partition": "2024-12-31",
            "workspace_fingerprint": "sha256:workspace",
        },
        "verification": {
            "target_semantics": {
                "dws_sales": {
                    "table_id": "id-dws-sales",
                    "semantic_context_fingerprint": "sha256:context",
                }
            }
        },
    }
    monkeypatch.setattr(
        run_cli,
        "require_fresh_plan",
        lambda *args, **kwargs: persisted_plan,
    )
    monkeypatch.setattr(
        run_cli,
        "_replan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("replan failed")
        ),
    )

    with pytest.raises(RuntimeError, match="replan failed"):
        run_cli.main(
            [
                "semantic-mode",
                "set",
                "--manifest",
                str(manifest_path),
                "--table",
                "dws_sales",
                "--mode",
                "changed",
            ]
        )

    updated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (
        updated["verification_intent"]["semantic_modes"]["dws_sales"]["mode"]
        == "changed"
    )
    for artifact_key in (
        "verification_plan",
        "shadow_run_result",
        "compare_result",
    ):
        path = manifest_path.parent / manifest["artifacts"][artifact_key]
        assert not path.exists()


def test_lightweight_replan_rejects_workspace_change(monkeypatch, tmp_path):
    monkeypatch.setattr(
        run_cli,
        "workspace_fingerprint",
        lambda root, project: "sha256:after",
    )

    with pytest.raises(StalePlanError, match="workspace changed.*analyze"):
        run_cli._require_snapshot_workspace(
            {"workspace_fingerprint": "sha256:before"},
            repo_root=tmp_path,
            project="shop",
        )


def test_semantic_mode_set_rejects_table_outside_affected_scope(
    tmp_path, monkeypatch
):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 13, 11, 32, 26, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    monkeypatch.setattr(
        run_cli,
        "require_fresh_plan",
        lambda plan_path, root, project: {
            "analysis_snapshot": {
                "partition": "2024-12-31",
                "workspace_fingerprint": "sha256:workspace",
            },
            "verification": {"target_semantics": {}},
        },
    )

    with pytest.raises(SystemExit, match="affected semantic scope"):
        run_cli.main(
            [
                "semantic-mode",
                "set",
                "--manifest",
                str(manifest_path),
                "--table",
                "missing_table",
                "--mode",
                "equivalent",
            ]
        )


def test_shadow_run_rejects_stale_plan_before_handler(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 13, 11, 32, 26, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    called = []

    def stale_plan(*args, **kwargs):
        raise StalePlanError(
            "stale_plan: workspace changed after analyze; run analyze again"
        )

    monkeypatch.setattr(run_cli, "require_fresh_plan", stale_plan)
    monkeypatch.setattr(
        run_cli,
        "run_shadow_plan",
        lambda *args, **kwargs: called.append((args, kwargs)),
    )

    with pytest.raises(SystemExit, match="stale_plan.*analyze"):
        run_cli.main(["shadow-run", "--manifest", str(manifest_path)])

    assert called == []


def test_compare_rejects_stale_plan_before_handler(tmp_path, monkeypatch):
    _write_warehouse_config(tmp_path)
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 13, 11, 32, 26, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    called = []

    def stale_plan(*args, **kwargs):
        raise StalePlanError(
            "stale_plan: workspace changed after analyze; run analyze again"
        )

    monkeypatch.setattr(run_cli, "require_fresh_plan", stale_plan)
    monkeypatch.setattr(
        run_cli,
        "compare_shadow_results",
        lambda *args, **kwargs: called.append((args, kwargs)),
    )

    with pytest.raises(SystemExit, match="stale_plan.*analyze"):
        run_cli.main(["compare", "--manifest", str(manifest_path)])

    assert called == []
