"""Collier and Lee County meeting collectors (CivicClerk public API, in test).

These sources are not in the default `all` group. Run them with
`--sources counties` or a single source id. A county is only marketed as live
once coverage.json lists it as live.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from scrapers.config import DEFAULT_LOOKBACK_DAYS
from scrapers.context import Outcome, RunContext
from scrapers.geo import county_jurisdiction
from scrapers.http_client import HttpError
from scrapers.publish import publish_counties
from scrapers.store import load_state, save_state

log = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
PAGE_SIZE = 100
AHEAD_DAYS = 90

COLLIER = {
    "id": "collier-meetings",
    "name": "Collier County meetings",
    "slug": "collier",
    "tenant": "colliercofl",
    "fips": "12021",
    "state": "FL",
    "label": "Collier County CivicClerk",
    "api": "https://colliercofl.api.civicclerk.com/v1/Events",
    "portal": "https://colliercofl.portal.civicclerk.com",
}

LEE = {
    "id": "lee-meetings",
    "name": "Lee County meetings",
    "slug": "lee",
    "tenant": "leecofl",
    "fips": "12071",
    "state": "FL",
    "label": "Lee County CivicClerk",
    "api": "https://leecofl.api.civicclerk.com/v1/Events",
    "portal": "https://leecofl.portal.civicclerk.com",
}

COUNTIES = (COLLIER, LEE)


def run_collier_meetings(ctx: RunContext) -> Outcome:
    return run_county_meetings(ctx, COLLIER)


def run_lee_meetings(ctx: RunContext) -> Outcome:
    return run_county_meetings(ctx, LEE)


def run_county_meetings(ctx: RunContext, county: dict) -> Outcome:
    state_path = ctx.state_dir / f"{county['id']}.json"
    state = load_state(state_path)
    start, end = _window(ctx, state)
    outcome = Outcome(checked=False)
    try:
        raw_events = _fetch_events(ctx, county["api"], start, end)
    except HttpError as exc:
        outcome.errors.append(str(exc))
        save_state(state_path, {**state, "window": [start.isoformat(), end.isoformat()]})
        return outcome
    items: list[dict] = []
    rejected = 0
    for raw in raw_events:
        try:
            mapped = map_event(raw, county)
        except ValueError:
            rejected += 1
            continue
        if mapped is None:
            continue
        items.append(mapped)
    accepted, problems = publish_counties(ctx, county["id"], items)
    outcome.records += accepted
    outcome.errors.extend(problems)
    if rejected:
        outcome.errors.append(
            f"{rejected} {county['id']} events were skipped because they were incomplete."
        )
    state = {
        "window": [start.isoformat(), end.isoformat()],
        "completed_through": end.isoformat(),
        "fetched": len(raw_events),
    }
    save_state(state_path, state)
    outcome.checked = True
    log.info(
        "%s %s..%s: fetched %s published %s",
        county["id"],
        start,
        end,
        len(raw_events),
        accepted,
    )
    return outcome


def map_event(raw: dict, county: dict) -> dict | None:
    if raw.get("isDeleted") is True:
        return None
    if str(raw.get("isPublished") or "").strip() != "Published":
        return None
    event_id = raw.get("id")
    if event_id is None or event_id == "":
        raise ValueError("CivicClerk event is missing id")
    title = _title(raw)
    if not title:
        raise ValueError(f"CivicClerk event {event_id} is missing a name")
    start = raw.get("startDateTime") or raw.get("eventDate")
    day = _event_date(start)
    if not day:
        raise ValueError(f"CivicClerk event {event_id} is missing a date")
    portal = county["portal"].rstrip("/")
    url = f"{portal}/event/{event_id}"
    category = raw.get("eventCategoryName") or raw.get("categoryName")
    summary = _plain(raw.get("eventDescription")) or _plain(category)
    return {
        "id": f"fl-{county['slug']}-{event_id}",
        "kind": "meeting",
        "title": title,
        "date": day,
        "url": url,
        "source": county["label"],
        "summary": summary,
        "identifier": str(event_id),
        "chamber": None,
        "documentType": _plain(raw.get("meetingTypeName")) or "Meeting",
        "commentsCloseOn": None,
        "effectiveOn": None,
        "agencies": None,
        "tags": [],
        "jurisdiction": county_jurisdiction(county["state"], county["fips"]),
    }


def _title(raw: dict) -> str:
    for key in ("eventName", "agendaName", "eventCategoryName"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _plain(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    return text or None


def _event_date(value: object) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            moment = datetime.fromisoformat(text)
    except ValueError:
        return text[:10] if len(text) >= 10 and text[4] == "-" else None
    if moment.tzinfo is None:
        return moment.date().isoformat()
    return moment.astimezone(EASTERN).date().isoformat()


def _window(ctx: RunContext, state: dict) -> tuple[date, date]:
    start = ctx.cli_start
    end = ctx.cli_end
    if start is None:
        cursor = state.get("completed_through")
        if isinstance(cursor, str) and len(cursor) >= 10:
            start = date.fromisoformat(cursor[:10]) - timedelta(days=1)
        else:
            start = ctx.today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if end is None:
        end = ctx.today + timedelta(days=AHEAD_DAYS)
    if end < start:
        raise SystemExit("County meeting --to date is before --from")
    return start, end


def _fetch_events(ctx: RunContext, api: str, start: date, end: date) -> list[dict]:
    events: list[dict] = []
    skip = 0
    while True:
        filt = (
            f"startDateTime ge {start.isoformat()}T00:00:00Z and "
            f"startDateTime le {end.isoformat()}T23:59:59Z"
        )
        params = {
            "$filter": filt,
            "$orderby": "startDateTime",
            "$top": str(PAGE_SIZE),
            "$skip": str(skip),
        }
        url = f"{api}?{urlencode(params)}"
        payload = ctx.client.get_json(url)
        rows = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise HttpError(f"{api} did not return an OData value array")
        for row in rows:
            if isinstance(row, dict):
                events.append(row)
        if len(rows) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return events
