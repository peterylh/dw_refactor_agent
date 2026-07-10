from __future__ import annotations

import argparse
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import dw_refactor_agent.config as config

from .ddl_deriver import inject_table_id, parse_create_table

_TABLE_MARKER_RE = re.compile(
    r"--[ \t]*table_id:[ \t]*(?P<value>[^\s]+)", re.IGNORECASE
)
_COLUMN_MARKER_RE = re.compile(
    r"--[ \t]*column_id:[ \t]*(?P<value>[^\s]+)", re.IGNORECASE
)


@dataclass(frozen=True)
class IdentityAssignment:
    kind: str
    path: Path
    value: str
    column_name: str = ""


@dataclass(frozen=True)
class IdentityIssue:
    code: str
    path: Path
    message: str
    line: int = 0
    column_name: str = ""
    value: str = ""


class SchemaIdentityError(ValueError):
    def __init__(self, issues: Sequence[IdentityIssue]):
        self.issues = list(issues)
        message = "; ".join(_format_issue(issue) for issue in self.issues)
        super().__init__(message or "schema identity validation failed")


@dataclass
class _FileScan:
    issues: List[IdentityIssue]
    table_occurrences: List[Tuple[str, Path, int, str]]
    column_occurrences: List[Tuple[str, Path, int, str]]


def _new_uuid4() -> str:
    return str(uuid.uuid4())


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return False
    return parsed.version == 4 and str(parsed) == str(value).lower()


def _newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _column_line_indices(
    text: str, column_names: Sequence[str]
) -> Dict[str, int]:
    lines = text.splitlines(keepends=True)
    result: Dict[str, int] = {}
    start = 0
    for column_name in column_names:
        escaped = re.escape(column_name)
        pattern = re.compile(rf"^[ \t]*`?{escaped}`?(?=[ \t]+)", re.IGNORECASE)
        for index in range(start, len(lines)):
            if pattern.match(lines[index]):
                result[column_name] = index
                start = index + 1
                break
    return result


def _column_markers_before(
    lines: Sequence[str], column_line: int
) -> List[Tuple[str, int]]:
    markers: List[Tuple[str, int]] = []
    index = column_line - 1
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped:
            index -= 1
            continue
        if not stripped.startswith("--"):
            break
        match = _COLUMN_MARKER_RE.search(lines[index])
        if match:
            markers.append((match.group("value"), index))
        index -= 1
    markers.reverse()
    return markers


def _read_parsed_file(path: Path):
    text = Path(path).read_text(encoding=config.TEXT_ENCODING)
    table = parse_create_table(text)
    if table is None:
        raise ValueError(f"DDL 无法解析: {path}")
    column_lines = _column_line_indices(
        text, [column.name for column in table.columns]
    )
    missing_locations = [
        column.name
        for column in table.columns
        if column.name not in column_lines
    ]
    if missing_locations:
        names = ", ".join(missing_locations)
        raise ValueError(f"无法定位字段定义行: {path}: {names}")
    return text, table, column_lines


def _existing_marker_errors(path: Path, text: str, table, column_lines):
    issues: List[IdentityIssue] = []
    lines = text.splitlines(keepends=True)
    table_markers = list(_TABLE_MARKER_RE.finditer(text))
    if len(table_markers) > 1:
        issues.append(
            IdentityIssue(
                "multiple_table_id",
                path,
                "一个 DDL 文件只能有一个 table_id",
            )
        )
    elif table_markers and not _is_uuid4(table_markers[0].group("value")):
        issues.append(
            IdentityIssue(
                "invalid_table_id",
                path,
                "table_id 必须是规范 UUID4",
                value=table_markers[0].group("value"),
            )
        )

    attached_marker_lines = set()
    for column in table.columns:
        markers = _column_markers_before(lines, column_lines[column.name])
        attached_marker_lines.update(line for _value, line in markers)
        if len(markers) > 1:
            issues.append(
                IdentityIssue(
                    "multiple_column_id",
                    path,
                    "一个字段只能有一个 column_id",
                    column_name=column.name,
                )
            )
        elif markers and not _is_uuid4(markers[0][0]):
            issues.append(
                IdentityIssue(
                    "invalid_column_id",
                    path,
                    "column_id 必须是规范 UUID4",
                    line=markers[0][1] + 1,
                    column_name=column.name,
                    value=markers[0][0],
                )
            )

    for index, line in enumerate(lines):
        if (
            _COLUMN_MARKER_RE.search(line)
            and index not in attached_marker_lines
        ):
            issues.append(
                IdentityIssue(
                    "orphan_column_id",
                    path,
                    "column_id 必须紧邻并关联到字段定义",
                    line=index + 1,
                )
            )
    return issues


