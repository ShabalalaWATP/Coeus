"""Shared fixtures for the AI model and provider tests."""

import json
from collections.abc import Callable
from typing import Any, ClassVar

from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.audit import AuditEvent, AuditLog

SEED_CREDENTIAL = "CoeusLocal1!"


def make_client(*, app_wrapper: Callable[[Any], Any] | None = None) -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    if app_wrapper is not None:
        app = app_wrapper(app)
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

    def stream(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
    ) -> "FakeLlmClient":
        FakeLlmClient.captured["method"] = method
        FakeLlmClient.captured["url"] = url
        FakeLlmClient.captured["headers"] = headers
        FakeLlmClient.captured["body"] = json
        return self

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        reply = json.dumps(
            {
                "action": "ask_missing_field",
                "strategy": "ask_one_field",
                "reason_codes": ["missing_required_field"],
                "suggested_field": "operational_question",
                "abstain": False,
            }
        )
        payload = {"candidates": [{"content": {"parts": [{"text": reply}]}}]}
        yield json.dumps(payload).encode()
