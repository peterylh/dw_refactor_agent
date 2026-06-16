#!/usr/bin/env python3
"""Bulk import lineage_data_<project>.json into the project lineage database."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import pymysql

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_ENV_CONFIG, PROJECT_CONFIG


DEFAULT_BATCH_SIZE = 5000
LINEAGE_DIR = Path(__file__).resolve().parent
SNAPSHOT_DELETE_TABLES = (
    "indirect_lineage",
    "column_lineage",
    "table_lineage",
    "job",
    "column_info",
    "table_info",
    "datasource",
)
VERIFY_TABLES = (
    "lineage_snapshot",
    "datasource",
    "table_info",
    "column_info",
    "job",
    "column_lineage",
    "indirect_lineage",
    "table_lineage",
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkippedEdge:
    kind: str
    source: str
    target: str
    reason: str


@dataclass(frozen=True)
class ImportContext:
    project: str
    snapshot_id: int
    datasource_id: int
    datasource_name: str
    db_type: str
    host: str


@dataclass
class LineageImportRows:
    datasource_rows: list[tuple] = field(default_factory=list)
    table_rows: list[tuple] = field(default_factory=list)
    column_rows: list[tuple] = field(default_factory=list)
    job_rows: list[tuple] = field(default_factory=list)
    column_lineage_rows: list[tuple] = field(default_factory=list)
    indirect_lineage_rows: list[tuple] = field(default_factory=list)
    table_lineage_rows: list[tuple] = field(default_factory=list)
    skipped_edges: list[SkippedEdge] = field(default_factory=list)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将 lineage_data_{project}.json 批量导入对应项目的 lineage 库"
    )
    parser.add_argument(
        "--project",
        default="shop",
        choices=sorted(PROJECT_CONFIG.keys()),
        help="项目名称",
    )
    parser.add_argument(
        "--lineage-file",
        default=None,
        help="可选的血缘 JSON 文件路径，默认使用 lineage/lineage_data_<project>.json",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"executemany 每批行数，默认 {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument(
        "--db-env",
        default="prod",
        choices=sorted(DB_ENV_CONFIG.keys()),
        help="Doris 物理环境",
    )
    parser.add_argument(
        "--snapshot-id",
        type=int,
        default=None,
        help="可选快照 ID，默认使用当前时间毫秒",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="导入后不把当前快照标记为 active",
    )
    return parser


def _edge_ref_type(ref: Any) -> str:
    return str(ref.get("type") or "") if isinstance(ref, dict) else "column"


def _edge_ref_id(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("id") or ref.get("value") or "")
    return str(ref or "")


def _normalize_relation_type(value: Any) -> str:
    return str(value or "direct").strip().upper()


def _split_column_ref(ref: str) -> tuple[str, str] | None:
    if "." not in str(ref or ""):
        return None
    table_name, column_name = str(ref).rsplit(".", 1)
    if not table_name or not column_name:
        return None
    return table_name, column_name


def _typed_direct_column_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    direct_edges = []
    for edge in edges:
        if _normalize_relation_type(edge.get("relation_type")) != "DIRECT":
            continue
        if _edge_ref_type(edge.get("source")) != "column":
            continue
        if _edge_ref_type(edge.get("target")) != "column":
            continue
        current = dict(edge)
        current["source"] = _edge_ref_id(edge.get("source"))
        current["target"] = _edge_ref_id(edge.get("target"))
        direct_edges.append(current)
    return direct_edges


def _typed_indirect_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    indirect_edges = []
    for edge in edges:
        relation_type = _normalize_relation_type(edge.get("relation_type"))
        if relation_type == "DIRECT":
            continue
        if _edge_ref_type(edge.get("source")) != "column":
            continue
        if _edge_ref_type(edge.get("target")) != "table":
            continue
        indirect_edges.append({
            "source": _edge_ref_id(edge.get("source")),
            "target_table": _edge_ref_id(edge.get("target")),
            "condition_type": relation_type,
            "condition_expression": edge.get("expression", ""),
            "source_file": edge.get("source_file", ""),
        })
    return indirect_edges


def _read_task_sql(tasks_dir: Path, source_file: str) -> str | None:
    sql_file = tasks_dir / source_file
    if not sql_file.exists():
        return None
    return sql_file.read_text(encoding="utf-8")


def _job_name(source_file: str) -> str:
    return Path(source_file).name.removesuffix(".sql")


def _build_table_rows(
    tables: Sequence[dict[str, Any]],
    context: ImportContext,
) -> tuple[list[tuple], dict[str, int]]:
    table_rows = []
    table_id_map = {}
    for table_id, table in enumerate(tables, start=1):
        table_name = str(table.get("name") or "").strip()
        if not table_name:
            continue
        table_rows.append((
            table_id,
            context.snapshot_id,
            context.datasource_id,
            table_name,
            str(table.get("full_name") or table_name),
            str(table.get("layer") or "OTHER").upper(),
            1 if table.get("is_transient") else 0,
            json.dumps(
                table.get("transient_sources") or [],
                ensure_ascii=False,
            ),
        ))
        table_id_map[table_name] = table_id
    return table_rows, table_id_map


def _build_column_rows(
    tables: Sequence[dict[str, Any]],
    table_id_map: dict[str, int],
    *,
    snapshot_id: int,
) -> tuple[list[tuple], dict[str, int]]:
    column_rows = []
    column_id_map = {}
    column_id = 1
    for table in tables:
        table_name = str(table.get("name") or "").strip()
        table_id = table_id_map.get(table_name)
        if not table_id:
            continue
        for ordinal, column in enumerate(table.get("columns") or []):
            column_name = str(column.get("name") or "").strip()
            if not column_name:
                continue
            column_ref = f"{table_name}.{column_name}"
            column_rows.append((
                column_id,
                snapshot_id,
                table_id,
                column_name,
                str(column.get("type") or column.get("data_type") or ""),
                str(column.get("comment") or ""),
                ordinal,
            ))
            column_id_map[column_ref] = column_id
            column_id += 1
    return column_rows, column_id_map


def _build_job_rows(
    source_files: Sequence[str],
    tasks_dir: Path,
    *,
    snapshot_id: int,
) -> tuple[list[tuple], dict[str, int]]:
    job_rows = []
    job_id_map = {}
    for job_id, source_file in enumerate(source_files, start=1):
        job_rows.append((
            job_id,
            snapshot_id,
            _job_name(source_file),
            source_file,
            "SQL",
            _read_task_sql(tasks_dir, source_file),
        ))
        job_id_map[source_file] = job_id
    return job_rows, job_id_map


def _skip(
    rows: LineageImportRows,
    *,
    kind: str,
    source: str,
    target: str,
    reason: str,
) -> None:
    rows.skipped_edges.append(
        SkippedEdge(
            kind=kind,
            source=source,
            target=target,
            reason=reason,
        )
    )


def _build_column_lineage_rows(
    direct_edges: Sequence[dict[str, Any]],
    *,
    table_id_map: dict[str, int],
    column_id_map: dict[str, int],
    job_id_map: dict[str, int],
    rows: LineageImportRows,
) -> set[tuple[int, int, int | None, str]]:
    table_lineage_set: set[tuple[int, int, int | None, str]] = set()
    lineage_id = 1
    for edge in direct_edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        source_ref = _split_column_ref(source)
        target_ref = _split_column_ref(target)
        if source_ref is None or target_ref is None:
            _skip(
                rows,
                kind="direct",
                source=source,
                target=target,
                reason="source or target is not a table.column reference",
            )
            continue

        source_table, _source_column = source_ref
        target_table, _target_column = target_ref
        source_table_id = table_id_map.get(source_table)
        target_table_id = table_id_map.get(target_table)
        source_column_id = column_id_map.get(source)
        target_column_id = column_id_map.get(target)
        if not all([
            source_table_id,
            target_table_id,
            source_column_id,
            target_column_id,
        ]):
            _skip(
                rows,
                kind="direct",
                source=source,
                target=target,
                reason="source or target metadata is missing",
            )
            continue

        job_id = job_id_map.get(str(edge.get("source_file") or ""))
        relation_type = _normalize_relation_type(edge.get("relation_type"))
        rows.column_lineage_rows.append((
            lineage_id,
            rows.datasource_rows[0][1],
            source_table_id,
            source_column_id,
            target_table_id,
            target_column_id,
            job_id,
            relation_type,
            str(edge.get("transformation_type") or ""),
            str(edge.get("expression") or ""),
        ))
        table_lineage_set.add((
            source_table_id,
            target_table_id,
            job_id,
            relation_type,
        ))
        lineage_id += 1
    return table_lineage_set


def _build_indirect_lineage_rows(
    indirect_edges: Sequence[dict[str, Any]],
    *,
    table_id_map: dict[str, int],
    column_id_map: dict[str, int],
    job_id_map: dict[str, int],
    rows: LineageImportRows,
    table_lineage_set: set[tuple[int, int, int | None, str]],
) -> None:
    lineage_id = 1
    for edge in indirect_edges:
        source = str(edge.get("source") or "")
        target_table = str(edge.get("target_table") or "")
        source_ref = _split_column_ref(source)
        if source_ref is None:
            _skip(
                rows,
                kind="indirect",
                source=source,
                target=target_table,
                reason="source is not a table.column reference",
            )
            continue

        source_table, _source_column = source_ref
        source_table_id = table_id_map.get(source_table)
        source_column_id = column_id_map.get(source)
        target_table_id = table_id_map.get(target_table)
        job_id = job_id_map.get(str(edge.get("source_file") or ""))
        if not all([source_table_id, source_column_id, target_table_id, job_id]):
            _skip(
                rows,
                kind="indirect",
                source=source,
                target=target_table,
                reason="source, target, or job metadata is missing",
            )
            continue

        condition_type = str(edge.get("condition_type") or "").upper()
        rows.indirect_lineage_rows.append((
            lineage_id,
            rows.datasource_rows[0][1],
            source_table_id,
            source_column_id,
            target_table_id,
            job_id,
            condition_type,
            str(edge.get("condition_expression") or ""),
        ))
        table_lineage_set.add((
            source_table_id,
            target_table_id,
            job_id,
            condition_type,
        ))
        lineage_id += 1


def _build_table_lineage_rows(
    table_lineage_set: set[tuple[int, int, int | None, str]],
    *,
    snapshot_id: int,
) -> list[tuple]:
    return [
        (
            lineage_id,
            snapshot_id,
            source_table_id,
            target_table_id,
            job_id,
            relation_type,
        )
        for lineage_id, (
            source_table_id,
            target_table_id,
            job_id,
            relation_type,
        ) in enumerate(
            sorted(
                table_lineage_set,
                key=lambda item: (
                    item[0],
                    item[1],
                    -1 if item[2] is None else item[2],
                    item[3],
                ),
            ),
            start=1,
        )
    ]


def build_import_rows(
    data: dict[str, Any],
    *,
    tasks_dir: Path,
    context: ImportContext,
) -> LineageImportRows:
    """Convert one lineage JSON snapshot into database row tuples."""
    rows = LineageImportRows()
    rows.datasource_rows.append((
        context.datasource_id,
        context.snapshot_id,
        context.project,
        context.datasource_name,
        context.db_type,
        context.host,
    ))
    tables = [
        table
        for table in data.get("tables") or []
        if isinstance(table, dict)
    ]
    raw_edges = [
        edge
        for edge in data.get("edges") or []
        if isinstance(edge, dict)
    ]
    direct_edges = _typed_direct_column_edges(raw_edges)
    indirect_edges = data.get("indirect_edges") or _typed_indirect_edges(raw_edges)
    indirect_edges = [
        edge
        for edge in indirect_edges
        if isinstance(edge, dict)
    ]

    rows.table_rows, table_id_map = _build_table_rows(tables, context)
    rows.column_rows, column_id_map = _build_column_rows(
        tables,
        table_id_map,
        snapshot_id=context.snapshot_id,
    )

    source_files = sorted({
        str(edge.get("source_file") or "")
        for edge in [*direct_edges, *indirect_edges]
        if str(edge.get("source_file") or "")
    })
    rows.job_rows, job_id_map = _build_job_rows(
        source_files,
        Path(tasks_dir),
        snapshot_id=context.snapshot_id,
    )

    table_lineage_set = _build_column_lineage_rows(
        direct_edges,
        table_id_map=table_id_map,
        column_id_map=column_id_map,
        job_id_map=job_id_map,
        rows=rows,
    )
    _build_indirect_lineage_rows(
        indirect_edges,
        table_id_map=table_id_map,
        column_id_map=column_id_map,
        job_id_map=job_id_map,
        rows=rows,
        table_lineage_set=table_lineage_set,
    )
    rows.table_lineage_rows = _build_table_lineage_rows(
        table_lineage_set,
        snapshot_id=context.snapshot_id,
    )
    return rows


def _chunks(rows: Sequence[tuple], batch_size: int) -> Iterable[Sequence[tuple]]:
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    for start in range(0, len(rows), batch_size):
        yield rows[start:start + batch_size]


def bulk_insert(
    cursor,
    sql: str,
    rows: Sequence[tuple],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Insert rows with cursor.executemany in bounded batches."""
    inserted = 0
    for batch in _chunks(rows, batch_size):
        cursor.executemany(sql, batch)
        inserted += len(batch)
    return inserted


