from dataclasses import dataclass

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.services.audit import AuditLog


@dataclass(frozen=True)
class AiModelState:
    provider: str
    active_model: str
    available_models: tuple[str, ...]


class AiModelService:
    """Administrator-controlled selection of the Gemini model used by agents.

    Locally the LLM provider stays `mock`; the selection records which Gemini
    model deployed environments should call through Vertex AI.
    """

    def __init__(self, settings: Settings, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._provider = settings.llm_provider
        self._available_models = tuple(settings.available_gemini_models)
        default_model = settings.gemma_vertex_model
        self._active_model = (
            default_model if default_model in self._available_models else self._available_models[0]
        )

    def state(self) -> AiModelState:
        return AiModelState(
            provider=self._provider,
            active_model=self._active_model,
            available_models=self._available_models,
        )

    def select(self, actor_user_id: str, model: str) -> AiModelState:
        if model not in self._available_models:
            raise AppError(422, "model_not_available", "The requested model is not available.")
        previous = self._active_model
        self._active_model = model
        self._audit_log.record(
            "ai_model_changed",
            actor_user_id,
            {"previous_model": previous, "active_model": model},
        )
        return self.state()
