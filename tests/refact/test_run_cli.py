import json
from datetime import datetime, timezone

import dw_refactor_agent.refactor.run as run_cli
from dw_refactor_agent.refactor.session import (
    create_run_manifest,
    write_manifest,
)


def _local_datetime(*args):
    return datetime(*args).astimezone()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def test_start_creates_manifest_and_baseline_artifacts(tmp_path, monkeypatch):
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


def test_analyze_refreshes_current_analysis_diff_and_plan(
    tmp_path, monkeypatch
):
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
    ):
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
            "baseline_ddl": {},
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
    issue_diff = json.loads(
        (run_root / "analysis" / "issue_diff.json").read_text()
    )
    assert issue_diff["summary"]["fixed_count"] == 0
    assert issue_diff["summary"]["remaining_count"] == 1
    assert issue_diff["summary"]["new_count"] == 0
    assert assess_calls[0]["change_analysis"]["affected_scope"][
        "assessment_tables"
    ] == ["dwd_order"]
    assert assess_calls[0]["change_analysis"]["changed_assets"][
        "model_tables"
    ] == ["dwd_order"]
    assert (run_root / "verification" / "plan.json").exists()
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


def test_analyze_marks_empty_diff_assessment_not_applicable(
    tmp_path, monkeypatch
):
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
    ):
        return {
            "project": project,
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "affected_scope": {
                "direct_tables": [],
                "downstream_tables": [],
                "anchor_tables": [],
                "assessment_tables": [],
                "assessment_tasks": [],
                "global_dimensions": [],
            },
            "modified_jobs": [],
            "downstream_tables": [],
            "anchors": [],
            "baseline_ddl": {},
            "ddl_changes": [],
            "partition_info": {},
            "jobs_to_run": [],
            "verification": {
                "checks": [],
                "data_anchor_status": "not_required",
            },
        }

    monkeypatch.setattr(run_cli, "build_lineage_artifacts", fake_lineage)
    monkeypatch.setattr(run_cli, "assess", fake_assess)
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


def test_shadow_run_and_compare_delegate_to_plan_handlers(
    tmp_path, monkeypatch
):
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

    def fake_shadow(plan, output, dry_run=False):
        calls.append(("shadow", plan, output, dry_run))
        _write_json(output, {"ok": True})
        return {"ok": True}

    def fake_compare(plan, output, method="all", sample=0, precision=0.01):
        calls.append(("compare", plan, output, method, sample, precision))
        _write_json(output, {"ok": True})
        return {"ok": True}

    monkeypatch.setattr(run_cli, "run_shadow_plan", fake_shadow)
    monkeypatch.setattr(run_cli, "compare_shadow_results", fake_compare)

    assert run_cli.main(["shadow-run", "--manifest", str(manifest_path)]) == 0
    assert run_cli.main(["compare", "--manifest", str(manifest_path)]) == 0

    assert calls[0][0] == "shadow"
    assert calls[0][1] == plan_path
    assert calls[1][0] == "compare"
    assert calls[1][1] == plan_path


def test_shadow_run_cli_reports_handler_failure(tmp_path, monkeypatch):
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc),
        git_info={},
    )
    write_manifest(manifest_path, manifest)
    plan_path = manifest_path.parent / "verification" / "plan.json"
    _write_json(plan_path, {"project": "shop"})

    def fake_shadow(plan, output, dry_run=False):
        _write_json(output, {"status": "failed"})
        return {"status": "failed"}

    monkeypatch.setattr(run_cli, "run_shadow_plan", fake_shadow)

    assert run_cli.main(["shadow-run", "--manifest", str(manifest_path)]) == 1
