"""Add package fields to existing feeds and write derived package files.

Congressional trade records are never rewritten here and are not exported.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from scrapers.config import SCHEMA_VERSION
from scrapers.deadlines import load_deadline_feeds, write_calendar, write_deadlines
from scrapers.export import (
    COUNTY_COLUMNS,
    COVERAGE_COLUMNS,
    DEADLINE_COLUMNS,
    FEDERAL_COLUMNS,
    coverage_rows,
    write_exports,
)
from scrapers.geo import coverage_payload, federal_jurisdiction, jurisdiction_for
from scrapers.http_client import HttpError
from scrapers.store import load_feed, save_json, sort_items
from scrapers.tags import merge_agency_names, tag_tariff_trade
from scrapers.validate import validate_county, validate_federal

log = logging.getLogger(__name__)

FR_DOCUMENT_URL = "https://www.federalregister.gov/api/v1/documents/{numbers}.json"
FR_FIELDS = ("document_number", "comments_close_on", "effective_on", "agencies")
BACKFILL_BATCH = 25


def finalize_package_data(ctx, *, backfill_deadlines: bool = True) -> None:
    """Enrich live feeds and write deadlines, coverage, and versioned exports."""
    if backfill_deadlines:
        _backfill_federal_register_fields(ctx)
    federal = _enrich_feed(ctx.federal_path, validate_federal)
    notices_path = ctx.federal_path.with_name("federal-notices.json")
    notices = _enrich_feed(notices_path, validate_federal, missing_ok=True)
    counties_path = ctx.federal_path.with_name("counties.json")
    counties = _enrich_feed(counties_path, validate_county, missing_ok=True)
    if federal is not None:
        save_json(
            ctx.federal_path,
            {"updated": ctx.now, "items": sort_items(federal, "date")},
        )
    if notices is not None:
        save_json(notices_path, {"updated": ctx.now, "items": sort_items(notices, "date")})
    if counties is not None:
        save_json(
            counties_path,
            {"updated": ctx.now, "items": sort_items(counties, "date")},
        )
    data_dir = ctx.federal_path.parent
    coverage = coverage_payload(ctx.now)
    save_json(data_dir / "coverage.json", coverage)
    deadline_rows = load_deadline_feeds(ctx.federal_path, notices_path)
    write_deadlines(data_dir / "deadlines.json", deadline_rows, updated=ctx.now)
    write_calendar(data_dir / "deadlines.ics", deadline_rows)
    write_exports(
        data_dir / "v1",
        updated=ctx.now,
        manifest_path=data_dir / "manifest.json",
        datasets=[
            {
                "id": "federal",
                "title": "Federal actions",
                "json_name": "federal.json",
                "csv_name": "federal.csv",
                "columns": FEDERAL_COLUMNS,
                "items": (federal or []),
                "lastUpdated": ctx.now,
            },
            {
                "id": "federal-notices",
                "title": "Federal Register notices",
                "json_name": "federal-notices.json",
                "csv_name": "federal-notices.csv",
                "columns": FEDERAL_COLUMNS,
                "items": (notices or []),
                "lastUpdated": ctx.now,
            },
            {
                "id": "deadlines",
                "title": "Comment deadlines and effective dates",
                "json_name": "deadlines.json",
                "csv_name": "deadlines.csv",
                "columns": DEADLINE_COLUMNS,
                "items": deadline_rows,
                "lastUpdated": ctx.now,
            },
            {
                "id": "counties",
                "title": "Florida county meetings",
                "json_name": "counties.json",
                "csv_name": "counties.csv",
                "columns": COUNTY_COLUMNS,
                "items": (counties or []),
                "lastUpdated": ctx.now,
            },
            {
                "id": "coverage",
                "title": "Jurisdiction coverage and county packs",
                "json_name": "coverage.json",
                "csv_name": "coverage.csv",
                "columns": COVERAGE_COLUMNS,
                "items": coverage_rows(coverage),
                "raw_json": coverage,
                "count": sum(len(state.get("counties") or []) for state in coverage["states"]),
                "lastUpdated": ctx.now,
            },
        ],
    )
    log.info(
        "package exports schema %s: federal %s notices %s deadlines %s counties %s",
        SCHEMA_VERSION,
        len(federal or []),
        len(notices or []),
        len(deadline_rows),
        len(counties or []),
    )


def enrich_record(item: dict) -> dict:
    kind = item.get("kind")
    if kind == "meeting":
        record = dict(item)
        record["jurisdiction"] = jurisdiction_for(record)
        record["tags"] = list(record.get("tags") or [])
        return validate_county(record)
    record = dict(item)
    if not record.get("jurisdiction"):
        record["jurisdiction"] = federal_jurisdiction()
    else:
        record["jurisdiction"] = jurisdiction_for(record)
    if record.get("agencies"):
        record["agencies"] = merge_agency_names(record["agencies"]) or record["agencies"]
    record["tags"] = tag_tariff_trade(record)
    return validate_federal(record)


def _enrich_feed(path, validator, *, missing_ok: bool = False) -> list[dict] | None:
    if not path.exists():
        if missing_ok:
            return []
        return None
    feed = load_feed(path)
    items: list[dict] = []
    for raw in feed.get("items") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        if validator is validate_federal:
            items.append(enrich_record(raw))
        else:
            items.append(enrich_record(raw) if raw.get("kind") == "meeting" else validator(raw))
    return items


def _backfill_federal_register_fields(ctx) -> None:
    """Fill comment and effective dates on stored Federal Register records."""
    client = getattr(ctx, "client", None)
    if client is None or not hasattr(client, "get_json"):
        return
    paths = [ctx.federal_path, ctx.federal_path.with_name("federal-notices.json")]
    needed: list[tuple[object, dict]] = []
    for path in paths:
        if not path.exists():
            continue
        feed = load_feed(path)
        for item in feed.get("items") or []:
            if not isinstance(item, dict):
                continue
            if item.get("kind") not in {"federal_register", "executive_order"}:
                continue
            if _already_backfilled(item):
                continue
            if not _document_number(item):
                continue
            needed.append((path, item))
    if not needed:
        return
    numbers = []
    seen: set[str] = set()
    for _path, item in needed:
        number = _document_number(item)
        if number in seen:
            continue
        seen.add(number)
        numbers.append(number)
    fetched: dict[str, dict] = {}
    for start in range(0, len(numbers), BACKFILL_BATCH):
        batch = numbers[start : start + BACKFILL_BATCH]
        try:
            payload = _fetch_documents(client, batch)
        except HttpError as exc:
            log.warning("Federal Register deadline backfill stopped: %s", exc)
            break
        fetched.update(payload)
    if not fetched:
        return
    by_path: dict[object, list[dict]] = {}
    for path, item in needed:
        by_path.setdefault(path, []).append(item)
    for path, items in by_path.items():
        feed = load_feed(path)
        changed = False
        by_id = {
            str(row["id"]): row
            for row in feed.get("items") or []
            if isinstance(row, dict) and row.get("id")
        }
        for item in items:
            extra = fetched.get(_document_number(item) or "")
            if not extra:
                continue
            current = by_id.get(str(item["id"]))
            if current is None:
                continue
            current["commentsCloseOn"] = _iso_or_none(extra.get("comments_close_on"))
            current["effectiveOn"] = _iso_or_none(extra.get("effective_on"))
            names = merge_agency_names(extra.get("agencies"))
            current["agencies"] = names
            changed = True
        if changed:
            save_json(path, feed)


def _already_backfilled(item: dict) -> bool:
    """True once a successful API backfill or a live scrape wrote these keys."""
    return "commentsCloseOn" in item and "effectiveOn" in item


def _iso_or_none(value: object) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    return value[:10]


def _document_number(item: dict) -> str | None:
    record_id = str(item.get("id") or "")
    if record_id.startswith("fr-"):
        return record_id[3:]
    identifier = item.get("identifier")
    if isinstance(identifier, str) and identifier and not identifier.startswith("EO "):
        return identifier
    url = item.get("url")
    if isinstance(url, str):
        parts = urlsplit(url).path.strip("/").split("/")
        for part in reversed(parts):
            if part and part[0].isdigit():
                return part
    return None


def _fetch_documents(client, numbers: list[str]) -> dict[str, dict]:
    url = FR_DOCUMENT_URL.format(numbers=",".join(numbers))
    params = [("fields[]", field) for field in FR_FIELDS]
    if hasattr(client, "get"):
        response = client.get(url, params=params)
        payload = response.json()
    else:
        payload = client.get_json(url, params=params)
    return _index_documents(payload)


def _index_documents(payload: object) -> dict[str, dict]:
    records: list[dict] = []
    if isinstance(payload, list):
        records = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            records = [row for row in payload["results"] if isinstance(row, dict)]
        elif "document_number" in payload:
            records = [payload]
        else:
            records = [row for row in payload.values() if isinstance(row, dict)]
    indexed: dict[str, dict] = {}
    for row in records:
        number = row.get("document_number")
        if isinstance(number, str) and number.strip():
            indexed[number.strip()] = row
    return indexed
