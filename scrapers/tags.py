"""Tag Federal Register documents and executive orders for tariff and trade alerts."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Topic tags requested by the GovWatcher data-based packages.
_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("tariff", re.compile(r"\btariffs?\b", re.I)),
    ("ieepa", re.compile(r"\bieepa\b|international emergency economic powers", re.I)),
    ("hts", re.compile(r"\bhts(?:[\s-]?us)?\b|harmonized tariff", re.I)),
)
# Bare "section 301(c)" / "section 301(ll)" are other statutes, not Trade Act 301.
_SECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("section-232", re.compile(r"\b(?:section|sec\.?)\s*232\b(?!\s*\()", re.I)),
    ("section-301", re.compile(r"\b(?:section|sec\.?)\s*301\b(?!\s*\()", re.I)),
)
_TRADE_CONTEXT = re.compile(
    r"\b(?:trade act|trade expansion|ustr|tariffs?|customs|antidumping|"
    r"countervailing|ieepa|harmonized tariff|hts)\b",
    re.I,
)

# Agency slugs and name fragments from the Federal Register agency list.
_AGENCY_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ustr",
        (
            "office-of-the-united-states-trade-representative",
            "trade representative",
            " ustr",
        ),
    ),
    (
        "ita",
        (
            "international-trade-administration",
            "international trade administration",
        ),
    ),
    (
        "cbp",
        (
            "customs-and-border-protection",
            "customs and border protection",
            "customs and border-protection",
        ),
    ),
    (
        "usitc",
        (
            "international-trade-commission",
            "international trade commission",
            "usitc",
        ),
    ),
    (
        "bis",
        (
            "industry-and-security",
            "industry and security",
            "bureau of industry and security",
        ),
    ),
)

TAGGABLE_KINDS = frozenset({"federal_register", "executive_order"})


def tag_tariff_trade(item: dict) -> list[str]:
    """Return sorted unique tags. Bills and votes are left untagged."""
    if item.get("kind") not in TAGGABLE_KINDS:
        return []
    text = _haystack(item)
    tags: set[str] = set()
    for tag, pattern in _TOPIC_PATTERNS:
        if pattern.search(text):
            tags.add(tag)
    for tag, pattern in _SECTION_PATTERNS:
        if pattern.search(text) and _TRADE_CONTEXT.search(text):
            tags.add(tag)
    for tag in _agency_tags(item.get("agencies"), text):
        tags.add(tag)
    return sorted(tags)


def _haystack(item: dict) -> str:
    parts = [
        item.get("title"),
        item.get("summary"),
        item.get("identifier"),
        item.get("documentType"),
    ]
    return " ".join(part for part in parts if isinstance(part, str))


def _agency_tags(agencies: object, text: str = "") -> list[str]:
    tags: list[str] = []
    blobs = _agency_blobs(agencies)
    if text:
        blobs.append(text.lower())
    for blob in blobs:
        for tag, needles in _AGENCY_TAGS:
            if any(needle in blob for needle in needles):
                tags.append(tag)
    return tags


def _agency_blobs(agencies: object) -> list[str]:
    if not isinstance(agencies, list):
        return []
    blobs: list[str] = []
    for agency in agencies:
        if isinstance(agency, str):
            blobs.append(agency.lower())
            continue
        if not isinstance(agency, dict):
            continue
        bits: list[str] = []
        for key in ("slug", "name", "raw_name"):
            value = agency.get(key)
            if isinstance(value, str) and value.strip():
                bits.append(value)
        if bits:
            blobs.append(" ".join(bits).lower())
    return blobs


def merge_agency_names(agencies: object) -> list[str] | None:
    """Store a short list of official agency names, or None when the source has none."""
    if not isinstance(agencies, list) or not agencies:
        return None
    names: list[str] = []
    seen: set[str] = set()
    for agency in agencies:
        name = _agency_name(agency)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names or None


def _agency_name(agency: object) -> str | None:
    if isinstance(agency, str) and agency.strip():
        return agency.strip()
    if not isinstance(agency, dict):
        return None
    for key in ("name", "raw_name"):
        value = agency.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def has_any_tag(item: dict, tags: Iterable[str]) -> bool:
    have = {str(tag).lower() for tag in (item.get("tags") or [])}
    return any(tag.lower() in have for tag in tags)
