"""Federal Register documents: rules, proposed rules, and executive orders.

The API needs no key. A window larger than the API's 10,000-hit page cap is
split by date. Smaller windows are read to the last page.
"""

import logging
import re
from datetime import date
from html import unescape

from scrapers.config import FEDERAL_REGISTER_MAX_HITS, FEDERAL_REGISTER_PAGE_SIZE
from scrapers.context import Outcome, RunContext
from scrapers.http_client import HttpError
from scrapers.publish import mark_checked, publish_federal
from scrapers.store import load_state, quarantine, save_state
from scrapers.windows import resolve_window, split_range, window_key

log = logging.getLogger(__name__)

SOURCE_ID = "federal-register"
SOURCE_NAME = "Federal Register"
LIST_URL = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS = (
    "document_number",
    "title",
    "type",
    "subtype",
    "executive_order_number",
    "publication_date",
    "html_url",
    "abstract",
    "citation",
)
_TAGS = re.compile(r"<[^>]+>")


class WindowTooWide(Exception):
    """The date span must be narrowed before any documents are published."""


def run_federal_register(ctx: RunContext) -> Outcome:
    state_path = ctx.state_dir / f"{SOURCE_ID}.json"
    state = load_state(state_path)
    state = _ensure_tasks(state, ctx)
    save_state(state_path, state)
    outcome = Outcome(checked=False)
    while state["tasks"]:
        task = state["tasks"][0]
        start = date.fromisoformat(task["start"])
        end = date.fromisoformat(task["end"])
        page = int(task["page"])
        try:
            payload = ctx.client.get_json(LIST_URL, params=_params(task["kind"], start, end, page))
            items, rejected, done = _read_page(payload, task["kind"], start, end, page)
        except WindowTooWide:
            pieces = split_range(start, end)
            if pieces is None:
                outcome.errors.append(
                    "Federal Register returned more than "
                    f"{FEDERAL_REGISTER_MAX_HITS} documents for {start.isoformat()}. "
                    "That day was not published."
                )
                state["tasks"].pop(0)
                save_state(state_path, state)
                continue
            left, right = pieces
            log.info(
                "federal-register splitting %s %s..%s at %s",
                task["kind"],
                start,
                end,
                left[1],
            )
            state["tasks"] = [
                _task(task["kind"], left[0], left[1]),
                _task(task["kind"], right[0], right[1]),
                *state["tasks"][1:],
            ]
            save_state(state_path, state)
            continue
        except HttpError as exc:
            outcome.errors.append(str(exc))
            save_state(state_path, state)
            return outcome
        for record_id, raw, reason in rejected:
            quarantine(ctx.state_dir, SOURCE_ID, record_id, raw, reason)
        if rejected:
            outcome.errors.append(
                f"{len(rejected)} federal-register records failed validation and were quarantined."
            )
        accepted, problems = publish_federal(ctx, SOURCE_ID, items)
        outcome.records += accepted
        outcome.errors.extend(problems)
        if done:
            state["tasks"].pop(0)
        else:
            task["page"] = page + 1
        save_state(state_path, state)
    state["completed_through"] = state["window"][1]
    state["tasks"] = []
    save_state(state_path, state)
    if outcome.records == 0:
        mark_checked(ctx, ctx.federal_path, "date")
    outcome.checked = True
    return outcome


def _ensure_tasks(state: dict, ctx: RunContext) -> dict:
    if state.get("tasks") and ctx.cli_start is None and ctx.cli_end is None:
        return state
    start, end = resolve_window(state, ctx)
    key = window_key(start, end)
    if state.get("window") == key and state.get("tasks"):
        return state
    return {
        "window": key,
        "completed_through": state.get("completed_through"),
        "tasks": [
            {"kind": "rules", "start": key[0], "end": key[1], "page": 1},
            {"kind": "executive_orders", "start": key[0], "end": key[1], "page": 1},
        ],
    }


def _task(kind: str, start: date, end: date) -> dict:
    return {"kind": kind, "start": start.isoformat(), "end": end.isoformat(), "page": 1}


