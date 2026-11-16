from datetime import date

from scrapers.dates import congress_and_session, ordinal, parse_month_day, parse_senate_vote_date


def test_congress_for_known_dates() -> None:
    assert congress_and_session(date(2026, 11, 16)) == (119, 2)
    assert congress_and_session(date(2026, 1, 2)) == (119, 1)
    assert congress_and_session(date(2025, 1, 3)) == (119, 1)
    assert congress_and_session(date(2027, 1, 3)) == (120, 1)


def test_house_and_senate_date_formats() -> None:
    assert parse_month_day("12-Nov", 2026) == date(2026, 11, 12)
    assert parse_month_day("12-Nov-2026", 2026) == date(2026, 11, 12)
    assert parse_senate_vote_date("November 12, 2026,  03:21 PM") == date(2026, 11, 12)


def test_ordinals() -> None:
    assert ordinal(119) == "119th"
    assert ordinal(101) == "101st"
    assert ordinal(112) == "112th"
    assert ordinal(113) == "113th"
