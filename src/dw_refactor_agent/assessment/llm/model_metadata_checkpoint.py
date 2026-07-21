"""Resumable MID inspections for long-running cold-start generation."""

from __future__ import annotations

import copy
import csv
import errno
import fcntl
import hashlib
import io
import json
import threading
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dw_refactor_agent.assessment.llm.catalog_proposals import (
    CATALOG_PROPOSAL_SCHEMA_VERSION,
)
from dw_refactor_agent.assessment.llm.inspection_cache_policy import (
    ISSUE_SCHEMA_VERSION,
    PARSER_SCHEMA_VERSION,
    InspectionCachePolicy,
    InvalidInspectionCacheError,
    current_policy_versions,
    inspection_reuse_decision,
)
from dw_refactor_agent.assessment.llm.metadata_flow import MetadataFlowPlan
from dw_refactor_agent.assessment.llm.model_metadata_updates import (
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
    cache_result_digest,
    dict_to_result,
    result_to_cache_dict,
)
from dw_refactor_agent.config import TEXT_ENCODING

MID_LAYERS = {"DWD", "DWS", "DIM"}
CHECKPOINT_MANIFEST_VERSION = 6
RESUMABLE_CHECKPOINT_MANIFEST_VERSIONS = {5, 6}
MAX_CHECKPOINT_VARIANTS_PER_TABLE = 4
MAX_CHECKPOINT_INVALIDATIONS_PER_TABLE = 8
INSPECTION_RESULT_SUFFIX = ".inspection.json"
LLM_LAYER_CLASSIFICATION_REPORT_NAME = "llm_layer_classification.csv"
LLM_LAYER_CLASSIFICATION_FIELDS = (
    "table_name",
    "declared_layer",
    "inferred_layer",
    "table_type",
    "confidence",
    "inspection_status",
)


class GenerateCheckpointLockError(RuntimeError):
    """Raised when another generate run owns the project checkpoint."""


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


def _is_mid_model(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("layer") or "").upper() in MID_LAYERS


