"""Per-table MID checkpoints for long-running cold-start generation."""

from __future__ import annotations

import copy
import json
import threading
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
        self._lock = threading.RLock()
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

    def _clear_previous_models(self) -> None:
        if not self.root.exists():
            return
        for path in self.root.glob("*.yaml"):
            path.unlink()

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
        self._atomic_write(
            checkpoint_path,
            yaml.safe_dump(
                metadata,
                allow_unicode=True,
                sort_keys=False,
            ),
        )
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
        self._manifest["tables"][table_name] = entry
        self._manifest["checkpoint_model_count"] = len(
            self._manifest["tables"]
        )
        self._manifest["inspected_table_count"] = sum(
            1
            for item in self._manifest["tables"].values()
            if item.get("inspection_status") is not None
        )
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
                inspection_status=result.status,
                confidence=result.confidence,
                retry_count=result.retry_count,
                validation=dict(result.validation or {}),
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
        with self._lock:
            self._manifest["status"] = status
            self._manifest["published"] = bool(published)
            self._manifest["publication_validation"] = validation
            self._write_manifest()

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
