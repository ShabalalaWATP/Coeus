import asyncio
from dataclasses import replace
from threading import Event, Timer
from time import monotonic
from typing import cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.store import StoreHybridCandidate
from coeus.domain.tickets import IntakeDetails
from coeus.main import create_app
from coeus.repositories.store_hybrid import MEMORY_VECTOR_WORK_LIMIT, memory_hybrid_candidates
from coeus.services.embeddings import EMBEDDING_DIMENSIONS, EmbeddingService
from coeus.services.rfi_ranking import RFI_RANKING_WORK_LIMIT, rank_hybrid_rfi_candidates
from store_api_helpers import login
from store_projection_helpers import seed_product

_VECTOR = (1.0, *(0.0 for _ in range(EMBEDDING_DIMENSIONS - 1)))


@pytest.mark.asyncio
async def test_delayed_store_embedding_does_not_stall_event_loop() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    embeddings = app.state.store_services.search._embeddings
    started = Event()
    release = Event()

    def delayed_embed(_text: str, *, purpose: str, principal_id: object | None = None) -> None:
        assert purpose == "store-browse-query"
        started.set()
        release.wait(timeout=2)
        return None

    embeddings.embed_cached = delayed_embed
    safety_release = Timer(2, release.set)
    safety_release.start()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        request = asyncio.create_task(client.get("/api/v1/store/products?query=regional"))
        wait_started_at = monotonic()
        started_in_time = await asyncio.to_thread(started.wait, 1)
        start_signal_elapsed = monotonic() - wait_started_at
        try:
            liveness = await asyncio.wait_for(client.get("/api/v1/health/live"), timeout=1)
        finally:
            release.set()
            safety_release.cancel()
        response = await request

    assert started_in_time
    assert start_signal_elapsed < 1
    assert liveness.status_code == 200
    assert response.status_code == 200


def test_memory_vector_provider_calls_are_capped_and_cached_across_corpus() -> None:
    class CountingEmbeddings:
        def __init__(self) -> None:
            self.calls = 0
            self.cache: dict[str, tuple[float, ...]] = {}

        def embed_cached(
            self, text: str, *, purpose: str, principal_id: object | None = None
        ) -> tuple[float, ...]:
            assert purpose == "memory-candidate"
            if text not in self.cache:
                self.calls += 1
                self.cache[text] = _VECTOR
            return self.cache[text]

    base = seed_product()
    products = tuple(
        replace(
            base,
            product_id=uuid4(),
            metadata=replace(base.metadata, title=f"Corpus product {index:03d}"),
        )
        for index in range(MEMORY_VECTOR_WORK_LIMIT + 1)
    )
    embeddings = CountingEmbeddings()

    memory_hybrid_candidates(
        products, "absent query", _VECTOR, cast(EmbeddingService, embeddings), leg_limit=10
    )
    assert embeddings.calls == MEMORY_VECTOR_WORK_LIMIT
    memory_hybrid_candidates(
        products, "absent query", _VECTOR, cast(EmbeddingService, embeddings), leg_limit=10
    )
    assert embeddings.calls == MEMORY_VECTOR_WORK_LIMIT


@pytest.mark.parametrize("extra", [0, 1])
def test_rfi_ranking_has_hard_candidate_work_budget(
    monkeypatch: pytest.MonkeyPatch, extra: int
) -> None:
    base = seed_product()
    candidates = tuple(
        StoreHybridCandidate(
            product=replace(
                base,
                product_id=uuid4(),
                metadata=replace(base.metadata, title=f"Candidate {index:03d}"),
            ),
            lexical_rank=index + 1,
            lexical_score=0.5,
            lexical_only=True,
        )
        for index in range(RFI_RANKING_WORK_LIMIT + extra)
    )
    calls = 0

    def counted_text(product: object) -> str:
        nonlocal calls
        calls += 1
        return "bounded deterministic candidate text"

    monkeypatch.setattr("coeus.services.rfi_ranking.product_semantic_text", counted_text)
    rank_hybrid_rfi_candidates(candidates, IntakeDetails(title="bounded candidate"))

    assert calls == RFI_RANKING_WORK_LIMIT
