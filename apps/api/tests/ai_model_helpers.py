"""Shared fixtures for the AI model and provider tests."""

from typing import Any, ClassVar

from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.audit import AuditEvent, AuditLog

SEED_CREDENTIAL = "CoeusLocal1!"


def make_client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def admin_login(client: AsyncClient, username: str = "admin@example.test") -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


class FailingAuditLog(AuditLog):
    def record(
        self,
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        raise RuntimeError("audit unavailable")


class FakeLlmClient:
    """Fake httpx.Client returning a Gemini-shaped reply and capturing calls."""

    captured: ClassVar[dict[str, Any]] = {}

    def __init__(self, *, timeout: int) -> None:
        FakeLlmClient.captured["timeout"] = timeout

    def __enter__(self) -> "FakeLlmClient":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
    ) -> "FakeLlmClient":
        FakeLlmClient.captured["url"] = url
        FakeLlmClient.captured["headers"] = headers
        FakeLlmClient.captured["body"] = json
        return self

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"candidates": [{"content": {"parts": [{"text": "Gemini reply."}]}}]}
