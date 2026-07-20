import httpx
import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.ticket_builder import ConfigurableIntakeProvider

REFUSAL = "I can only help capture the requirement. Please provide the missing details."
PRIORITY_QUESTION = (
    "Thanks, that helps. How urgent is this for you: critical, high, medium, routine or low?"
)


class ForbiddenClient:
    """Fails the test if the provider tries to reach any external LLM API."""

    def __init__(self, *, timeout: int) -> None:
        raise AssertionError("No external LLM API may be called on this path.")


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
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test", gemini_api_key="env-secret")
    ai_models = AiModelService(settings, AuditLog())
    provider = ConfigurableIntakeProvider(settings, ai_models)

    message = provider.build_assistant_message(_intake(), ())

    assert ai_models.provider() == "mock"
    assert message == PRIORITY_QUESTION


def test_key_configuration_alone_does_not_activate_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    assert ai_models.provider() == "mock"
    assert provider.build_assistant_message(_intake(), ()) == PRIORITY_QUESTION


def test_explicit_provider_activation_routes_replies_to_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    ai_models.select_provider("admin-id", "admin@example.test", "gemini_api")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    assert ai_models.provider() == "gemini_api"
    assert provider.build_assistant_message(_intake(), ()) == "Gemini reply."


def test_flagged_messages_are_refused_without_calling_any_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    ai_models.select_provider("admin-id", "admin@example.test", "gemini_api")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    message = provider.build_assistant_message(_intake(), ("prompt_injection_attempt",))

    assert message == REFUSAL


def test_provider_failure_degrades_to_the_mock_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FailingClient)
    settings = Settings(environment="test", llm_provider="gemini_api", gemini_api_key="env-secret")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == PRIORITY_QUESTION


def test_admitted_reply_reports_remote_fallback_and_success() -> None:
    responses: list[object] = [
        AppError(503, "provider_unavailable", "Synthetic failure."),
        "Remote response.",
    ]

    def reply(_call: object) -> str:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)

    provider = ConfigurableIntakeProvider(
        Settings(environment="test", llm_provider="gemini_api", gemini_api_key="synthetic"),
        None,
        text_generator=reply,
    )

    fallback = provider.build_admitted_assistant_message(_intake(), ())
    success = provider.build_admitted_assistant_message(_intake(), ())

    assert fallback.text == PRIORITY_QUESTION
    assert not fallback.provider_succeeded
    assert success.text == "Remote response."
    assert success.provider_succeeded


def test_provider_circuit_stops_repeated_failed_remote_calls() -> None:
    calls = 0

    def fail(_call: object) -> str:
        nonlocal calls
        calls += 1
        raise AppError(503, "provider_unavailable", "Synthetic provider failure.")

    settings = Settings(
        environment="test",
        llm_provider="gemini_api",
        gemini_api_key="env-secret",
        provider_circuit_failure_threshold=2,
    )
    provider = ConfigurableIntakeProvider(settings, None, text_generator=fail)

    assert provider.build_assistant_message(_intake(), ()) == PRIORITY_QUESTION
    assert provider.build_assistant_message(_intake(), ()) == PRIORITY_QUESTION
    assert provider.build_assistant_message(_intake(), ()) == PRIORITY_QUESTION
    assert calls == 2
    assert not provider.uses_operator_provider()


def test_unexpected_provider_failure_is_recorded_and_propagated() -> None:
    def fail(_call: object) -> str:
        raise RuntimeError("synthetic unexpected failure")

    provider = ConfigurableIntakeProvider(
        Settings(
            environment="test",
            llm_provider="gemini_api",
            gemini_api_key="env-secret",
            provider_circuit_failure_threshold=1,
        ),
        None,
        text_generator=fail,
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        provider.build_assistant_message(_intake(), ())
    assert not provider.uses_operator_provider()


def test_provider_without_key_degrades_to_the_mock_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", ForbiddenClient)
    settings = Settings(environment="test", llm_provider="gemini_api")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == PRIORITY_QUESTION


def test_settings_driven_openai_provider_is_called_without_ai_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "OpenAI reply."}}]}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def post(self, url: str, *, json: object, headers: object) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeClient)
    settings = Settings(environment="test", llm_provider="openai_api", openai_api_key="sk-test")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == "OpenAI reply."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