class GenerateModelCheckpoint:
    """Persist and resume completed MID inspections outside formal models."""

    def __init__(
        self,
        project: str,
        *,
        project_dir: Path,
        plan: MetadataFlowPlan,
        resume_enabled: bool = True,
        catalog_snapshot_hash: str = "",
        asset_manifest_hash: str = "",
    ) -> None:
        self.project = project
        self.project_dir = Path(project_dir)
        self.plan = plan
        self.catalog_snapshot_hash = str(catalog_snapshot_hash or "")
        self.asset_manifest_hash = str(asset_manifest_hash or "")
        self.run_id = _checkpoint_run_id()
        self.root = self.project_dir / "mid_checkpoints"
        self.manifest_path = self.root / "manifest.json"
        self.lock_path = self.root / ".generate.lock"
        self._lock = threading.RLock()
        self._lock_handle = None
        self._closed = False
        self._acquire_process_lock()
        try:
            self._recover_pending_write()
            previous_manifest = self._load_existing_manifest()
            (
                self._resume_cache,
                preserved_tables,
                preserved_result_names,
                resumed_from_run_id,
            ) = self._prepare_resume_state(
                previous_manifest,
                resume_enabled=resume_enabled,
            )
            self._prune_previous_files(preserved_result_names)
            self._manifest: dict[str, Any] = {
                "version": CHECKPOINT_MANIFEST_VERSION,
                "project": project,
                "mode": "generate",
                "run_id": self.run_id,
                "resumed_from_run_id": resumed_from_run_id,
                "resume_enabled": bool(resume_enabled),
                **current_policy_versions(),
                "catalog_snapshot_hash": self.catalog_snapshot_hash,
                "asset_manifest_hash": self.asset_manifest_hash,
                "status": "running",
                "published": False,
                "catalog_proposal_audit": {
                    "schema_version": CATALOG_PROPOSAL_SCHEMA_VERSION,
                    "catalog_snapshot_hash": self.catalog_snapshot_hash,
                    "proposals": [],
                    "proposal_count": 0,
                    "conflicts": [],
                    "conflict_count": 0,
                    "generated_at": None,
                },
                "created_at": _utc_timestamp(),
                "updated_at": _utc_timestamp(),
                "table_count": sum(
                    1
                    for metadata in plan.base_model_metadata.values()
                    if _is_mid_model(metadata)
                ),
                "tables": preserved_tables,
            }
            self._refresh_manifest_counts(self._manifest)
            self._write_manifest()
        except BaseException:
            self.close()
            raise

    def _acquire_process_lock(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+", encoding=TEXT_ENCODING)
        try:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except OSError as exc:
            handle.close()
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            raise GenerateCheckpointLockError(
                "another generate --llm run is active for project "
                f"{self.project}"
            ) from exc
        self._lock_handle = handle

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        handle = self._lock_handle
        self._lock_handle = None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    @classmethod
    def recover_existing(cls, project_dir: Path) -> dict[str, Any]:
        """Recover one journaled write without starting a new generation."""
        checkpoint = cls.__new__(cls)
        checkpoint.project_dir = Path(project_dir)
        checkpoint.project = checkpoint.project_dir.name
        checkpoint.root = checkpoint.project_dir / "mid_checkpoints"
        checkpoint.manifest_path = checkpoint.root / "manifest.json"
        checkpoint.lock_path = checkpoint.root / ".generate.lock"
        checkpoint._lock = threading.RLock()
        checkpoint._lock_handle = None
        checkpoint._closed = False
        checkpoint._acquire_process_lock()
        try:
            checkpoint._recover_pending_write()
            return checkpoint._load_existing_manifest()
        finally:
            checkpoint.close()

    def resume_cache(self) -> dict[str, Any]:
        """Return validated inspection variants available to this run."""
        with self._lock:
            return copy.deepcopy(self._resume_cache)

    def _mid_table_names(self) -> set[str]:
        return {
            table_name
            for table_name, metadata in self.plan.base_model_metadata.items()
            if _is_mid_model(metadata)
        }

    def _prepare_resume_state(
        self,
        manifest: dict[str, Any],
        *,
        resume_enabled: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], set[str], str | None]:
        if not self._manifest_is_resumable(manifest, resume_enabled):
            return {}, {}, set(), None

        resume_cache: dict[str, Any] = {}
        preserved_tables: dict[str, Any] = {}
        preserved_result_names: set[str] = set()
        tables = manifest.get("tables") or {}
        for table_name, raw_entry in tables.items():
            if table_name not in self._mid_table_names():
                continue
            if not isinstance(raw_entry, dict):
                continue
            (
                variants,
                rejected_hashes,
                rejected_reasons,
            ) = self._validated_resume_variants(
                table_name,
                raw_entry.get("inspection_variants"),
            )
            invalidated_hashes = self._normalized_context_hashes(
                raw_entry.get("invalidated_context_hashes")
            )
            invalidation_reasons = self._normalized_invalidation_reasons(
                raw_entry.get("resume_invalidation_reasons")
            )
            for context_hash in rejected_hashes:
                if context_hash not in invalidated_hashes:
                    invalidated_hashes.append(context_hash)
                invalidation_reasons.setdefault(
                    context_hash,
                    rejected_reasons.get(
                        context_hash,
                        "checkpoint_variant_invalid",
                    ),
                )
            for context_hash in variants:
                with suppress(ValueError):
                    invalidated_hashes.remove(context_hash)
                invalidation_reasons.pop(context_hash, None)
            invalidated_hashes = invalidated_hashes[
                -MAX_CHECKPOINT_INVALIDATIONS_PER_TABLE:
            ]
            invalidation_reasons = {
                context_hash: invalidation_reasons.get(
                    context_hash,
                    "previously_invalidated",
                )
                for context_hash in invalidated_hashes
            }
            if not variants and not invalidated_hashes:
                continue
            variants = dict(
                list(variants.items())[-MAX_CHECKPOINT_VARIANTS_PER_TABLE:]
            )
            cache_variants = {
                context_hash: {
                    "result": item["result"],
                    "content_sha256": cache_result_digest(item["result"]),
                }
                for context_hash, item in variants.items()
            }
            resume_cache[table_name] = {
                "variants": cache_variants,
                "invalid_context_hashes": invalidated_hashes,
                "invalidation_reasons": invalidation_reasons,
            }
            variant_metadata = {
                context_hash: item["metadata"]
                for context_hash, item in variants.items()
            }
            active_context_hash = str(
                raw_entry.get("active_context_hash") or ""
            )
            if active_context_hash not in variant_metadata:
                active_context_hash = next(
                    reversed(list(variant_metadata)),
                    "",
                )
            preserved_result_names.update(
                str(item["metadata"]["result_name"])
                for item in variants.values()
            )
            preserved_tables[table_name] = {
                "target_path": str(self._target_path(table_name)),
                "stage": "resume_candidate",
                "updated_at": _utc_timestamp(),
                "revision": int(raw_entry.get("revision") or 0),
                "inspection_variants": variant_metadata,
                "invalidated_context_hashes": invalidated_hashes,
                "resume_invalidation_reasons": invalidation_reasons,
                "resumed_context_hashes": [],
                "active_context_hash": active_context_hash,
            }
        source_run_id = str(manifest.get("run_id") or "") or None
        if not resume_cache:
            source_run_id = None
        return (
            resume_cache,
            preserved_tables,
            preserved_result_names,
            source_run_id,
        )

    def _manifest_is_resumable(
        self,
        manifest: dict[str, Any],
        resume_enabled: bool,
    ) -> bool:
        versions = current_policy_versions()
        policy_versions_present = all(
            isinstance(manifest.get(name), int)
            and not isinstance(manifest.get(name), bool)
            and manifest.get(name) >= 0
            for name in versions
        )
        return bool(
            resume_enabled
            and manifest.get("version")
            in RESUMABLE_CHECKPOINT_MANIFEST_VERSIONS
            and manifest.get("project") == self.project
            and manifest.get("mode") == "generate"
            and isinstance(manifest.get("tables"), dict)
            and policy_versions_present
            and manifest.get("parser_schema_version") == PARSER_SCHEMA_VERSION
            and manifest.get("issue_schema_version") == ISSUE_SCHEMA_VERSION
            and manifest.get("catalog_snapshot_hash")
            == self.catalog_snapshot_hash
            and manifest.get("asset_manifest_hash") == self.asset_manifest_hash
        )

    def _validated_resume_variants(
        self,
        table_name: str,
        raw_variants: Any,
    ) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
        if not isinstance(raw_variants, dict):
            return {}, [], {}
        variants: dict[str, dict[str, Any]] = {}
        rejected_hashes: list[str] = []
        rejected_reasons: dict[str, str] = {}
        for context_hash, raw_metadata in raw_variants.items():
            context_hash = str(context_hash or "")
            if not context_hash:
                continue
            rejected_hashes.append(context_hash)
            rejected_reasons[context_hash] = "checkpoint_variant_invalid"
            if not isinstance(raw_metadata, dict):
                rejected_reasons[context_hash] = "variant_metadata_invalid"
                continue
            if raw_metadata.get("resume_eligible") is False:
                rejected_reasons[context_hash] = str(
                    raw_metadata.get("invalidation_reason")
                    or "legacy_marked_non_resumable"
                )
                continue
            result_name = str(raw_metadata.get("result_name") or "")
            expected_digest = str(raw_metadata.get("content_sha256") or "")
            result_path = self._safe_root_file(result_name)
            if (
                result_path is None
                or not result_name.endswith(INSPECTION_RESULT_SUFFIX)
                or not expected_digest
                or self._file_digest(result_path) != expected_digest
            ):
                rejected_reasons[context_hash] = "sidecar_missing_or_corrupt"
                continue
            try:
                payload = json.loads(
                    result_path.read_text(encoding=TEXT_ENCODING)
                )
            except (OSError, ValueError):
                rejected_reasons[context_hash] = "sidecar_json_invalid"
                continue
            if not isinstance(payload, dict):
                rejected_reasons[context_hash] = "sidecar_json_invalid"
                continue
            try:
                cache_policy = InspectionCachePolicy.from_dict(
                    payload.get("cache_policy")
                )
                if not cache_policy.matches_inputs(
                    context_hash=context_hash,
                    catalog_snapshot_hash=self.catalog_snapshot_hash,
                    asset_manifest_hash=self.asset_manifest_hash,
                ):
                    rejected_reasons[context_hash] = (
                        "input_fingerprint_changed"
                    )
                    continue
                result = dict_to_result(
                    payload,
                    table_name=table_name,
                    declared_layer=str(payload.get("declared_layer") or ""),
                )
            except (
                InvalidInspectionCacheError,
                TypeError,
                ValueError,
            ):
                rejected_reasons[context_hash] = "payload_or_policy_invalid"
                continue
            if (
                result.table_name != table_name
                or result.context_hash != context_hash
                or result.catalog_snapshot_hash != self.catalog_snapshot_hash
                or result.asset_manifest_hash != self.asset_manifest_hash
                or result.parsed_candidate is None
                or result.parsed_candidate.table_name != table_name
                or (
                    result.raw_response is not None
                    and (
                        result.raw_response.table_name != table_name
                        or result.parsed_candidate.raw_response_hash
                        != result.raw_response.content_hash
                    )
                )
            ):
                rejected_reasons[context_hash] = "payload_identity_mismatch"
                continue
            reuse = inspection_reuse_decision(
                result,
                min_confidence=(
                    self.plan.resolution_policy.min_llm_confidence
                ),
            )
            if not reuse.eligible:
                rejected_reasons[context_hash] = reuse.reason
                continue
            metadata = dict(raw_metadata)
            metadata.update(
                {
                    "result_name": result_name,
                    "content_sha256": expected_digest,
                    "inspection_status": result.status,
                    "confidence": result.confidence,
                    "resume_eligible": True,
                    "reuse_kind": reuse.kind,
                    "invalidation_reason": "",
                }
            )
            variants[context_hash] = {
                "result": payload,
                "metadata": metadata,
            }
            rejected_hashes.remove(context_hash)
            rejected_reasons.pop(context_hash, None)
        return variants, rejected_hashes, rejected_reasons

    @staticmethod
    def _normalized_context_hashes(raw_hashes: Any) -> list[str]:
        if not isinstance(raw_hashes, list):
            return []
        hashes: list[str] = []
        for raw_hash in raw_hashes:
            context_hash = str(raw_hash or "")
            if context_hash and context_hash not in hashes:
                hashes.append(context_hash)
        return hashes

    @staticmethod
    def _normalized_invalidation_reasons(raw_reasons: Any) -> dict[str, str]:
        if not isinstance(raw_reasons, dict):
            return {}
        return {
            str(context_hash): str(reason or "previously_invalidated")
            for context_hash, reason in raw_reasons.items()
            if str(context_hash or "")
        }

    def _prune_previous_files(self, preserved_result_names: set[str]) -> None:
        if not self.root.exists():
            return
        for path in self.root.glob("*.yaml"):
            path.unlink()
        layer_report_path = self.root / LLM_LAYER_CLASSIFICATION_REPORT_NAME
        if layer_report_path.exists():
            layer_report_path.unlink()
        for path in self.root.glob(f"*{INSPECTION_RESULT_SUFFIX}"):
            if path.name not in preserved_result_names:
                path.unlink()
        for path in self.root.glob(".*.pending"):
            path.unlink()

    def _load_existing_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}
        try:
            payload = json.loads(
                self.manifest_path.read_text(encoding=TEXT_ENCODING)
            )
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staged_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            staged_path.write_text(content, encoding=TEXT_ENCODING)
            staged_path.replace(path)
        finally:
            if staged_path.exists():
                staged_path.unlink()

    @staticmethod
    def _content_digest(content: str) -> str:
        return hashlib.sha256(content.encode(TEXT_ENCODING)).hexdigest()

    @classmethod
    def _file_digest(cls, path: Path) -> str | None:
        try:
            return cls._content_digest(path.read_text(encoding=TEXT_ENCODING))
        except OSError:
            return None

    def _safe_root_file(self, name: str) -> Path | None:
        if not name or Path(name).name != name:
            return None
        return self.root / name

    def _write_manifest(self) -> None:
        self._manifest["updated_at"] = _utc_timestamp()
        self._atomic_write(
            self.manifest_path,
            json.dumps(self._manifest, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _refresh_manifest_counts(manifest: dict[str, Any]) -> None:
        tables = manifest.get("tables")
        if not isinstance(tables, dict):
            tables = {}
            manifest["tables"] = tables
        active_entries = [
            item
            for item in tables.values()
            if isinstance(item, dict)
            and item.get("stage") != "resume_candidate"
        ]
        manifest.pop("checkpoint_model_count", None)
        manifest["processed_table_count"] = len(active_entries)
        manifest["inspected_table_count"] = sum(
            1
            for item in active_entries
            if item.get("inspection_status") is not None
        )
        manifest["resume_candidate_table_count"] = sum(
            1
            for item in tables.values()
            if isinstance(item, dict) and item.get("inspection_variants")
        )
        manifest["resume_candidate_variant_count"] = sum(
            len(item.get("inspection_variants") or {})
            for item in tables.values()
            if isinstance(item, dict)
        )
        manifest["resumed_table_count"] = sum(
            1
            for item in tables.values()
            if isinstance(item, dict) and item.get("resumed_context_hashes")
        )
        manifest["resumed_variant_count"] = sum(
            len(item.get("resumed_context_hashes") or [])
            for item in tables.values()
            if isinstance(item, dict)
        )
        manifest["invalidated_variant_count"] = sum(
            len(item.get("invalidated_context_hashes") or [])
            for item in tables.values()
            if isinstance(item, dict)
        )
        reuse_kind_counts: dict[str, int] = {}
        invalidation_reason_counts: dict[str, int] = {}
        for item in tables.values():
            if not isinstance(item, dict):
                continue
            for variant in (item.get("inspection_variants") or {}).values():
                if not isinstance(variant, dict) or not variant.get(
                    "resume_eligible"
                ):
                    continue
                kind = str(variant.get("reuse_kind") or "accepted")
                reuse_kind_counts[kind] = reuse_kind_counts.get(kind, 0) + 1
            for reason in (
                item.get("resume_invalidation_reasons") or {}
            ).values():
                reason = str(reason or "previously_invalidated")
                invalidation_reason_counts[reason] = (
                    invalidation_reason_counts.get(reason, 0) + 1
                )
        manifest["resume_candidate_kind_counts"] = dict(
            sorted(reuse_kind_counts.items())
        )
        manifest["invalidation_reason_counts"] = dict(
            sorted(invalidation_reason_counts.items())
        )

    def _pending_file_specs(
        self,
        pending: dict[str, Any],
        table_name: str,
    ) -> list[dict[str, str]]:
        raw_files = pending.get("files")
        if isinstance(raw_files, list):
            return [item for item in raw_files if isinstance(item, dict)]
        return [
            {
                "staged_name": str(pending.get("staged_name") or ""),
                "target_name": f"{table_name}.yaml",
                "content_sha256": str(pending.get("content_sha256") or ""),
            }
        ]

    def _recover_pending_write(self) -> None:
        manifest = self._load_existing_manifest()
        pending = manifest.get("pending_write")
        if not isinstance(pending, dict):
            return
        table_name = str(pending.get("table") or "")
        entry = pending.get("entry")
        file_specs = self._pending_file_specs(pending, table_name)
        recoverable_specs = []
        for spec in file_specs:
            target_name = str(spec.get("target_name") or "")
            if Path(target_name).suffix.lower() != ".yaml":
                recoverable_specs.append(spec)
                continue
            for name in (
                str(spec.get("staged_name") or ""),
                target_name,
            ):
                legacy_path = self._safe_root_file(name)
                if legacy_path is not None and legacy_path.exists():
                    legacy_path.unlink()

        files_recovered = bool(recoverable_specs)
        for spec in recoverable_specs:
            staged_path = self._safe_root_file(
                str(spec.get("staged_name") or "")
            )
            target_path = self._safe_root_file(
                str(spec.get("target_name") or "")
            )
            expected_digest = str(spec.get("content_sha256") or "")
            if target_path is None or not expected_digest:
                files_recovered = False
                continue
            if self._file_digest(target_path) == expected_digest:
                continue
            if (
                staged_path is not None
                and self._file_digest(staged_path) == expected_digest
            ):
                staged_path.replace(target_path)
                continue
            files_recovered = False
            if staged_path is not None and staged_path.exists():
                staged_path.unlink()
        if table_name and isinstance(entry, dict) and files_recovered:
            tables = manifest.setdefault("tables", {})
            if isinstance(tables, dict):
                tables[table_name] = entry
        manifest.pop("pending_write", None)
        self._refresh_manifest_counts(manifest)
        self._manifest = manifest
        self._write_manifest()

    def recover_pending_write(self) -> None:
        """Reconcile a journaled table write after an interrupted update."""
        with self._lock:
            self._recover_pending_write()

    def _target_path(self, table_name: str) -> Path:
        target_path = self.plan.write_targets.model_paths.get(table_name)
        if target_path is not None:
            return Path(target_path)
        return self.project_dir / "mid" / "models" / f"{table_name}.yaml"

    def _inspection_result_name(
        self,
        table_name: str,
        context_hash: str,
    ) -> str:
        if Path(table_name).name != table_name:
            raise ValueError(f"invalid checkpoint table name: {table_name!r}")
        return f"{table_name}.{context_hash}{INSPECTION_RESULT_SUFFIX}"

    def _stage_file(
        self,
        target_path: Path,
        content: str,
    ) -> tuple[Path, dict[str, str]]:
        staged_path = target_path.with_name(
            f".{target_path.name}.{uuid4().hex}.pending"
        )
        staged_path.write_text(content, encoding=TEXT_ENCODING)
        return staged_path, {
            "staged_name": staged_path.name,
            "target_name": target_path.name,
            "content_sha256": self._content_digest(content),
        }

    def _write_inspection_result(
        self,
        inspection_result: TableInspectResult,
    ) -> None:
        table_name = inspection_result.table_name
        previous = self._manifest["tables"].get(table_name) or {}
        entry = {
            "target_path": str(self._target_path(table_name)),
            "stage": "inspected",
            "updated_at": _utc_timestamp(),
            "revision": int(previous.get("revision") or 0) + 1,
            "inspection_variants": dict(
                previous.get("inspection_variants") or {}
            ),
            "invalidated_context_hashes": self._normalized_context_hashes(
                previous.get("invalidated_context_hashes")
            ),
            "resume_invalidation_reasons": (
                self._normalized_invalidation_reasons(
                    previous.get("resume_invalidation_reasons")
                )
            ),
            "resumed_context_hashes": list(
                previous.get("resumed_context_hashes") or []
            ),
            "active_context_hash": str(
                previous.get("active_context_hash") or ""
            ),
            "inspection_status": inspection_result.status,
            "confidence": inspection_result.confidence,
            "retry_count": inspection_result.retry_count,
            "validation": dict(inspection_result.validation or {}),
        }
        staged_files: list[tuple[Path, Path, dict[str, str]]] = []
        context_hash = str(inspection_result.context_hash or "")
        if context_hash:
            entry["active_context_hash"] = context_hash
            result_name = self._inspection_result_name(
                table_name,
                context_hash,
            )
            result_path = self.root / result_name
            reuse = inspection_reuse_decision(
                inspection_result,
                min_confidence=(
                    self.plan.resolution_policy.min_llm_confidence
                ),
            )
            inspection_result.resume_eligible = reuse.eligible
            rendered_result = json.dumps(
                result_to_cache_dict(inspection_result),
                ensure_ascii=False,
                indent=2,
            )
            staged_path, file_spec = self._stage_file(
                result_path,
                rendered_result,
            )
            staged_files.append((staged_path, result_path, file_spec))
            entry["inspection_variants"][context_hash] = {
                "result_name": result_name,
                "content_sha256": file_spec["content_sha256"],
                "inspection_status": inspection_result.status,
                "confidence": inspection_result.confidence,
                "resume_eligible": reuse.eligible,
                "reuse_kind": reuse.kind,
                "invalidation_reason": reuse.reason,
                "updated_at": _utc_timestamp(),
            }
            invalidated_hashes = entry["invalidated_context_hashes"]
            invalidation_reasons = entry["resume_invalidation_reasons"]
            if reuse.eligible:
                with suppress(ValueError):
                    invalidated_hashes.remove(context_hash)
                invalidation_reasons.pop(context_hash, None)
            elif context_hash not in invalidated_hashes:
                invalidated_hashes.append(context_hash)
                del invalidated_hashes[
                    :-MAX_CHECKPOINT_INVALIDATIONS_PER_TABLE
                ]
                invalidation_reasons[context_hash] = reuse.reason
            entry["resume_invalidation_reasons"] = {
                cache_hash: invalidation_reasons.get(
                    cache_hash,
                    "previously_invalidated",
                )
                for cache_hash in invalidated_hashes
            }
            while (
                len(entry["inspection_variants"])
                > MAX_CHECKPOINT_VARIANTS_PER_TABLE
            ):
                entry["inspection_variants"].pop(
                    next(iter(entry["inspection_variants"]))
                )
            if inspection_result.reuse_source == "checkpoint":
                resumed_hashes = entry["resumed_context_hashes"]
                if context_hash not in resumed_hashes:
                    resumed_hashes.append(context_hash)

        if staged_files:
            first_file_spec = staged_files[0][2]
            self._manifest["pending_write"] = {
                "table": table_name,
                "entry": entry,
                "staged_name": first_file_spec["staged_name"],
                "content_sha256": first_file_spec["content_sha256"],
                "files": [spec for _, _, spec in staged_files],
            }
            try:
                self._write_manifest()
            except BaseException:
                self._manifest.pop("pending_write", None)
                for staged_path, _, _ in staged_files:
                    with suppress(OSError):
                        staged_path.unlink()
                raise
            for staged_path, target_path, _ in staged_files:
                staged_path.replace(target_path)

        self._manifest["tables"][table_name] = entry
        self._manifest.pop("pending_write", None)
        self._refresh_manifest_counts(self._manifest)
        self._write_manifest()

    def _processed_inspection_result(
        self,
        result: TableInspectResult,
    ) -> TableInspectResult:
        result_copy = copy.deepcopy(result)
        table_name = result_copy.table_name
        existing = dict(self.plan.base_model_metadata.get(table_name) or {})
        update_model_yaml(
            self.project,
            result_copy,
            dry_run=True,
            write_scope=self.plan.write_scope,
            existing_model=existing,
            path=self._target_path(table_name),
            resolution_policy=self.plan.resolution_policy,
            include_model_metadata=True,
        )
        return result_copy

    def write_inspection_result(self, result: TableInspectResult) -> None:
        """Persist one processed inspection result for cross-run recovery."""
        with self._lock:
            self._write_inspection_result(
                self._processed_inspection_result(result)
            )

    def _successful_layer_classifications(
        self,
        inspection_results: list[TableInspectResult],
    ) -> list[dict[str, Any]]:
        latest_by_table: dict[str, TableInspectResult] = {}
        for result in inspection_results:
            if not isinstance(result, TableInspectResult):
                continue
            processed = self._processed_inspection_result(result)
            table_name = str(processed.table_name or "").strip()
            if table_name:
                latest_by_table[table_name] = processed

        rows = []
        for table_name, result in sorted(latest_by_table.items()):
            if result.status != "passed":
                continue
            inferred_layer = str(result.inferred_layer or "").upper()
            if not inferred_layer:
                continue
            rows.append(
                {
                    "table_name": table_name,
                    "declared_layer": str(result.declared_layer or "").upper(),
                    "inferred_layer": inferred_layer,
                    "table_type": str(result.table_type or "").lower(),
                    "confidence": result.confidence,
                    "inspection_status": "passed",
                }
            )
        return rows

    def write_layer_classification_report(
        self,
        inspection_results: list[TableInspectResult],
    ) -> Path:
        """Write one CSV after all table inspections have completed."""
        with self._lock:
            rows = self._successful_layer_classifications(inspection_results)
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(
                buffer,
                fieldnames=LLM_LAYER_CLASSIFICATION_FIELDS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
            content = buffer.getvalue()
            report_path = self.root / LLM_LAYER_CLASSIFICATION_REPORT_NAME
            self._atomic_write(report_path, content)
            self._manifest["layer_classification_csv"] = {
                "path": str(report_path),
                "row_count": len(rows),
                "content_sha256": self._content_digest(content),
                "generated_at": _utc_timestamp(),
            }
            self._write_manifest()
            return report_path

    def write_catalog_proposal_audit(
        self,
        proposal_report: dict[str, Any],
    ) -> None:
        """Persist derived proposals without treating them as resume input."""
        proposals = proposal_report.get("catalog_proposals") or []
        conflicts = proposal_report.get("catalog_proposal_conflicts") or []
        if not isinstance(proposals, list) or not isinstance(conflicts, list):
            raise ValueError("catalog proposal audit must contain lists")
        with self._lock:
            self._manifest["catalog_proposal_audit"] = {
                "schema_version": CATALOG_PROPOSAL_SCHEMA_VERSION,
                "catalog_snapshot_hash": self.catalog_snapshot_hash,
                "proposals": copy.deepcopy(proposals),
                "proposal_count": len(proposals),
                "conflicts": copy.deepcopy(conflicts),
                "conflict_count": len(conflicts),
                "generated_at": _utc_timestamp(),
            }
            self._write_manifest()

    def _invalidate_publication_rejected_variants(
        self,
        validation: dict[str, Any],
    ) -> None:
        raw_tables = validation.get("reinspection_tables")
        if not isinstance(raw_tables, list):
            return
        entries_by_key = {
            str(table_name).casefold(): entry
            for table_name, entry in self._manifest["tables"].items()
            if isinstance(entry, dict)
        }
        for raw_table_name in raw_tables:
            entry = entries_by_key.get(str(raw_table_name).casefold())
            if entry is None:
                continue
            variants = entry.get("inspection_variants")
            if not isinstance(variants, dict) or not variants:
                continue
            context_hash = str(entry.get("active_context_hash") or "")
            if context_hash not in variants:
                context_hash = next(reversed(list(variants)), "")
            variant = variants.get(context_hash)
            if not isinstance(variant, dict):
                continue
            variant["resume_eligible"] = False
            variant["reuse_kind"] = ""
            variant["invalidation_reason"] = "publication_rejected"
            variant["updated_at"] = _utc_timestamp()
            invalidated_hashes = self._normalized_context_hashes(
                entry.get("invalidated_context_hashes")
            )
            if context_hash not in invalidated_hashes:
                invalidated_hashes.append(context_hash)
            entry["invalidated_context_hashes"] = invalidated_hashes[
                -MAX_CHECKPOINT_INVALIDATIONS_PER_TABLE:
            ]
            invalidation_reasons = self._normalized_invalidation_reasons(
                entry.get("resume_invalidation_reasons")
            )
            invalidation_reasons[context_hash] = "publication_rejected"
            entry["resume_invalidation_reasons"] = {
                cache_hash: invalidation_reasons.get(
                    cache_hash,
                    "previously_invalidated",
                )
                for cache_hash in entry["invalidated_context_hashes"]
            }

    def finish(
        self,
        *,
        status: str,
        published: bool,
        validation: dict[str, Any],
    ) -> None:
        try:
            with self._lock:
                self._manifest["status"] = status
                self._manifest["published"] = bool(published)
                self._manifest["publication_validation"] = validation
                self._invalidate_publication_rejected_variants(validation)
                self._refresh_manifest_counts(self._manifest)
                self._write_manifest()
        finally:
            self.close()

    def report(self) -> dict[str, Any]:
        with self._lock:
            layer_report = self._manifest.get("layer_classification_csv")
            if not isinstance(layer_report, dict):
                layer_report = {}
            proposal_audit = self._manifest.get("catalog_proposal_audit")
            if not isinstance(proposal_audit, dict):
                proposal_audit = {}
            return {
                "enabled": True,
                "run_id": self.run_id,
                "path": str(self.root),
                "manifest_path": str(self.manifest_path),
                "status": self._manifest["status"],
                "resume_enabled": self._manifest.get("resume_enabled", False),
                "resumed_from_run_id": self._manifest.get(
                    "resumed_from_run_id"
                ),
                "resume_candidate_table_count": self._manifest.get(
                    "resume_candidate_table_count", 0
                ),
                "resume_candidate_variant_count": self._manifest.get(
                    "resume_candidate_variant_count", 0
                ),
                "resumed_table_count": self._manifest.get(
                    "resumed_table_count", 0
                ),
                "resumed_variant_count": self._manifest.get(
                    "resumed_variant_count", 0
                ),
                "invalidated_variant_count": self._manifest.get(
                    "invalidated_variant_count", 0
                ),
                "resume_candidate_kind_counts": self._manifest.get(
                    "resume_candidate_kind_counts", {}
                ),
                "invalidation_reason_counts": self._manifest.get(
                    "invalidation_reason_counts", {}
                ),
                "policy_versions": {
                    name: self._manifest.get(name)
                    for name in current_policy_versions()
                },
                "processed_table_count": self._manifest[
                    "processed_table_count"
                ],
                "inspected_table_count": self._manifest[
                    "inspected_table_count"
                ],
                "layer_classification_csv_path": layer_report.get("path"),
                "layer_classification_table_count": layer_report.get(
                    "row_count", 0
                ),
                "catalog_proposal_count": proposal_audit.get(
                    "proposal_count", 0
                ),
                "catalog_proposal_conflict_count": proposal_audit.get(
                    "conflict_count", 0
                ),
            }
