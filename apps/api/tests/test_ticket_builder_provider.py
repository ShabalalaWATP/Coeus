import httpx
import pytest

from coeus.core.config import Settings
from coeus.domain.tickets import IntakeDetails
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.ticket_builder import ConfigurableIntakeProvider

REFUSAL = "I can only help capture the requirement. Please provide the missing details."


class ForbiddenClient:
    """Fails the test if the provider tries to reach the Gemini API."""

    def __init__(self, *, timeout: int) -> None:
        raise AssertionError("Gemini API must not be called on this path.")


class FailingClient:
    def __init__(self, *, timeout: int) -> None:
        self._timeout = timeout

    def __enter__(self) -> "FailingClient":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def post(self, url: str, *, json: object, headers: object) -> object:
        raise httpx.ConnectError("mock network failure")


def _intake() -> IntakeDetails:
    return IntakeDetails(title="Harbour brief", missing_information=("priority",))


def test_env_key_alone_never_switches_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coeus.integrations.gemini_api.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test", gemini_api_key="env-secret")
    ai_models = AiModelService(settings, AuditLog())
    provider = ConfigurableIntakeProvider(settings, ai_models)

    message = provider.build_assistant_message(_intake(), ())

    assert ai_models.provider() == "mock"
    assert message == "I need priority before this can be submitted."


def test_admin_key_configuration_switches_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"candidates": [{"content": {"parts": [{"text": "Gemini reply."}]}}]}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            self._timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def post(self, url: str, *, json: object, headers: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("coeus.integrations.gemini_api.httpx.Client", FakeClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    assert ai_models.provider() == "gemini_api"
    assert provider.build_assistant_message(_intake(), ()) == "Gemini reply."


def test_flagged_messages_are_refused_without_calling_gemini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.gemini_api.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    message = provider.build_assistant_message(_intake(), ("prompt_injection_attempt",))

    assert message == REFUSAL


def test_gemini_failure_degrades_to_the_mock_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coeus.integrations.gemini_api.httpx.Client", FailingClient)
    settings = Settings(environment="test", llm_provider="gemini_api", gemini_api_key="env-secret")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == "I need priority before this can be submitted."


def test_gemini_provider_without_key_degrades_to_the_mock_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.gemini_api.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test", llm_provider="gemini_api")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == "I need priority before this can be submitted."
