"""Paths, identity, and polite request limits."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
STATE_DIR = ROOT / "state"
FEDERAL_PATH = DATA_DIR / "federal.json"
TRADES_PATH = DATA_DIR / "trades.json"
STATUS_PATH = DATA_DIR / "status.json"

USER_AGENT = (
    "CivicTracker-bot/1.0 (+https://github.com/Futurewhitehat2024/civic-tracker)"
)

# Senate eFD search requires accepting a terms gate. Do not request this host.
BLOCKED_HOSTS = frozenset({"efdsearch.senate.gov"})

# Seconds between requests to the same host. Congress.gov's published cap is
# 5,000/hour. These pauses stay far under that and match a 1/second clerk pace.
HOST_INTERVAL_SECONDS = {
    "api.congress.gov": 0.8,
    "www.federalregister.gov": 1.0,
    "clerk.house.gov": 1.0,
    "www.senate.gov": 1.0,
    "disclosures-clerk.house.gov": 1.0,
}
DEFAULT_INTERVAL_SECONDS = 1.0

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3

# Federal Register asks clients not to page past the first 2,000 hits.
FEDERAL_REGISTER_MAX_HITS = 2000
FEDERAL_REGISTER_PAGE_SIZE = 1000

# First run, when a source has no cursor and the workflow did not pass dates.
DEFAULT_LOOKBACK_DAYS = 14

API_KEY_ENV = "DATA_GOV_API_KEY"
