from scrapers.tags import tag_tariff_trade


def test_tags_section_232_and_ustr() -> None:
    item = {
        "kind": "federal_register",
        "title": "Section 232 tariffs on imported steel",
        "summary": "Issued under the Trade Expansion Act.",
        "agencies": [
            {
                "name": "Office of the United States Trade Representative",
                "slug": "office-of-the-united-states-trade-representative",
            }
        ],
    }
    assert tag_tariff_trade(item) == ["section-232", "tariff", "ustr"]


def test_tags_ieepa_hts_and_cbp() -> None:
    item = {
        "kind": "executive_order",
        "title": "Adjusting imports under IEEPA",
        "summary": "Amend the Harmonized Tariff Schedule of the United States.",
        "agencies": ["U.S. Customs and Border Protection"],
    }
    assert tag_tariff_trade(item) == ["cbp", "hts", "ieepa", "tariff"]


def test_tags_skip_bills() -> None:
    item = {
        "kind": "bill",
        "title": "A bill to amend section 301 tariff policy",
        "summary": None,
    }
    assert tag_tariff_trade(item) == []


def test_tags_ita_and_usitc_from_agency_only() -> None:
    item = {
        "kind": "federal_register",
        "title": "Routine procedural notice",
        "summary": None,
        "agencies": [
            {
                "slug": "international-trade-administration",
                "name": "International Trade Administration",
            },
            {"slug": "international-trade-commission", "name": "International Trade Commission"},
        ],
    }
    assert tag_tariff_trade(item) == ["ita", "usitc"]


def test_tags_ignore_section_301_of_other_statutes() -> None:
    fda = {
        "kind": "federal_register",
        "title": "N-acetyl-L-cysteine dietary supplements",
        "summary": "Not a prohibited act under section 301(ll) of the FD&C Act.",
    }
    sbic = {
        "kind": "federal_register",
        "title": "SBIC License Issuance",
        "summary": "Authority under section 301(c) of the Small Business Investment Act of 1958.",
    }
    assert tag_tariff_trade(fda) == []
    assert tag_tariff_trade(sbic) == []


def test_tags_agency_names_in_title() -> None:
    item = {
        "kind": "federal_register",
        "title": (
            "Request for Comments Regarding International Trade "
            "Commission's Economic Analysis"
        ),
        "summary": "Pursuant to Section 332 of the Tariff Act of 1930.",
    }
    assert "usitc" in tag_tariff_trade(item)
    assert "tariff" in tag_tariff_trade(item)
