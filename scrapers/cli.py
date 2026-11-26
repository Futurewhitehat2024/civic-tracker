"""Command line entry for the scheduled job and for a manual backfill."""

import argparse
import logging
import os

from scrapers.config import (
    API_KEY_ENV,
    DATA_DIR,
    FEDERAL_PATH,
    STATE_DIR,
    STATUS_PATH,
    TRADES_PATH,
)
from scrapers.context import RunContext
from scrapers.dates import now_iso, parse_cli_date, today_et
from scrapers.enrich import finalize_package_data
from scrapers.http_client import PoliteClient
from scrapers.runner import parse_sources, run_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch official federal actions and congressional trade filings."
    )
    parser.add_argument(
        "--sources",
        default=os.environ.get("SCRAPE_SOURCES", "all"),
        help="all, federal, or a comma-separated list of source ids",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        default=os.environ.get("SCRAPE_FROM") or None,
        help="Backfill start date YYYY-MM-DD. Default: saved cursor, or the last 14 days.",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        default=os.environ.get("SCRAPE_TO") or None,
        help="Backfill end date YYYY-MM-DD. Default: today in America/New_York.",
    )
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="Skip source fetches. Enrich stored feeds and write package exports.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # httpx logs the full request URL at INFO. That URL can carry the API key.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    source_ids = [] if args.finalize_only else parse_sources(args.sources)
    cli_start = parse_cli_date(args.from_date, "--from")
    cli_end = parse_cli_date(args.to_date, "--to")
    key = os.environ.get(API_KEY_ENV, "").strip()
    if key:
        logging.info("DATA_GOV_API_KEY is set")
    else:
        logging.info("DATA_GOV_API_KEY is not set; Congress.gov bills will be skipped")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with PoliteClient(secrets=[key] if key else []) as client:
        ctx = RunContext(
            client=client,
            federal_path=FEDERAL_PATH,
            trades_path=TRADES_PATH,
            status_path=STATUS_PATH,
            state_dir=STATE_DIR,
            cli_start=cli_start,
            cli_end=cli_end,
            today=today_et(),
            now=now_iso(),
        )
        if args.finalize_only:
            finalize_package_data(ctx)
        else:
            run_sources(ctx, source_ids)
    return 0
