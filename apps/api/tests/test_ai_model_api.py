import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.integrations import gemini_api
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.ai_models import AI_MODEL_NAMESPACE, AiModelService
from coeus.services.audit import AuditLog

SEED_CREDENTIAL = "CoeusLocal1!"


def _client() -> AsyncClient:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


class ToggleStateStore:
    def __init__(self) -> None:
        self.fail_saves = False
        self.payloads: dict[str, dict[str, object]] = {}

    def load(self, namespace: str) -> dict[str, object] | None:
        return self.payloads.get(namespace)

    def save(self, namespace: str, payload: dict[str, object]) -> None:
        if self.fail_saves:
            raise RuntimeError("state store unavailable")
        self.payloads[namespace] = payload


class FailingAuditLog(AuditLog):
    def record(
        self,
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        raise RuntimeError("audit unavailable")


@pytest.mark.asyncio
async def test_admin_reads_and_switches_the_active_gemini_model() -> None:
    async with _client() as client:
        csrf = await _login(client, "admin@example.test")

        state = await client.get("/api/v1/admin/ai-model")
        assert state.status_code == 200
        payload = state.json()
        assert payload["provider"] == "mock"
        assert payload["activeModel"] == "gemini-2.5-flash"
        assert "gemini-2.5-pro" in payload["availableModels"]
        assert payload["apiKeyConfigured"] is False
        assert payload["embeddingProvider"] == "mock"
        assert payload["embeddedProductCount"] == 0
        assert payload["changedBy"] is None
        assert payload["changedAt"] is None

        switched = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gemini-2.5-pro"},
        )
        assert switched.status_code == 200
        assert switched.json()["activeModel"] == "gemini-2.5-pro"
        assert switched.json()["changedBy"] == "admin@example.test"
        assert switched.json()["changedAt"] is not None

        refreshed = await client.get("/api/v1/admin/ai-model")
        assert refreshed.json()["activeModel"] == "gemini-2.5-pro"
        assert refreshed.json()["changedBy"] == "admin@example.test"


@pytest.mark.asyncio
async def test_admin_configures_gemini_key_without_reading_it_back() -> None:
    async with _client() as client:
        csrf = await _login(client, "admin@example.test")

        configured = await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value"},
        )
        assert configured.status_code == 200
        assert configured.json()["provider"] == "gemini_api"
        assert configured.json()["apiKeyConfigured"] is True
        assert "gemini-api-key-value" not in configured.text

        refreshed = await client.get("/api/v1/admin/ai-model")
        assert refreshed.json()["apiKeyConfigured"] is True
        assert "gemini-api-key-value" not in refreshed.text


def test_gemini_key_is_not_persisted_in_state_store() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(
        Settings(environment="test", gemini_api_key="env-secret"),
        AuditLog(),
        state_store=state_store,
    )

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert "api_key" not in payload
    assert "env-secret" not in str(payload)

    service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.api_key() == "runtime-secret"
    assert "api_key" not in payload
    assert "runtime-secret" not in str(payload)


def test_legacy_persisted_gemini_key_is_scrubbed() -> None:
    state_store = MemoryStateStore()
    state_store.save(
        AI_MODEL_NAMESPACE,
        {"active_model": "gemini-2.5-pro", "api_key": "legacy-secret"},
    )

    service = AiModelService(Settings(environment="test"), AuditLog(), state_store=state_store)

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.api_key() is None
    assert service.active_model() == "gemini-2.5-pro"
    assert "api_key" not in payload
    assert "legacy-secret" not in str(payload)


def test_model_selection_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(Settings(environment="test"), FailingAuditLog(), state_store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-2.5-pro")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.active_model() == "gemini-2.5-flash"
    assert service.state().changed_by is None
    assert payload["active_model"] == "gemini-2.5-flash"


def test_model_selection_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.select("admin-id", "admin@example.test", "gemini-2.5-pro")

    assert service.active_model() == "gemini-2.5-flash"
    assert service.state().changed_by is None


def test_api_key_configuration_rolls_back_when_audit_fails() -> None:
    state_store = MemoryStateStore()
    service = AiModelService(Settings(environment="test"), FailingAuditLog(), state_store)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")

    payload = state_store.load(AI_MODEL_NAMESPACE)
    assert payload is not None
    assert service.provider() == "mock"
    assert service.api_key() is None
    assert service.state().api_key_configured is False
    assert "runtime-secret" not in str(payload)


def test_api_key_configuration_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = AiModelService(Settings(environment="test"), AuditLog(), state_store)

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.configure_api_key("admin-id", "admin@example.test", "runtime-secret")

    assert service.provider() == "mock"
    assert service.api_key() is None
    assert service.state().api_key_configured is False


@pytest.mark.asyncio
async def test_admin_gemini_settings_drive_ticket_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"candidates": [{"content": {"parts": [{"text": "Gemini reply."}]}}]}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def post(
            self,
            url: str,
            *,
            json: dict[str, object],
            headers: dict[str, str],
        ) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json
            return FakeResponse()

    monkeypatch.setattr(gemini_api.httpx, "Client", FakeClient)

    async with _client() as client:
        csrf = await _login(client, "admin@example.test")
        await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gemini-2.5-pro"},
        )
        await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"apiKey": "gemini-api-key-value"},
        )
        user_csrf = await _login(client, "user@example.test")
        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": user_csrf},
            json={"message": "Need a routine assessment for Baltic ports."},
        )

    assert response.status_code == 201
    assert response.json()["messages"][-1]["body"] == "Gemini reply."
    assert "models/gemini-2.5-pro:generateContent" in str(captured["url"])
    headers = {str(key).casefold(): value for key, value in captured["headers"].items()}
    assert headers["x-goog-api-key"] == "gemini-api-key-value"


@pytest.mark.asyncio
async def test_env_key_alone_does_not_override_the_configured_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForbiddenClient:
        def __init__(self, *, timeout: int) -> None:
            raise AssertionError("Gemini API must not be called when the provider is mock.")

    monkeypatch.setattr(gemini_api.httpx, "Client", ForbiddenClient)
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, gemini_api_key="env-secret")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await _login(client, "admin@example.test")
        state = await client.get("/api/v1/admin/ai-model")
        assert state.json()["provider"] == "mock"
        assert state.json()["apiKeyConfigured"] is True

        user_csrf = await _login(client, "user@example.test")
        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": user_csrf},
            json={"message": "Need a routine assessment for Baltic ports."},
        )

    assert response.status_code == 201
    assert "before this can be submitted." in response.json()["messages"][-1]["body"]


@pytest.mark.asyncio
async def test_unknown_models_are_rejected() -> None:
    async with _client() as client:
        csrf = await _login(client, "admin@example.test")

        response = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": csrf},
            json={"model": "gpt-99-ultra"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "model_not_available"


@pytest.mark.asyncio
async def test_model_selection_requires_admin_permission_and_csrf() -> None:
    async with _client() as client:
        user_csrf = await _login(client, "user@example.test")

        forbidden_read = await client.get("/api/v1/admin/ai-model")
        assert forbidden_read.status_code == 403

        forbidden_write = await client.put(
            "/api/v1/admin/ai-model",
            headers={"X-CSRF-Token": user_csrf},
            json={"model": "gemini-2.5-pro"},
        )
        assert forbidden_write.status_code == 403

        await _login(client, "admin@example.test")
        missing_csrf = await client.put(
            "/api/v1/admin/ai-model",
            json={"model": "gemini-2.5-pro"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"
