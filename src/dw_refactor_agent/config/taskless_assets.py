"""Explicit producer declarations for managed tables without task SQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    qualified_table_name,
    table_identity,
    table_identity_match_key,
)


class TasklessAssetConfigError(ValueError):
    """Raised when ``execution.taskless_assets`` is not deterministic."""

    def __init__(self, message: str, *, table: str = ""):
        super().__init__(message)
        self.table = table


@dataclass(frozen=True)
class ExternalTasklessAsset:
    """A project-owned declaration that a table is produced externally."""

    canonical_identity: str
    display_identity: str
    reason: str
    producer: str = "external"

    @property
    def match_key(self) -> tuple[str, str, str]:
        catalog, database, table = self.canonical_identity.split(".", 2)
        return catalog, database, table

    def to_dict(self) -> dict[str, str]:
        return {
            "table": self.display_identity,
            "producer": self.producer,
            "reason": self.reason,
        }


def parse_external_taskless_assets(
    config: Mapping[str, Any],
    *,
    default_catalog: str,
    default_database: str,
) -> tuple[ExternalTasklessAsset, ...]:
    """Parse and validate explicit external producer declarations.

    Fully-qualified identities are required so a declaration cannot silently
    bind to a different database when project defaults change.
    """
    raw_execution = config.get("execution")
    execution = {} if raw_execution is None else raw_execution
    if not isinstance(execution, Mapping):
        raise TasklessAssetConfigError("execution must be a mapping")
    raw_assets = execution.get("taskless_assets", [])
    if not isinstance(raw_assets, list):
        raise TasklessAssetConfigError(
            "execution.taskless_assets must be a list"
        )

    declarations: list[ExternalTasklessAsset] = []
    seen: set[tuple[str, str, str]] = set()
    allowed_keys = {"table", "producer", "reason"}
    for index, raw_asset in enumerate(raw_assets):
        if not isinstance(raw_asset, Mapping):
            raise TasklessAssetConfigError(
                f"execution.taskless_assets[{index}] must be a mapping"
            )
        unknown_keys = sorted(
            str(key) for key in set(raw_asset) - allowed_keys
        )
        if unknown_keys:
            raise TasklessAssetConfigError(
                "execution.taskless_assets"
                f"[{index}] has unsupported fields: {', '.join(unknown_keys)}"
            )
        raw_table = str(raw_asset.get("table") or "").strip()
        normalized_table = canonical_qualified_identifier(raw_table)
        raw_parts = raw_table.replace("`", "").replace('"', "").split(".")
        if (
            len(raw_parts) != 3
            or any(not part.strip() for part in raw_parts)
            or len(normalized_table.split(".")) != 3
        ):
            raise TasklessAssetConfigError(
                "taskless asset table must be fully qualified as "
                "catalog.database.table",
                table=raw_table,
            )
        producer = str(raw_asset.get("producer") or "").strip().casefold()
        if producer != "external":
            raise TasklessAssetConfigError(
                "taskless asset producer must be external",
                table=raw_table,
            )
        reason = str(raw_asset.get("reason") or "").strip()
        if not reason:
            raise TasklessAssetConfigError(
                "taskless asset reason is required",
                table=raw_table,
            )

        catalog, database, table = table_identity(
            normalized_table,
            default_catalog=default_catalog,
            default_db=default_database,
        )
        display_identity = qualified_table_name(catalog, database, table)
        match_key = table_identity_match_key(
            display_identity,
            default_catalog=default_catalog,
            default_db=default_database,
        )
        if match_key in seen:
            raise TasklessAssetConfigError(
                "duplicate taskless asset declaration",
                table=display_identity,
            )
        seen.add(match_key)
        declarations.append(
            ExternalTasklessAsset(
                canonical_identity=".".join(match_key),
                display_identity=display_identity,
                reason=reason,
            )
        )

    return tuple(
        sorted(
            declarations,
            key=lambda declaration: declaration.canonical_identity,
        )
    )
