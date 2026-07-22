from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.embedding_math import mock_embedding
from coeus.domain.enums import TicketState
from coeus.main import create_app
from coeus.services.embeddings import EmbeddingService
from coeus.services.provider_admission import ProviderAdmissionController
from rfi_search_helpers import login, submitted_ticket


class CountingRemoteEmbeddingProvider:
    name = "synthetic-remote"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls += 1
        return mock_embedding(text)


def _admission(max_calls: int) -> ProviderAdmissionController:
    return ProviderAdmissionController(
        max_concurrent=2,
        max_calls_per_window=max_calls,
        max_calls_per_principal=max_calls,
        window_seconds=60,
    )


@pytest.mark.asyncio
async def test_store_normalises_and_caches_queries_before_provider_admission() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    provider = CountingRemoteEmbeddingProvider()
    app.state.store_services.search._embeddings = EmbeddingService(provider, _admission(1))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        first = await client.get(
            "/api/v1/store/products", params={"query": "  Regional   Stability "}
        )
        cached = await client.get("/api/v1/store/products", params={"query": "regional stability"})
        denied = await client.get("/api/v1/store/products", params={"query": "collection sensors"})

    assert first.status_code == 200
    assert cached.status_code == 200
    assert denied.status_code == 429
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_rfi_one_run_gate_and_provider_budget_precede_mutation() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )
    provider = CountingRemoteEmbeddingProvider()
    app.state.rfi_search_service._embeddings = EmbeddingService(provider, _admission(2))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_ids = [
            await submitted_ticket(
                client,
                csrf,
                title=f"Synthetic request {index}",
                area_or_region=f"Synthetic region {index}",
            )
            for index in range(3)
        ]
        first = await client.post(
            f"/api/v1/rfi-search/{ticket_ids[0]}/run",
            headers={"X-CSRF-Token": csrf},
        )
        repeat = await client.post(
            f"/api/v1/rfi-search/{ticket_ids[0]}/run",
            headers={"X-CSRF-Token": csrf},
        )
        second = await client.post(
            f"/api/v1/rfi-search/{ticket_ids[1]}/run",
            headers={"X-CSRF-Token": csrf},
        )
        denied = await client.post(
            f"/api/v1/rfi-search/{ticket_ids[2]}/run",
            headers={"X-CSRF-Token": csrf},
        )

    untouched = app.state.ticket_services.tickets._repository.get(UUID(ticket_ids[2]))
    assert first.status_code == 200
    assert repeat.status_code == 409
    assert second.status_code == 200
    assert denied.status_code == 429
    assert provider.calls == 2
    assert untouched is not None
    assert untouched.state == TicketState.RFI_SEARCHING
    assert untouched.search_metrics == ()
