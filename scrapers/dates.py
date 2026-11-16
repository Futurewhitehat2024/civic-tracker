"""Date helpers shared by the scrapers. The clock for 'today' is America/New_York."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def today_et() -> date:
    return datetime.now(ET).date()


def now_iso() -> str:
    return datetime.now(ET).isoformat(timespec="seconds")


def parse_cli_date(value: str | None, flag: str) -> date | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f"{flag} must be YYYY-MM-DD, got {raw!r}") from exc


def congress_and_session(day: date) -> tuple[int, int]:
    """Return (congress, session) for a calendar date.

    A congress begins on January 3 of an odd year. January 1 and 2 still
    belong to the previous congress.
    """
    year = day.year
    if (day.month, day.day) < (1, 3):
        year -= 1
    if year % 2 == 0:
        start_year = year - 1
        session = 2
    else:
        start_year = year
        session = 1
    congress = (start_year - 1789) // 2 + 1
    return congress, session


def sessions_covering(start: date, end: date) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    day = start
    while day <= end:
        pair = congress_and_session(day)
        if not found or found[-1] != pair:
            found.append(pair)
        day += timedelta(days=1)
    return found


def parse_month_day(value: str, year: int) -> date:
    """Parse '12-Nov' or '12-Nov-2026'."""
    parts = value.strip().split("-")
    if len(parts) == 3:
        day_text, month_text, year_text = parts
        year = int(year_text)
    elif len(parts) == 2:
        day_text, month_text = parts
    else:
        raise ValueError(f"unrecognized date {value!r}")
    month = _MONTHS.get(month_text[:3].lower())
    if month is None:
        raise ValueError(f"unrecognized month in {value!r}")
    return date(year, month, int(day_text))


def parse_senate_vote_date(value: str) -> date:
    """Parse 'November 12, 2026,  03:21 PM' down to a day."""
    head = value.split(",")[0].strip()
    month_text, day_text = head.split()
    year_text = value.split(",")[1].strip().split()[0]
    month = _MONTHS.get(month_text[:3].lower())
    if month is None:
        raise ValueError(f"unrecognized Senate vote date {value!r}")
    return date(int(year_text), month, int(day_text))


def ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"
