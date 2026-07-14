"""QA database pool configuration and lifecycle helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

import pymysql

from dw_refactor_agent.config import DORIS_HOST, DORIS_PORT, DORIS_QA_USER
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError

_DATABASE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OBJECT_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SYSTEM_DATABASES = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
}
EXECUTION_MARKER_TABLE = "dw_refactor_execution_marker"
MARKER_FORMAT_VERSION = 2
MARKER_COLUMNS = (
    "format_version",
    "marker_key",
    "project",
    "run_id",
    "execution_id",
    "qa_database",
    "plan_fingerprint",
    "workspace_fingerprint",
    "claimed_at",
)
_LEGACY_MARKER_COLUMNS = (
    "marker_key",
    "execution_id",
    "plan_fingerprint",
    "workspace_fingerprint",
    "completed_at",
)
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class QaSlotOwnership:
    """Immutable ownership recorded in one claimed QA database."""

    format_version: int
    project: str
    run_id: str
    execution_id: str
    qa_database: str
    plan_fingerprint: str
    workspace_fingerprint: str
    claimed_at: str
    claimed_at_epoch: int


@dataclass(frozen=True)
class QaSlotInspection:
    """Current allocation condition for one configured QA database."""

    project: str
    database: str
    availability: str
    ownership: QaSlotOwnership | None
    diagnostic: str | None
    objects: tuple[tuple[str, str], ...]


class QaPoolExhaustedError(ArtifactFormatError):
    """Raised when every configured QA pool slot is unavailable."""

    def __init__(self, inspections: list[QaSlotInspection]):
        self.inspections = tuple(inspections)
        summary = ", ".join(
            f"{item.database}={item.availability}" for item in self.inspections
        )
        super().__init__(f"QA database pool is exhausted: {summary}")


def validate_qa_identifier(value: str) -> str:
    """Return one safe Doris database identifier or raise ``ValueError``."""
    database = str(value or "").strip()
    if not _DATABASE_IDENTIFIER.fullmatch(database):
        raise ValueError(f"invalid Doris database identifier: {value!r}")
    return database


def _quoted_identifier(value: str) -> str:
    return f"`{validate_qa_identifier(value)}`"


def _quoted_object_identifier(value: str) -> str:
    identifier = str(value or "").strip()
    if not _OBJECT_IDENTIFIER.fullmatch(identifier):
        raise ArtifactFormatError(
            f"unsafe Doris object identifier in QA slot: {value!r}"
        )
    return f"`{identifier}`"


def get_qa_connection(database: str = "information_schema"):
    """Open an autocommit Doris connection using the restricted QA user."""
    return pymysql.connect(
        host=DORIS_HOST,
        port=DORIS_PORT,
        user=DORIS_QA_USER,
        database=validate_qa_identifier(database),
        charset="utf8mb4",
        autocommit=True,
    )


def _query_all(connection, sql: str, params=None) -> list[tuple]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        return list(cursor.fetchall())
    finally:
        cursor.close()


def _invalid_inspection(
    project: str,
    database: str,
    objects: tuple[tuple[str, str], ...],
    diagnostic: str,
) -> QaSlotInspection:
    return QaSlotInspection(
        project=project,
        database=database,
        availability="invalid",
        ownership=None,
        diagnostic=diagnostic,
        objects=objects,
    )


def _normalized_claimed_at(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ")
    return str(value or "").strip()


def _ownership_from_row(row: tuple) -> QaSlotOwnership:
    if len(row) != len(MARKER_COLUMNS) + 1:
        raise ValueError("marker query returned an unexpected column count")
    values = dict(zip(MARKER_COLUMNS, row[:-1]))
    if values["format_version"] != MARKER_FORMAT_VERSION:
        raise ValueError(
            f"marker format_version must be {MARKER_FORMAT_VERSION}"
        )
    if values["marker_key"] != "current":
        raise ValueError("marker_key must be current")
    for field in (
        "project",
        "run_id",
        "execution_id",
        "qa_database",
        "plan_fingerprint",
        "workspace_fingerprint",
    ):
        if not isinstance(values[field], str) or not values[field].strip():
            raise ValueError(f"marker {field} must be a non-empty string")
    for field in ("plan_fingerprint", "workspace_fingerprint"):
        if not _FINGERPRINT_RE.fullmatch(values[field]):
            raise ValueError(f"marker {field} is invalid")
    claimed_at = _normalized_claimed_at(values["claimed_at"])
    if not claimed_at:
        raise ValueError("marker claimed_at is empty")
    try:
        claimed_at_epoch = int(row[-1])
    except (TypeError, ValueError) as exc:
        raise ValueError("marker claimed_at epoch is invalid") from exc
    return QaSlotOwnership(
        format_version=values["format_version"],
        project=values["project"],
        run_id=values["run_id"],
        execution_id=values["execution_id"],
        qa_database=values["qa_database"],
        plan_fingerprint=values["plan_fingerprint"],
        workspace_fingerprint=values["workspace_fingerprint"],
        claimed_at=claimed_at,
        claimed_at_epoch=claimed_at_epoch,
    )


def inspect_qa_slot(
    project: str,
    database: str,
    *,
    connection=None,
) -> QaSlotInspection:
    """Inspect one configured slot without mutating any Doris object."""
    database = validate_qa_identifier(database)
    owns_connection = connection is None
    conn = connection or get_qa_connection()
    try:
        raw_objects = _query_all(
            conn,
            f"SHOW FULL TABLES FROM {_quoted_identifier(database)}",
        )
        objects = tuple((str(row[0]), str(row[1])) for row in raw_objects)
        marker_objects = [
            item
            for item in objects
            if item[0].casefold() == EXECUTION_MARKER_TABLE.casefold()
        ]
        if not marker_objects:
            if not objects:
                return QaSlotInspection(
                    project, database, "free", None, None, objects
                )
            return _invalid_inspection(
                project,
                database,
                objects,
                "non-empty QA database has no ownership marker",
            )
        if len(marker_objects) != 1:
            return _invalid_inspection(
                project,
                database,
                objects,
                "QA database has duplicate ownership marker objects",
            )

        raw_columns = _query_all(
            conn,
            "SHOW COLUMNS FROM "
            f"{_quoted_identifier(database)}."
            f"{_quoted_identifier(EXECUTION_MARKER_TABLE)}",
        )
        columns = tuple(str(row[0]).casefold() for row in raw_columns)
        if columns == _LEGACY_MARKER_COLUMNS:
            return QaSlotInspection(
                project,
                database,
                "legacy",
                None,
                "legacy ownership marker schema",
                objects,
            )
        if columns != MARKER_COLUMNS:
            return _invalid_inspection(
                project,
                database,
                objects,
                "ownership marker schema does not match the current format",
            )

        select_columns = ", ".join(
            _quoted_identifier(column) for column in MARKER_COLUMNS
        )
        rows = _query_all(
            conn,
            f"SELECT {select_columns}, UNIX_TIMESTAMP(claimed_at) "
            f"FROM {_quoted_identifier(database)}."
            f"{_quoted_identifier(EXECUTION_MARKER_TABLE)}",
        )
        if len(rows) != 1:
            return _invalid_inspection(
                project,
                database,
                objects,
                "ownership marker must contain exactly one row",
            )
        try:
            ownership = _ownership_from_row(rows[0])
        except ValueError as exc:
            return _invalid_inspection(project, database, objects, str(exc))
        if ownership.project != project:
            return _invalid_inspection(
                project,
                database,
                objects,
                "marker project does not match configured project",
            )
        if ownership.qa_database != database:
            return _invalid_inspection(
                project,
                database,
                objects,
                "marker qa_database does not match physical database",
            )
        return QaSlotInspection(
            project, database, "claimed", ownership, None, objects
        )
    finally:
        if owns_connection:
            conn.close()


def require_slot_ownership(
    *,
    project: str,
    run_id: str,
    execution_id: str,
    database: str,
    plan_fingerprint: str,
    workspace_fingerprint: str,
    connection=None,
) -> QaSlotOwnership:
    """Require the marker in one slot to match every expected owner field."""
    inspection = inspect_qa_slot(project, database, connection=connection)
    if inspection.availability != "claimed" or inspection.ownership is None:
        raise ArtifactFormatError(
            f"QA slot {database} is not claimed: "
            f"{inspection.availability} ({inspection.diagnostic or 'no owner'})"
        )
    ownership = inspection.ownership
    expected = {
        "project": project,
        "run_id": run_id,
        "execution_id": execution_id,
        "qa_database": database,
        "plan_fingerprint": plan_fingerprint,
        "workspace_fingerprint": workspace_fingerprint,
    }
    for field, expected_value in expected.items():
        actual = getattr(ownership, field)
        if actual != expected_value:
            raise ArtifactFormatError(
                f"QA slot ownership {field} mismatch: "
                f"expected {expected_value!r}, got {actual!r}"
            )
    return ownership


def _rotated_pool(pool: tuple[str, ...], execution_id: str) -> tuple[str, ...]:
    if not pool:
        return ()
    digest = hashlib.sha256(execution_id.encode("utf-8")).digest()
    start = int.from_bytes(digest[:8], "big") % len(pool)
    return pool[start:] + pool[:start]


def _marker_table_exists_error(exc: Exception) -> bool:
    code = exc.args[0] if getattr(exc, "args", ()) else None
    if code == 1050:
        return True
    message = " ".join(str(value) for value in getattr(exc, "args", ()))
    normalized = message.casefold()
    return EXECUTION_MARKER_TABLE.casefold() in normalized and (
        "already exists" in normalized or "table exists" in normalized
    )


def _marker_create_sql() -> str:
    return f"""\
