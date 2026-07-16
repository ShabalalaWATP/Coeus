import json

import httpx

from coeus.core.errors import AppError

OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
MAX_SDP_ANSWER_BYTES = 64 * 1024


def create_realtime_call(
    *, api_key: str, model: str, voice: str, sdp: str, safety_identifier: str
) -> str:
    """Exchange a browser SDP offer without exposing the OpenAI key."""
    session = {
        "type": "realtime",
        "model": model,
        "instructions": (
            "You are Istari, a concise assistant helping a customer draft a synthetic "
            "intelligence request. Ask one useful question at a time. Never request or infer "
            "classified, operational, personal, or real-world sensitive information."
        ),
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
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(
            502, "voice_provider_unavailable", "The voice provider is temporarily unavailable."
        ) from exc
    return answer
