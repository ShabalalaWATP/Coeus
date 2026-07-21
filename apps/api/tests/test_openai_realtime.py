import json
from collections.abc import Iterator
from typing import Any, ClassVar

import httpx
import pytest

from coeus.core.errors import AppError
from coeus.integrations.openai_realtime import (
    MAX_SDP_ANSWER_BYTES,
    MAX_TEST_RESPONSE_BYTES,
    OPENAI_REALTIME_CALLS_URL,
    OPENAI_REALTIME_CLIENT_SECRETS_URL,
    create_realtime_call,
)
from coeus.integrations.openai_realtime import (
    test_realtime_connection as check_realtime_connection,
)


class FakeClient:
    captured: ClassVar[dict[str, Any]] = {}
    status_code: int | None = None
    network_error = False
    answer = "v=0\r\nm=audio answer\r\n"
    payload: ClassVar[dict[str, Any]] = {
        "value": "ek-test",
        "expires_at": 1_754_440_432,
        "session": {"type": "realtime", "model": "gpt-realtime-mini"},
    }
    raw_content: bytes | None = None

    def __init__(self, *, timeout: int) -> None:
        self.captured["timeout"] = timeout

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> "FakeClient":
        self.captured.update({"url": url, "headers": headers, "files": files, "json": json})
        if self.network_error:
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("network failure with sk-upstream-leak", request=request)
        return self

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> "FakeClient":
        self.captured["method"] = method
        return self.post(url, headers=headers, json=json)

    def raise_for_status(self) -> None:
        if self.status_code is not None:
            request = httpx.Request("POST", str(self.captured["url"]))
            response = httpx.Response(
                self.status_code,
                json={"error": {"message": "provider detail with sk-upstream-leak"}},
                request=request,
            )
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    @property
    def text(self) -> str:
        return self.answer

    @property
    def content(self) -> bytes:
        return self.raw_content or json.dumps(self.payload).encode()

    def iter_bytes(self) -> Iterator[bytes]:
        content = self.content
        midpoint = max(1, len(content) // 2)
        yield content[:midpoint]
        yield content[midpoint:]

    def json(self) -> dict[str, Any]:
        return self.payload


def test_realtime_connection_creates_a_bounded_client_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = False
    FakeClient.payload = {
        "value": "ek-test",
        "expires_at": 1_754_440_432,
        "session": {"type": "realtime", "model": "gpt-realtime-mini"},
    }
    FakeClient.raw_content = None
    FakeClient.captured = {}
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    check_realtime_connection(api_key="sk-secret", model="gpt-realtime-mini")

    assert FakeClient.captured["timeout"] == 10
    assert FakeClient.captured["method"] == "POST"
    assert FakeClient.captured["url"] == OPENAI_REALTIME_CLIENT_SECRETS_URL
    assert FakeClient.captured["headers"] == {"Authorization": "Bearer sk-secret"}
    assert FakeClient.captured["json"] == {
        "session": {"type": "realtime", "model": "gpt-realtime-mini"}
    }


@pytest.mark.parametrize(
    ("payload", "raw_content"),
    [
        ({}, None),
        ({"value": ""}, None),
        ({"value": "ek-test"}, b"x" * (MAX_TEST_RESPONSE_BYTES + 1)),
        ({"value": "ek-test"}, b"\xff"),
    ],
    ids=["missing-secret", "missing-value", "oversized", "invalid-encoding"],
)
def test_realtime_connection_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    raw_content: bytes | None,
) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = False
    FakeClient.payload = payload
    FakeClient.raw_content = raw_content
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        check_realtime_connection(api_key="sk-secret", model="gpt-realtime-mini")

    assert raised.value.code == "voice_provider_invalid_response"


def test_realtime_connection_sanitises_provider_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.status_code = 401
    FakeClient.network_error = False
    FakeClient.raw_content = None
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        check_realtime_connection(api_key="sk-secret", model="gpt-realtime-mini")

    assert raised.value.code == "voice_provider_credentials_rejected"
    assert "sk-secret" not in raised.value.message


@pytest.mark.parametrize(
    ("model", "reasoning"),
    [("gpt-realtime-mini", None), ("gpt-realtime-2.1", {"effort": "low"})],
)
def test_realtime_models_share_the_guarded_session_contract(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    reasoning: dict[str, str] | None,
) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = False
    FakeClient.answer = "v=0\r\nm=audio answer\r\n"
    FakeClient.captured = {}
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    answer = create_realtime_call(
        api_key="sk-secret",
        instructions="Guarded synthetic RFI intake.",
        model=model,
        voice="marin",
        sdp="v=0\r\nm=audio offer\r\n",
        safety_identifier="safe-user",
    )

    assert answer.startswith("v=0")
    assert FakeClient.captured["url"] == OPENAI_REALTIME_CALLS_URL
    assert FakeClient.captured["headers"] == {
        "Authorization": "Bearer sk-secret",
        "OpenAI-Safety-Identifier": "safe-user",
    }
    files = FakeClient.captured["files"]
    assert files["sdp"] == (None, "v=0\r\nm=audio offer\r\n")
    session = json.loads(files["session"][1])
    assert session["model"] == model
    assert session["instructions"] == "Guarded synthetic RFI intake."
    assert session["max_output_tokens"] == 256
    assert session["tools"] == []
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-realtime-whisper"
    assert session.get("reasoning") == reasoning


@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_code", "message_fragment"),
    [
        (400, 503, "voice_provider_configuration_rejected", "session configuration"),
        (401, 503, "voice_provider_credentials_rejected", "API key"),
        (403, 503, "voice_provider_credentials_rejected", "API key"),
        (404, 503, "voice_model_not_available", "model is unavailable"),
        (422, 503, "voice_provider_configuration_rejected", "session configuration"),
        (429, 503, "voice_provider_rate_limited", "quota or is rate limited"),
        (500, 502, "voice_provider_unavailable", "temporarily unavailable"),
    ],
)
def test_realtime_call_maps_upstream_status_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_status: int,
    expected_code: str,
    message_fragment: str,
) -> None:
    FakeClient.status_code = status_code
    FakeClient.network_error = False
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            instructions="Guarded synthetic RFI intake.",
            model="gpt-realtime-mini",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.status_code == expected_status
    assert raised.value.code == expected_code
    assert message_fragment in raised.value.message
    assert "sk-secret" not in raised.value.message
    assert "sk-upstream-leak" not in raised.value.message


def test_realtime_call_hides_network_error_details(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = True
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            instructions="Guarded synthetic RFI intake.",
            model="gpt-realtime-mini",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.status_code == 502
    assert raised.value.code == "voice_provider_unavailable"
    assert "sk-upstream-leak" not in raised.value.message


@pytest.mark.parametrize(
    "answer",
    ["not-sdp", "v=0" + ("x" * (MAX_SDP_ANSWER_BYTES + 1))],
    ids=["malformed", "oversized"],
)
def test_realtime_call_rejects_an_invalid_answer(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = False
    FakeClient.answer = answer
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            instructions="Guarded synthetic RFI intake.",
            model="gpt-realtime-mini",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.status_code == 502
    assert raised.value.code == "voice_provider_invalid_response"
