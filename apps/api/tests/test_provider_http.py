"""Transport-level bounds for synchronous provider JSON calls."""

import time

import httpx
import pytest

import coeus.integrations.bounded_http as bounded_http
from coeus.integrations.provider_http import get_json, post_json


class FakeResponse:
    def __init__(self, *, raw: bytes = b"{}", headers: dict[str, str] | None = None) -> None:
        self._raw = raw
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield self._raw


def _fake_client(response: FakeResponse, captured: dict[str, object]) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            json: object | None = None,
            headers: dict[str, str],
        ) -> FakeResponse:
            captured["headers"] = headers
            return response

    return FakeClient


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({"content-encoding": "gzip"}, "Encoded provider responses"),
        ({"content-encoding": "br"}, "Encoded provider responses"),
        ({"content-length": "11"}, "exceeded the allowed byte limit"),
        ({"content-length": "invalid"}, "response length was invalid"),
    ],
)
def test_response_headers_are_rejected_before_decoded_iteration(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
    message: str,
) -> None:
    class RejectedResponse(FakeResponse):
        def iter_bytes(self):  # type: ignore[no-untyped-def]
            raise AssertionError("Rejected response body must not be decoded.")

    captured: dict[str, object] = {}
    response = RejectedResponse(headers=headers)
    monkeypatch.setattr(
        "coeus.integrations.bounded_http.httpx.Client", _fake_client(response, captured)
    )

    with pytest.raises(ValueError, match=message):
        post_json(
            "https://provider.example.test",
            headers={},
            body={},
            timeout=1,
            max_response_bytes=10,
        )


def test_identity_response_with_bounded_declared_length_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    response = FakeResponse(headers={"content-encoding": "identity", "content-length": "2"})
    monkeypatch.setattr(
        "coeus.integrations.bounded_http.httpx.Client", _fake_client(response, captured)
    )

    assert (
        post_json(
            "https://provider.example.test",
            headers={"accept-encoding": "gzip"},
            body={},
            timeout=1,
            max_response_bytes=2,
        )
        == {}
    )
    assert captured["headers"] == {"Accept-Encoding": "identity"}


def test_non_positive_transport_limit_is_rejected_before_network() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        post_json(
            "https://provider.example.test",
            headers={},
            body={},
            timeout=1,
            max_response_bytes=0,
        )


def test_non_positive_total_timeout_is_rejected_before_network() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        get_json(
            "https://provider.example.test",
            headers={},
            timeout=0,
            max_response_bytes=10,
        )


def test_client_creation_cannot_consume_the_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class SlowConstructionClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 1

        def close(self) -> None:
            nonlocal closed
            closed = True

    clock = iter((10.0, 11.1))
    monkeypatch.setattr("coeus.integrations.bounded_http.httpx.Client", SlowConstructionClient)
    monkeypatch.setattr("coeus.integrations.bounded_http.time.monotonic", lambda: next(clock))

    with pytest.raises(httpx.ReadTimeout, match="total deadline"):
        get_json(
            "https://provider.example.test",
            headers={},
            timeout=1,
            max_response_bytes=10,
        )

    assert closed is True


def test_incremental_response_limit_stops_before_next_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    response = FakeResponse(raw=b"123")
    monkeypatch.setattr(
        "coeus.integrations.bounded_http.httpx.Client", _fake_client(response, captured)
    )

    with pytest.raises(ValueError, match="exceeded the allowed byte limit"):
        get_json(
            "https://provider.example.test",
            headers={},
            timeout=1,
            max_response_bytes=2,
        )


def test_get_json_uses_the_same_response_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    response = FakeResponse(raw=b'{"data":[]}', headers={"content-length": "11"})
    monkeypatch.setattr(
        "coeus.integrations.bounded_http.httpx.Client", _fake_client(response, captured)
    )

    assert get_json(
        "https://provider.example.test/v1/models",
        headers={"Authorization": "Bearer test"},
        timeout=2,
        max_response_bytes=11,
    ) == {"data": []}
    assert captured["headers"] == {
        "Authorization": "Bearer test",
        "Accept-Encoding": "identity",
    }


def test_total_deadline_stops_a_progressing_response(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = False

    class SlowResponse(FakeResponse):
        def iter_bytes(self):  # type: ignore[no-untyped-def]
            while not closed:
                time.sleep(0.02)
                yield b" "

    class SlowClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 0.05

        def __enter__(self) -> "SlowClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def close(self) -> None:
            nonlocal closed
            closed = True

        def stream(
            self,
            method: str,
            url: str,
            *,
            headers: dict[str, str],
        ) -> SlowResponse:
            return SlowResponse()

    monkeypatch.setattr("coeus.integrations.bounded_http.httpx.Client", SlowClient)
    started = time.monotonic()

    with pytest.raises(httpx.ReadTimeout, match="total deadline"):
        get_json(
            "https://provider.example.test/v1/models",
            headers={},
            timeout=0.05,
            max_response_bytes=1_000,
        )

    assert time.monotonic() - started < 0.2
    assert closed is True


def test_non_deadline_network_errors_remain_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        def __enter__(self) -> "FailingClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def stream(self, method: str, url: str, *, headers: dict[str, str]) -> FakeResponse:
            raise httpx.ConnectError("unavailable", request=httpx.Request(method, url))

    monkeypatch.setattr("coeus.integrations.bounded_http.httpx.Client", FailingClient)

    with pytest.raises(httpx.ConnectError, match="unavailable"):
        get_json(
            "https://provider.example.test",
            headers={},
            timeout=1,
            max_response_bytes=10,
        )


def test_socket_interrupt_is_idempotent() -> None:
    shutdowns: list[int] = []

    class FakeSocket:
        def shutdown(self, operation: int) -> None:
            shutdowns.append(operation)

    class FakeNetworkStream:
        def get_extra_info(self, key: str) -> object:
            return FakeSocket() if key == "socket" else None

    class SocketResponse:
        def __init__(self) -> None:
            self.extensions = {"network_stream": FakeNetworkStream()}

    deadline = bounded_http.TotalDeadline(time.monotonic() - 1, 1, lambda: None)
    deadline.bind_response(SocketResponse(), object())  # type: ignore[arg-type]
    with pytest.raises(httpx.ReadTimeout, match="total deadline"):
        deadline.check()

    assert shutdowns == [bounded_http.socket.SHUT_RDWR]
