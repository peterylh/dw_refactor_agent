import os
import time
from datetime import datetime, timezone

import pytest

from dw_refactor_agent.config import core as config_core
from dw_refactor_agent.refactor.session import (
    artifact_path,
    create_run_manifest,
    load_manifest,
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
