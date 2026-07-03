"""Shared time period normalization helpers for model metadata."""

from __future__ import annotations

from typing import Any

VALID_TIME_PERIODS = ("D", "W", "M", "Q", "Y", "S")
_VALID_TIME_PERIOD_SET = set(VALID_TIME_PERIODS)

TIME_PERIOD_ALIASES = {
    "1D": "D",
    "DAY": "D",
    "DAILY": "D",
    "D": "D",
    "日": "D",
    "日度": "D",
    "天": "D",
    "每日": "D",
    "1W": "W",
    "WEEK": "W",
    "WEEKLY": "W",
    "W": "W",
    "周": "W",
    "周度": "W",
    "星期": "W",
    "每周": "W",
    "1M": "M",
    "MONTH": "M",
    "MONTHLY": "M",
    "M": "M",
    "月": "M",
    "月度": "M",
    "自然月": "M",
    "每月": "M",
    "1Q": "Q",
    "QUARTER": "Q",
    "QUARTERLY": "Q",
    "Q": "Q",
    "季": "Q",
    "季度": "Q",
    "每季": "Q",
    "1Y": "Y",
    "YEAR": "Y",
    "YEARLY": "Y",
    "Y": "Y",
    "年": "Y",
    "年度": "Y",
    "每年": "Y",
    "SNAPSHOT": "S",
    "SNAP": "S",
    "S": "S",
    "快照": "S",
}


def normalize_time_period(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    key = text.upper().replace(" ", "").replace("_", "").replace("-", "")
    if key in _VALID_TIME_PERIOD_SET:
        return key
    if key in TIME_PERIOD_ALIASES:
        return TIME_PERIOD_ALIASES[key]
    if key.startswith("1"):
        suffix = key[1:]
        if suffix in _VALID_TIME_PERIOD_SET:
            return suffix
        if suffix in TIME_PERIOD_ALIASES:
            return TIME_PERIOD_ALIASES[suffix]
    return ""


def is_canonical_time_period(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or text in _VALID_TIME_PERIOD_SET