def _raise_existing_marker_errors(
    path: Path, text: str, table, column_lines
) -> None:
    issues = _existing_marker_errors(path, text, table, column_lines)
    if issues:
        raise SchemaIdentityError(issues)


def _insert_column_ids(
    text: str,
    path: Path,
    column_lines: Dict[str, int],
    assignments: Sequence[IdentityAssignment],
) -> str:
    if not assignments:
        return text
    lines = text.splitlines(keepends=True)
    newline = _newline_for(text)
    insertions = []
    for assignment in assignments:
        index = column_lines[assignment.column_name]
        indent_match = re.match(r"^[ \t]*", lines[index])
        indent = indent_match.group(0) if indent_match else ""
        marker = f"{indent}-- column_id: {assignment.value}{newline}"
        insertions.append((index, marker))
    for index, marker in sorted(insertions, reverse=True):
        lines.insert(index, marker)
    return "".join(lines)


def init_file(path: Path) -> List[IdentityAssignment]:
    target = Path(path)
    text, table, column_lines = _read_parsed_file(target)
    _raise_existing_marker_errors(target, text, table, column_lines)

    assignments: List[IdentityAssignment] = []
    if not table.table_id:
        assignments.append(IdentityAssignment("table", target, _new_uuid4()))
    for column in table.columns:
        if column.column_id:
            continue
        assignments.append(
            IdentityAssignment("column", target, _new_uuid4(), column.name)
        )
    if not assignments:
        return []

    column_assignments = [
        assignment for assignment in assignments if assignment.kind == "column"
    ]
    new_text = _insert_column_ids(
        text, target, column_lines, column_assignments
    )
    table_assignment = next(
        (
            assignment
            for assignment in assignments
            if assignment.kind == "table"
        ),
        None,
    )
    if table_assignment:
        new_text = inject_table_id(new_text, table_assignment.value)
    target.write_text(new_text, encoding=config.TEXT_ENCODING)
    return assignments


def assign_column(path: Path, column_name: str) -> IdentityAssignment:
    target = Path(path)
    text, table, column_lines = _read_parsed_file(target)
    _raise_existing_marker_errors(target, text, table, column_lines)
    matches = [
        column
        for column in table.columns
        if column.name.casefold() == str(column_name).casefold()
    ]
    if not matches:
        raise ValueError(f"字段不存在: {target}: {column_name}")
    column = matches[0]
    if column.column_id:
        raise ValueError(
            f"字段已有 column_id: {target}: {column.name}: {column.column_id}"
        )
    assignment = IdentityAssignment(
        "column", target, _new_uuid4(), column.name
    )
    new_text = _insert_column_ids(text, target, column_lines, [assignment])
    target.write_text(new_text, encoding=config.TEXT_ENCODING)
    return assignment


def managed_ddl_files(project: str) -> List[Path]:
    if project not in config.PROJECT_CONFIG:
        raise ValueError(f"未知项目: {project}")
    return config.iter_project_asset_files(project, "ddl", "*.sql")


