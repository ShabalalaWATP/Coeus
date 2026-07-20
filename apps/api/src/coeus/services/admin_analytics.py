from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from coeus.application.ports.outbox import OutboxDispatcherPort
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.outbox import OutboxEventNotFound, ReplayDisposition
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.admission_metrics import AdmissionMetrics
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditEvent, AuditLog
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.voice_models import VoiceModelService, VoiceModelState

WINDOW_DAYS = 30
logger = get_logger(__name__)
SECURITY_EVENTS = frozenset({"auth_throttled", "login_failure", "password_change_failed"})
CONFIGURATION_EVENTS = frozenset(
    {
        "ai_api_key_configured",
        "ai_custom_model_added",
        "ai_model_changed",
        "ai_models_refreshed",
        "ai_provider_changed",
        "search_embedding_configuration_changed",
        "search_embedding_key_configured",
        "user_clearance_updated",
        "user_disabled",
        "user_enabled",
        "user_password_reset",
        "user_roles_updated",
        "voice_api_key_configured",
        "voice_model_configured",
    }
)


@dataclass(frozen=True)
class RoleCount:
    role: str
    count: int


@dataclass(frozen=True)
class UserAnalytics:
    total: int
    active: int
    disabled: int
    password_reset_required: int
    pending_registrations: int
    active_users_30d: int
    role_counts: tuple[RoleCount, ...]


@dataclass(frozen=True)
class AssistantAnalytics:
    provider: str
    model: str
    api_key_configured: bool
    chat_turns_30d: int


@dataclass(frozen=True)
class SearchAnalytics:
    provider: str
    model: str
    api_key_configured: bool
    index_status: str
    search_runs_30d: int
    indexed_products: int
    indexed_passages: int
    indexed_requests: int
    failed_assets: int


@dataclass(frozen=True)
class VoiceAnalytics:
    model: str
    enabled: bool
    api_key_configured: bool
    sessions_started_30d: int
    users_30d: int


@dataclass(frozen=True)
class AuditAnalytics:
    window_days: int
    retained_events: int
    events_30d: int
    login_successes_30d: int
    login_failures_30d: int
    security_events_30d: int
    configuration_changes_30d: int
    coverage_starts_at: datetime | None
    retention_limit_reached: bool


@dataclass(frozen=True)
class ProcessAnalytics:
    remote_requests_admitted: int
    remote_requests_denied: int


@dataclass(frozen=True)
class OutboxAnalytics:
    configured: bool
    available: bool
    pending_count: int
    retrying_count: int
    dead_letter_count: int
    oldest_pending_age_seconds: int | None


@dataclass(frozen=True)
class AdminAnalyticsDashboard:
    generated_at: datetime
    users: UserAnalytics
    assistant: AssistantAnalytics
    search: SearchAnalytics
    voice: VoiceAnalytics
    audit: AuditAnalytics
    process: ProcessAnalytics
    outbox: OutboxAnalytics


