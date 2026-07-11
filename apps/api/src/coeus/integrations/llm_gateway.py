"""Single HTTP gateway for every supported LLM provider.

All providers are key-based over plain HTTPS so no vendor SDKs are needed:
Gemini and Vertex AI (express mode) take the key in the ``x-goog-api-key``
header, OpenAI and Bedrock (long-term API keys) as a bearer token. Keys are
never placed in URLs. Callers build the prompt; this module only transports
it and extracts the reply text.
"""

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from coeus.core.errors import AppError

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
VERTEX_URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
BEDROCK_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/converse"

PROVIDER_LABELS = {
    "gemini_api": "Gemini API",
    "openai_api": "OpenAI API",
    "vertex_ai": "Vertex AI",
    "bedrock": "Bedrock",
}


@dataclass(frozen=True)
class LlmCall:
    provider: str
    model: str
    api_key: str
    prompt: str
    timeout: int
    region: str = ""


def generate_text(call: LlmCall) -> str:
    """Send one prompt and return the reply text ('' when unparseable).

    Raises AppError 502 when the provider cannot be reached or answers with
    an error; callers decide whether to fall back to the mock provider.
    """
    url, headers, body = _request_for(call)
    label = PROVIDER_LABELS.get(call.provider, call.provider)
    try:
        with httpx.Client(timeout=call.timeout) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(502, "llm_provider_unavailable", f"{label} is unavailable.") from exc
    return _reply_text(call.provider, payload)


def _request_for(call: LlmCall) -> tuple[str, dict[str, str], dict[str, object]]:
    model = quote(call.model, safe="")
    if call.provider == "gemini_api":
        return (
            GEMINI_URL.format(model=model),
            {"x-goog-api-key": call.api_key},
            {"contents": [{"parts": [{"text": call.prompt}]}]},
        )
    if call.provider == "openai_api":
        return (
            OPENAI_URL,
            {"Authorization": f"Bearer {call.api_key}"},
            {"model": call.model, "messages": [{"role": "user", "content": call.prompt}]},
        )
    if call.provider == "vertex_ai":
        return (
            VERTEX_URL.format(model=model),
            {"x-goog-api-key": call.api_key},
            {"contents": [{"parts": [{"text": call.prompt}]}]},
        )
    if call.provider == "bedrock":
        return (
            BEDROCK_URL.format(region=quote(call.region, safe=""), model=model),
            {"Authorization": f"Bearer {call.api_key}"},
            {"messages": [{"role": "user", "content": [{"text": call.prompt}]}]},
        )
    raise AppError(422, "llm_provider_unknown", "The LLM provider is not supported.")


def _reply_text(provider: str, payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    if provider in ("gemini_api", "vertex_ai"):
        return _candidate_text(payload)
    if provider == "openai_api":
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        return str(content or "").strip()
    output = payload.get("output", {})
    message = output.get("message", {}) if isinstance(output, dict) else {}
    parts = message.get("content", []) if isinstance(message, dict) else []
    if not isinstance(parts, list):
        return ""
    return " ".join(
        str(part.get("text", "")).strip() for part in parts if isinstance(part, dict)
    ).strip()


def _candidate_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list):
        return ""
    return " ".join(
        str(part.get("text", "")).strip() for part in parts if isinstance(part, dict)
    ).strip()
