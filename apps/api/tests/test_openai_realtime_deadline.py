"""Total-deadline regressions for OpenAI Realtime transport."""

import threading
from collections.abc import Callable, Iterator

import pytest

import coeus.integrations.bounded_http as bounded_http
from coeus.core.errors import AppError
from coeus.integrations.openai_realtime import create_realtime_call


def test_realtime_slow_drip_is_interrupted_when_chunks_keep_arriving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_interrupted = threading.Event()

    class ControlledTimer:
        daemon = False
        _function: Callable[[], None] | None = None

        def __init__(self, interval: float, function: Callable[[], None]) -> None:
            assert interval <= 20
            ControlledTimer._function = function

        def start(self) -> None:
            return None

        def cancel(self) -> None:
            return None

        def join(self) -> None:
            return None

        @classmethod
        def fire(cls) -> None:
            assert cls._function is not None
            cls._function()

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
            yield b"v=0\r\n"
            ControlledTimer.fire()
            if not response_interrupted.is_set():
                raise AssertionError("Expired Realtime request was not interrupted.")
            yield b"m=audio answer\r\n"

    class DelayedStream:
        def __enter__(self) -> BlockingResponse:
            return BlockingResponse()

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

    class DelayedClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 20

        def __enter__(self) -> "DelayedClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def close(self) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            headers: dict[str, str],
            files: dict[str, object],
        ) -> DelayedStream:
            return DelayedStream()

    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", DelayedClient)
    monkeypatch.setattr("coeus.integrations.bounded_http.threading.Timer", ControlledTimer)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            instructions="Guarded synthetic RFI intake.",
            model="gpt-realtime-2.1",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.code == "voice_provider_unavailable"
    assert response_interrupted.is_set()
