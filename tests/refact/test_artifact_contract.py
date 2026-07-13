import json

import pytest

from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
    read_json_object,
    require_format_version,
    sha256_json,
)


def test_atomic_write_json_replaces_complete_document(tmp_path):
    path = tmp_path / "manifest.json"

    atomic_write_json(path, {"format_version": 1, "value": "old"})
    atomic_write_json(path, {"format_version": 1, "value": "new"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "format_version": 1,
        "value": "new",
    }
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []


def test_sha256_json_is_independent_of_mapping_order():
    assert sha256_json({"b": 2, "a": 1}) == sha256_json({"a": 1, "b": 2})
    assert sha256_json({"a": 1}).startswith("sha256:")


@pytest.mark.parametrize("actual", [None, 0, 2, "1"])
def test_require_format_version_rejects_missing_or_wrong_value(actual):
    with pytest.raises(ArtifactFormatError, match="plan.*format_version"):
        require_format_version({"format_version": actual}, "plan")


def test_require_format_version_accepts_current_value():
    require_format_version({"format_version": FORMAT_VERSION}, "plan")


@pytest.mark.parametrize("content", ["{broken", "[]", '"text"'])
def test_read_json_object_reports_corrupt_or_non_object_artifact(
    tmp_path, content
):
    path = tmp_path / "artifact.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ArtifactFormatError, match="test artifact"):
        read_json_object(path, "test artifact")
