import json
from datetime import date
from pathlib import Path

import pytest

import scrapers.runner as runner
from scrapers.context import Outcome
from scrapers.runner import parse_sources, run_sources
from scrapers.sources.congress_bills import map_bill, run_congress_bills
from scrapers.sources.federal_register import run_federal_register
from scrapers.sources.house_votes import parse_house_vote, run_house_votes
from scrapers.sources.senate_votes import parse_senate_vote, run_senate_votes
from scrapers.store import load_feed, load_state, save_state
from tests.support import make_context

FIXTURES = Path(__file__).parent / "fixtures"
SECRET = "test-key-should-not-leak"


class RouteClient:
    def __init__(self, routes: dict[str, str | dict]):
        self.routes = routes
        self.calls: list[tuple[str, object]] = []
        self.secrets: list[str] = []

    def get_text(self, url: str, *, params=None, headers=None) -> str:
        self.calls.append((url, params))
        for fragment, body in self.routes.items():
            if fragment in url:
                if not isinstance(body, str):
                    raise AssertionError(f"expected text for {url}")
                return body
        raise AssertionError(f"unexpected URL {url}")

    def get_json(self, url: str, *, params=None, headers=None) -> dict:
        self.calls.append((url, params))
        for fragment, body in self.routes.items():
            if fragment in url:
                if not isinstance(body, dict):
                    raise AssertionError(f"expected JSON for {url}")
                return body
        raise AssertionError(f"unexpected URL {url}")


def _document(number: str, *, kind: str = "rule") -> dict:
    if kind == "eo":
        return {
            "document_number": number,
            "title": "An executive order",
            "type": "Presidential Document",
            "subtype": "Executive Order",
            "executive_order_number": "14438",
            "publication_date": "2026-11-12",
            "html_url": f"https://www.federalregister.gov/documents/2026/11/12/{number}/example",
            "abstract": None,
            "citation": "91 FR 1",
        }
    return {
        "document_number": number,
        "title": "A proposed rule",
        "type": "Proposed Rule",
        "subtype": None,
        "executive_order_number": None,
        "publication_date": "2026-11-12",
        "html_url": f"https://www.federalregister.gov/documents/2026/11/12/{number}/example",
        "abstract": "<p>Comment by Friday.</p>",
        "citation": "91 FR 2",
    }


def _page(results: list[dict], count: int | None = None) -> dict:
    return {"count": len(results) if count is None else count, "results": results}


def test_parse_sources_accepts_groups_and_rejects_unknown() -> None:
    assert parse_sources("federal") == [
        "federal-register",
        "house-votes",
        "senate-votes",
        "congress-bills",
    ]
    assert parse_sources("house-votes, senate-votes") == ["house-votes", "senate-votes"]
    assert parse_sources("trades") == ["house-ptr", "senate-efd"]
    with pytest.raises(SystemExit):
        parse_sources("not-a-source")


def test_federal_register_maps_rules_and_orders_and_rerun_is_stable(tmp_path) -> None:
    client = RouteClient(
        {
            "federalregister.gov": _page(
                [_document("2026-10001"), _document("2026-10002", kind="eo")]
            )
        }
    )
    # Two tasks share one canned page. Both documents are returned for each
    # task, and the mapper keeps only the shape that task asked for.
    ctx = make_context(tmp_path, client)
    first = run_federal_register(ctx)
    second = run_federal_register(ctx)
    feed = load_feed(ctx.federal_path)
    ids = [item["id"] for item in feed["items"]]
    assert first.records == 2
    assert second.records == 2
    assert ids.count("fr-2026-10001") == 1
    assert ids.count("fr-2026-10002") == 1
    rule = next(item for item in feed["items"] if item["id"] == "fr-2026-10001")
    order = next(item for item in feed["items"] if item["id"] == "fr-2026-10002")
    assert rule["kind"] == "federal_register"
    assert rule["documentType"] == "Proposed Rule"
    assert rule["summary"] == "Comment by Friday."
    assert rule["chamber"] is None
    assert order["kind"] == "executive_order"
    assert order["documentType"] == "Executive Order"
    assert order["identifier"] == "EO 14438"
    assert load_state(ctx.state_dir / "federal-register.json")["completed_through"] == "2026-11-12"


