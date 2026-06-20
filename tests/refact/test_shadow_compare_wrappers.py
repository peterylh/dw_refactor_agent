import json

import refact.verify_check as verify_check
import refact.verify_run as verify_run
from refact.compare import compare_shadow_results
from refact.shadow_run import run_shadow_plan


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def test_run_shadow_plan_delegates_to_verify_run(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_json(
        plan_path,
        {"project": "shop", "project_db": "shop_dm", "qa_db": "shop_dm_qa"},
    )
    calls = []

    def fake_run_metadata(meta, dry_run=False):
        calls.append((meta, dry_run))
        return {"status": "completed"}

    monkeypatch.setattr(verify_run, "run_metadata", fake_run_metadata)

    result = run_shadow_plan(plan_path, output_path)

    assert calls == [
        (
            {
                "project": "shop",
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
            },
            False,
        )
    ]
    assert result["status"] == "completed"
    assert json.loads(output_path.read_text())["status"] == "completed"


def test_compare_shadow_results_delegates_to_verify_check(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    _write_json(
        plan_path,
        {"project": "shop", "project_db": "shop_dm", "qa_db": "shop_dm_qa"},
    )
    calls = []

    def fake_run_checks(meta, method="all", sample=0, precision=0.01):
        calls.append((meta, method, sample, precision))
        return {"all_pass": True, "results": []}

    monkeypatch.setattr(verify_check, "run_checks", fake_run_checks)

    result = compare_shadow_results(
        plan_path,
        output_path,
        method="count",
        sample=10,
        precision=0.1,
    )

    assert calls == [
        (
            {
                "project": "shop",
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
            },
            "count",
            10,
            0.1,
        )
    ]
    assert result == {"all_pass": True, "results": []}
    assert json.loads(output_path.read_text()) == result
