from typing import Any

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.integrations import gemini_api
from coeus.integrations.gemini_api import GeminiApiLlmProvider


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"candidates": [{"content": {"parts": [{"text": "Please add the priority."}]}}]}


def test_gemini_provider_calls_generate_content(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

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
    provider = GeminiApiLlmProvider(
        Settings(
            gemini_api_key="test-key",
            gemini_api_model="gemini-2.5-flash",
            llm_provider="gemini_api",
        )
    )

    message = provider.build_assistant_message(
        IntakeDetails(title="Harbour brief", missing_information=("priority",)),
        (),
    )

    assert message == "Please add the priority."
    headers = {str(key).casefold(): value for key, value in captured["headers"].items()}
    assert headers["x-goog-api-key"] == "test-key"
    assert "models/gemini-2.5-flash:generateContent" in captured["url"]
    assert captured["timeout"] == 10
    prompt = captured["body"]["contents"][0]["parts"][0]["text"]
    assert "Harbour brief" in prompt


def test_gemini_provider_requires_api_key_before_call() -> None:
    provider = GeminiApiLlmProvider(Settings(llm_provider="gemini_api"))

    with pytest.raises(AppError, match="llm_provider_not_configured"):
        provider.build_assistant_message(IntakeDetails(), ())
