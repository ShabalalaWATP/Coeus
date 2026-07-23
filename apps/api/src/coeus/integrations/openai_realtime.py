import json

import httpx

from coeus.core.errors import AppError
from coeus.integrations.bounded_http import TotalDeadline, total_deadline_client

OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
OPENAI_REALTIME_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"
MAX_SDP_ANSWER_BYTES = 64 * 1024
MAX_TEST_RESPONSE_BYTES = 64 * 1024


def test_realtime_connection(*, api_key: str, model: str) -> None:
    """Validate Realtime credentials without opening an audio connection."""
    try:
        with (
            total_deadline_client(10) as (client, deadline),
            client.stream(
                "POST",
                OPENAI_REALTIME_CLIENT_SECRETS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept-Encoding": "identity",
                },
                json={"session": _session_identity(model)},
            ) as response,
        ):
            deadline.bind_response(response, client)
            response.raise_for_status()
            content = _read_bounded_response(response, deadline, MAX_TEST_RESPONSE_BYTES)
            payload = json.loads(content)
            secret = payload.get("value") if isinstance(payload, dict) else None
            if not isinstance(secret, str) or not secret.strip():
                raise ValueError("Invalid Realtime test response")
    except httpx.HTTPStatusError as exc:
        raise _provider_status_error(exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise AppError(
            502, "voice_provider_unavailable", "The voice provider is temporarily unavailable."
        ) from exc
    except (UnicodeError, ValueError) as exc:
        raise AppError(
            502,
            "voice_provider_invalid_response",
            "The voice provider returned an invalid response.",
        ) from exc


def create_realtime_call(
    *,
    api_key: str,
    instructions: str,
    model: str,
    voice: str,
    sdp: str,
    safety_identifier: str,
) -> str:
    """Exchange a browser SDP offer without exposing the OpenAI key."""
    session = {
        **_session_identity(model),
        "instructions": instructions,
        "max_output_tokens": 256,
        "tools": [],
        "audio": {
            "input": {"transcription": {"model": "gpt-realtime-whisper"}},
            "output": {"voice": voice},
        },
    }
    try:
        with (
            total_deadline_client(20) as (client, deadline),
            client.stream(
                "POST",
                OPENAI_REALTIME_CALLS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "OpenAI-Safety-Identifier": safety_identifier,
                    "Accept-Encoding": "identity",
                },
                files={
                    "sdp": (None, sdp),
                    "session": (None, json.dumps(session), "application/json"),
                },
            ) as response,
        ):
            deadline.bind_response(response, client)
            response.raise_for_status()
            content = _read_bounded_response(response, deadline, MAX_SDP_ANSWER_BYTES)
            answer = content.decode("utf-8", errors="strict")
            if not answer.startswith("v=0"):
                raise ValueError("Invalid Realtime SDP answer")
    except httpx.HTTPStatusError as exc:
        raise _provider_status_error(exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise AppError(
            502, "voice_provider_unavailable", "The voice provider is temporarily unavailable."
        ) from exc
    except ValueError as exc:
        raise AppError(
            502,
            "voice_provider_invalid_response",
            "The voice provider returned an invalid response.",
        ) from exc
    return answer


def _read_bounded_response(
    response: httpx.Response,
    deadline: TotalDeadline,
    max_response_bytes: int,
) -> bytes:
    _validate_identity_response(response, max_response_bytes)
    content = bytearray()
    for chunk in response.iter_bytes():
        deadline.check()
        if len(content) + len(chunk) > max_response_bytes:
            raise ValueError("Oversized Realtime provider response")
        content.extend(chunk)
    deadline.check()
    return bytes(content)


def _validate_identity_response(response: httpx.Response, max_response_bytes: int) -> None:
    response_headers = getattr(response, "headers", {})
    content_encoding = response_headers.get("content-encoding", "").strip().casefold()
    if content_encoding not in {"", "identity"}:
        raise ValueError("Encoded Realtime SDP answers are not accepted")
    declared_length = response_headers.get("content-length")
    if declared_length is not None and (
        not declared_length.isascii()
        or not declared_length.isdecimal()
        or int(declared_length) > max_response_bytes
    ):
        raise ValueError("Invalid Realtime SDP answer length")


def _session_identity(model: str) -> dict[str, object]:
    session: dict[str, object] = {"type": "realtime", "model": model}
    if model.startswith("gpt-realtime-2"):
        session["reasoning"] = {"effort": "low"}
    return session


def _provider_status_error(status_code: int) -> AppError:
    if status_code in {401, 403}:
        return AppError(
            503,
            "voice_provider_credentials_rejected",
            "OpenAI rejected the configured Realtime API key. Ask an administrator to replace it.",
        )
    if status_code == 404:
        return AppError(
            503,
            "voice_model_not_available",
            "The selected OpenAI Realtime model is unavailable to this project.",
        )
    if status_code == 429:
        return AppError(
            503,
            "voice_provider_rate_limited",
            "OpenAI Realtime has no available quota or is rate limited. Try again later.",
        )
    if 400 <= status_code < 500:
        return AppError(
            503,
            "voice_provider_configuration_rejected",
            "OpenAI rejected the Realtime session configuration. "
            "Check the selected model and voice.",
        )
    return AppError(
        502, "voice_provider_unavailable", "The voice provider is temporarily unavailable."
    )
