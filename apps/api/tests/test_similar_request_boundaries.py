import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from test_similar_requests_api import login, similar_ticket_pair, submitted_ticket


async def test_join_and_link_reject_invalid_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        colleague = await login(client, "colleague@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(colleague["csrfToken"]))
        admin = await login(client, "admin@example.test")
        non_owner_join = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )

        user = await login(client, "user@example.test")
        unrelated_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Unrelated logistics query",
            question="What are the catering requirements for a training event?",
            region="Southwest England",
            description="Plan non-intelligence logistics for a training event.",
            output_format="logistics note",
        )
        other_unrelated_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Independent catering query",
            question="Which suppliers can cater a conference in Cardiff?",
            region="Cardiff",
            description="Plan catering for an unrelated conference.",
            output_format="supplier note",
        )
        monkeypatch.setattr(app.state.similar_request_service, "_find_match", lambda *_args: None)
        no_match_join = await client.post(
            f"/api/v1/similar-requests/tickets/{unrelated_id}/join/{other_unrelated_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

        manager = await login(client, "rfa.manager@example.test")
        self_link = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/link/{source_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert non_owner_join.status_code == 404
    assert no_match_join.status_code == 404
    assert self_link.status_code == 422
