from __future__ import annotations

import pytest

import dw_refactor_agent.refactor.qa_pool as qa_pool
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.qa_pool import (
    MARKER_COLUMNS,
    QaPoolExhaustedError,
    QaSlotInspection,
    QaSlotOwnership,
    claim_qa_slot,
    configured_qa_pool,
    inspect_qa_slot,
    parse_age,
    parse_created_before,
    release_qa_slot,
    require_slot_ownership,
    select_cleanup_slots,
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


@pytest.mark.parametrize(
    "value, expected",
    [("30s", 30), ("15m", 900), ("2h", 7200), ("7d", 604800)],
)
def test_parse_age_supports_explicit_units(value, expected):
    assert parse_age(value) == expected


@pytest.mark.parametrize("value", ["", "7", "-1d", "1month", "0h"])
def test_parse_age_rejects_ambiguous_or_nonpositive_values(value):
    with pytest.raises(ValueError, match="age"):
        parse_age(value)


def test_parse_created_before_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        parse_created_before("2026-07-01T00:00:00")

    assert parse_created_before("1970-01-01T08:00:01+08:00") == 1


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


def _ownership(
    database="shop_dm_qa_02",
    *,
    execution_id="execution-1",
    run_id="run-1",
    claimed_at_epoch=1784001600,
):
    return QaSlotOwnership(
        2,
        "shop",
        run_id,
        execution_id,
        database,
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "2026-07-14 12:00:00",
        claimed_at_epoch,
    )


def _inspection(
    database,
    availability="claimed",
    ownership=None,
    *,
    objects=(),
):
    if availability == "claimed" and ownership is None:
        ownership = _ownership(database)
    return QaSlotInspection(
        "shop", database, availability, ownership, None, tuple(objects)
    )


def test_claim_rotates_pool_and_returns_verified_owner(monkeypatch):
    owner = _ownership()
    inspections = {
        "shop_dm_qa": _inspection("shop_dm_qa", "claimed"),
        "shop_dm_qa_02": _inspection("shop_dm_qa_02", "free"),
    }
    calls = []
    monkeypatch.setattr(
        qa_pool, "_rotated_pool", lambda pool, execution_id: tuple(pool)
    )
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda project, database, **kwargs: inspections[database],
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: calls.append(database) or owner,
    )

    result = claim_qa_slot(
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        pool=("shop_dm_qa", "shop_dm_qa_02"),
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )

    assert result.qa_database == "shop_dm_qa_02"
    assert calls == ["shop_dm_qa_02"]


def test_claim_loser_moves_to_next_slot_after_duplicate_table(monkeypatch):
    owner = _ownership()
    monkeypatch.setattr(
        qa_pool, "_rotated_pool", lambda pool, execution_id: tuple(pool)
    )
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda project, database, **kwargs: _inspection(database, "free"),
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: (
            None if database == "shop_dm_qa" else owner
        ),
    )

    result = claim_qa_slot(
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        pool=("shop_dm_qa", "shop_dm_qa_02"),
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )

    assert result.qa_database == "shop_dm_qa_02"


def test_claim_exhaustion_never_drops_or_overwrites(monkeypatch):
    owner = _ownership("shop_dm_qa", execution_id="execution-old")
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda project, database, **kwargs: _inspection(
            database, "claimed", owner
        ),
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: (_ for _ in ()).throw(
            AssertionError("claimed slots must not be overwritten")
        ),
    )

    with pytest.raises(QaPoolExhaustedError) as exc:
        claim_qa_slot(
            project="shop",
            run_id="run-1",
            execution_id="execution-1",
            pool=("shop_dm_qa", "shop_dm_qa_02"),
            plan_fingerprint="sha256:" + "a" * 64,
            workspace_fingerprint="sha256:" + "b" * 64,
        )

    assert {item.database for item in exc.value.inspections} == {
        "shop_dm_qa",
        "shop_dm_qa_02",
    }


def test_cleanup_selector_combines_claimed_filters_with_and_semantics():
    inspections = [
        _inspection(
            "shop_dm_qa",
            ownership=_ownership(
                "shop_dm_qa",
                execution_id="old",
                claimed_at_epoch=100,
            ),
        ),
        _inspection(
            "shop_dm_qa_02",
            ownership=_ownership(
                "shop_dm_qa_02",
                execution_id="new",
                claimed_at_epoch=300,
            ),
        ),
    ]

    selected = select_cleanup_slots(
        inspections,
        project="shop",
        run_id="run-1",
        execution_id=None,
        database=None,
        cutoff_epoch=200,
    )

    assert [item.database for item in selected] == ["shop_dm_qa"]