def init_project(project: str) -> List[IdentityAssignment]:
    assignments: List[IdentityAssignment] = []
    for path in managed_ddl_files(project):
        assignments.extend(init_file(path))
    return assignments


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _scan_file(path: Path, require_complete: bool) -> _FileScan:
    target = Path(path)
    text = target.read_text(encoding=config.TEXT_ENCODING)
    table = parse_create_table(text)
    if table is None:
        issues = (
            [IdentityIssue("parse_error", target, "DDL 无法解析")]
            if require_complete
            else []
        )
        return _FileScan(issues, [], [])

    column_lines = _column_line_indices(
        text, [column.name for column in table.columns]
    )
    issues = _existing_marker_errors(target, text, table, column_lines)
    lines = text.splitlines(keepends=True)
    table_occurrences: List[Tuple[str, Path, int, str]] = []
    column_occurrences: List[Tuple[str, Path, int, str]] = []

    table_markers = list(_TABLE_MARKER_RE.finditer(text))
    if not table_markers and require_complete:
        issues.append(
            IdentityIssue("missing_table_id", target, "受管 DDL 缺少 table_id")
        )
    for marker in table_markers:
        value = marker.group("value")
        if _is_uuid4(value):
            table_occurrences.append(
                (
                    value.lower(),
                    target,
                    _line_number(text, marker.start()),
                    table.short_name,
                )
            )

    for column in table.columns:
        line_index = column_lines.get(column.name)
        if line_index is None:
            if require_complete:
                issues.append(
                    IdentityIssue(
                        "column_source_not_found",
                        target,
                        "无法定位字段定义行",
                        column_name=column.name,
                    )
                )
            continue
        markers = _column_markers_before(lines, line_index)
        if not markers and require_complete:
            issues.append(
                IdentityIssue(
                    "missing_column_id",
                    target,
                    "受管字段缺少 column_id",
                    line=line_index + 1,
                    column_name=column.name,
                )
            )
        for value, marker_line in markers:
            if _is_uuid4(value):
                column_occurrences.append(
                    (
                        value.lower(),
                        target,
                        marker_line + 1,
                        column.name,
                    )
                )
    return _FileScan(
        sorted(issues, key=_issue_sort_key),
        table_occurrences,
        column_occurrences,
    )


def _managed_identity_projects(requested_project: str) -> List[str]:
    projects = {requested_project}
    for project, project_config in config.PROJECT_CONFIG.items():
        identity_config = project_config.get("schema_identity") or {}
        if isinstance(identity_config, dict) and identity_config.get(
            "required"
        ):
            projects.add(project)
    return sorted(projects)


def _duplicate_issues(
    occurrences: Sequence[Tuple[str, Path, int, str]],
    *,
    code: str,
    label: str,
) -> List[IdentityIssue]:
    by_value: Dict[str, List[Tuple[Path, int, str]]] = {}
    for value, path, line, owner in occurrences:
        by_value.setdefault(value, []).append((path, line, owner))
    issues = []
    for value, owners in by_value.items():
        if len(owners) < 2:
            continue
        for path, line, owner in owners:
            issues.append(
                IdentityIssue(
                    code,
                    path,
                    f"{label} 在受管 DDL 中重复",
                    line=line,
                    column_name=owner if code == "duplicate_column_id" else "",
                    value=value,
                )
            )
    return issues


def _issue_sort_key(issue: IdentityIssue):
    return (
        issue.path.as_posix(),
        issue.line,
        issue.code,
        issue.column_name,
    )


def validate_project(project: str) -> List[IdentityIssue]:
    target_files = set(managed_ddl_files(project))
    issues: List[IdentityIssue] = []
    table_occurrences: List[Tuple[str, Path, int, str]] = []
    column_occurrences: List[Tuple[str, Path, int, str]] = []
    scanned = set()
    for identity_project in _managed_identity_projects(project):
        for path in managed_ddl_files(identity_project):
            if path in scanned:
                continue
            scanned.add(path)
            scan = _scan_file(path, require_complete=path in target_files)
            issues.extend(scan.issues)
            table_occurrences.extend(scan.table_occurrences)
            column_occurrences.extend(scan.column_occurrences)
    issues.extend(
        _duplicate_issues(
            table_occurrences,
            code="duplicate_table_id",
            label="table_id",
        )
    )
    issues.extend(
        _duplicate_issues(
            column_occurrences,
            code="duplicate_column_id",
            label="column_id",
        )
    )
    return sorted(issues, key=_issue_sort_key)


