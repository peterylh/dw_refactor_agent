from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlglot
from sqlglot.errors import ErrorLevel

from dw_refactor_agent.refactor.shadow_scope import (
    Overlap,
    RowScope,
    ScopeKind,
    scope_for_predicate,
    statement_scope,
)


def _where(sql: str):
    statement = sqlglot.parse_one(
        sql, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    return statement.args["where"].this


def test_date_point_scope_algebra_proves_adjacent_days_are_disjoint():
    previous_day = RowScope.point("stat_date", date(2025, 1, 14))
    current_day = RowScope.point("stat_date", date(2025, 1, 15))

    assert previous_day.overlap(current_day) is Overlap.DISJOINT
    assert previous_day.intersection(current_day).kind is ScopeKind.EMPTY
    assert previous_day.union(current_day) == RowScope.from_points(
        "stat_date", (date(2025, 1, 14), date(2025, 1, 15))
    )
    assert previous_day.is_subset_of(previous_day.union(current_day)) is True


def test_interval_scope_algebra_handles_overlap_and_subset():
    january = RowScope.interval(
        "stat_date", date(2025, 1, 1), date(2025, 2, 1)
    )
    middle = RowScope.interval(
        "stat_date", date(2025, 1, 10), date(2025, 1, 20)
    )
    february = RowScope.interval(
        "stat_date", date(2025, 2, 1), date(2025, 3, 1)
    )

    assert january.overlap(middle) is Overlap.OVERLAP
    assert middle.is_subset_of(january) is True
    assert january.overlap(february) is Overlap.DISJOINT


def test_predicate_scope_handles_between_in_and_typed_scalars():
    between = scope_for_predicate(
        _where(
            "SELECT * FROM t "
            "WHERE stat_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-31'"
        ),
        "stat_date",
        {},
    )
    regions = scope_for_predicate(
        _where("SELECT * FROM t WHERE region_id IN (1, 3, 5)"),
        "region_id",
        {},
    )

    assert between == RowScope.interval(
        "stat_date",
        date(2025, 1, 1),
        date(2025, 1, 31),
        upper_inclusive=True,
    )
    assert regions == RowScope.from_points("region_id", (1, 3, 5))


def test_predicate_scope_folds_if_and_boolean_composition():
    predicate = _where(
        "SELECT * FROM t WHERE "
        "IF(@full_refresh = 1, TRUE, stat_date = @etl_date)"
    )

    assert (
        scope_for_predicate(
            predicate,
            "stat_date",
            {"full_refresh": 1, "etl_date": "2025-01-15"},
        ).kind
        is ScopeKind.ALL
    )
    assert scope_for_predicate(
        predicate,
        "stat_date",
        {"full_refresh": 0, "etl_date": "2025-01-15"},
    ) == RowScope.point("stat_date", date(2025, 1, 15))

    combined = scope_for_predicate(
        _where(
            "SELECT * FROM t WHERE "
            "stat_date >= DATE '2025-01-01' "
            "AND stat_date < DATE '2025-02-01'"
        ),
        "stat_date",
        {},
    )
    assert combined == RowScope.interval(
        "stat_date", date(2025, 1, 1), date(2025, 2, 1)
    )


@pytest.mark.parametrize(
    ("date_format", "expected"),
    [
        ("%Y-%m-%d", (date(2025, 2, 18),)),
        (
            "%Y-%m",
            tuple(date(2025, 2, day) for day in range(1, 29)),
        ),
        (
            "%Y",
            tuple(
                date(2024, 1, 1) + timedelta(days=offset)
                for offset in range(366)
            ),
        ),
    ],
)
def test_predicate_scope_recognizes_supported_date_format_periods(
    date_format, expected
):
    predicate = _where(
        "SELECT * FROM t WHERE "
        f"DATE_FORMAT(stat_date, '{date_format}') = "
        f"DATE_FORMAT(@etl_date, '{date_format}')"
    )

    scope = scope_for_predicate(
        predicate,
        "stat_date",
        {"etl_date": "2025-02-18" if date_format != "%Y" else "2024-06-15"},
        "DATE",
    )

    assert scope == RowScope.from_points("stat_date", expected)


def test_predicate_scope_keeps_date_format_conservative_for_datetime_column():
    predicate = _where(
        "SELECT * FROM t WHERE DATE_FORMAT(event_time, '%Y-%m') = '2025-02'"
    )

    scope = scope_for_predicate(predicate, "event_time", {}, "DATETIME")

    assert scope == RowScope.interval(
        "event_time", date(2025, 2, 1), date(2025, 3, 1)
    )


def test_predicate_scope_keeps_unrepresentable_date_format_period_unknown():
    predicate = _where(
        "SELECT * FROM t WHERE DATE_FORMAT(stat_date, '%Y') = '9999'"
    )

    scope = scope_for_predicate(predicate, "stat_date", {}, "DATE")

    assert scope.kind is ScopeKind.UNKNOWN


def test_unresolved_column_expression_is_unknown_not_empty():
    scope = scope_for_predicate(
        _where("SELECT * FROM t WHERE mystery_bucket(stat_date) = 7"),
        "stat_date",
        {},
    )

    assert scope.kind is ScopeKind.UNKNOWN
    assert "mystery_bucket" in scope.reason.lower()
    assert (
        scope.overlap(RowScope.point("stat_date", date(2025, 1, 15)))
        is Overlap.UNKNOWN
    )


def test_statement_scope_recognizes_self_read_and_existing_row_mutations():
    insert = sqlglot.parse_one(
        "INSERT INTO sales "
        "SELECT * FROM sales "
        "WHERE stat_date = DATE_SUB(@etl_date, INTERVAL 1 DAY)",
        dialect="doris",
    )
    update = sqlglot.parse_one(
        "UPDATE sales SET amount = amount + 1 WHERE stat_date = @etl_date",
        dialect="doris",
    )
    delete_all = sqlglot.parse_one("DELETE FROM sales", dialect="doris")

    insert_access = statement_scope(
        insert, "sales", "stat_date", {"etl_date": "2025-01-15"}
    )
    update_access = statement_scope(
        update, "sales", "stat_date", {"etl_date": "2025-01-15"}
    )
    delete_access = statement_scope(delete_all, "sales", "stat_date", {})

    assert insert_access.read_scope == RowScope.point(
        "stat_date", date(2025, 1, 14)
    )
    assert insert_access.write_scope.kind is ScopeKind.UNKNOWN
    assert insert_access.target_requires_existing is False
    assert update_access.read_scope == RowScope.point(
        "stat_date", date(2025, 1, 15)
    )
    assert update_access.write_scope == update_access.read_scope
    assert update_access.target_requires_existing is True
    assert delete_access.read_scope.kind is ScopeKind.EMPTY
    assert delete_access.write_scope.kind is ScopeKind.ALL
    assert delete_access.target_requires_existing is False


def test_statement_scope_propagates_date_scope_through_left_join_equality():
    insert = sqlglot.parse_one(
        "INSERT INTO report "
        "SELECT s.store_id FROM store_snapshot s "
        "LEFT JOIN sales ss "
        "ON s.store_id = ss.store_id "
        "AND s.snapshot_date = ss.stat_date "
        "WHERE s.snapshot_date = CAST(@etl_date AS DATE)",
        dialect="doris",
    )

    access = statement_scope(
        insert,
        "sales",
        "stat_date",
        {"etl_date": "2025-02-18"},
        "DATE",
    )

    assert access.read_scope == RowScope.point("stat_date", date(2025, 2, 18))
