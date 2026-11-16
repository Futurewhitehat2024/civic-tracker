"""Parse text extracted from an electronic House periodic transaction report.

Scanned PDFs have no text layer. Callers treat that as a link-only filing.
This module does not OCR.
"""

import re
from datetime import datetime

_ANCHOR = re.compile(
    r"(?P<ttype>S\s*\(partial\)|S\s*\(full\)|P|S|E)(?![A-Za-z])\s*"
    r"(?P<tdate>\d{2}/\d{2}/\d{4})\s*"
    r"(?P<ndate>\d{2}/\d{2}/\d{4})\s*"
    r"(?P<amount>\$[\d,]+\s*[\u2013-]\s*\$[\d,]+)",
    re.IGNORECASE,
)
_ASSET_CLOSE = re.compile(r"\[[A-Z]{2}\]")
_JUNK = re.compile(
    r"(?:Amount Cap\.?|Gains >|\$200\?|ID Owner Asset|Transaction Type|Notification Date)",
    re.IGNORECASE,
)
_LEADING_OWNER = re.compile(r"^(SP|JT|DC)\b\s*", re.IGNORECASE)
_DROP_LINE = re.compile(
    r"^(?:"
    r"p t r|f i|t|i v d|i p o|c s|"
    r"clerk of the house.*|"
    r"name:.*|status:.*|state/district.*|"
    r"id owner.*|transaction|type|date notification|date|amount|cap\.|gains.*|"
    r"f s:.*|s o:.*|l:.*|d:.*|"
    r"filing id.*|\* for the complete.*|i certify.*|digitally signed.*|"
    r"yes.*no.*|\[[a-z]{2}\]"
    r")$",
    re.IGNORECASE,
)
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.]{0,7})\)")
_ASSET_CODE = re.compile(r"\s*\[[A-Z]{2}\]\s*")
_OWNERS = {
    "SP": "spouse",
    "JT": "joint",
    "DC": "dependent",
}


def parse_ptr_text(text: str) -> list[dict]:
    """Return transactions in filing order. An empty list means nothing parsed."""
    cleaned = text.replace("\x00", "")
    for marker in ("I CERTIFY", "* For the complete list"):
        index = cleaned.find(marker)
        if index != -1:
            cleaned = cleaned[:index]
    matches = list(_ANCHOR.finditer(cleaned))
    raw_blobs = []
    for index, match in enumerate(matches):
        begin = 0 if index == 0 else matches[index - 1].end()
        raw_blobs.append(cleaned[begin : match.start()])
    # A wrapped asset name can continue after the amount, before the next row.
    tails = [_split_previous_tail(blob) for blob in raw_blobs]
    found: list[dict] = []
    for index, match in enumerate(matches):
        extra = tails[index + 1][0] if index + 1 < len(tails) else ""
        asset, ticker, owner = _asset(tails[index][1] + "\n" + extra)
        if not asset:
            continue
        found.append(
            {
                "transactionType": _transaction_type(match.group("ttype")),
                "asset": asset,
                "ticker": ticker,
                "amountRange": _amount(match.group("amount")),
                "transactionDate": _us_date(match.group("tdate")),
                "owner": owner,
            }
        )
    return found


def _split_previous_tail(blob: str) -> tuple[str, str]:
    """Return (text that finishes the previous row, text for this row)."""
    codes = list(_ASSET_CLOSE.finditer(blob))
    if len(codes) < 2:
        return "", blob
    return blob[: codes[0].end()], blob[codes[0].end() :]


def _asset(blob: str) -> tuple[str, str | None, str | None]:
    owner = None
    lines: list[str] = []
    for raw_line in blob.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or _DROP_LINE.match(line):
            continue
        if line.upper() in _OWNERS and owner is None and not lines:
            owner = _OWNERS[line.upper()]
            continue
        lines.append(line)
    text = _ASSET_CODE.sub(" ", " ".join(lines))
    text = _JUNK.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    owner_match = _LEADING_OWNER.match(text)
    if owner_match and owner is None:
        owner = _OWNERS[owner_match.group(1).upper()]
        text = text[owner_match.end() :].strip()
    ticker_match = None
    for ticker_match in _TICKER.finditer(text):
        pass
    ticker = ticker_match.group(1) if ticker_match else None
    if ticker_match:
        text = (text[: ticker_match.start()] + text[ticker_match.end() :]).strip(" -")
        text = re.sub(r"\s+", " ", text).strip()
    return text, ticker, owner


def _amount(value: str) -> str:
    return re.sub(r"\s+", " ", value).replace("\u2013", "-")


def _transaction_type(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip().lower()
    if text in {"p", "purchase"}:
        return "purchase"
    if text in {"s", "sale"}:
        return "sale"
    if text in {"s (partial)", "sale (partial)"}:
        return "sale (partial)"
    if text in {"s (full)", "sale (full)"}:
        return "sale"
    if text in {"e", "exchange"}:
        return "exchange"
    return re.sub(r"\s+", " ", raw).strip()


def _us_date(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
