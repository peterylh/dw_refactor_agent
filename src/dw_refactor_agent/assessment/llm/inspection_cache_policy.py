"""Versioned policy metadata for inspection cache and checkpoint payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dw_refactor_agent.assessment.llm.inspection_issues import (
    ISSUE_SCHEMA_VERSION,
    PARSED_CANDIDATE_SCHEMA_VERSION,
)

INSPECTION_CACHE_SCHEMA_VERSION = 2
SUPPORTED_INSPECTION_CACHE_SCHEMA_VERSIONS = frozenset({1, 2})
PARSER_SCHEMA_VERSION = PARSED_CANDIDATE_SCHEMA_VERSION
RECOVERY_VERSION = 1
DECISION_POLICY_VERSION = 0
GOVERNANCE_SCHEMA_VERSION = 0

POLICY_VERSION_FIELDS = (
    "parser_schema_version",
    "issue_schema_version",
    "recovery_version",
    "decision_policy_version",
    "governance_schema_version",
)


class InvalidInspectionCacheError(ValueError):
    """A cache payload cannot be safely interpreted by the current policy."""


def _strict_version(data: dict[str, Any], name: str) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidInspectionCacheError(
            f"inspection cache {name} must be a non-negative integer"
        )
    return value


@dataclass(frozen=True)
class InspectionCachePolicy:
    """Versions and immutable inputs needed to safely replay one result."""

    context_hash: str
    catalog_snapshot_hash: str
    asset_manifest_hash: str
    parser_schema_version: int = PARSER_SCHEMA_VERSION
    issue_schema_version: int = ISSUE_SCHEMA_VERSION
    recovery_version: int = RECOVERY_VERSION
    decision_policy_version: int = DECISION_POLICY_VERSION
    governance_schema_version: int = GOVERNANCE_SCHEMA_VERSION
    schema_version: int = INSPECTION_CACHE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "context_hash": self.context_hash,
            "catalog_snapshot_hash": self.catalog_snapshot_hash,
            "asset_manifest_hash": self.asset_manifest_hash,
            "parser_schema_version": self.parser_schema_version,
            "issue_schema_version": self.issue_schema_version,
            "recovery_version": self.recovery_version,
            "decision_policy_version": self.decision_policy_version,
            "governance_schema_version": self.governance_schema_version,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "InspectionCachePolicy":
        if not isinstance(data, dict):
            raise InvalidInspectionCacheError(
                "inspection cache policy must be an object"
            )
        expected_fields = {
            "schema_version",
            "context_hash",
            "catalog_snapshot_hash",
            "asset_manifest_hash",
            *POLICY_VERSION_FIELDS,
        }
        if set(data) != expected_fields:
            raise InvalidInspectionCacheError(
                "inspection cache policy fields are incomplete or unknown"
            )
        schema_version = _strict_version(data, "schema_version")
        if schema_version not in SUPPORTED_INSPECTION_CACHE_SCHEMA_VERSIONS:
            raise InvalidInspectionCacheError(
                "unsupported inspection cache schema version"
            )
        parser_schema_version = _strict_version(data, "parser_schema_version")
        if parser_schema_version != PARSER_SCHEMA_VERSION:
            raise InvalidInspectionCacheError(
                "unsupported inspection parser schema version"
            )
        issue_schema_version = _strict_version(data, "issue_schema_version")
        if issue_schema_version != ISSUE_SCHEMA_VERSION:
            raise InvalidInspectionCacheError(
                "unsupported inspection issue schema version"
            )
        fingerprints = {}
        for name in (
            "context_hash",
            "catalog_snapshot_hash",
            "asset_manifest_hash",
        ):
            value = data.get(name)
            if not isinstance(value, str):
                raise InvalidInspectionCacheError(
                    f"inspection cache {name} must be a string"
                )
            fingerprints[name] = value
        return cls(
            schema_version=schema_version,
            parser_schema_version=parser_schema_version,
            issue_schema_version=issue_schema_version,
            recovery_version=_strict_version(data, "recovery_version"),
            decision_policy_version=_strict_version(
                data, "decision_policy_version"
            ),
            governance_schema_version=_strict_version(
                data, "governance_schema_version"
            ),
            **fingerprints,
        )

    def matches_inputs(
        self,
        *,
        context_hash: str,
        catalog_snapshot_hash: str,
        asset_manifest_hash: str,
    ) -> bool:
        return (
            self.context_hash == context_hash
            and self.catalog_snapshot_hash == catalog_snapshot_hash
            and self.asset_manifest_hash == asset_manifest_hash
        )

    @property
    def requires_policy_replay(self) -> bool:
        return (
            self.schema_version != INSPECTION_CACHE_SCHEMA_VERSION
            or self.recovery_version != RECOVERY_VERSION
            or self.decision_policy_version != DECISION_POLICY_VERSION
            or self.governance_schema_version != GOVERNANCE_SCHEMA_VERSION
        )


def current_policy_versions() -> dict[str, int]:
    """Return explicit versions for manifests and reproducibility reports."""
    return {
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "issue_schema_version": ISSUE_SCHEMA_VERSION,
        "recovery_version": RECOVERY_VERSION,
        "decision_policy_version": DECISION_POLICY_VERSION,
        "governance_schema_version": GOVERNANCE_SCHEMA_VERSION,
    }