def _load_lineage_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _lineage_file(project: str, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return LINEAGE_DIR / f"lineage_data_{project}.json"


def _open_connection(database: str, *, db_env: str = "prod"):
    env_config = DB_ENV_CONFIG[db_env]
    return pymysql.connect(
        host=env_config["host"],
        port=int(env_config["port"]),
        user=env_config["user"],
        database=database,
        charset="utf8mb4",
    )


def default_snapshot_id() -> int:
    return int(datetime.now().timestamp() * 1000)


def delete_snapshot_rows(cursor, *, snapshot_id: int) -> None:
    for table_name in SNAPSHOT_DELETE_TABLES:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE snapshot_id = %s",
            (snapshot_id,),
        )
    cursor.execute(
        "DELETE FROM lineage_snapshot WHERE id = %s",
        (snapshot_id,),
    )


def _insert_all(
    cursor,
    *,
    rows: LineageImportRows,
    batch_size: int,
) -> dict[str, int]:
    counts = {}
    insert_specs = (
        (
            "datasource",
            "INSERT INTO datasource "
            "(id, snapshot_id, project, name, db_type, host) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            rows.datasource_rows,
        ),
        (
            "table_info",
            "INSERT INTO table_info "
            "(id, snapshot_id, datasource_id, table_name, full_name, layer, "
            "is_transient, transient_sources) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            rows.table_rows,
        ),
        (
            "column_info",
            "INSERT INTO column_info "
            "(id, snapshot_id, table_id, column_name, data_type, comment, ordinal) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            rows.column_rows,
        ),
        (
            "job",
            "INSERT INTO job (id, snapshot_id, job_name, source_file, job_type, raw_sql) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            rows.job_rows,
        ),
        (
            "column_lineage",
            "INSERT INTO column_lineage "
            "(id, snapshot_id, source_table_id, source_column_id, target_table_id, "
            "target_column_id, job_id, relation_type, transformation_type, expression) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows.column_lineage_rows,
        ),
        (
            "indirect_lineage",
            "INSERT INTO indirect_lineage "
            "(id, snapshot_id, source_table_id, source_column_id, target_table_id, job_id, "
            "condition_type, condition_expression) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            rows.indirect_lineage_rows,
        ),
        (
            "table_lineage",
            "INSERT INTO table_lineage "
            "(id, snapshot_id, source_table_id, target_table_id, job_id, relation_type) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            rows.table_lineage_rows,
        ),
    )
    for table_name, sql, table_rows in insert_specs:
        counts[table_name] = bulk_insert(
            cursor,
            sql,
            table_rows,
            batch_size=batch_size,
        )
    return counts