@pytest.mark.parametrize("availability", ["legacy", "invalid"])
def test_cleanup_selector_requires_exact_database_for_unsafe_slots(
    availability,
):
    inspection = _inspection("shop_dm_qa", availability, None)

    assert not select_cleanup_slots(
        [inspection],
        project="shop",
        run_id=None,
        execution_id=None,
        database=None,
        cutoff_epoch=None,
    )
    assert select_cleanup_slots(
        [inspection],
        project="shop",
        run_id=None,
        execution_id=None,
        database="shop_dm_qa",
        cutoff_epoch=None,
    ) == [inspection]


class RecordingCursor:
    def __init__(self, *, fail_on=None):
        self.fail_on = fail_on
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("simulated drop failure")

    def close(self):
        pass


class RecordingConnection:
    def __init__(self, *, fail_on=None):
        self.recording_cursor = RecordingCursor(fail_on=fail_on)
        self.closed = False

    def cursor(self):
        return self.recording_cursor

    def close(self):
        self.closed = True


def test_try_claim_creates_marker_without_if_not_exists_and_inserts_values(
    monkeypatch,
):
    connection = RecordingConnection()
    owner = _ownership()
    monkeypatch.setattr(
        qa_pool, "get_qa_connection", lambda database: connection
    )
    monkeypatch.setattr(
        qa_pool, "require_slot_ownership", lambda **kwargs: owner
    )

    result = qa_pool._try_claim_slot(
        "shop_dm_qa_02",
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )

    statements = connection.recording_cursor.executed
    assert statements[0][0].startswith("CREATE TABLE")
    assert "IF NOT EXISTS" not in statements[0][0]
    assert statements[1][0].startswith("INSERT INTO")
    assert statements[1][1][2:6] == (
        "shop",
        "run-1",
        "execution-1",
        "shop_dm_qa_02",
    )
    assert result is owner
    assert connection.closed


def test_try_claim_treats_only_duplicate_marker_table_as_race(monkeypatch):
    class DuplicateCursor(RecordingCursor):
        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            raise qa_pool.pymysql.err.OperationalError(
                1050, "Table dw_refactor_execution_marker already exists"
            )

    connection = RecordingConnection()
    connection.recording_cursor = DuplicateCursor()
    monkeypatch.setattr(
        qa_pool, "get_qa_connection", lambda database: connection
    )

    result = qa_pool._try_claim_slot(
        "shop_dm_qa_02",
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )

    assert result is None
    assert connection.closed


def test_release_drops_views_then_tables_and_marker_last(monkeypatch):
    owner = _ownership()
    inspection = _inspection(
        "shop_dm_qa_02",
        ownership=owner,
        objects=(
            ("table_a", "BASE TABLE"),
            ("view_a", "VIEW"),
            ("dw_refactor_execution_marker", "BASE TABLE"),
        ),
    )
    connection = RecordingConnection()
    monkeypatch.setattr(qa_pool, "inspect_qa_slot", lambda *a, **k: inspection)
    monkeypatch.setattr(
        qa_pool, "get_qa_connection", lambda database: connection
    )

    result = release_qa_slot(
        inspection,
        configured_pool=("shop_dm_qa", "shop_dm_qa_02"),
        protected_databases={"shop_dm", "shop_lineage"},
    )

    statements = [sql for sql, _ in connection.recording_cursor.executed]
    assert statements[0].startswith("DROP VIEW")
    assert "`view_a`" in statements[0]
    assert "`table_a`" in statements[1]
    assert "`dw_refactor_execution_marker`" in statements[-1]
    assert result["dropped_objects"] == [
        "view_a",
        "table_a",
        "dw_refactor_execution_marker",
    ]


def test_release_business_object_failure_preserves_marker(monkeypatch):
    inspection = _inspection(
        "shop_dm_qa_02",
        objects=(
            ("table_a", "BASE TABLE"),
            ("dw_refactor_execution_marker", "BASE TABLE"),
        ),
    )
    connection = RecordingConnection(fail_on="`table_a`")
    monkeypatch.setattr(qa_pool, "inspect_qa_slot", lambda *a, **k: inspection)
    monkeypatch.setattr(
        qa_pool, "get_qa_connection", lambda database: connection
    )

    with pytest.raises(ArtifactFormatError, match="table_a"):
        release_qa_slot(
            inspection,
            configured_pool=("shop_dm_qa", "shop_dm_qa_02"),
            protected_databases={"shop_dm", "shop_lineage"},
        )

    statements = [sql for sql, _ in connection.recording_cursor.executed]
    assert not any("dw_refactor_execution_marker" in sql for sql in statements)


def test_release_rejects_unconfigured_or_protected_database():
    inspection = _inspection("shop_dm")

    with pytest.raises(ArtifactFormatError, match="protected"):
        release_qa_slot(
            inspection,
            configured_pool=("shop_dm",),
            protected_databases={"shop_dm", "shop_lineage"},
        )
