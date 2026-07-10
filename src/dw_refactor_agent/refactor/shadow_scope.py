"""Typed row-scope analysis for shadow execution planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from sqlglot import exp


class ScopeKind(Enum):
    EMPTY = "empty"
    ALL = "all"
    POINTS = "points"
    INTERVALS = "intervals"
    UNKNOWN = "unknown"


class Overlap(Enum):
    DISJOINT = "disjoint"
    OVERLAP = "overlap"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Interval:
    lower: Any = None
    upper: Any = None
    lower_inclusive: bool = True
    upper_inclusive: bool = False


def _value_type(value: Any) -> str:
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, str):
        return "string"
    return "unknown"


def _scope_type(values: tuple[Any, ...]) -> str:
    types = {_value_type(value) for value in values if value is not None}
    return types.pop() if len(types) == 1 else "unknown"


def _canonical(name: str) -> str:
    return name.casefold()


def _compare(left: Any, right: Any) -> Optional[int]:
    try:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    except TypeError:
        return None


def _point_in_interval(value: Any, interval: Interval) -> Optional[bool]:
    if interval.lower is not None:
        comparison = _compare(value, interval.lower)
        if comparison is None:
            return None
        if comparison < 0 or (
            comparison == 0 and not interval.lower_inclusive
        ):
            return False
    if interval.upper is not None:
        comparison = _compare(value, interval.upper)
        if comparison is None:
            return None
        if comparison > 0 or (
            comparison == 0 and not interval.upper_inclusive
        ):
            return False
    return True


def _intersect_interval(left: Interval, right: Interval) -> Optional[Interval]:
    lower = left.lower
    lower_inclusive = left.lower_inclusive
    if lower is None:
        lower, lower_inclusive = right.lower, right.lower_inclusive
    elif right.lower is not None:
        comparison = _compare(lower, right.lower)
        if comparison is None:
            return None
        if comparison < 0:
            lower, lower_inclusive = right.lower, right.lower_inclusive
        elif comparison == 0:
            lower_inclusive = lower_inclusive and right.lower_inclusive

    upper = left.upper
    upper_inclusive = left.upper_inclusive
    if upper is None:
        upper, upper_inclusive = right.upper, right.upper_inclusive
    elif right.upper is not None:
        comparison = _compare(upper, right.upper)
        if comparison is None:
            return None
        if comparison > 0:
            upper, upper_inclusive = right.upper, right.upper_inclusive
        elif comparison == 0:
            upper_inclusive = upper_inclusive and right.upper_inclusive

    if lower is not None and upper is not None:
        comparison = _compare(lower, upper)
        if comparison is None:
            return None
        if comparison > 0:
            return Interval(1, 0)
        if comparison == 0 and not (lower_inclusive and upper_inclusive):
            return Interval(1, 0)
    return Interval(lower, upper, lower_inclusive, upper_inclusive)


def _interval_is_empty(interval: Interval) -> bool:
    if interval.lower == 1 and interval.upper == 0:
        return True
    if interval.lower is None or interval.upper is None:
        return False
    comparison = _compare(interval.lower, interval.upper)
    if comparison is None:
        return False
    return comparison > 0 or (
        comparison == 0
        and not (interval.lower_inclusive and interval.upper_inclusive)
    )


def _interval_subset(left: Interval, right: Interval) -> Optional[bool]:
    intersection = _intersect_interval(left, right)
    if intersection is None:
        return None
    return intersection == left


@dataclass(frozen=True)
class RowScope:
    column: str
    value_type: str
    kind: ScopeKind
    points: tuple[Any, ...] = ()
    intervals: tuple[Interval, ...] = ()
    reason: str = ""

    @classmethod
    def empty(cls, column: str) -> "RowScope":
        return cls(column, "unknown", ScopeKind.EMPTY)

    @classmethod
    def all(cls, column: str) -> "RowScope":
        return cls(column, "unknown", ScopeKind.ALL)

    @classmethod
    def unknown(cls, column: str, reason: str) -> "RowScope":
        return cls(column, "unknown", ScopeKind.UNKNOWN, reason=reason)

    @classmethod
    def point(cls, column: str, value: Any) -> "RowScope":
        return cls.from_points(column, (value,))

    @classmethod
    def from_points(cls, column: str, values: tuple[Any, ...]) -> "RowScope":
        unique = tuple(sorted(set(values)))
        if not unique:
            return cls.empty(column)
        return cls(
            column, _scope_type(unique), ScopeKind.POINTS, points=unique
        )

    @classmethod
    def interval(
        cls,
        column: str,
        lower: Any = None,
        upper: Any = None,
        *,
        lower_inclusive: bool = True,
        upper_inclusive: bool = False,
    ) -> "RowScope":
        interval = Interval(lower, upper, lower_inclusive, upper_inclusive)
        if _interval_is_empty(interval):
            return cls.empty(column)
        return cls(
            column,
            _scope_type((lower, upper)),
            ScopeKind.INTERVALS,
            intervals=(interval,),
        )

    def _compatible(self, other: "RowScope") -> bool:
        return _canonical(self.column) == _canonical(other.column)

    def intersection(self, other: "RowScope") -> "RowScope":
        if not self._compatible(other):
            return RowScope.unknown(self.column, "scope columns differ")
        if self.kind is ScopeKind.EMPTY or other.kind is ScopeKind.EMPTY:
            return RowScope.empty(self.column)
        if self.kind is ScopeKind.UNKNOWN or other.kind is ScopeKind.UNKNOWN:
            return RowScope.unknown(
                self.column, "intersection includes unknown"
            )
        if self.kind is ScopeKind.ALL:
            return other
        if other.kind is ScopeKind.ALL:
            return self

        points = []
        if self.points and other.points:
            points.extend(set(self.points).intersection(other.points))
        for value in self.points:
            if any(
                _point_in_interval(value, item) is True
                for item in other.intervals
            ):
                points.append(value)
        for value in other.points:
            if any(
                _point_in_interval(value, item) is True
                for item in self.intervals
            ):
                points.append(value)

        intervals = []
        for left in self.intervals:
            for right in other.intervals:
                item = _intersect_interval(left, right)
                if item is None:
                    return RowScope.unknown(
                        self.column, "interval values are not comparable"
                    )
                if not _interval_is_empty(item):
                    intervals.append(item)
        return _from_parts(self.column, tuple(points), tuple(intervals))

    def union(self, other: "RowScope") -> "RowScope":
        if not self._compatible(other):
            return RowScope.unknown(self.column, "scope columns differ")
        if self.kind is ScopeKind.UNKNOWN or other.kind is ScopeKind.UNKNOWN:
            return RowScope.unknown(self.column, "union includes unknown")
        if self.kind is ScopeKind.ALL or other.kind is ScopeKind.ALL:
            return RowScope.all(self.column)
        if self.kind is ScopeKind.EMPTY:
            return other
        if other.kind is ScopeKind.EMPTY:
            return self
        return _from_parts(
            self.column,
            self.points + other.points,
            self.intervals + other.intervals,
        )

    def overlap(self, other: "RowScope") -> Overlap:
        intersection = self.intersection(other)
        if intersection.kind is ScopeKind.UNKNOWN:
            return Overlap.UNKNOWN
        if intersection.kind is ScopeKind.EMPTY:
            return Overlap.DISJOINT
        return Overlap.OVERLAP

    def is_subset_of(self, other: "RowScope") -> Optional[bool]:
        if not self._compatible(other):
            return None
        if self.kind is ScopeKind.EMPTY:
            return True
        if other.kind is ScopeKind.ALL:
            return True
        if self.kind is ScopeKind.UNKNOWN or other.kind is ScopeKind.UNKNOWN:
            return None
        if other.kind is ScopeKind.EMPTY:
            return False
        if self.kind is ScopeKind.ALL:
            return other.kind is ScopeKind.ALL

        for value in self.points:
            if value in other.points:
                continue
            membership = [
                _point_in_interval(value, item) for item in other.intervals
            ]
            if any(result is None for result in membership):
                return None
            if not any(membership):
                return False
        for interval in self.intervals:
            subsets = [
                _interval_subset(interval, item) for item in other.intervals
            ]
            if any(result is None for result in subsets):
                return None
            if not any(subsets):
                return False
        return True


@dataclass(frozen=True)
class StatementScope:
    read_scope: RowScope
    write_scope: RowScope
    target_requires_existing: bool = False


def _from_parts(
    column: str,
    points: tuple[Any, ...],
    intervals: tuple[Interval, ...],
) -> RowScope:
    unique_points = []
    for value in sorted(set(points)):
        if not any(
            _point_in_interval(value, item) is True for item in intervals
        ):
            unique_points.append(value)
    if intervals:
        values = tuple(
            bound
            for item in intervals
            for bound in (item.lower, item.upper)
            if bound is not None
        )
        return RowScope(
            column,
            _scope_type(values + tuple(unique_points)),
            ScopeKind.INTERVALS,
            points=tuple(unique_points),
            intervals=intervals,
        )
    return RowScope.from_points(column, tuple(unique_points))


def _column_matches(node: exp.Expression, column: str) -> bool:
    return isinstance(node, exp.Column) and _canonical(
        node.name
    ) == _canonical(column)


def _contains_column(node: exp.Expression, column: str) -> bool:
    return any(
        _column_matches(item, column) for item in node.find_all(exp.Column)
    )


def _coerce_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        if "T" in value or " " in value:
            return datetime.fromisoformat(value)
        return date.fromisoformat(value)
    except ValueError:
        return value


def _parameter_name(node: exp.Parameter) -> str:
    value = node.this
    return value.name if isinstance(value, exp.Var) else str(value)


def _cast_value(value: Any, target: exp.Expression) -> Any:
    type_name = target.sql().upper()
    if type_name == "DATE":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
    if type_name.startswith("DATETIME"):
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    if type_name in {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT"}:
        return int(value)
    return value


def _eval_value(
    node: exp.Expression, params: dict[str, Any]
) -> tuple[bool, Any]:
    if isinstance(node, exp.Paren):
        return _eval_value(node.this, params)
    if isinstance(node, exp.Parameter):
        name = _parameter_name(node)
        for key, value in params.items():
            if _canonical(str(key).lstrip("@")) == _canonical(name):
                return True, _coerce_scalar(value)
        return False, None
    if isinstance(node, exp.Boolean):
        return True, bool(node.this)
    if isinstance(node, exp.Null):
        return True, None
    if isinstance(node, exp.Literal):
        if node.is_string:
            return True, _coerce_scalar(node.this)
        text = str(node.this)
        try:
            return True, int(text)
        except ValueError:
            try:
                return True, float(text)
            except ValueError:
                return False, None
    if isinstance(node, exp.Cast):
        resolved, value = _eval_value(node.this, params)
        if not resolved:
            return False, None
        try:
            return True, _cast_value(value, node.args["to"])
        except (TypeError, ValueError):
            return False, None
    if isinstance(node, (exp.DateAdd, exp.DateSub)):
        resolved, value = _eval_value(node.this, params)
        amount_ok, amount = _eval_value(node.expression, params)
        unit = str(node.args.get("unit") or "DAY").upper()
        if not resolved or not amount_ok or unit != "DAY":
            return False, None
        delta = timedelta(days=int(amount))
        return True, value - delta if isinstance(
            node, exp.DateSub
        ) else value + delta
    if isinstance(node, exp.Neg):
        resolved, value = _eval_value(node.this, params)
        return (True, -value) if resolved else (False, None)
    if isinstance(node, exp.If):
        resolved, condition = _eval_value(node.this, params)
        if not resolved:
            return False, None
        branch = node.args["true"] if condition else node.args.get("false")
        return _eval_value(branch, params)
    if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
        left_ok, left = _eval_value(node.this, params)
        right_ok, right = _eval_value(node.expression, params)
        if not left_ok or not right_ok:
            return False, None
        comparison = _compare(left, right)
        if comparison is None:
            return False, None
        operations = {
            exp.EQ: comparison == 0,
            exp.NEQ: comparison != 0,
            exp.GT: comparison > 0,
            exp.GTE: comparison >= 0,
            exp.LT: comparison < 0,
            exp.LTE: comparison <= 0,
        }
        return True, operations[type(node)]
    if isinstance(node, exp.And):
        left_ok, left = _eval_value(node.this, params)
        right_ok, right = _eval_value(node.expression, params)
        return (
            (True, bool(left and right))
            if left_ok and right_ok
            else (False, None)
        )
    if isinstance(node, exp.Or):
        left_ok, left = _eval_value(node.this, params)
        right_ok, right = _eval_value(node.expression, params)
        return (
            (True, bool(left or right))
            if left_ok and right_ok
            else (False, None)
        )
    return False, None


def _comparison_scope(
    predicate: exp.Expression,
    column: str,
    params: dict[str, Any],
) -> RowScope:
    left = predicate.this
    right = predicate.expression
    reverse = False
    if _column_matches(left, column):
        value_node = right
    elif _column_matches(right, column):
        value_node = left
        reverse = True
    elif _contains_column(predicate, column):
        return RowScope.unknown(column, predicate.sql(dialect="doris"))
    else:
        return RowScope.all(column)

    resolved, value = _eval_value(value_node, params)
    if not resolved:
        return RowScope.unknown(column, predicate.sql(dialect="doris"))
    operation = type(predicate)
    if reverse:
        operation = {
            exp.GT: exp.LT,
            exp.GTE: exp.LTE,
            exp.LT: exp.GT,
            exp.LTE: exp.GTE,
        }.get(operation, operation)
    if operation is exp.EQ:
        return RowScope.point(column, value)
    if operation is exp.GT:
        return RowScope.interval(column, value, lower_inclusive=False)
    if operation is exp.GTE:
        return RowScope.interval(column, value, lower_inclusive=True)
    if operation is exp.LT:
        return RowScope.interval(column, upper=value, upper_inclusive=False)
    if operation is exp.LTE:
        return RowScope.interval(column, upper=value, upper_inclusive=True)
    return RowScope.unknown(column, predicate.sql(dialect="doris"))


def scope_for_predicate(
    predicate: exp.Expression,
    column: str,
    params: Optional[dict[str, Any]] = None,
) -> RowScope:
    """Return the rows selected by *predicate* along *column*.

    The analysis is intentionally conservative: an expression involving the
    tracked column that cannot be constant-folded produces UNKNOWN.
    """
    params = params or {}
    if isinstance(predicate, exp.Paren):
        return scope_for_predicate(predicate.this, column, params)
    if isinstance(predicate, exp.Boolean):
        return (
            RowScope.all(column) if predicate.this else RowScope.empty(column)
        )
    if isinstance(predicate, exp.And):
        return scope_for_predicate(
            predicate.this, column, params
        ).intersection(
            scope_for_predicate(predicate.expression, column, params)
        )
    if isinstance(predicate, exp.Or):
        return scope_for_predicate(predicate.this, column, params).union(
            scope_for_predicate(predicate.expression, column, params)
        )
    if isinstance(predicate, exp.If):
        resolved, condition = _eval_value(predicate.this, params)
        if not resolved:
            return RowScope.unknown(column, predicate.sql(dialect="doris"))
        branch = (
            predicate.args["true"]
            if condition
            else predicate.args.get("false")
        )
        if branch is None:
            return RowScope.empty(column)
        return scope_for_predicate(branch, column, params)
    if isinstance(
        predicate, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)
    ):
        return _comparison_scope(predicate, column, params)
    if isinstance(predicate, exp.Between):
        if not _column_matches(predicate.this, column):
            if _contains_column(predicate, column):
                return RowScope.unknown(column, predicate.sql(dialect="doris"))
            return RowScope.all(column)
        low_ok, low = _eval_value(predicate.args["low"], params)
        high_ok, high = _eval_value(predicate.args["high"], params)
        if not low_ok or not high_ok:
            return RowScope.unknown(column, predicate.sql(dialect="doris"))
        return RowScope.interval(
            column, low, high, lower_inclusive=True, upper_inclusive=True
        )
    if isinstance(predicate, exp.In):
        if not _column_matches(predicate.this, column):
            if _contains_column(predicate, column):
                return RowScope.unknown(column, predicate.sql(dialect="doris"))
            return RowScope.all(column)
        values = []
        for item in predicate.expressions:
            resolved, value = _eval_value(item, params)
            if not resolved:
                return RowScope.unknown(column, predicate.sql(dialect="doris"))
            values.append(value)
        return RowScope.from_points(column, tuple(values))

    resolved, value = _eval_value(predicate, params)
    if resolved:
        return RowScope.all(column) if value else RowScope.empty(column)
    if _contains_column(predicate, column):
        return RowScope.unknown(column, predicate.sql(dialect="doris"))
    return RowScope.all(column)


def _target_table(statement: exp.Expression) -> Optional[exp.Table]:
    target = statement.this
    if isinstance(target, exp.Schema):
        target = target.this
    return target if isinstance(target, exp.Table) else None


def _same_table(table: exp.Table, name: str) -> bool:
    return _canonical(table.name) == _canonical(name)


def _predicate_scope(
    statement: exp.Expression,
    table: str,
    column: str,
    params: dict[str, Any],
) -> RowScope:
    where = statement.find(exp.Where)
    if where is None:
        return RowScope.all(column)
    physical_tables = list(statement.find_all(exp.Table))
    physical_relation_keys = {
        (_canonical(relation.db), _canonical(relation.name))
        for relation in physical_tables
    }
    qualifiers = {_canonical(table)}
    for relation in physical_tables:
        if not _same_table(relation, table):
            continue
        qualifiers.add(_canonical(relation.name))
        if relation.alias_or_name:
            qualifiers.add(_canonical(relation.alias_or_name))
    matching_columns = [
        item
        for item in where.find_all(exp.Column)
        if _canonical(item.name) == _canonical(column)
    ]
    same_name_relations = {
        (_canonical(relation.db), _canonical(relation.name))
        for relation in physical_tables
        if _same_table(relation, table)
    }
    if matching_columns and len(same_name_relations) > 1:
        return RowScope.unknown(
            column,
            "same short table name is present in multiple databases",
        )
    for item in matching_columns:
        if item.table and _canonical(item.table) not in qualifiers:
            return RowScope.unknown(
                column,
                f"partition column is qualified by another relation: {item.sql()}",
            )
        if not item.table and len(physical_relation_keys) > 1:
            return RowScope.unknown(
                column,
                "unqualified partition column is ambiguous across relations",
            )
    return scope_for_predicate(where.this, column, params)


def statement_scope(
    statement: exp.Expression,
    table: str,
    column: str,
    params: Optional[dict[str, Any]] = None,
) -> StatementScope:
    """Describe one statement's data access to a physical table.

    INSERT projections are not assumed to preserve a partition column, so their
    write scope remains UNKNOWN unless a later planner supplies model coverage.
    """
    params = params or {}
    target = _target_table(statement)
    is_target = target is not None and _same_table(target, table)
    sources = [
        item
        for item in statement.find_all(exp.Table)
        if item is not target and _same_table(item, table)
    ]

    if isinstance(statement, exp.Delete) and is_target:
        where = statement.args.get("where")
        if where is None:
            return StatementScope(
                RowScope.empty(column), RowScope.all(column), False
            )
        scope = _predicate_scope(statement, table, column, params)
        return StatementScope(scope, scope, True)

    if isinstance(statement, exp.Update) and is_target:
        scope = _predicate_scope(statement, table, column, params)
        return StatementScope(scope, scope, True)

    if isinstance(statement, exp.TruncateTable) and is_target:
        return StatementScope(
            RowScope.empty(column), RowScope.all(column), False
        )

    if isinstance(statement, exp.Insert) and is_target:
        read_scope = (
            _predicate_scope(statement, table, column, params)
            if sources
            else RowScope.empty(column)
        )
        return StatementScope(
            read_scope,
            RowScope.unknown(column, "INSERT projection coverage is unknown"),
            False,
        )

    read_scope = (
        _predicate_scope(statement, table, column, params)
        if sources
        or (
            not is_target
            and any(
                _same_table(item, table)
                for item in statement.find_all(exp.Table)
            )
        )
        else RowScope.empty(column)
    )
    return StatementScope(read_scope, RowScope.empty(column), False)
