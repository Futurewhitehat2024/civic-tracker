"""Link-only Senate financial disclosure rows.

efdsearch.senate.gov requires accepting a terms agreement. This module does
not request that host. It reads the public Senate contact list and stores the
search page URL for each current senator. Parsed transactions are not invented.
"""

import logging
from email.utils import parsedate_to_datetime

from lxml import etree

from scrapers.context import Outcome, RunContext
from scrapers.http_client import HttpError
from scrapers.publish import publish_trades

log = logging.getLogger(__name__)

SOURCE_ID = "senate-efd"
SOURCE_NAME = "Senate eFD links"
SENATORS_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
# Public search page. Stored as a link. Never requested by this package.
EFD_SEARCH_URL = "https://efdsearch.senate.gov/search/"
_PARTIES = {
    "D": "Democratic",
    "R": "Republican",
    "I": "Independent",
    "ID": "Independent",
}


def run_senate_efd(ctx: RunContext) -> Outcome:
    outcome = Outcome()
    try:
        response = ctx.client.get(SENATORS_URL)
    except HttpError as exc:
        outcome.errors.append(str(exc))
        return outcome
    try:
        members = parse_senators(response.content)
    except etree.XMLSyntaxError as exc:
        outcome.errors.append(f"Senate member list was not valid XML: {exc}")
        return outcome
    host = getattr(response.url, "host", "") or ""
    if "efdsearch.senate.gov" in host:
        outcome.errors.append("Refusing Senate eFD search results.")
        return outcome
    checked = _header_day(response.headers.get("last-modified")) or ctx.today.isoformat()
    items = [_item(member, checked) for member in members]
    accepted, problems = publish_trades(ctx, SOURCE_ID, items, replace_prefix="senate-efd-")
    outcome.records = accepted
    outcome.errors.extend(problems)
    outcome.checked = True
    log.info("senate-efd linked %s senators", accepted)
    return outcome


def parse_senators(xml: bytes) -> list[dict]:
    root = etree.fromstring(xml)
    members = []
    for member in root.findall("member"):
        bioguide = (member.findtext("bioguide_id") or "").strip()
        first = (member.findtext("first_name") or "").strip()
        last = (member.findtext("last_name") or "").strip()
        if not last or not (bioguide or first):
            continue
        party_code = (member.findtext("party") or "").strip()
        members.append(
            {
                "id": f"senate-efd-{bioguide or _slug(first, last)}",
                "member": " ".join(part for part in (first, last) if part),
                "party": _PARTIES.get(party_code, party_code or None),
                "state": (member.findtext("state") or "").strip() or None,
            }
        )
    return members


def _item(member: dict, checked: str) -> dict:
    return {
        "id": member["id"],
        "member": member["member"],
        "chamber": "senate",
        "party": member["party"],
        "state": member["state"],
        "transactionType": "senate-efd-search",
        "asset": "Senate eFD periodic transaction reports",
        "ticker": None,
        "amountRange": "See official search",
        "transactionDate": None,
        "filingDate": checked,
        "owner": None,
        "url": EFD_SEARCH_URL,
    }


def _header_day(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _slug(first: str, last: str) -> str:
    raw = f"{last}-{first}".lower()
    cleaned = "".join(char if char.isalnum() else "-" for char in raw)
    return "-".join(part for part in cleaned.split("-") if part)
