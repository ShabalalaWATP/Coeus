import asyncio
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.main import _dispatch_outbox, _lifespan
from coeus.services.outbox_dispatcher import DispatchResult


@pytest.mark.anyio
async def test_runtime_dispatches_a_bounded_batch_and_stops_cleanly() -> None:
    stop = asyncio.Event()

    class Dispatcher:
        def __init__(self) -> None:
            self.calls: list[tuple[UUID, int]] = []

        def dispatch(self, worker_id: UUID, *, limit: int = 50) -> DispatchResult:
            self.calls.append((worker_id, limit))
            stop.set()
            return DispatchResult(0, 0, 0, 0)

    app = FastAPI()
    app.state.settings = Settings(
        environment="test",
        persistence_provider="memory",
        outbox_batch_size=7,
        outbox_poll_seconds=1,
    )
    dispatcher = Dispatcher()

    await _dispatch_outbox(app, dispatcher, stop)

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0][1] == 7


@pytest.mark.anyio
async def test_runtime_contains_dispatch_failures() -> None:
    stop = asyncio.Event()

    class Dispatcher:
        def dispatch(self, _worker_id: UUID, *, limit: int = 50) -> DispatchResult:
            assert limit == 5
            stop.set()
            raise RuntimeError("synthetic dispatcher failure")

    app = FastAPI()
    app.state.settings = Settings(
        environment="test",
        persistence_provider="memory",
        outbox_batch_size=5,
        outbox_poll_seconds=1,
    )

    await _dispatch_outbox(app, Dispatcher(), stop)


@pytest.mark.anyio
async def test_runtime_records_safe_structured_dispatch_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = asyncio.Event()
    logger = MagicMock()
    monkeypatch.setattr("coeus.main.logger", logger)

    class Dispatcher:
        def dispatch(self, _worker_id: UUID, *, limit: int = 50) -> DispatchResult:
            assert limit == 4
            stop.set()
            return DispatchResult(4, 2, 2, 1)

    app = FastAPI()
    app.state.settings = Settings(
        environment="test",
        persistence_provider="memory",
        outbox_batch_size=4,
        outbox_poll_seconds=1,
    )

    await _dispatch_outbox(app, Dispatcher(), stop)

    logger.info.assert_called_once_with(
        "outbox_dispatch_completed",
        extra={"claimed": 4, "delivered": 2, "failed": 2, "dead_lettered": 1},
    )
    assert "payload" not in repr(logger.info.call_args)


@pytest.mark.anyio
@pytest.mark.parametrize("with_dispatcher", [False, True])
async def test_lifespan_starts_optional_dispatcher_and_always_disposes(
    monkeypatch: pytest.MonkeyPatch,
    with_dispatcher: bool,
) -> None:
    disposed = False

    async def dispose() -> None:
        nonlocal disposed
        disposed = True

    class Dispatcher:
        def dispatch(self, _worker_id: UUID, *, limit: int = 50) -> DispatchResult:
            return DispatchResult(0, 0, 0, 0)

    monkeypatch.setattr("coeus.main.dispose_readiness_engines", dispose)
    app = FastAPI()
    app.state.settings = Settings(
        environment="test", persistence_provider="memory", outbox_poll_seconds=1
    )
    if with_dispatcher:
        app.state.outbox_dispatcher = Dispatcher()

    async with _lifespan(app):
        assert not disposed

    assert disposed
