"""Per-table MID checkpoints for long-running cold-start generation."""

from __future__ import annotations

import copy
import errno
import fcntl
import json
import threading
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from dw_refactor_agent.assessment.llm.metadata_flow import MetadataFlowPlan
from dw_refactor_agent.assessment.llm.model_metadata_updates import (
    update_model_yaml,
)
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import TEXT_ENCODING

MID_LAYERS = {"DWD", "DWS", "DIM"}


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
    """Persist completed MID candidates without touching formal models."""

    def __init__(
        self,
        project: str,
        *,
        project_dir: Path,
        plan: MetadataFlowPlan,
    ) -> None:
        self.project = project
        self.project_dir = Path(project_dir)
        self.plan = plan
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
            self._clear_previous_models()
            self._manifest: dict[str, Any] = {
                "version": 1,
                "project": project,
                "mode": "generate",
                "run_id": self.run_id,
                "status": "running",
                "published": False,
                "created_at": _utc_timestamp(),
                "updated_at": _utc_timestamp(),
                "table_count": sum(
                    1
                    for metadata in plan.base_model_metadata.values()
                    if _is_mid_model(metadata)
                ),
                "checkpoint_model_count": 0,
                "inspected_table_count": 0,
                "tables": {},
            }
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

    def _clear_previous_models(self) -> None:
        if not self.root.exists():
            return
        for path in self.root.glob("*.yaml"):
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
        manifest["checkpoint_model_count"] = len(tables)
        manifest["inspected_table_count"] = sum(
            1
            for item in tables.values()
            if isinstance(item, dict)
            and item.get("inspection_status") is not None
        )

    def _recover_pending_write(self) -> None:
        manifest = self._load_existing_manifest()
        pending = manifest.get("pending_write")
        if not isinstance(pending, dict):
            return
        table_name = str(pending.get("table") or "")
        entry = pending.get("entry")
        checkpoint_path = self.root / f"{table_name}.yaml"
        if table_name and isinstance(entry, dict) and checkpoint_path.exists():
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

    def _write_model(
        self,
        table_name: str,
        metadata: dict[str, Any],
        *,
        stage: str,
        inspection_status: str | None = None,
        confidence: float | None = None,
        retry_count: int | None = None,
        validation: dict[str, Any] | None = None,
    ) -> Path:
        checkpoint_path = self.root / f"{table_name}.yaml"
        previous = self._manifest["tables"].get(table_name) or {}
        entry = {
            "target_path": str(self._target_path(table_name)),
            "checkpoint_path": str(checkpoint_path),
            "stage": stage,
            "updated_at": _utc_timestamp(),
            "revision": int(previous.get("revision") or 0) + 1,
        }
        for key, value in (
            ("inspection_status", inspection_status),
            ("confidence", confidence),
            ("retry_count", retry_count),
            ("validation", validation),
        ):
            if value is not None:
                entry[key] = value
            elif key in previous:
                entry[key] = previous[key]
        self._manifest["pending_write"] = {
            "table": table_name,
            "entry": entry,
        }
        self._write_manifest()
        self._atomic_write(
            checkpoint_path,
            yaml.safe_dump(
                metadata,
                allow_unicode=True,
                sort_keys=False,
            ),
        )
        self._manifest["tables"][table_name] = entry
        self._manifest.pop("pending_write", None)
        self._refresh_manifest_counts(self._manifest)
        self._write_manifest()
        return checkpoint_path

    def write_inspection_result(self, result: TableInspectResult) -> None:
        """Write one MID YAML immediately after its inspection completes."""
        with self._lock:
            table_name = result.table_name
            existing = dict(
                self.plan.base_model_metadata.get(table_name) or {}
            )
            result_copy = copy.deepcopy(result)
            update = update_model_yaml(
                self.project,
                result_copy,
                dry_run=True,
                write_scope=self.plan.write_scope,
                existing_model=existing,
                path=self._target_path(table_name),
                resolution_policy=self.plan.resolution_policy,
                include_model_metadata=True,
            )
            metadata = dict(update.get("model_metadata") or existing)
            self._write_model(
                table_name,
                metadata,
                stage="inspected",
                inspection_status=result_copy.status,
                confidence=result_copy.confidence,
                retry_count=result_copy.retry_count,
                validation=dict(result_copy.validation or {}),
            )

    def write_final_candidates(
        self,
        model_metadata: dict[str, dict[str, Any]],
    ) -> None:
        """Replace partial YAML with each complete in-memory MID candidate."""
        with self._lock:
            for table_name, metadata in sorted(model_metadata.items()):
                if not _is_mid_model(metadata):
                    continue
                self._write_model(
                    table_name,
                    dict(metadata),
                    stage="final_candidate",
                )

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
                self._write_manifest()
        finally:
            self.close()

    def report(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "run_id": self.run_id,
                "path": str(self.root),
                "manifest_path": str(self.manifest_path),
                "status": self._manifest["status"],
                "checkpoint_model_count": self._manifest[
                    "checkpoint_model_count"
                ],
                "inspected_table_count": self._manifest[
                    "inspected_table_count"
                ],
            }
