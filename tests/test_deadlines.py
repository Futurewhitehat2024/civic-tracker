from scrapers.deadlines import deadline_items, write_calendar, write_deadlines


def test_deadline_items_and_ics(tmp_path) -> None:
    feed = {
        "items": [
            {
                "id": "fr-2026-10001",
                "title": "Proposed tariff rule",
                "url": "https://www.federalregister.gov/documents/2026/11/12/2026-10001/example",
                "source": "Federal Register",
                "documentType": "Proposed Rule",
                "commentsCloseOn": "2026-12-15",
                "effectiveOn": "2027-01-01",
                "tags": ["tariff"],
                "jurisdiction": {"level": "federal", "state": None, "countyFips": None},
            },
            {
                "id": "hr-1-119",
                "title": "A bill",
                "commentsCloseOn": None,
            },
        ]
    }
    items = deadline_items(feed)
    assert [item["id"] for item in items] == [
        "fr-2026-10001-effective",
        "fr-2026-10001-comment-due",
    ]
    # Newer deadline first after the date sort used by the store helper (descending).
    assert items[0]["date"] == "2027-01-01"
    assert items[1]["date"] == "2026-12-15"
    assert items[1]["kind"] == "comment_due"
    path = tmp_path / "deadlines.json"
    write_deadlines(path, items, updated="2026-11-25T21:00:00-05:00")
    calendar = write_calendar(tmp_path / "deadlines.ics", items)
    assert "BEGIN:VCALENDAR" in calendar
    assert "COMMENT-DUE" not in calendar  # kind is comment_due
    assert "CATEGORIES:comment_due" in calendar
    assert "DTSTART;VALUE=DATE:20261215" in calendar
    assert "SUMMARY:Comment due: Proposed tariff rule" in calendar
    # Regenerating the same items must not change DTSTAMP.
    again = write_calendar(tmp_path / "deadlines.ics", items)
    assert again == calendar
