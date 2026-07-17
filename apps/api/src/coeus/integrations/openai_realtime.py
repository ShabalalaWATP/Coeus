import json

import httpx

from coeus.core.errors import AppError

OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
MAX_SDP_ANSWER_BYTES = 64 * 1024


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
        "type": "realtime",
        "model": model,
        "instructions": instructions,
        "audio": {
            "input": {"transcription": {"model": "gpt-realtime-whisper"}},
            "output": {"voice": voice},
        },
    }
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                OPENAI_REALTIME_CALLS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "OpenAI-Safety-Identifier": safety_identifier,
                },
                files={
                    "sdp": (None, sdp),
                    "session": (None, json.dumps(session), "application/json"),
                },
            )
            response.raise_for_status()
            answer = response.text
            if len(answer.encode("utf-8")) > MAX_SDP_ANSWER_BYTES or not answer.startswith("v=0"):
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
