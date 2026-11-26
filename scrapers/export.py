"""Stable versioned JSON and CSV exports plus a manifest."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from scrapers.store import save_json

SCHEMA_VERSION = "1.1.0"

FEDERAL_COLUMNS = [
    "id",
    "kind",
    "title",
    "date",
    "url",
    "source",
    "summary",
    "identifier",
    "chamber",
    "documentType",
    "commentsCloseOn",
    "effectiveOn",
    "agencies",
    "tags",
    "jurisdiction.level",
    "jurisdiction.state",
    "jurisdiction.countyFips",
]

DEADLINE_COLUMNS = [
    "id",
    "recordId",
    "kind",
    "date",
    "title",
    "url",
    "source",
    "documentType",
    "tags",
    "jurisdiction.level",
    "jurisdiction.state",
    "jurisdiction.countyFips",
]

COUNTY_COLUMNS = FEDERAL_COLUMNS

COVERAGE_COLUMNS = [
    "state",
    "name",
    "fullName",
    "fips",
    "status",
    "borders",
    "pack",
]


def write_exports(
    export_dir: Path,
    *,
    updated: str,
    datasets: list[dict[str, Any]],
    manifest_path: Path,
) -> dict:
    export_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for dataset in datasets:
        json_name = dataset["json_name"]
        csv_name = dataset["csv_name"]
        columns = dataset["columns"]
        items = dataset["items"]
        last_updated = dataset.get("lastUpdated") or updated
        json_payload = {
            "updated": last_updated,
            "schemaVersion": SCHEMA_VERSION,
            "dataset": dataset["id"],
            "items": items,
        }
        json_path = export_dir / json_name
        if dataset.get("raw_json") is not None:
            json_path.write_text(
                json.dumps(dataset["raw_json"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        else:
            save_json(json_path, json_payload)
        write_csv(export_dir / csv_name, items, columns)
        entries.append(
            {
                "id": dataset["id"],
                "title": dataset["title"],
                "json": f"v1/{json_name}",
                "csv": f"v1/{csv_name}",
                "count": dataset.get("count", len(items)),
                "lastUpdated": last_updated,
                "schemaVersion": SCHEMA_VERSION,
            }
        )
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "updated": updated,
        "datasets": entries,
        "excluded": [
            {
                "id": "trades",
                "reason": (
                    "Congressional stock-trade filings stay on the free public news "
                    "page and are not part of the package API or bulk export."
                ),
            }
        ],
    }
    save_json(manifest_path, manifest)
    save_json(export_dir / "manifest.json", manifest)
    return manifest


def write_csv(path: Path, items: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow({column: _csv_value(item, column) for column in columns})


def coverage_rows(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for state in payload.get("states") or []:
        code = state.get("code")
        for county in state.get("counties") or []:
            row = dict(county)
            row["state"] = code
            rows.append(row)
    return rows


def _csv_value(item: dict, column: str) -> str:
    if column.startswith("jurisdiction."):
        key = column.split(".", 1)[1]
        value = (item.get("jurisdiction") or {}).get(key) if isinstance(
            item.get("jurisdiction"), dict
        ) else None
    else:
        value = item.get(column)
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(str(part) for part in value)
    return str(value)
