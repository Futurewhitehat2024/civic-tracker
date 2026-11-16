from scrapers.redact import redact, strip_api_key
from scrapers.store import load_feed, load_state, save_state, touch_feed, upsert_items
from scrapers.validate import validate_federal


def test_redact_strips_key_from_text_and_query() -> None:
    secret = "abc123secret"
    text = f"failed https://api.congress.gov/v3/bill?limit=1&api_key={secret} token {secret}"
    cleaned = redact(text, [secret])
    assert secret not in cleaned
    assert "api_key=[REDACTED]" in cleaned


def test_strip_api_key_keeps_other_query_params() -> None:
    url = "https://api.congress.gov/v3/bill/119/hr/1?format=json&api_key=abc123"
    assert strip_api_key(url) == "https://api.congress.gov/v3/bill/119/hr/1?format=json"


def test_upsert_is_idempotent_and_sorts_newest_first(tmp_path) -> None:
    path = tmp_path / "federal.json"
    first = [
        {
            "id": "fr-1",
            "kind": "federal_register",
            "title": "Older",
            "date": "2026-11-01",
            "url": "https://www.federalregister.gov/documents/1",
            "source": "Federal Register",
            "summary": None,
            "identifier": "1",
            "chamber": None,
        },
        {
            "id": "fr-2",
            "kind": "federal_register",
            "title": "Newer",
            "date": "2026-11-02",
            "url": "https://www.federalregister.gov/documents/2",
            "source": "Federal Register",
            "summary": None,
            "identifier": "2",
            "chamber": None,
        },
    ]
    upsert_items(path, first, updated="2026-11-16T10:00:00-05:00", date_key="date")
    again = dict(first[0])
    again["title"] = "Older revised"
    upsert_items(path, [again], updated="2026-11-16T11:00:00-05:00", date_key="date")
    upsert_items(path, [again], updated="2026-11-16T12:00:00-05:00", date_key="date")
    feed = load_feed(path)
    assert [item["id"] for item in feed["items"]] == ["fr-2", "fr-1"]
    assert feed["items"][1]["title"] == "Older revised"
    assert sum(1 for item in feed["items"] if item["id"] == "fr-1") == 1


def test_cursor_round_trip(tmp_path) -> None:
    path = tmp_path / "state" / "federal-register.json"
    save_state(path, {"completed_through": "2026-11-15", "tasks": [{"page": 2}]})
    assert load_state(path)["tasks"] == [{"page": 2}]


def test_validate_federal_strips_api_key_and_rejects_bad_urls() -> None:
    try:
        validate_federal(
            {
                "id": "hr-1-119",
                "kind": "bill",
                "title": "Example",
                "date": "2026-11-01",
                "url": "javascript:alert(1)",
                "source": "Congress.gov",
                "chamber": "house",
            }
        )
    except ValueError as exc:
        assert "http" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    cleaned = validate_federal(
        {
            "id": "hr-1-119",
            "kind": "bill",
            "title": "Example",
            "date": "2026-11-01T00:00:00Z",
            "url": "https://www.congress.gov/bill/119th-congress/house-bill/1?format=json&api_key=sekret",
            "source": "Congress.gov",
            "chamber": "house",
        }
    )
    assert "api_key" not in cleaned["url"]
    assert cleaned["date"] == "2026-11-01"


def test_touch_keeps_items(tmp_path) -> None:
    path = tmp_path / "federal.json"
    upsert_items(
        path,
        [
            {
                "id": "a",
                "kind": "vote",
                "title": "Roll",
                "date": "2026-11-12",
                "url": "https://clerk.house.gov/evs/2026/roll001.xml",
                "source": "House Clerk",
                "summary": None,
                "identifier": "Roll 1",
                "chamber": "house",
            }
        ],
        updated="2026-11-16T10:00:00-05:00",
        date_key="date",
    )
    touch_feed(path, updated="2026-11-16T12:00:00-05:00", date_key="date")
    feed = load_feed(path)
    assert feed["updated"] == "2026-11-16T12:00:00-05:00"
    assert feed["items"][0]["id"] == "a"
