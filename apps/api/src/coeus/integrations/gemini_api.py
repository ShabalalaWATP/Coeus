from typing import Protocol
from urllib.parse import quote

import httpx

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.services.intake import MockLlmProvider
from coeus.services.intake_standard import next_elicitation

GEMINI_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiRuntimeConfig(Protocol):
    def active_model(self) -> str:
        pass

    def api_key(self) -> str | None:
        pass


class GeminiApiLlmProvider:
    def __init__(
        self,
        settings: Settings,
        runtime_config: GeminiRuntimeConfig | None = None,
    ) -> None:
        self._settings = settings
        self._runtime_config = runtime_config
        self._timeout = settings.gemini_api_timeout_seconds
        self._fallback = MockLlmProvider()

    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        api_key = self._api_key()
        if api_key is None:
            raise AppError(
                409,
                "llm_provider_not_configured",
                "Gemini API key is not configured.",
            )
        prompt = _prompt(intake, safety_flags)
        url = GEMINI_GENERATE_CONTENT_URL.format(model=quote(self._model(), safe=""))
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    headers={"x-goog-api-key": api_key},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(502, "llm_provider_unavailable", "Gemini API is unavailable.") from exc
        text = _candidate_text(payload)
        return text or self._fallback.build_assistant_message(intake, safety_flags)

    def _model(self) -> str:
        if self._runtime_config is not None:
            return self._runtime_config.active_model()
        return self._settings.gemini_api_model

    def _api_key(self) -> str | None:
        if self._runtime_config is not None:
            return self._runtime_config.api_key()
        return self._settings.gemini_api_key


def _prompt(intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
    missing = ", ".join(intake.missing_information) or "none"
    entry = next_elicitation(intake.missing_information)
    if entry is None:
        goal = (
            "All required details are captured. Confirm the request is complete "
            "and invite the requester to review the details and press Submit."
        )
    else:
        goal = (
            f"Ask one natural question to capture the missing '{entry.label}' "
            f"detail. Why it is needed: {entry.rationale} "
            f"A good phrasing: {entry.question}"
        )
    return "\n".join(
        (
            "You are Istari's secure intake assistant, helping a customer shape",
            "a request for information through a natural conversation.",
            "Use only the extracted fields below; do not invent operational facts.",
            "Sound like a helpful colleague, never like a form: do not mention",
            "required fields, checklists, counts or completeness.",
            "Briefly acknowledge what the customer just gave you, then follow the",
            "goal. Ask about exactly one missing detail per reply, never several.",
            "Reply in at most two short sentences for the requester.",
            f"Goal: {goal}",
            f"Title: {intake.title or 'missing'}",
            f"Description: {intake.description or 'missing'}",
            f"Operational question: {intake.operational_question or 'missing'}",
            f"Region: {intake.area_or_region or 'missing'}",
            f"Time period: {intake.time_period_start or 'missing'}",
            f"Priority: {intake.priority or 'missing'}",
            f"Supported operation: {intake.supported_operation or 'missing'}",
            f"Urgency justification: {intake.urgency_justification or 'missing'}",
            f"Latest useful time: {intake.deadline or 'missing'}",
            f"Requesting unit: {intake.requesting_unit or 'missing'}",
            f"Disciplines: {intake.intelligence_disciplines or 'missing'}",
            f"Output format: {intake.required_output_format or 'missing'}",
            f"Success criteria: {intake.customer_success_criteria or 'missing'}",
            f"Missing fields: {missing}",
            f"Safety flags: {', '.join(safety_flags) or 'none'}",
        )
    )


def _candidate_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list):
        return ""
    return " ".join(str(part.get("text", "")).strip() for part in parts if isinstance(part, dict))
