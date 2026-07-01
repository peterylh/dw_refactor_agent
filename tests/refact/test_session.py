from datetime import datetime, timezone

from refact.session import (
    artifact_path,
    create_run_manifest,
    load_manifest,
    run_root_from_manifest_path,
    write_manifest,
)


def test_create_run_manifest_writes_expected_layout(tmp_path):
    now = datetime(2026, 6, 20, 7, 30, tzinfo=timezone.utc)

    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "shop",
        now=now,
        git_info={"branch": "main", "head": "abc1234", "dirty": False},
    )

    assert manifest_path == (
        tmp_path / "refact" / "runs" / "20260620_073000_shop" / "manifest.json"
    )
    assert manifest["run_id"] == "20260620_073000_shop"
    assert manifest["project"] == "shop"
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


def test_manifest_round_trip_and_run_root(tmp_path):
    manifest_path, manifest = create_run_manifest(
        tmp_path,
        "finance_analytics",
        now=datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
        git_info={"branch": "", "head": "def5678", "dirty": True},
    )

    write_manifest(manifest_path, manifest)

    assert load_manifest(manifest_path) == manifest
    assert run_root_from_manifest_path(manifest_path) == manifest_path.parent
