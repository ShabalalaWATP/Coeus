import json
from typing import Any

import pytest

from ai_model_helpers import admin_login, make_client
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.litellm_endpoint import litellm_base_url_errors, litellm_endpoint
from coeus.domain.advisory_agents import AdvisoryAgentKind, AdvisoryPrompt
from coeus.integrations.llm_gateway import LlmCall, generate_text
from coeus.integrations.llm_models import discover_models
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.advisory_provider_selection import freeze_advisory_provider
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.headers: dict[str, str] = {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield json.dumps(self.payload).encode()


def fake_client(captured: dict[str, Any], payload: object) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
            captured.update(url=url, headers=headers)
            return FakeResponse(payload)

        def stream(
            self,
            method: str,
            url: str,
            *,
            json: dict[str, object] | None = None,
            headers: dict[str, str],
        ) -> FakeResponse:
            captured.update(method=method, url=url, body=json, headers=headers)
            return FakeResponse(payload)

    return FakeClient


def test_litellm_endpoint_normalises_an_origin_or_v1_prefix() -> None:
    assert (
        litellm_endpoint("https://llm.example.test/gateway/", "models")
        == "https://llm.example.test/gateway/v1/models"
    )
    assert (
        litellm_endpoint("https://llm.example.test/gateway/v1", "chat/completions")
        == "https://llm.example.test/gateway/v1/chat/completions"
    )


@pytest.mark.parametrize(
    "url",
    (
        "ftp://llm.example.test",
        "https://user:secret@llm.example.test",
        "https://llm.example.test?target=other",
        "https://llm.example.test/%2e%2e/private",
        "https://llm.example.test/prefix%2fadmin",
        "https://llm.example.test/\nadmin",
        "https://llm.example.test:99999",
    ),
)
def test_litellm_endpoint_rejects_unsafe_or_invalid_urls(url: str) -> None:
    assert litellm_base_url_errors(url, hosted=False)
    with pytest.raises(ValueError, match="base URL is invalid"):
        litellm_endpoint(url, "models")


def test_litellm_requires_https_when_hosted_and_fixed_resources() -> None:
    assert litellm_base_url_errors("http://litellm.internal:4000", hosted=True) == (
        "COEUS_LITELLM_BASE_URL must use HTTPS in hosted environments.",
    )
    with pytest.raises(ValueError, match="resource is invalid"):
        litellm_endpoint("https://llm.example.test", "admin/config")


def test_litellm_chat_uses_the_openai_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    payload = {
        "choices": [{"message": {"content": '{"question":"Where?"}'}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 5},
    }
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", fake_client(captured, payload)
    )
    result = generate_text(
        LlmCall(
            provider="litellm_proxy",
            model="analysis-route",
            api_key="sk-virtual-key",
            prompt="Bounded request context",
            instructions="Return one JSON object.",
            timeout=7,
            max_output_tokens=64,
            structured_output=True,
            litellm_base_url="https://llm.example.test/proxy",
            hosted=True,
        )
    )

    assert result == '{"question":"Where?"}'
    assert (result.input_tokens, result.output_tokens) == (11, 5)
    assert captured["url"] == "https://llm.example.test/proxy/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-virtual-key"
    assert captured["body"]["model"] == "analysis-route"
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_litellm_model_discovery_is_bounded_and_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    payload = {
        "data": [
            {"id": "analysis-route"},
            {"id": "text-embedding-route"},
            {"id": "realtime-route"},
        ]
    }
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", fake_client(captured, payload)
    )

    assert discover_models(
        "litellm_proxy", "sk-virtual-key", 9, "https://llm.example.test", True
    ) == ("analysis-route",)
    assert captured["url"] == "https://llm.example.test/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-virtual-key"


def test_litellm_service_passes_deployment_context_to_discovery() -> None:
    captured: list[object] = []

    def discovery(*args: object) -> tuple[str, ...]:
        captured.extend(args)
        return ("analysis-route",)

    settings = Settings(
        environment="test",
        litellm_api_key="sk-environment-key",
        litellm_base_url="http://litellm:4000",
    )
    service = AiModelService(settings, AuditLog(), MemoryStateStore(), model_discovery=discovery)
    state = service.refresh_models("admin-id", "admin@example.test", "litellm_proxy")
    provider = next(item for item in state.providers if item.name == "litellm_proxy")

    assert provider.supports_model_refresh is True
    assert "analysis-route" in provider.models
    assert captured == [
        "litellm_proxy",
        "sk-environment-key",
        settings.llm_api_timeout_seconds,
        "http://litellm:4000",
        False,
    ]


def test_litellm_gateway_fails_closed_for_hosted_http_without_network() -> None:
    with pytest.raises(AppError) as raised:
        generate_text(
            LlmCall(
                provider="litellm_proxy",
                model="analysis-route",
                api_key="sk-virtual-key",
                prompt="Bounded request context",
                timeout=7,
                litellm_base_url="http://litellm.internal:4000",
                hosted=True,
            )
        )

    assert raised.value.code == "llm_provider_misconfigured"
    assert "http://litellm.internal" not in raised.value.message


def test_advisory_selection_freezes_the_litellm_target_and_guardrails() -> None:
    settings = Settings(
        environment="test",
        llm_provider="litellm_proxy",
        litellm_api_key="sk-virtual-key",
        litellm_api_model="analysis-route",
        available_litellm_models=["analysis-route"],
        litellm_base_url="http://litellm:4000",
    )
    selection = freeze_advisory_provider(
        settings,
        None,
        AdvisoryAgentKind.SEARCH_PLANNER,
        AdvisoryPrompt(
            data='{"question":"bounded"}',
            instructions="Return the closed search plan schema.",
            prompt_version="test-prompt-v1",
            policy_version="test-policy-v1",
            context_schema_version="test-context-v1",
            max_output_tokens=128,
        ),
    )

    assert selection.call is not None
    assert selection.call.provider == "litellm_proxy"
    assert selection.call.litellm_base_url == "http://litellm:4000"
    assert selection.call.structured_output is True
    assert selection.call.max_output_tokens == 128
    assert selection.call.hosted is False


@pytest.mark.asyncio
async def test_admin_can_store_a_virtual_key_and_refresh_litellm_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client",
        fake_client(captured, {"data": [{"id": "analysis-route"}]}),
    )
    async with make_client() as client:
        csrf = await admin_login(client)
        configured = await client.put(
            "/api/v1/admin/ai-model/api-key",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "litellm_proxy", "apiKey": "sk-virtual-key"},
        )
        refreshed = await client.post(
            "/api/v1/admin/ai-model/refresh",
            headers={"X-CSRF-Token": csrf},
            json={"provider": "litellm_proxy"},
        )

    assert configured.status_code == 200
    assert "sk-virtual-key" not in configured.text
    provider = next(
        item for item in refreshed.json()["providers"] if item["name"] == "litellm_proxy"
    )
    assert provider["models"] == ["default", "analysis-route"]
    assert provider["supportsModelRefresh"] is True
    assert captured["url"] == "http://127.0.0.1:4000/v1/models"
