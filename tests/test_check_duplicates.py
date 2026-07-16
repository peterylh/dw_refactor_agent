from pathlib import Path

from scripts.check_duplicates import (
    collect_python_files,
    duplicate_line_count,
    find_similarities,
    render_report,
)

DUPLICATE_BODY = """\
value_1 = 1
value_2 = 2
value_3 = 3
value_4 = 4
value_5 = 5
value_6 = 6
"""


def test_duplicate_report_and_exit_data(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(DUPLICATE_BODY, encoding="utf-8")
    second.write_text(DUPLICATE_BODY, encoding="utf-8")

    files = collect_python_files([tmp_path])
    checker, similarities = find_similarities(files, min_lines=4)
    report = render_report(
        checker,
        similarities,
        file_count=len(files),
        min_lines=4,
        root=tmp_path,
    )

    assert files == [first, second]
    assert len(similarities) == 1
    assert duplicate_line_count(similarities) == 6
    assert "duplicate_blocks=1" in report
    assert "TOTAL lines=12 duplicates=6 percent=50.00" in report
    assert "first.py:1-6" in report
    assert "second.py:1-6" in report


def test_collect_python_files_ignores_non_python_files(tmp_path: Path) -> None:
    python_file = tmp_path / "module.py"
    python_file.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("value = 1\n", encoding="utf-8")

    assert collect_python_files([tmp_path]) == [python_file]
