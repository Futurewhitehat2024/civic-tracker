from scrapers.export import FEDERAL_COLUMNS, write_exports


def test_versioned_json_csv_and_manifest(tmp_path) -> None:
    items = [
        {
            "id": "fr-1",
            "kind": "federal_register",
            "title": "Example",
            "date": "2026-11-12",
            "url": "https://www.federalregister.gov/documents/2026/11/12/1/example",
            "source": "Federal Register",
            "summary": None,
            "identifier": "1",
            "chamber": None,
            "documentType": "Rule",
            "tags": ["tariff", "ustr"],
            "jurisdiction": {"level": "federal", "state": None, "countyFips": None},
        }
    ]
    export_dir = tmp_path / "v1"
    manifest = write_exports(
        export_dir,
        updated="2026-11-25T21:00:00-05:00",
        manifest_path=tmp_path / "manifest.json",
        datasets=[
            {
                "id": "federal",
                "title": "Federal actions",
                "json_name": "federal.json",
                "csv_name": "federal.csv",
                "columns": FEDERAL_COLUMNS,
                "items": items,
                "lastUpdated": "2026-11-25T21:00:00-05:00",
            }
        ],
    )
    assert manifest["schemaVersion"] == "1.1.0"
    assert manifest["datasets"][0]["count"] == 1
    assert manifest["excluded"][0]["id"] == "trades"
    csv_text = (export_dir / "federal.csv").read_text(encoding="utf-8")
    assert "tariff|ustr" in csv_text
    assert "federal" in csv_text.splitlines()[0] or "id,kind,title" in csv_text
