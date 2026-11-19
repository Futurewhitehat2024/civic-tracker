import io
import json
import zipfile
from datetime import date

from scrapers.sources.house_ptr import parse_fd_xml, run_house_ptr
from scrapers.sources.house_roster import normalize_name, parse_roster
from scrapers.store import load_feed, save_json
from tests.support import make_context

ROSTER = [
    {
        "name": {"first": "Byron", "last": "Donalds", "official_full": "Byron Donalds"},
        "terms": [{"type": "rep", "state": "FL", "district": 19, "party": "Republican"}],
    },
    {
        "name": {
            "first": "John",
            "middle": "J.",
            "last": "McGuire",
            "official_full": "John J. McGuire",
        },
        "terms": [{"type": "rep", "state": "VA", "district": 5, "party": "Republican"}],
    },
    {
        "name": {"first": "John", "last": "Smith", "official_full": "John Smith"},
        "terms": [{"type": "rep", "state": "CA", "district": 1, "party": "Democrat"}],
    },
    {
        "name": {"first": "John", "last": "Smith", "official_full": "John Smith"},
        "terms": [{"type": "rep", "state": "CA", "district": 2, "party": "Republican"}],
    },
    {
        "name": {"first": "Maria", "last": "Cantwell", "official_full": "Maria Cantwell"},
        "terms": [{"type": "sen", "state": "WA", "party": "Democrat"}],
    },
]


def test_party_match_uses_name_state_and_district() -> None:
    roster = parse_roster(ROSTER)
    assert roster.party_for("Byron Donalds", "FL", 19) == "Republican"
    assert roster.party_for("John J McGuire", "VA", 5) == "Republican"
    assert roster.party_for("John Smith", "CA", None) is None
    assert roster.party_for("John Smith", "CA", 1) == "Democratic"
    assert roster.party_for("Nobody", "FL", 19) is None
    legal = parse_roster(
        [
            {
                "name": {
                    "first": "J.",
                    "middle": "French",
                    "last": "Hill",
                    "official_full": "J. French Hill",
                },
                "terms": [{"type": "rep", "state": "AR", "district": 2, "party": "Republican"}],
            },
            {
                "name": {
                    "first": "Rick",
                    "middle": "W.",
                    "last": "Allen",
                    "official_full": "Rick W. Allen",
                },
                "terms": [{"type": "rep", "state": "GA", "district": 12, "party": "Republican"}],
            },
            {
                "name": {"first": "Ro", "last": "Khanna", "official_full": "Ro Khanna"},
                "terms": [{"type": "rep", "state": "CA", "district": 17, "party": "Democrat"}],
            },
        ]
    )
    assert legal.party_for("James French Hill", "AR", None) == "Republican"
    assert legal.party_for("Richard W. Allen", "GA", None) == "Republican"
    assert legal.party_for("Rohit Khanna", "CA", None) == "Democratic"
    assert normalize_name("Hon. John J. McGuire Jr.") == "john j mcguire"


def test_fd_xml_keeps_the_district() -> None:
    xml = b"""<?xml version="1.0"?>
    <FinancialDisclosure><Member>
      <First>Byron</First><Last>Donalds</Last>
      <FilingType>P</FilingType><StateDst>FL19</StateDst><Year>2026</Year>
      <FilingDate>11/16/2026</FilingDate><DocID>20035811</DocID>
    </Member></FinancialDisclosure>"""
    filing = parse_fd_xml(xml)[0]
    assert filing["state"] == "FL"
    assert filing["district"] == 19


def test_run_backfills_existing_house_rows_and_leaves_senate_alone(tmp_path, monkeypatch) -> None:
    save_json(
        tmp_path / "trades.json",
        {
            "updated": "2026-11-01T00:00:00-05:00",
            "items": [
                {
                    "id": "house-ptr-1",
                    "member": "Byron Donalds",
                    "chamber": "house",
                    "party": None,
                    "state": "FL",
                    "transactionType": "sale",
                    "asset": "Example",
                    "ticker": "EX",
                    "amountRange": "$1,001 - $15,000",
                    "transactionDate": "2026-10-02",
                    "filingDate": "2026-11-16",
                    "owner": None,
                    "url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/1.pdf",
                },
                {
                    "id": "house-ptr-ambiguous",
                    "member": "John Smith",
                    "chamber": "house",
                    "party": None,
                    "state": "CA",
                    "transactionType": "sale",
                    "asset": "Example",
                    "ticker": None,
                    "amountRange": "$1,001 - $15,000",
                    "transactionDate": None,
                    "filingDate": "2026-11-01",
                    "owner": None,
                    "url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/2.pdf",
                },
                {
                    "id": "senate-efd-A000382",
                    "member": "Angela D. Alsobrooks",
                    "chamber": "senate",
                    "party": "Democratic",
                    "state": "MD",
                    "transactionType": "senate-efd-search",
                    "asset": "Senate eFD periodic transaction reports",
                    "ticker": None,
                    "amountRange": "See official search",
                    "transactionDate": None,
                    "filingDate": "2026-11-18",
                    "owner": None,
                    "url": "https://efdsearch.senate.gov/search/",
                },
            ],
        },
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "2026FD.xml",
            """<?xml version="1.0"?><FinancialDisclosure>
            <Member><First>Byron</First><Last>Donalds</Last>
            <FilingType>P</FilingType><StateDst>FL19</StateDst><Year>2026</Year>
            <FilingDate>11/16/2026</FilingDate><DocID>9</DocID></Member>
            </FinancialDisclosure>""",
        )

    class Client:
        def get_text(self, url, **kwargs):
            assert url.endswith("legislators-current.json")
            return json.dumps(ROSTER)

        def get_bytes(self, url, headers=None):
            if url.endswith(".zip"):
                return buffer.getvalue(), {}
            return b"%PDF-1.4", {}

    ctx = make_context(
        tmp_path,
        Client(),
        cli_start=date(2026, 11, 16),
        cli_end=date(2026, 11, 16),
    )
    monkeypatch.setattr("scrapers.sources.house_ptr._pdf_text", lambda payload: "")
    run_house_ptr(ctx)
    rows = {item["id"]: item for item in load_feed(ctx.trades_path)["items"]}
    assert rows["house-ptr-1"]["party"] == "Republican"
    assert rows["house-ptr-ambiguous"]["party"] is None
    assert rows["senate-efd-A000382"]["party"] == "Democratic"
