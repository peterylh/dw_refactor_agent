"""Serialized, recoverable publication for managed metadata files."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence, Tuple
from uuid import uuid4

from dw_refactor_agent.assessment.llm.model_metadata_runtime import (
    project_root,
)
from dw_refactor_agent.config import PROJECT_CONFIG, TEXT_ENCODING

ABSENT_FILE_HASH = "absent"
JOURNAL_SCHEMA_VERSION = 1
_CATALOG_FILE_NAMES = (
    "business_taxonomy.yaml",
    "business_processes.yaml",
    "semantic_subjects.yaml",
    "business_semantics.yaml",
)
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()
_LOCAL = threading.local()


@dataclass(frozen=True)
class MetadataPublicationSnapshot:
    """Hash of the complete managed catalog/model file set."""

    project: str
    files_hash: str
    file_hashes: Tuple[Tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "files_hash": self.files_hash,
            "file_hashes": dict(self.file_hashes),
        }


@dataclass(frozen=True)
class MetadataPublicationOutcome:
    """Durability state returned by publication and recovery."""

    formal_files_state: str
    finalization_status: str
    recovery_required: bool
    transaction_id: str = ""
    recovered_action: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "formal_files_state": self.formal_files_state,
            "finalization_status": self.finalization_status,
            "recovery_required": self.recovery_required,
            "transaction_id": self.transaction_id,
            "recovered_action": self.recovered_action,
            "error": self.error,
        }


class MetadataPublicationError(RuntimeError):
    """Publication failed after its formal-file state was established."""

    def __init__(
        self,
        message: str,
        *,
        outcome: MetadataPublicationOutcome,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.outcome = outcome
        self.cause = cause


class MetadataPublicationConflict(MetadataPublicationError):
    """The managed formal-file fingerprint changed before publication."""


class MetadataPublicationRecoveryRequired(MetadataPublicationError):
    """A durable journal could not be deterministically recovered."""


def _process_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.RLock())


def _project_dir(project: str) -> Path:
    config = PROJECT_CONFIG.get(project)
    if not config:
        raise KeyError(f"未知项目: {project}")
    return project_root() / str(config["dir"])


def metadata_publication_lock_path(project: str) -> Path:
    return (
        _project_dir(project)
        / "artifacts"
        / "assessment"
        / ".metadata_publication.lock"
    )


def metadata_publication_journal_path(project: str) -> Path:
    return (
        _project_dir(project)
        / "artifacts"
        / "assessment"
        / ".metadata_publication.journal.json"
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_fsynced(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _write_json_fsynced(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode(TEXT_ENCODING)
    try:
        _write_bytes_fsynced(temporary, content)
        os.replace(str(temporary), str(path))
        _fsync_directory(path.parent)
    finally:
        with suppress(OSError):
            temporary.unlink()


def _file_hash(path: Path) -> str:
    if not path.is_file():
        return ABSENT_FILE_HASH
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _display_path(path: Path) -> str:
    root = project_root().resolve()
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _managed_metadata_paths(project: str) -> Tuple[Path, ...]:
    directory = _project_dir(project)
    paths = {directory / name for name in _CATALOG_FILE_NAMES}
    for role in ("ods", "mid", "ads"):
        model_root = directory / role / "models"
        if model_root.exists():
            paths.update(model_root.rglob("*.yaml"))
    return tuple(
        sorted(paths, key=lambda path: _display_path(path).casefold())
    )


def _capture_snapshot_locked(project: str) -> MetadataPublicationSnapshot:
    file_hashes = tuple(
        (_display_path(path), _file_hash(path))
        for path in _managed_metadata_paths(project)
    )
    encoded = json.dumps(
        file_hashes,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode(TEXT_ENCODING)
    return MetadataPublicationSnapshot(
        project=project,
        files_hash=_bytes_hash(encoded),
        file_hashes=file_hashes,
    )


def _validate_snapshot(
    project: str,
    expected: MetadataPublicationSnapshot,
) -> MetadataPublicationSnapshot:
    if expected.project != project:
        raise ValueError(
            "publication snapshot project mismatch: "
            f"expected={expected.project}, actual={project}"
        )
    current = _capture_snapshot_locked(project)
    if current.files_hash != expected.files_hash:
        outcome = MetadataPublicationOutcome(
            formal_files_state="unchanged",
            finalization_status="not_started",
            recovery_required=False,
            error="formal_files_fingerprint_changed",
        )
        raise MetadataPublicationConflict(
            "managed catalog/model files changed before publication",
            outcome=outcome,
        )
    return current


def _journal_payload(
    project: str,
    transaction_id: str,
    phase: str,
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "project": project,
        "transaction_id": transaction_id,
        "phase": phase,
        "entries": [dict(entry) for entry in entries],
    }


def _persist_journal(
    project: str,
    transaction_id: str,
    phase: str,
    entries: Sequence[Mapping[str, Any]],
) -> None:
    _write_json_fsynced(
        metadata_publication_journal_path(project),
        _journal_payload(project, transaction_id, phase, entries),
    )


def _load_journal(project: str) -> dict[str, Any] | None:
    path = metadata_publication_journal_path(project)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
    except (OSError, ValueError) as exc:
        outcome = MetadataPublicationOutcome(
            formal_files_state="unknown",
            finalization_status="failed",
            recovery_required=True,
            error=f"invalid_publication_journal: {exc}",
        )
        raise MetadataPublicationRecoveryRequired(
            "metadata publication journal is unreadable",
            outcome=outcome,
            cause=exc,
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != JOURNAL_SCHEMA_VERSION
        or payload.get("project") != project
        or not isinstance(payload.get("entries"), list)
    ):
        outcome = MetadataPublicationOutcome(
            formal_files_state="unknown",
            finalization_status="failed",
            recovery_required=True,
            error="invalid_publication_journal_contract",
        )
        raise MetadataPublicationRecoveryRequired(
            "metadata publication journal contract is invalid",
            outcome=outcome,
        )
    return payload


def _path_within_project(project: str, raw_path: Any) -> Path:
    path = Path(str(raw_path or "")).resolve(strict=False)
    directory = _project_dir(project).resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError(f"publication path escapes project: {path}") from exc
    return path


def _journal_entries(
    project: str, journal: Mapping[str, Any]
) -> list[dict[str, Any]]:
    entries = []
    for raw in journal.get("entries") or []:
        if not isinstance(raw, dict):
            raise ValueError("publication journal entry must be an object")
        entry = dict(raw)
        for key in ("target", "stage", "backup"):
            entry[key] = _path_within_project(project, entry.get(key))
        if entry.get("action") not in {"install", "delete"}:
            raise ValueError("publication journal action is invalid")
        entries.append(entry)
    return entries


def _remove_path(path: Path) -> None:
    if path.exists():
        path.unlink()
        _fsync_directory(path.parent)


def _cleanup_transaction_files(entries: Sequence[Mapping[str, Any]]) -> None:
    for entry in entries:
        for key in ("stage", "backup"):
            path = Path(entry[key])
            _remove_path(path)


def _verify_hashes(
    entries: Sequence[Mapping[str, Any]], *, expected_key: str
) -> None:
    failures = []
    for entry in entries:
        target = Path(entry["target"])
        expected_hash = str(entry[expected_key])
        actual_hash = _file_hash(target)
        if actual_hash != expected_hash:
            failures.append(
                f"{target}: expected={expected_hash}, actual={actual_hash}"
            )
    if failures:
        raise OSError(
            "publication verification failed: " + "; ".join(failures)
        )


def _rollback_entries(entries: Sequence[Mapping[str, Any]]) -> None:
    for entry in reversed(entries):
        target = Path(entry["target"])
        backup = Path(entry["backup"])
        old_hash = str(entry["old_hash"])
        if backup.exists():
            if target.exists():
                _remove_path(target)
            os.replace(str(backup), str(target))
            _fsync_directory(target.parent)
        elif old_hash == ABSENT_FILE_HASH:
            _remove_path(target)
        elif _file_hash(target) != old_hash:
            raise OSError(f"missing rollback backup for {target}")
    _verify_hashes(entries, expected_key="old_hash")


def _finish_recovery(
    project: str, journal: Mapping[str, Any]
) -> MetadataPublicationOutcome:
    transaction_id = str(journal.get("transaction_id") or "")
    try:
        entries = _journal_entries(project, journal)
        phase = str(journal.get("phase") or "")
        if phase == "verified":
            _verify_hashes(entries, expected_key="new_hash")
            recovered_action = "commit"
        elif phase in {"preparing", "staged"}:
            recovered_action = "discard_staged"
        else:
            _rollback_entries(entries)
            recovered_action = "rollback"
        _cleanup_transaction_files(entries)
        journal_path = metadata_publication_journal_path(project)
        _remove_path(journal_path)
        return MetadataPublicationOutcome(
            formal_files_state="recovered",
            finalization_status="completed",
            recovery_required=False,
            transaction_id=transaction_id,
            recovered_action=recovered_action,
        )
    except Exception as exc:
        outcome = MetadataPublicationOutcome(
            formal_files_state="unknown",
            finalization_status="failed",
            recovery_required=True,
            transaction_id=transaction_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise MetadataPublicationRecoveryRequired(
            "metadata publication recovery failed",
            outcome=outcome,
            cause=exc,
        ) from exc


def _recover_locked(project: str) -> MetadataPublicationOutcome | None:
    journal = _load_journal(project)
    return None if journal is None else _finish_recovery(project, journal)


@contextmanager
def metadata_publication_lock(project: str) -> Iterator[None]:
    """Serialize writers and recover a durable journal before first entry."""
    path = metadata_publication_lock_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    depths = getattr(_LOCAL, "depths", None)
    if depths is None:
        depths = {}
        _LOCAL.depths = depths
    with _process_lock(path):
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield
            finally:
                depths[key] -= 1
            return
        with path.open("a+", encoding=TEXT_ENCODING) as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            depths[key] = 1
            try:
                recovery = _recover_locked(project)
                recoveries = getattr(_LOCAL, "recoveries", None)
                if recoveries is None:
                    recoveries = {}
                    _LOCAL.recoveries = recoveries
                recoveries[key] = recovery
                yield
            finally:
                depths.pop(key, None)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def consistent_metadata_read(project: str) -> Iterator[None]:
    """Hold the publication boundary while an internal reader loads a snapshot."""
    with metadata_publication_lock(project):
        yield


def read_consistent_metadata_snapshot(
    project: str,
    loader: Callable[[], Any],
) -> tuple[Any, MetadataPublicationSnapshot]:
    """Load data and its formal-file fingerprint under one lock boundary."""
    with metadata_publication_lock(project):
        before = _capture_snapshot_locked(project)
        value = loader()
        after = _capture_snapshot_locked(project)
        if before.files_hash != after.files_hash:
            outcome = MetadataPublicationOutcome(
                formal_files_state="unknown",
                finalization_status="not_started",
                recovery_required=False,
                error="formal_files_changed_during_snapshot_read",
            )
            raise MetadataPublicationConflict(
                "managed files changed during snapshot read",
                outcome=outcome,
            )
        return value, after


def capture_metadata_publication_snapshot(
    project: str,
) -> MetadataPublicationSnapshot:
    with metadata_publication_lock(project):
        return _capture_snapshot_locked(project)


def recover_metadata_publication(project: str) -> MetadataPublicationOutcome:
    """Recover any pending journal and report the deterministic action."""
    key = str(metadata_publication_lock_path(project).resolve())
    with metadata_publication_lock(project):
        recoveries = getattr(_LOCAL, "recoveries", {})
        recovered = recoveries.get(key)
        if recovered is not None:
            return recovered
        return MetadataPublicationOutcome(
            formal_files_state="unchanged",
            finalization_status="not_started",
            recovery_required=False,
        )


def _normalize_publication_entries(
    project: str,
    transaction_id: str,
    rendered_files: Mapping[Path, str | bytes],
    delete_paths: Sequence[Path],
) -> tuple[list[dict[str, Any]], dict[Path, bytes]]:
    contents: dict[Path, bytes] = {}
    for raw_path, raw_content in rendered_files.items():
        path = _path_within_project(project, raw_path)
        content = (
            raw_content
            if isinstance(raw_content, bytes)
            else str(raw_content).encode(TEXT_ENCODING)
        )
        contents[path] = content
    delete_targets = {
        _path_within_project(project, raw_path) for raw_path in delete_paths
    } - set(contents)
    targets = list(contents) + list(delete_targets)
    path_keys = [str(path).casefold() for path in targets]
    if len(path_keys) != len(set(path_keys)):
        raise ValueError("publication target paths collide under casefold")

    entries = []
    for target in sorted(targets, key=lambda path: str(path).casefold()):
        old_hash = _file_hash(target)
        action = "install" if target in contents else "delete"
        new_hash = (
            _bytes_hash(contents[target])
            if action == "install"
            else ABSENT_FILE_HASH
        )
        if old_hash == new_hash:
            continue
        entries.append(
            {
                "action": action,
                "target": str(target),
                "stage": str(
                    target.with_name(f".{target.name}.{transaction_id}.staged")
                ),
                "backup": str(
                    target.with_name(f".{target.name}.{transaction_id}.backup")
                ),
                "old_hash": old_hash,
                "new_hash": new_hash,
            }
        )
    return entries, contents


def transactional_metadata_publication(
    project: str,
    rendered_files: Mapping[Path, str | bytes],
    *,
    delete_paths: Sequence[Path] = (),
    expected_snapshot: MetadataPublicationSnapshot | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> MetadataPublicationOutcome:
    """Install one managed file set with CAS, journal, rollback and recovery."""
    with metadata_publication_lock(project):
        if expected_snapshot is not None:
            _validate_snapshot(project, expected_snapshot)
        transaction_id = uuid4().hex
        entries, contents = _normalize_publication_entries(
            project,
            transaction_id,
            rendered_files,
            delete_paths,
        )
        if not entries:
            return MetadataPublicationOutcome(
                formal_files_state="unchanged",
                finalization_status="not_started",
                recovery_required=False,
            )

        journal_created = False
        formal_verified = False
        try:
            _persist_journal(project, transaction_id, "preparing", entries)
            journal_created = True
            for entry in entries:
                if entry["action"] != "install":
                    continue
                target = Path(entry["target"])
                _write_bytes_fsynced(Path(entry["stage"]), contents[target])
            _persist_journal(project, transaction_id, "staged", entries)
            if failure_injector:
                failure_injector("stage")
            try:
                _verify_hashes(entries, expected_key="old_hash")
            except OSError as exc:
                try:
                    _cleanup_transaction_files(entries)
                    _remove_path(metadata_publication_journal_path(project))
                except Exception as cleanup_exc:
                    outcome = MetadataPublicationOutcome(
                        formal_files_state="unchanged",
                        finalization_status="failed",
                        recovery_required=True,
                        transaction_id=transaction_id,
                        error=f"{type(cleanup_exc).__name__}: {cleanup_exc}",
                    )
                    raise MetadataPublicationRecoveryRequired(
                        "stale publication staging requires cleanup recovery",
                        outcome=outcome,
                        cause=cleanup_exc,
                    ) from exc
                outcome = MetadataPublicationOutcome(
                    formal_files_state="unchanged",
                    finalization_status="not_started",
                    recovery_required=False,
                    transaction_id=transaction_id,
                    error="formal_files_changed_after_staging",
                )
                raise MetadataPublicationConflict(
                    "managed files changed after publication staging",
                    outcome=outcome,
                    cause=exc,
                ) from exc

            _persist_journal(project, transaction_id, "backing_up", entries)
            for entry in entries:
                target = Path(entry["target"])
                backup = Path(entry["backup"])
                if target.exists():
                    os.replace(str(target), str(backup))
                    _fsync_directory(target.parent)
            _persist_journal(project, transaction_id, "backed_up", entries)
            if failure_injector:
                failure_injector("backup")

            for entry in entries:
                if entry["action"] != "install":
                    continue
                stage = Path(entry["stage"])
                target = Path(entry["target"])
                os.replace(str(stage), str(target))
                _fsync_directory(target.parent)
            _persist_journal(project, transaction_id, "installed", entries)
            if failure_injector:
                failure_injector("install")

            if failure_injector:
                failure_injector("verify")
            _verify_hashes(entries, expected_key="new_hash")
            _persist_journal(project, transaction_id, "verified", entries)
            formal_verified = True
        except MetadataPublicationConflict:
            raise
        except Exception as exc:
            if not journal_created:
                journal_created = metadata_publication_journal_path(
                    project
                ).exists()
            if not journal_created:
                raise
            try:
                _rollback_entries(entries)
                _cleanup_transaction_files(entries)
                _remove_path(metadata_publication_journal_path(project))
            except Exception as rollback_exc:
                outcome = MetadataPublicationOutcome(
                    formal_files_state="unknown",
                    finalization_status="failed",
                    recovery_required=True,
                    transaction_id=transaction_id,
                    error=f"{type(rollback_exc).__name__}: {rollback_exc}",
                )
                raise MetadataPublicationRecoveryRequired(
                    "publication and rollback both failed",
                    outcome=outcome,
                    cause=rollback_exc,
                ) from exc
            outcome = MetadataPublicationOutcome(
                formal_files_state="unchanged",
                finalization_status="not_started",
                recovery_required=False,
                transaction_id=transaction_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise MetadataPublicationError(
                "metadata publication failed and was rolled back",
                outcome=outcome,
                cause=exc,
            ) from exc

        try:
            if failure_injector:
                failure_injector("finalize")
            _cleanup_transaction_files(entries)
            _remove_path(metadata_publication_journal_path(project))
        except Exception as exc:
            outcome = MetadataPublicationOutcome(
                formal_files_state=(
                    "published" if formal_verified else "unknown"
                ),
                finalization_status="failed",
                recovery_required=True,
                transaction_id=transaction_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise MetadataPublicationRecoveryRequired(
                "published files require journal cleanup recovery",
                outcome=outcome,
                cause=exc,
            ) from exc
        return MetadataPublicationOutcome(
            formal_files_state="published" if formal_verified else "unknown",
            finalization_status="completed",
            recovery_required=False,
            transaction_id=transaction_id,
        )
