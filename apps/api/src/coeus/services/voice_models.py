from dataclasses import dataclass

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.persistence.state_store import StateStore
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import EncryptedIntegrationSecretStore

VOICE_MODEL_NAMESPACE = "voice_model"
VOICE_CREDENTIAL_NAME = "voice:openai_realtime"


@dataclass(frozen=True)
class VoiceModelState:
    model: str
    available_models: tuple[str, ...]
    enabled: bool
    api_key_configured: bool


class VoiceModelService:
    """Application-wide OpenAI Realtime voice configuration."""

    def __init__(
        self,
        settings: Settings,
        audit_log: AuditLog,
        state_store: StateStore,
        secret_store: EncryptedIntegrationSecretStore | None = None,
    ) -> None:
        self._available = tuple(settings.available_openai_realtime_models)
        self._model = settings.openai_realtime_model
        self._enabled = False
        self._api_key: str | None = None
        self._audit_log = audit_log
        self._state_store = state_store
        self._secret_store = secret_store or EncryptedIntegrationSecretStore(state_store, settings)
        self._restore()

    def state(self) -> VoiceModelState:
        return VoiceModelState(
            model=self._model,
            available_models=self._available,
            enabled=self._enabled,
            api_key_configured=bool(self._api_key),
        )

    def configure(
        self, actor_user_id: str, actor_username: str, model: str, enabled: bool
    ) -> VoiceModelState:
        if model not in self._available:
            raise AppError(422, "voice_model_not_available", "The voice model is not available.")
        if enabled and not self._api_key:
            raise AppError(
                422,
                "voice_provider_not_configured",
                "Configure the dedicated OpenAI Realtime API key before enabling voice.",
            )
        previous = (self._model, self._enabled)
        self._model, self._enabled = model, enabled
        try:
            self._persist()
            self._audit_log.record(
                "voice_model_configured",
                actor_user_id,
                {"actor_username": actor_username, "model": model, "enabled": str(enabled)},
            )
        except Exception:
            self._model, self._enabled = previous
            self._persist()
            raise
        return self.state()

    def configure_api_key(
        self, actor_user_id: str, actor_username: str, api_key: str
    ) -> VoiceModelState:
        previous = self._api_key
        self._api_key = api_key
        try:
            self._persist()
            self._audit_log.record(
                "voice_api_key_configured",
                actor_user_id,
                {"actor_username": actor_username},
            )
        except Exception:
            self._api_key = previous
            self._persist()
            raise
        return self.state()

    def api_key(self) -> str | None:
        return self._api_key

    def require_enabled(self) -> VoiceModelState:
        state = self.state()
        if not state.enabled:
            raise AppError(409, "voice_not_enabled", "Realtime voice is not enabled.")
        if not state.api_key_configured:
            raise AppError(409, "voice_provider_not_configured", "OpenAI voice is not configured.")
        return state

    def _restore(self) -> None:
        stored = self._state_store.load(VOICE_MODEL_NAMESPACE) or {}
        model = stored.get("model")
        enabled = stored.get("enabled")
        if isinstance(model, str) and model in self._available:
            self._model = model
        if isinstance(enabled, bool):
            self._enabled = enabled
        self._api_key = self._secret_store.load(VOICE_CREDENTIAL_NAME)
        self._persist()

    def _persist(self) -> None:
        self._state_store.save(
            VOICE_MODEL_NAMESPACE, {"model": self._model, "enabled": self._enabled}
        )
        if self._api_key:
            self._secret_store.save(VOICE_CREDENTIAL_NAME, self._api_key)
        else:
            self._secret_store.clear(VOICE_CREDENTIAL_NAME)
