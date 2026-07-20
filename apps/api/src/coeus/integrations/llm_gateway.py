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
from coeus.core.resource_limits import (
    MAX_INTAKE_OUTPUT_TOKENS,
    MAX_LLM_PROVIDER_RESPONSE_BYTES,
)
from coeus.integrations.provider_http import post_json

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
    instructions: str = ""
    max_output_tokens: int = MAX_INTAKE_OUTPUT_TOKENS
    structured_output: bool = False


class LlmGeneration(str):
    """Reply text with optional provider-reported token usage."""

    input_tokens: int | None
    output_tokens: int | None

    def __new__(
        cls,
        value: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> "LlmGeneration":
        instance = super().__new__(cls, value)
        instance.input_tokens = input_tokens
        instance.output_tokens = output_tokens
        return instance


def generate_text(call: LlmCall) -> LlmGeneration:
    """Send one prompt and return the reply text ('' when unparseable).

    Raises AppError 502 when the provider cannot be reached or answers with
    an error; callers decide whether to fall back to the mock provider.
    """
    url, headers, body = _request_for(call)
    label = PROVIDER_LABELS.get(call.provider, call.provider)
    try:
        payload = post_json(
            url,
            headers=headers,
            body=body,
            timeout=call.timeout,
            max_response_bytes=MAX_LLM_PROVIDER_RESPONSE_BYTES,
        )
    except httpx.HTTPError as exc:
        raise AppError(502, "llm_provider_unavailable", f"{label} is unavailable.") from exc
    except (UnicodeError, ValueError) as exc:
        raise AppError(
            502,
            "llm_provider_invalid_response",
            f"{label} returned an invalid response.",
        ) from exc
    input_tokens, output_tokens = _token_usage(call.provider, payload)
    return LlmGeneration(
        _reply_text(call.provider, payload),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _request_for(call: LlmCall) -> tuple[str, dict[str, str], dict[str, object]]:
    if not 1 <= call.max_output_tokens <= 4_096:
        raise AppError(422, "llm_output_limit_invalid", "The LLM output limit is invalid.")
    model = quote(call.model, safe="")
    if call.provider == "gemini_api":
        return (
            GEMINI_URL.format(model=model),
            {"x-goog-api-key": call.api_key},
            _google_body(call),
        )
    if call.provider == "openai_api":
        return (
            OPENAI_URL,
            {"Authorization": f"Bearer {call.api_key}"},
            _openai_body(call),
        )
    if call.provider == "vertex_ai":
        return (
            VERTEX_URL.format(model=model),
            {"x-goog-api-key": call.api_key},
            _google_body(call),
        )
    if call.provider == "bedrock":
        return (
            BEDROCK_URL.format(region=quote(call.region, safe=""), model=model),
            {"Authorization": f"Bearer {call.api_key}"},
            _bedrock_body(call),
        )
    raise AppError(422, "llm_provider_unknown", "The LLM provider is not supported.")


def _google_body(call: LlmCall) -> dict[str, object]:
    generation_config: dict[str, object] = {"maxOutputTokens": call.max_output_tokens}
    if call.structured_output:
        generation_config["responseMimeType"] = "application/json"
    body: dict[str, object] = {
        "contents": [{"parts": [{"text": call.prompt}]}],
        "generationConfig": generation_config,
    }
    if call.instructions:
        body["systemInstruction"] = {"parts": [{"text": call.instructions}]}
    return body


def _openai_body(call: LlmCall) -> dict[str, object]:
    messages: list[dict[str, str]] = []
    if call.instructions:
        messages.append({"role": "system", "content": call.instructions})
    messages.append({"role": "user", "content": call.prompt})
    body: dict[str, object] = {
        "model": call.model,
        "messages": messages,
        "max_completion_tokens": call.max_output_tokens,
    }
    if call.structured_output:
        body["response_format"] = {"type": "json_object"}
    return body


def _bedrock_body(call: LlmCall) -> dict[str, object]:
    body: dict[str, object] = {
        "messages": [{"role": "user", "content": [{"text": call.prompt}]}],
        "inferenceConfig": {"maxTokens": call.max_output_tokens},
    }
    if call.instructions:
        body["system"] = [{"text": call.instructions}]
    return body


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


def _token_usage(provider: str, payload: object) -> tuple[int | None, int | None]:
    if not isinstance(payload, dict):
        return None, None
    if provider in ("gemini_api", "vertex_ai"):
        usage = payload.get("usageMetadata", {})
        return _usage_values(usage, "promptTokenCount", "candidatesTokenCount")
    if provider == "openai_api":
        usage = payload.get("usage", {})
        return _usage_values(usage, "prompt_tokens", "completion_tokens")
    usage = payload.get("usage", {})
    return _usage_values(usage, "inputTokens", "outputTokens")


def _usage_values(usage: object, input_key: str, output_key: str) -> tuple[int | None, int | None]:
    if not isinstance(usage, dict):
        return None, None
    input_tokens = usage.get(input_key)
    output_tokens = usage.get(output_key)
    return (
        input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None,
        output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None,
    )
