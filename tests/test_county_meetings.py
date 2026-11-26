from scrapers.runner import parse_sources
from scrapers.sources.county_meetings import COLLIER, map_event, run_county_meetings
from scrapers.store import load_feed
from tests.support import make_context


class RouteClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get_json(self, url: str, *, params=None, headers=None) -> dict:
        self.urls.append(url)
        return self.payload


def test_parse_sources_keeps_counties_out_of_all() -> None:
    assert "collier-meetings" not in parse_sources("all")
    assert parse_sources("counties") == ["collier-meetings", "lee-meetings"]


def test_map_event_sets_county_jurisdiction() -> None:
    item = map_event(
        {
            "id": 1507,
            "eventName": "Board of County Commissioners Meeting",
            "eventDescription": "Regular meeting",
            "startDateTime": "2026-01-27T14:00:00Z",
            "isPublished": "Published",
            "isDeleted": False,
            "meetingTypeName": "Regular Meeting",
        },
        COLLIER,
    )
    assert item is not None
    assert item["id"] == "fl-collier-1507"
    assert item["kind"] == "meeting"
    assert item["date"] == "2026-01-27"
    assert item["url"] == "https://colliercofl.portal.civicclerk.com/event/1507"
    assert item["jurisdiction"] == {
        "level": "county",
        "state": "FL",
        "countyFips": "12021",
    }


def test_map_event_skips_unpublished_and_deleted() -> None:
    unpublished = map_event(
        {
            "id": 1,
            "eventName": "Draft",
            "startDateTime": "2026-01-27T14:00:00Z",
            "isPublished": "Draft",
        },
        COLLIER,
    )
    deleted = map_event(
        {
            "id": 2,
            "eventName": "Gone",
            "startDateTime": "2026-01-27T14:00:00Z",
            "isPublished": "Published",
            "isDeleted": True,
        },
        COLLIER,
    )
    assert unpublished is None
    assert deleted is None


def test_county_collector_publishes_meetings(tmp_path) -> None:
    client = RouteClient(
        {
            "value": [
                {
                    "id": 9,
                    "eventName": "Tourist Development Council Meeting",
                    "eventDescription": "",
                    "startDateTime": "2026-11-20T14:00:00Z",
                    "isPublished": "Published",
                    "isDeleted": False,
                    "meetingTypeName": "Meeting",
                    "eventCategoryName": "Tourist Development Council",
                }
            ]
        }
    )
    ctx = make_context(tmp_path, client)
    outcome = run_county_meetings(ctx, COLLIER)
    assert outcome.records == 1
    assert outcome.errors == []
    feed = load_feed(tmp_path / "counties.json")
    assert feed["items"][0]["id"] == "fl-collier-9"
    assert "colliercofl.api.civicclerk.com" in client.urls[0]
