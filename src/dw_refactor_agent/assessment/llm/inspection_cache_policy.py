"""Versioned policy metadata for inspection cache and checkpoint payloads."""

from __future__ import annotations

import math
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Any

from dw_refactor_agent.assessment.llm.inspection_issues import (
    HARD_BLOCK_ISSUE_CODES,
    ISSUE_SCHEMA_VERSION,
    PARSED_CANDIDATE_SCHEMA_VERSION,
)
from dw_refactor_agent.config.model_governance import (
    MODEL_GOVERNANCE_SCHEMA_VERSION,
)

INSPECTION_CACHE_SCHEMA_VERSION = 2
SUPPORTED_INSPECTION_CACHE_SCHEMA_VERSIONS = frozenset({1, 2})
PARSER_SCHEMA_VERSION = PARSED_CANDIDATE_SCHEMA_VERSION
RECOVERY_VERSION = 1
DECISION_POLICY_VERSION = 1
GOVERNANCE_SCHEMA_VERSION = MODEL_GOVERNANCE_SCHEMA_VERSION

REUSE_KIND_ACCEPTED = "accepted"
REUSE_KIND_SEMANTIC_QUARANTINE = "semantic_quarantine"

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
        return bool(self.version_differences())

    def version_differences(self) -> dict[str, tuple[int, int]]:
        """Return prior/current versions that require local re-adjudication."""
        current = {
            "schema_version": INSPECTION_CACHE_SCHEMA_VERSION,
            **current_policy_versions(),
        }
        return {
            name: (int(getattr(self, name)), expected)
            for name, expected in current.items()
            if int(getattr(self, name)) != expected
        }


@dataclass(frozen=True)
class InspectionReuseDecision:
    """Fail-closed decision for replaying one lossless LLM candidate."""

    eligible: bool
    kind: str = ""
    reason: str = ""


def inspection_reuse_decision(
    result: Any,
    *,
    min_confidence: float,
) -> InspectionReuseDecision:
    """Allow accepted or non-retryable semantic candidates, never failures."""
    parsed_candidate = getattr(result, "parsed_candidate", None)
    if parsed_candidate is None:
        return InspectionReuseDecision(
            False, reason="lossless_payload_missing"
        )
    confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    if not math.isfinite(confidence) or confidence < float(min_confidence):
        return InspectionReuseDecision(False, reason="low_confidence")
    issues = tuple(getattr(result, "issues", ()) or ())
    if any(bool(getattr(issue, "retryable", False)) for issue in issues):
        return InspectionReuseDecision(False, reason="retryable_issue")
    if any(
        str(getattr(issue, "origin", ""))
        in {"transport", "parser", "internal"}
        for issue in issues
    ):
        return InspectionReuseDecision(
            False, reason="boundary_or_internal_failure"
        )
    if any(
        str(getattr(issue, "stage", "")) == "propagation" for issue in issues
    ):
        return InspectionReuseDecision(False, reason="unsettled_propagation")
    if any(
        str(getattr(issue, "code", "")) in HARD_BLOCK_ISSUE_CODES
        or str(getattr(issue, "origin", ""))
        in {"deterministic_asset", "deterministic_contract"}
        for issue in issues
    ):
        return InspectionReuseDecision(
            False, reason="deterministic_hard_block"
        )

    status = str(getattr(result, "status", "") or "")
    if status in {"passed", "warning"}:
        return InspectionReuseDecision(True, kind=REUSE_KIND_ACCEPTED)
    if (
        status == "blocked"
        and issues
        and all(
            str(getattr(issue, "origin", "")) == "llm_validation"
            and bool(tuple(getattr(issue, "sections", ()) or ()))
            for issue in issues
        )
    ):
        return InspectionReuseDecision(
            True,
            kind=REUSE_KIND_SEMANTIC_QUARANTINE,
        )
    return InspectionReuseDecision(False, reason="unclassified_blocked_result")


class InspectionReuseStats:
    """Thread-safe cache/checkpoint reuse and policy replay counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lookups: Counter = Counter()
        self._hits: Counter = Counter()
        self._hit_kinds: Counter = Counter()
        self._miss_reasons: Counter = Counter()
        self._policy_replays: Counter = Counter()
        self._policy_replay_count = 0
        self._api_call_count = 0

    def record_lookup(self, source: str) -> None:
        with self._lock:
            self._lookups[source] += 1

    def record_miss(self, source: str, reason: str) -> None:
        with self._lock:
            self._miss_reasons[f"{source}:{reason}"] += 1

    def record_hit(
        self,
        source: str,
        decision: InspectionReuseDecision,
        cache_policy: InspectionCachePolicy,
    ) -> None:
        with self._lock:
            self._hits[source] += 1
            self._hit_kinds[decision.kind] += 1
            version_differences = cache_policy.version_differences()
            if version_differences:
                self._policy_replay_count += 1
            for name in version_differences:
                self._policy_replays[name] += 1

    def record_api_call(self) -> None:
        with self._lock:
            self._api_call_count += 1

    def report(self) -> dict[str, Any]:
        with self._lock:
            lookup_count = sum(self._lookups.values())
            hit_count = sum(self._hits.values())
            return {
                "schema_version": 1,
                "policy_versions": current_policy_versions(),
                "lookup_count": lookup_count,
                "hit_count": hit_count,
                "miss_count": sum(self._miss_reasons.values()),
                "hit_rate": (
                    round(hit_count / lookup_count, 6) if lookup_count else 0.0
                ),
                "api_call_count": self._api_call_count,
                "lookups_by_source": dict(sorted(self._lookups.items())),
                "hits_by_source": dict(sorted(self._hits.items())),
                "hits_by_kind": dict(sorted(self._hit_kinds.items())),
                "misses_by_reason": dict(sorted(self._miss_reasons.items())),
                "adjudication_replay_count": hit_count,
                "policy_replay_count": self._policy_replay_count,
                "policy_replays_by_version": dict(
                    sorted(self._policy_replays.items())
                ),
            }


def current_policy_versions() -> dict[str, int]:
    """Return explicit versions for manifests and reproducibility reports."""
    return {
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "issue_schema_version": ISSUE_SCHEMA_VERSION,
        "recovery_version": RECOVERY_VERSION,
        "decision_policy_version": DECISION_POLICY_VERSION,
        "governance_schema_version": GOVERNANCE_SCHEMA_VERSION,
    }