def test_federal_register_splits_windows_over_the_page_cap(tmp_path) -> None:
    wide = _page([_document("2026-WIDE")], count=10001)
    left = _page([_document("2026-LEFT")])
    right = _page([_document("2026-RIGHT")])
    payloads = [wide, left, right, _page([]), _page([])]

    class Scripted:
        def __init__(self) -> None:
            self.calls = 0

        def get_json(self, url, *, params=None, headers=None):
            payload = payloads[self.calls]
            self.calls += 1
            return payload

    ctx = make_context(
        tmp_path,
        Scripted(),
        cli_start=date(2026, 11, 10),
        cli_end=date(2026, 11, 12),
    )
    outcome = run_federal_register(ctx)
    ids = {item["id"] for item in load_feed(ctx.federal_path)["items"]}
    assert "fr-2026-WIDE" not in ids
    assert ids == {"fr-2026-LEFT", "fr-2026-RIGHT"}
    assert outcome.checked is True


class ScriptedSingle:
    def get_json(self, url, *, params=None, headers=None):
        return _page([_document("2026-DAY")], count=10001)


def test_single_day_over_the_page_cap_is_not_published(tmp_path) -> None:
    ctx = make_context(
        tmp_path,
        ScriptedSingle(),
        cli_start=date(2026, 11, 12),
        cli_end=date(2026, 11, 12),
    )
    outcome = run_federal_register(ctx)
    assert load_feed(ctx.federal_path)["items"] == []
    assert any("was not published" in error for error in outcome.errors)
    assert outcome.checked is True


def _param(params, key: str) -> str:
    for name, value in params:
        if name == key:
            return value
    raise AssertionError(f"missing {key}")


def _is_executive_order(params) -> bool:
    return any(name.startswith("conditions[presidential_document_type]") for name, _value in params)


def _types(params) -> set[str]:
    return {value for name, value in params if name == "conditions[type][]"}


def _empty_page() -> dict:
    return {"description": "none", "count": 0}


def test_leftover_task_catches_up_through_today(tmp_path) -> None:
    """A stuck older task must finish, then the same run reads through today."""

    class Client:
        def get_json(self, url, *, params=None, headers=None):
            if _is_executive_order(params) or _types(params) != {"RULE", "PRORULE"}:
                return _empty_page()
            start = _param(params, "conditions[publication_date][gte]")
            end = _param(params, "conditions[publication_date][lte]")
            assert (start, end) == ("2026-11-16", "2026-11-18")
            document = _document("2026-17111")
            document["publication_date"] = "2026-11-17"
            return _page([document])

    ctx = make_context(
        tmp_path,
        Client(),
        cli_start=None,
        cli_end=None,
        today=date(2026, 11, 18),
    )
    save_state(
        ctx.state_dir / "federal-register.json",
        {
            "window": ["2026-11-16", "2026-11-16"],
            "completed_through": "2026-11-16",
            "tasks": [
                {
                    "kind": "executive_orders",
                    "start": "2026-11-16",
                    "end": "2026-11-16",
                    "page": 1,
                }
            ],
        },
    )
    outcome = run_federal_register(ctx)
    feed = load_feed(ctx.federal_path)
    state = load_state(ctx.state_dir / "federal-register.json")
    assert outcome.errors == []
    assert outcome.checked is True
    assert [item["id"] for item in feed["items"]] == ["fr-2026-17111"]
    assert state["tasks"] == []
    assert state["completed_through"] == "2026-11-18"
    assert state["window"] == ["2026-11-16", "2026-11-18"]


