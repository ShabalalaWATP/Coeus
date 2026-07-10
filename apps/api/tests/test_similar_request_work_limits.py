import asyncio
import time
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.similar_requests import SIMILARITY_CANDIDATE_LIMIT
from test_similar_requests_api import login, similar_ticket_pair, submitted_ticket


class RecordingEmbeddings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def embed(self, text: str, *, purpose: str) -> tuple[float, ...]:
        self.calls.append((text, purpose))
        return (1.0,) * 384


class SlowEmbeddings(RecordingEmbeddings):
    def embed(self, text: str, *, purpose: str) -> tuple[float, ...]:
        time.sleep(0.02)
        return super().embed(text, purpose=purpose)


@pytest.mark.asyncio
async def test_customer_similarity_filters_hidden_candidates_before_scoring() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    embeddings = RecordingEmbeddings()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        colleague = await login(client, "colleague@example.test")
        hidden_id = await _submitted(client, colleague, "Hidden vessel movements")
        user = await login(client, "user@example.test")
        source_id = await _submitted(client, user, "Visible vessel movements")
        app.state.similar_request_service._embeddings = embeddings
        notice = await client.get(f"/api/v1/similar-requests/tickets/{source_id}")
        joined = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{hidden_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert notice.status_code == 200
    assert notice.json() == {"matches": []}
    assert joined.status_code == 404
    assert embeddings.calls == []


@pytest.mark.asyncio
async def test_manager_similarity_caps_scoring_and_link_response_is_pairwise() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    embeddings = RecordingEmbeddings()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        repository = app.state.ticket_services.tickets._repository
        target = repository.get(UUID(target_id))
        assert target is not None
        for index in range(SIMILARITY_CANDIDATE_LIMIT + 25):
            repository.save(
                replace(
                    target,
                    ticket_id=uuid4(),
                    reference=f"TCK-LIMIT-{index:04d}",
                    related_ticket_ids=(),
                )
            )

        manager = await login(client, "rfa.manager@example.test")
        app.state.similar_request_service._embeddings = embeddings
        listed = await client.get(f"/api/v1/similar-requests/routing/{source_id}")
        list_call_count = len(embeddings.calls)
        embeddings.calls.clear()
        linked = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/link/{target_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert listed.status_code == 200
    assert list_call_count == SIMILARITY_CANDIDATE_LIMIT + 1
    assert linked.status_code == 200
    assert linked.json()["matches"][0]["ticketId"] == target_id
    assert linked.json()["matches"][0]["alreadyLinked"] is True
    assert len(embeddings.calls) == 2


@pytest.mark.asyncio
async def test_similarity_embedding_work_does_not_block_the_event_loop() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, _target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        await login(client, "rfa.manager@example.test")
        app.state.similar_request_service._embeddings = SlowEmbeddings()

        request = asyncio.create_task(client.get(f"/api/v1/similar-requests/routing/{source_id}"))
        await asyncio.sleep(0.005)

        assert not request.done()
        response = await request

    assert response.status_code == 200


async def _submitted(client: AsyncClient, session: dict[str, object], title: str) -> str:
    return await submitted_ticket(
        client,
        str(session["csrfToken"]),
        title=title,
        question="What vessel movements require attention?",
        region="Gulf of Finland",
        description="Assess synthetic vessel movements.",
        output_format="movement report",
    )