def _params(kind: str, start: date, end: date, page: int) -> list[tuple[str, str]]:
    params = [
        ("per_page", str(FEDERAL_REGISTER_PAGE_SIZE)),
        ("order", "oldest"),
        ("page", str(page)),
        ("conditions[publication_date][gte]", start.isoformat()),
        ("conditions[publication_date][lte]", end.isoformat()),
    ]
    params.extend(("fields[]", field) for field in FIELDS)
    if kind == "rules":
        params.append(("conditions[type][]", "RULE"))
        params.append(("conditions[type][]", "PRORULE"))
    elif kind == "executive_orders":
        params.append(("conditions[presidential_document_type][]", "executive_order"))
    else:
        raise ValueError(f"unknown Federal Register task {kind}")
    return params


def _read_page(
    payload: dict,
    kind: str,
    start: date,
    end: date,
    page: int,
) -> tuple[list[dict], list[tuple[str, dict, str]], bool]:
    _raise_if_api_error(payload)
    count = payload.get("count")
    if not isinstance(count, int):
        raise HttpError("Federal Register response did not include a document count")
    if page == 1 and count > FEDERAL_REGISTER_MAX_HITS:
        raise WindowTooWide(count)
    results = payload.get("results")
    # A zero-hit query is `{"count": 0, "description": ...}` with no results key.
    if count == 0 and not isinstance(results, list):
        results = []
    if not isinstance(results, list):
        raise HttpError(
            "Federal Register response did not include results "
            f"for {count} matching documents"
        )
    log.info(
        "federal-register %s %s..%s page %s: %s of %s",
        kind,
        start,
        end,
        page,
        len(results),
        count,
    )
    items: list[dict] = []
    rejected: list[tuple[str, dict, str]] = []
    for raw in results:
        if not isinstance(raw, dict):
            rejected.append(("document", {}, "Federal Register result was not an object"))
            continue
        try:
            items.append(_map_document(raw, kind))
        except ValueError as exc:
            record_id = str(raw.get("document_number") or "document")
            rejected.append((record_id, raw, str(exc)))
    fetched = page * FEDERAL_REGISTER_PAGE_SIZE
    done = len(results) < FEDERAL_REGISTER_PAGE_SIZE or fetched >= count
    return items, rejected, done


def _raise_if_api_error(payload: dict) -> None:
    """Surface an error document instead of treating it as a normal page."""
    status = payload.get("status")
    message = payload.get("message")
    detail = message.strip() if isinstance(message, str) and message.strip() else ""
    if isinstance(status, int) and status >= 400:
        text = detail or "request failed"
        raise HttpError(f"Federal Register API error HTTP {status}: {text}")
    if detail and "count" not in payload and "results" not in payload:
        raise HttpError(f"Federal Register API error: {detail}")


def _map_document(raw: dict, kind: str) -> dict:
    document_number = raw.get("document_number")
    title = raw.get("title")
    if not isinstance(document_number, str) or not document_number.strip():
        raise ValueError("Federal Register document is missing document_number")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Federal Register document {document_number} is missing a title")
    subtype = (raw.get("subtype") or "").strip() if isinstance(raw.get("subtype"), str) else ""
    doc_type = (raw.get("type") or "").strip() if isinstance(raw.get("type"), str) else ""
    if kind == "executive_orders":
        if subtype != "Executive Order":
            label = subtype or doc_type or "untyped"
            raise ValueError(
                f"Federal Register document {document_number} was {label}, not an executive order"
            )
        feed_kind = "executive_order"
        number = raw.get("executive_order_number")
        if isinstance(number, str) and number.strip():
            identifier = f"EO {number.strip()}"
        else:
            identifier = document_number
    elif kind == "rules":
        if doc_type not in {"Rule", "Proposed Rule"}:
            raise ValueError(
                f"Federal Register document {document_number} has type {doc_type or 'missing'}"
            )
        feed_kind = "federal_register"
        identifier = document_number
    else:
        raise ValueError(f"unknown Federal Register task {kind}")
    return {
        "id": f"fr-{document_number.strip()}",
        "kind": feed_kind,
        "title": title.strip(),
        "date": raw.get("publication_date"),
        "url": raw.get("html_url"),
        "source": "Federal Register",
        "summary": _plain(raw.get("abstract")),
        "identifier": identifier,
        "chamber": None,
    }


def _plain(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = unescape(_TAGS.sub(" ", value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
