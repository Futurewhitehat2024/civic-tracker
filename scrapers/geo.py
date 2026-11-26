"""Jurisdiction fields and the Florida county coverage registry."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "fl_counties.json"

FEDERAL_JURISDICTION = {
    "level": "federal",
    "state": None,
    "countyFips": None,
}

IN_TEST_FIPS = frozenset({"12021", "12071"})


def load_florida_counties() -> dict:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("counties"), list):
        raise ValueError("fl_counties.json must include a counties array")
    return payload


def federal_jurisdiction() -> dict:
    return dict(FEDERAL_JURISDICTION)


def jurisdiction_for(item: dict) -> dict:
    existing = item.get("jurisdiction")
    if isinstance(existing, dict) and existing.get("level") in {"federal", "state", "county"}:
        return normalize_jurisdiction(existing)
    return federal_jurisdiction()


def normalize_jurisdiction(value: dict) -> dict:
    level = value.get("level")
    if level not in {"federal", "state", "county"}:
        raise ValueError(f"jurisdiction.level {level!r} is not federal, state, or county")
    state = _optional_state(value.get("state"))
    fips = _optional_fips(value.get("countyFips"))
    if level == "state" and not state:
        raise ValueError("state jurisdiction requires a state code")
    if level == "county" and (not state or not fips):
        raise ValueError("county jurisdiction requires a state code and county FIPS")
    if level == "federal":
        return {"level": "federal", "state": None, "countyFips": None}
    return {"level": level, "state": state, "countyFips": fips}


def county_jurisdiction(state: str, county_fips: str) -> dict:
    return normalize_jurisdiction(
        {"level": "county", "state": state, "countyFips": county_fips}
    )


def coverage_payload(updated: str) -> dict:
    registry = load_florida_counties()
    counties = []
    for raw in registry["counties"]:
        counties.append(
            {
                "name": raw["name"],
                "fullName": raw["fullName"],
                "fips": raw["fips"],
                "status": raw["status"],
                "borders": list(raw["borders"]),
                "pack": list(raw["pack"]),
                "sources": list(raw.get("sources") or []),
            }
        )
    in_test = [row["fips"] for row in counties if row["status"] == "in_test"]
    planned = [row["fips"] for row in counties if row["status"] == "planned"]
    return {
        "updated": updated,
        "schemaVersion": "1.1.0",
        "states": [
            {
                "code": "FL",
                "name": "Florida",
                "status": "in_test",
                "counties": counties,
            }
        ],
        "summary": {
            "inTest": in_test,
            "planned": planned,
            "live": [],
        },
        "notes": {
            "congressionalTrades": (
                "Congressional stock-trade filings are collected for the free public "
                "news page only. They are not included in package exports."
            ),
            "influencerProgram": (
                "The influencer referral program is a site and billing feature. "
                "The scraper does not collect it."
            ),
            "breaches": (
                "No live breach collector yet. Official source research is in "
                "docs/data/PLANNED-SOURCES.md."
            ),
        },
    }


def county_pack(fips: str) -> list[str]:
    registry = load_florida_counties()
    for row in registry["counties"]:
        if row["fips"] == fips:
            return list(row["pack"])
    raise KeyError(f"unknown Florida county FIPS {fips}")


def _optional_state(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("jurisdiction.state must be a string or null")
    code = value.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("jurisdiction.state must be a two-letter code")
    return code


def _optional_fips(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        value = f"{value:05d}"
    if not isinstance(value, str):
        raise ValueError("jurisdiction.countyFips must be a string or null")
    digits = value.strip()
    if len(digits) != 5 or not digits.isdigit():
        raise ValueError("jurisdiction.countyFips must be a 5-digit FIPS code")
    return digits
