import asyncio
import time
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import AnalystAssignment, IntakeDetails, RoutingRoute
from coeus.main import create_app
from coeus.services.similar_request_scoring import MAX_VECTOR_CANDIDATES
from test_similar_requests_api import login, similar_ticket_pair, submitted_ticket


class RecordingEmbeddings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def embed(
        self, text: str, *, purpose: str, principal_id: object | None = None
    ) -> tuple[float, ...]:
        self.calls.append((text, purpose))
        return (1.0,) * 384


class SlowEmbeddings(RecordingEmbeddings):
    def embed(
        self, text: str, *, purpose: str, principal_id: object | None = None
    ) -> tuple[float, ...]:
        time.sleep(0.02)
        return super().embed(text, purpose=purpose, principal_id=principal_id)


class IndexedEmbeddings:
    space_id = "mock:indexed-test:1536:g1"

    def embed_many(
        self, texts: tuple[str, ...], *, principal_id: object
    ) -> tuple[tuple[float, ...], ...]:
        return tuple(self._vector(text) for text in texts)

    def embed(
        self, text: str, *, purpose: str, principal_id: object | None = None
    ) -> tuple[float, ...]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> tuple[float, ...]:
        relevant = "quasar" in text.casefold() or "nebula" in text.casefold()
        dimension = 0 if relevant else 1
        return tuple(1.0 if index == dimension else 0.0 for index in range(1536))


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
    assert joined.status_code == 409
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
        for index in range(125):
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
    assert list_call_count == MAX_VECTOR_CANDIDATES + 1
    assert linked.status_code == 200
    assert linked.json()["matches"][0]["ticketId"] == target_id
    assert linked.json()["matches"][0]["alreadyLinked"] is True
    assert len(embeddings.calls) == 2


@pytest.mark.asyncio
async def test_manager_finds_rfa_and_collection_matches_after_100_unrelated_tickets() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id = await _submitted(client, user, "Baltic vessel movement assessment")
        repository = app.state.ticket_services.tickets._repository
        source = repository.get(UUID(source_id))
        assert source is not None
        for index in range(125):
            repository.save(
                replace(
                    source,
                    ticket_id=uuid4(),
                    reference=f"TCK-UNRELATED-{index:04d}",
                    intake=IntakeDetails(
                        title=f"Synthetic weather pattern {index}",
                        description="Assess mock Antarctic weather.",
                        operational_question="What weather is expected?",
                        area_or_region="Antarctic",
                    ),
                )
            )
        rfa = _routed_copy(source, RoutingRoute.RFA, "RFA Baltic Team", "TCK-LATE-RFA")
        collection = _routed_copy(
            source,
            RoutingRoute.CM,
            "Collection Baltic Team",
            "TCK-LATE-COLLECTION",
        )
        repository.save(rfa)
        repository.save(collection)
        await login(client, "rfa.manager@example.test")
        app.state.similar_request_service._embeddings = RecordingEmbeddings()

        listed = await client.get(f"/api/v1/similar-requests/routing/{source_id}")

    assert listed.status_code == 200
    matches = {item["ticketId"]: item for item in listed.json()["matches"]}
    assert str(rfa.ticket_id) in matches
    assert str(collection.ticket_id) in matches
    assert matches[str(rfa.ticket_id)]["requestKind"] == "RFA"
    assert matches[str(rfa.ticket_id)]["assignedTeam"] == "RFA Baltic Team"
    assert matches[str(collection.ticket_id)]["requestKind"] == "Collection"


@pytest.mark.asyncio
async def test_ready_v2_index_finds_semantic_match_beyond_legacy_candidate_cap() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    indexed = IndexedEmbeddings()
    legacy = RecordingEmbeddings()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Quasar transport anomaly",
            question="Where is the quasar cargo moving?",
            region="Sector Alpha",
            description="Assess the synthetic quasar transit pattern.",
            output_format="briefing note",
        )
        for index in range(MAX_VECTOR_CANDIDATES + 8):
            await submitted_ticket(
                client,
                str(user["csrfToken"]),
                title=f"Weather observation {index}",
                question=f"What is the synthetic cloud state {index}?",
                region="Antarctic",
                description="Assess a synthetic weather observation.",
                output_format="weather table",
            )
        target_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Nebula logistics pattern",
            question="Locate the nebula transit route.",
            region="Sector Zulu",
            description="Trace a synthetic nebula logistics pattern.",
            output_format="map layer",
        )
        app.state.search_indexing_service._embeddings = indexed
        app.state.similar_request_service._search_embeddings = indexed
        app.state.similar_request_service._embeddings = legacy
        admin = await login(client, "admin@example.test")
        reindexed = await client.post(
            "/api/v1/admin/search-embeddings/reindex",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )
        await login(client, "rfa.manager@example.test")
        listed = await client.get(f"/api/v1/similar-requests/routing/{source_id}")

    assert reindexed.status_code == 202
    assert listed.status_code == 200
    assert target_id in {item["ticketId"] for item in listed.json()["matches"]}
    assert legacy.calls == []


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


def _routed_copy(source, route: RoutingRoute, team_name: str, reference: str):
    ticket_id = uuid4()
    return replace(
        source,
        ticket_id=ticket_id,
        reference=reference,
        analyst_assignments=(
            AnalystAssignment(
                assignment_id=uuid4(),
                ticket_id=ticket_id,
                analyst_user_id=uuid4(),
                assigned_by_user_id=uuid4(),
                route=route,
                created_at=datetime.now(UTC),
                team_name=team_name,
            ),
        ),
    )
