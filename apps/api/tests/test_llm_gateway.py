from typing import Any

import pytest

from coeus.core.errors import AppError
from coeus.integrations.llm_gateway import LlmCall, _reply_text, generate_text


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _fake_client(captured: dict[str, Any], payload: dict[str, object]) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def post(
            self, url: str, *, json: dict[str, object], headers: dict[str, str]
        ) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json
            return FakeResponse(payload)

    return FakeClient


def _call(provider: str, **overrides: Any) -> LlmCall:
    defaults: dict[str, Any] = {
        "provider": provider,
        "model": "test-model",
        "api_key": "test-key",
        "prompt": "Harbour brief prompt",
        "timeout": 10,
        "region": "eu-west-2",
    }
    defaults.update(overrides)
    return LlmCall(**defaults)


def test_gemini_call_uses_key_header_and_generate_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {"candidates": [{"content": {"parts": [{"text": "Gemini says hello."}]}}]}
    monkeypatch.setattr(
        "coeus.integrations.llm_gateway.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("gemini_api", model="gemini-2.5-flash"))

    assert text == "Gemini says hello."
    assert "models/gemini-2.5-flash:generateContent" in str(captured["url"])
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "key=" not in str(captured["url"])


def test_openai_call_uses_bearer_token_and_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {"choices": [{"message": {"content": "OpenAI says hello."}}]}
    monkeypatch.setattr(
        "coeus.integrations.llm_gateway.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("openai_api", model="gpt-5-mini"))

    assert text == "OpenAI says hello."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "gpt-5-mini"


def test_vertex_call_targets_the_publisher_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    payload = {"candidates": [{"content": {"parts": [{"text": "Vertex says hello."}]}}]}
    monkeypatch.setattr(
        "coeus.integrations.llm_gateway.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("vertex_ai", model="gemini-2.5-pro"))

    assert text == "Vertex says hello."
    assert "aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-pro" in str(
        captured["url"]
    )
    assert captured["headers"]["x-goog-api-key"] == "test-key"


def test_bedrock_call_targets_the_regional_converse_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {"output": {"message": {"content": [{"text": "Bedrock says hello."}]}}}
    monkeypatch.setattr(
        "coeus.integrations.llm_gateway.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("bedrock", model="anthropic.claude-haiku-4-5-20251001-v1:0"))

    assert text == "Bedrock says hello."
    assert str(captured["url"]).startswith("https://bedrock-runtime.eu-west-2.amazonaws.com/model/")
    assert str(captured["url"]).endswith("/converse")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["messages"][0]["content"] == [{"text": "Harbour brief prompt"}]


def test_unknown_provider_is_rejected_before_any_network_call() -> None:
    with pytest.raises(AppError, match="llm_provider_unknown"):
        generate_text(_call("carrier_pigeon"))


def test_network_failures_surface_as_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RaisingClient:
        def __init__(self, *, timeout: int) -> None:
            pass

        def __enter__(self) -> "RaisingClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def post(self, url: str, *, json: object, headers: object) -> FakeResponse:
            import httpx

            raise httpx.ConnectError("mock network failure")

    monkeypatch.setattr("coeus.integrations.llm_gateway.httpx.Client", RaisingClient)
    with pytest.raises(AppError, match="llm_provider_unavailable"):
        generate_text(_call("openai_api"))


def test_reply_text_rejects_malformed_response_shapes() -> None:
    assert _reply_text("gemini_api", []) == ""
    assert _reply_text("gemini_api", {"candidates": []}) == ""
    assert _reply_text("gemini_api", {"candidates": [{"content": {"parts": "invalid"}}]}) == ""
    assert _reply_text("openai_api", {"choices": []}) == ""
    assert _reply_text("openai_api", {"choices": [{"message": {"content": None}}]}) == ""
    assert _reply_text("openai_api", {"choices": ["invalid"]}) == ""
    assert _reply_text("bedrock", {"output": "invalid"}) == ""
    assert _reply_text("bedrock", {"output": {"message": {"content": "invalid"}}}) == ""