CREATE TABLE {_quoted_identifier(EXECUTION_MARKER_TABLE)} (
    format_version TINYINT NOT NULL,
    marker_key VARCHAR(32) NOT NULL,
    project VARCHAR(128) NOT NULL,
    run_id VARCHAR(255) NOT NULL,
    execution_id VARCHAR(64) NOT NULL,
    qa_database VARCHAR(128) NOT NULL,
    plan_fingerprint VARCHAR(80) NOT NULL,
    workspace_fingerprint VARCHAR(80) NOT NULL,
    claimed_at DATETIME NOT NULL
) ENGINE=OLAP
UNIQUE KEY(format_version, marker_key)
DISTRIBUTED BY HASH(format_version, marker_key) BUCKETS 1
PROPERTIES ("replication_num" = "1")"""


def _try_claim_slot(
    database: str,
    *,
    project: str,
    run_id: str,
    execution_id: str,
    plan_fingerprint: str,
    workspace_fingerprint: str,
) -> QaSlotOwnership | None:
    """Atomically create and populate one marker; ``None`` means race lost."""
    database = validate_qa_identifier(database)
    connection = get_qa_connection(database)
    try:
        cursor = connection.cursor()
        try:
            try:
                cursor.execute(_marker_create_sql())
            except pymysql.MySQLError as exc:
                if _marker_table_exists_error(exc):
                    return None
                raise ArtifactFormatError(
                    "failed to create QA ownership marker in "
                    f"{database}: {exc}"
                ) from exc
            try:
                cursor.execute(
                    f"INSERT INTO {_quoted_identifier(EXECUTION_MARKER_TABLE)} "
                    "(format_version, marker_key, project, run_id, "
                    "execution_id, qa_database, plan_fingerprint, "
                    "workspace_fingerprint, claimed_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                    (
                        MARKER_FORMAT_VERSION,
                        "current",
                        project,
                        run_id,
                        execution_id,
                        database,
                        plan_fingerprint,
                        workspace_fingerprint,
                    ),
                )
            except pymysql.MySQLError as exc:
                raise ArtifactFormatError(
                    f"failed to write QA ownership marker in {database}; "
                    "the marker was retained for manual cleanup: "
                    f"{exc}"
                ) from exc
        finally:
            cursor.close()
        return require_slot_ownership(
            project=project,
            run_id=run_id,
            execution_id=execution_id,
            database=database,
            plan_fingerprint=plan_fingerprint,
            workspace_fingerprint=workspace_fingerprint,
            connection=connection,
        )
    finally:
        connection.close()


def claim_qa_slot(
    *,
    project: str,
    run_id: str,
    execution_id: str,
    pool: tuple[str, ...],
    plan_fingerprint: str,
    workspace_fingerprint: str,
) -> QaSlotOwnership:
    """Claim the first atomically available slot in deterministic rotation."""
    normalized_pool = tuple(validate_qa_identifier(value) for value in pool)
    if not normalized_pool:
        raise ArtifactFormatError("QA database pool must not be empty")
    inspections = []
    for database in _rotated_pool(normalized_pool, execution_id):
        inspection = inspect_qa_slot(project, database)
        if inspection.availability != "free":
            inspections.append(inspection)
            continue
        owner = _try_claim_slot(
            database,
            project=project,
            run_id=run_id,
            execution_id=execution_id,
            plan_fingerprint=plan_fingerprint,
            workspace_fingerprint=workspace_fingerprint,
        )
        if owner is not None:
            return owner
        inspections.append(inspect_qa_slot(project, database))
    raise QaPoolExhaustedError(inspections)


def select_cleanup_slots(
    inspections: list[QaSlotInspection],
    *,
    project: str | None,
    run_id: str | None,
    execution_id: str | None,
    database: str | None,
    cutoff_epoch: int | None,
) -> list[QaSlotInspection]:
    """Select cleanup targets using AND semantics and fail-closed states."""
    database_key = database.casefold() if database else None
    selected = []
    for inspection in inspections:
        if project is not None and inspection.project != project:
            continue
        if (
            database_key is not None
            and inspection.database.casefold() != database_key
        ):
            continue
        if inspection.availability in {"legacy", "invalid"}:
            if (
                database_key is not None
                and run_id is None
                and execution_id is None
                and cutoff_epoch is None
            ):
                selected.append(inspection)
            continue
        if inspection.availability != "claimed":
            continue
        ownership = inspection.ownership
        if ownership is None:
            continue
        if run_id is not None and ownership.run_id != run_id:
            continue
        if execution_id is not None and ownership.execution_id != execution_id:
            continue
        if (
            cutoff_epoch is not None
            and ownership.claimed_at_epoch > cutoff_epoch
        ):
            continue
        selected.append(inspection)
    return selected


def _drop_qa_object(
    connection,
    *,
    database: str,
    object_name: str,
    object_type: str,
) -> None:
    normalized_type = object_type.strip().casefold()
    if normalized_type == "view":
        kind = "VIEW"
    elif normalized_type == "base table":
        kind = "TABLE"
    else:
        raise ArtifactFormatError(
            f"unsupported QA object type for {object_name}: {object_type}"
        )
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"DROP {kind} {_quoted_identifier(database)}."
            f"{_quoted_object_identifier(object_name)}"
        )
    finally:
        cursor.close()


def release_qa_slot(
    inspection: QaSlotInspection,
    *,
    configured_pool: tuple[str, ...],
    protected_databases: set[str],
) -> dict:
    """Release one selected slot, deleting its ownership marker last."""
    database = validate_qa_identifier(inspection.database)
    database_key = database.casefold()
    protected = {value.casefold() for value in protected_databases}
    if database_key in protected:
        raise ArtifactFormatError(
            f"refusing to release protected database {database}"
        )
    pool_keys = {
        validate_qa_identifier(value).casefold() for value in configured_pool
    }
    if database_key not in pool_keys:
        raise ArtifactFormatError(
            f"refusing to release unconfigured QA database {database}"
        )

    connection = get_qa_connection(database)
    try:
        current = inspect_qa_slot(
            inspection.project, database, connection=connection
        )
        if inspection.availability == "claimed":
            if (
                current.availability != "claimed"
                or current.ownership != inspection.ownership
            ):
                raise ArtifactFormatError(
                    f"QA slot {database} ownership changed before cleanup"
                )
        elif current != inspection:
            raise ArtifactFormatError(
                f"QA slot {database} changed before cleanup"
            )

        marker = None
        views = []
        tables = []
        for object_name, object_type in current.objects:
            if object_name.casefold() == EXECUTION_MARKER_TABLE.casefold():
                marker = (object_name, object_type)
            elif object_type.strip().casefold() == "view":
                views.append((object_name, object_type))
            else:
                tables.append((object_name, object_type))
        ordered = sorted(views) + sorted(tables)
        if marker is not None:
            ordered.append(marker)

        dropped = []
        for object_name, object_type in ordered:
            try:
                _drop_qa_object(
                    connection,
                    database=database,
                    object_name=object_name,
                    object_type=object_type,
                )
            except ArtifactFormatError:
                raise
            except Exception as exc:
                raise ArtifactFormatError(
                    f"failed to drop QA object {database}.{object_name}; "
                    "ownership marker was retained when possible: "
                    f"{exc}"
                ) from exc
            dropped.append(object_name)
        return {
            "project": inspection.project,
            "database": database,
            "result": "released",
            "dropped_objects": dropped,
        }
    finally:
        connection.close()


def configured_qa_pool(
    project: str, project_config: Mapping
) -> tuple[str, ...]:
    """Return the validated, ordered QA database pool for one project."""
    verification = project_config.get("verification") or {}
    raw_pool = verification.get("qa_database_pool")
    if raw_pool is None:
        raw_pool = [project_config.get("qa_db")]
    if not isinstance(raw_pool, (list, tuple)) or not raw_pool:
        raise ValueError(
            f"{project}.verification.qa_database_pool must be a non-empty list"
        )

    protected = {
        str(project_config.get("db") or "")
        .strip()
        .casefold(): "production database",
        str(project_config.get("lineage_db") or "")
        .strip()
        .casefold(): "lineage database",
    }
    protected = {key: label for key, label in protected.items() if key}

    pool = []
    seen = set()
    for raw_database in raw_pool:
        database = validate_qa_identifier(raw_database)
        key = database.casefold()
        if key in _SYSTEM_DATABASES:
            raise ValueError(
                f"{project} QA pool cannot contain system database {database}"
            )
        if key in protected:
            raise ValueError(
                f"{project} QA pool cannot contain {protected[key]} {database}"
            )
        if key in seen:
            raise ValueError(
                f"{project} QA pool contains duplicate database {database}"
            )
        seen.add(key)
        pool.append(database)
    return tuple(pool)
