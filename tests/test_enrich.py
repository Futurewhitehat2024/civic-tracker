import json
from pathlib import Path

from scrapers.enrich import finalize_package_data
from scrapers.sources.federal_register import _map_document
from scrapers.store import save_json
from tests.support import make_context


class FakeClient:
    def __init__(self, documents: dict[str, dict]) -> None:
        self.documents = documents
        self.calls: list[str] = []

    def get_json(self, url: str, *, params=None, headers=None) -> dict:
        self.calls.append(url)
        results = []
        for number, row in self.documents.items():
            if number in url:
                results.append(row)
        return {"results": results}


def test_map_document_copies_deadlines_agencies_and_tags() -> None:
    raw = {
        "document_number": "2026-10001",
        "title": "Section 301 tariff action",
        "type": "Proposed Rule",
        "subtype": None,
        "publication_date": "2026-11-12",
        "html_url": "https://www.federalregister.gov/documents/2026/11/12/2026-10001/example",
        "abstract": "Comments invited.",
        "comments_close_on": "2026-12-15",
        "effective_on": None,
        "agencies": [
            {
                "name": "Office of the United States Trade Representative",
                "slug": "office-of-the-united-states-trade-representative",
            }
        ],
    }
    record = _map_document(raw, "rules")
    assert record["commentsCloseOn"] == "2026-12-15"
    assert record["effectiveOn"] is None
    assert record["agencies"] == ["Office of the United States Trade Representative"]
    assert record["jurisdiction"]["level"] == "federal"
    assert "section-301" in record["tags"]
    assert "tariff" in record["tags"]
    assert "ustr" in record["tags"]


def test_enrich_and_finalize_writes_package_files(tmp_path: Path) -> None:
    federal = tmp_path / "federal.json"
    save_json(
        federal,
        {
            "updated": "2026-11-16T12:00:00-05:00",
            "items": [
                {
                    "id": "fr-2026-10001",
                    "kind": "federal_register",
                    "title": "Section 232 tariffs on steel",
                    "date": "2026-11-12",
                    "url": "https://www.federalregister.gov/documents/2026/11/12/2026-10001/example",
                    "source": "Federal Register",
                    "summary": None,
                    "identifier": "2026-10001",
                    "chamber": None,
                    "documentType": "Rule",
                },
                {
                    "id": "hr-1-119",
                    "kind": "bill",
                    "title": "Example Act",
                    "date": "2026-11-12",
                    "url": "https://www.congress.gov/bill/119th-congress/house-bill/1",
                    "source": "Congress.gov",
                    "summary": None,
                    "identifier": "H.R. 1",
                    "chamber": "house",
                },
            ],
        },
    )
    client = FakeClient(
        {
            "2026-10001": {
                "document_number": "2026-10001",
                "comments_close_on": None,
                "effective_on": "2026-12-01",
                "agencies": [
                    {"name": "Bureau of Industry and Security", "slug": "industry-and-security"}
                ],
            }
        }
    )
    ctx = make_context(tmp_path, client, federal_path=federal)
    finalize_package_data(ctx)
    payload = json.loads(federal.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["fr-2026-10001"]["effectiveOn"] == "2026-12-01"
    assert by_id["fr-2026-10001"]["agencies"] == ["Bureau of Industry and Security"]
    assert "section-232" in by_id["fr-2026-10001"]["tags"]
    assert "bis" in by_id["fr-2026-10001"]["tags"]
    assert by_id["hr-1-119"]["jurisdiction"]["level"] == "federal"
    assert by_id["hr-1-119"]["tags"] == []
    assert client.calls
    deadlines = json.loads((tmp_path / "deadlines.json").read_text(encoding="utf-8"))
    assert deadlines["items"][0]["date"] == "2026-12-01"
    assert deadlines["items"][0]["kind"] == "effective"
    ics = (tmp_path / "deadlines.ics").read_text(encoding="utf-8")
    assert "DTSTART;VALUE=DATE:20261201" in ics
    coverage = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert len(coverage["states"][0]["counties"]) == 67
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "1.1.0"
    assert manifest["excluded"][0]["id"] == "trades"
    assert (tmp_path / "v1" / "federal.csv").exists()
    # Congressional trades must not be written by finalize.
    assert not (tmp_path / "trades.json").exists()
    assert all(entry["id"] != "trades" for entry in manifest["datasets"])
