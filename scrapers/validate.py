"""Check records against docs/data/SCHEMA.md before they are published."""

from urllib.parse import urlsplit

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
    return {
        "id": _required(item, "id"),
        "kind": kind,
        "title": _required(item, "title"),
        "date": _date(item.get("date"), "date"),
        "url": _url(item.get("url")),
        "source": _required(item, "source"),
        "summary": _optional_text(item.get("summary")),
        "identifier": _optional_text(item.get("identifier")),
        "chamber": chamber if chamber in CHAMBERS else None,
    }


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


def _optional_date(value: object) -> str | None:
    if value is None or value == "":
        return None
    return _date(value, "transactionDate")


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
