#!/usr/bin/env python3
"""Command-line lineage viewer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.config import TEXT_ENCODING, job_dag_path
from dw_refactor_agent.lineage.contract import (
    validate_job_dag_v2,
    validate_lineage_v2,
)
from dw_refactor_agent.lineage.formatters import (
    format_column_json,
    format_column_text,
    format_stats_json,
    format_stats_text,
    format_table_dot,
    format_table_html,
    format_table_json,
    format_table_text,
)
from dw_refactor_agent.lineage.query import (
    build_column_lineage,
    build_project_stats,
    build_table_subgraph,
)
from dw_refactor_agent.lineage.service import open_lineage
from dw_refactor_agent.lineage.store import JsonLineageStore


def _lineage_store(args: argparse.Namespace) -> JsonLineageStore:
    lineage_dir = Path(args.lineage_dir) if args.lineage_dir else None
    return JsonLineageStore(lineage_dir=lineage_dir)


def _open_view(args: argparse.Namespace):
    return open_lineage(
        args.project,
        snapshot_id=getattr(args, "snapshot_id", None),
        store=_lineage_store(args),
    )


def _write_stdout(text: str) -> None:
    print(text)


def _handle_stats(args: argparse.Namespace) -> int:
    stats = build_project_stats(_open_view(args))
    if args.format == "json":
        _write_stdout(format_stats_json(stats))
    else:
        _write_stdout(format_stats_text(stats))
    return 0


def _handle_table(args: argparse.Namespace) -> int:
    subgraph = build_table_subgraph(
        _open_view(args),
        args.table,
        direction=args.direction,
        depth=args.depth,
    )
    if args.format == "json":
        _write_stdout(format_table_json(subgraph))
    elif args.format == "dot":
        _write_stdout(format_table_dot(subgraph))
    else:
        _write_stdout(format_table_text(subgraph))
    return 0


def _handle_column(args: argparse.Namespace) -> int:
    lineage = build_column_lineage(
        _open_view(args),
        args.table,
        args.column,
        direction=args.direction,
        depth=args.depth,
    )
    if args.format == "json":
        _write_stdout(format_column_json(lineage))
    else:
        _write_stdout(format_column_text(lineage, verbose=args.verbose))
    return 0


def _handle_export_html(args: argparse.Namespace) -> int:
    subgraph = build_table_subgraph(
        _open_view(args),
        args.table,
        direction=args.direction,
        depth=args.depth,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_table_html(subgraph), encoding=TEXT_ENCODING)
    _write_stdout(f"HTML written: {output_path}")
    return 0


def _handle_validate(args: argparse.Namespace) -> int:
    store = _lineage_store(args)
    lineage_path = store._snapshot_path(args.project, args.snapshot_id)
    dag_path = (
        Path(args.lineage_dir) / "job_dag.json"
        if args.lineage_dir
        else job_dag_path(args.project)
    )

    with lineage_path.open(encoding=TEXT_ENCODING) as file:
        validate_lineage_v2(json.load(file))
    with dag_path.open(encoding=TEXT_ENCODING) as file:
        validate_job_dag_v2(json.load(file))

    _write_stdout(f"lineage v2 valid: {lineage_path}")
    _write_stdout(f"job DAG v2 valid: {dag_path}")
    return 0


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        default="shop",
        help="Project name",
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help="Optional lineage snapshot id suffix",
    )
    parser.add_argument(
        "--lineage-dir",
        default=None,
        help=(
            "Directory containing lineage_data_<project>.json; defaults to "
            "warehouses/{project}/artifacts/lineage/lineage_data.json"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local lineage viewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stats_parser = subparsers.add_parser(
        "stats", help="Show project lineage stats"
    )
    _add_common_options(stats_parser)
    stats_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    stats_parser.set_defaults(handler=_handle_stats)

    table_parser = subparsers.add_parser("table", help="Show table lineage")
    _add_common_options(table_parser)
    table_parser.add_argument("--table", required=True, help="Root table name")
    table_parser.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="upstream",
        help="Lineage traversal direction",
    )
    table_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Maximum lineage hops",
    )
    table_parser.add_argument(
        "--format",
        choices=["text", "json", "dot"],
        default="text",
        help="Output format",
    )
    table_parser.set_defaults(handler=_handle_table)

    column_parser = subparsers.add_parser("column", help="Show column lineage")
    _add_common_options(column_parser)
    column_parser.add_argument(
        "--table", required=True, help="Root table name"
    )
    column_parser.add_argument(
        "--column", required=True, help="Required column name"
    )
    column_parser.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="upstream",
        help="Lineage traversal direction",
    )
    column_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Maximum lineage hops",
    )
    column_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    column_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show condition lineage such as filters and group-by columns",
    )
    column_parser.set_defaults(handler=_handle_column)

    html_parser = subparsers.add_parser(
        "export-html",
        help="Export a standalone local table-lineage HTML file",
    )
    _add_common_options(html_parser)
    html_parser.add_argument("--table", required=True, help="Root table name")
    html_parser.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="upstream",
        help="Lineage traversal direction",
    )
    html_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Maximum lineage hops",
    )
    html_parser.add_argument(
        "--output",
        required=True,
        help="HTML output path",
    )
    html_parser.set_defaults(handler=_handle_export_html)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Strictly validate lineage and Job DAG version 2 artifacts",
    )
    _add_common_options(validate_parser)
    validate_parser.set_defaults(handler=_handle_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
