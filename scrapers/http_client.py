"""HTTP client with a per-host pause, retries, and redacted errors."""

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from scrapers.config import (
    BLOCKED_HOSTS,
    DEFAULT_INTERVAL_SECONDS,
    HOST_INTERVAL_SECONDS,
    MAX_ATTEMPTS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)
from scrapers.redact import redact

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class HttpError(Exception):
    """A request failed in a way the caller can show on the status page."""


class PoliteClient:
    """GET helper for official government hosts.

    One source failing is the caller's problem. This client only retries
    timeouts, 429, and 5xx, and it never puts secrets into exception text.
    """

    def __init__(
        self,
        *,
        secrets: list[str] | None = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
        default_interval: float = DEFAULT_INTERVAL_SECONDS,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        self.secrets = [secret for secret in (secrets or []) if secret]
        self.max_attempts = max_attempts
        self.default_interval = default_interval
        self.sleep = sleep
        self.clock = clock
        self.random_fn = random_fn
        self._host_next: dict[str, float] = {}
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
            },
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(
        self,
        url: str,
        *,
        params: list[tuple[str, str]] | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        self._reject_blocked(url)
        last_error = "request failed"
        for attempt in range(1, self.max_attempts + 1):
            self._pause(url)
            try:
                response = self._client.get(url, params=params, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = redact(f"{type(exc).__name__}", self.secrets)
                if attempt == self.max_attempts:
                    break
                self._backoff(attempt, None)
                continue
            if response.status_code in RETRYABLE_STATUS and attempt < self.max_attempts:
                last_error = f"HTTP {response.status_code}"
                self._backoff(attempt, response)
                continue
            if response.status_code >= 400:
                raise HttpError(self._status_error(url, response))
            return response
        raise HttpError(
            f"{self._host(url)} failed after {self.max_attempts} attempts: {last_error}"
        )

    def get_json(
        self,
        url: str,
        *,
        params: list[tuple[str, str]] | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        response = self.get(url, params=params, headers=headers)
        try:
            payload = response.json()
        except ValueError as exc:
            raise HttpError(f"{self._host(url)} returned a response that was not JSON") from exc
        if not isinstance(payload, dict):
            raise HttpError(f"{self._host(url)} returned JSON that was not an object")
        return payload

    def get_text(
        self,
        url: str,
        *,
        params: list[tuple[str, str]] | dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        return self.get(url, params=params, headers=headers).text

    def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, httpx.Headers]:
        response = self.get(url, headers=headers)
        return response.content, response.headers

    def _reject_blocked(self, url: str) -> None:
        host = self._host(url)
        if host in BLOCKED_HOSTS:
            raise HttpError(
                "Refusing to request efdsearch.senate.gov. "
                "Senate eFD search is link-only until legal review is recorded."
            )

    def _pause(self, url: str) -> None:
        host = self._host(url)
        interval = HOST_INTERVAL_SECONDS.get(host, self.default_interval)
        now = self.clock()
        earliest = self._host_next.get(host, 0.0)
        if earliest > now:
            self.sleep(earliest - now)
            now = self.clock()
        self._host_next[host] = now + interval

    def _backoff(self, attempt: int, response: httpx.Response | None) -> None:
        delay = _retry_after_seconds(response)
        if delay is None:
            delay = min(30.0, float(2 ** (attempt - 1)))
        delay += self.random_fn() * 0.25
        self.sleep(delay)

    def _status_error(self, url: str, response: httpx.Response) -> str:
        text = f"{self._host(url)} returned HTTP {response.status_code}"
        detail = _error_message(response)
        if detail:
            text = f"{text}: {detail}"
        return redact(text, self.secrets)

    @staticmethod
    def _host(url: str) -> str:
        return urlsplit(url).netloc.lower()


def _error_message(response: httpx.Response) -> str | None:
    """Short message from a JSON error body, such as the Federal Register 400s."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    message = payload.get("message")
    if not isinstance(message, str):
        return None
    message = message.strip()
    if not message:
        return None
    return message[:300]


def _retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OSError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())
