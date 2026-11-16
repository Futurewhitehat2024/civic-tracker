"""JSON feeds, per-source cursors, and quarantine writes.

Writes are atomic. A crashed run leaves the previous file in place, and the
cursor advances only when the caller saves it after a validated write.
"""

import json
import os
import re
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def empty_feed() -> dict[str, Any]:
    return {"updated": None, "items": []}


def load_feed(path: Path) -> dict[str, Any]:
    payload = load_json(path, empty_feed())
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(f"{path.name} must be an object with an items array")
    return payload


def sort_items(items: list[dict[str, Any]], date_key: str) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: str(item.get("id") or ""))
    ordered.sort(key=lambda item: str(item.get(date_key) or ""), reverse=True)
    return ordered


def upsert_items(
    path: Path,
    new_items: list[dict[str, Any]],
    *,
    updated: str,
    date_key: str,
    replace_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Merge items by id. Re-running with the same ids replaces in place."""
    feed = load_feed(path)
    kept: list[dict[str, Any]] = []
    for item in feed["items"]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if replace_prefix and str(item["id"]).startswith(replace_prefix):
            continue
        kept.append(item)
    by_id = {str(item["id"]): item for item in kept}
    for item in new_items:
        by_id[str(item["id"])] = item
    items = sort_items(list(by_id.values()), date_key)
    save_json(path, {"updated": updated, "items": items})
    return items


def touch_feed(path: Path, *, updated: str, date_key: str) -> None:
    """Mark a feed checked when a source succeeded and had nothing new to add."""
    feed = load_feed(path)
    items = [
        item
        for item in feed["items"]
        if isinstance(item, dict) and item.get("id")
    ]
    save_json(path, {"updated": updated, "items": sort_items(items, date_key)})


def load_state(path: Path) -> dict[str, Any]:
    payload = load_json(path, {})
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return payload


def save_state(path: Path, payload: dict[str, Any]) -> None:
    save_json(path, payload)


def upsert_status(path: Path, item: dict[str, Any], *, updated: str) -> None:
    feed = load_feed(path)
    by_id = {
        str(existing["id"]): existing
        for existing in feed["items"]
        if isinstance(existing, dict) and existing.get("id")
    }
    by_id[str(item["id"])] = item
    items = [by_id[key] for key in sorted(by_id)]
    save_json(path, {"updated": updated, "items": items})


def quarantine(root: Path, source: str, record_id: str, record: Any, reason: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", record_id).strip("._")[:80] or "record"
    path = root / "quarantine" / source / f"{safe}.json"
    save_json(path, {"reason": reason, "record": record})
    return path