class AdminAnalyticsService:
    """Aggregate platform administration signals without operational content."""

    def __init__(
        self,
        users: SeedUserRepository,
        registrations: RegistrationRepository,
        audit_log: AuditLog,
        ai_models: AiModelService,
        search: SearchConfigurationService,
        voice: VoiceModelService,
        admission_metrics: AdmissionMetrics,
    ) -> None:
        self._users = users
        self._registrations = registrations
        self._audit_log = audit_log
        self._ai_models = ai_models
        self._search = search
        self._voice = voice
        self._admission_metrics = admission_metrics

    def dashboard(
        self,
        actor: UserAccount,
        outbox: OutboxDispatcherPort | None = None,
    ) -> AdminAnalyticsDashboard:
        if Permission.ANALYTICS_VIEW_GLOBAL not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        now = datetime.now(UTC)
        all_events = self._audit_log.list_events()
        events = tuple(event for event in all_events if event.occurred_at >= _cutoff(now))
        counts = Counter(event.event_type for event in events)
        users = self._users.list_users()
        ai_state = self._ai_models.state()
        search_state = self._search.state()
        voice_state = self._voice.state()
        process = self._admission_metrics.snapshot()
        return AdminAnalyticsDashboard(
            generated_at=now,
            users=_user_analytics(users, self._registrations.pending_count(), events),
            assistant=AssistantAnalytics(
                provider=ai_state.provider,
                model=ai_state.active_model,
                api_key_configured=ai_state.api_key_configured,
                chat_turns_30d=counts["ticket_chat_message_received"],
            ),
            search=SearchAnalytics(
                provider=search_state.provider,
                model=search_state.model,
                api_key_configured=search_state.api_key_configured,
                index_status=search_state.index_status,
                search_runs_30d=counts["rfi_search_completed"],
                indexed_products=search_state.product_count,
                indexed_passages=search_state.chunk_count,
                indexed_requests=search_state.ticket_count,
                failed_assets=search_state.failed_asset_count,
            ),
            voice=_voice_analytics(voice_state, events),
            audit=_audit_analytics(self._audit_log, all_events, counts),
            process=ProcessAnalytics(
                remote_requests_admitted=process.get("provider.admitted", 0),
                remote_requests_denied=sum(
                    value for key, value in process.items() if key.startswith("provider.denied_")
                ),
            ),
            outbox=_outbox_analytics(outbox),
        )

    def replay_dead_letter(
        self,
        actor: UserAccount,
        outbox: OutboxDispatcherPort,
        event_id: UUID,
        reason: str,
    ) -> ReplayDisposition:
        if Permission.SYSTEM_CONFIGURE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        normalised_reason = reason.strip()
        if not 5 <= len(normalised_reason) <= 500:
            raise AppError(
                422,
                "invalid_replay_reason",
                "Replay reason must contain between 5 and 500 characters.",
            )
        self._audit_log.record(
            "outbox_dead_letter_replay_authorised",
            str(actor.user_id),
            {
                "event_id": str(event_id),
                "reason": normalised_reason,
            },
        )
        try:
            disposition = outbox.replay_dead_letter(event_id)
        except OutboxEventNotFound as exc:
            raise AppError(404, "outbox_event_not_found", "Outbox event was not found.") from exc
        return disposition


def _cutoff(now: datetime) -> datetime:
    return now - timedelta(days=WINDOW_DAYS)


def _outbox_analytics(outbox: OutboxDispatcherPort | None) -> OutboxAnalytics:
    if outbox is None:
        return OutboxAnalytics(False, False, 0, 0, 0, None)
    try:
        status = outbox.status()
    except Exception:
        logger.warning("outbox_status_failed")
        return OutboxAnalytics(True, False, 0, 0, 0, None)
    return OutboxAnalytics(
        configured=True,
        available=True,
        pending_count=status.pending_count,
        retrying_count=status.retrying_count,
        dead_letter_count=status.dead_letter_count,
        oldest_pending_age_seconds=status.oldest_pending_age_seconds,
    )


def _user_analytics(
    users: tuple[UserAccount, ...], pending: int, events: tuple[AuditEvent, ...]
) -> UserAnalytics:
    roles = Counter(str(role) for user in users for role in user.roles)
    active_users = {
        event.actor_user_id
        for event in events
        if event.event_type == "login_success" and event.actor_user_id is not None
    }
    return UserAnalytics(
        total=len(users),
        active=sum(user.is_active for user in users),
        disabled=sum(not user.is_active for user in users),
        password_reset_required=sum(user.password_reset_required for user in users),
        pending_registrations=pending,
        active_users_30d=len(active_users),
        role_counts=tuple(RoleCount(role, count) for role, count in sorted(roles.items())),
    )


def _voice_analytics(state: VoiceModelState, events: tuple[AuditEvent, ...]) -> VoiceAnalytics:
    starts = tuple(event for event in events if event.event_type == "voice_session_started")
    return VoiceAnalytics(
        model=state.model,
        enabled=state.enabled,
        api_key_configured=state.api_key_configured,
        sessions_started_30d=len(starts),
        users_30d=len({event.actor_user_id for event in starts if event.actor_user_id}),
    )


def _audit_analytics(
    audit_log: AuditLog, events: tuple[AuditEvent, ...], counts: Counter[str]
) -> AuditAnalytics:
    return AuditAnalytics(
        window_days=WINDOW_DAYS,
        retained_events=len(events),
        events_30d=sum(counts.values()),
        login_successes_30d=counts["login_success"],
        login_failures_30d=counts["login_failure"],
        security_events_30d=sum(counts[event] for event in SECURITY_EVENTS),
        configuration_changes_30d=sum(counts[event] for event in CONFIGURATION_EVENTS),
        coverage_starts_at=min((event.occurred_at for event in events), default=None),
        retention_limit_reached=len(events) >= audit_log.retention_limit,
    )
