"""Lineage service entry points."""

from __future__ import annotations

from lineage.store import JsonLineageStore, LineageStore
from lineage.view import LineageView


def open_lineage(
    project: str,
    *,
    snapshot_id: str | None = None,
    store: LineageStore | None = None,
) -> LineageView:
    """Open one lineage snapshot and return an indexed read view."""
    lineage_store = store or JsonLineageStore()
    snapshot = lineage_store.load_snapshot(project, snapshot_id)
    return LineageView(snapshot)
