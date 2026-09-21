"""Reporting window arithmetic.

The digest is stateless: every run recomputes the window from the calendar.
Default is the previous ISO week (Monday..Sunday) relative to "today" in
Cyprus time, which is what a Monday-morning scheduled run wants.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

CY_TZ = ZoneInfo("Asia/Nicosia")


@dataclass(frozen=True)
class Window:
    start: dt.date  # inclusive
    end: dt.date    # inclusive

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"

    @property
    def human_ru(self) -> str:
        return f"{self.start.strftime('%d.%m.%Y')} – {self.end.strftime('%d.%m.%Y')}"

    def contains(self, d: dt.date | dt.datetime | None) -> bool:
        if d is None:
            return False
        if isinstance(d, dt.datetime):
            d = d.date()
        return self.start <= d <= self.end

    # ISO datetimes for WP REST API filters (site-local time is Cyprus time)
    @property
    def iso_after(self) -> str:
        return f"{self.start.isoformat()}T00:00:00"

    @property
    def iso_before(self) -> str:
        return f"{self.end.isoformat()}T23:59:59"


def today_cy() -> dt.date:
    return dt.datetime.now(CY_TZ).date()


def previous_week(today: dt.date | None = None) -> Window:
    today = today or today_cy()
    this_monday = today - dt.timedelta(days=today.weekday())
    start = this_monday - dt.timedelta(days=7)
    return Window(start, start + dt.timedelta(days=6))


def current_week(today: dt.date | None = None) -> Window:
    today = today or today_cy()
    start = today - dt.timedelta(days=today.weekday())
    return Window(start, today)


def last_days(n: int, today: dt.date | None = None) -> Window:
    today = today or today_cy()
    return Window(today - dt.timedelta(days=n - 1), today)


def explicit(start: str, end: str) -> Window:
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    if e < s:
        raise ValueError("window end before start")
    return Window(s, e)
