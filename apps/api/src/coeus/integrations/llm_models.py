"""Discover the models each provider currently offers.

Live listing is available for OpenAI and Gemini over the same key-based
HTTPS the gateway uses, so the selectable set stays current as vendors ship
new models. Vertex AI and Bedrock do not expose a model list to the
express/runtime keys we hold, so callers fall back to the curated list plus
any model ids an administrator adds by hand.
"""

import httpx

from coeus.core.errors import AppError
from coeus.integrations.llm_gateway import PROVIDER_LABELS

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"

# OpenAI ids containing any of these are not chat-completion models.
_OPENAI_NON_CHAT = (
    "embedding",
    "whisper",
    "tts",
    "dall-e",
    "audio",
    "image",
    "moderation",
    "realtime",
    "transcribe",
    "search",
    "similarity",
    "davinci",
    "babbage",
    "ada",
    "curie",
)
_OPENAI_CHAT_PREFIXES = ("gpt", "o1", "o3", "o4", "chatgpt")


def discover_models(provider: str, api_key: str, timeout: int) -> tuple[str, ...]:
    """Return the chat models a provider currently offers to this key.

    Raises AppError 422 for providers without a usable listing endpoint and
    502 when the provider cannot be reached.
    """
    if provider == "openai_api":
        headers = {"Authorization": f"Bearer {api_key}"}
        return _openai_models(_get_json(provider, OPENAI_MODELS_URL, headers, timeout))
    if provider == "gemini_api":
        headers = {"x-goog-api-key": api_key}
        return _gemini_models(_get_json(provider, GEMINI_MODELS_URL, headers, timeout))
    raise AppError(
        422,
        "refresh_not_supported",
        "Live model listing is not available for this provider. Add model ids by hand instead.",
    )


def _get_json(provider: str, url: str, headers: dict[str, str], timeout: int) -> dict[str, object]:
    label = PROVIDER_LABELS.get(provider, provider)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(502, "llm_provider_unavailable", f"{label} is unavailable.") from exc
    return payload if isinstance(payload, dict) else {}


def _openai_models(payload: dict[str, object]) -> tuple[str, ...]:
    entries = payload.get("data", [])
    ids: set[str] = set()
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id", "")).strip()
            lowered = model_id.lower()
            if not model_id or any(token in lowered for token in _OPENAI_NON_CHAT):
                continue
            if lowered.startswith(_OPENAI_CHAT_PREFIXES):
                ids.add(model_id)
    return tuple(sorted(ids))


def _gemini_models(payload: dict[str, object]) -> tuple[str, ...]:
    entries = payload.get("models", [])
    ids: set[str] = set()
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            methods = entry.get("supportedGenerationMethods", [])
            if not isinstance(methods, list) or "generateContent" not in methods:
                continue
            name = str(entry.get("name", "")).strip().removeprefix("models/")
            if name:
                ids.add(name)
    return tuple(sorted(ids))
