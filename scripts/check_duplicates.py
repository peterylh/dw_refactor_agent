import argparse
import tokenize
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from pylint.checkers.similar import LineSet, Similar

DEFAULT_MIN_LINES = 8


def collect_python_files(paths: Iterable[Path]) -> List[Path]:
    """Collect unique Python files below files or directories."""
    files = set()
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.add(path.resolve())
        elif path.is_dir():
            files.update(
                candidate.resolve() for candidate in path.rglob("*.py")
            )
    return sorted(files)


def find_similarities(
    files: Iterable[Path], min_lines: int
) -> Tuple[Similar, list]:
    """Run Pylint's similarity engine for the supplied Python files."""
    checker = Similar(
        min_lines=min_lines,
        ignore_comments=True,
        ignore_docstrings=True,
        ignore_imports=True,
        ignore_signatures=True,
    )
    for path in files:
        with tokenize.open(str(path)) as stream:
            checker.append_stream(str(path), stream)
    return checker, checker._compute_sims()


def duplicate_line_count(similarities: list) -> int:
    """Count duplicated lines using the same formula as Pylint's symilar CLI."""
    return sum(
        line_count * (len(locations) - 1)
        for line_count, locations in similarities
    )


def display_path(path: str, root: Path) -> str:
    """Return a repository-relative path when possible."""
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return path


def display_location(
    line_set: LineSet, start_line: int, end_line: int, root: Path
) -> str:
    """Convert Pylint's zero-based slice to a human-readable line range."""
    return "{}:{}-{}".format(
        display_path(line_set.name, root),
        int(start_line) + 1,
        int(end_line),
    )


def render_report(
    checker: Similar,
    similarities: list,
    file_count: int,
    min_lines: int,
    root: Path,
) -> str:
    """Render a concise report with locations and an overall duplication rate."""
    total_lines = sum(len(line_set) for line_set in checker.linesets)
    duplicated_lines = duplicate_line_count(similarities)
    percentage = duplicated_lines * 100.0 / total_lines if total_lines else 0.0
    lines = [
        "Python duplicate code report",
        "files={} threshold={} duplicate_blocks={}".format(
            file_count, min_lines, len(similarities)
        ),
        "TOTAL lines={} duplicates={} percent={:.2f}".format(
            total_lines, duplicated_lines, percentage
        ),
    ]
    for index, (line_count, locations) in enumerate(similarities, start=1):
        lines.append("")
        lines.append(
            "{}. {} similar lines in {} files".format(
                index, line_count, len(locations)
            )
        )
        for line_set, start_line, end_line in sorted(locations):
            lines.append(
                "   " + display_location(line_set, start_line, end_line, root)
            )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect duplicate Python code"
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=DEFAULT_MIN_LINES,
        help="minimum number of similar effective lines (default: 8)",
    )
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if args.min_lines < 1:
        parser.error("--min-lines must be at least 1")
    return args


def main(argv: Sequence[str] = None) -> int:
    args = parse_args(argv)
    root = Path.cwd().resolve()
    files = collect_python_files(args.paths)
    if not files:
        print("No Python files found in the supplied paths")
        return 2
    checker, similarities = find_similarities(files, args.min_lines)
    print(
        render_report(
            checker,
            similarities,
            file_count=len(files),
            min_lines=args.min_lines,
            root=root,
        )
    )
    return 1 if similarities else 0


if __name__ == "__main__":
    raise SystemExit(main())
