"""Validate records and merge them into a feed. Invalid ones are quarantined."""

from scrapers.context import RunContext
from scrapers.store import quarantine, touch_feed, upsert_items, upsert_status
from scrapers.validate import validate_federal, validate_status, validate_trade


def publish_federal(
    ctx: RunContext,
    source_id: str,
    items: list[dict],
    *,
    path=None,
) -> tuple[int, list[str]]:
    return _publish(
        ctx,
        source_id,
        items,
        validate_federal,
        path or ctx.federal_path,
        "date",
    )


def publish_trades(
    ctx: RunContext,
    source_id: str,
    items: list[dict],
    *,
    replace_prefix: str | None = None,
    drop_id: str | None = None,
) -> tuple[int, list[str]]:
    return _publish(
        ctx,
        source_id,
        items,
        validate_trade,
        ctx.trades_path,
        "filingDate",
        replace_prefix=replace_prefix,
        drop_id=drop_id,
    )


def publish_status(ctx: RunContext, item: dict) -> None:
    upsert_status(ctx.status_path, validate_status(item), updated=ctx.now)


def mark_checked(ctx: RunContext, path, date_key: str) -> None:
    touch_feed(path, updated=ctx.now, date_key=date_key)


def _publish(
    ctx: RunContext,
    source_id: str,
    items: list[dict],
    validator,
    path,
    date_key: str,
    *,
    replace_prefix: str | None = None,
    drop_id: str | None = None,
) -> tuple[int, list[str]]:
    good: list[dict] = []
    errors: list[str] = []
    for item in items:
        try:
            good.append(validator(item))
        except ValueError as exc:
            record_id = str(item.get("id") or "record")
            quarantine(ctx.state_dir, source_id, record_id, item, str(exc))
    if good:
        upsert_items(
            path,
            good,
            updated=ctx.now,
            date_key=date_key,
            replace_prefix=replace_prefix,
            drop_id=drop_id,
        )
    if len(good) != len(items):
        failed = len(items) - len(good)
        errors.append(
            f"{failed} {source_id} records failed validation and were quarantined."
        )
    return len(good), errors