def test_empty_day_without_results_is_not_an_error(tmp_path) -> None:
    """A zero-hit day omits `results`. That is an empty day, not a failed fetch."""
    client = RouteClient(
        {
            "federalregister.gov": {
                "description": "Documents published on 11/15/2026",
                "count": 0,
            }
        }
    )
    ctx = make_context(tmp_path, client)
    outcome = run_federal_register(ctx)
    assert outcome.records == 0
    assert outcome.errors == []
    assert outcome.checked is True
    assert load_feed(ctx.federal_path)["items"] == []
    state = load_state(ctx.state_dir / "federal-register.json")
    assert state["tasks"] == []
    assert state["completed_through"] == "2026-11-12"


def test_rules_publish_when_executive_orders_are_an_empty_day(tmp_path) -> None:
    class ByKind:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def get_json(self, url, *, params=None, headers=None):
            self.calls.append(params)
            if _is_executive_order(params) or _types(params) != {"RULE", "PRORULE"}:
                return _empty_page()
            return _page([_document("2026-10001")])

    client = ByKind()
    ctx = make_context(tmp_path, client)
    outcome = run_federal_register(ctx)
    feed = load_feed(ctx.federal_path)
    assert outcome.errors == []
    assert outcome.checked is True
    assert [item["id"] for item in feed["items"]] == ["fr-2026-10001"]
    assert load_state(ctx.state_dir / "federal-register.json")["tasks"] == []


def test_positive_count_without_results_is_an_error(tmp_path) -> None:
    client = RouteClient(
        {"federalregister.gov": {"description": "Documents", "count": 4}}
    )
    ctx = make_context(tmp_path, client)
    outcome = run_federal_register(ctx)
    assert outcome.checked is False
    assert load_feed(ctx.federal_path)["items"] == []
    assert any("did not include results" in error for error in outcome.errors)
    assert any("4" in error for error in outcome.errors)


def test_api_error_document_is_reported(tmp_path) -> None:
    client = RouteClient(
        {
            "federalregister.gov": {
                "status": 400,
                "message": (
                    "Pagination limit exceeded.  "
                    "No more than 10000 items can be requested at a time"
                ),
            }
        }
    )
    ctx = make_context(tmp_path, client)
    outcome = run_federal_register(ctx)
    assert outcome.checked is False
    assert outcome.records == 0
    assert any("Pagination limit exceeded" in error for error in outcome.errors)
    assert load_feed(ctx.federal_path)["items"] == []


