"""House roll-call votes from the Clerk's XML.

The legacy index pages supply roll numbers and dates. The XML file for each
roll is the record that gets published.
"""

import logging
from datetime import date
from urllib.parse import urljoin

from lxml import etree
from lxml import html as lhtml

from scrapers.context import Outcome, RunContext
from scrapers.dates import parse_month_day
from scrapers.http_client import HttpError
from scrapers.publish import mark_checked, publish_federal
from scrapers.store import load_state, save_state
from scrapers.windows import resolve_window, window_key

log = logging.getLogger(__name__)

SOURCE_ID = "house-votes"
SOURCE_NAME = "House roll-call votes"
MAX_ATTEMPTS = 3


def run_house_votes(ctx: RunContext) -> Outcome:
    state_path = ctx.state_dir / f"{SOURCE_ID}.json"
    state = load_state(state_path)
    outcome = Outcome()
    try:
        state = _ensure_pending(state, ctx)
    except HttpError as exc:
        outcome.errors.append(str(exc))
        save_state(state_path, state)
        return outcome
    save_state(state_path, state)
    still_pending = []
    for roll in list(state.get("pending") or []):
        year = int(roll["year"])
        number = int(roll["roll"])
        url = _xml_url(year, number)
        try:
            xml = ctx.client.get_text(url)
            item = parse_house_vote(xml, year, number)
        except (HttpError, etree.XMLSyntaxError, ValueError) as exc:
            attempts = int(roll.get("attempts") or 0) + 1
            roll["attempts"] = attempts
            message = f"House roll {year}-{number} failed: {exc}"
            log.warning(message)
            if attempts >= MAX_ATTEMPTS:
                outcome.errors.append(message)
            else:
                still_pending.append(roll)
            continue
        accepted, problems = publish_federal(ctx, SOURCE_ID, [item])
        outcome.records += accepted
        outcome.errors.extend(problems)
        save_state(state_path, {**state, "pending": still_pending + _rest_after(state, roll)})
    state["pending"] = still_pending
    if not still_pending:
        state["completed_through"] = state.get("window", [None, None])[1]
        if outcome.records == 0:
            mark_checked(ctx, ctx.federal_path, "date")
        outcome.checked = True
    save_state(state_path, state)
    return outcome


def parse_house_vote(xml: str, year: int, roll: int) -> dict:
    root = etree.fromstring(xml.encode("utf-8"))
    meta = root.find("vote-metadata")
    if meta is None:
        raise ValueError("House vote XML has no vote-metadata")
    found = (meta.findtext("rollcall-num") or "").strip()
    if found and int(found) != roll:
        raise ValueError(f"House vote XML roll {found} did not match {roll}")
    action_date = (meta.findtext("action-date") or "").strip()
    if not action_date:
        raise ValueError("House vote XML has no action-date")
    question = (meta.findtext("vote-question") or "").strip()
    legis = (meta.findtext("legis-num") or "").strip()
    description = (meta.findtext("vote-desc") or "").strip()
    if legis.upper() == "QUORUM":
        legis = ""
    title = question or description or f"House roll {roll}"
    if legis:
        title = f"{title}: {legis}"
    if description and description not in title:
        title = f"{title} — {description}"
    result = (meta.findtext("vote-result") or "").strip()
    totals = meta.find("vote-totals/totals-by-vote")
    summary = _summary(result, totals)
    return {
        "id": f"house-vote-{year}-{roll}",
        "kind": "vote",
        "title": title,
        "date": parse_month_day(action_date, year).isoformat(),
        "url": _xml_url(year, roll),
        "source": "House Clerk",
        "summary": summary,
        "identifier": f"Roll {roll}",
        "chamber": "house",
    }


def parse_roll_index(page: str, year: int) -> list[tuple[int, date]]:
    document = lhtml.fromstring(page)
    found: list[tuple[int, date]] = []
    for row in document.xpath("//tr[td]"):
        cells = row.xpath("./td")
        if len(cells) < 2:
            continue
        roll_text = " ".join(cells[0].text_content().split())
        if not roll_text.isdigit():
            continue
        when = parse_month_day(" ".join(cells[1].text_content().split()), year)
        found.append((int(roll_text), when))
    return found


def _ensure_pending(state: dict, ctx: RunContext) -> dict:
    if state.get("pending") and ctx.cli_start is None and ctx.cli_end is None:
        return state
    start, end = resolve_window(state, ctx)
    key = window_key(start, end)
    if state.get("window") == key and state.get("listed") and "pending" in state:
        return state
    pending = []
    seen: set[tuple[int, int]] = set()
    for year in range(start.year, end.year + 1):
        for roll, voted_on in _rolls_for_year(ctx, year):
            if start <= voted_on <= end and (year, roll) not in seen:
                seen.add((year, roll))
                pending.append({"year": year, "roll": roll, "attempts": 0})
    pending.sort(key=lambda item: (item["year"], item["roll"]))
    log.info("house-votes listed %s rolls in %s..%s", len(pending), start, end)
    return {
        "window": key,
        "completed_through": state.get("completed_through"),
        "listed": True,
        "pending": pending,
    }


def _rolls_for_year(ctx: RunContext, year: int) -> list[tuple[int, date]]:
    index_url = f"https://clerk.house.gov/evslegacy/{year}/index.asp"
    try:
        index = ctx.client.get_text(index_url)
    except HttpError as exc:
        if "HTTP 404" in str(exc):
            log.info("house-votes index for %s is not published", year)
            return []
        raise
    pages = [index]
    document = lhtml.fromstring(index)
    for href in document.xpath("//a/@href"):
        if "ROLL_" not in href.upper():
            continue
        pages.append(ctx.client.get_text(urljoin(index_url, href)))
    rolls: list[tuple[int, date]] = []
    for page in pages:
        rolls.extend(parse_roll_index(page, year))
    return rolls


def _rest_after(state: dict, current: dict) -> list[dict]:
    pending = list(state.get("pending") or [])
    for index, roll in enumerate(pending):
        if roll.get("year") == current.get("year") and roll.get("roll") == current.get("roll"):
            return pending[index + 1 :]
    return []


def _xml_url(year: int, roll: int) -> str:
    return f"https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"


def _summary(result: str, totals: etree._Element | None) -> str | None:
    counts = []
    if totals is not None:
        for label, tag in (
            ("yeas", "yea-total"),
            ("nays", "nay-total"),
            ("present", "present-total"),
            ("not voting", "not-voting-total"),
        ):
            value = (totals.findtext(tag) or "").strip()
            if value:
                counts.append(f"{label} {value}")
    parts = []
    if result:
        parts.append(result if result.endswith(".") else f"{result}.")
    if counts:
        parts.append(", ".join(counts) + ".")
    text = " ".join(parts).strip()
    return text or None
