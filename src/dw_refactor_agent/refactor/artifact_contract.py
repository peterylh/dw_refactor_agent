"""Shared contracts for persisted refactor artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from dw_refactor_agent.config import TEXT_ENCODING

FORMAT_VERSION = 1


class ArtifactFormatError(ValueError):
    """Raised when a persisted refactor artifact violates its contract."""


def canonical_json_bytes(value) -> bytes:
    """Serialize a value deterministically for hashing."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(TEXT_ENCODING)


def sha256_json(value) -> str:
    """Return a namespaced SHA-256 digest for canonical JSON."""
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"


def atomic_write_json(path: Path, value: dict) -> None:
    """Atomically replace a JSON document in its target directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=TEXT_ENCODING) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace a byte artifact in its target directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def read_json_object(path: Path, artifact_name: str) -> dict:
    """Read one persisted JSON object with a stable contract error."""
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding=TEXT_ENCODING))
    except (OSError, ValueError) as exc:
        raise ArtifactFormatError(
            f"cannot read {artifact_name} {source}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ArtifactFormatError(
            f"{artifact_name} must be a JSON object: {source}"
        )
    return value


def require_format_version(value: dict, artifact_name: str) -> None:
    """Require the current explicit artifact format version."""
    actual = value.get("format_version")
    if actual != FORMAT_VERSION:
        raise ArtifactFormatError(
            f"{artifact_name} format_version must be {FORMAT_VERSION}; "
            f"received {actual!r}; create a new refactor run"
        )
