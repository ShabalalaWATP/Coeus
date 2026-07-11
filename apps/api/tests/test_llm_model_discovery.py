from typing import Any

import httpx
import pytest

from coeus.core.errors import AppError
from coeus.integrations.llm_models import discover_models


def _fake_get_client(captured: dict[str, Any], payload: dict[str, object]) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def get(self, url: str, *, headers: dict[str, str]) -> "FakeClient":
            captured["url"] = url
            captured["headers"] = headers
            return self

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return payload

    return FakeClient


def test_openai_listing_keeps_chat_models_and_drops_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {
        "data": [
            {"id": "gpt-5"},
            {"id": "gpt-6-turbo"},
            {"id": "o3-pro"},
            {"id": "text-embedding-3-large"},
            {"id": "whisper-1"},
            {"id": "dall-e-3"},
            {"id": "chatgpt-5-latest"},
            {"id": ""},
            "not-a-dict",
        ]
    }
    monkeypatch.setattr(
        "coeus.integrations.llm_models.httpx.Client", _fake_get_client(captured, payload)
    )

    models = discover_models("openai_api", "sk-key", 10)

    assert models == ("chatgpt-5-latest", "gpt-5", "gpt-6-turbo", "o3-pro")
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-key"


def test_gemini_listing_keeps_generatecontent_models(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    payload = {
        "models": [
            {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/", "supportedGenerationMethods": ["generateContent"]},
            {"supportedGenerationMethods": "invalid"},
        ]
    }
    monkeypatch.setattr(
        "coeus.integrations.llm_models.httpx.Client", _fake_get_client(captured, payload)
    )

    models = discover_models("gemini_api", "gk-key", 10)

    assert models == ("gemini-3-flash", "gemini-3-pro")
    assert captured["headers"]["x-goog-api-key"] == "gk-key"


def test_unsupported_providers_ask_for_manual_entry() -> None:
    for provider in ("vertex_ai", "bedrock"):
        with pytest.raises(AppError, match="refresh_not_supported"):
            discover_models(provider, "key", 10)


def test_listing_network_failure_surfaces_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingClient:
        def __init__(self, *, timeout: int) -> None:
            pass

        def __enter__(self) -> "FailingClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def get(self, url: str, *, headers: dict[str, str]) -> object:
            raise httpx.ConnectError("mock network failure")

    monkeypatch.setattr("coeus.integrations.llm_models.httpx.Client", FailingClient)
    with pytest.raises(AppError, match="llm_provider_unavailable"):
        discover_models("openai_api", "sk-key", 10)


def test_non_dict_payload_yields_no_models(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "coeus.integrations.llm_models.httpx.Client",
        _fake_get_client(captured, []),  # type: ignore[arg-type]
    )
    assert discover_models("openai_api", "sk-key", 10) == ()
