import io
import zipfile
from datetime import date

from scrapers.sources.house_ptr import parse_fd_xml, run_house_ptr
from scrapers.sources.ptr_text import parse_ptr_text
from scrapers.sources.senate_efd import parse_senators, run_senate_efd
from scrapers.store import load_feed
from tests.support import make_context

PTR_TEXT = """
Name: Hon. Mark Alford
Amazon.com, Inc. - Common Stock
(AMZN) [ST]
S (partial)03/16/202603/16/2026$1,001 - $15,000
F S: New
D: The full transaction included the following sales: AMZN - 25 shares
SP
Apple Inc. (AAPL) [ST]
P03/01/202603/02/2026$15,001 - $50,000
I CERTIFY that the statements I have made are true.
"""

FD_XML = b"""<?xml version="1.0"?>
<FinancialDisclosure>
  <Member>
    <First>Mark</First><Last>Alford</Last><Suffix></Suffix>
    <FilingType>P</FilingType><StateDst>MO04</StateDst><Year>2026</Year>
    <FilingDate>3/31/2026</FilingDate><DocID>20034201</DocID>
  </Member>
  <Member>
    <First>John J Mr</First><Last>McGuire</Last>
    <FilingType>P</FilingType><StateDst>VA05</StateDst><Year>2026</Year>
    <FilingDate>11/1/2026</FilingDate><DocID>20035484</DocID>
  </Member>
  <Member>
    <First>Richard</First><Last>Aaron</Last>
    <FilingType>W</FilingType><StateDst>MI04</StateDst><Year>2026</Year>
    <FilingDate>4/15/2026</FilingDate><DocID>8068</DocID>
  </Member>
</FinancialDisclosure>
"""

SENATE_XML = b"""<?xml version="1.0"?>
<contact_information>
  <member>
    <last_name>Alsobrooks</last_name>
    <first_name>Angela D.</first_name>
    <party>D</party>
    <state>MD</state>
    <bioguide_id>A000382</bioguide_id>
  </member>
  <member>
    <last_name>Example</last_name>
    <first_name>Pat</first_name>
    <party>R</party>
    <state>TX</state>
    <bioguide_id>E000001</bioguide_id>
  </member>
</contact_information>
"""


def test_ptr_text_parses_electronic_rows_and_ignores_the_certification() -> None:
    rows = parse_ptr_text(PTR_TEXT)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AMZN"
    assert rows[0]["transactionType"] == "sale (partial)"
    assert rows[0]["amountRange"] == "$1,001 - $15,000"
    assert rows[0]["transactionDate"] == "2026-03-16"
    assert rows[0]["owner"] is None
    assert rows[0]["asset"] == "Amazon.com, Inc. - Common Stock"
    assert "shares" not in rows[0]["asset"]
    assert rows[1]["ticker"] == "AAPL"
    assert rows[1]["transactionType"] == "purchase"
    assert rows[1]["owner"] == "spouse"
    assert parse_ptr_text("") == []
    wrapped = parse_ptr_text(
        "Norwegian Cruise Line HoldingsP10/20/202611/09/2026$1,001 - $15,000\n"
        "Amount Cap.\n$200?\n"
        "Ltd. Ordinary Shares (NCLH) [ST]\n"
        "NVIDIA Corporation - Common Stock (NVDA) [ST]\n"
        "S (partial)10/20/202611/09/2026$1,001 - $15,000\n"
    )
    assert [row["ticker"] for row in wrapped] == ["NCLH", "NVDA"]
    assert wrapped[0]["asset"] == "Norwegian Cruise Line Holdings Ltd. Ordinary Shares"
    assert wrapped[0]["transactionType"] == "purchase"
    owned = parse_ptr_text(
        "Amount Cap. $200? JT BP p.l.c. Common Stock (BP) [ST]\n"
        "S (partial)10/01/202611/13/2026$1,001 - $15,000\n"
    )
    assert owned[0]["owner"] == "joint"
    assert owned[0]["ticker"] == "BP"
    assert owned[0]["asset"] == "BP p.l.c. Common Stock"


def test_fd_xml_keeps_periodic_reports_only() -> None:
    filings = parse_fd_xml(FD_XML)
    assert [item["doc_id"] for item in filings] == ["20034201", "20035484"]
    assert filings[1]["member"] == "John J McGuire"
    assert filings[1]["state"] == "VA"
    assert filings[1]["filing_date"] == "2026-11-01"


def test_house_ptr_run_is_idempotent(tmp_path, monkeypatch) -> None:
    import scrapers.sources.house_ptr as house_ptr

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("2026FD.xml", FD_XML)

    class Client:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get_bytes(self, url, headers=None):
            self.urls.append(url)
            if url.endswith(".zip"):
                return buffer.getvalue(), {}
            return b"%PDF-1.4", {}

    monkeypatch.setattr(house_ptr, "_pdf_text", lambda payload: PTR_TEXT)
    client = Client()
    ctx = make_context(
        tmp_path,
        client,
        cli_start=date(2026, 11, 1),
        cli_end=date(2026, 11, 16),
    )
    first = run_house_ptr(ctx)
    second = run_house_ptr(ctx)
    items = load_feed(ctx.trades_path)["items"]
    assert first.records == 2
    assert second.records == 0
    assert [item["id"] for item in items] == ["house-ptr-20035484-1", "house-ptr-20035484-2"]
    assert items[0]["url"].endswith("/2026/20035484.pdf")
    assert sum(1 for url in client.urls if url.endswith("20034201.pdf")) == 0
    assert sum(1 for url in client.urls if url.endswith("20035484.pdf")) == 1


def test_senate_links_do_not_request_the_search(tmp_path) -> None:
    class Response:
        content = SENATE_XML
        headers = {"last-modified": "Tue, 10 Nov 2026 17:30:25 GMT"}
        url = type("URL", (), {"host": "www.senate.gov"})()

    class Client:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, url, **kwargs):
            self.urls.append(url)
            assert "efdsearch.senate.gov" not in url
            return Response()

    client = Client()
    ctx = make_context(tmp_path, client)
    outcome = run_senate_efd(ctx)
    items = load_feed(ctx.trades_path)["items"]
    assert outcome.records == 2
    assert {item["id"] for item in items} == {"senate-efd-A000382", "senate-efd-E000001"}
    assert items[0]["url"] == "https://efdsearch.senate.gov/search/"
    assert items[0]["transactionType"] == "senate-efd-search"
    assert items[0]["filingDate"] == "2026-11-10"
    parties = {item["member"]: item["party"] for item in items}
    assert parties["Angela D. Alsobrooks"] == "Democratic"
    assert all("efdsearch.senate.gov" not in url for url in client.urls)
    parsed = parse_senators(SENATE_XML)
    assert len(parsed) == 2
