"""Senate roll-call votes from the LIS XML files on senate.gov.

The vote menu lists numbers and dates. Each roll's own XML is the record
that gets published. This module does not read member positions.
"""

import logging
from datetime import date

from lxml import etree

from scrapers.context import Outcome, RunContext
from scrapers.dates import parse_month_day, parse_senate_vote_date, sessions_covering
from scrapers.http_client import HttpError
from scrapers.publish import mark_checked, publish_federal
from scrapers.store import load_state, save_state
from scrapers.windows import resolve_window, window_key

log = logging.getLogger(__name__)

SOURCE_ID = "senate-votes"
SOURCE_NAME = "Senate roll-call votes"
MAX_ATTEMPTS = 3


def run_senate_votes(ctx: RunContext) -> Outcome:
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
    still_pending: list[dict] = []
    original = list(state.get("pending") or [])
    for index, roll in enumerate(original):
        congress = int(roll["congress"])
        session = int(roll["session"])
        number = int(roll["number"])
        url = _xml_url(congress, session, number)
        try:
            item = parse_senate_vote(ctx.client.get_text(url), congress, session, number)
        except (HttpError, etree.XMLSyntaxError, ValueError) as exc:
            attempts = int(roll.get("attempts") or 0) + 1
            failed = dict(roll)
            failed["attempts"] = attempts
            message = f"Senate vote {congress}-{session}-{number} failed: {exc}"
            log.warning(message)
            if attempts >= MAX_ATTEMPTS:
                outcome.errors.append(message)
            else:
                still_pending.append(failed)
            save_state(state_path, {**state, "pending": still_pending + original[index + 1 :]})
            continue
        accepted, problems = publish_federal(ctx, SOURCE_ID, [item])
        outcome.records += accepted
        outcome.errors.extend(problems)
        save_state(state_path, {**state, "pending": still_pending + original[index + 1 :]})
    state["pending"] = still_pending
    if not still_pending:
        window = state.get("window") or [None, None]
        state["completed_through"] = window[1]
        if outcome.records == 0:
            mark_checked(ctx, ctx.federal_path, "date")
        outcome.checked = True
    save_state(state_path, state)
    return outcome


def parse_senate_vote(xml: str, congress: int, session: int, number: int) -> dict:
    root = etree.fromstring(xml.encode("utf-8"))
    found = (root.findtext("vote_number") or "").strip()
    if found and int(found) != number:
        raise ValueError(f"Senate vote XML number {found} did not match {number}")
    vote_date = (root.findtext("vote_date") or "").strip()
    if not vote_date:
        raise ValueError("Senate vote XML has no vote_date")
    title = (root.findtext("vote_title") or "").strip()
    question = (root.findtext("question") or "").strip()
    if not title:
        title = question or f"Senate vote {number}"
    result_text = (root.findtext("vote_result_text") or "").strip()
    result = (root.findtext("vote_result") or "").strip()
    summary = result_text or _count_summary(result, root.find("count"))
    return {
        "id": f"senate-vote-{congress}-{session}-{number}",
        "kind": "vote",
        "title": title,
        "date": parse_senate_vote_date(vote_date).isoformat(),
        "url": _xml_url(congress, session, number),
        "source": "Senate.gov",
        "summary": summary or None,
        "identifier": f"Vote {number}",
        "chamber": "senate",
    }


def parse_vote_menu(xml: str) -> list[tuple[int, int, int, date]]:
    root = etree.fromstring(xml.encode("utf-8"))
    congress = int((root.findtext("congress") or "").strip())
    session = int((root.findtext("session") or "").strip())
    year = int((root.findtext("congress_year") or "").strip())
    found: list[tuple[int, int, int, date]] = []
    for vote in root.findall("./votes/vote"):
        number = int((vote.findtext("vote_number") or "").strip())
        voted_on = parse_month_day((vote.findtext("vote_date") or "").strip(), year)
        found.append((congress, session, number, voted_on))
    return found


def _ensure_pending(state: dict, ctx: RunContext) -> dict:
    if state.get("pending") and ctx.cli_start is None and ctx.cli_end is None:
        return state
    start, end = resolve_window(state, ctx)
    key = window_key(start, end)
    if state.get("window") == key and state.get("listed") and "pending" in state:
        return state
    pending = []
    seen: set[tuple[int, int, int]] = set()
    for congress, session in sessions_covering(start, end):
        for item in _menu(ctx, congress, session):
            _congress, _session, number, voted_on = item
            if not (start <= voted_on <= end):
                continue
            identity = (_congress, _session, number)
            if identity in seen:
                continue
            seen.add(identity)
            pending.append(
                {
                    "congress": _congress,
                    "session": _session,
                    "number": number,
                    "attempts": 0,
                }
            )
    pending.sort(key=lambda item: (item["congress"], item["session"], item["number"]))
    log.info("senate-votes listed %s votes in %s..%s", len(pending), start, end)
    return {
        "window": key,
        "completed_through": state.get("completed_through"),
        "listed": True,
        "pending": pending,
    }


def _menu(ctx: RunContext, congress: int, session: int) -> list[tuple[int, int, int, date]]:
    url = (
        "https://www.senate.gov/legislative/LIS/roll_call_lists/"
        f"vote_menu_{congress}_{session}.xml"
    )
    try:
        xml = ctx.client.get_text(url)
    except HttpError as exc:
        if "HTTP 404" in str(exc):
            log.info("senate-votes menu %s session %s is not published", congress, session)
            return []
        raise
    return parse_vote_menu(xml)


def _xml_url(congress: int, session: int, number: int) -> str:
    return (
        "https://www.senate.gov/legislative/LIS/roll_call_votes/"
        f"vote{congress}{session}/vote_{congress}_{session}_{number:05d}.xml"
    )


def _count_summary(result: str, count: etree._Element | None) -> str:
    parts = []
    if result:
        parts.append(result if result.endswith(".") else f"{result}.")
    if count is not None:
        bits = []
        pairs = (("yeas", "yeas"), ("nays", "nays"), ("present", "present"), ("absent", "absent"))
        for label, tag in pairs:
            value = (count.findtext(tag) or "").strip()
            if value:
                bits.append(f"{label} {value}")
        if bits:
            parts.append(", ".join(bits) + ".")
    return " ".join(parts).strip()
