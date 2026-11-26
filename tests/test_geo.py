from scrapers.geo import (
    county_pack,
    coverage_payload,
    load_florida_counties,
    normalize_jurisdiction,
)


def test_florida_registry_has_all_counties_and_test_status() -> None:
    registry = load_florida_counties()
    counties = {row["fips"]: row for row in registry["counties"]}
    assert len(counties) == 67
    assert counties["12021"]["name"] == "Collier"
    assert counties["12021"]["status"] == "in_test"
    assert counties["12071"]["name"] == "Lee"
    assert counties["12071"]["status"] == "in_test"
    assert counties["12021"]["sources"]
    assert counties["12001"]["status"] == "planned"


def test_county_pack_is_home_plus_florida_neighbors() -> None:
    pack = county_pack("12021")
    assert pack[0] == "12021"
    assert "12071" in pack  # Lee
    assert "12051" in pack  # Hendry


def test_coverage_payload_and_jurisdiction() -> None:
    payload = coverage_payload("2026-11-25T21:00:00-05:00")
    assert payload["states"][0]["code"] == "FL"
    assert payload["summary"]["inTest"] == ["12021", "12071"]
    assert "influencerProgram" in payload["notes"]
    assert normalize_jurisdiction({"level": "county", "state": "fl", "countyFips": "12021"}) == {
        "level": "county",
        "state": "FL",
        "countyFips": "12021",
    }
