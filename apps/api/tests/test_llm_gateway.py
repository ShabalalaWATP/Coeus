import json
from typing import Any

import pytest

from coeus.core.errors import AppError
from coeus.integrations.llm_gateway import (
    LlmCall,
    _reply_text,
    _request_for,
    _token_usage,
    generate_text,
)


class FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        raw: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._payload = payload
        self._raw = raw
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield self._raw if self._raw is not None else json.dumps(self._payload).encode()


def _fake_client(captured: dict[str, Any], payload: dict[str, object]) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
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
        ) -> FakeResponse:
            captured["method"] = method
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
        "instructions": "Trusted instructions",
        "max_output_tokens": 123,
        "structured_output": True,
    }
    defaults.update(overrides)
    return LlmCall(**defaults)


def test_gemini_call_uses_key_header_and_generate_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {
        "candidates": [{"content": {"parts": [{"text": "Gemini says hello."}]}}],
        "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4},
    }
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("gemini_api", model="gemini-3.5-flash"))

    assert text == "Gemini says hello."
    assert "models/gemini-3.5-flash:generateContent" in str(captured["url"])
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["headers"]["Accept-Encoding"] == "identity"
    assert "key=" not in str(captured["url"])
    assert captured["method"] == "POST"
    assert captured["body"]["systemInstruction"] == {"parts": [{"text": "Trusted instructions"}]}
    assert captured["body"]["generationConfig"] == {
        "maxOutputTokens": 123,
        "responseMimeType": "application/json",
    }
    assert text.input_tokens == 12
    assert text.output_tokens == 4


def test_openai_call_uses_bearer_token_and_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {"choices": [{"message": {"content": "OpenAI says hello."}}]}
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("openai_api", model="gpt-5.6-terra"))

    assert text == "OpenAI says hello."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "gpt-5.6-terra"
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "Trusted instructions"},
        {"role": "user", "content": "Harbour brief prompt"},
    ]
    assert captured["body"]["max_completion_tokens"] == 123
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_vertex_call_targets_the_publisher_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    payload = {"candidates": [{"content": {"parts": [{"text": "Vertex says hello."}]}}]}
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("vertex_ai", model="gemini-2.5-pro"))

    assert text == "Vertex says hello."
    assert "aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-pro" in str(
        captured["url"]
    )
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["body"]["generationConfig"]["maxOutputTokens"] == 123


def test_bedrock_call_targets_the_regional_converse_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {"output": {"message": {"content": [{"text": "Bedrock says hello."}]}}}
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(captured, payload)
    )

    text = generate_text(_call("bedrock", model="anthropic.claude-haiku-4-5-20251001-v1:0"))

    assert text == "Bedrock says hello."
    assert str(captured["url"]).startswith("https://bedrock-runtime.eu-west-2.amazonaws.com/model/")
    assert str(captured["url"]).endswith("/converse")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["messages"][0]["content"] == [{"text": "Harbour brief prompt"}]
    assert captured["body"]["system"] == [{"text": "Trusted instructions"}]
    assert captured["body"]["inferenceConfig"] == {"maxTokens": 123}


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

        def stream(self, method: str, url: str, *, json: object, headers: object) -> FakeResponse:
            import httpx

            raise httpx.ConnectError("mock network failure")

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", RaisingClient)
    with pytest.raises(AppError, match="llm_provider_unavailable"):
        generate_text(_call("openai_api"))


def test_oversized_response_is_rejected_while_streaming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    raw = b"x" * 11
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client",
        _fake_client(captured, {}),
    )
    monkeypatch.setattr("coeus.integrations.llm_gateway.MAX_LLM_PROVIDER_RESPONSE_BYTES", 10)

    class OversizedClient(_fake_client(captured, {})):
        def stream(self, method: str, url: str, *, json: object, headers: object) -> FakeResponse:
            return FakeResponse({}, raw=raw)

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", OversizedClient)

    with pytest.raises(AppError, match="llm_provider_invalid_response"):
        generate_text(_call("openai_api"))


def test_invalid_json_and_invalid_output_limit_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class InvalidJsonClient(_fake_client(captured, {})):
        def stream(self, method: str, url: str, *, json: object, headers: object) -> FakeResponse:
            return FakeResponse({}, raw=b"not-json")

    monkeypatch.setattr("coeus.integrations.provider_http.httpx.Client", InvalidJsonClient)
    with pytest.raises(AppError, match="llm_provider_invalid_response"):
        generate_text(_call("openai_api"))
    with pytest.raises(AppError, match="llm_output_limit_invalid"):
        generate_text(_call("openai_api", max_output_tokens=0))


@pytest.mark.parametrize("provider", ["gemini_api", "vertex_ai", "openai_api", "bedrock"])
def test_plain_text_request_keeps_data_in_the_user_message(provider: str) -> None:
    _, _, body = _request_for(
        _call(provider, instructions="", structured_output=False, max_output_tokens=7)
    )

    assert "systemInstruction" not in body
    assert "system" not in body
    if provider in ("gemini_api", "vertex_ai"):
        assert body["generationConfig"] == {"maxOutputTokens": 7}
    elif provider == "openai_api":
        assert body["messages"] == [{"role": "user", "content": "Harbour brief prompt"}]
        assert "response_format" not in body
    else:
        assert body["inferenceConfig"] == {"maxTokens": 7}


def test_usage_metadata_rejects_malformed_or_negative_counts() -> None:
    assert _token_usage("openai_api", []) == (None, None)
    assert _token_usage("openai_api", {"usage": "invalid"}) == (None, None)
    assert _token_usage(
        "openai_api", {"usage": {"prompt_tokens": -1, "completion_tokens": "four"}}
    ) == (None, None)


def test_reply_text_rejects_malformed_response_shapes() -> None:
    assert _reply_text("gemini_api", []) == ""
    assert _reply_text("gemini_api", {"candidates": []}) == ""
    assert _reply_text("gemini_api", {"candidates": [{"content": {"parts": "invalid"}}]}) == ""
    assert _reply_text("openai_api", {"choices": []}) == ""
    assert _reply_text("openai_api", {"choices": [{"message": {"content": None}}]}) == ""
    assert _reply_text("openai_api", {"choices": ["invalid"]}) == ""
    assert _reply_text("bedrock", {"output": "invalid"}) == ""
    assert _reply_text("bedrock", {"output": {"message": {"content": "invalid"}}}) == ""
