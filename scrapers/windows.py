"""Decide the date window for a source, including an interrupted resume."""

from datetime import date, timedelta

from scrapers.config import DEFAULT_LOOKBACK_DAYS
from scrapers.context import RunContext


def resolve_window(state: dict, ctx: RunContext) -> tuple[date, date]:
    if ctx.cli_start or ctx.cli_end:
        end = ctx.cli_end or ctx.today
        start = ctx.cli_start or end - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)
    else:
        end = ctx.today
        completed = state.get("completed_through")
        if isinstance(completed, str) and completed:
            start = date.fromisoformat(completed)
        else:
            start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)
    if start > end:
        raise SystemExit("--from is after --to")
    return start, end


def window_key(start: date, end: date) -> list[str]:
    return [start.isoformat(), end.isoformat()]


def split_range(start: date, end: date) -> tuple[tuple[date, date], tuple[date, date]] | None:
    """Split a date span in half. A single day cannot be split."""
    if start >= end:
        return None
    mid = start + timedelta(days=(end - start).days // 2)
    if mid < start or mid >= end:
        return None
    return (start, mid), (mid + timedelta(days=1), end)
