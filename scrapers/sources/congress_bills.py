"""Congress.gov bills updated in a date window.

The api.data.gov key is read from DATA_GOV_API_KEY. When it is missing the
source records that fact and does not call the API. Saved links point at
congress.gov, never at a URL that carried the key.
"""

import logging
import os
from datetime import date

from scrapers.config import API_KEY_ENV
from scrapers.context import Outcome, RunContext
from scrapers.dates import ordinal
from scrapers.http_client import HttpError
from scrapers.publish import mark_checked, publish_federal
from scrapers.redact import strip_api_key
from scrapers.store import load_state, quarantine, save_state
from scrapers.windows import resolve_window, window_key

log = logging.getLogger(__name__)

SOURCE_ID = "congress-bills"
SOURCE_NAME = "Congress.gov bills"
LIST_URL = "https://api.congress.gov/v3/bill"
PAGE_SIZE = 250

# type -> (public slug, chamber, display prefix)
BILL_TYPES = {
    "HR": ("house-bill", "house", "H.R."),
    "S": ("senate-bill", "senate", "S."),
    "HJRES": ("house-joint-resolution", "house", "H.J.Res."),
    "SJRES": ("senate-joint-resolution", "senate", "S.J.Res."),
    "HCONRES": ("house-concurrent-resolution", "house", "H.Con.Res."),
    "SCONRES": ("senate-concurrent-resolution", "senate", "S.Con.Res."),
    "HRES": ("house-resolution", "house", "H.Res."),
    "SRES": ("senate-resolution", "senate", "S.Res."),
}


def run_congress_bills(ctx: RunContext) -> Outcome:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        return Outcome(
            records=0,
            errors=["DATA_GOV_API_KEY is not set; Congress.gov bills were not fetched."],
            checked=False,
        )
    state_path = ctx.state_dir / f"{SOURCE_ID}.json"
    state = load_state(state_path)
    state, start, end = _prepare(state, ctx)
    save_state(state_path, state)
    outcome = Outcome()
    while True:
        offset = int(state["offset"])
        params = [
            ("format", "json"),
            ("limit", str(PAGE_SIZE)),
            ("offset", str(offset)),
            ("fromDateTime", f"{start.isoformat()}T00:00:00Z"),
            ("toDateTime", f"{end.isoformat()}T23:59:59Z"),
            ("sort", "updateDate asc"),
            ("api_key", key),
        ]
        try:
            payload = ctx.client.get_json(LIST_URL, params=params)
        except HttpError as exc:
            outcome.errors.append(str(exc))
            save_state(state_path, state)
            return outcome
        if "error" in payload and "bills" not in payload:
            code = ""
            error = payload.get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or "")
            outcome.errors.append(f"Congress.gov returned {code or 'an error'}")
            save_state(state_path, state)
            return outcome
        bills = payload.get("bills")
        if not isinstance(bills, list):
            outcome.errors.append("Congress.gov bill list did not include a bills array")
            save_state(state_path, state)
            return outcome
        mapped, problems = _map_page(ctx, bills)
        accepted, validation_errors = publish_federal(ctx, SOURCE_ID, mapped)
        outcome.records += accepted
        outcome.errors.extend(validation_errors)
        outcome.errors.extend(problems)
        log.info("congress-bills offset %s: %s bills", offset, len(bills))
        state["offset"] = offset + len(bills)
        raw_pagination = payload.get("pagination")
        pagination = raw_pagination if isinstance(raw_pagination, dict) else {}
        more = bool(bills) and bool(pagination.get("next"))
        if not more:
            state["in_progress"] = False
            state["offset"] = 0
            state["completed_through"] = end.isoformat()
            outcome.checked = True
            if outcome.records == 0:
                mark_checked(ctx, ctx.federal_path, "date")
        save_state(state_path, state)
        if not more:
            break
    return outcome


def _summary(action_text: object) -> str | None:
    if not isinstance(action_text, str):
        return None
    text = action_text.strip()
    return text or None


def map_bill(raw: dict) -> dict:
    congress = raw.get("congress")
    number = str(raw.get("number") or "").strip()
    bill_type = str(raw.get("type") or "").strip().upper()
    if not isinstance(congress, int) or not number or not bill_type:
        raise ValueError("bill is missing congress, type, or number")
    if bill_type not in BILL_TYPES:
        raise ValueError(f"unexpected bill type {bill_type}")
    slug, chamber, label = BILL_TYPES[bill_type]
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{bill_type} {number} is missing a title")
    latest = raw.get("latestAction") if isinstance(raw.get("latestAction"), dict) else {}
    action_date = latest.get("actionDate") if isinstance(latest.get("actionDate"), str) else ""
    update_date = raw.get("updateDate") if isinstance(raw.get("updateDate"), str) else ""
    when = action_date or update_date
    if not when:
        raise ValueError(f"{bill_type} {number} is missing a date")
    action_text = latest.get("text") if isinstance(latest.get("text"), str) else None
    return {
        "id": f"{bill_type.lower()}-{number}-{congress}",
        "kind": "bill",
        "title": title.strip(),
        "date": when,
        "url": (
            f"https://www.congress.gov/bill/{ordinal(int(congress))}-congress/{slug}/{number}"
        ),
        "source": "Congress.gov",
        "summary": _summary(action_text),
        "identifier": f"{label} {number}",
        "chamber": chamber,
    }


def _map_page(ctx: RunContext, bills: list) -> tuple[list[dict], list[str]]:
    mapped: list[dict] = []
    failed = 0
    for raw in bills:
        if not isinstance(raw, dict):
            failed += 1
            continue
        try:
            mapped.append(map_bill(raw))
        except ValueError as exc:
            failed += 1
            record_id = f"{raw.get('type') or 'bill'}-{raw.get('number') or 'unknown'}"
            quarantine(ctx.state_dir, SOURCE_ID, str(record_id), _scrub(raw), str(exc))
    errors = []
    if failed:
        errors.append(f"{failed} congress-bills records failed validation and were quarantined.")
    return mapped, errors


def _scrub(value):
    if isinstance(value, str):
        return strip_api_key(value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _prepare(state: dict, ctx: RunContext) -> tuple[dict, date, date]:
    window = state.get("window")
    resume = (
        ctx.cli_start is None
        and ctx.cli_end is None
        and state.get("in_progress")
        and isinstance(window, list)
        and len(window) == 2
    )
    if resume:
        state["offset"] = int(state.get("offset") or 0)
        return state, date.fromisoformat(window[0]), date.fromisoformat(window[1])
    start, end = resolve_window(state, ctx)
    key = window_key(start, end)
    if state.get("window") == key and state.get("in_progress"):
        state["offset"] = int(state.get("offset") or 0)
        return state, start, end
    return (
        {
            "window": key,
            "completed_through": state.get("completed_through"),
            "offset": 0,
            "in_progress": True,
        },
        start,
        end,
    )
