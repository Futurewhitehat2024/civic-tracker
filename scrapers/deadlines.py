"""Build comment-deadline and effective-date files from Federal Register records."""

from __future__ import annotations

from pathlib import Path

from scrapers.store import load_feed, save_json, sort_items

COMMENT_KIND = "comment_due"
EFFECTIVE_KIND = "effective"


def deadline_items(*feeds: dict) -> list[dict]:
    items: list[dict] = []
    for feed in feeds:
        for record in feed.get("items") or []:
            if not isinstance(record, dict):
                continue
            items.extend(_from_record(record))
    return sort_items(items, "date")


def write_deadlines(path: Path, items: list[dict], *, updated: str) -> dict:
    payload = {"updated": updated, "items": items}
    save_json(path, payload)
    return payload


def write_calendar(path: Path, items: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Civic Tracker//Deadlines//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Civic Tracker deadlines",
    ]
    for item in items:
        lines.extend(_vevent(item))
    lines.append("END:VCALENDAR")
    text = "\r\n".join(lines) + "\r\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def load_deadline_feeds(federal_path: Path, notices_path: Path) -> list[dict]:
    return deadline_items(load_feed(federal_path), load_feed(notices_path))


def _from_record(record: dict) -> list[dict]:
    items: list[dict] = []
    comment = record.get("commentsCloseOn")
    effective = record.get("effectiveOn")
    if isinstance(comment, str) and comment:
        items.append(_item(record, COMMENT_KIND, comment, "Comment due"))
    if isinstance(effective, str) and effective:
        items.append(_item(record, EFFECTIVE_KIND, effective, "Effective date"))
    return items


def _item(record: dict, kind: str, day: str, label: str) -> dict:
    title = str(record.get("title") or "Federal Register document")
    return {
        "id": f"{record['id']}-{kind.replace('_', '-')}",
        "recordId": record["id"],
        "kind": kind,
        "date": day[:10],
        "title": f"{label}: {title}",
        "url": record.get("url"),
        "source": record.get("source") or "Federal Register",
        "documentType": record.get("documentType"),
        "jurisdiction": record.get("jurisdiction"),
        "tags": list(record.get("tags") or []),
    }


def _vevent(item: dict) -> list[str]:
    day = str(item["date"]).replace("-", "")
    uid = f"{item['id']}@civic-tracker"
    # DTSTAMP is derived from the deadline date so the file is deterministic.
    stamp = f"{day}T000000Z"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day}",
        f"SUMMARY:{_escape(item['title'])}",
    ]
    url = item.get("url")
    if isinstance(url, str) and url:
        lines.append(f"URL:{url}")
    lines.append(f"CATEGORIES:{item['kind']}")
    lines.append("END:VEVENT")
    return lines


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )
