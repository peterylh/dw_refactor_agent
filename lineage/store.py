"""Lineage storage interfaces."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from typing import Protocol
except ImportError:  # Python 3.7
    from typing_extensions import Protocol

from config import TEXT_ENCODING, lineage_data_path
from lineage.model import LineageSnapshot


class LineageStore(Protocol):
    """Storage abstraction for loading lineage snapshots."""

    def load_snapshot(
        self,
        project: str,
        snapshot_id: str | None = None,
    ) -> LineageSnapshot:
        """Load a lineage snapshot for one project."""


class JsonLineageStore:
    """Load lineage snapshots from the repository's JSON files."""

    def __init__(self, lineage_dir: Path | None = None):
        self.lineage_dir = Path(lineage_dir) if lineage_dir else None

    def load_snapshot(
        self,
        project: str,
        snapshot_id: str | None = None,
    ) -> LineageSnapshot:
        path = self._snapshot_path(project, snapshot_id)
        with path.open(encoding=TEXT_ENCODING) as file:
            data = json.load(file)
        return LineageSnapshot.from_dict(
            project,
            data,
            snapshot_id=snapshot_id or "",
        )

    def _snapshot_path(self, project: str, snapshot_id: str | None) -> Path:
        if self.lineage_dir is not None and snapshot_id:
            return (
                self.lineage_dir / f"lineage_data_{project}_{snapshot_id}.json"
            )

        if self.lineage_dir is not None:
            project_path = self.lineage_dir / f"lineage_data_{project}.json"
            if project_path.exists():
                return project_path

            raise FileNotFoundError(
                f"未找到 {project} 的血缘数据文件 "
                f"(lineage_data_{project}.json)"
            )

        project_path = lineage_data_path(project, snapshot_id=snapshot_id)
        if project_path.exists():
            return project_path

        raise FileNotFoundError(
            f"未找到 {project} 的血缘数据文件 "
            f"({project}/lineage/lineage_data.json)"
        )
