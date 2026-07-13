import os
import time
from datetime import datetime, timezone

import pytest

from dw_refactor_agent.config import core as config_core
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.session import (
    artifact_path,
    create_run_manifest,
    load_historical_manifests,
    load_manifest,
    resolve_manifest_path,
    run_root_from_manifest_path,
    write_manifest,
)


def _local_datetime(*args):
    return datetime(*args).astimezone()


@pytest.fixture
def set_process_timezone(request):
    if not hasattr(time, "tzset"):
        pytest.skip("local timezone switching requires time.tzset")

    original_tz = os.environ.get("TZ")

    def set_timezone(name):
        os.environ["TZ"] = name
        time.tzset()

    def restore_timezone():
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()

    request.addfinalizer(restore_timezone)
    return set_timezone


def test_create_run_manifest_writes_expected_layout(tmp_path):
    now = _local_datetime(2026, 6, 20, 7, 30)

    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=now,
        git_info={"branch": "main", "head": "abc1234", "dirty": False},
    )

    assert manifest_path == (
        tmp_path
        / "warehouses"
        / "shop"
        / "artifacts"
        / "refactor_runs"
        / "20260620_073000_shop"
        / "manifest.json"
    )
    assert manifest["run_id"] == "20260620_073000_shop"
    assert manifest["format_version"] == 1
    assert manifest["project"] == "shop"
    assert manifest["root"] == str(tmp_path.resolve())
    assert manifest["base_git"] == {
        "branch": "main",
        "head": "abc1234",
        "dirty": False,
    }
    for dirname in ["baseline", "current", "analysis", "verification"]:
        assert (manifest_path.parent / dirname).is_dir()

    assert artifact_path(manifest_path, "baseline_lineage") == (
        manifest_path.parent / "baseline" / "lineage_data.json"
    )
    assert manifest["artifacts"]["baseline_full_assess"] == (
        "baseline/assess_result.json"
    )
    assert manifest["artifacts"]["current_scoped_assess"] == (
        "current/assess_result.json"
    )
    assert manifest["artifacts"]["scoped_issue_diff"] == (
        "analysis/issue_diff.json"
    )


def test_create_run_manifest_uses_configured_project_dir(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setitem(
        config_core.PROJECT_CONFIG,
        "demo",
        {"dir": "warehouses/custom_demo"},
    )

    manifest_path, _manifest = create_run_manifest(
        tmp_path,
        "demo",
        now=_local_datetime(2026, 6, 20, 7, 30),
        git_info={},
    )

    assert manifest_path == (
        tmp_path
        / "warehouses"
        / "custom_demo"
        / "artifacts"
        / "refactor_runs"
        / "20260620_073000_demo"
        / "manifest.json"
    )


def test_create_run_manifest_uses_local_time_for_names_and_metadata(
    tmp_path,
    set_process_timezone,
):
    set_process_timezone("Asia/Shanghai")

    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=datetime(2026, 7, 1, 2, 22, 42, 539505, tzinfo=timezone.utc),
        git_info={},
    )

    assert manifest_path == (
        tmp_path
        / "warehouses"
        / "shop"
        / "artifacts"
        / "refactor_runs"
        / "20260701_102242_shop"
        / "manifest.json"
    )
    assert manifest["run_id"] == "20260701_102242_shop"
    assert manifest["created_at"] == "2026-07-01T10:22:42.539505+08:00"


def test_manifest_round_trip_and_run_root(tmp_path):
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "finance_analytics",
        now=_local_datetime(2026, 6, 20, 8, 0),
        git_info={"branch": "", "head": "def5678", "dirty": True},
    )

    write_manifest(manifest_path, manifest)

    assert load_manifest(manifest_path) == manifest
    assert run_root_from_manifest_path(manifest_path) == manifest_path.parent


@pytest.mark.parametrize(
    "payload", [{"project": "shop"}, {"format_version": 2}]
)
def test_load_manifest_rejects_missing_or_wrong_format_version(
    tmp_path, payload
):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(str(payload).replace("'", '"'), encoding="utf-8")

    with pytest.raises(ArtifactFormatError, match="manifest.*format_version"):
        load_manifest(manifest_path)


def test_resolve_manifest_path_finds_unique_run_across_projects(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        config_core,
        "PROJECT_CONFIG",
        {
            "shop": {"dir": "warehouses/shop"},
            "finance": {"dir": "warehouses/finance"},
        },
    )
    manifest_path, _manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=_local_datetime(2026, 7, 13, 11, 32, 26),
        git_info={},
    )

    assert (
        resolve_manifest_path(
            manifest_path=None,
            run_id="20260713_113226_shop",
            root=tmp_path,
        )
        == manifest_path
    )


def test_resolve_manifest_path_rejects_zero_and_multiple_matches(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        config_core,
        "PROJECT_CONFIG",
        {
            "one": {"dir": "warehouses/one"},
            "two": {"dir": "warehouses/two"},
        },
    )
    with pytest.raises(SystemExit, match="no run.*--manifest"):
        resolve_manifest_path(
            manifest_path=None, run_id="same_run", root=tmp_path
        )

    for project in ("one", "two"):
        path = (
            tmp_path
            / "warehouses"
            / project
            / "artifacts/refactor_runs/same_run/manifest.json"
        )
        write_manifest(
            path,
            {
                "format_version": 1,
                "run_id": "same_run",
                "project": project,
                "root": str(tmp_path),
                "artifacts": {},
            },
        )

    with pytest.raises(SystemExit, match="multiple.*--manifest"):
        resolve_manifest_path(
            manifest_path=None, run_id="same_run", root=tmp_path
        )


def test_load_historical_manifests_skips_corrupt_history_with_diagnostic(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        config_core,
        "PROJECT_CONFIG",
        {"shop": {"dir": "warehouses/shop"}},
    )
    current_path, current = create_run_manifest(
        tmp_path,
        "shop",
        now=_local_datetime(2026, 7, 13, 12, 0, 0),
        git_info={},
    )
    historical_path, historical = create_run_manifest(
        tmp_path,
        "shop",
        now=_local_datetime(2026, 7, 12, 12, 0, 0),
        git_info={},
    )
    historical["verification_intent"] = {
        "semantic_modes": {"dws_sales": {"mode": "equivalent"}}
    }
    write_manifest(historical_path, historical)
    corrupt_path = (
        historical_path.parent.parent
        / "20260711_120000_shop"
        / "manifest.json"
    )
    corrupt_path.parent.mkdir()
    corrupt_path.write_text("{broken", encoding="utf-8")

    loaded, diagnostics = load_historical_manifests(current_path, current)

    assert loaded == [(historical_path, historical)]
    assert len(diagnostics) == 1
    assert "20260711_120000_shop" in diagnostics[0]
