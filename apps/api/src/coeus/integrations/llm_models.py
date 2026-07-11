"""Bounded discovery of text-generation models offered by providers."""

import httpx

from coeus.core.errors import AppError
from coeus.core.model_ids import clean_model_ids
from coeus.integrations.llm_gateway import PROVIDER_LABELS
from coeus.integrations.provider_http import get_json

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"

# OpenAI does not publish endpoint capabilities in the list response. Reject
# families known not to work with this app's text chat gateway, but do not use
# a frozen positive prefix list that would hide future text model families.
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
    "similarity",
    "instruct",
    "davinci",
    "babbage",
    "ada",
    "curie",
)


def discover_models(provider: str, api_key: str, timeout: int) -> tuple[str, ...]:
    """Return a safe, bounded catalogue or fail without changing app state."""
    if provider == "openai_api":
        payload = _get_json(
            provider,
            OPENAI_MODELS_URL,
            {"Authorization": f"Bearer {api_key}"},
            timeout,
        )
        return _openai_models(payload)
    if provider == "gemini_api":
        payload = _get_json(
            provider,
            GEMINI_MODELS_URL,
            {"x-goog-api-key": api_key},
            timeout,
        )
        return _gemini_models(payload)
    raise AppError(
        422,
        "refresh_not_supported",
        "Live model listing is not available for this provider. Add model IDs by hand instead.",
    )


def _get_json(provider: str, url: str, headers: dict[str, str], timeout: int) -> dict[str, object]:
    label = PROVIDER_LABELS.get(provider, provider)
    try:
        payload = get_json(url, headers=headers, timeout=timeout)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            raise AppError(
                422,
                "provider_credentials_rejected",
                f"{label} rejected the configured API key.",
            ) from exc
        if status == 429:
            raise AppError(
                503,
                "provider_rate_limited",
                f"{label} is rate limiting model discovery. Try again later.",
            ) from exc
        raise AppError(502, "llm_provider_unavailable", f"{label} is unavailable.") from exc
    except httpx.HTTPError as exc:
        raise AppError(502, "llm_provider_unavailable", f"{label} is unavailable.") from exc
    except ValueError as exc:
        raise _invalid_catalogue(label) from exc
    if not isinstance(payload, dict):
        raise _invalid_catalogue(label)
    return payload


def _openai_models(payload: dict[str, object]) -> tuple[str, ...]:
    entries = payload.get("data")
    if not isinstance(entries, list):
        raise _invalid_catalogue("OpenAI API")
    candidates = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if isinstance(model_id, str) and not any(
            token in model_id.casefold() for token in _OPENAI_NON_CHAT
        ):
            candidates.append(model_id)
    return _require_models(clean_model_ids(candidates), "OpenAI API")


def _gemini_models(payload: dict[str, object]) -> tuple[str, ...]:
    entries = payload.get("models")
    if not isinstance(entries, list):
        raise _invalid_catalogue("Gemini API")
    candidates = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        methods = entry.get("supportedGenerationMethods")
        name = entry.get("name")
        if isinstance(methods, list) and "generateContent" in methods and isinstance(name, str):
            candidates.append(name.strip().removeprefix("models/"))
    return _require_models(clean_model_ids(candidates), "Gemini API")


def _require_models(models: list[str], label: str) -> tuple[str, ...]:
    if not models:
        raise _invalid_catalogue(label)
    return tuple(models)


def _invalid_catalogue(label: str) -> AppError:
    return AppError(
        502,
        "provider_model_list_invalid",
        f"{label} returned an invalid or empty model catalogue.",
    )
