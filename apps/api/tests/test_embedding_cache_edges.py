from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from coeus.services.embeddings import EmbeddingService, EmbeddingUnavailable


def test_cached_embedding_waiter_and_eviction_paths_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()

    class BlockingProvider:
        name = "blocking"

        def embed(self, text: str) -> tuple[float, ...]:
            if text == "first":
                started.set()
                assert release.wait(timeout=5)
            return (float(len(text)),)

    service = EmbeddingService(BlockingProvider())
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(service.embed_cached, "first", purpose="test")
        assert started.wait(timeout=5)
        waiter = pool.submit(service.embed_cached, "first", purpose="test")
        release.set()
        assert leader.result(timeout=5) == waiter.result(timeout=5) == (5.0,)

    monkeypatch.setattr("coeus.services.embeddings.EMBEDDING_CACHE_LIMIT", 1)
    assert service.embed_cached("second", purpose="test") == (6.0,)
    assert len(service._cache) == 1


def test_embedding_warning_is_emitted_once_for_repeated_failure() -> None:
    class FailingProvider:
        name = "failing"

        def embed(self, _text: str) -> tuple[float, ...]:
            raise EmbeddingUnavailable("synthetic failure")

    service = EmbeddingService(FailingProvider())

    assert service.embed("one", purpose="first") is None
    assert service.embed("two", purpose="second") is None
    assert service._warned == {"failing:synthetic failure"}