def insert_snapshot_row(
    cursor,
    *,
    snapshot_id: int,
    project: str,
    source_path: Path,
    status: str,
    is_active: int,
    rows: LineageImportRows,
) -> None:
    cursor.execute(
        "INSERT INTO lineage_snapshot "
        "(id, project, source_path, imported_at, status, is_active, "
        "table_count, column_count, job_count, column_lineage_count, "
        "indirect_lineage_count, table_lineage_count) "
        "VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            snapshot_id,
            project,
            str(source_path),
            status,
            is_active,
            len(rows.table_rows),
            len(rows.column_rows),
            len(rows.job_rows),
            len(rows.column_lineage_rows),
            len(rows.indirect_lineage_rows),
            len(rows.table_lineage_rows),
        ),
    )


def activate_snapshot(cursor, *, project: str, snapshot_id: int) -> None:
    cursor.execute(
        "UPDATE lineage_snapshot SET is_active = 0 "
        "WHERE project = %s AND id <> %s",
        (project, snapshot_id),
    )
    cursor.execute(
        "UPDATE lineage_snapshot SET status = %s, is_active = 1 "
        "WHERE project = %s AND id = %s",
        ("ACTIVE", project, snapshot_id),
    )


def _verify_counts(cursor, *, snapshot_id: int) -> dict[str, int]:
    counts = {}
    for table_name in VERIFY_TABLES:
        if table_name == "lineage_snapshot":
            cursor.execute(
                "SELECT COUNT(*) FROM lineage_snapshot WHERE id = %s",
                (snapshot_id,),
            )
        else:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE snapshot_id = %s",
                (snapshot_id,),
            )
        counts[table_name] = int(cursor.fetchone()[0])
    return counts


