"""Strip API keys from text that might be logged or saved."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_API_KEY_QUERY = re.compile(r"(?i)(api_key=)[^&\s\"']+")


def redact(text: str, secrets: list[str] | None = None) -> str:
    cleaned = text
    for secret in secrets or []:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return _API_KEY_QUERY.sub(r"\1[REDACTED]", cleaned)


def strip_api_key(url: str) -> str:
    """Return a URL safe to store. Drops the api_key query parameter."""
    parts = urlsplit(url)
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != "api_key"
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))
