"""Run the selected sources. One source failing does not stop the others."""

import logging

from scrapers.context import Outcome, RunContext
from scrapers.publish import publish_status
from scrapers.redact import redact
from scrapers.sources.congress_bills import SOURCE_ID as BILLS_ID
from scrapers.sources.congress_bills import SOURCE_NAME as BILLS_NAME
from scrapers.sources.congress_bills import run_congress_bills
from scrapers.sources.federal_register import SOURCE_ID as REGISTER_ID
from scrapers.sources.federal_register import SOURCE_NAME as REGISTER_NAME
from scrapers.sources.federal_register import run_federal_register
from scrapers.sources.house_ptr import SOURCE_ID as PTR_ID
from scrapers.sources.house_ptr import SOURCE_NAME as PTR_NAME
from scrapers.sources.house_ptr import run_house_ptr
from scrapers.sources.house_votes import SOURCE_ID as HOUSE_ID
from scrapers.sources.house_votes import SOURCE_NAME as HOUSE_NAME
from scrapers.sources.house_votes import run_house_votes
from scrapers.sources.senate_efd import SOURCE_ID as EFD_ID
from scrapers.sources.senate_efd import SOURCE_NAME as EFD_NAME
from scrapers.sources.senate_efd import run_senate_efd
from scrapers.sources.senate_votes import SOURCE_ID as SENATE_ID
from scrapers.sources.senate_votes import SOURCE_NAME as SENATE_NAME
from scrapers.sources.senate_votes import run_senate_votes

log = logging.getLogger(__name__)

SOURCES: list[tuple[str, str, object]] = [
    (REGISTER_ID, REGISTER_NAME, run_federal_register),
    (HOUSE_ID, HOUSE_NAME, run_house_votes),
    (SENATE_ID, SENATE_NAME, run_senate_votes),
    (BILLS_ID, BILLS_NAME, run_congress_bills),
    (PTR_ID, PTR_NAME, run_house_ptr),
    (EFD_ID, EFD_NAME, run_senate_efd),
]

FEDERAL_IDS = [REGISTER_ID, HOUSE_ID, SENATE_ID, BILLS_ID]
TRADE_IDS = [PTR_ID, EFD_ID]


def parse_sources(raw: str | None) -> list[str]:
    text = (raw or "all").strip().lower()
    known = {source_id for source_id, _name, _fn in SOURCES}
    if text in {"", "all"}:
        return [source_id for source_id, _name, _fn in SOURCES]
    if text == "federal":
        return list(FEDERAL_IDS)
    if text == "trades":
        return list(TRADE_IDS)
    selected: list[str] = []
    for part in text.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name == "federal":
            for source_id in FEDERAL_IDS:
                if source_id not in selected:
                    selected.append(source_id)
            continue
        if name not in known:
            known_list = ", ".join(sorted(known | {"all", "federal", "trades"}))
            raise SystemExit(f"Unknown source {name!r}. Choose from: {known_list}")
        if name not in selected:
            selected.append(name)
    if not selected:
        raise SystemExit("No sources selected")
    return selected


def run_sources(ctx: RunContext, source_ids: list[str]) -> None:
    by_id = {source_id: (name, fn) for source_id, name, fn in SOURCES}
    for source_id in source_ids:
        name, fn = by_id[source_id]
        log.info("starting %s", source_id)
        try:
            outcome = fn(ctx)
        except Exception as exc:
            secrets = list(getattr(ctx.client, "secrets", []) or [])
            message = redact(str(exc), secrets) or f"{source_id} failed"
            log.error("%s failed: %s", source_id, message)
            outcome = Outcome(records=0, errors=[message], checked=False)
        secrets = list(getattr(ctx.client, "secrets", []) or [])
        errors = [redact(error, secrets) for error in (outcome.errors or [])]
        publish_status(
            ctx,
            {
                "id": source_id,
                "name": name,
                "lastRun": ctx.now,
                "records": outcome.records,
                "errors": errors,
            },
        )
        log.info("%s records %s errors %s", source_id, outcome.records, len(errors))