def test_federal_register_fetches_every_page(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("scrapers.sources.federal_register.FEDERAL_REGISTER_PAGE_SIZE", 2)
    docs = [_document(f"2026-1100{index}") for index in range(5)]

    class Pager:
        def __init__(self) -> None:
            self.pages: list[tuple[str, str]] = []

        def get_json(self, url, *, params=None, headers=None):
            page = _param(params, "page")
            if _types(params) == {"NOTICE"}:
                self.pages.append(("notices", page))
                return _empty_page()
            if _types(params) == {"PRESDOCU"} or _is_executive_order(params):
                self.pages.append(("presidential", page))
                return _empty_page()
            self.pages.append(("rules", page))
            page_no = int(page)
            chunk = docs[(page_no - 1) * 2 : page_no * 2]
            return {"count": len(docs), "total_pages": 3, "results": chunk}

    client = Pager()
    ctx = make_context(tmp_path, client)
    outcome = run_federal_register(ctx)
    ids = [item["id"] for item in load_feed(ctx.federal_path)["items"]]
    assert outcome.errors == []
    assert outcome.checked is True
    assert outcome.records == 5
    assert ids == [f"fr-2026-1100{index}" for index in range(5)]
    assert client.pages == [
        ("rules", "1"),
        ("rules", "2"),
        ("rules", "3"),
        ("notices", "1"),
        ("presidential", "1"),
    ]


def test_notices_are_separate_and_presidential_types_stay_on_the_main_feed(tmp_path) -> None:
    notice = _document("2026-20001")
    notice["type"] = "Notice"
    notice["title"] = "Agency Information Collection Activities"
    proclamation = _document("2026-20002", kind="eo")
    proclamation["subtype"] = "Proclamation"
    proclamation["title"] = "A proclamation"
    proclamation["executive_order_number"] = None
    presidential_notice = _document("2026-20005", kind="eo")
    presidential_notice["subtype"] = "Notice"
    presidential_notice["title"] = "Continuation of a national emergency"
    presidential_notice["executive_order_number"] = None
    order = _document("2026-20003", kind="eo")

    class Client:
        def get_json(self, url, *, params=None, headers=None):
            kinds = _types(params)
            if kinds == {"NOTICE"}:
                return _page([notice])
            if kinds == {"PRESDOCU"}:
                return _page([proclamation, presidential_notice, order])
            if kinds == {"RULE", "PRORULE"}:
                return _page([_document("2026-20004")])
            return _empty_page()

    ctx = make_context(tmp_path, Client())
    outcome = run_federal_register(ctx)
    main = {item["id"]: item for item in load_feed(ctx.federal_path)["items"]}
    notices = load_feed(ctx.federal_path.with_name("federal-notices.json"))["items"]
    assert outcome.errors == []
    assert outcome.records == 5
    assert set(main) == {"fr-2026-20004", "fr-2026-20002", "fr-2026-20005", "fr-2026-20003"}
    assert main["fr-2026-20004"]["documentType"] == "Proposed Rule"
    assert main["fr-2026-20004"]["kind"] == "federal_register"
    assert main["fr-2026-20002"]["kind"] == "federal_register"
    assert main["fr-2026-20002"]["documentType"] == "Proclamation"
    assert main["fr-2026-20005"]["documentType"] == "Presidential Notice"
    assert main["fr-2026-20005"]["kind"] == "federal_register"
    assert main["fr-2026-20003"]["kind"] == "executive_order"
    assert main["fr-2026-20003"]["documentType"] == "Executive Order"
    assert [item["id"] for item in notices] == ["fr-2026-20001"]
    assert notices[0]["documentType"] == "Notice"
    assert notices[0]["kind"] == "federal_register"


def test_house_vote_xml_and_date_filter(tmp_path) -> None:
    xml = (FIXTURES / "house_roll.xml").read_text(encoding="utf-8")
    index = (FIXTURES / "house_index.html").read_text(encoding="utf-8")
    item = parse_house_vote(xml, 2026, 323)
    assert item["id"] == "house-vote-2026-323"
    assert item["chamber"] == "house"
    assert item["date"] == "2026-11-12"
    assert item["summary"] == "Passed. yeas 392, nays 18, present 0, not voting 23."
    assert item["url"].endswith("/roll323.xml")
    client = RouteClient(
        {
            "evslegacy/2026/": index,
            "roll323.xml": xml,
        }
    )
    ctx = make_context(tmp_path, client)
    outcome = run_house_votes(ctx)
    feed = load_feed(ctx.federal_path)
    assert outcome.records == 1
    assert [row["id"] for row in feed["items"]] == ["house-vote-2026-323"]
    assert not any("roll001.xml" in url for url, _params in client.calls)
    again = run_house_votes(ctx)
    assert again.records == 0
    assert [row["id"] for row in load_feed(ctx.federal_path)["items"]] == ["house-vote-2026-323"]


def test_senate_vote_xml_and_date_filter(tmp_path) -> None:
    xml = (FIXTURES / "senate_vote.xml").read_text(encoding="utf-8")
    menu = (FIXTURES / "senate_menu.xml").read_text(encoding="utf-8")
    item = parse_senate_vote(xml, 119, 2, 262)
    assert item["identifier"] == "Vote 262"
    assert item["summary"] == "Cloture Motion Agreed to (49-26)"
    assert item["chamber"] == "senate"
    client = RouteClient(
        {
            "vote_menu_119_2.xml": menu,
            "vote_119_2_00262.xml": xml,
        }
    )
    ctx = make_context(tmp_path, client)
    outcome = run_senate_votes(ctx)
    assert outcome.records == 1
    saved = load_feed(ctx.federal_path)["items"][0]
    assert saved["url"].endswith("vote_119_2_00262.xml")
    assert "api_key" not in json.dumps(saved)


def test_congress_bills_skip_without_a_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    client = RouteClient({})
    ctx = make_context(tmp_path, client)
    outcome = run_congress_bills(ctx)
    assert outcome.records == 0
    assert outcome.checked is False
    assert "DATA_GOV_API_KEY is not set" in outcome.errors[0]
    assert client.calls == []


def test_congress_bills_publish_public_urls_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_GOV_API_KEY", SECRET)
    payload = {
        "bills": [
            {
                "congress": 119,
                "number": "2102",
                "type": "HR",
                "title": "Major Richard Star Act",
                "updateDate": "2026-11-12",
                "latestAction": {
                    "actionDate": "2026-11-12",
                    "text": "Passed House.",
                },
                "url": f"https://api.congress.gov/v3/bill/119/hr/2102?api_key={SECRET}",
            },
            {
                "congress": 119,
                "number": "9",
                "type": "NOTABILL",
                "title": "Nope",
                "url": f"https://api.congress.gov/v3/bill?api_key={SECRET}",
            },
        ],
        "pagination": {"next": None},
    }
    client = RouteClient({"api.congress.gov": payload})
    client.secrets = [SECRET]
    ctx = make_context(tmp_path, client)
    outcome = run_congress_bills(ctx)
    feed = load_feed(ctx.federal_path)
    assert outcome.records == 1
    assert feed["items"][0]["id"] == "hr-2102-119"
    assert feed["items"][0]["url"] == "https://www.congress.gov/bill/119th-congress/house-bill/2102"
    assert feed["items"][0]["summary"] == "Passed House."
    blob = json.dumps({"feed": feed, "state": load_state(ctx.state_dir / "congress-bills.json")})
    quarantine = list((ctx.state_dir / "quarantine").rglob("*.json"))
    blob += "".join(path.read_text(encoding="utf-8") for path in quarantine)
    assert SECRET not in blob
    assert "api_key" not in blob
    _url, params = client.calls[0]
    assert ("api_key", SECRET) in params


def test_map_bill_identifier() -> None:
    item = map_bill(
        {
            "congress": 119,
            "number": "1",
            "type": "S",
            "title": "A senate bill",
            "updateDate": "2026-01-03",
            "latestAction": {"actionDate": "2026-01-03", "text": "Introduced."},
        }
    )
    assert item["identifier"] == "S. 1"
    assert item["chamber"] == "senate"
    assert item["url"].endswith("/senate-bill/1")


def test_runner_records_a_skip_and_continues(tmp_path, monkeypatch) -> None:
    def boom(ctx):
        raise RuntimeError(f"token {SECRET} failed")

    def ok(ctx):
        return Outcome(records=3, errors=[], checked=True)

    monkeypatch.setattr(
        runner,
        "SOURCES",
        [
            ("federal-register", "Federal Register", boom),
            ("house-votes", "House roll-call votes", ok),
        ],
    )
    client = RouteClient({})
    client.secrets = [SECRET]
    ctx = make_context(tmp_path, client)
    run_sources(ctx, ["federal-register", "house-votes"])
    rows = {item["id"]: item for item in load_feed(ctx.status_path)["items"]}
    assert rows["federal-register"]["records"] == 0
    assert SECRET not in rows["federal-register"]["errors"][0]
    assert "failed" in rows["federal-register"]["errors"][0]
    assert rows["house-votes"]["records"] == 3
    assert rows["house-votes"]["errors"] == []
