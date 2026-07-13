"""Resolve explicit ETL dates and rolling calendar-month windows."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def _parse_iso_date(value: str, option_name: str) -> date:
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(
            f"{option_name} 日期格式无效 '{value}', 需要 YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != str(value):
        raise ValueError(
            f"{option_name} 日期格式无效 '{value}', 需要 YYYY-MM-DD"
        )
    return parsed


def _subtract_calendar_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def resolve_etl_dates(
    explicit_dates: list[str] | None,
    *,
    lookback_months: int | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> list[str] | None:
    """Return validated ETL dates, expanding a rolling month window."""
    if explicit_dates and lookback_months is not None:
        raise ValueError("--etl-dates 不能与 --etl-lookback-months 同时使用")
    if end_date and lookback_months is None:
        raise ValueError(
            "--etl-end-date 只能与 --etl-lookback-months 一起使用"
        )

    if explicit_dates:
        result: list[str] = []
        seen: set[str] = set()
        for raw_value in explicit_dates:
            value = _parse_iso_date(raw_value, "--etl-dates").isoformat()
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    if lookback_months is None:
        return None
    if lookback_months < 1:
        raise ValueError("--etl-lookback-months 必须 >= 1")

    window_end = (
        _parse_iso_date(end_date, "--etl-end-date")
        if end_date
        else today or date.today()
    )
    window_start = _subtract_calendar_months(window_end, lookback_months)
    days = (window_end - window_start).days
    return [
        (window_start + timedelta(days=offset)).isoformat()
        for offset in range(days + 1)
    ]