def validate_table_defs(tables: dict, source: str) -> List[IdentityIssue]:
    issues: List[IdentityIssue] = []
    table_occurrences: List[Tuple[str, Path, int, str]] = []
    column_occurrences: List[Tuple[str, Path, int, str]] = []
    source_path = Path(source)
    for table_name, table in sorted(tables.items()):
        path = source_path / f"{table_name}.sql"
        if not table.table_id:
            issues.append(
                IdentityIssue(
                    "missing_table_id", path, "基线 DDL 缺少 table_id"
                )
            )
        elif not _is_uuid4(table.table_id):
            issues.append(
                IdentityIssue(
                    "invalid_table_id",
                    path,
                    "table_id 必须是规范 UUID4",
                    value=table.table_id,
                )
            )
        else:
            table_occurrences.append(
                (table.table_id.lower(), path, 0, table_name)
            )
        for column in table.columns:
            if not column.column_id:
                issues.append(
                    IdentityIssue(
                        "missing_column_id",
                        path,
                        "基线字段缺少 column_id",
                        column_name=column.name,
                    )
                )
            elif not _is_uuid4(column.column_id):
                issues.append(
                    IdentityIssue(
                        "invalid_column_id",
                        path,
                        "column_id 必须是规范 UUID4",
                        column_name=column.name,
                        value=column.column_id,
                    )
                )
            else:
                column_occurrences.append(
                    (
                        column.column_id.lower(),
                        path,
                        0,
                        column.name,
                    )
                )
    issues.extend(
        _duplicate_issues(
            table_occurrences,
            code="duplicate_table_id",
            label="table_id",
        )
    )
    issues.extend(
        _duplicate_issues(
            column_occurrences,
            code="duplicate_column_id",
            label="column_id",
        )
    )
    return sorted(issues, key=_issue_sort_key)


def require_valid_project(project: str) -> None:
    issues = validate_project(project)
    if issues:
        raise SchemaIdentityError(issues)


def _format_issue(issue: IdentityIssue) -> str:
    location = issue.path.as_posix()
    if issue.line:
        location = f"{location}:{issue.line}"
    if issue.column_name:
        location = f"{location} [{issue.column_name}]"
    return f"{issue.code}: {location}: {issue.message}"


def _print_assignments(assignments: Sequence[IdentityAssignment]) -> None:
    for assignment in assignments:
        owner = (
            f" column={assignment.column_name}"
            if assignment.column_name
            else ""
        )
        print(
            f"{assignment.kind}: {assignment.path}{owner} id={assignment.value}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="受管 DDL schema ID 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_project_parser = subparsers.add_parser("init-project")
    init_project_parser.add_argument("--project", required=True)

    init_file_parser = subparsers.add_parser("init-file")
    init_file_parser.add_argument("--file", type=Path, required=True)

    assign_parser = subparsers.add_parser("assign-column")
    assign_parser.add_argument("--file", type=Path, required=True)
    assign_parser.add_argument("--column", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--project", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "init-project":
            assignments = init_project(args.project)
            _print_assignments(assignments)
            print(f"完成: {len(assignments)} 个 schema ID")
            return 0
        if args.command == "init-file":
            assignments = init_file(args.file)
            _print_assignments(assignments)
            print(f"完成: {len(assignments)} 个 schema ID")
            return 0
        if args.command == "assign-column":
            assignment = assign_column(args.file, args.column)
            _print_assignments([assignment])
            return 0

        issues = validate_project(args.project)
        if issues:
            for issue in issues:
                print(_format_issue(issue))
            print(f"校验失败: {len(issues)} 个问题")
            return 1
        print(f"校验通过: {args.project}")
        return 0
    except (OSError, SchemaIdentityError, ValueError) as exc:
        print(f"错误: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
