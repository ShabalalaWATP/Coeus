import json
from typing import Any, ClassVar

import httpx
import pytest

from coeus.core.errors import AppError
from coeus.integrations.openai_realtime import (
    MAX_SDP_ANSWER_BYTES,
    OPENAI_REALTIME_CALLS_URL,
    create_realtime_call,
)


class FakeClient:
    captured: ClassVar[dict[str, Any]] = {}
    status_code: int | None = None
    network_error = False
    answer = "v=0\r\nm=audio answer\r\n"

    def __init__(self, *, timeout: int) -> None:
        self.captured["timeout"] = timeout

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], files: dict[str, Any]) -> "FakeClient":
        self.captured.update({"url": url, "headers": headers, "files": files})
        if self.network_error:
            request = httpx.Request("POST", OPENAI_REALTIME_CALLS_URL)
            raise httpx.ConnectError("network failure with sk-upstream-leak", request=request)
        return self

    def raise_for_status(self) -> None:
        if self.status_code is not None:
            request = httpx.Request("POST", OPENAI_REALTIME_CALLS_URL)
            response = httpx.Response(
                self.status_code,
                json={"error": {"message": "provider detail with sk-upstream-leak"}},
                request=request,
            )
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    @property
    def text(self) -> str:
        return self.answer


def test_realtime_call_uses_multipart_session_and_safety_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.status_code = None
    FakeClient.network_error = False
    FakeClient.answer = "v=0\r\nm=audio answer\r\n"
    FakeClient.captured = {}
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    answer = create_realtime_call(
        api_key="sk-secret",
        instructions="Guarded synthetic RFI intake.",
        model="gpt-realtime-mini",
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
    assert session["model"] == "gpt-realtime-mini"
    assert session["instructions"] == "Guarded synthetic RFI intake."
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-realtime-whisper"


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
