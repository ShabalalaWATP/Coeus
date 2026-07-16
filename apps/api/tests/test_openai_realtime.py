import json
from typing import Any, ClassVar

import httpx
import pytest

from coeus.core.errors import AppError
from coeus.integrations.openai_realtime import OPENAI_REALTIME_CALLS_URL, create_realtime_call


class FakeClient:
    captured: ClassVar[dict[str, Any]] = {}
    fail = False
    answer = "v=0\r\nm=audio answer\r\n"

    def __init__(self, *, timeout: int) -> None:
        self.captured["timeout"] = timeout

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], files: dict[str, Any]) -> "FakeClient":
        self.captured.update({"url": url, "headers": headers, "files": files})
        return self

    def raise_for_status(self) -> None:
        if self.fail:
            request = httpx.Request("POST", OPENAI_REALTIME_CALLS_URL)
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    @property
    def text(self) -> str:
        return self.answer


def test_realtime_call_uses_multipart_session_and_safety_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.fail = False
    FakeClient.answer = "v=0\r\nm=audio answer\r\n"
    FakeClient.captured = {}
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    answer = create_realtime_call(
        api_key="sk-secret",
        model="gpt-realtime-2.1-mini",
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
    assert session["model"] == "gpt-realtime-2.1-mini"
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-realtime-whisper"


def test_realtime_call_hides_upstream_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.fail = True
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            model="gpt-realtime-2.1-mini",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.status_code == 502
    assert raised.value.code == "voice_provider_unavailable"
    assert "401" not in raised.value.message


def test_realtime_call_rejects_a_malformed_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.fail = False
    FakeClient.answer = "not-sdp"
    monkeypatch.setattr("coeus.integrations.openai_realtime.httpx.Client", FakeClient)

    with pytest.raises(AppError) as raised:
        create_realtime_call(
            api_key="sk-secret",
            model="gpt-realtime-2.1-mini",
            voice="marin",
            sdp="v=0\r\nm=audio offer\r\n",
            safety_identifier="safe-user",
        )

    assert raised.value.code == "voice_provider_unavailable"
