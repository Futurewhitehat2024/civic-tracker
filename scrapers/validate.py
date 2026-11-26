"""Check records against docs/data/SCHEMA.md before they are published."""

from urllib.parse import urlsplit

from scrapers.geo import federal_jurisdiction, normalize_jurisdiction
from scrapers.redact import strip_api_key

FEDERAL_KINDS = frozenset({"bill", "vote", "executive_order", "federal_register"})
CHAMBERS = frozenset({"house", "senate"})


def validate_federal(item: dict) -> dict:
    kind = _required(item, "kind")
    if kind not in FEDERAL_KINDS:
        raise ValueError(f"kind {kind!r} is not a federal feed kind")
    chamber = item.get("chamber")
    if chamber is not None and chamber not in CHAMBERS:
        raise ValueError(f"chamber {chamber!r} is not house or senate")
    if kind in {"executive_order", "federal_register"} and chamber not in {None, ""}:
        raise ValueError("executive and Federal Register items have no chamber")
    record = {
        "id": _required(item, "id"),
        "kind": kind,
        "title": _required(item, "title"),
        "date": _date(item.get("date"), "date"),
        "url": _url(item.get("url")),
        "source": _required(item, "source"),
        "summary": _optional_text(item.get("summary")),
        "identifier": _optional_text(item.get("identifier")),
        "chamber": chamber if chamber in CHAMBERS else None,
        "documentType": _optional_text(item.get("documentType")),
        "tags": _tags(item.get("tags")),
        "jurisdiction": _jurisdiction(item.get("jurisdiction"), default_federal=True),
    }
    _copy_register_fields(item, record)
    return record


def validate_county(item: dict) -> dict:
    kind = _required(item, "kind")
    if kind != "meeting":
        raise ValueError(f"kind {kind!r} is not a county meeting kind")
    record = {
        "id": _required(item, "id"),
        "kind": kind,
        "title": _required(item, "title"),
        "date": _date(item.get("date"), "date"),
        "url": _url(item.get("url")),
        "source": _required(item, "source"),
        "summary": _optional_text(item.get("summary")),
        "identifier": _optional_text(item.get("identifier")),
        "chamber": None,
        "documentType": _optional_text(item.get("documentType")),
        "tags": _tags(item.get("tags")),
        "jurisdiction": _jurisdiction(item.get("jurisdiction"), default_federal=False),
    }
    if record["jurisdiction"]["level"] != "county":
        raise ValueError("county meetings require county jurisdiction")
    _copy_register_fields(item, record)
    return record


def validate_trade(item: dict) -> dict:
    chamber = _required(item, "chamber")
    if chamber not in CHAMBERS:
        raise ValueError(f"chamber {chamber!r} is not house or senate")
    return {
        "id": _required(item, "id"),
        "member": _required(item, "member"),
        "chamber": chamber,
        "party": _optional_text(item.get("party")),
        "state": _optional_text(item.get("state")),
        "transactionType": _required(item, "transactionType"),
        "asset": _required(item, "asset"),
        "ticker": _optional_text(item.get("ticker")),
        "amountRange": _required(item, "amountRange"),
        "transactionDate": _optional_date(item.get("transactionDate")),
        "filingDate": _date(item.get("filingDate"), "filingDate"),
        "owner": _optional_text(item.get("owner")),
        "url": _url(item.get("url")),
    }


def validate_status(item: dict) -> dict:
    records = item.get("records")
    if isinstance(records, bool) or not isinstance(records, int) or records < 0:
        raise ValueError("records must be a non-negative integer")
    errors = item.get("errors")
    if not isinstance(errors, list) or not all(isinstance(entry, str) for entry in errors):
        raise ValueError("errors must be an array of strings")
    last_run = item.get("lastRun")
    if last_run is not None and not isinstance(last_run, str):
        raise ValueError("lastRun must be a string or null")
    return {
        "id": _required(item, "id"),
        "name": _required(item, "name"),
        "lastRun": last_run,
        "records": records,
        "errors": errors,
    }


def _required(item: dict, field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text field must be a string or null")
    stripped = value.strip()
    return stripped or None


def _date(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError(f"{field} must be an ISO date")
    day = value[:10]
    if not _iso_day(day):
        raise ValueError(f"{field} must be an ISO date")
    return day


def _optional_date(value: object, field: str = "transactionDate") -> str | None:
    if value is None or value == "":
        return None
    return _date(value, field)


def _tags(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be an array of strings")
    tags: list[str] = []
    seen: set[str] = set()
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError("tags must be an array of strings")
        tag = entry.strip().lower()
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _jurisdiction(value: object, *, default_federal: bool) -> dict:
    if value is None or value == "":
        if default_federal:
            return federal_jurisdiction()
        raise ValueError("jurisdiction is required")
    if not isinstance(value, dict):
        raise ValueError("jurisdiction must be an object")
    return normalize_jurisdiction(value)


def _agencies(value: object) -> list[str] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, list):
        raise ValueError("agencies must be an array of strings")
    names: list[str] = []
    for entry in value:
        if isinstance(entry, dict):
            name = entry.get("name") or entry.get("raw_name")
        else:
            name = entry
        if not isinstance(name, str) or not name.strip():
            raise ValueError("agencies must be an array of strings")
        names.append(name.strip())
    return names or None


def _copy_register_fields(item: dict, record: dict) -> None:
    if "commentsCloseOn" in item:
        record["commentsCloseOn"] = _optional_date(item.get("commentsCloseOn"), "commentsCloseOn")
    if "effectiveOn" in item:
        record["effectiveOn"] = _optional_date(item.get("effectiveOn"), "effectiveOn")
    if "agencies" in item:
        record["agencies"] = _agencies(item.get("agencies"))


def _iso_day(value: str) -> bool:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        return False
    year, month, day = value.split("-")
    return year.isdigit() and month.isdigit() and day.isdigit()


def _url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("url is required")
    cleaned = strip_api_key(value.strip())
    parts = urlsplit(cleaned)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("url must be an absolute http or https link")
    if "api_key=" in cleaned.lower():
        raise ValueError("url still contains an API key")
    return cleaned
