from pathlib import Path

from tests.taxonomy import TEST_TYPE_BY_FILE, TEST_TYPE_MARKERS


def test_test_files_have_registered_explicit_type_markers(request):
    repo_root = Path(__file__).resolve().parents[1]
    test_files = {
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "tests").rglob("test*.py")
    }
    configured_files = set(TEST_TYPE_BY_FILE)

    missing = sorted(test_files - configured_files)
    stale = sorted(configured_files - test_files)
    invalid = {
        path: test_type
        for path, test_type in sorted(TEST_TYPE_BY_FILE.items())
        if test_type not in TEST_TYPE_MARKERS
    }

    configured_marker_lines = "\n".join(request.config.getini("markers"))
    unregistered_markers = sorted(
        marker
        for marker in TEST_TYPE_MARKERS
        if f"{marker}:" not in configured_marker_lines
    )

    assigned_markers = {
        marker
        for marker in TEST_TYPE_MARKERS
        if request.node.get_closest_marker(marker) is not None
    }

    assert missing == []
    assert stale == []
    assert invalid == {}
    assert unregistered_markers == []
    assert assigned_markers == {"guard"}
