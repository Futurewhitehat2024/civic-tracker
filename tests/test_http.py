import httpx

from scrapers.http_client import HttpError, PoliteClient


def test_retries_429_then_honors_retry_after() -> None:
    calls = {"n": 0}
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    client = PoliteClient(
        transport=httpx.MockTransport(handler),
        default_interval=0,
        sleep=delays.append,
        random_fn=lambda: 0.0,
    )
    try:
        assert client.get_json("https://example.com/items") == {"ok": True}
    finally:
        client.close()
    assert calls["n"] == 2
    assert delays == [0.0]


def test_retries_timeout_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timed out")
        return httpx.Response(200, text="<ok/>")

    client = PoliteClient(
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
        random_fn=lambda: 0.0,
    )
    try:
        assert client.get_text("https://clerk.house.gov/evs/2026/roll001.xml") == "<ok/>"
    finally:
        client.close()
    assert calls["n"] == 2


def test_http_error_includes_federal_register_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "status": 400,
                "message": (
                    "Pagination limit exceeded.  "
                    "No more than 10000 items can be requested at a time"
                ),
            },
        )

    client = PoliteClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None)
    try:
        try:
            client.get_json("https://www.federalregister.gov/api/v1/documents.json")
        except HttpError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected HttpError")
    finally:
        client.close()
    assert message == (
        "www.federalregister.gov returned HTTP 400: "
        "Pagination limit exceeded.  No more than 10000 items can be requested at a time"
    )


def test_does_not_retry_404() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    client = PoliteClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None)
    try:
        try:
            client.get("https://www.senate.gov/missing.xml")
        except HttpError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected HttpError")
    finally:
        client.close()
    assert calls["n"] == 1
    assert message == "www.senate.gov returned HTTP 404"


def test_error_text_does_not_contain_the_key() -> None:
    secret = "super-secret-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == secret
        return httpx.Response(403, text=f"bad key {secret}")

    client = PoliteClient(
        secrets=[secret],
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )
    try:
        try:
            client.get("https://api.congress.gov/v3/bill", params={"api_key": secret, "limit": "1"})
        except HttpError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected HttpError")
    finally:
        client.close()
    assert secret not in message
    assert "api.congress.gov returned HTTP 403" in message


def test_refuses_senate_efd_search_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("blocked host was requested")

    client = PoliteClient(transport=httpx.MockTransport(handler))
    try:
        try:
            client.get("https://efdsearch.senate.gov/search/")
        except HttpError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected HttpError")
    finally:
        client.close()
    assert "link-only" in message


def test_pauses_between_requests_to_the_same_host() -> None:
    clock = {"now": 0.0}
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += seconds

    client = PoliteClient(
        transport=httpx.MockTransport(handler),
        sleep=sleep,
        clock=lambda: clock["now"],
        random_fn=lambda: 0.0,
    )
    try:
        client.get_text("https://clerk.house.gov/a")
        client.get_text("https://clerk.house.gov/b")
    finally:
        client.close()
    assert slept == [1.0]
