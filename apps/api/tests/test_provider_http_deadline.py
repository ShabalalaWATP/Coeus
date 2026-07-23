"""Race regressions for the provider transport's total deadline."""

import threading
from collections.abc import Callable, Iterator

import httpx
import pytest

import coeus.integrations.bounded_http as bounded_http
from coeus.integrations.provider_http import get_json


def test_expired_deadline_rebind_interrupts_response_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_closed = threading.Event()
    response_interrupted = threading.Event()

    class ImmediateTimer:
        daemon = False

        def __init__(self, interval: float, function: Callable[[], None]) -> None:
            assert interval <= 1
            self._function = function

        def start(self) -> None:
            self._function()

        def cancel(self) -> None:
            return None

        def join(self) -> None:
            return None

    class FakeSocket:
        def shutdown(self, operation: int) -> None:
            assert operation == bounded_http.socket.SHUT_RDWR
            response_interrupted.set()

    class FakeNetworkStream:
        def get_extra_info(self, key: str) -> object:
            return FakeSocket() if key == "socket" else None

    class BlockingResponse:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.extensions = {"network_stream": FakeNetworkStream()}

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self) -> Iterator[bytes]:
            if not response_interrupted.is_set():
                raise AssertionError("Expired watchdog did not interrupt the returned response.")
            yield b"{}"

    class DelayedStream:
        def __enter__(self) -> BlockingResponse:
            assert client_closed.is_set()
            return BlockingResponse()

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

    class DelayedClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 1

        def __enter__(self) -> "DelayedClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def close(self) -> None:
            client_closed.set()

        def stream(self, method: str, url: str, *, headers: dict[str, str]) -> DelayedStream:
            return DelayedStream()

    monkeypatch.setattr("coeus.integrations.bounded_http.httpx.Client", DelayedClient)
    monkeypatch.setattr("coeus.integrations.bounded_http.threading.Timer", ImmediateTimer)

    with pytest.raises(httpx.ReadTimeout, match="total deadline"):
        get_json(
            "https://provider.example.test",
            headers={},
            timeout=1,
            max_response_bytes=10,
        )

    assert client_closed.is_set()
    assert response_interrupted.is_set()
