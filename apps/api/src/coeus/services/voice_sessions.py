import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.integrations.openai_realtime import create_realtime_call
from coeus.services.audit import AuditLog
from coeus.services.voice_admission import VoiceSessionAdmission
from coeus.services.voice_models import VoiceModelService

MAX_SDP_BYTES = 64 * 1024


@dataclass(frozen=True)
class VoiceSessionStart:
    answer: str
    token: UUID


class VoiceSessionService:
    def __init__(
        self,
        settings: Settings,
        voice_models: VoiceModelService,
        admission: VoiceSessionAdmission,
        audit_log: AuditLog,
    ) -> None:
        self._settings = settings
        self._voice_models = voice_models
        self._admission = admission
        self._audit_log = audit_log

    def create(self, user_id: UUID, sdp: str) -> VoiceSessionStart:
        state = self._voice_models.require_enabled()
        api_key = self._voice_models.api_key()
        if not api_key:
            raise AppError(409, "voice_provider_not_configured", "OpenAI voice is not configured.")
        token = self._admission.acquire(user_id)
        try:
            answer = create_realtime_call(
                api_key=api_key,
                model=state.model,
                voice=self._settings.openai_realtime_voice,
                sdp=sdp,
                safety_identifier=self._safety_identifier(user_id),
            )
            self._audit_log.record("voice_session_started", str(user_id), {"model": state.model})
        except Exception:
            self._admission.release(user_id, token)
            raise
        return VoiceSessionStart(answer, token)

    def release(self, user_id: UUID, token: UUID) -> None:
        if self._admission.release(user_id, token):
            self._audit_log.record("voice_session_ended", str(user_id), {})

    def _safety_identifier(self, user_id: UUID) -> str:
        message = b"coeus-openai-realtime-v1:" + user_id.bytes
        return hmac.new(
            self._settings.asset_token_secret.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