def import_lineage(
    *,
    project: str,
    lineage_file: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    snapshot_id: int | None = None,
    activate: bool = True,
    db_env: str = "prod",
) -> dict[str, int]:
    """Load one project lineage JSON into its configured Doris lineage database."""
    cfg = PROJECT_CONFIG[project]
    env_config = DB_ENV_CONFIG[db_env]
    tasks_dir = PROJECT_ROOT / cfg["dir"] / "tasks"
    data = _load_lineage_json(lineage_file)
    current_snapshot_id = (
        snapshot_id if snapshot_id is not None else default_snapshot_id()
    )
    context = ImportContext(
        project=project,
        snapshot_id=current_snapshot_id,
        datasource_id=1,
        datasource_name=cfg["db"],
        db_type="doris",
        host=f"{env_config['host']}:{env_config['port']}",
    )
    rows = build_import_rows(data, tasks_dir=tasks_dir, context=context)

    connection = _open_connection(cfg["lineage_db"], db_env=db_env)
    try:
        cursor = connection.cursor()
        try:
            LOGGER.info("清理快照 %s 的历史导入数据", current_snapshot_id)
            delete_snapshot_rows(cursor, snapshot_id=current_snapshot_id)
            connection.commit()

            LOGGER.info(
                "批量导入: tables=%s columns=%s jobs=%s column_edges=%s "
                "indirect_edges=%s table_edges=%s batch_size=%s",
                len(rows.table_rows),
                len(rows.column_rows),
                len(rows.job_rows),
                len(rows.column_lineage_rows),
                len(rows.indirect_lineage_rows),
                len(rows.table_lineage_rows),
                batch_size,
            )
            _insert_all(
                cursor,
                rows=rows,
                batch_size=batch_size,
            )
            insert_snapshot_row(
                cursor,
                snapshot_id=current_snapshot_id,
                project=project,
                source_path=lineage_file,
                status="IMPORTED",
                is_active=0,
                rows=rows,
            )
            if activate:
                activate_snapshot(
                    cursor,
                    project=project,
                    snapshot_id=current_snapshot_id,
                )
            connection.commit()

            if rows.skipped_edges:
                LOGGER.warning("跳过 %s 条无法映射的血缘边", len(rows.skipped_edges))
                for edge in rows.skipped_edges[:20]:
                    LOGGER.warning(
                        "跳过 %s: %s -> %s (%s)",
                        edge.kind,
                        edge.source,
                        edge.target,
                        edge.reason,
                    )

            return _verify_counts(cursor, snapshot_id=current_snapshot_id)
        finally:
            cursor.close()
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    lineage_file = _lineage_file(args.project, args.lineage_file)
    counts = import_lineage(
        project=args.project,
        lineage_file=lineage_file,
        batch_size=args.batch_size,
        snapshot_id=args.snapshot_id,
        activate=not args.no_activate,
        db_env=args.db_env,
    )
    LOGGER.info("")
    LOGGER.info("=== 验证 ===")
    for table_name in VERIFY_TABLES:
        LOGGER.info("  %s: %s 行", table_name, counts.get(table_name, 0))
    LOGGER.info("")
    LOGGER.info("%s 导入完成!", PROJECT_CONFIG[args.project]["lineage_db"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
