import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_audit_api_pages_beyond_recent_cache() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            persistence_provider="memory",
            audit_log_max_events=2,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        audit = app.state.auth_service.audit_log
        audit.record("user_credential_reset")
        for index in range(3):
            audit.record(f"public_failure_{index}")

        recent = await client.get("/api/v1/audit", params={"limit": 2})
        older = await client.get(
            "/api/v1/audit",
            params={"limit": 2, "before": recent.json()["nextCursor"]},
        )

    assert recent.status_code == 200
    assert [event["eventType"] for event in recent.json()["events"]] == [
        "public_failure_1",
        "public_failure_2",
    ]
    assert recent.json()["nextCursor"] is not None
    assert "user_credential_reset" in {event["eventType"] for event in older.json()["events"]}
