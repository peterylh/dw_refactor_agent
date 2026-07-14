"""QA database pool configuration and lifecycle helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping

_DATABASE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SYSTEM_DATABASES = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
}


def validate_qa_identifier(value: str) -> str:
    """Return one safe Doris database identifier or raise ``ValueError``."""
    database = str(value or "").strip()
    if not _DATABASE_IDENTIFIER.fullmatch(database):
        raise ValueError(f"invalid Doris database identifier: {value!r}")
    return database


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
