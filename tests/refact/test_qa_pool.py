from __future__ import annotations

import pytest

import dw_refactor_agent.refactor.qa_pool as qa_pool
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.qa_pool import (
    MARKER_COLUMNS,
    QaSlotInspection,
    QaSlotOwnership,
    configured_qa_pool,
    inspect_qa_slot,
    require_slot_ownership,
)


class ScriptedCursor:
    def __init__(self, responses):
        self.responses = responses
        self.rows = []

    def execute(self, sql, params=None):
        del params
        for pattern, rows in self.responses:
            if pattern in sql:
                self.rows = list(rows)
                return
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class ScriptedConnection:
    def __init__(self):
        self.responses = []

    def add(self, pattern, rows):
        self.responses.append((pattern, rows))

    def cursor(self):
        return ScriptedCursor(self.responses)


@pytest.fixture
def scripted_connection():
    return ScriptedConnection()


def _marker_row(**overrides):
    values = {
        "format_version": 2,
        "marker_key": "current",
        "project": "shop",
        "run_id": "run-1",
        "execution_id": "execution-1",
        "qa_database": "shop_dm_qa_02",
        "plan_fingerprint": "sha256:" + "a" * 64,
        "workspace_fingerprint": "sha256:" + "b" * 64,
        "claimed_at": "2026-07-14 11:33:20",
        "claimed_at_epoch": 1784000000,
    }
    values.update(overrides)
    return tuple(values[column] for column in MARKER_COLUMNS) + (
        values["claimed_at_epoch"],
    )


def _add_current_marker(connection, rows=None, *, objects=None):
    connection.add(
        "SHOW FULL TABLES",
        objects or [("dw_refactor_execution_marker", "BASE TABLE")],
    )
    connection.add("SHOW COLUMNS", [(name,) for name in MARKER_COLUMNS])
    connection.add(
        "UNIX_TIMESTAMP(claimed_at)",
        [_marker_row()] if rows is None else rows,
    )


def _project_config(pool=None):
    verification = {}
    if pool is not None:
        verification["qa_database_pool"] = pool
    return {
        "db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "lineage_db": "shop_lineage",
        "verification": verification,
    }


def test_configured_qa_pool_normalizes_explicit_pool():
    assert configured_qa_pool(
        "shop",
        _project_config(["shop_dm_qa", "shop_dm_qa_02"]),
    ) == ("shop_dm_qa", "shop_dm_qa_02")


def test_configured_qa_pool_falls_back_to_legacy_qa_database():
    assert configured_qa_pool("shop", _project_config()) == ("shop_dm_qa",)


@pytest.mark.parametrize(
    "pool, expected",
    [
        ([], "non-empty"),
        (["shop_dm"], "production database"),
        (["shop_lineage"], "lineage database"),
        (["bad-name"], "identifier"),
        (["shop_dm_qa", "SHOP_DM_QA"], "duplicate"),
        (["information_schema"], "system database"),
    ],
)
def test_configured_qa_pool_rejects_unsafe_values(pool, expected):
    with pytest.raises(ValueError, match=expected):
        configured_qa_pool("shop", _project_config(pool))


def test_get_qa_connection_uses_qa_credentials_and_autocommit(monkeypatch):
    calls = []
    expected = object()
    monkeypatch.setattr(
        qa_pool.pymysql,
        "connect",
        lambda **kwargs: calls.append(kwargs) or expected,
    )

    assert qa_pool.get_qa_connection("shop_dm_qa") is expected
    assert calls == [
        {
            "host": qa_pool.DORIS_HOST,
            "port": qa_pool.DORIS_PORT,
            "user": qa_pool.DORIS_QA_USER,
            "database": "shop_dm_qa",
            "charset": "utf8mb4",
            "autocommit": True,
        }
    ]


def test_inspect_empty_slot_returns_free(scripted_connection):
    scripted_connection.add("SHOW FULL TABLES", [])

    result = inspect_qa_slot(
        "shop", "shop_dm_qa_02", connection=scripted_connection
    )

    assert result == QaSlotInspection(
        project="shop",
        database="shop_dm_qa_02",
        availability="free",
        ownership=None,
        diagnostic=None,
        objects=(),
    )


def test_inspect_current_marker_schema_returns_legacy(scripted_connection):
    scripted_connection.add(
        "SHOW FULL TABLES",
        [("dw_refactor_execution_marker", "BASE TABLE")],
    )
    scripted_connection.add(
        "SHOW COLUMNS",
        [
            ("marker_key",),
            ("execution_id",),
            ("plan_fingerprint",),
            ("workspace_fingerprint",),
            ("completed_at",),
        ],
    )

    result = inspect_qa_slot(
        "shop", "shop_dm_qa", connection=scripted_connection
    )

    assert result.availability == "legacy"
    assert result.ownership is None
    assert "legacy" in result.diagnostic


def test_inspect_valid_marker_returns_exact_ownership(scripted_connection):
    _add_current_marker(scripted_connection)

    result = inspect_qa_slot(
        "shop", "shop_dm_qa_02", connection=scripted_connection
    )

    assert result.availability == "claimed"
    assert result.ownership == QaSlotOwnership(
        format_version=2,
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        qa_database="shop_dm_qa_02",
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
        claimed_at="2026-07-14 11:33:20",
        claimed_at_epoch=1784000000,
    )


def test_inspect_markerless_nonempty_slot_returns_invalid(
    scripted_connection,
):
    scripted_connection.add(
        "SHOW FULL TABLES", [("business_table", "BASE TABLE")]
    )

    result = inspect_qa_slot(
        "shop", "shop_dm_qa_02", connection=scripted_connection
    )

    assert result.availability == "invalid"
    assert "marker" in result.diagnostic


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([_marker_row(format_version=3)], "format_version"),
        ([], "exactly one"),
        ([_marker_row(), _marker_row()], "exactly one"),
        ([_marker_row(qa_database="other_qa")], "qa_database"),
    ],
)
def test_inspect_malformed_marker_returns_invalid(
    scripted_connection, rows, expected
):
    _add_current_marker(scripted_connection, rows)

    result = inspect_qa_slot(
        "shop", "shop_dm_qa_02", connection=scripted_connection
    )

    assert result.availability == "invalid"
    assert expected in result.diagnostic


def test_require_slot_ownership_rejects_any_mismatch(monkeypatch):
    owner = QaSlotOwnership(
        2,
        "shop",
        "run-1",
        "execution-1",
        "shop_dm_qa_02",
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "2026-07-14 11:33:20",
        1784000000,
    )
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda *args, **kwargs: QaSlotInspection(
            "shop", "shop_dm_qa_02", "claimed", owner, None, ()
        ),
    )

    with pytest.raises(ArtifactFormatError, match="execution_id"):
        require_slot_ownership(
            project="shop",
            run_id="run-1",
            execution_id="different",
            database="shop_dm_qa_02",
            plan_fingerprint="sha256:" + "a" * 64,
            workspace_fingerprint="sha256:" + "b" * 64,
        )
