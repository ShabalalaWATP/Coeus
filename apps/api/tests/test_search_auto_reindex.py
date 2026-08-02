import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest

from coeus.core.errors import AppError
from coeus.services.search_auto_reindex import SearchAutoReindexService


class _Configuration:
    def __init__(self, status: str, reason: str | None = None) -> None:
        self.status = status
        self.reason = reason

    def state(self):
        return SimpleNamespace(index_status=self.status, degraded_reason=self.reason)


class _Indexing:
    def __init__(self, configuration: _Configuration) -> None:
        self.configuration = configuration
        self.started: list[UUID] = []
        self.ran: list[object] = []

    def start(self, actor: UUID):
        self.started.append(actor)
        self.configuration.status = "indexing"
        return SimpleNamespace(profile_id=UUID(int=2))

    def run(self, profile: object) -> None:
        self.ran.append(profile)
        self.configuration.status = "ready"
        self.configuration.reason = None


class _FailingIndexing(_Indexing):
    def __init__(self, configuration: _Configuration, error: Exception) -> None:
        super().__init__(configuration)
        self.error = error

    def start(self, actor: UUID):
        self.started.append(actor)
        raise self.error


@pytest.mark.asyncio
async def test_auto_reindex_builds_stale_corpus_once() -> None:
    configuration = _Configuration("stale", "corpus_changed")
    indexing = _Indexing(configuration)
    service = SearchAutoReindexService(configuration, indexing, enabled=True, debounce_seconds=0.01)

    await service._rebuild_if_required()
    await service._rebuild_if_required()

    assert len(indexing.started) == 1
    assert len(indexing.ran) == 1


@pytest.mark.asyncio
async def test_auto_reindex_requeues_an_active_build() -> None:
    configuration = _Configuration("indexing")
    service = SearchAutoReindexService(
        configuration, _Indexing(configuration), enabled=True, debounce_seconds=0.01
    )

    await service._rebuild_if_required()

    assert service._take_queued() is True


def test_disabled_auto_reindex_discards_notifications() -> None:
    configuration = _Configuration("stale", "corpus_changed")
    service = SearchAutoReindexService(
        configuration, _Indexing(configuration), enabled=False, debounce_seconds=0.01
    )

    service.enqueue()

    assert service._take_queued() is False


@pytest.mark.asyncio
async def test_disabled_auto_reindex_worker_returns_immediately() -> None:
    configuration = _Configuration("stale", "corpus_changed")
    service = SearchAutoReindexService(
        configuration, _Indexing(configuration), enabled=False, debounce_seconds=0.01
    )

    await service.run(asyncio.Event())

    assert service._take_queued() is False


@pytest.mark.asyncio
async def test_worker_builds_then_waits_for_shutdown() -> None:
    configuration = _Configuration("stale", "corpus_changed")
    indexing = _Indexing(configuration)
    service = SearchAutoReindexService(
        configuration, indexing, enabled=True, debounce_seconds=0.001
    )
    stop = asyncio.Event()

    task = asyncio.create_task(service.run(stop))
    for _ in range(100):
        if indexing.ran:
            break
        await asyncio.sleep(0.001)
    stop.set()
    await asyncio.wait_for(task, timeout=1)

    assert len(indexing.ran) == 1


@pytest.mark.asyncio
async def test_worker_can_stop_during_debounce() -> None:
    configuration = _Configuration("stale", "corpus_changed")
    indexing = _Indexing(configuration)
    service = SearchAutoReindexService(configuration, indexing, enabled=True, debounce_seconds=0.1)
    stop = asyncio.Event()

    task = asyncio.create_task(service.run(stop))
    await asyncio.sleep(0.001)
    stop.set()
    await asyncio.wait_for(task, timeout=1)

    assert indexing.ran == []


@pytest.mark.asyncio
async def test_ready_index_does_not_start_another_generation() -> None:
    configuration = _Configuration("ready")
    indexing = _Indexing(configuration)
    service = SearchAutoReindexService(configuration, indexing, enabled=True, debounce_seconds=0.01)

    await service._rebuild_if_required()

    assert indexing.started == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason", "expected_queued"),
    [
        (AppError(409, "search_reindex_active", "active"), None, True),
        (AppError(503, "search_reindex_unavailable", "unavailable"), None, False),
        (RuntimeError("failed"), None, False),
        (RuntimeError("failed"), "corpus_changed", True),
    ],
)
async def test_rebuild_failures_are_bounded_and_requeued_when_needed(
    error: Exception, reason: str | None, expected_queued: bool
) -> None:
    configuration = _Configuration("error", reason)
    service = SearchAutoReindexService(
        configuration,
        _FailingIndexing(configuration, error),
        enabled=True,
        debounce_seconds=0.01,
    )

    await service._rebuild_if_required()

    assert service._take_queued() is expected_queued
