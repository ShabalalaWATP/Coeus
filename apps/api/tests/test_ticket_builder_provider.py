import json

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


class JsonStream:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> "JsonStream":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield json.dumps(self._payload).encode()


def _structured_reply() -> str:
    return json.dumps(
        {
            "action": "ask_missing_field",
            "strategy": "ask_one_field",
            "reason_codes": ["missing_required_field"],
            "suggested_field": "priority",
            "abstain": False,
        }
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

    def stream(self, method: str, url: str, *, json: object, headers: object) -> object:
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
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            self._timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def stream(self, method: str, url: str, *, json: object, headers: object) -> JsonStream:
            reply = _structured_reply()
            return JsonStream({"candidates": [{"content": {"parts": [{"text": reply}]}}]})

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeClient)
    settings = Settings(environment="test")
    ai_models = AiModelService(settings, AuditLog())
    ai_models.configure_api_key("admin-id", "admin@example.test", "runtime-secret")
    ai_models.select_provider("admin-id", "admin@example.test", "gemini_api")
    provider = ConfigurableIntakeProvider(settings, ai_models)

    assert ai_models.provider() == "gemini_api"
    assert provider.build_assistant_message(_intake(), ()) == PRIORITY_QUESTION


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
        _structured_reply(),
    ]

    def reply(_call: object) -> str:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)

    provider = ConfigurableIntakeProvider(
        Settings(
            environment="test",
            llm_provider="gemini_api",
            gemini_api_key="synthetic",
        ),
        None,
        text_generator=reply,
    )

    fallback = provider.build_admitted_assistant_message(_intake(), ())
    success = provider.build_admitted_assistant_message(_intake(), ())

    assert fallback.text == PRIORITY_QUESTION
    assert not fallback.provider_succeeded
    assert success.text == PRIORITY_QUESTION
    assert success.provider_succeeded
    assert success.provider == "gemini_api"
    assert success.model
    assert success.duration_ms is not None
    assert success.outcome == "provider_success"
    assert success.prompt_version == "intake-planner-v1"


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
    assert not provider.prepare_assistant_reply(_intake(), ()).requires_admission


def test_unexpected_provider_failure_is_recorded_and_falls_back() -> None:
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

    reply = provider.build_admitted_assistant_message(_intake(), ())

    assert reply.text == PRIORITY_QUESTION
    assert reply.outcome == "provider_error_fallback"
    assert reply.error_class == "RuntimeError"
    assert not provider.prepare_assistant_reply(_intake(), ()).requires_admission


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

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def stream(self, method: str, url: str, *, json: object, headers: object) -> JsonStream:
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json
            return JsonStream({"choices": [{"message": {"content": _structured_reply()}}]})

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", FakeClient)
    settings = Settings(environment="test", llm_provider="openai_api", openai_api_key="sk-test")
    provider = ConfigurableIntakeProvider(settings, None)

    message = provider.build_assistant_message(_intake(), ())

    assert message == PRIORITY_QUESTION
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["max_completion_tokens"] == 256
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert "PURPOSE: advise the deterministic RFI intake controller only" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    prompt = json.loads(messages[1]["content"])
    assert "Harbour brief" not in messages[1]["content"]
    assert prompt == {"captured_fields": {}, "missing_fields": ["priority"]}
