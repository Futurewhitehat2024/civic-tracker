"""House periodic transaction reports from the Clerk's annual XML index.

Electronic PDFs are parsed from their text layer. Image-only PDFs are listed
with a link and no transactions. There is no OCR.
"""

import io
import logging
import re
import zipfile
from datetime import datetime

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from scrapers.context import Outcome, RunContext
from scrapers.http_client import HttpError
from scrapers.publish import publish_trades
from scrapers.sources.ptr_text import parse_ptr_text
from scrapers.store import load_state, save_state
from scrapers.windows import resolve_window, window_key

log = logging.getLogger(__name__)

SOURCE_ID = "house-ptr"
SOURCE_NAME = "House periodic transaction reports"
MAX_ATTEMPTS = 3
_TITLE_SUFFIX = re.compile(r"\s+(Mr|Mrs|Ms|Miss|Hon)\.?$", re.IGNORECASE)


def run_house_ptr(ctx: RunContext) -> Outcome:
    state_path = ctx.state_dir / f"{SOURCE_ID}.json"
    state = load_state(state_path)
    start, end = resolve_window(state, ctx)
    key = window_key(start, end)
    if state.get("window") != key:
        state["window"] = key
    done = state.setdefault("done", {})
    attempts = state.setdefault("attempts", {})
    outcome = Outcome()
    try:
        filings = _filings_in_window(ctx, start, end)
    except HttpError as exc:
        outcome.errors.append(str(exc))
        save_state(state_path, state)
        return outcome
    log.info("house-ptr %s filings in %s..%s", len(filings), start, end)
    for filing in filings:
        doc_id = filing["doc_id"]
        year = filing["year"]
        finished = done.setdefault(str(year), [])
        if doc_id in finished:
            continue
        if int(attempts.get(doc_id) or 0) >= MAX_ATTEMPTS:
            continue
        try:
            pdf, status = _download_pdf(ctx, year, doc_id)
            items = _items_for_filing(filing, pdf, status)
        except HttpError as exc:
            attempts[doc_id] = int(attempts.get(doc_id) or 0) + 1
            outcome.errors.append(f"House PTR {doc_id} failed: {exc}")
            save_state(state_path, state)
            continue
        if items and items[0].get("transactionType") == "unparsed filing":
            outcome.errors.append(
                f"House PTR {doc_id} had extractable text but no transactions were parsed."
            )
            items[0]["transactionType"] = "scanned filing"
        accepted, problems = publish_trades(
            ctx,
            SOURCE_ID,
            items,
            drop_id=f"house-ptr-{doc_id}",
        )
        outcome.records += accepted
        outcome.errors.extend(problems)
        if accepted:
            finished.append(doc_id)
            attempts.pop(doc_id, None)
        else:
            attempts[doc_id] = int(attempts.get(doc_id) or 0) + 1
            outcome.errors.append(f"House PTR {doc_id} was not published.")
        save_state(state_path, state)
    pending = [
        filing["doc_id"]
        for filing in filings
        if filing["doc_id"] not in done.get(str(filing["year"]), [])
        and int(attempts.get(filing["doc_id"]) or 0) < MAX_ATTEMPTS
    ]
    if not pending:
        state["completed_through"] = key[1]
        outcome.checked = True
    save_state(state_path, state)
    return outcome


def parse_fd_xml(xml: bytes) -> list[dict]:
    root = etree.fromstring(xml)
    filings = []
    for member in root.findall("Member"):
        if (member.findtext("FilingType") or "").strip() != "P":
            continue
        doc_id = (member.findtext("DocID") or "").strip()
        filed = (member.findtext("FilingDate") or "").strip()
        if not doc_id or not filed:
            continue
        year_text = (member.findtext("Year") or "").strip()
        filings.append(
            {
                "doc_id": doc_id,
                "year": int(year_text) if year_text.isdigit() else _us_date(filed).year,
                "filing_date": _us_date(filed).isoformat(),
                "member": _member_name(member),
                "state": _state(member.findtext("StateDst") or ""),
            }
        )
    return filings


def _filings_in_window(ctx: RunContext, start, end) -> list[dict]:
    found: list[dict] = []
    for year in range(start.year, end.year + 1):
        url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
        try:
            payload, _headers = ctx.client.get_bytes(url)
        except HttpError as exc:
            if "HTTP 404" in str(exc):
                log.info("house-ptr index for %s is not published", year)
                continue
            raise
        xml = _xml_from_zip(payload)
        for filing in parse_fd_xml(xml):
            filed = datetime.strptime(filing["filing_date"], "%Y-%m-%d").date()
            if start <= filed <= end:
                found.append(filing)
    found.sort(key=lambda item: (item["filing_date"], item["doc_id"]))
    return found


def _download_pdf(ctx: RunContext, year: int, doc_id: str) -> tuple[bytes | None, int]:
    url = _pdf_url(year, doc_id)
    try:
        payload, _headers = ctx.client.get_bytes(url)
    except HttpError as exc:
        if "HTTP 404" in str(exc):
            return None, 404
        raise
    if not payload.startswith(b"%PDF"):
        return None, 404
    return payload, 200


def _items_for_filing(filing: dict, pdf: bytes | None, status: int) -> list[dict]:
    url = _pdf_url(filing["year"], filing["doc_id"])
    base = {
        "member": filing["member"],
        "chamber": "house",
        "party": None,
        "state": filing["state"],
        "filingDate": filing["filing_date"],
        "url": url,
    }
    if pdf is None or status != 200:
        return [_link_only(filing, base)]
    text = _pdf_text(pdf)
    if not text.strip():
        return [_link_only(filing, base)]
    transactions = parse_ptr_text(text)
    if not transactions:
        row = _link_only(filing, base)
        row["transactionType"] = "unparsed filing"
        return [row]
    items = []
    for index, transaction in enumerate(transactions, start=1):
        items.append(
            {
                **base,
                "id": f"house-ptr-{filing['doc_id']}-{index}",
                "transactionType": transaction["transactionType"],
                "asset": transaction["asset"],
                "ticker": transaction["ticker"],
                "amountRange": transaction["amountRange"],
                "transactionDate": transaction["transactionDate"],
                "owner": transaction["owner"],
            }
        )
    return items


def _link_only(filing: dict, base: dict) -> dict:
    return {
        **base,
        "id": f"house-ptr-{filing['doc_id']}",
        "transactionType": "scanned filing",
        "asset": "Scanned periodic transaction report",
        "ticker": None,
        "amountRange": "See official filing",
        "transactionDate": None,
        "owner": None,
    }


def _pdf_text(payload: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(payload))
    except PdfReadError:
        return ""
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts).replace("\x00", "")


def _xml_from_zip(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not names:
            raise HttpError("House financial disclosure zip did not contain XML")
        return archive.read(names[0])


def _member_name(member: etree._Element) -> str:
    first = _TITLE_SUFFIX.sub("", (member.findtext("First") or "").strip())
    last = (member.findtext("Last") or "").strip()
    suffix = (member.findtext("Suffix") or "").strip()
    return " ".join(part for part in (first, last, suffix) if part)


def _state(value: str) -> str | None:
    code = value.strip().upper()
    if len(code) >= 2 and code[:2].isalpha():
        return code[:2]
    return None


def _us_date(value: str):
    return datetime.strptime(value.strip(), "%m/%d/%Y").date()


def _pdf_url(year: int, doc_id: str) -> str:
    return f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
